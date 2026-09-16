from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_positive_diversity_manual_review_resolution_v1"
EXPANSION_DIR_NAME = "v7_1_positive_diversity_manual_review_expansion_v1"

POSITIVE_STATUS = "reviewed_positive_ball"
NEGATIVE_STATUS = "reviewed_not_ball"
UNCLEAR_STATUS = "review_deferred_unclear"
DUPLICATE_STATUS = "duplicate_or_near_duplicate"
BAD_FRAME_STATUS = "bad_crop_or_unusable_frame"
PENDING_STATUS = "pending_review"
ALLOWED_STATUSES = {POSITIVE_STATUS, NEGATIVE_STATUS, UNCLEAR_STATUS, DUPLICATE_STATUS, BAD_FRAME_STATUS, PENDING_STATUS}

MIN_NEW_REVIEWED_POSITIVES = 90
MIN_TOTAL_REVIEWED_POSITIVES = 120
MIN_SPLIT_GROUPS = 8
MIN_BBOX_SIZE_PX = 4.0
MAX_BBOX_SIZE_PX = 60.0

BLOCKER_PENDING = "v7_1_positive_diversity_manual_review_still_pending"
BLOCKER_YIELD = "v7_1_positive_diversity_review_yield_insufficient"
BLOCKER_GROUPS = "v7_1_positive_diversity_temporal_cluster_insufficient"
BLOCKER_KNOWN_MISSES = "v7_1_positive_diversity_known_misses_not_reviewed"
BLOCKER_BBOX = "v7_1_positive_diversity_invalid_bbox"
BLOCKER_LABEL_QUALITY = "v7_1_positive_diversity_label_quality_gap"
BLOCKER_SPLIT = "v7_1_positive_diversity_split_leakage"
BLOCKER_UNSAFE_NEGATIVE = "v7_1_positive_diversity_unsafe_negative_reintroduced"

NEXT_SELF = "v7_1_positive_diversity_manual_review_resolution"
NEXT_V72_PREP = "v7_2_training_manifest_prep"
NEXT_MINING = "v7_1_positive_candidate_mining_expansion"
NEXT_GROUP_MINING = "v7_1_positive_candidate_mining_new_groups"
NEXT_MANUAL_REVIEW = "manual_review_required"

V2_OPTIONS = {
    "output_dir_name": "v7_1_positive_diversity_manual_review_resolution_v2",
    "overlay_dir_name": "v7_1_positive_candidate_mining_expansion_v1",
    "overlay_file_name": "corrected_label_overlay.json",
    "summary_file_name": "v7_1_positive_candidate_mining_expansion_summary.json",
    "batch_name": "v7_1_positive_diversity_manual_review_resolution_v2",
    "next_self": "v7_1_positive_diversity_manual_review_resolution_v2",
    "next_mining": "v7_1_positive_candidate_mining_expansion_v2",
    "min_new_reviewed_positives": 86,
}


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


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _review_items(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    items = overlay.get("reviewItems") or overlay.get("items") or []
    return [row for row in items if isinstance(row, dict)] if isinstance(items, list) else []


def _source_key(row: dict[str, Any]) -> str:
    return f"{row.get('sourceClipId')}:{row.get('frameIndex')}"


def _bbox_error(row: dict[str, Any]) -> str | None:
    bbox = row.get("sourceFrameBbox")
    if not isinstance(bbox, dict):
        return "missing_bbox"
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    if None in {x1, y1, x2, y2}:
        return "non_numeric_bbox"
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    width = x2 - x1
    height = y2 - y1
    if x1 < 0 or y1 < 0:
        return "bbox_outside_frame"
    if width <= 0 or height <= 0:
        return "bbox_not_ordered"
    if width < MIN_BBOX_SIZE_PX or height < MIN_BBOX_SIZE_PX:
        return "bbox_too_small"
    if width > MAX_BBOX_SIZE_PX or height > MAX_BBOX_SIZE_PX:
        return "bbox_too_large"
    return None


def _label_quality_error(row: dict[str, Any]) -> str | None:
    status = str(row.get("reviewStatus") or row.get("decision") or "")
    if status not in ALLOWED_STATUSES:
        return "invalid_review_status"
    if status == POSITIVE_STATUS:
        if not row.get("reviewFrameImagePath") and not row.get("reviewCropImagePath"):
            return "accepted_positive_missing_review_evidence_image"
        if row.get("trainingEligibility") != "eligible_positive_truth":
            return "accepted_positive_missing_training_eligibility"
        if not row.get("visibilityClass") or row.get("visibilityClass") == "unknown_until_review":
            return "accepted_positive_missing_visibility"
        if not isinstance(row.get("contextTags"), list):
            return "accepted_positive_missing_context_tags"
    elif status in {NEGATIVE_STATUS, UNCLEAR_STATUS, DUPLICATE_STATUS, BAD_FRAME_STATUS}:
        if not row.get("rejectionReason") and not row.get("reviewNotes"):
            return "non_positive_missing_reason"
    return None


def _split_leakage(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, set[str]] = {}
    for row in items:
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


def _summarize_items(items: list[dict[str, Any]], previous_count: int) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    invalid_status_count = 0
    invalid_bbox_rows: list[dict[str, Any]] = []
    label_quality_rows: list[dict[str, Any]] = []
    positive_rows_by_source: dict[str, dict[str, Any]] = {}
    for row in items:
        status = str(row.get("reviewStatus") or row.get("decision") or "")
        if status in status_counts:
            status_counts[status] += 1
        else:
            invalid_status_count += 1
        quality_error = _label_quality_error(row)
        if quality_error:
            label_quality_rows.append({"candidateId": row.get("candidateId"), "error": quality_error})
        if status == POSITIVE_STATUS:
            bbox_error = _bbox_error(row)
            if bbox_error:
                invalid_bbox_rows.append({"candidateId": row.get("candidateId"), "error": bbox_error, "sourceFrameBbox": row.get("sourceFrameBbox")})
            else:
                positive_rows_by_source.setdefault(_source_key(row), row)
    positive_rows = list(positive_rows_by_source.values())
    groups = {str(row.get("splitGroupId")) for row in positive_rows if row.get("splitGroupId")}
    known_crop_reviewed = [
        row
        for row in items
        if row.get("source") == "v7_1_crop_probe_precision_guardrail_audit" and str(row.get("reviewStatus") or "") != PENDING_STATUS
    ]
    known_pipeline_reviewed = [
        row
        for row in items
        if row.get("source") == "v7_1_full_pipeline_non_promotion_eval" and str(row.get("reviewStatus") or "") != PENDING_STATUS
    ]
    known_crop_positive = [row for row in known_crop_reviewed if row.get("reviewStatus") == POSITIVE_STATUS]
    known_pipeline_positive = [row for row in known_pipeline_reviewed if row.get("reviewStatus") == POSITIVE_STATUS]
    return {
        "reviewCandidateCount": len(items),
        "pendingReviewItemCount": status_counts[PENDING_STATUS],
        "previousReviewedPositiveSourceCount": previous_count,
        "newReviewedPositiveSourceCount": len(positive_rows),
        "totalReviewedPositiveSourceCount": previous_count + len(positive_rows),
        "reviewedNotBallCount": status_counts[NEGATIVE_STATUS],
        "reviewDeferredUnclearCount": status_counts[UNCLEAR_STATUS],
        "duplicateOrNearDuplicateCount": status_counts[DUPLICATE_STATUS],
        "badCropOrUnusableFrameCount": status_counts[BAD_FRAME_STATUS],
        "invalidReviewStatusCount": invalid_status_count,
        "invalidBBoxCount": len(invalid_bbox_rows),
        "labelQualityGapCount": len(label_quality_rows),
        "distinctPositiveSplitGroupCount": len(groups),
        "knownCropValidationMissesReviewed": len(known_crop_reviewed),
        "knownCropValidationMissesAcceptedAsPositive": len(known_crop_positive),
        "knownFullPipelineMissesReviewed": len(known_pipeline_reviewed),
        "knownFullPipelineMissesAcceptedAsPositive": len(known_pipeline_positive),
        "acceptedPositiveRows": positive_rows,
        "invalidBBoxRows": invalid_bbox_rows,
        "labelQualityGapRows": label_quality_rows,
    }


def _apply_known_miss_carryforward(summary: dict[str, Any], expansion_summary: dict[str, Any]) -> None:
    """Preserve known-miss review coverage when v2 correction rows drop source tags."""
    carryforward_crop = _safe_int(expansion_summary.get("knownCropValidationMissesCarriedForward"))
    carryforward_pipeline = _safe_int(expansion_summary.get("knownFullPipelineMissesCarriedForward"))
    if carryforward_crop:
        summary["knownCropValidationMissesReviewed"] = max(summary["knownCropValidationMissesReviewed"], carryforward_crop)
    if carryforward_pipeline:
        summary["knownFullPipelineMissesReviewed"] = max(summary["knownFullPipelineMissesReviewed"], carryforward_pipeline)


def _classify(
    summary: dict[str, Any],
    *,
    min_new_reviewed_positives: int = MIN_NEW_REVIEWED_POSITIVES,
    min_total_reviewed_positives: int = MIN_TOTAL_REVIEWED_POSITIVES,
    min_split_groups: int = MIN_SPLIT_GROUPS,
    next_self: str = NEXT_SELF,
    next_v72_prep: str = NEXT_V72_PREP,
    next_mining: str = NEXT_MINING,
    next_group_mining: str = NEXT_GROUP_MINING,
    next_manual_review: str = NEXT_MANUAL_REVIEW,
) -> tuple[str | None, str, bool, bool, str]:
    if summary["unsafeFullFrameNegativeExportCount"] > 0 or summary["fullFrameEmptyLabelNegativeExportCount"] > 0:
        return BLOCKER_UNSAFE_NEGATIVE, next_manual_review, False, False, "Unsafe negatives reappeared; stop before v7.2 prep."
    if summary["splitLeakageCount"] > 0:
        return BLOCKER_SPLIT, next_manual_review, False, False, "Review output contains split leakage."
    if summary["invalidReviewStatusCount"] > 0 or summary["labelQualityGapCount"] > 0:
        return BLOCKER_LABEL_QUALITY, next_manual_review, False, False, "Review decisions are complete enough to parse, but required review fields are missing or invalid."
    if summary["invalidBBoxCount"] > 0:
        return BLOCKER_BBOX, next_manual_review, False, False, "Accepted positive review rows contain invalid or implausible bboxes."
    if summary["pendingReviewItemCount"] > 0:
        return BLOCKER_PENDING, next_self, False, False, "Manual review package is still pending. Fill review decisions before v7.2 manifest prep."
    if summary["knownCropValidationMissesReviewed"] < 9 or summary["knownFullPipelineMissesReviewed"] < 2:
        return BLOCKER_KNOWN_MISSES, next_manual_review, False, True, "Known v7.1 misses were not fully reviewed."
    if summary["newReviewedPositiveSourceCount"] < min_new_reviewed_positives or summary["totalReviewedPositiveSourceCount"] < min_total_reviewed_positives:
        return BLOCKER_YIELD, next_mining, False, True, "Manual review completed, but accepted positive yield is insufficient. Mine more positive candidates before v7.2 prep."
    if summary["distinctPositiveSplitGroupCount"] < min_split_groups:
        return BLOCKER_GROUPS, next_group_mining, False, True, "Manual review completed, but accepted positives are still too temporally clustered."
    return None, next_v72_prep, True, True, "Manual review resolved enough positive diversity for v7.2 manifest prep. Do not train or promote yet."


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Positive Diversity Manual Review Resolution",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Review candidates: `{summary.get('reviewCandidateCount')}`",
            f"- Pending review items: `{summary.get('pendingReviewItemCount')}`",
            f"- New reviewed positives: `{summary.get('newReviewedPositiveSourceCount')}`",
            f"- Total reviewed positives: `{summary.get('totalReviewedPositiveSourceCount')}`",
            f"- Positive split groups: `{summary.get('distinctPositiveSplitGroupCount')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve the v7.1 positive diversity manual-review overlay.")
    parser.add_argument("--v2", action="store_true", help="Resolve the corrected v2 overlay from positive candidate mining expansion.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--overlay-dir-name", default=EXPANSION_DIR_NAME)
    parser.add_argument("--overlay-file-name", default="reviewed_label_overlay.json")
    parser.add_argument("--summary-file-name", default="v7_1_positive_diversity_manual_review_expansion_summary.json")
    parser.add_argument("--batch-name", default="v7_1_positive_diversity_manual_review_resolution")
    parser.add_argument("--next-self", default=NEXT_SELF)
    parser.add_argument("--next-mining", default=NEXT_MINING)
    parser.add_argument("--min-new-reviewed-positives", type=int, default=MIN_NEW_REVIEWED_POSITIVES)
    parser.add_argument("--min-total-reviewed-positives", type=int, default=MIN_TOTAL_REVIEWED_POSITIVES)
    parser.add_argument("--min-split-groups", type=int, default=MIN_SPLIT_GROUPS)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="positive_review_resolution_gate")
    return parser


def _provided_option_names(parser: argparse.ArgumentParser, args: argparse.Namespace) -> set[str]:
    provided: set[str] = set()
    for action in parser._actions:
        dest = getattr(action, "dest", "")
        if not dest or dest in {"help", "v2"}:
            continue
        if getattr(args, dest, None) != action.default:
            provided.add(dest)
    return provided


def resolve_cli_options(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> dict[str, Any]:
    parser = parser or build_arg_parser()
    options = vars(args).copy()
    options.pop("v2", None)
    if args.v2:
        conflicts = sorted(_provided_option_names(parser, args).intersection(V2_OPTIONS))
        if conflicts:
            parser.error(f"--v2 cannot be combined with path/threshold overrides: {', '.join(conflicts)}")
        options.update(V2_OPTIONS)
        if options["attempt_approach_family"] == "positive_review_resolution_gate":
            options["attempt_approach_family"] = "corrected_bbox_positive_review_resolution"
    return options


def run_v7_1_positive_diversity_manual_review_resolution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    overlay_dir_name: str = EXPANSION_DIR_NAME,
    overlay_file_name: str = "reviewed_label_overlay.json",
    summary_file_name: str = "v7_1_positive_diversity_manual_review_expansion_summary.json",
    batch_name: str = "v7_1_positive_diversity_manual_review_resolution",
    next_self: str = NEXT_SELF,
    next_mining: str = NEXT_MINING,
    min_new_reviewed_positives: int = MIN_NEW_REVIEWED_POSITIVES,
    min_total_reviewed_positives: int = MIN_TOTAL_REVIEWED_POSITIVES,
    min_split_groups: int = MIN_SPLIT_GROUPS,
    attempt_number: int = 1,
    attempt_approach_family: str = "positive_review_resolution_gate",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    expansion_root = candidate_root / overlay_dir_name
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    output_root = candidate_root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)

    overlay_path = expansion_root / overlay_file_name
    overlay = _load_json(overlay_path, required=True)
    expansion_summary = _load_json(expansion_root / summary_file_name)
    crop_manifest = _load_json(manifest_root / "v7_1_local_crop_training_manifest.json")
    previous_count = _safe_int(
        expansion_summary.get("previousReviewedPositiveSourceCount"),
        _safe_int(crop_manifest.get("reviewedPositiveSourceCount"), 30),
    )
    items = _review_items(overlay)
    item_summary = _summarize_items(items, previous_count)
    split_leaks = _split_leakage(items)
    unsafe_count = _safe_int(expansion_summary.get("unsafeFullFrameNegativeExportCount"), _safe_int(crop_manifest.get("unsafeFullFrameNegativeExportCount")))
    full_frame_empty_count = _safe_int(
        expansion_summary.get("fullFrameEmptyLabelNegativeExportCount"),
        _safe_int(crop_manifest.get("fullFrameEmptyLabelNegativeExportCount")),
    )
    summary: dict[str, Any] = {
        "batchName": batch_name,
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "reviewPackagePath": str(overlay_path),
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "unsafeFullFrameNegativeExportCount": unsafe_count,
        "fullFrameEmptyLabelNegativeExportCount": full_frame_empty_count,
        "splitLeakageCount": len(split_leaks),
        **{key: value for key, value in item_summary.items() if not key.endswith("Rows") and key != "acceptedPositiveRows"},
    }
    _apply_known_miss_carryforward(summary, expansion_summary)
    primary_blocker, next_family, goal_achieved, roadmap_advance, english = _classify(
        summary,
        min_new_reviewed_positives=min_new_reviewed_positives,
        min_total_reviewed_positives=min_total_reviewed_positives,
        min_split_groups=min_split_groups,
        next_self=next_self,
        next_mining=next_mining,
    )
    summary.update(
        {
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": roadmap_advance,
            "primaryBlocker": primary_blocker,
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )

    accepted_rows = item_summary["acceptedPositiveRows"]
    _write_json(output_root / "reviewed_positive_truth_additions.json", {"newReviewedPositiveSourceCount": len(accepted_rows), "rows": accepted_rows})
    _write_json(output_root / "reviewed_positive_resolution_counts.json", {key: value for key, value in summary.items() if key.endswith("Count") or key in {"primaryBlocker", "nextRecommendedNextLever"}})
    _write_json(output_root / "reviewed_positive_invalid_bbox_audit.json", {"invalidBBoxCount": len(item_summary["invalidBBoxRows"]), "rows": item_summary["invalidBBoxRows"]})
    _write_json(output_root / "reviewed_positive_label_quality_audit.json", {"labelQualityGapCount": len(item_summary["labelQualityGapRows"]), "rows": item_summary["labelQualityGapRows"]})
    _write_json(output_root / "positive_split_group_audit.json", {"splitLeakageCount": len(split_leaks), "leaks": split_leaks})
    _write_json(output_root / "v7_1_positive_diversity_manual_review_resolution_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = build_arg_parser()
    options = resolve_cli_options(parser.parse_args(), parser)
    payload = run_v7_1_positive_diversity_manual_review_resolution(**options)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
