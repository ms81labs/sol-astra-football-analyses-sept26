from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_optional as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_positive_diversity_refresh_v1"

MIN_REVIEWED_POSITIVES = 120
MIN_NEW_REVIEWED_POSITIVES = 90
MIN_SPLIT_GROUPS = 8

BLOCKER_COUNT = "v7_1_positive_diversity_insufficient_reviewed_count"
BLOCKER_GROUPS = "v7_1_positive_diversity_temporal_cluster_insufficient"
BLOCKER_OVERLAY = "v7_1_positive_diversity_label_overlay_missing"
BLOCKER_SPLIT = "v7_1_positive_diversity_split_leakage"
BLOCKER_MISSES = "v7_1_positive_diversity_known_misses_not_included"
BLOCKER_UNSAFE_NEGATIVE = "v7_1_positive_diversity_unsafe_negative_reintroduced"

NEXT_V72_PREP = "v7_2_training_manifest_prep"
NEXT_MANUAL_REVIEW = "v7_1_positive_diversity_manual_review_expansion"
NEXT_SPLIT_POLICY = "v7_1_positive_diversity_split_policy_refresh"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _source_key(row: dict[str, Any]) -> str:
    return f"{row.get('sourceClipId')}:{row.get('frameIndex')}"


def _source_positive_rows(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for crop in manifest.get("positiveCropExamples", []):
        if not isinstance(crop, dict):
            continue
        key = _source_key(crop)
        if key not in rows:
            rows[key] = {
                "sourceClipId": crop.get("sourceClipId"),
                "frameIndex": crop.get("frameIndex"),
                "sourceFrameBbox": crop.get("sourceFrameBbox"),
                "splitGroupId": crop.get("splitGroupId"),
                "split": crop.get("split"),
                "cropSizes": [],
                "cropExampleIds": [],
            }
        rows[key]["cropSizes"].append(crop.get("cropSizePx"))
        rows[key]["cropExampleIds"].append(crop.get("exampleId"))
    return rows


def _split_leakage(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    by_group: dict[str, set[str]] = {}
    for crop in manifest.get("positiveCropExamples", []):
        if not isinstance(crop, dict):
            continue
        group = str(crop.get("splitGroupId") or "")
        split = str(crop.get("split") or "")
        if not group or not split:
            continue
        by_group.setdefault(group, set()).add(split)
    return [
        {"splitGroupId": group, "splits": sorted(splits)}
        for group, splits in sorted(by_group.items())
        if len(splits) > 1
    ]


def _bbox_size_bucket(bbox: dict[str, Any] | None) -> str:
    if not isinstance(bbox, dict):
        return "bbox_missing"
    width = float(bbox.get("x2", 0.0)) - float(bbox.get("x1", 0.0))
    height = float(bbox.get("y2", 0.0)) - float(bbox.get("y1", 0.0))
    size = max(width, height)
    if size < 12:
        return "smallBallUnder12Px"
    if size <= 24:
        return "mediumBall12To24Px"
    return "largeBallOver24Px"


def _diversity_summary(source_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    size_counts: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    frame_counts = {"earlyFramesUnder1000": 0, "middleFrames1000To5000": 0, "lateFramesOver5000": 0}
    for row in source_rows.values():
        bucket = _bbox_size_bucket(row.get("sourceFrameBbox"))
        size_counts[bucket] = size_counts.get(bucket, 0) + 1
        group = str(row.get("splitGroupId") or "missing_split_group")
        group_counts[group] = group_counts.get(group, 0) + 1
        frame_index = int(row.get("frameIndex") or 0)
        if frame_index < 1000:
            frame_counts["earlyFramesUnder1000"] += 1
        elif frame_index <= 5000:
            frame_counts["middleFrames1000To5000"] += 1
        else:
            frame_counts["lateFramesOver5000"] += 1
    return {
        "positiveDiversitySummary": {**size_counts, **frame_counts},
        "splitGroupCounts": group_counts,
        "distinctPositiveSplitGroupCount": len(group_counts),
    }


def _known_miss_candidates(
    *,
    crop_misses: list[dict[str, Any]],
    pipeline_misses: list[dict[str, Any]],
    existing_sources: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    example_to_source: dict[str, dict[str, Any]] = {}
    for source in existing_sources.values():
        for example_id in source.get("cropExampleIds", []):
            example_to_source[str(example_id)] = source
    for miss in crop_misses:
        example_id = str(miss.get("exampleId") or "")
        source = example_to_source.get(example_id, {})
        candidate_id = f"crop-validation-miss-{example_id}"
        candidates[candidate_id] = {
            "candidateId": candidate_id,
            "candidateStatus": "proposed_positive_candidate",
            "source": "v7_1_crop_probe_precision_guardrail_audit",
            "missType": miss.get("missType", "no_prediction"),
            "exampleId": example_id,
            "sourceClipId": source.get("sourceClipId"),
            "frameIndex": source.get("frameIndex"),
            "sourceFrameBbox": source.get("sourceFrameBbox"),
            "reviewAction": "retain_as_positive_hard_case",
            "recommendedCropVariants": [192, 256, 384],
            "labelPolicy": "requires_human_review_before_training",
        }
    for miss in pipeline_misses:
        frame_index = miss.get("frameIndex")
        source_clip_id = miss.get("sourceClipId")
        candidate_id = f"full-pipeline-miss-{source_clip_id}-{frame_index}"
        candidates[candidate_id] = {
            "candidateId": candidate_id,
            "candidateStatus": "proposed_positive_candidate",
            "source": "v7_1_full_pipeline_non_promotion_eval",
            "missType": "pipeline_source_frame_miss",
            "sourceClipId": source_clip_id,
            "frameIndex": frame_index,
            "sourceFrameBbox": miss.get("sourceFrameBbox"),
            "reviewAction": "retain_as_positive_hard_case",
            "recommendedCropVariants": [192, 256, 384],
            "labelPolicy": "requires_human_review_before_training",
        }
    return list(candidates.values())


def _temporal_neighbor_candidates(source_rows: dict[str, dict[str, Any]], *, max_candidates: int = 120) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sorted(source_rows.values(), key=lambda item: (str(item.get("sourceClipId")), int(item.get("frameIndex") or 0))):
        frame_index = int(source.get("frameIndex") or 0)
        for offset in (-30, -20, -10, 10, 20, 30):
            candidate_frame = max(0, frame_index + offset)
            candidate_id = f"temporal-neighbor-{source.get('sourceClipId')}-{candidate_frame}"
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            output.append(
                {
                    "candidateId": candidate_id,
                    "candidateStatus": "proposed_positive_candidate",
                    "source": "temporal_neighbor_around_reviewed_positive",
                    "sourceClipId": source.get("sourceClipId"),
                    "frameIndex": candidate_frame,
                    "anchorFrameIndex": frame_index,
                    "sourceFrameBbox": source.get("sourceFrameBbox"),
                    "reviewAction": "manual_review_required",
                    "recommendedCropVariants": [192, 256, 384],
                    "labelPolicy": "requires_human_review_before_training",
                }
            )
            if len(output) >= max_candidates:
                return output
    return output


def _copy_contact_sheet(source_path: Path, target_path: Path) -> bool:
    if not source_path.exists():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return True


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if summary["unsafeFullFrameNegativeExportCount"] > 0 or summary["fullFrameEmptyLabelNegativeExportCount"] > 0:
        return BLOCKER_UNSAFE_NEGATIVE, NEXT_MANUAL_REVIEW, False, "Unsafe full-frame empty negatives reappeared; stop before training prep."
    if summary["splitLeakageCount"] > 0:
        return BLOCKER_SPLIT, NEXT_SPLIT_POLICY, False, "Positive split groups leak across splits; repair split policy before v7.2 prep."
    if not summary["knownMissesIncluded"]:
        return BLOCKER_MISSES, NEXT_MANUAL_REVIEW, False, "Known v7.1 misses were not included in the refresh queue."
    if summary["totalReviewedPositiveSourceCount"] < MIN_REVIEWED_POSITIVES or summary["newReviewedPositiveSourceCount"] < MIN_NEW_REVIEWED_POSITIVES:
        return BLOCKER_COUNT, NEXT_MANUAL_REVIEW, True, "Positive review queue is ready, but the repo does not yet contain enough newly reviewed positives for v7.2 training prep."
    if summary["distinctPositiveSplitGroupCount"] < MIN_SPLIT_GROUPS:
        return BLOCKER_GROUPS, NEXT_MANUAL_REVIEW, True, "Reviewed positive count is sufficient, but temporal/source group diversity is still too narrow."
    if not summary["labelOverlayReviewReady"]:
        return BLOCKER_OVERLAY, NEXT_MANUAL_REVIEW, False, "Positive overlay review artifacts are missing."
    return None, NEXT_V72_PREP, True, "Positive truth diversity refreshed. Advance to v7.2 training manifest prep; do not train or promote yet."


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Positive Diversity Refresh",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Previous reviewed positives: `{summary.get('previousReviewedPositiveSourceCount')}`",
            f"- New reviewed positives: `{summary.get('newReviewedPositiveSourceCount')}`",
            f"- Total reviewed positives: `{summary.get('totalReviewedPositiveSourceCount')}`",
            f"- Review queue candidates: `{summary.get('positiveReviewQueueCandidateCount')}`",
            f"- Known crop misses included: `{summary.get('knownCropValidationMissesIncluded')}`",
            f"- Known full-pipeline misses included: `{summary.get('knownFullPipelineMissesIncluded')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_positive_diversity_refresh(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "positive_diversity_gap_analysis",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    pipeline_root = candidate_root / "v7_1_full_pipeline_non_promotion_eval_v1"
    guardrail_root = candidate_root / "v7_1_crop_probe_precision_guardrail_audit_v1"
    output_root = reset_output(candidate_root, output_dir_name)
    manifest = _load_json(manifest_root / "v7_1_local_crop_training_manifest.json", required=True)
    full_pipeline_summary = _load_json(pipeline_root / "v7_1_full_pipeline_non_promotion_summary.json")
    crop_miss_payload = _load_json(guardrail_root / "validation_positive_miss_analysis.json")
    pipeline_miss_payload = _load_json(pipeline_root / "positive_miss_analysis.json")
    source_rows = _source_positive_rows(manifest)
    diversity = _diversity_summary(source_rows)
    split_leaks = _split_leakage(manifest)
    crop_misses = [row for row in crop_miss_payload.get("misses", []) if isinstance(row, dict)]
    pipeline_misses = [row for row in pipeline_miss_payload.get("misses", []) if isinstance(row, dict)]
    known_miss_candidates = _known_miss_candidates(crop_misses=crop_misses, pipeline_misses=pipeline_misses, existing_sources=source_rows)
    temporal_candidates = _temporal_neighbor_candidates(source_rows)
    candidate_by_id = {str(row["candidateId"]): row for row in [*known_miss_candidates, *temporal_candidates]}
    review_queue = list(candidate_by_id.values())
    previous_count = int(manifest.get("reviewedPositiveSourceCount") or len(source_rows))
    total_count = len(source_rows)
    new_count = max(0, total_count - 30)
    known_misses_included = bool(crop_misses or pipeline_misses) and len(known_miss_candidates) >= len({str(row.get("exampleId") or row.get("frameIndex")) for row in [*crop_misses, *pipeline_misses]})
    crop_variant_plan = [
        {
            "sourceClipId": row.get("sourceClipId"),
            "frameIndex": row.get("frameIndex"),
            "sourceFrameBbox": row.get("sourceFrameBbox"),
            "recommendedCropVariants": [192, 256, 384],
            "truthUse": "reviewed_positive_training_seed",
        }
        for row in source_rows.values()
    ]
    label_overlay_ready = len(review_queue) > 0
    _copy_contact_sheet(guardrail_root / "worst_positive_misses_contact_sheet.jpg", output_root / "hard_case_positive_contact_sheet.jpg")
    _copy_contact_sheet(pipeline_root / "worst_positive_misses_contact_sheet.jpg", output_root / "positive_overlay_contact_sheet.jpg")
    summary: dict[str, Any] = {
        "batchName": "v7_1_positive_diversity_refresh",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "goal": "expand reviewed positive ball truth diversity before any promotion path",
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "previousReviewedPositiveSourceCount": previous_count,
        "newReviewedPositiveSourceCount": new_count,
        "totalReviewedPositiveSourceCount": total_count,
        "distinctPositiveSplitGroupCount": diversity["distinctPositiveSplitGroupCount"],
        "knownCropValidationMissesIncluded": len(crop_misses),
        "knownFullPipelineMissesIncluded": len(pipeline_misses),
        "knownMissesIncluded": known_misses_included,
        "positiveCropVariantPlanCount": len(crop_variant_plan) * 3,
        "positiveReviewQueueCandidateCount": len(review_queue),
        "unsafeFullFrameNegativeExportCount": int(manifest.get("unsafeFullFrameNegativeExportCount") or 0),
        "fullFrameEmptyLabelNegativeExportCount": int(manifest.get("fullFrameEmptyLabelNegativeExportCount") or 0),
        "splitLeakageCount": len(split_leaks),
        "labelOverlayReviewReady": label_overlay_ready,
        "secondaryConcernCarriedForward": full_pipeline_summary.get("secondaryConcern"),
        **diversity,
    }
    primary_blocker, next_family, goal_achieved, english = _classify(summary)
    summary.update(
        {
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": goal_achieved,
            "primaryBlocker": primary_blocker,
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )
    _write_json(output_root / "positive_candidate_mining_audit.json", {"knownMissCandidates": known_miss_candidates, "temporalNeighborCandidates": temporal_candidates})
    _write_json(output_root / "positive_review_queue.json", {"candidateCount": len(review_queue), "candidates": review_queue})
    _write_json(output_root / "reviewed_positive_additions.json", {"newReviewedPositiveSourceCount": new_count, "rows": []})
    _write_json(output_root / "reviewed_positive_rejections.json", {"rows": []})
    _write_json(output_root / "positive_diversity_summary.json", diversity)
    _write_json(output_root / "positive_split_group_audit.json", {"splitLeakageCount": len(split_leaks), "leaks": split_leaks})
    _write_json(output_root / "positive_crop_variant_plan.json", {"positiveCropVariantPlanCount": len(crop_variant_plan) * 3, "rows": crop_variant_plan})
    _write_json(output_root / "known_miss_refresh_plan.json", {"cropValidationMisses": crop_misses, "fullPipelineMisses": pipeline_misses, "reviewCandidates": known_miss_candidates})
    _write_json(output_root / "label_overlay_review_manifest.json", {"labelOverlayReviewReady": label_overlay_ready, "candidateCount": len(review_queue), "candidates": review_queue[:60]})
    _write_json(output_root / "v7_1_positive_diversity_refresh_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="positive_diversity_gap_analysis")
    args = parser.parse_args()
    payload = run_v7_1_positive_diversity_refresh(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
