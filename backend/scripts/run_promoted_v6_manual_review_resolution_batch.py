from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_resolution_v1"
DEFAULT_MANUAL_REVIEW_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_manual_review_followthrough_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "promoted_v6_manual_review_resolution_v1"
ALLOWED_DECISIONS = {
    "pending_review",
    "accept_seed",
    "adjust_bbox",
    "reject_seed",
    "confirm_hard_negative",
}
POSITIVE_DECISIONS = {"accept_seed", "adjust_bbox"}
NEGATIVE_DECISIONS = {"reject_seed", "confirm_hard_negative"}


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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


def _lineage_complete(item: dict[str, Any]) -> bool:
    if item.get("lineageComplete") is True:
        return True
    lineage = item.get("lineage")
    if not isinstance(lineage, dict):
        return False
    required = {
        "baselineBallTruthLayersPath",
        "baselineSelectedClusterDeltaPath",
        "promotedBallTruthLayersPath",
        "promotedSelectedClusterDeltaPath",
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
        reasons.append("unknown_review_decision")
        return reasons
    if decision == "accept_seed" and not _valid_bbox_payload(item.get("seedBBox")):
        reasons.append("accept_seed_requires_valid_seed_bbox")
    if decision == "adjust_bbox" and not _valid_bbox_payload(item.get("reviewedBBox")):
        reasons.append("adjust_bbox_requires_reviewed_bbox")
    if decision in POSITIVE_DECISIONS and not _lineage_complete(item):
        reasons.append("positive_decision_requires_complete_lineage")
    return reasons


def build_review_decision_matrix(overlay: dict[str, Any]) -> dict[str, Any]:
    rows = []
    counts = {
        "reviewItemCount": 0,
        "pendingReviewCount": 0,
        "acceptedSeedCount": 0,
        "adjustedBBoxCount": 0,
        "rejectedSeedCount": 0,
        "confirmedHardNegativeCount": 0,
        "reviewedPositiveCount": 0,
        "reviewedNegativeCount": 0,
        "invalidDecisionCount": 0,
        "lineageCompleteCount": 0,
    }
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
            counts["reviewedPositiveCount"] += 1
        if decision in NEGATIVE_DECISIONS:
            counts["reviewedNegativeCount"] += 1
        if _lineage_complete(item):
            counts["lineageCompleteCount"] += 1
        if reasons:
            counts["invalidDecisionCount"] += 1
            repair_guidance[review_item_id] = [
                "add_valid_reviewed_bbox_for_adjust_bbox"
                if reason == "adjust_bbox_requires_reviewed_bbox"
                else reason
                for reason in reasons
            ]
        rows.append(
            {
                "reviewItemId": review_item_id,
                "candidateFrameId": item.get("candidateFrameId"),
                "frameIndex": item.get("frameIndex"),
                "windowId": item.get("windowId") or item.get("curationUnitId"),
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


def build_reviewed_followthrough_truth_seed(
    *,
    overlay: dict[str, Any],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    if _safe_int(matrix.get("pendingReviewCount"), 0) > 0 or _safe_int(matrix.get("invalidDecisionCount"), 0) > 0:
        return {
            "generatedAt": _utc_now_iso(),
            "reviewedPositiveSeedCount": 0,
            "reviewedPositiveSeedRows": [],
            "truthStatus": "not_ready_pending_or_invalid_review",
        }
    positive_rows = []
    negative_rows = []
    for item in _review_items(overlay):
        decision = str(item.get("decision") or "")
        if decision in POSITIVE_DECISIONS:
            bbox = item.get("reviewedBBox") if decision == "adjust_bbox" else item.get("seedBBox")
            positive_rows.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "candidateFrameId": item.get("candidateFrameId"),
                    "windowId": item.get("windowId") or item.get("curationUnitId"),
                    "frameIndex": item.get("frameIndex"),
                    "timestampSeconds": item.get("timestampSeconds"),
                    "sourceClipId": item.get("sourceClipId"),
                    "reviewDecision": decision,
                    "seedBBox": item.get("seedBBox"),
                    "reviewedBBox": bbox,
                    "lineage": item.get("lineage") if isinstance(item.get("lineage"), dict) else {},
                }
            )
        elif decision in NEGATIVE_DECISIONS:
            negative_rows.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "candidateFrameId": item.get("candidateFrameId"),
                    "frameIndex": item.get("frameIndex"),
                    "reviewDecision": decision,
                }
            )
    return {
        "generatedAt": _utc_now_iso(),
        "reviewedPositiveSeedCount": len(positive_rows),
        "reviewedNegativeSeedCount": len(negative_rows),
        "reviewedPositiveSeedRows": positive_rows,
        "reviewedNegativeSeedRows": negative_rows,
        "truthStatus": "review_resolved",
    }


def build_decision_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    pending = _safe_int(matrix.get("pendingReviewCount"), 0)
    invalid = _safe_int(matrix.get("invalidDecisionCount"), 0)
    positives = _safe_int(matrix.get("reviewedPositiveCount"), 0)
    negatives = _safe_int(matrix.get("reviewedNegativeCount"), 0)
    if invalid > 0:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "batchStatus": "manual_review_invalid",
            "nextCorrectiveFamily": "manual_review_required",
            "successfulApproach": "B_review_overlay_repair_guidance",
            "weakEvidenceReasons": ["invalid_review_decisions_present"],
            "rationale": "Manual review decisions contain invalid values or missing required boxes.",
        }
    if pending > 0:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "batchStatus": "manual_review_pending",
            "nextCorrectiveFamily": "manual_review_pending",
            "successfulApproach": "A_review_decision_validation",
            "weakEvidenceReasons": ["pending_review_items_remaining"],
            "rationale": "Manual review decisions are still pending; do not advance to detector-side work.",
        }
    if positives > 0:
        return {
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "batchStatus": "review_resolved",
            "nextCorrectiveFamily": "reviewed_followthrough_selection_fix",
            "successfulApproach": "C_reviewed_truth_seed_generation",
            "weakEvidenceReasons": [],
            "rationale": "Manual review resolved positive follow-through seeds for the next detector-side batch.",
        }
    if negatives > 0:
        return {
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "batchStatus": "review_resolved",
            "nextCorrectiveFamily": "gold_truth_seed_refuted_refresh",
            "successfulApproach": "C_reviewed_truth_seed_generation",
            "weakEvidenceReasons": [],
            "rationale": "Manual review rejected all follow-through seeds; refresh the gold truth premise.",
        }
    return {
        "goalAchieved": False,
        "roadmapAdvanceAllowed": False,
        "batchStatus": "manual_review_invalid",
        "nextCorrectiveFamily": "manual_review_required",
        "successfulApproach": "B_review_overlay_repair_guidance",
        "weakEvidenceReasons": ["no_review_decisions_available"],
        "rationale": "Manual review has no actionable decisions.",
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Promoted V6 Manual Review Resolution",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- reviewItemCount: {summary.get('reviewItemCount')}",
            f"- pendingReviewCount: {summary.get('pendingReviewCount')}",
            f"- invalidDecisionCount: {summary.get('invalidDecisionCount')}",
            f"- reviewedPositiveCount: {summary.get('reviewedPositiveCount')}",
            f"- reviewedNegativeCount: {summary.get('reviewedNegativeCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_manual_review_resolution_batch(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    manual_review_root: Path = DEFAULT_MANUAL_REVIEW_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    manual_review_root = Path(manual_review_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)
    overlay = _load_json_dict(manual_review_root / "reviewed_label_overlay.json")
    frame_manifest = _load_optional_json_dict(manual_review_root / "review_frame_manifest.json")
    bundle_manifest = _load_optional_json_dict(manual_review_root / "review_bundle_manifest.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(suite_root / "suite_summary.json")

    matrix = build_review_decision_matrix(overlay)
    truth_seed = build_reviewed_followthrough_truth_seed(overlay=overlay, matrix=matrix)
    decision = build_decision_matrix(matrix)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "activeQueueItem": "manual_review_pending",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "review_decision_validation",
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
        "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        "reviewFrameCount": frame_manifest.get("reviewFrameCount"),
        "reviewBundleManifestPath": bundle_manifest.get("reviewedLabelOverlayPath"),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        **{key: value for key, value in matrix.items() if key not in {"generatedAt", "reviewDecisions", "repairGuidanceByReviewItemId"}},
        **decision,
    }
    batch_outcome = {
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "approachFamily": "review_decision_validation",
        "batchStatus": summary["batchStatus"],
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "artifacts": {
            "manualReviewResolutionSummaryPath": str(output_root / "manual_review_resolution_summary.json"),
            "reviewDecisionMatrixPath": str(output_root / "review_decision_matrix.json"),
            "reviewedFollowthroughTruthSeedPath": str(output_root / "reviewed_followthrough_truth_seed.json"),
        },
    }

    _write_json(output_root / "manual_review_resolution_summary.json", summary)
    _write_json(output_root / "review_decision_matrix.json", matrix)
    _write_json(output_root / "reviewed_followthrough_truth_seed.json", truth_seed)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    if not decision["goalAchieved"]:
        _write_json(
            output_root / "review_resolution_blocker_summary.json",
            {
                **summary,
                "blockerSummaryType": "manual_review_resolution_blocker",
                "repairGuidanceByReviewItemId": matrix.get("repairGuidanceByReviewItemId", {}),
            },
        )
    _ = runtime_default_path, source_manifest_path
    return {
        "summary": summary,
        "reviewDecisionMatrix": matrix,
        "reviewedFollowthroughTruthSeed": truth_seed,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manual-review-root", type=Path, default=DEFAULT_MANUAL_REVIEW_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_manual_review_resolution_batch(
        output_root=args.output_root,
        manual_review_root=args.manual_review_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
