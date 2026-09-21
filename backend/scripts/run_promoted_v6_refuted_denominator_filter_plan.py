from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_INPUT_ROOT = DEFAULT_SUITE_ROOT / "baseline_denominator_review_refresh_v1"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "refuted_denominator_filter_plan_v1"


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


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Refuted Denominator Filter Plan",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- proposedExcludedFrameCount: {summary.get('proposedExcludedFrameCount')}",
            f"- effectiveDenominatorAfterFilter: {summary.get('effectiveDenominatorAfterFilter')}",
            f"- effectiveAcceptedRetentionRatio: {summary.get('effectiveAcceptedRetentionRatio')}",
            f"- acceptedRetentionGuardrail: {summary.get('acceptedRetentionGuardrail')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_refuted_denominator_filter_plan(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    input_root = Path(input_root)
    output_root = Path(output_root)
    summary_in = _load_json_dict(input_root / "baseline_denominator_review_summary.json")
    matrix = _load_json_dict(input_root / "denominator_frame_review_matrix.json")
    effective_delta = _load_json_dict(input_root / "effective_retention_denominator_delta.json")

    rows = _list_dicts(matrix.get("frames"))
    excluded_rows = [
        row
        for row in rows
        if row.get("classification") == "refuted_bootstrap_seed_denominator_contaminant"
    ]
    retained_rows = [
        row
        for row in rows
        if row.get("classification") != "refuted_bootstrap_seed_denominator_contaminant"
    ]
    ratio = float(effective_delta.get("effectiveAcceptedRetentionRatioAfterRefutedFilter") or 0.0)
    guardrail = float(effective_delta.get("acceptedRetentionGuardrail") or summary_in.get("acceptedRetentionGuardrail") or 0.6)
    next_family = "reviewed_denominator_validation_batch" if ratio >= guardrail else "v7_training_data_lane"
    generated_at = _utc_now_iso()

    proposed_delta = {
        "generatedAt": generated_at,
        "analysisOnly": True,
        "mutationPolicy": "proposed_delta_only_do_not_mutate_frozen_manifest",
        "excludedFrameCount": len(excluded_rows),
        "excludedFrameIds": [int(row["frameIndex"]) for row in excluded_rows],
        "excludedReason": "explicit_refuted_bootstrap_seed_evidence",
        "retainedFrameCount": len(retained_rows),
        "retainedFrameIds": [int(row["frameIndex"]) for row in retained_rows],
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
    }
    filtered_metric = {
        "generatedAt": generated_at,
        "analysisOnly": True,
        "baselineDenominatorFrameCount": summary_in.get("baselineDenominatorFrameCount"),
        "effectiveDenominatorAfterFilter": effective_delta.get("effectiveDenominatorAfterRefutedFilter"),
        "promotedAcceptedOverlapCount": summary_in.get("promotedAcceptedOverlapCount"),
        "effectiveAcceptedRetentionRatio": ratio,
        "acceptedRetentionGuardrail": guardrail,
        "wouldClearAcceptedRetentionGuardrail": ratio >= guardrail,
        "nextCorrectiveFamily": next_family,
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": "refuted_denominator_filter_plan",
        "attemptNumber": 2,
        "attemptBudget": 3,
        "attemptApproachFamily": "refuted_denominator_filter_plan",
        "batchStatus": "succeeded",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "proposedExcludedFrameCount": len(excluded_rows),
        "effectiveDenominatorAfterFilter": effective_delta.get("effectiveDenominatorAfterRefutedFilter"),
        "effectiveAcceptedRetentionRatio": ratio,
        "acceptedRetentionGuardrail": guardrail,
        "wouldClearAcceptedRetentionGuardrail": ratio >= guardrail,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
    }
    decision = {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "rationale": (
            "Filtering explicitly refuted denominator frames is not enough to clear the retention guardrail."
            if next_family == "v7_training_data_lane"
            else "Filtered denominator metric clears the accepted-retention guardrail as analysis-only truth."
        ),
    }
    batch_outcome = {
        **summary,
        "proposedDenominatorDelta": proposed_delta,
        "filteredRetentionMetric": filtered_metric,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "refuted_denominator_filter_plan_summary.json", summary)
    _write_json(output_root / "proposed_denominator_delta.json", proposed_delta)
    _write_json(output_root / "filtered_retention_metric.json", filtered_metric)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "proposedDenominatorDelta": proposed_delta,
        "filteredRetentionMetric": filtered_metric,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = run_promoted_v6_refuted_denominator_filter_plan(
        input_root=args.input_root,
        output_root=args.output_root,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
