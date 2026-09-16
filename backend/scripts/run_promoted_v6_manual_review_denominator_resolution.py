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

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_EXPANSION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_denominator_expansion_v1"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "manual_review_denominator_resolution_v1"
DEFAULT_V7_REFRESH_ROOT = DEFAULT_SUITE_ROOT / "touchline_detector_candidate_v7_training_data_refresh_v1"
DEFAULT_MIN_TOTAL_POSITIVE_FRAMES = 20
POSITIVE_DECISIONS = {"accept_seed", "adjust_bbox"}
NEGATIVE_DECISIONS = {"reject_seed", "confirm_hard_negative"}
ALLOWED_DECISIONS = {"pending_review", *POSITIVE_DECISIONS, *NEGATIVE_DECISIONS}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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


def _lineage_complete(item: dict[str, Any]) -> bool:
    lineage = item.get("lineage")
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


def _review_items(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(overlay.get("reviewItems")),
        key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")),
    )


def _validate_item(item: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    decision = str(item.get("decision") or "")
    if decision not in ALLOWED_DECISIONS:
        return ["unknown_review_decision"]
    if decision == "accept_seed" and not _valid_bbox_payload(item.get("seedBBox")):
        reasons.append("accept_seed_requires_valid_seed_bbox")
    if decision == "adjust_bbox" and not _valid_bbox_payload(item.get("reviewedBBox")):
        reasons.append("adjust_bbox_requires_reviewed_bbox")
    return reasons


def _build_review_decision_matrix(overlay: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "reviewItemCount": 0,
        "pendingReviewCount": 0,
        "acceptedSeedCount": 0,
        "adjustedBBoxCount": 0,
        "rejectedSeedCount": 0,
        "confirmedHardNegativeCount": 0,
        "denominatorReviewedPositiveCount": 0,
        "denominatorReviewedNegativeCount": 0,
        "invalidDecisionCount": 0,
        "lineageCompleteCount": 0,
    }
    rows: list[dict[str, Any]] = []
    repair_guidance: dict[str, list[str]] = {}
    for item in _review_items(overlay):
        decision = str(item.get("decision") or "")
        reasons = _validate_item(item)
        review_item_id = str(item.get("reviewItemId") or "")
        counts["reviewItemCount"] += 1
        if decision == "pending_review":
            counts["pendingReviewCount"] += 1
        if decision == "accept_seed":
            counts["acceptedSeedCount"] += 1
        if decision == "adjust_bbox":
            counts["adjustedBBoxCount"] += 1
        if decision == "reject_seed":
            counts["rejectedSeedCount"] += 1
        if decision == "confirm_hard_negative":
            counts["confirmedHardNegativeCount"] += 1
        if decision in POSITIVE_DECISIONS:
            counts["denominatorReviewedPositiveCount"] += 1
        if decision in NEGATIVE_DECISIONS:
            counts["denominatorReviewedNegativeCount"] += 1
        if _lineage_complete(item):
            counts["lineageCompleteCount"] += 1
        if reasons:
            counts["invalidDecisionCount"] += 1
            repair_guidance[review_item_id] = reasons
        rows.append(
            {
                "reviewItemId": review_item_id,
                "frameIndex": item.get("frameIndex"),
                "sourceClipId": item.get("sourceClipId"),
                "candidateFrameId": item.get("candidateFrameId"),
                "decision": decision,
                "valid": not reasons,
                "invalidReasons": reasons,
                "lineageComplete": _lineage_complete(item),
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        **counts,
        "repairGuidanceByReviewItemId": repair_guidance,
        "reviewDecisions": rows,
    }


def _build_truth_seed(overlay: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    if _safe_int(matrix.get("pendingReviewCount"), 0) > 0 or _safe_int(matrix.get("invalidDecisionCount"), 0) > 0:
        return {
            "generatedAt": _utc_now_iso(),
            "truthStatus": "not_ready_pending_or_invalid_review",
            "reviewedPositiveSeedCount": 0,
            "reviewedNegativeSeedCount": 0,
            "reviewedPositiveSeedRows": [],
            "reviewedNegativeSeedRows": [],
        }
    positive_rows: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    for item in _review_items(overlay):
        decision = str(item.get("decision") or "")
        if decision in POSITIVE_DECISIONS:
            reviewed_bbox = item.get("reviewedBBox") if decision == "adjust_bbox" else item.get("seedBBox")
            positive_rows.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "candidateFrameId": item.get("candidateFrameId"),
                    "frameIndex": item.get("frameIndex"),
                    "timestampSeconds": item.get("timestampSeconds"),
                    "sourceClipId": item.get("sourceClipId"),
                    "reviewDecision": decision,
                    "seedBBox": item.get("seedBBox"),
                    "reviewedBBox": reviewed_bbox,
                    "lineage": item.get("lineage") if isinstance(item.get("lineage"), dict) else {},
                    "reviewedBy": item.get("reviewedBy"),
                    "reviewMethod": item.get("reviewMethod"),
                    "truthUse": "reviewed_positive_denominator_seed",
                }
            )
        elif decision in NEGATIVE_DECISIONS:
            negative_rows.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "candidateFrameId": item.get("candidateFrameId"),
                    "frameIndex": item.get("frameIndex"),
                    "sourceClipId": item.get("sourceClipId"),
                    "reviewDecision": decision,
                    "truthUse": "reviewed_negative_denominator_refutation",
                }
            )
    return {
        "generatedAt": _utc_now_iso(),
        "truthStatus": "review_resolved",
        "reviewedPositiveSeedCount": len(positive_rows),
        "reviewedNegativeSeedCount": len(negative_rows),
        "reviewedPositiveSeedRows": positive_rows,
        "reviewedNegativeSeedRows": negative_rows,
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Manual Review Denominator Resolution",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- denominatorReviewedPositiveCount: {summary.get('denominatorReviewedPositiveCount')}",
            f"- denominatorReviewedNegativeCount: {summary.get('denominatorReviewedNegativeCount')}",
            f"- totalReviewedPositiveFrameCount: {summary.get('totalReviewedPositiveFrameCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def _decision_for(matrix: dict[str, Any], *, total_positive_count: int, min_total_positive_frames: int) -> dict[str, Any]:
    pending = _safe_int(matrix.get("pendingReviewCount"), 0)
    invalid = _safe_int(matrix.get("invalidDecisionCount"), 0)
    if invalid > 0:
        return {
            "batchStatus": "manual_review_invalid",
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "nextCorrectiveFamily": "manual_review_denominator_repair",
            "weakEvidenceReasons": ["invalid_review_decisions_present"],
        }
    if pending > 0:
        return {
            "batchStatus": "manual_review_pending",
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "nextCorrectiveFamily": "manual_review_pending",
            "weakEvidenceReasons": ["pending_review_items_remaining"],
        }
    if total_positive_count >= min_total_positive_frames:
        return {
            "batchStatus": "review_resolved",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "nextCorrectiveFamily": "touchline_detector_candidate_v7_training_prep",
            "weakEvidenceReasons": [],
        }
    return {
        "batchStatus": "review_resolved_but_sparse",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "nextCorrectiveFamily": "manual_review_positive_expansion",
        "weakEvidenceReasons": ["total_reviewed_positive_count_below_minimum"],
    }


def run_promoted_v6_manual_review_denominator_resolution(
    *,
    expansion_root: Path = DEFAULT_EXPANSION_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    v7_refresh_root: Path = DEFAULT_V7_REFRESH_ROOT,
    min_total_positive_frames: int = DEFAULT_MIN_TOTAL_POSITIVE_FRAMES,
) -> dict[str, Any]:
    expansion_root = Path(expansion_root)
    output_root = Path(output_root)
    v7_refresh_root = Path(v7_refresh_root)
    overlay = _load_json_dict(expansion_root / "reviewed_label_overlay.json")
    v7_summary = _load_json_dict(v7_refresh_root / "touchline_detector_candidate_v7_training_data_refresh_summary.json")
    matrix = _build_review_decision_matrix(overlay)
    seed = _build_truth_seed(overlay, matrix)
    prior_positive_count = _safe_int(v7_summary.get("reviewedPositiveFrameCount"), 0)
    denominator_positive_count = _safe_int(matrix.get("denominatorReviewedPositiveCount"), 0)
    total_positive_count = prior_positive_count + denominator_positive_count
    decision = _decision_for(
        matrix,
        total_positive_count=total_positive_count,
        min_total_positive_frames=min_total_positive_frames,
    )
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "batchName": "manual_review_denominator_resolution",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "denominator_review_decision_validation",
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "priorReviewedPositiveFrameCount": prior_positive_count,
        "totalReviewedPositiveFrameCount": total_positive_count,
        **matrix,
        **decision,
        "nextRecommendedBatch": decision["nextCorrectiveFamily"],
    }
    decision_matrix = {
        **decision,
        "nextRecommendedBatch": decision["nextCorrectiveFamily"],
        "totalReviewedPositiveFrameCount": total_positive_count,
        "runtimeDefaultChanged": False,
    }
    batch_outcome = {
        **summary,
        "reviewDecisionMatrix": matrix,
        "reviewedDenominatorTruthSeed": seed,
        "decisionMatrix": decision_matrix,
    }
    _write_json(output_root / "manual_review_denominator_resolution_summary.json", summary)
    _write_json(output_root / "review_decision_matrix.json", matrix)
    _write_json(output_root / "reviewed_denominator_truth_seed.json", seed)
    if not bool(decision["goalAchieved"]):
        _write_json(output_root / "review_resolution_blocker_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "reviewDecisionMatrix": matrix,
        "reviewedDenominatorTruthSeed": seed,
        "decisionMatrix": decision_matrix,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate denominator manual review decisions.")
    parser.add_argument("--expansion-root", type=Path, default=DEFAULT_EXPANSION_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--v7-refresh-root", type=Path, default=DEFAULT_V7_REFRESH_ROOT)
    parser.add_argument("--min-total-positive-frames", type=int, default=DEFAULT_MIN_TOTAL_POSITIVE_FRAMES)
    args = parser.parse_args()
    payload = run_promoted_v6_manual_review_denominator_resolution(
        expansion_root=args.expansion_root,
        output_root=args.output_root,
        v7_refresh_root=args.v7_refresh_root,
        min_total_positive_frames=args.min_total_positive_frames,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
