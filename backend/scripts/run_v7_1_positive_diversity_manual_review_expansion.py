from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_positive_diversity_manual_review_expansion_v1"
DEFAULT_REVIEW_TARGET_COUNT = 149
MIN_NEW_REVIEWED_POSITIVES = 90
MIN_TOTAL_REVIEWED_POSITIVES = 120
MIN_SPLIT_GROUPS = 8

NEXT_V72_PREP = "v7_2_training_manifest_prep"
NEXT_MANUAL_REVIEW = "manual_review_required"
NEXT_MINING = "v7_1_positive_candidate_mining_expansion"
NEXT_GROUP_MINING = "v7_1_positive_candidate_mining_new_groups"

BLOCKER_REVIEW_YIELD = "v7_1_positive_diversity_review_yield_insufficient"
BLOCKER_GROUPS = "v7_1_positive_diversity_temporal_cluster_insufficient"
BLOCKER_KNOWN_MISSES = "v7_1_positive_diversity_known_misses_not_reviewed"
BLOCKER_SPLIT = "v7_1_positive_diversity_split_leakage"
BLOCKER_UNSAFE_NEGATIVE = "v7_1_positive_diversity_unsafe_negative_reintroduced"

POSITIVE_STATUS = "reviewed_positive_ball"
NEGATIVE_STATUS = "reviewed_not_ball"
UNCLEAR_STATUS = "review_deferred_unclear"
DUPLICATE_STATUS = "duplicate_or_near_duplicate"
BAD_FRAME_STATUS = "bad_crop_or_unusable_frame"
PENDING_STATUS = "pending_review"


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


def _source_key(row: dict[str, Any]) -> str:
    return f"{row.get('sourceClipId')}:{row.get('frameIndex')}"


def _split_group_for(row: dict[str, Any]) -> str:
    if row.get("splitGroupId"):
        return str(row["splitGroupId"])
    source_clip_id = str(row.get("sourceClipId") or "unknown-clip")
    frame_index = _safe_int(row.get("frameIndex"))
    return f"{source_clip_id}-positive-diversity-cluster-{frame_index // 100:04d}"


def _normalize_candidate(row: dict[str, Any], *, default_status: str = PENDING_STATUS) -> dict[str, Any]:
    frame_index = _safe_int(row.get("frameIndex"))
    source_clip_id = str(row.get("sourceClipId") or "trimed-5min.mp4")
    candidate_id = str(row.get("candidateId") or f"candidate-{source_clip_id}-{frame_index}")
    normalized = {
        "candidateId": candidate_id,
        "reviewStatus": str(row.get("reviewStatus") or row.get("decision") or default_status),
        "candidateStatus": str(row.get("candidateStatus") or "proposed_positive_candidate"),
        "source": str(row.get("source") or "positive_diversity_manual_review_expansion"),
        "sourceClipId": source_clip_id,
        "frameIndex": frame_index,
        "sourceFrameBbox": row.get("sourceFrameBbox"),
        "visibilityClass": row.get("visibilityClass") or "unknown_until_review",
        "contextTags": row.get("contextTags") or [],
        "splitGroupId": _split_group_for(row),
        "reviewer": row.get("reviewer") or "manual_required",
        "trainingEligibility": "pending_review",
        "recommendedCropVariants": row.get("recommendedCropVariants") or [192, 256, 384],
        "labelPolicy": "requires_human_review_before_training",
    }
    if normalized["reviewStatus"] == POSITIVE_STATUS:
        normalized["trainingEligibility"] = "eligible_positive_truth"
    elif normalized["reviewStatus"] in {NEGATIVE_STATUS, UNCLEAR_STATUS, DUPLICATE_STATUS, BAD_FRAME_STATUS}:
        normalized["trainingEligibility"] = "evidence_only_not_positive_training_truth"
    return normalized


def _load_existing_sources(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for crop in manifest.get("positiveCropExamples", []):
        if not isinstance(crop, dict):
            continue
        key = _source_key(crop)
        rows.setdefault(
            key,
            {
                "sourceClipId": crop.get("sourceClipId"),
                "frameIndex": crop.get("frameIndex"),
                "sourceFrameBbox": crop.get("sourceFrameBbox"),
                "splitGroupId": crop.get("splitGroupId") or _split_group_for(crop),
            },
        )
    return rows


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        normalized = _normalize_candidate(candidate)
        candidate_id = str(normalized["candidateId"])
        by_id.setdefault(candidate_id, normalized)
    return list(by_id.values())


def _mine_surplus_candidates(
    *,
    base_candidates: list[dict[str, Any]],
    existing_sources: dict[str, dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    candidates = _dedupe_candidates(base_candidates)
    seen_ids = {str(row["candidateId"]) for row in candidates}
    seen_frames = {(str(row.get("sourceClipId")), _safe_int(row.get("frameIndex"))) for row in candidates}
    anchors = sorted(existing_sources.values(), key=lambda row: (str(row.get("sourceClipId")), _safe_int(row.get("frameIndex"))))
    if not anchors:
        anchors = [{"sourceClipId": "trimed-5min.mp4", "frameIndex": 0, "sourceFrameBbox": None}]
    offsets = [-240, -180, -120, -60, 60, 120, 180, 240, 360, 480]
    round_index = 0
    while len(candidates) < target_count:
        anchor = anchors[round_index % len(anchors)]
        offset = offsets[(round_index // len(anchors)) % len(offsets)]
        frame_index = max(0, _safe_int(anchor.get("frameIndex")) + offset + (round_index // (len(anchors) * len(offsets))) * 37)
        source_clip_id = str(anchor.get("sourceClipId") or "trimed-5min.mp4")
        frame_key = (source_clip_id, frame_index)
        candidate_id = f"surplus-positive-diversity-{source_clip_id}-{frame_index}"
        round_index += 1
        if candidate_id in seen_ids or frame_key in seen_frames:
            continue
        seen_ids.add(candidate_id)
        seen_frames.add(frame_key)
        candidates.append(
            _normalize_candidate(
                {
                    "candidateId": candidate_id,
                    "candidateStatus": "proposed_positive_candidate",
                    "source": "positive_diversity_surplus_temporal_mining",
                    "sourceClipId": source_clip_id,
                    "frameIndex": frame_index,
                    "sourceFrameBbox": anchor.get("sourceFrameBbox"),
                    "contextTags": ["surplus_temporal_candidate"],
                    "reviewAction": "manual_review_required",
                }
            )
        )
    return candidates


def _overlay_items(existing_overlay: dict[str, Any], generated_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_items = existing_overlay.get("reviewItems") or existing_overlay.get("items") or []
    if isinstance(existing_items, list) and existing_items:
        return [_normalize_candidate(item) for item in existing_items if isinstance(item, dict)]
    return generated_candidates


def _counts(review_items: list[dict[str, Any]], previous_count: int) -> dict[str, Any]:
    positive = [row for row in review_items if row.get("reviewStatus") == POSITIVE_STATUS]
    reviewed_not_ball = [row for row in review_items if row.get("reviewStatus") == NEGATIVE_STATUS]
    unclear = [row for row in review_items if row.get("reviewStatus") == UNCLEAR_STATUS]
    duplicates = [row for row in review_items if row.get("reviewStatus") == DUPLICATE_STATUS]
    bad_frames = [row for row in review_items if row.get("reviewStatus") == BAD_FRAME_STATUS]
    pending = [row for row in review_items if row.get("reviewStatus") == PENDING_STATUS]
    groups = {str(row.get("splitGroupId")) for row in positive if row.get("splitGroupId")}
    known_crop_reviewed = [
        row
        for row in review_items
        if row.get("source") == "v7_1_crop_probe_precision_guardrail_audit" and row.get("reviewStatus") != PENDING_STATUS
    ]
    known_pipeline_reviewed = [
        row
        for row in review_items
        if row.get("source") == "v7_1_full_pipeline_non_promotion_eval" and row.get("reviewStatus") != PENDING_STATUS
    ]
    known_crop_positive = [row for row in known_crop_reviewed if row.get("reviewStatus") == POSITIVE_STATUS]
    known_pipeline_positive = [row for row in known_pipeline_reviewed if row.get("reviewStatus") == POSITIVE_STATUS]
    return {
        "reviewQueueCandidateCount": len(review_items),
        "reviewedCandidateCount": len(review_items) - len(pending),
        "pendingReviewCount": len(pending),
        "newReviewedPositiveSourceCount": len(positive),
        "totalReviewedPositiveSourceCount": previous_count + len(positive),
        "reviewedNotBallCount": len(reviewed_not_ball),
        "reviewDeferredUnclearCount": len(unclear),
        "duplicateOrNearDuplicateCount": len(duplicates),
        "badCropOrUnusableFrameCount": len(bad_frames),
        "distinctPositiveSplitGroupCount": len(groups),
        "knownCropValidationMissesReviewed": len(known_crop_reviewed),
        "knownCropValidationMissesAcceptedAsPositive": len(known_crop_positive),
        "knownFullPipelineMissesReviewed": len(known_pipeline_reviewed),
        "knownFullPipelineMissesAcceptedAsPositive": len(known_pipeline_positive),
    }


def _split_leakage(review_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, set[str]] = {}
    for row in review_items:
        group = str(row.get("splitGroupId") or "")
        split = str(row.get("split") or "")
        if not group or not split:
            continue
        by_group.setdefault(group, set()).add(split)
    return [
        {"splitGroupId": group, "splits": sorted(splits)}
        for group, splits in sorted(by_group.items())
        if len(splits) > 1
    ]


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if summary["unsafeFullFrameNegativeExportCount"] > 0 or summary["fullFrameEmptyLabelNegativeExportCount"] > 0:
        return BLOCKER_UNSAFE_NEGATIVE, NEXT_MANUAL_REVIEW, False, "Unsafe negatives reappeared; stop before any v7.2 manifest prep."
    if summary["splitLeakageCount"] > 0:
        return BLOCKER_SPLIT, "v7_1_positive_diversity_split_policy_refresh", False, "Positive review decisions contain split leakage."
    if summary["pendingReviewCount"] > 0:
        return None, NEXT_MANUAL_REVIEW, True, "Manual positive diversity review package is ready; resolve pending review decisions before v7.2 prep."
    if summary["knownCropValidationMissesReviewed"] < 9 or summary["knownFullPipelineMissesReviewed"] < 2:
        return BLOCKER_KNOWN_MISSES, NEXT_MANUAL_REVIEW, False, "Known v7.1 misses were not fully reviewed."
    if summary["newReviewedPositiveSourceCount"] < MIN_NEW_REVIEWED_POSITIVES or summary["totalReviewedPositiveSourceCount"] < MIN_TOTAL_REVIEWED_POSITIVES:
        return BLOCKER_REVIEW_YIELD, NEXT_MINING, True, "Manual review improved truth but did not reach the reviewed-positive threshold."
    if summary["distinctPositiveSplitGroupCount"] < MIN_SPLIT_GROUPS:
        return BLOCKER_GROUPS, NEXT_GROUP_MINING, True, "Reviewed-positive count passed, but temporal/source diversity remains too narrow."
    return None, NEXT_V72_PREP, True, "Positive diversity expanded enough for v7.2 manifest prep. Do not train or promote yet."


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Positive Diversity Manual Review Expansion",
            "",
            f"- Batch status: `{summary.get('batchStatus')}`",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Review queue candidates: `{summary.get('reviewQueueCandidateCount')}`",
            f"- Pending review count: `{summary.get('pendingReviewCount')}`",
            f"- New reviewed positives: `{summary.get('newReviewedPositiveSourceCount')}`",
            f"- Total reviewed positives: `{summary.get('totalReviewedPositiveSourceCount')}`",
            f"- Split groups: `{summary.get('distinctPositiveSplitGroupCount')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_positive_diversity_manual_review_expansion(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "positive_review_package_generation",
    review_target_count: int = DEFAULT_REVIEW_TARGET_COUNT,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    refresh_root = candidate_root / "v7_1_positive_diversity_refresh_v1"
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    output_root = candidate_root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)

    refresh_summary = _load_json(refresh_root / "v7_1_positive_diversity_refresh_summary.json", required=True)
    review_queue = _load_json(refresh_root / "positive_review_queue.json", required=True)
    crop_manifest = _load_json(manifest_root / "v7_1_local_crop_training_manifest.json", required=True)
    existing_overlay = _load_json(output_root / "reviewed_label_overlay.json")

    previous_count = _safe_int(refresh_summary.get("totalReviewedPositiveSourceCount"), _safe_int(crop_manifest.get("reviewedPositiveSourceCount"), 30))
    existing_sources = _load_existing_sources(crop_manifest)
    base_candidates = [row for row in review_queue.get("candidates", []) if isinstance(row, dict)]
    generated_candidates = _mine_surplus_candidates(
        base_candidates=base_candidates,
        existing_sources=existing_sources,
        target_count=review_target_count,
    )
    review_items = _overlay_items(existing_overlay, generated_candidates)
    split_leaks = _split_leakage(review_items)
    count_payload = _counts(review_items, previous_count)
    unsafe_count = _safe_int(crop_manifest.get("unsafeFullFrameNegativeExportCount"))
    full_frame_empty_count = _safe_int(crop_manifest.get("fullFrameEmptyLabelNegativeExportCount"))
    summary: dict[str, Any] = {
        "batchName": "v7_1_positive_diversity_manual_review_expansion",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "previousReviewedPositiveSourceCount": previous_count,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "unsafeFullFrameNegativeExportCount": unsafe_count,
        "fullFrameEmptyLabelNegativeExportCount": full_frame_empty_count,
        "splitLeakageCount": len(split_leaks),
        "secondaryConcernCarriedForward": refresh_summary.get("secondaryConcernCarriedForward"),
        **count_payload,
    }
    primary_blocker, next_family, goal_achieved, english = _classify(summary)
    summary.update(
        {
            "batchStatus": "manual_review_pending" if summary["pendingReviewCount"] > 0 else "review_resolved",
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": goal_achieved,
            "primaryBlocker": primary_blocker,
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )

    additions = [row for row in review_items if row.get("reviewStatus") == POSITIVE_STATUS]
    rejections = [row for row in review_items if row.get("reviewStatus") == NEGATIVE_STATUS]
    unclear = [row for row in review_items if row.get("reviewStatus") == UNCLEAR_STATUS]
    duplicates = [row for row in review_items if row.get("reviewStatus") == DUPLICATE_STATUS]
    hard_cases = [
        row
        for row in review_items
        if row.get("source") in {"v7_1_crop_probe_precision_guardrail_audit", "v7_1_full_pipeline_non_promotion_eval"}
    ]

    overlay = {
        "batchName": summary["batchName"],
        "reviewItemCount": len(review_items),
        "pendingReviewCount": summary["pendingReviewCount"],
        "allowedReviewStatuses": [POSITIVE_STATUS, NEGATIVE_STATUS, UNCLEAR_STATUS, DUPLICATE_STATUS, BAD_FRAME_STATUS, PENDING_STATUS],
        "reviewItems": review_items,
    }
    _write_json(output_root / "reviewed_label_overlay.json", overlay)
    _write_json(output_root / "reviewed_positive_additions.json", {"newReviewedPositiveSourceCount": len(additions), "rows": additions})
    _write_json(output_root / "reviewed_positive_rejections.json", {"reviewedNotBallCount": len(rejections), "rows": rejections})
    _write_json(output_root / "reviewed_positive_unclear.json", {"reviewDeferredUnclearCount": len(unclear), "rows": unclear})
    _write_json(output_root / "reviewed_positive_duplicates.json", {"duplicateOrNearDuplicateCount": len(duplicates), "rows": duplicates})
    _write_json(output_root / "positive_review_queue_expanded.json", {"candidateCount": len(generated_candidates), "candidates": generated_candidates})
    _write_json(output_root / "positive_diversity_summary.json", {k: summary[k] for k in sorted(summary) if k.endswith("Count") or k in {"distinctPositiveSplitGroupCount"}})
    _write_json(output_root / "positive_split_group_audit.json", {"splitLeakageCount": len(split_leaks), "leaks": split_leaks})
    _write_json(output_root / "positive_hard_case_overlay_contact_sheet_manifest.json", {"hardCaseCount": len(hard_cases), "rows": hard_cases})
    _write_json(output_root / "positive_review_overlay_contact_sheet_manifest.json", {"candidateCount": len(review_items), "rows": review_items[:80]})
    _write_json(output_root / "v7_1_positive_diversity_manual_review_expansion_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or resolve the v7.1 positive diversity manual review expansion package.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="positive_review_package_generation")
    parser.add_argument("--review-target-count", type=int, default=DEFAULT_REVIEW_TARGET_COUNT)
    args = parser.parse_args()
    payload = run_v7_1_positive_diversity_manual_review_expansion(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
        review_target_count=args.review_target_count,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
