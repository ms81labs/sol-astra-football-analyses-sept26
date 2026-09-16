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
from urllib.parse import quote, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT
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
from backend.scripts.run_promoted_v6_manual_review_resolution_batch import (
    DEFAULT_OUTPUT_ROOT as DEFAULT_RESOLUTION_OUTPUT_ROOT,
)
from backend.scripts.run_promoted_v6_manual_review_resolution_batch import (
    DEFAULT_RETENTION_DELTA_ROOT,
)
from backend.scripts.run_promoted_v6_manual_review_resolution_batch import DEFAULT_SUITE_ROOT
from backend.scripts.run_promoted_v6_manual_review_resolution_batch import (
    run_promoted_v6_manual_review_resolution_batch,
)

DEFAULT_REVIEW_ROOT = (
    DEFAULT_STORAGE_ROOT
    / "benchmark_suites"
    / "frozen-viable-baseline-slice-suite"
    / "promoted_v6_manual_review_followthrough_v1"
)
DEFAULT_UI_ROOT = REPO_ROOT / "backend" / "review_ui" / "promoted_v6_manual_review"
ALLOWED_UPDATE_DECISIONS = {
    "accept_seed",
    "adjust_bbox",
    "reject_seed",
    "confirm_hard_negative",
    "pending_review",
}
POSITIVE_DECISIONS = {"accept_seed", "adjust_bbox"}
NEGATIVE_DECISIONS = {"reject_seed", "confirm_hard_negative"}


class ReviewUpdateError(ValueError):
    pass


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


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    return float(x2) > float(x1) and float(y2) > float(y1)


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
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in items)
    accepted = sum(str(item.get("decision") or "") == "accept_seed" for item in items)
    adjusted = sum(str(item.get("decision") or "") == "adjust_bbox" for item in items)
    rejected = sum(str(item.get("decision") or "") == "reject_seed" for item in items)
    hard_negative = sum(str(item.get("decision") or "") == "confirm_hard_negative" for item in items)
    return {
        "reviewItemCount": len(items),
        "pendingReviewCount": pending,
        "acceptedSeedCount": accepted,
        "adjustedBBoxCount": adjusted,
        "rejectedSeedCount": rejected,
        "confirmedHardNegativeCount": hard_negative,
        "reviewedPositiveCount": accepted + adjusted,
        "reviewedNegativeCount": rejected + hard_negative,
    }


def _image_urls_by_item(frame_manifest: dict[str, Any]) -> dict[str, str]:
    urls: dict[str, str] = {}
    frames = frame_manifest.get("reviewFrames")
    if not isinstance(frames, list):
        return urls
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        review_item_id = str(frame.get("reviewItemId") or "")
        image_path = str(frame.get("imagePath") or "")
        if review_item_id and image_path:
            urls[review_item_id] = f"/review_frames/{quote(Path(image_path).name)}"
    return urls


def load_review_state(*, review_root: Path = DEFAULT_REVIEW_ROOT) -> dict[str, Any]:
    review_root = Path(review_root)
    overlay = _load_json_dict(review_root / "reviewed_label_overlay.json")
    frame_manifest = _load_json_dict(review_root / "review_frame_manifest.json")
    bundle_manifest = _load_json_dict(review_root / "review_bundle_manifest.json")
    image_urls = _image_urls_by_item(frame_manifest)
    items = sorted(
        _review_items(overlay),
        key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")),
    )
    enriched_items = [
        {
            **item,
            "imageUrl": image_urls.get(str(item.get("reviewItemId") or "")),
        }
        for item in items
    ]
    return {
        "summary": summarize_overlay({**overlay, "reviewItems": items}),
        "reviewItems": enriched_items,
        "frameManifest": frame_manifest,
        "bundleManifest": bundle_manifest,
    }


def _recount_overlay(overlay: dict[str, Any]) -> None:
    summary = summarize_overlay(overlay)
    overlay.update(summary)
    overlay["lineageCompleteCount"] = sum(
        1 for item in _review_items(overlay) if item.get("lineageComplete") is True
    )
    overlay["lineageIncompleteCount"] = summary["reviewItemCount"] - int(overlay["lineageCompleteCount"])
    overlay["validSeedBBoxCount"] = sum(1 for item in _review_items(overlay) if _valid_bbox_payload(item.get("seedBBox")))
    overlay["missingSeedBBoxCount"] = summary["reviewItemCount"] - int(overlay["validSeedBBoxCount"])


def update_review_item(
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    review_item_id: str,
    decision: str,
    reviewed_bbox: object = None,
    reviewer_notes: str | None = None,
) -> dict[str, Any]:
    if decision not in ALLOWED_UPDATE_DECISIONS:
        raise ReviewUpdateError("unknown_review_decision")
    if decision == "adjust_bbox" and not _valid_bbox_payload(reviewed_bbox):
        raise ReviewUpdateError("adjust_bbox_requires_valid_reviewed_bbox")

    review_root = Path(review_root)
    with REVIEW_UPDATE_LOCK:
        overlay_path = review_root / "reviewed_label_overlay.json"
        overlay = _load_json_dict(overlay_path)
        items = _review_items(overlay)
        matched = False
        for item in items:
            if str(item.get("reviewItemId") or "") != str(review_item_id):
                continue
            matched = True
            item["decision"] = decision
            item["reviewedBBox"] = _normalize_bbox(reviewed_bbox) if decision == "adjust_bbox" else None
            if reviewer_notes is not None:
                item["reviewerNotes"] = reviewer_notes
            break
        if not matched:
            raise ReviewUpdateError("review_item_not_found")

        overlay["reviewItems"] = items
        _recount_overlay(overlay)
        _write_json_atomic(overlay_path, overlay)
        return {"summary": summarize_overlay(overlay), "reviewItem": item}


def run_resolution_gate(
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    output_root: Path = DEFAULT_RESOLUTION_OUTPUT_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
) -> dict[str, Any]:
    return run_promoted_v6_manual_review_resolution_batch(
        output_root=Path(output_root),
        manual_review_root=Path(review_root),
        retention_delta_root=Path(retention_delta_root),
        suite_root=Path(suite_root),
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


def build_handler(*, review_root: Path, ui_root: Path):
    review_root = Path(review_root)
    ui_root = Path(ui_root)

    class PromotedV6ManualReviewHandler(BaseHTTPRequestHandler):
        timeout = 5.0

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path in {"/", "/index.html"}:
                    self._serve_file(ui_root / "index.html")
                    return
                if path == "/api/review-state":
                    _json_response(self, load_review_state(review_root=review_root))
                    return
                if path == "/api/summary":
                    _json_response(self, load_review_state(review_root=review_root)["summary"])
                    return
                if path.startswith("/review_frames/"):
                    filename = unquote(path.removeprefix("/review_frames/"))
                    manifest = _load_json_dict(review_root / "review_frame_manifest.json")
                    approved = {
                        Path(frame["imagePath"]).name: Path(frame["imagePath"])
                        for frame in manifest.get("reviewFrames", [])
                        if isinstance(frame, dict) and frame.get("reviewItemId") and frame.get("imagePath")
                    }
                    image_path = approved.get(filename)
                    content_type = mimetypes.guess_type(filename)[0] or ""
                    if image_path is None or not content_type.startswith("image/"):
                        raise FileNotFoundError(filename)
                    self._serve_file(image_path)
                    return
                _error_response(self, "not_found", HTTPStatus.NOT_FOUND)
            except FileNotFoundError:
                _error_response(self, "not_found", HTTPStatus.NOT_FOUND)
            except Exception as exc:  # pragma: no cover - defensive server guard
                _error_response(self, str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                payload = read_json_payload(self)
                if path.startswith("/api/review-items/"):
                    review_item_id = unquote(path.removeprefix("/api/review-items/"))
                    result = update_review_item(
                        review_root=review_root,
                        review_item_id=review_item_id,
                        decision=str(payload.get("decision") or ""),
                        reviewed_bbox=payload.get("reviewedBBox"),
                        reviewer_notes=payload.get("reviewerNotes") if "reviewerNotes" in payload else None,
                    )
                    _json_response(self, result)
                    return
                if path == "/api/run-resolution":
                    _json_response(self, run_resolution_gate(review_root=review_root))
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
            except Exception as exc:  # pragma: no cover - defensive server guard
                _error_response(self, str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _serve_file(self, path: Path) -> None:
            body = read_regular_file(path)
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return PromotedV6ManualReviewHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a localhost UI for promoted-v6 manual review decisions.")
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--ui-root", type=Path, default=DEFAULT_UI_ROOT)
    parser.add_argument("--host", type=loopback_host, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true", help="Validate artifacts and print the review summary without serving.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = load_review_state(review_root=args.review_root)
    if args.dry_run:
        print(json.dumps(state["summary"], indent=2, sort_keys=True))
        return 0

    class LocalServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if ":" in args.host else socket.AF_INET

    server = LocalServer(
        (args.host, args.port),
        build_handler(review_root=args.review_root, ui_root=args.ui_root),
    )
    url_host = f"[{args.host}]" if ":" in args.host else args.host
    print(f"Serving promoted-v6 manual review UI at http://{url_host}:{server.server_port}/")
    print(json.dumps(state["summary"], indent=2, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped manual review UI server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
