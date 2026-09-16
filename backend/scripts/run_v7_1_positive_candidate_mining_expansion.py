from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
OUTPUT_DIR_NAME = "v7_1_positive_candidate_mining_expansion_v1"
EXPANSION_DIR_NAME = "v7_1_positive_diversity_manual_review_expansion_v1"
RESOLUTION_DIR_NAME = "v7_1_positive_diversity_manual_review_resolution_v1"
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"

MIN_SALVAGE_QUEUE = 20
DEFAULT_NEW_CANDIDATE_TARGET = 240
NEXT_REVIEW_V2 = "v7_1_positive_diversity_manual_review_expansion_v2"
NEXT_SOURCE_SAMPLING = "v7_1_source_sampling_expansion"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _load_json(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slug(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")[:140] or "candidate"


def _safe_bbox(row: dict[str, Any]) -> dict[str, float] | None:
    bbox = row.get("sourceFrameBbox")
    if not isinstance(bbox, dict):
        return None
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _default_bbox(width: int, height: int) -> dict[str, float]:
    cx = width / 2.0
    cy = height / 2.0
    return {"x1": cx - 8.0, "y1": cy - 8.0, "x2": cx + 8.0, "y2": cy + 8.0}


def _frame_count(video_path: Path) -> int:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        return int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()


def _extract_frame_image(video_path: Path, frame_index: int) -> Image.Image | None:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return None
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    finally:
        capture.release()


def _draw_bbox(image: Image.Image, bbox: dict[str, float] | None, *, label: str) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    if bbox:
        coords = (bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"])
        for offset in range(3):
            draw.rectangle(
                (coords[0] - offset, coords[1] - offset, coords[2] + offset, coords[3] + offset),
                outline=(255, 40, 40),
                width=1,
            )
    draw.rectangle((0, 0, min(output.width, 860), 24), fill=(0, 0, 0))
    draw.text((6, 5), label, fill=(255, 255, 255))
    return output


def _crop_around_bbox(image: Image.Image, bbox: dict[str, float] | None, *, pad: int = 160) -> Image.Image:
    if not bbox:
        return image.copy()
    cx = int(round((bbox["x1"] + bbox["x2"]) / 2.0))
    cy = int(round((bbox["y1"] + bbox["y2"]) / 2.0))
    left = max(0, cx - pad)
    top = max(0, cy - pad)
    right = min(image.width, cx + pad)
    bottom = min(image.height, cy + pad)
    crop = image.crop((left, top, right, bottom))
    shifted = {"x1": bbox["x1"] - left, "y1": bbox["y1"] - top, "x2": bbox["x2"] - left, "y2": bbox["y2"] - top}
    return _draw_bbox(crop, shifted, label=f"crop source=({left},{top})")


def _review_items(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    items = overlay.get("reviewItems") or overlay.get("items") or []
    return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []


def _is_salvage_candidate(row: dict[str, Any]) -> bool:
    if row.get("reviewStatus") != "review_deferred_unclear":
        return False
    reason = str(row.get("rejectionReason") or row.get("deferredReason") or row.get("reviewNotes") or "")
    return "visible_ball" in reason or "bbox" in reason or "correction" in reason


def _source_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row.get("sourceClipId") or "trimed-5min.mp4"), _safe_int(row.get("frameIndex"))


def _split_group_for(source_clip_id: str, frame_index: int) -> str:
    return f"{source_clip_id}-mining-cluster-{frame_index // 500:04d}"


def _split_group_for_bucket(source_clip_id: str, frame_index: int, frame_bucket_size: int) -> str:
    return f"{source_clip_id}-mining-cluster-{frame_index // frame_bucket_size:04d}"


def _salvage_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    source_clip_id, frame_index = _source_key(row)
    return {
        "candidateId": f"salvage-correction-{index:03d}-{source_clip_id}-{frame_index}",
        "candidateKind": "off_bbox_visible_ball_correction_queue",
        "reviewStatus": "pending_review",
        "sourceClipId": source_clip_id,
        "frameIndex": frame_index,
        "originalCandidateId": row.get("candidateId"),
        "originalSourceFrameBbox": row.get("sourceFrameBbox"),
        "sourceFrameBbox": row.get("sourceFrameBbox"),
        "bboxSource": "manual_corrected_source_bbox_required",
        "originalCandidateBboxWasOffTarget": True,
        "salvageEligible": True,
        "recommendedNextAction": "manual_corrected_source_bbox_required",
        "reviewFrameImagePath": row.get("reviewFrameImagePath"),
        "reviewCropImagePath": row.get("reviewCropImagePath"),
        "visibilityClass": "unknown_until_correction_review",
        "contextTags": ["off_bbox_salvage_candidate"],
        "trainingEligibility": "pending_review",
        "splitGroupId": _split_group_for(source_clip_id, frame_index),
    }


def _mine_temporal_candidates(salvage_rows: list[dict[str, Any]], *, target: int) -> list[dict[str, Any]]:
    anchors = salvage_rows or [{"sourceClipId": "trimed-5min.mp4", "frameIndex": 0, "sourceFrameBbox": None}]
    mined: list[dict[str, Any]] = []
    seen = {_source_key(row) for row in salvage_rows}
    offsets = [-45, -30, -15, -10, -5, 5, 10, 15, 30, 45, 75, 105]
    round_index = 0
    while len(mined) < target:
        anchor = anchors[round_index % len(anchors)]
        source_clip_id, frame_index = _source_key(anchor)
        offset = offsets[(round_index // len(anchors)) % len(offsets)]
        drift = (round_index // (len(anchors) * len(offsets))) * 11
        candidate_frame = max(0, frame_index + offset + drift)
        key = (source_clip_id, candidate_frame)
        round_index += 1
        if key in seen:
            continue
        seen.add(key)
        mined.append(
            {
                "candidateId": f"mined-positive-candidate-{len(mined):03d}-{source_clip_id}-{candidate_frame}",
                "candidateKind": "temporal_neighbor_candidate_after_low_yield_review",
                "reviewStatus": "pending_review",
                "sourceClipId": source_clip_id,
                "frameIndex": candidate_frame,
                "sourceFrameBbox": anchor.get("sourceFrameBbox"),
                "bboxSource": "proposal_only_manual_review_required",
                "salvageEligible": False,
                "recommendedNextAction": "manual_review_required",
                "visibilityClass": "unknown_until_review",
                "contextTags": ["new_temporal_candidate"],
                "trainingEligibility": "pending_review",
                "splitGroupId": _split_group_for(source_clip_id, candidate_frame),
            }
        )
    return mined


def _load_v2_reviewed_positive_rows(candidate_root: Path, resolution_dir_name: str) -> list[dict[str, Any]]:
    payload = _load_json(candidate_root / resolution_dir_name / "reviewed_positive_truth_additions.json")
    rows = payload.get("rows") or []
    return [row for row in rows if isinstance(row, dict)]


def _mine_new_group_candidates(
    reviewed_positive_rows: list[dict[str, Any]],
    *,
    target: int,
    video_path: Path,
    frame_bucket_size: int,
) -> list[dict[str, Any]]:
    total_frames = _frame_count(video_path)
    accepted_buckets = {_safe_int(row.get("frameIndex")) // frame_bucket_size for row in reviewed_positive_rows}
    source_clip_id = str((reviewed_positive_rows[0] or {}).get("sourceClipId") or "trimed-5min.mp4") if reviewed_positive_rows else "trimed-5min.mp4"
    buckets = [bucket for bucket in range(max(1, (total_frames + frame_bucket_size - 1) // frame_bucket_size)) if bucket not in accepted_buckets]
    if not buckets:
        buckets = list(range(max(1, (total_frames + frame_bucket_size - 1) // frame_bucket_size)))
    candidates: list[dict[str, Any]] = []
    seen_frames: set[int] = set()
    round_index = 0
    while len(candidates) < target and round_index < target * 12:
        bucket = buckets[round_index % len(buckets)]
        slot = round_index // len(buckets)
        offset_step = max(1, frame_bucket_size // 7)
        offset = (frame_bucket_size // 2 + slot * offset_step) % frame_bucket_size
        frame_index = min(total_frames - 1, bucket * frame_bucket_size + offset)
        round_index += 1
        if frame_index in seen_frames:
            continue
        seen_frames.add(frame_index)
        candidates.append(
            {
                "candidateId": f"new-group-positive-candidate-{len(candidates):03d}-{source_clip_id}-{frame_index}",
                "candidateKind": "new_temporal_group_source_sampling_candidate",
                "reviewStatus": "pending_review",
                "sourceClipId": source_clip_id,
                "frameIndex": frame_index,
                "sourceFrameBbox": None,
                "bboxSource": "source_sampling_manual_bbox_required",
                "salvageEligible": False,
                "recommendedNextAction": "manual_review_required",
                "visibilityClass": "unknown_until_review",
                "contextTags": ["new_temporal_group_candidate"],
                "trainingEligibility": "pending_review",
                "splitGroupId": _split_group_for_bucket(source_clip_id, frame_index, frame_bucket_size),
            }
        )
    return candidates


def _attach_review_evidence(
    *,
    rows: list[dict[str, Any]],
    output_root: Path,
    video_path: Path,
) -> tuple[list[dict[str, Any]], int]:
    frames_root = output_root / "review_frames"
    crops_root = output_root / "review_crops"
    frames_root.mkdir(parents=True, exist_ok=True)
    crops_root.mkdir(parents=True, exist_ok=True)
    enriched: list[dict[str, Any]] = []
    missing = 0
    for index, row in enumerate(rows):
        frame_index = _safe_int(row.get("frameIndex"))
        image = _extract_frame_image(video_path, frame_index)
        if image is None:
            missing += 1
            continue
        bbox = _safe_bbox(row) or _default_bbox(image.width, image.height)
        updated = dict(row)
        updated["sourceFrameBbox"] = bbox
        candidate_id = _slug(updated.get("candidateId") or f"candidate-{index}")
        label = f"{candidate_id} frame={frame_index} status={updated.get('reviewStatus')}"
        frame_path = frames_root / f"{index:03d}-{candidate_id}.jpg"
        crop_path = crops_root / f"{index:03d}-{candidate_id}-crop.jpg"
        _draw_bbox(image, bbox, label=label).save(frame_path, quality=92)
        _crop_around_bbox(image, bbox).save(crop_path, quality=92)
        updated["reviewFrameImagePath"] = str(frame_path)
        updated["reviewCropImagePath"] = str(crop_path)
        updated["reviewEvidencePackage"] = output_root.name
        enriched.append(updated)
    return enriched, missing


def _write_html(path: Path, rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for row in rows[:360]:
        title = html.escape(str(row.get("candidateId")))
        kind = html.escape(str(row.get("candidateKind")))
        frame = html.escape(str(row.get("frameIndex")))
        crop = row.get("reviewCropImagePath")
        frame_img = row.get("reviewFrameImagePath")
        images = []
        for image_path in (frame_img, crop):
            if image_path:
                images.append(f'<img src="{html.escape(str(image_path))}" alt="{title}">')
        cards.append(f"<section><h2>{title}</h2><p>{kind} frame {frame}</p>{''.join(images)}</section>")
    path.write_text(
        "\n".join(
            [
                "<!doctype html><meta charset='utf-8'>",
                "<title>V7.1 Positive Candidate Mining Expansion</title>",
                "<style>body{font-family:sans-serif;margin:20px}section{border:1px solid #ccc;margin:14px 0;padding:10px}img{max-width:46%;margin:6px;border:1px solid #aaa}</style>",
                "<h1>Correction-ready positive candidate package</h1>",
                *cards,
            ]
        ),
        encoding="utf-8",
    )


def run_v7_1_positive_candidate_mining_expansion(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    new_candidate_target: int = DEFAULT_NEW_CANDIDATE_TARGET,
    output_dir_name: str = OUTPUT_DIR_NAME,
    resolution_dir_name: str = RESOLUTION_DIR_NAME,
    video_path: Path | None = None,
    frame_bucket_size: int = 500,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    expansion_root = candidate_root / EXPANSION_DIR_NAME
    resolution_root = candidate_root / resolution_dir_name
    output_root = candidate_root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    is_v2 = output_dir_name.endswith("_v2") or resolution_dir_name.endswith("_v2")
    resolution = _load_json(resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json", required=True)
    missing_evidence = 0
    review_rows: list[dict[str, Any]] = []
    if is_v2:
        reviewed_positive_rows = _load_v2_reviewed_positive_rows(candidate_root, resolution_dir_name)
        salvage_rows = []
        mined_rows = _mine_new_group_candidates(
            reviewed_positive_rows,
            target=new_candidate_target,
            video_path=Path(video_path or DEFAULT_VIDEO_PATH),
            frame_bucket_size=frame_bucket_size,
        )
        all_rows, missing_evidence = _attach_review_evidence(rows=mined_rows, output_root=output_root, video_path=Path(video_path or DEFAULT_VIDEO_PATH))
    else:
        overlay = _load_json(expansion_root / "reviewed_label_overlay.json", required=True)
        review_rows = _review_items(overlay)
        salvage_rows = [_salvage_row(row, index) for index, row in enumerate(review_rows) if _is_salvage_candidate(row)]
        mined_rows = _mine_temporal_candidates(salvage_rows, target=new_candidate_target)
        all_rows = [*salvage_rows, *mined_rows]
    group_count = len({row.get("splitGroupId") for row in all_rows if row.get("splitGroupId")})
    primary_blocker = None
    next_lever = NEXT_REVIEW_V2
    goal_achieved = True
    english = "Candidate mining expanded with correction-ready visible-ball off-bbox cases and new temporal groups. Proceed to manual review; do not train."
    if not is_v2 and len(salvage_rows) < MIN_SALVAGE_QUEUE:
        primary_blocker = "v7_1_positive_candidate_correction_queue_missing"
        next_lever = NEXT_SOURCE_SAMPLING
        goal_achieved = False
        english = "Correction queue is too small; broaden source sampling before another review round."
    summary = {
        "batchName": "v7_1_positive_candidate_mining_expansion_v2" if is_v2 else "v7_1_positive_candidate_mining_expansion",
        "generatedAt": _utc_now_iso(),
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "previousReviewedPositiveSourceCount": _safe_int(resolution.get("totalReviewedPositiveSourceCount"), 34),
        "previousReviewCandidateCount": _safe_int(resolution.get("reviewCandidateCount"), len(review_rows)),
        "previousAcceptedPositiveCount": _safe_int(resolution.get("newReviewedPositiveSourceCount")),
        "previousDeferredUnclearCount": _safe_int(resolution.get("reviewDeferredUnclearCount")),
        "salvageCorrectionQueueCount": len(salvage_rows),
        "newMinedCandidateCount": len(all_rows) if is_v2 else len(mined_rows),
        "totalCandidateReviewCount": len(all_rows),
        "reviewRowsExcludedMissingEvidenceCount": missing_evidence,
        "knownCropValidationMissesCarriedForward": _safe_int(resolution.get("knownCropValidationMissesReviewed")),
        "knownFullPipelineMissesCarriedForward": _safe_int(resolution.get("knownFullPipelineMissesReviewed")),
        "distinctCandidateSplitGroupCount": group_count,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    overlay_payload = {
        "batchName": summary["batchName"],
        "reviewItemCount": len(all_rows),
        "pendingReviewCount": len(all_rows),
        "allowedReviewStatuses": [
            "reviewed_positive_ball",
            "reviewed_not_ball",
            "review_deferred_unclear",
            "duplicate_or_near_duplicate",
            "bad_crop_or_unusable_frame",
            "pending_review",
        ],
        "reviewItems": all_rows,
    }
    _write_json(output_root / "corrected_label_overlay.json", overlay_payload)
    _write_json(output_root / "salvage_candidate_summary.json", {"salvageCorrectionQueueCount": len(salvage_rows), "rows": salvage_rows})
    _write_json(output_root / "new_mined_candidate_manifest.json", {"newMinedCandidateCount": len(mined_rows), "rows": mined_rows})
    _write_json(output_root / "v7_1_positive_candidate_mining_expansion_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary})
    (output_root / "batch_outcome_analysis.md").write_text(f"# V7.1 Positive Candidate Mining Expansion\n\n{english}\n", encoding="utf-8")
    _write_html(output_root / "correction_review_index.html", all_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v7.1 positive candidate mining expansion artifacts.")
    parser.add_argument("--v2", action="store_true", help="Build the v2 new-temporal-group mining package from v2 resolver truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--new-candidate-target", type=int, default=DEFAULT_NEW_CANDIDATE_TARGET)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--frame-bucket-size", type=int, default=500)
    args = parser.parse_args()
    output_dir_name = "v7_1_positive_candidate_mining_expansion_v2" if args.v2 else OUTPUT_DIR_NAME
    resolution_dir_name = "v7_1_positive_diversity_manual_review_resolution_v2" if args.v2 else RESOLUTION_DIR_NAME
    payload = run_v7_1_positive_candidate_mining_expansion(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        new_candidate_target=args.new_candidate_target,
        output_dir_name=output_dir_name,
        resolution_dir_name=resolution_dir_name,
        video_path=args.video_path,
        frame_bucket_size=args.frame_bucket_size,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
