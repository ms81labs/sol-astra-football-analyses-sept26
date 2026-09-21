from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import socket
import sys
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.review_io import (
    REVIEW_UPDATE_LOCK,
    ReviewWriteError,
    ReviewWriteOutcomeUncertain,
    read_review_bytes,
    write_json_atomic as _write_json_atomic,
)
from backend.scripts.review_http import (
    HttpRequestError,
    loopback_host,
    read_json_payload,
    read_regular_file,
)
from backend.scripts.run_v7_1_positive_diversity_manual_review_resolution import (  # noqa: E402
    run_v7_1_positive_diversity_manual_review_resolution,
)

DEFAULT_CANDIDATE_ROOT = (
    DEFAULT_STORAGE_ROOT / "trained_detector_candidates" / "touchline_detector_candidate_v7"
)
DEFAULT_UI_ROOT = REPO_ROOT / "backend" / "review_ui" / "v7_1_positive_diversity_review"
MIN_BBOX_SIZE_PX = 4.0
MAX_BBOX_SIZE_PX = 60.0

POSITIVE_STATUS = "reviewed_positive_ball"
NEGATIVE_STATUS = "reviewed_not_ball"
UNCLEAR_STATUS = "review_deferred_unclear"
DUPLICATE_STATUS = "duplicate_or_near_duplicate"
BAD_FRAME_STATUS = "bad_crop_or_unusable_frame"
PENDING_STATUS = "pending_review"
ALLOWED_STATUSES = {
    POSITIVE_STATUS,
    NEGATIVE_STATUS,
    UNCLEAR_STATUS,
    DUPLICATE_STATUS,
    BAD_FRAME_STATUS,
    PENDING_STATUS,
}


class ReviewUpdateError(ValueError):
    pass


def _overlay_path(candidate_root: Path) -> Path:
    candidate_root = Path(candidate_root)
    for dirname in (
        "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1",
        "v7_1_positive_candidate_mining_expansion_v2",
        "v7_1_positive_candidate_mining_expansion_v1",
    ):
        overlay_path = candidate_root / dirname / "corrected_label_overlay.json"
        if overlay_path.exists():
            return overlay_path
    return candidate_root / "v7_1_positive_candidate_mining_expansion_v1" / "corrected_label_overlay.json"


def _overlay_dir_name(candidate_root: Path) -> str:
    return _overlay_path(candidate_root).parent.name


def _min_new_reviewed_positives(candidate_root: Path) -> int:
    summary_path = _overlay_path(candidate_root).parent / "v7_1_positive_candidate_mining_expansion_summary.json"
    summary = _load_json_dict(summary_path) if summary_path.exists() else {}
    previous_count = int(summary.get("previousReviewedPositiveSourceCount") or 34)
    return max(1, 120 - previous_count)


def _load_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(read_review_bytes(path))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ReviewUpdateError("invalid_review_document") from None
    except OSError:
        raise ReviewWriteError("review_write_failed") from None
    if not isinstance(payload, dict):
        raise ReviewUpdateError("invalid_review_document")
    return payload


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_bbox_payload(bbox: object) -> bool:
    if not isinstance(bbox, dict):
        return False
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    if None in {x1, y1, x2, y2}:
        return False
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    width = x2 - x1
    height = y2 - y1
    return x1 >= 0 and y1 >= 0 and MIN_BBOX_SIZE_PX <= width <= MAX_BBOX_SIZE_PX and MIN_BBOX_SIZE_PX <= height <= MAX_BBOX_SIZE_PX


def _normalize_bbox(bbox: object) -> dict[str, float] | None:
    if not _valid_bbox_payload(bbox):
        return None
    assert isinstance(bbox, dict)
    return {
        "x1": float(bbox["x1"]),
        "y1": float(bbox["y1"]),
        "x2": float(bbox["x2"]),
        "y2": float(bbox["y2"]),
    }


def _review_items(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    value = overlay.get("reviewItems")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ReviewUpdateError("invalid_review_items")
    return [dict(item) for item in value]


def summarize_overlay(overlay: dict[str, Any]) -> dict[str, int]:
    items = _review_items(overlay)
    counts = {status: 0 for status in ALLOWED_STATUSES}
    for item in items:
        status = str(item.get("reviewStatus") or "")
        if status in counts:
            counts[status] += 1
    return {
        "reviewItemCount": len(items),
        "pendingReviewItemCount": counts[PENDING_STATUS],
        "newReviewedPositiveRowCount": counts[POSITIVE_STATUS],
        "reviewedNotBallCount": counts[NEGATIVE_STATUS],
        "reviewDeferredUnclearCount": counts[UNCLEAR_STATUS],
        "duplicateOrNearDuplicateCount": counts[DUPLICATE_STATUS],
        "badCropOrUnusableFrameCount": counts[BAD_FRAME_STATUS],
        "resolvedReviewItemCount": len(items) - counts[PENDING_STATUS],
    }


def _image_url(path: object) -> str | None:
    if not path:
        return None
    return f"/source-image?path={quote(str(path))}"


def load_review_state(*, candidate_root: Path = DEFAULT_CANDIDATE_ROOT) -> dict[str, Any]:
    overlay = _load_json_dict(_overlay_path(Path(candidate_root)))
    items = sorted(
        _review_items(overlay),
        key=lambda item: (str(item.get("candidateKind") or ""), int(item.get("frameIndex") or 0), str(item.get("candidateId") or "")),
    )
    enriched = [
        {
            **item,
            "frameImageUrl": _image_url(item.get("reviewFrameImagePath")),
            "cropImageUrl": _image_url(item.get("reviewCropImagePath")),
        }
        for item in items
    ]
    return {
        "summary": summarize_overlay({**overlay, "reviewItems": items}),
        "reviewItems": enriched,
        "overlayPath": str(_overlay_path(Path(candidate_root))),
    }


def _recount_overlay(overlay: dict[str, Any]) -> None:
    summary = summarize_overlay(overlay)
    overlay.update(
        {
            "reviewItemCount": summary["reviewItemCount"],
            "pendingReviewCount": summary["pendingReviewItemCount"],
            "reviewedPositiveCount": summary["newReviewedPositiveRowCount"],
            "reviewedNotBallCount": summary["reviewedNotBallCount"],
            "reviewDeferredUnclearCount": summary["reviewDeferredUnclearCount"],
            "duplicateOrNearDuplicateCount": summary["duplicateOrNearDuplicateCount"],
            "badCropOrUnusableFrameCount": summary["badCropOrUnusableFrameCount"],
        }
    )


def update_review_item(
    *,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    candidate_id: str,
    review_status: str,
    source_frame_bbox: object = None,
    bbox_source: str | None = None,
    original_candidate_bbox_was_off_target: bool | None = None,
    visibility_class: str | None = None,
    context_tags: list[str] | None = None,
    rejection_reason: str | None = None,
    review_notes: str | None = None,
) -> dict[str, Any]:
    if review_status not in ALLOWED_STATUSES:
        raise ReviewUpdateError("unknown_review_status")
    if review_status == POSITIVE_STATUS and not _valid_bbox_payload(source_frame_bbox):
        raise ReviewUpdateError("positive_requires_valid_source_frame_bbox")
    if review_status in {NEGATIVE_STATUS, UNCLEAR_STATUS, DUPLICATE_STATUS, BAD_FRAME_STATUS} and not rejection_reason:
        raise ReviewUpdateError("non_positive_requires_rejection_reason")

    with REVIEW_UPDATE_LOCK:
        overlay_path = _overlay_path(Path(candidate_root))
        overlay = _load_json_dict(overlay_path)
        items = _review_items(overlay)
        matched = False
        for item in items:
            if str(item.get("candidateId") or "") != str(candidate_id):
                continue
            matched = True
            item["reviewStatus"] = review_status
            if review_notes is not None:
                item["reviewNotes"] = review_notes
            if review_status == POSITIVE_STATUS:
                item["sourceFrameBbox"] = _normalize_bbox(source_frame_bbox)
                item["bboxSource"] = bbox_source or "manual_corrected_from_off_bbox_candidate"
                item["originalCandidateBboxWasOffTarget"] = (
                    bool(original_candidate_bbox_was_off_target)
                    if original_candidate_bbox_was_off_target is not None
                    else item.get("candidateKind") == "off_bbox_visible_ball_correction_queue"
                )
                item["visibilityClass"] = visibility_class or "clear"
                item["contextTags"] = context_tags if isinstance(context_tags, list) else ["small_ball"]
                item["trainingEligibility"] = "eligible_positive_truth"
                item.pop("rejectionReason", None)
            elif review_status == PENDING_STATUS:
                item["trainingEligibility"] = "pending_review"
                item.pop("rejectionReason", None)
            else:
                item["rejectionReason"] = rejection_reason
                item["trainingEligibility"] = "evidence_only_not_positive_training_truth"
            break
        if not matched:
            raise ReviewUpdateError("review_item_not_found")

        overlay["reviewItems"] = items
        _recount_overlay(overlay)
        _write_json_atomic(overlay_path, overlay)
        return {"summary": summarize_overlay(overlay), "reviewItem": item}


def run_resolution_gate(*, storage_root: Path = DEFAULT_STORAGE_ROOT, candidate_name: str = "touchline_detector_candidate_v7") -> dict[str, Any]:
    candidate_root = Path(storage_root) / "trained_detector_candidates" / candidate_name
    return run_v7_1_positive_diversity_manual_review_resolution(
        storage_root=Path(storage_root),
        candidate_name=candidate_name,
        output_dir_name="v7_1_positive_diversity_manual_review_resolution_v2",
        overlay_dir_name=_overlay_dir_name(candidate_root),
        overlay_file_name="corrected_label_overlay.json",
        summary_file_name="v7_1_positive_candidate_mining_expansion_summary.json",
        batch_name="v7_1_positive_diversity_manual_review_resolution_v2",
        next_self="v7_1_positive_diversity_manual_review_resolution_v2",
        next_mining="v7_1_positive_candidate_mining_expansion_v2",
        min_new_reviewed_positives=_min_new_reviewed_positives(candidate_root),
        attempt_approach_family="corrected_bbox_positive_review_resolution",
    )


def _json_response(handler: BaseHTTPRequestHandler, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _error_response(handler: BaseHTTPRequestHandler, error: str, status: HTTPStatus) -> None:
    _json_response(handler, {"error": error}, status)


def _serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    body = read_regular_file(path)
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def build_handler(*, candidate_root: Path, ui_root: Path):
    candidate_root = Path(candidate_root)
    ui_root = Path(ui_root)

    class V71PositiveDiversityReviewHandler(BaseHTTPRequestHandler):
        timeout = 5.0

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path in {"/", "/index.html"}:
                    _serve_file(self, ui_root / "index.html")
                    return
                if parsed.path == "/favicon.ico":
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                    return
                if parsed.path == "/api/review-state":
                    _json_response(self, load_review_state(candidate_root=candidate_root))
                    return
                if parsed.path == "/api/summary":
                    _json_response(self, load_review_state(candidate_root=candidate_root)["summary"])
                    return
                if parsed.path == "/source-image":
                    requested = parse_qs(parsed.query).get("path", [""])[0]
                    approved = {
                        str(item[field])
                        for item in _review_items(_load_json_dict(_overlay_path(candidate_root)))
                        for field in ("reviewFrameImagePath", "reviewCropImagePath")
                        if item.get(field)
                    }
                    content_type = mimetypes.guess_type(requested)[0] or ""
                    if requested not in approved or not content_type.startswith("image/"):
                        raise FileNotFoundError(requested)
                    _serve_file(self, Path(requested))
                    return
                _error_response(self, "not_found", HTTPStatus.NOT_FOUND)
            except FileNotFoundError:
                _error_response(self, "not_found", HTTPStatus.NOT_FOUND)
            except Exception as exc:  # pragma: no cover
                _error_response(self, str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = read_json_payload(self)
                if parsed.path.startswith("/api/review-items/"):
                    result = update_review_item(
                        candidate_root=candidate_root,
                        candidate_id=unquote(parsed.path.removeprefix("/api/review-items/")),
                        review_status=str(payload.get("reviewStatus") or ""),
                        source_frame_bbox=payload.get("sourceFrameBbox"),
                        bbox_source=payload.get("bboxSource"),
                        original_candidate_bbox_was_off_target=payload.get("originalCandidateBboxWasOffTarget"),
                        visibility_class=payload.get("visibilityClass"),
                        context_tags=payload.get("contextTags"),
                        rejection_reason=payload.get("rejectionReason"),
                        review_notes=payload.get("reviewNotes"),
                    )
                    _json_response(self, result)
                    return
                if parsed.path == "/api/run-resolution":
                    _json_response(self, run_resolution_gate(storage_root=Path(candidate_root).parents[1], candidate_name=Path(candidate_root).name))
                    return
                _error_response(self, "not_found", HTTPStatus.NOT_FOUND)
            except HttpRequestError as exc:
                self.close_connection = True
                _error_response(self, str(exc), exc.status)
            except ReviewWriteOutcomeUncertain:
                _error_response(self, "review_write_outcome_uncertain_do_not_retry", HTTPStatus.CONFLICT)
            except ReviewWriteError:
                _error_response(self, "review_write_failed", HTTPStatus.SERVICE_UNAVAILABLE)
            except ReviewUpdateError as exc:
                _error_response(self, str(exc), HTTPStatus.BAD_REQUEST)
            except json.JSONDecodeError:
                _error_response(self, "invalid_json_body", HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # pragma: no cover
                _error_response(self, str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

        def log_message(self, format: str, *args: object) -> None:
            return

    return V71PositiveDiversityReviewHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a localhost UI for v7.1 positive diversity corrected-label review.")
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--ui-root", type=Path, default=DEFAULT_UI_ROOT)
    parser.add_argument("--host", type=loopback_host, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--dry-run", action="store_true", help="Validate artifacts and print the review summary without serving.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = load_review_state(candidate_root=args.candidate_root)
    if args.dry_run:
        print(json.dumps(state["summary"], indent=2, sort_keys=True))
        return 0

    class LocalServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if ":" in args.host else socket.AF_INET

    server = LocalServer(
        (args.host, args.port),
        build_handler(candidate_root=args.candidate_root, ui_root=args.ui_root),
    )
    url_host = f"[{args.host}]" if ":" in args.host else args.host
    print(f"Serving v7.1 positive diversity review UI at http://{url_host}:{server.server_port}/")
    print(json.dumps(state["summary"], indent=2, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped v7.1 review UI server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
