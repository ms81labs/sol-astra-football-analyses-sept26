from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import socket
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]

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
from backend.scripts.run_football_external_soccernet_detector_miss_manual_review_resolution import (  # noqa: E402
    run_football_external_soccernet_detector_miss_manual_review_resolution,
)

DEFAULT_CANDIDATE_ROOT = (
    DEFAULT_STORAGE_ROOT / "trained_detector_candidates" / "touchline_detector_candidate_v7"
)
DEFAULT_UI_ROOT = REPO_ROOT / "backend" / "review_ui" / "football_external_soccernet_detector_miss_review"

POSITIVE_STATUS = "reviewed_real_detector_miss_positive"
HIT_OR_NOT_MISS_STATUS = "reviewed_detector_hit_or_not_miss"
NOT_BALL_STATUS = "reviewed_not_ball_or_out_of_play"
UNCLEAR_STATUS = "review_deferred_unclear"
BAD_FRAME_STATUS = "bad_frame_or_unusable"
PENDING_STATUS = "pending_review"
ALLOWED_STATUSES = {
    POSITIVE_STATUS,
    HIT_OR_NOT_MISS_STATUS,
    NOT_BALL_STATUS,
    UNCLEAR_STATUS,
    BAD_FRAME_STATUS,
    PENDING_STATUS,
}
MIN_BBOX_SIZE_PX = 2.0
MAX_BBOX_SIZE_PX = 80.0


class ReviewUpdateError(ValueError):
    pass


def _overlay_path(candidate_root: Path) -> Path:
    return (
        Path(candidate_root)
        / "football_external_soccernet_detector_miss_capture_and_label_queue_v1"
        / "soccernet_detector_miss_review_overlay.json"
    )


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
        "reviewedRealDetectorMissPositiveCount": counts[POSITIVE_STATUS],
        "reviewedDetectorHitOrNotMissCount": counts[HIT_OR_NOT_MISS_STATUS],
        "reviewedNotBallOrOutOfPlayCount": counts[NOT_BALL_STATUS],
        "reviewDeferredUnclearCount": counts[UNCLEAR_STATUS],
        "badFrameOrUnusableCount": counts[BAD_FRAME_STATUS],
        "resolvedReviewItemCount": len(items) - counts[PENDING_STATUS],
    }


def _image_url(path: object) -> str | None:
    if not path:
        return None
    return f"/source-image?path={quote(str(path))}"


def load_review_state(*, candidate_root: Path = DEFAULT_CANDIDATE_ROOT) -> dict[str, Any]:
    overlay_path = _overlay_path(Path(candidate_root))
    overlay = _load_json_dict(overlay_path)
    items = sorted(
        _review_items(overlay),
        key=lambda item: (str(item.get("reviewStatus") or ""), int(item.get("frameIndex") or 0), str(item.get("reviewItemId") or "")),
    )
    enriched = [
        {
            **item,
            "fullFrameImageUrl": _image_url(item.get("fullFrameImagePath")),
            "cropImageUrl": _image_url(item.get("cropImagePath")),
        }
        for item in items
    ]
    return {
        "summary": summarize_overlay({**overlay, "reviewItems": items}),
        "reviewItems": enriched,
        "overlayPath": str(overlay_path),
    }


def _recount_overlay(overlay: dict[str, Any]) -> None:
    summary = summarize_overlay(overlay)
    overlay.update(
        {
            "reviewItemCount": summary["reviewItemCount"],
            "pendingReviewCount": summary["pendingReviewItemCount"],
            "reviewedRealDetectorMissPositiveCount": summary["reviewedRealDetectorMissPositiveCount"],
            "reviewedDetectorHitOrNotMissCount": summary["reviewedDetectorHitOrNotMissCount"],
            "reviewedNotBallOrOutOfPlayCount": summary["reviewedNotBallOrOutOfPlayCount"],
            "reviewDeferredUnclearCount": summary["reviewDeferredUnclearCount"],
            "badFrameOrUnusableCount": summary["badFrameOrUnusableCount"],
        }
    )


def update_review_item(
    *,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    review_item_id: str,
    review_status: str,
    source_frame_bbox: object = None,
    visibility_class: str | None = None,
    context_tags: list[str] | None = None,
    rejection_reason: str | None = None,
    review_notes: str | None = None,
) -> dict[str, Any]:
    if review_status not in ALLOWED_STATUSES:
        raise ReviewUpdateError("unknown_review_status")
    if review_status == POSITIVE_STATUS and not _valid_bbox_payload(source_frame_bbox):
        raise ReviewUpdateError("positive_requires_valid_source_frame_bbox")
    if review_status in {HIT_OR_NOT_MISS_STATUS, NOT_BALL_STATUS, UNCLEAR_STATUS, BAD_FRAME_STATUS} and not rejection_reason:
        raise ReviewUpdateError("non_positive_requires_rejection_reason")

    with REVIEW_UPDATE_LOCK:
        overlay_path = _overlay_path(Path(candidate_root))
        overlay = _load_json_dict(overlay_path)
        items = _review_items(overlay)
        matched = False
        for item in items:
            if str(item.get("reviewItemId") or "") != str(review_item_id):
                continue
            matched = True
            item["reviewStatus"] = review_status
            if review_notes is not None:
                item["reviewNotes"] = review_notes
            if review_status == POSITIVE_STATUS:
                item["sourceFrameBbox"] = _normalize_bbox(source_frame_bbox)
                item["bboxSource"] = "manual_reviewed_real_detector_miss"
                item["visibilityClass"] = visibility_class or "clear"
                item["contextTags"] = context_tags if isinstance(context_tags, list) else ["small_ball", "in_play"]
                item["trainingEligibility"] = "eligible_real_detector_miss_positive"
                item.pop("rejectionReason", None)
            elif review_status == PENDING_STATUS:
                item["trainingEligibility"] = "pending_review"
                item.pop("rejectionReason", None)
            else:
                item["rejectionReason"] = rejection_reason
                item["trainingEligibility"] = "evidence_only_not_real_detector_miss"
                item["sourceFrameBbox"] = None
            break
        if not matched:
            raise ReviewUpdateError("review_item_not_found")

        overlay["reviewItems"] = items
        _recount_overlay(overlay)
        _write_json_atomic(overlay_path, overlay)
        return {"summary": summarize_overlay(overlay), "reviewItem": item}


def run_resolution_gate(*, storage_root: Path = DEFAULT_STORAGE_ROOT, candidate_name: str = "touchline_detector_candidate_v7") -> dict[str, Any]:
    return run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=Path(storage_root),
        candidate_name=candidate_name,
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

    class SoccerNetDetectorMissReviewHandler(BaseHTTPRequestHandler):
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
                        for field in ("fullFrameImagePath", "cropImagePath")
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
                        review_item_id=unquote(parsed.path.removeprefix("/api/review-items/")),
                        review_status=str(payload.get("reviewStatus") or ""),
                        source_frame_bbox=payload.get("sourceFrameBbox"),
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

    return SoccerNetDetectorMissReviewHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a localhost UI for SoccerNet detector-miss review.")
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--ui-root", type=Path, default=DEFAULT_UI_ROOT)
    parser.add_argument("--host", type=loopback_host, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8773)
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
    print(f"Serving SoccerNet detector-miss review UI at http://{url_host}:{server.server_port}/")
    print(json.dumps(state["summary"], indent=2, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped SoccerNet detector-miss review UI server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
