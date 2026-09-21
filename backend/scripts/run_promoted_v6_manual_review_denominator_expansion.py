from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_V7_REFRESH_ROOT = DEFAULT_SUITE_ROOT / "touchline_detector_candidate_v7_training_data_refresh_v1"
DEFAULT_LABELING_QUEUE_PATH = DEFAULT_V7_REFRESH_ROOT / "v7_labeling_queue.json"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "manual_review_denominator_expansion_v1"
DEFAULT_ACCEPTED_GAP_MANIFEST_PATH = (
    DEFAULT_SUITE_ROOT / "global_accepted_gap_audit_v1" / "accepted_gap_frame_manifest.json"
)
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"
DEFAULT_TARGET_CLIP_ID = "trimed-5min.mp4"
DEFAULT_BATCH_NAME = "manual_review_denominator_expansion_v1"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_id(*parts: object) -> str:
    joined = "::".join(str(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:20]


def _lineage_for_item(item: dict[str, Any], *, accepted_gap_manifest_path: Path) -> dict[str, str]:
    source_clip_id = str(item.get("sourceClipId") or DEFAULT_TARGET_CLIP_ID)
    return {
        "labelingQueuePath": str(DEFAULT_LABELING_QUEUE_PATH),
        "v7DatasetManifestPath": str(DEFAULT_V7_REFRESH_ROOT / "v7_dataset_manifest.json"),
        "baselineDenominatorReviewSummaryPath": str(
            DEFAULT_SUITE_ROOT
            / "baseline_denominator_review_refresh_v1"
            / "baseline_denominator_review_summary.json"
        ),
        "acceptedGapFrameManifestPath": str(accepted_gap_manifest_path),
        "sourceClipId": source_clip_id,
    }


def _lineage_complete(lineage: object) -> bool:
    if not isinstance(lineage, dict):
        return False
    required = {
        "labelingQueuePath",
        "v7DatasetManifestPath",
        "baselineDenominatorReviewSummaryPath",
        "acceptedGapFrameManifestPath",
        "sourceClipId",
    }
    return required.issubset({str(key) for key in lineage.keys()})


def _valid_bbox_payload(bbox: object) -> bool:
    if not isinstance(bbox, dict):
        return False
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return False
    return x2 > x1 and y2 > y1


def _baseline_seed_boxes_by_frame(accepted_gap_manifest: dict[str, Any]) -> dict[int, dict[str, float]]:
    by_frame: dict[int, dict[str, float]] = {}
    for row in _list_dicts(accepted_gap_manifest.get("frames")):
        frame_index = _safe_int(row.get("frameIndex"), -1)
        baseline_row = row.get("baselineRow") if isinstance(row.get("baselineRow"), dict) else {}
        source_bbox = baseline_row.get("sourceBBox")
        if not _valid_bbox_payload(source_bbox):
            continue
        by_frame[frame_index] = {
            "x1": float(source_bbox["x1"]),
            "y1": float(source_bbox["y1"]),
            "x2": float(source_bbox["x2"]),
            "y2": float(source_bbox["y2"]),
        }
    return by_frame


def _review_items_from_queue(
    labeling_queue: dict[str, Any],
    *,
    seed_boxes_by_frame: dict[int, dict[str, float]] | None = None,
    accepted_gap_manifest_path: Path = DEFAULT_ACCEPTED_GAP_MANIFEST_PATH,
) -> list[dict[str, Any]]:
    seed_boxes_by_frame = dict(seed_boxes_by_frame or {})
    rows = sorted(
        _list_dicts(labeling_queue.get("reviewItems")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )
    review_items: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        frame_index = _safe_int(row.get("frameIndex"), -1)
        source_clip_id = str(row.get("sourceClipId") or DEFAULT_TARGET_CLIP_ID)
        review_item_id = str(
            row.get("reviewItemId")
            or f"denominator-review-{source_clip_id}-{frame_index}-{_stable_id(source_clip_id, frame_index, index)}"
        )
        candidate_frame_id = str(row.get("candidateFrameId") or f"denominator-review-frame-{frame_index}")
        file_stem = f"{source_clip_id}__f{frame_index:06d}__{review_item_id}"
        seed_bbox = seed_boxes_by_frame.get(frame_index)
        lineage = _lineage_for_item(row, accepted_gap_manifest_path=accepted_gap_manifest_path)
        review_items.append(
            {
                "reviewItemId": review_item_id,
                "curationUnitId": f"{source_clip_id}-denominator-review",
                "matchId": None,
                "sourceClipId": source_clip_id,
                "frameIndex": frame_index,
                "timestampSeconds": round(frame_index / 25.0, 3) if frame_index >= 0 else None,
                "seedSource": "baseline_current_accepted_ball",
                "seedBBox": seed_bbox,
                "decision": "pending_review",
                "reviewedBBox": None,
                "notes": (
                    "Review whether this baseline-accepted denominator frame contains a real ball signal. "
                    "Do not infer a positive label from v6 acceptance or refuted bootstrap seeds."
                ),
                "split": "manual_review_denominator_expansion",
                "fileStem": file_stem,
                "candidateFrameId": candidate_frame_id,
                "windowId": f"{source_clip_id}-denominator-review",
                "gapClass": row.get("gapClass"),
                "classification": row.get("classification"),
                "reviewTruthClass": row.get("reviewTruthClass"),
                "baselineAccepted": row.get("baselineAccepted"),
                "promotedAccepted": row.get("promotedAccepted"),
                "truthUse": "pending_denominator_review",
                "priority": row.get("priority", index + 1),
                "lineage": lineage,
                "lineageComplete": _lineage_complete(lineage),
                "refutedSeedRows": [],
            }
        )
    return review_items


def _overlay_counts(review_items: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in review_items)
    lineage_complete = sum(bool(item.get("lineageComplete")) for item in review_items)
    return {
        "reviewItemCount": len(review_items),
        "pendingReviewCount": pending,
        "reviewedPositiveCount": sum(
            str(item.get("decision") or "") in {"accept_seed", "adjust_bbox"} for item in review_items
        ),
        "reviewedNegativeCount": sum(
            str(item.get("decision") or "") in {"reject_seed", "confirm_hard_negative"} for item in review_items
        ),
        "lineageCompleteCount": lineage_complete,
        "lineageIncompleteCount": len(review_items) - lineage_complete,
        "validSeedBBoxCount": sum(_valid_bbox_payload(item.get("seedBBox")) for item in review_items),
        "missingSeedBBoxCount": sum(not _valid_bbox_payload(item.get("seedBBox")) for item in review_items),
    }


def _review_frame_manifest_item(
    item: dict[str, Any],
    *,
    image_path: Path | None,
    extracted: bool,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "reviewItemId": item.get("reviewItemId"),
        "frameIndex": item.get("frameIndex"),
        "sourceClipId": item.get("sourceClipId"),
        "fileStem": item.get("fileStem"),
        "imagePath": str(image_path) if image_path is not None else None,
        "imageExtracted": extracted,
        "error": error,
    }


def _extract_review_frames(
    *,
    review_items: list[dict[str, Any]],
    video_path: Path,
    output_root: Path,
) -> tuple[str, list[dict[str, Any]]]:
    frames_root = output_root / "review_frames"
    review_frames: list[dict[str, Any]] = []
    if not video_path.exists():
        return (
            "json_only_no_video",
            [
                _review_frame_manifest_item(item, image_path=None, extracted=False, error="video_missing")
                for item in review_items
            ],
        )
    try:
        import cv2  # type: ignore
    except ImportError:
        return (
            "json_only_no_cv2",
            [
                _review_frame_manifest_item(item, image_path=None, extracted=False, error="cv2_missing")
                for item in review_items
            ],
        )
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return (
            "json_only_video_open_failed",
            [
                _review_frame_manifest_item(item, image_path=None, extracted=False, error="video_open_failed")
                for item in review_items
            ],
        )
    frames_root.mkdir(parents=True, exist_ok=True)
    try:
        for item in review_items:
            frame_index = _safe_int(item.get("frameIndex"), -1)
            if frame_index < 0:
                review_frames.append(
                    _review_frame_manifest_item(item, image_path=None, extracted=False, error="invalid_frame_index")
                )
                continue
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok or frame is None:
                review_frames.append(
                    _review_frame_manifest_item(item, image_path=None, extracted=False, error="frame_read_failed")
                )
                continue
            image_path = frames_root / f"{item.get('fileStem')}.jpg"
            write_ok = bool(cv2.imwrite(str(image_path), frame))
            review_frames.append(
                _review_frame_manifest_item(
                    item,
                    image_path=image_path if write_ok else None,
                    extracted=write_ok,
                    error=None if write_ok else "image_write_failed",
                )
            )
    finally:
        capture.release()
    extracted_count = sum(bool(frame.get("imageExtracted")) for frame in review_frames)
    if extracted_count == len(review_items):
        return "images_extracted", review_frames
    if extracted_count > 0:
        return "partial_images_extracted", review_frames
    return "json_only_image_extraction_failed", review_frames


def _build_overlay(review_items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _overlay_counts(review_items)
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "reviewPurpose": (
            "Resolve unreviewed baseline denominator frames before v7 training-data prep."
        ),
        **counts,
        "denominatorReviewComplete": counts["pendingReviewCount"] == 0,
        "reviewItems": review_items,
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Manual Review Denominator Expansion",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewItemCount: {summary.get('reviewItemCount')}",
            f"- pendingReviewCount: {summary.get('pendingReviewCount')}",
            f"- imageExtractionStatus: {summary.get('imageExtractionStatus')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_manual_review_denominator_expansion(
    *,
    labeling_queue_path: Path = DEFAULT_LABELING_QUEUE_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    accepted_gap_manifest_path: Path = DEFAULT_ACCEPTED_GAP_MANIFEST_PATH,
    video_path: Path = DEFAULT_VIDEO_PATH,
) -> dict[str, Any]:
    labeling_queue_path = Path(labeling_queue_path)
    output_root = Path(output_root)
    labeling_queue = _load_json_dict(labeling_queue_path)
    accepted_gap_manifest_path = Path(accepted_gap_manifest_path)
    accepted_gap_manifest = _load_json_dict(accepted_gap_manifest_path)
    review_items = _review_items_from_queue(
        labeling_queue,
        seed_boxes_by_frame=_baseline_seed_boxes_by_frame(accepted_gap_manifest),
        accepted_gap_manifest_path=accepted_gap_manifest_path,
    )
    image_status, review_frames = _extract_review_frames(
        review_items=review_items,
        video_path=Path(video_path),
        output_root=output_root,
    )
    overlay = _build_overlay(review_items)
    counts = _overlay_counts(review_items)
    weak_reasons: list[str] = []
    if not review_items:
        weak_reasons.append("no_pending_denominator_review_items")
    if counts["lineageIncompleteCount"] > 0:
        weak_reasons.append("lineage_incomplete")
    goal_achieved = not weak_reasons
    next_family = "manual_review_denominator_resolution" if goal_achieved else "manual_review_lineage_refresh"
    generated_at = _utc_now_iso()
    review_candidate_manifest = {
        "generatedAt": generated_at,
        "candidateCount": len(review_items),
        "candidateFrames": [
            {
                "reviewItemId": item.get("reviewItemId"),
                "frameIndex": item.get("frameIndex"),
                "sourceClipId": item.get("sourceClipId"),
                "truthUse": item.get("truthUse"),
                "gapClass": item.get("gapClass"),
                "classification": item.get("classification"),
                "lineageComplete": item.get("lineageComplete"),
            }
            for item in review_items
        ],
    }
    refutation_guard_manifest = {
        "generatedAt": generated_at,
        "policy": "refuted_bootstrap_seeds_remain_negative_only",
        "denominatorReviewItemsUseRefutedSeedsAsPositiveEvidence": False,
    }
    review_frame_manifest = {
        "generatedAt": generated_at,
        "imageExtractionStatus": image_status,
        "reviewFrameCount": len(review_frames),
        "extractedFrameCount": sum(bool(frame.get("imageExtracted")) for frame in review_frames),
        "frames": review_frames,
    }
    review_bundle_manifest = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "reviewedLabelOverlayPath": str(output_root / "reviewed_label_overlay.json"),
        "reviewFrameManifestPath": str(output_root / "review_frame_manifest.json"),
        "reviewFrameDirectory": str(output_root / "review_frames"),
        "jsonOnlyFallback": not image_status.startswith("images_extracted"),
        "reviewInstructions": [
            "Use accept_seed or adjust_bbox only when the frame contains a real visible ball.",
            "Use reject_seed when the baseline denominator frame is visually unsupported.",
            "Use confirm_hard_negative when the frame is useful negative evidence.",
            "Do not reuse refuted bootstrap seeds as positives.",
        ],
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": "manual_review_denominator_expansion",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "denominator_review_package_generation",
        "batchStatus": "manual_review_pending" if goal_achieved else "blocked",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "imageExtractionStatus": image_status,
        "weakEvidenceReasons": weak_reasons,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        **counts,
    }
    decision = {
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "rationale": (
            "The denominator review package is ready; stop on manual review before v7 training prep."
            if goal_achieved
            else "The denominator review package is not complete enough; refresh lineage before review."
        ),
    }
    batch_outcome = {
        **summary,
        "reviewedLabelOverlay": overlay,
        "reviewFrameManifest": review_frame_manifest,
        "reviewBundleManifest": review_bundle_manifest,
        "denominatorReviewCandidateManifest": review_candidate_manifest,
        "refutationGuardManifest": refutation_guard_manifest,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "manual_review_denominator_expansion_summary.json", summary)
    _write_json(output_root / "reviewed_label_overlay.json", overlay)
    _write_json(output_root / "review_frame_manifest.json", review_frame_manifest)
    _write_json(output_root / "review_bundle_manifest.json", review_bundle_manifest)
    _write_json(output_root / "denominator_review_candidate_manifest.json", review_candidate_manifest)
    _write_json(output_root / "refutation_guard_manifest.json", refutation_guard_manifest)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "reviewedLabelOverlay": overlay,
        "reviewFrameManifest": review_frame_manifest,
        "reviewBundleManifest": review_bundle_manifest,
        "denominatorReviewCandidateManifest": review_candidate_manifest,
        "refutationGuardManifest": refutation_guard_manifest,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the promoted-v6 denominator manual review expansion package.")
    parser.add_argument("--labeling-queue-path", type=Path, default=DEFAULT_LABELING_QUEUE_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--accepted-gap-manifest-path", type=Path, default=DEFAULT_ACCEPTED_GAP_MANIFEST_PATH)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    args = parser.parse_args()
    payload = run_promoted_v6_manual_review_denominator_expansion(
        labeling_queue_path=args.labeling_queue_path,
        output_root=args.output_root,
        accepted_gap_manifest_path=args.accepted_gap_manifest_path,
        video_path=args.video_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
