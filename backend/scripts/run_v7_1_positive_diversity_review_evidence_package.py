from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import html
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
EXPANSION_DIR_NAME = "v7_1_positive_diversity_manual_review_expansion_v1"
OUTPUT_DIR_NAME = "v7_1_positive_diversity_review_evidence_package_v1"
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _slug(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")[:140] or "candidate"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bbox_tuple(item: dict[str, Any]) -> tuple[int, int, int, int] | None:
    bbox = item.get("sourceFrameBbox")
    if not isinstance(bbox, dict):
        return None
    try:
        x1 = int(round(float(bbox["x1"])))
        y1 = int(round(float(bbox["y1"])))
        x2 = int(round(float(bbox["x2"])))
        y2 = int(round(float(bbox["y2"])))
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _extract_frame_image(*, video_path: Path, frame_index: int) -> Image.Image:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Could not read frame {frame_index} from {video_path}")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    finally:
        capture.release()


def _draw_bbox(image: Image.Image, bbox: tuple[int, int, int, int] | None, *, label: str) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        for offset in range(3):
            draw.rectangle((x1 - offset, y1 - offset, x2 + offset, y2 + offset), outline=(255, 40, 40), width=1)
    draw.rectangle((0, 0, min(output.width, 760), 24), fill=(0, 0, 0))
    draw.text((6, 5), label, fill=(255, 255, 255))
    return output


def _crop_around_bbox(image: Image.Image, bbox: tuple[int, int, int, int] | None, *, pad: int = 96) -> Image.Image:
    if bbox is None:
        return image.copy()
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    left = max(0, cx - pad)
    top = max(0, cy - pad)
    right = min(image.width, cx + pad)
    bottom = min(image.height, cy + pad)
    crop = image.crop((left, top, right, bottom))
    shifted = (x1 - left, y1 - top, x2 - left, y2 - top)
    return _draw_bbox(crop, shifted, label=f"crop source=({left},{top})")


def _write_html(path: Path, rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for row in rows:
        candidate_id = html.escape(str(row.get("candidateId")))
        frame = html.escape(str(row.get("frameIndex")))
        source = html.escape(str(row.get("source")))
        bbox = html.escape(json.dumps(row.get("sourceFrameBbox"), sort_keys=True))
        frame_path = html.escape(Path(str(row.get("reviewFrameImagePath"))).name)
        crop_path = html.escape(Path(str(row.get("reviewCropImagePath"))).name)
        cards.append(
            "\n".join(
                [
                    '<section class="card">',
                    f"<h2>{candidate_id}</h2>",
                    f"<p>frame {frame} | {source}</p>",
                    f"<p><code>{bbox}</code></p>",
                    f'<img src="review_frames/{frame_path}" alt="{candidate_id} frame">',
                    f'<img src="review_crops/{crop_path}" alt="{candidate_id} crop">',
                    "</section>",
                ]
            )
        )
    path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<meta charset='utf-8'>",
                "<title>V7.1 Positive Diversity Review Evidence</title>",
                "<style>body{font-family:sans-serif;margin:20px;background:#f6f6f6}.card{background:white;border:1px solid #ddd;margin:0 0 24px;padding:12px}img{max-width:48%;margin:6px;border:1px solid #aaa;vertical-align:top}code{font-size:12px}</style>",
                "<h1>V7.1 Positive Diversity Review Evidence</h1>",
                *cards,
            ]
        ),
        encoding="utf-8",
    )


def run_v7_1_positive_diversity_review_evidence_package(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    video_path: Path = DEFAULT_VIDEO_PATH,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    expansion_root = candidate_root / EXPANSION_DIR_NAME
    output_root = candidate_root / OUTPUT_DIR_NAME
    frames_root = output_root / "review_frames"
    crops_root = output_root / "review_crops"
    frames_root.mkdir(parents=True, exist_ok=True)
    crops_root.mkdir(parents=True, exist_ok=True)
    overlay_path = expansion_root / "reviewed_label_overlay.json"
    overlay = _load_json(overlay_path)
    items = [item for item in overlay.get("reviewItems", []) if isinstance(item, dict)]
    decision_mutations = 0
    updated_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        before_status = item.get("reviewStatus")
        frame_index = _safe_int(item.get("frameIndex"))
        candidate_id = _slug(item.get("candidateId") or f"candidate-{index}")
        bbox = _bbox_tuple(item)
        image = _extract_frame_image(video_path=video_path, frame_index=frame_index)
        label = f"{candidate_id} frame={frame_index} status={before_status}"
        frame_overlay = _draw_bbox(image, bbox, label=label)
        crop_overlay = _crop_around_bbox(image, bbox)
        frame_path = frames_root / f"{index:03d}-{candidate_id}.jpg"
        crop_path = crops_root / f"{index:03d}-{candidate_id}-crop.jpg"
        frame_overlay.save(frame_path, quality=92)
        crop_overlay.save(crop_path, quality=92)
        updated = dict(item)
        updated["reviewFrameImagePath"] = str(frame_path)
        updated["reviewCropImagePath"] = str(crop_path)
        updated["reviewEvidencePackage"] = OUTPUT_DIR_NAME
        if updated.get("reviewStatus") != before_status:
            decision_mutations += 1
        updated_items.append(updated)
    overlay["reviewItems"] = updated_items
    overlay["reviewEvidencePackagePath"] = str(output_root)
    overlay["reviewIndexHtmlPath"] = str(output_root / "review_index.html")
    overlay_path.write_text(json.dumps(overlay, indent=2, sort_keys=True), encoding="utf-8")
    _write_html(output_root / "review_index.html", updated_items)
    summary = {
        "batchName": "v7_1_positive_diversity_review_evidence_package",
        "generatedAt": _utc_now_iso(),
        "reviewItemCount": len(updated_items),
        "frameImageCount": len(updated_items),
        "cropImageCount": len(updated_items),
        "reviewDecisionMutationCount": decision_mutations,
        "reviewedLabelOverlayPath": str(overlay_path),
        "reviewIndexHtmlPath": str(output_root / "review_index.html"),
        "trainingExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationAllowed": False,
    }
    _write_json(output_root / "review_evidence_package_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract visual evidence for v7.1 positive diversity review.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    args = parser.parse_args()
    payload = run_v7_1_positive_diversity_review_evidence_package(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        video_path=args.video_path,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
