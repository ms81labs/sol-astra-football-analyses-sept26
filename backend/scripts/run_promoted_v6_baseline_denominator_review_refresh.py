from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "baseline_denominator_review_refresh_v1"
DEFAULT_GLOBAL_GAP_ROOT = DEFAULT_SUITE_ROOT / "global_accepted_gap_audit_v1"
DEFAULT_REACHABLE_ROOT = DEFAULT_SUITE_ROOT / "global_reachable_acceptance_probe_v1"
DEFAULT_REFUTED_SEED_PATH = (
    DEFAULT_SUITE_ROOT / "gold_truth_seed_refuted_refresh_v1" / "rejected_seed_refutation_manifest.json"
)
DEFAULT_REVIEWED_TRUTH_PATH = (
    DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1" / "expanded_reviewed_truth_seed.json"
)
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_GUARDRAIL_ROOT = DEFAULT_SUITE_ROOT / "accepted_retention_guardrail_audit_v1"

CLASS_REVIEWED_POSITIVE = "reviewed_positive_supported_denominator_frame"
CLASS_REFUTED = "refuted_bootstrap_seed_denominator_contaminant"
CLASS_UNREVIEWED = "unreviewed_denominator_frame"
CLASS_PROMOTED_OVERLAP = "promoted_accepted_overlap"
CLASS_ARTIFACT_GAP = "artifact_gap"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
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


def _frame_set(rows: list[dict[str, Any]], key: str = "frameIndex") -> set[int]:
    return {
        _safe_int(row.get(key), -1)
        for row in rows
        if _safe_int(row.get(key), -1) >= 0
    }


def _classification_for_frame(
    row: dict[str, Any],
    *,
    refuted_frames: set[int],
    reviewed_positive_frames: set[int],
) -> str:
    frame_id = _safe_int(row.get("frameIndex"), -1)
    if frame_id < 0:
        return CLASS_ARTIFACT_GAP
    if bool(row.get("promotedAccepted")) or row.get("gapClass") == "baseline_accepted_already_accepted_in_promoted":
        return CLASS_PROMOTED_OVERLAP
    if frame_id in refuted_frames or row.get("reviewTruthClass") == "refuted_bootstrap_seed":
        return CLASS_REFUTED
    if frame_id in reviewed_positive_frames or str(row.get("reviewTruthClass") or "").startswith("reviewed_positive"):
        return CLASS_REVIEWED_POSITIVE
    if row.get("reviewTruthClass") == "unreviewed":
        return CLASS_UNREVIEWED
    return CLASS_ARTIFACT_GAP


def _select_next_family(
    *,
    refuted_count: int,
    denominator_count: int,
    effective_ratio: float,
    guardrail: float,
    artifact_gap_count: int,
) -> str:
    if artifact_gap_count > 0:
        return "manual_review_denominator_expansion"
    if effective_ratio >= guardrail:
        return "reviewed_denominator_validation_batch"
    if refuted_count >= max(1, denominator_count // 2):
        return "refuted_denominator_filter_plan"
    return "v7_training_data_lane"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline Denominator Review Refresh",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- baselineDenominatorFrameCount: {summary.get('baselineDenominatorFrameCount')}",
            f"- promotedAcceptedOverlapCount: {summary.get('promotedAcceptedOverlapCount')}",
            f"- refutedDenominatorFrameCount: {summary.get('refutedDenominatorFrameCount')}",
            f"- reviewedPositiveSupportedFrameCount: {summary.get('reviewedPositiveSupportedFrameCount')}",
            f"- unreviewedDenominatorFrameCount: {summary.get('unreviewedDenominatorFrameCount')}",
            f"- effectiveAcceptedRetentionRatioAfterRefutedFilter: {summary.get('effectiveAcceptedRetentionRatioAfterRefutedFilter')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_baseline_denominator_review_refresh(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    global_gap_root: Path = DEFAULT_GLOBAL_GAP_ROOT,
    reachable_root: Path = DEFAULT_REACHABLE_ROOT,
    refuted_seed_path: Path = DEFAULT_REFUTED_SEED_PATH,
    reviewed_truth_path: Path = DEFAULT_REVIEWED_TRUTH_PATH,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    guardrail_root: Path = DEFAULT_GUARDRAIL_ROOT,
) -> dict[str, Any]:
    output_root = Path(output_root)
    global_gap_root = Path(global_gap_root)
    reachable_root = Path(reachable_root)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)
    guardrail_root = Path(guardrail_root)

    accepted_gap_manifest = _load_json_dict(global_gap_root / "accepted_gap_frame_manifest.json")
    accepted_gap_taxonomy = _load_optional_json_dict(global_gap_root / "accepted_gap_class_taxonomy.json")
    reachable_summary = _load_optional_json_dict(reachable_root / "global_reachable_acceptance_summary.json")
    refuted_manifest = _load_optional_json_dict(Path(refuted_seed_path))
    reviewed_truth = _load_optional_json_dict(Path(reviewed_truth_path))
    validation_arm_matrix = _load_optional_json_dict(validation_root / "arm_matrix.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    guardrail_summary = _load_optional_json_dict(guardrail_root / "accepted_retention_guardrail_summary.json")

    denominator_rows = _list_dicts(accepted_gap_manifest.get("frames"))
    refuted_frames = _frame_set(_list_dicts(refuted_manifest.get("rejectedSeeds")))
    reviewed_positive_frames = _frame_set(_list_dicts(reviewed_truth.get("reviewedPositiveSeedRows")))

    matrix_rows: list[dict[str, Any]] = []
    for row in sorted(denominator_rows, key=lambda item: _safe_int(item.get("frameIndex"), -1)):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        classification = _classification_for_frame(
            row,
            refuted_frames=refuted_frames,
            reviewed_positive_frames=reviewed_positive_frames,
        )
        matrix_rows.append(
            {
                "frameIndex": frame_id,
                "classification": classification,
                "gapClass": row.get("gapClass"),
                "reviewTruthClass": row.get("reviewTruthClass"),
                "baselineAccepted": bool(row.get("baselineAccepted")),
                "promotedAccepted": bool(row.get("promotedAccepted")),
                "isRefutedSeed": frame_id in refuted_frames,
                "isReviewedPositive": frame_id in reviewed_positive_frames,
                "refutationUse": "negative_only_do_not_use_as_positive" if frame_id in refuted_frames else None,
            }
        )

    counts = Counter(row["classification"] for row in matrix_rows)
    denominator_count = len(matrix_rows)
    promoted_overlap_count = counts.get(CLASS_PROMOTED_OVERLAP, 0)
    refuted_count = counts.get(CLASS_REFUTED, 0)
    artifact_gap_count = counts.get(CLASS_ARTIFACT_GAP, 0)
    effective_denominator = denominator_count - refuted_count
    effective_ratio = round(
        promoted_overlap_count / effective_denominator,
        3,
    ) if effective_denominator > 0 else 0.0
    guardrail = _safe_float(
        guardrail_summary.get("acceptedRetentionGuardrail"),
        _safe_float(guardrail_summary.get("controlledRetentionGuardrail"), 0.6),
    )
    next_family = _select_next_family(
        refuted_count=refuted_count,
        denominator_count=denominator_count,
        effective_ratio=effective_ratio,
        guardrail=guardrail,
        artifact_gap_count=artifact_gap_count,
    )
    generated_at = _utc_now_iso()
    refuted_reused_as_positive = any(
        row["classification"] == CLASS_REVIEWED_POSITIVE and bool(row.get("isRefutedSeed"))
        for row in matrix_rows
    )

    effective_delta = {
        "generatedAt": generated_at,
        "analysisOnly": True,
        "baselineDenominatorFrameCount": denominator_count,
        "proposedExcludedRefutedFrameCount": refuted_count,
        "effectiveDenominatorAfterRefutedFilter": effective_denominator,
        "promotedAcceptedOverlapCount": promoted_overlap_count,
        "effectiveAcceptedRetentionRatioAfterRefutedFilter": effective_ratio,
        "acceptedRetentionGuardrail": guardrail,
        "wouldClearAcceptedRetentionGuardrail": effective_ratio >= guardrail,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": "baseline_denominator_review_refresh",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "baseline_denominator_truth_audit",
        "batchStatus": "succeeded" if denominator_count else "needs_next_attempt",
        "goalAchieved": bool(denominator_count),
        "roadmapAdvanceAllowed": bool(denominator_count),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "baselineDenominatorFrameCount": denominator_count,
        "promotedAcceptedOverlapCount": promoted_overlap_count,
        "refutedDenominatorFrameCount": refuted_count,
        "reviewedPositiveSupportedFrameCount": counts.get(CLASS_REVIEWED_POSITIVE, 0) + promoted_overlap_count,
        "unreviewedDenominatorFrameCount": counts.get(CLASS_UNREVIEWED, 0),
        "artifactGapFrameCount": artifact_gap_count,
        "classificationCounts": dict(sorted(counts.items())),
        "refutedSeedsReusedAsPositiveEvidence": refuted_reused_as_positive,
        "effectiveDenominatorAfterRefutedFilter": effective_denominator,
        "effectiveAcceptedRetentionRatioAfterRefutedFilter": effective_ratio,
        "acceptedRetentionGuardrail": guardrail,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "globalGapTruth": {
            "gapClassCounts": accepted_gap_taxonomy.get("gapClassCounts"),
            "reviewTruthClassCounts": accepted_gap_taxonomy.get("reviewTruthClassCounts"),
            "dominantGapClass": accepted_gap_taxonomy.get("dominantGapClass"),
        },
        "reachableTruth": {
            "acceptedFrameCount": reachable_summary.get("acceptedFrameCount"),
            "selectedFrameCount": reachable_summary.get("selectedFrameCount"),
            "reachableFrameIds": reachable_summary.get("reachableFrameIds"),
        },
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "validationTruth": {
            "evaluatedArmCount": len(_list_dicts(validation_arm_matrix.get("arms"))),
        },
    }
    taxonomy = {
        "generatedAt": generated_at,
        "classificationCounts": summary["classificationCounts"],
        "refutedDenominatorFrameCount": refuted_count,
        "refutedFrames": [
            row for row in matrix_rows if row["classification"] == CLASS_REFUTED
        ],
        "truthPolicy": "refuted_seed_refutation_only",
        "refutedSeedsReusedAsPositiveEvidence": refuted_reused_as_positive,
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "rationale": (
            "Refuted bootstrap seed frames dominate the denominator, so write a proposed refuted-denominator "
            "filter plan before adding detector-side work."
            if next_family == "refuted_denominator_filter_plan"
            else "Filtering refuted frames does not produce enough effective retention; route the evidence to v7/training data."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
        "effectiveRetentionDenominatorDelta": effective_delta,
    }

    _write_json(output_root / "baseline_denominator_review_summary.json", summary)
    _write_json(
        output_root / "denominator_frame_review_matrix.json",
        {"generatedAt": generated_at, "frames": matrix_rows},
    )
    _write_json(output_root / "refuted_denominator_overlap_taxonomy.json", taxonomy)
    _write_json(output_root / "effective_retention_denominator_delta.json", effective_delta)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "denominatorFrameReviewMatrix": {"frames": matrix_rows},
        "refutedDenominatorOverlapTaxonomy": taxonomy,
        "effectiveRetentionDenominatorDelta": effective_delta,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--global-gap-root", type=Path, default=DEFAULT_GLOBAL_GAP_ROOT)
    parser.add_argument("--reachable-root", type=Path, default=DEFAULT_REACHABLE_ROOT)
    parser.add_argument("--refuted-seed-path", type=Path, default=DEFAULT_REFUTED_SEED_PATH)
    parser.add_argument("--reviewed-truth-path", type=Path, default=DEFAULT_REVIEWED_TRUTH_PATH)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--guardrail-root", type=Path, default=DEFAULT_GUARDRAIL_ROOT)
    args = parser.parse_args()
    payload = run_promoted_v6_baseline_denominator_review_refresh(
        output_root=args.output_root,
        global_gap_root=args.global_gap_root,
        reachable_root=args.reachable_root,
        refuted_seed_path=args.refuted_seed_path,
        reviewed_truth_path=args.reviewed_truth_path,
        validation_root=args.validation_root,
        retention_delta_root=args.retention_delta_root,
        guardrail_root=args.guardrail_root,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
