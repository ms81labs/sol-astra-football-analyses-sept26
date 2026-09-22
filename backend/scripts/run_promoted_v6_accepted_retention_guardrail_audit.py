from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from math import ceil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "accepted_retention_guardrail_audit_v1"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_MICROFIX_ROOT = DEFAULT_SUITE_ROOT / "residual_segment_selection_microfix_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_RETENTION_GUARDRAIL = 0.60

BUCKET_GUARDRAIL_GAP = "accepted_controlled_retention_guardrail_gap"
BUCKET_ARM_RANKING_EDGE_PRIORITY = "arm_ranking_prefers_edge_share_over_retention"
BUCKET_PROMOTION_GATE_CLEARED = "promotion_gate_cleared"
BUCKET_ARTIFACT_GAP = "retention_guardrail_artifact_gap"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def _source_summary(arm: dict[str, Any], clip_id: str) -> dict[str, Any]:
    source_summaries = arm.get("sourceSummaries")
    if not isinstance(source_summaries, dict):
        return {}
    summary = source_summaries.get(clip_id)
    return dict(summary) if isinstance(summary, dict) else {}


def _clip_proof_run(arm: dict[str, Any], clip_id: str) -> dict[str, Any]:
    for proof_run in _list_dicts(arm.get("proofRuns")):
        if str(proof_run.get("sourceClipId") or "") == clip_id:
            return proof_run
    return {}


def _required_frames(denominator: int, guardrail: float) -> int | None:
    if denominator <= 0:
        return None
    return int(ceil(float(guardrail) * denominator))


def _arm_matrix_rows(
    *,
    arm_matrix: dict[str, Any],
    clip_id: str,
    guardrail: float,
) -> list[dict[str, Any]]:
    arms = _list_dicts(arm_matrix.get("arms"))
    baseline_arm = next((arm for arm in arms if str(arm.get("armName") or "") == "baseline_current"), {})
    baseline_proof = _clip_proof_run(baseline_arm, clip_id)
    baseline_accepted_frames = _safe_int(baseline_proof.get("acceptedBallFrames"), 0)
    baseline_controlled_frames = _safe_int(baseline_proof.get("controlledPossessionFrames"), 0)
    accepted_required = _required_frames(baseline_accepted_frames, guardrail)
    controlled_required = _required_frames(baseline_controlled_frames, guardrail)

    rows: list[dict[str, Any]] = []
    for arm in arms:
        arm_name = str(arm.get("armName") or "")
        source = _source_summary(arm, clip_id)
        proof = _clip_proof_run(arm, clip_id)
        outcome = dict(arm.get("outcome") or {})
        accepted_frames = _safe_int(proof.get("acceptedBallFrames"), 0)
        controlled_frames = _safe_int(proof.get("controlledPossessionFrames"), 0)
        accepted_ratio = _safe_float(source.get("medianAcceptedRetentionRatio"), 0.0)
        controlled_ratio = _safe_float(source.get("medianControlledRetentionRatio"), 0.0)
        rows.append(
            {
                "armName": arm_name,
                "acceptedBallFrames": accepted_frames,
                "controlledPossessionFrames": controlled_frames,
                "baselineAcceptedBallFrames": baseline_accepted_frames,
                "baselineControlledPossessionFrames": baseline_controlled_frames,
                "acceptedRetentionRatio": round(accepted_ratio, 3),
                "controlledRetentionRatio": round(controlled_ratio, 3),
                "acceptedRetentionGuardrail": guardrail,
                "controlledRetentionGuardrail": guardrail,
                "acceptedFramesRequiredForGuardrail": accepted_required,
                "controlledFramesRequiredForGuardrail": controlled_required,
                "acceptedFramesShortOfGuardrail": (
                    max(0, int(accepted_required) - accepted_frames) if accepted_required is not None else None
                ),
                "controlledFramesShortOfGuardrail": (
                    max(0, int(controlled_required) - controlled_frames) if controlled_required is not None else None
                ),
                "edgeShareImprovement": round(_safe_float(outcome.get("failingSourceEdgeShareImprovement"), 0.0), 3),
                "medianBallTrackEdgeFrameShare": _safe_float(source.get("medianBallTrackEdgeFrameShare"), 0.0),
                "sourceViable": bool(source.get("sourceViable")),
                "sourceFailureSignal": source.get("sourceFailureSignal"),
                "passedPromotionGate": bool(outcome.get("passedPromotionGate")),
                "promotionBlockers": list(outcome.get("promotionBlockers") or []),
                "configOutcome": outcome.get("configOutcome"),
            }
        )
    return rows


def _best_promoted_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    promoted = [row for row in rows if str(row.get("armName") or "").startswith("promoted_v6")]
    if not promoted:
        return {}
    return sorted(
        promoted,
        key=lambda row: (
            _safe_float(row.get("acceptedRetentionRatio"), 0.0),
            _safe_float(row.get("controlledRetentionRatio"), 0.0),
            _safe_float(row.get("edgeShareImprovement"), 0.0),
            str(row.get("armName") or ""),
        ),
        reverse=True,
    )[0]


def _ranking_finding(rows: list[dict[str, Any]], winning_arm_name: str) -> dict[str, Any]:
    winning = next((row for row in rows if row.get("armName") == winning_arm_name), {})
    best_retention = _best_promoted_row(rows)
    if not winning or not best_retention:
        return {"present": False}
    return {
        "present": winning.get("armName") != best_retention.get("armName"),
        "winningArmName": winning.get("armName"),
        "winningArmEdgeShareImprovement": winning.get("edgeShareImprovement"),
        "winningArmAcceptedRetentionRatio": winning.get("acceptedRetentionRatio"),
        "bestRetentionArmName": best_retention.get("armName"),
        "bestRetentionArmEdgeShareImprovement": best_retention.get("edgeShareImprovement"),
        "bestRetentionArmAcceptedRetentionRatio": best_retention.get("acceptedRetentionRatio"),
        "interpretation": (
            "Among failing promoted arms, validation ranking prefers edge-share improvement before retention."
            if winning.get("armName") != best_retention.get("armName")
            else "Winning arm is also the best promoted retention arm."
        ),
    }


def _dominant_blocker(
    *,
    rows: list[dict[str, Any]],
    validation_summary: dict[str, Any],
    ranking_finding: dict[str, Any],
    retention_guardrail: float,
) -> str:
    if not rows:
        return BUCKET_ARTIFACT_GAP
    if bool(validation_summary.get("winningPassedPromotionGate")) or any(
        bool(row.get("passedPromotionGate")) for row in rows if str(row.get("armName") or "").startswith("promoted_v6")
    ):
        return BUCKET_PROMOTION_GATE_CLEARED
    best_promoted = _best_promoted_row(rows)
    if not best_promoted:
        return BUCKET_ARTIFACT_GAP
    if (
        _safe_float(best_promoted.get("acceptedRetentionRatio"), 0.0) < retention_guardrail
        or _safe_float(best_promoted.get("controlledRetentionRatio"), 0.0) < retention_guardrail
    ):
        return BUCKET_GUARDRAIL_GAP
    if bool(ranking_finding.get("present")):
        return BUCKET_ARM_RANKING_EDGE_PRIORITY
    return BUCKET_ARTIFACT_GAP


def _next_family(dominant_blocker: str) -> str:
    if dominant_blocker == BUCKET_PROMOTION_GATE_CLEARED:
        return "validate_promoted_touchline_runtime_default"
    if dominant_blocker == BUCKET_GUARDRAIL_GAP:
        return "global_accepted_gap_audit"
    if dominant_blocker == BUCKET_ARM_RANKING_EDGE_PRIORITY:
        return "source_robustness_arm_ranking_audit"
    return "proof_runtime_frame_diagnostics"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Accepted Retention Guardrail Audit",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- winningArmName: {summary.get('winningArmName')}",
            f"- bestRetentionArmName: {summary.get('bestRetentionArmName')}",
            f"- bestAcceptedRetentionRatio: {summary.get('bestAcceptedRetentionRatio')}",
            f"- bestControlledRetentionRatio: {summary.get('bestControlledRetentionRatio')}",
            f"- acceptedRetentionGuardrail: {summary.get('acceptedRetentionGuardrail')}",
            f"- acceptedFramesShortOfGuardrail: {summary.get('acceptedFramesShortOfGuardrail')}",
            f"- controlledFramesShortOfGuardrail: {summary.get('controlledFramesShortOfGuardrail')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_accepted_retention_guardrail_audit(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    microfix_root: Path = DEFAULT_MICROFIX_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
    retention_guardrail: float = DEFAULT_RETENTION_GUARDRAIL,
) -> dict[str, Any]:
    output_root = Path(output_root)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)
    microfix_root = Path(microfix_root)

    validation_summary = _load_optional_json_dict(validation_root / "validation_summary.json")
    arm_matrix = _load_optional_json_dict(validation_root / "arm_matrix.json")
    retention_summary = _load_optional_json_dict(retention_delta_root / "retention_delta_summary.json")
    microfix_summary = _load_optional_json_dict(microfix_root / "residual_segment_selection_microfix_summary.json")

    rows = _arm_matrix_rows(
        arm_matrix=arm_matrix,
        clip_id=failing_source_clip_id,
        guardrail=retention_guardrail,
    )
    winning_arm_name = str(validation_summary.get("winningArmName") or "")
    best_promoted = _best_promoted_row(rows)
    ranking = _ranking_finding(rows, winning_arm_name)
    dominant = _dominant_blocker(
        rows=rows,
        validation_summary=validation_summary,
        ranking_finding=ranking,
        retention_guardrail=retention_guardrail,
    )
    next_family = _next_family(dominant)
    generated_at = _utc_now_iso()

    summary = {
        "generatedAt": generated_at,
        "batchName": "accepted_retention_guardrail_audit",
        "batchStatus": "succeeded" if rows else "needs_next_attempt",
        "goalAchieved": bool(rows),
        "roadmapAdvanceAllowed": bool(rows),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "failingSourceClipId": failing_source_clip_id,
        "dominantBlockerClass": dominant,
        "winningArmName": winning_arm_name or None,
        "winningPassedPromotionGate": bool(validation_summary.get("winningPassedPromotionGate")),
        "winningPromotionBlockers": list(validation_summary.get("winningPromotionBlockers") or []),
        "bestRetentionArmName": best_promoted.get("armName"),
        "bestAcceptedRetentionRatio": best_promoted.get("acceptedRetentionRatio"),
        "bestControlledRetentionRatio": best_promoted.get("controlledRetentionRatio"),
        "acceptedRetentionGuardrail": retention_guardrail,
        "controlledRetentionGuardrail": retention_guardrail,
        "acceptedFramesRequiredForGuardrail": best_promoted.get("acceptedFramesRequiredForGuardrail"),
        "controlledFramesRequiredForGuardrail": best_promoted.get("controlledFramesRequiredForGuardrail"),
        "acceptedFramesShortOfGuardrail": best_promoted.get("acceptedFramesShortOfGuardrail"),
        "controlledFramesShortOfGuardrail": best_promoted.get("controlledFramesShortOfGuardrail"),
        "residualMicrofixTruth": {
            "residualSelectedFrameCount": microfix_summary.get("residualSelectedFrameCount"),
            "residualAcceptedFrameCount": microfix_summary.get("residualAcceptedFrameCount"),
            "nextCorrectiveFamily": microfix_summary.get("nextCorrectiveFamily"),
        },
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "roadmapAdvanceAllowed": retention_summary.get("roadmapAdvanceAllowed"),
        },
        "rankingFinding": ranking,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "recommendedApproachQueue": [
            {
                "attempt": 1,
                "family": "accepted_gap_manifest_refresh",
                "purpose": "Enumerate all baseline-accepted frames still missing from the best promoted proof.",
            },
            {
                "attempt": 2,
                "family": "reachable_global_acceptance_probe",
                "purpose": "Prioritize frames with raw/collapsed evidence outside the reviewed-positive branch.",
            },
            {
                "attempt": 3,
                "family": "v7_training_data_lane",
                "purpose": "If the residual gap is mostly no-detect, convert reviewed positives/refutations into training data.",
            },
        ],
    }
    arm_artifact = {
        "generatedAt": generated_at,
        "failingSourceClipId": failing_source_clip_id,
        "retentionGuardrail": retention_guardrail,
        "arms": rows,
        "rankingFinding": ranking,
    }
    residual_closeout = {
        "generatedAt": generated_at,
        "microfixSummary": microfix_summary,
        "interpretation": (
            "Residual selected-segment microprofile produced accepted reviewed-positive frames, "
            "but generated promotion truth remains below the accepted/controlled retention guardrails."
        ),
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "rationale": (
            "The best promoted arm remains far below the 0.60 accepted/controlled retention guardrails."
            if dominant == BUCKET_GUARDRAIL_GAP
            else "Promotion gate state is not blocked by the accepted/controlled retention guardrails."
        ),
    }
    batch_outcome = {
        **summary,
        "armRetentionGuardrailMatrix": arm_artifact,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "accepted_retention_guardrail_summary.json", summary)
    _write_json(output_root / "arm_retention_guardrail_matrix.json", arm_artifact)
    _write_json(output_root / "residual_lift_closeout.json", residual_closeout)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "armRetentionGuardrailMatrix": arm_artifact,
        "residualLiftCloseout": residual_closeout,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--microfix-root", type=Path, default=DEFAULT_MICROFIX_ROOT)
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    parser.add_argument("--retention-guardrail", type=float, default=DEFAULT_RETENTION_GUARDRAIL)
    args = parser.parse_args()
    payload = run_promoted_v6_accepted_retention_guardrail_audit(
        output_root=args.output_root,
        validation_root=args.validation_root,
        retention_delta_root=args.retention_delta_root,
        microfix_root=args.microfix_root,
        failing_source_clip_id=args.failing_source_clip_id,
        retention_guardrail=args.retention_guardrail,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
