from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
DEFAULT_EVALUATION_ROOT = (
    DEFAULT_STORAGE_ROOT / "trained_detector_candidates" / "touchline_detector_candidate_v6" / "evaluation_v1"
)
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_ANALYSIS_BATCH_NAME = "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
RETENTION_GUARDRAIL = 0.60

ARM_NAME_BASELINE_CURRENT = "baseline_current"
ARM_NAME_PROMOTED_V6_BASELINE = "promoted_v6_baseline"
ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN = "promoted_v6_plus_best_thin"

PRIMARY_BLOCKER_ACCEPTED_SIGNAL = "accepted_signal_retention_collapse"
PRIMARY_BLOCKER_SELECTED_CLUSTER = "selected_cluster_follow_through_collapse"
PRIMARY_BLOCKER_CONTROLLED_POSSESSION = "controlled_possession_follow_through_collapse"
PRIMARY_BLOCKER_UNRESOLVED = "retention_collapse_unresolved"

NEXT_BATCH_FOR_BLOCKER = {
    PRIMARY_BLOCKER_ACCEPTED_SIGNAL: "touchline_detector_candidate_v6_accepted_signal_retention_fix_v1",
    PRIMARY_BLOCKER_SELECTED_CLUSTER: "touchline_detector_candidate_v6_selected_cluster_follow_through_fix_v1",
    PRIMARY_BLOCKER_CONTROLLED_POSSESSION: "touchline_detector_candidate_v6_controlled_possession_follow_through_fix_v1",
}


def _load_json_dict(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _summary_stage_metrics(payload: dict[str, object] | None) -> dict[str, object]:
    payload = dict(payload or {})
    return {
        "acceptedBallFrames": _safe_int(payload.get("acceptedBallFrames"), 0),
        "controlledPossessionFrames": _safe_int(payload.get("controlledPossessionFrames"), 0),
        "supportedAcceptedBallRatio": round(_safe_float(payload.get("supportedAcceptedBallRatio"), 0.0), 3),
        "unsupportedAcceptedEdgeFrames": _safe_int(payload.get("unsupportedAcceptedEdgeFrames"), 0),
        "ballTrackEdgeFrameShare": round(_safe_float(payload.get("ballTrackEdgeFrameShare"), 0.0), 3),
        "ballTrackViable": bool(payload.get("ballTrackViable")),
        "eventFamilyCount": _safe_int(payload.get("eventFamilyCount"), 0),
        "truthGateReasons": list(payload.get("truthGateReasons") or []),
    }


def _source_summary_stage_metrics(payload: dict[str, object] | None) -> dict[str, object]:
    payload = dict(payload or {})
    return {
        "acceptedRetentionRatio": round(_safe_float(payload.get("medianAcceptedRetentionRatio"), 0.0), 3),
        "controlledRetentionRatio": round(_safe_float(payload.get("medianControlledRetentionRatio"), 0.0), 3),
        "supportedAcceptedBallRatio": round(_safe_float(payload.get("medianSupportedAcceptedBallRatio"), 0.0), 3),
        "unsupportedAcceptedEdgeFrames": round(
            _safe_float(payload.get("medianUnsupportedAcceptedEdgeFrames"), 0.0),
            3,
        ),
        "ballTrackEdgeFrameShare": round(_safe_float(payload.get("medianBallTrackEdgeFrameShare"), 0.0), 3),
        "sourceViable": bool(payload.get("sourceViable")),
        "sourceFailureSignal": payload.get("sourceFailureSignal"),
        "truthReadyEntryCount": _safe_int(payload.get("truthReadyEntryCount"), 0),
    }


def _find_arm_payload(arm_matrix: dict[str, object], arm_name: str) -> dict[str, object]:
    for arm_payload in arm_matrix.get("arms", []):
        if isinstance(arm_payload, dict) and str(arm_payload.get("armName") or "") == arm_name:
            return arm_payload
    raise KeyError(f"Could not find arm payload for {arm_name}")


def _find_failing_source_proof_run(arm_payload: dict[str, object], failing_source_clip_id: str) -> dict[str, object]:
    proof_runs = [dict(proof_run) for proof_run in arm_payload.get("proofRuns", []) if isinstance(proof_run, dict)]
    for proof_run in proof_runs:
        if str(proof_run.get("sourceClipId") or "") == failing_source_clip_id:
            return proof_run
    if len(proof_runs) == 1:
        return proof_runs[0]
    raise KeyError(
        f"Could not resolve failing-source proof run for {arm_payload.get('armName')} and {failing_source_clip_id}"
    )


def _load_selected_cluster_delta(proof_run: dict[str, object]) -> tuple[dict[str, object], Path]:
    reused_evidence = dict(proof_run.get("reusedEvidence") or {})
    selected_cluster_delta_path = Path(str(reused_evidence.get("selectedClusterDeltaPath") or "")).expanduser()
    if not selected_cluster_delta_path.exists():
        raise FileNotFoundError(
            f"Missing selected-cluster delta for proof run {proof_run.get('sourceClipId')}: {selected_cluster_delta_path}"
        )
    return _load_json_dict(selected_cluster_delta_path), selected_cluster_delta_path


def _load_proof_summary(proof_run: dict[str, object], selected_cluster_delta_path: Path) -> tuple[dict[str, object], Path]:
    proof_summary_path = selected_cluster_delta_path.parent / "proof_summary.json"
    if not proof_summary_path.exists():
        raise FileNotFoundError(
            f"Missing proof summary sibling for selected-cluster delta {selected_cluster_delta_path}"
        )
    return _load_json_dict(proof_summary_path), proof_summary_path


def _stage_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    return {
        "acceptedBallFramesDelta": _safe_int(after.get("acceptedBallFrames"), 0)
        - _safe_int(before.get("acceptedBallFrames"), 0),
        "controlledPossessionFramesDelta": _safe_int(after.get("controlledPossessionFrames"), 0)
        - _safe_int(before.get("controlledPossessionFrames"), 0),
        "eventFamilyCountDelta": _safe_int(after.get("eventFamilyCount"), 0)
        - _safe_int(before.get("eventFamilyCount"), 0),
    }


def _retention_ratio(numerator: object, denominator: object) -> float:
    denominator_value = _safe_int(denominator, 0)
    if denominator_value <= 0:
        return 0.0
    return round(_safe_int(numerator, 0) / denominator_value, 3)


def _build_arm_stage_payload(
    *,
    arm_payload: dict[str, object],
    failing_source_clip_id: str,
    baseline_selected_cluster_after: dict[str, object] | None,
) -> dict[str, object]:
    proof_run = _find_failing_source_proof_run(arm_payload, failing_source_clip_id)
    selected_cluster_delta, selected_cluster_delta_path = _load_selected_cluster_delta(proof_run)
    proof_summary, proof_summary_path = _load_proof_summary(proof_run, selected_cluster_delta_path)

    selected_cluster_before = _summary_stage_metrics(
        selected_cluster_delta.get("before") if isinstance(selected_cluster_delta.get("before"), dict) else {}
    )
    selected_cluster_after = _summary_stage_metrics(
        selected_cluster_delta.get("after") if isinstance(selected_cluster_delta.get("after"), dict) else {}
    )
    baseline_selected_cluster_after = dict(baseline_selected_cluster_after or {})
    before_accepted_retention_ratio = _retention_ratio(
        selected_cluster_before.get("acceptedBallFrames"),
        baseline_selected_cluster_after.get("acceptedBallFrames"),
    )
    after_accepted_retention_ratio = _retention_ratio(
        selected_cluster_after.get("acceptedBallFrames"),
        baseline_selected_cluster_after.get("acceptedBallFrames"),
    )
    after_controlled_retention_ratio = _retention_ratio(
        selected_cluster_after.get("controlledPossessionFrames"),
        baseline_selected_cluster_after.get("controlledPossessionFrames"),
    )
    source_summaries = (
        dict(arm_payload.get("sourceSummaries"))
        if isinstance(arm_payload.get("sourceSummaries"), dict)
        else {}
    )
    final_source_summary = _source_summary_stage_metrics(source_summaries.get(failing_source_clip_id))

    return {
        "armName": str(arm_payload.get("armName") or ""),
        "proofSummary": _summary_stage_metrics(proof_summary),
        "selectedClusterBefore": {
            **selected_cluster_before,
            "acceptedRetentionRatio": before_accepted_retention_ratio,
        },
        "selectedClusterAfter": {
            **selected_cluster_after,
            "acceptedRetentionRatio": after_accepted_retention_ratio,
            "controlledRetentionRatio": after_controlled_retention_ratio,
        },
        "selectedClusterDelta": _stage_delta(selected_cluster_before, selected_cluster_after),
        "selectedClusterMeta": {
            "selectedClusterDeltaPath": str(selected_cluster_delta_path),
            "proofSummaryPath": str(proof_summary_path),
            "selectedClusterId": selected_cluster_delta.get("selectedClusterId"),
            "improvedFields": list(selected_cluster_delta.get("improvedFields") or []),
            "remainingTruthGateReasons": list(selected_cluster_delta.get("remainingTruthGateReasons") or []),
        },
        "finalSourceSummary": final_source_summary,
    }


def _classify_retention_blocker(
    *,
    winning_arm_stage_payload: dict[str, object],
) -> tuple[str, bool, str]:
    final_source_summary = dict(winning_arm_stage_payload.get("finalSourceSummary") or {})
    selected_cluster_before = dict(winning_arm_stage_payload.get("selectedClusterBefore") or {})
    selected_cluster_after = dict(winning_arm_stage_payload.get("selectedClusterAfter") or {})

    final_accepted_retention_ratio = _safe_float(final_source_summary.get("acceptedRetentionRatio"), 0.0)
    final_controlled_retention_ratio = _safe_float(final_source_summary.get("controlledRetentionRatio"), 0.0)
    before_accepted_retention_ratio = _safe_float(selected_cluster_before.get("acceptedRetentionRatio"), 0.0)
    after_controlled_retention_ratio = _safe_float(selected_cluster_after.get("controlledRetentionRatio"), 0.0)

    if (
        final_accepted_retention_ratio < RETENTION_GUARDRAIL
        and before_accepted_retention_ratio < RETENTION_GUARDRAIL
    ):
        return (
            PRIMARY_BLOCKER_ACCEPTED_SIGNAL,
            False,
            NEXT_BATCH_FOR_BLOCKER[PRIMARY_BLOCKER_ACCEPTED_SIGNAL],
        )
    if (
        before_accepted_retention_ratio >= RETENTION_GUARDRAIL
        and after_controlled_retention_ratio < RETENTION_GUARDRAIL
    ):
        return (
            PRIMARY_BLOCKER_SELECTED_CLUSTER,
            True,
            NEXT_BATCH_FOR_BLOCKER[PRIMARY_BLOCKER_SELECTED_CLUSTER],
        )
    if (
        final_accepted_retention_ratio >= RETENTION_GUARDRAIL
        and after_controlled_retention_ratio >= RETENTION_GUARDRAIL
        and final_controlled_retention_ratio < RETENTION_GUARDRAIL
    ):
        return (
            PRIMARY_BLOCKER_CONTROLLED_POSSESSION,
            False,
            NEXT_BATCH_FOR_BLOCKER[PRIMARY_BLOCKER_CONTROLLED_POSSESSION],
        )
    return (
        PRIMARY_BLOCKER_UNRESOLVED,
        False,
        "missing_evidence:retention_collapse_stage_boundary_unresolved",
    )


def _write_batch_outcome_markdown(path: Path, payload: dict[str, object]) -> None:
    text = "\n".join(
        [
            "# Promoted V6 Retention Delta Analysis v1",
            "",
            f"- batchGoal: {payload.get('batchGoal')}",
            f"- goalAchieved: {payload.get('goalAchieved')}",
            f"- roadmapAdvanceAllowed: {payload.get('roadmapAdvanceAllowed')}",
            f"- winningArmName: {payload.get('winningArmName')}",
            f"- primaryRetentionBlockerClass: {payload.get('primaryRetentionBlockerClass')}",
            f"- nextImplementationBatchRecommendation: {payload.get('nextImplementationBatchRecommendation')}",
            f"- nextRecommendedNextLever: {payload.get('nextRecommendedNextLever')}",
            "",
            "## English Summary",
            "",
            str(payload.get("englishSummary") or ""),
            "",
            "## English Decision",
            "",
            str(payload.get("englishDecision") or ""),
        ]
    )
    _write_text(path, text)


def run_promoted_touchline_detector_candidate_retention_delta_analysis(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    evaluation_root: Path = DEFAULT_EVALUATION_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    validation_root = Path(validation_root)
    analysis_root = Path(analysis_root)
    evaluation_root = Path(evaluation_root)

    arm_matrix = _load_json_dict(validation_root / "arm_matrix.json")
    validation_summary = _load_json_dict(validation_root / "validation_summary.json")
    evaluation_summary = _load_json_dict(evaluation_root / "evaluation_summary.json")

    baseline_arm_payload = _find_arm_payload(arm_matrix, ARM_NAME_BASELINE_CURRENT)
    baseline_stage_payload = _build_arm_stage_payload(
        arm_payload=baseline_arm_payload,
        failing_source_clip_id=failing_source_clip_id,
        baseline_selected_cluster_after=None,
    )
    baseline_selected_cluster_after = dict(baseline_stage_payload.get("selectedClusterAfter") or {})

    arm_stage_payloads = {
        ARM_NAME_BASELINE_CURRENT: baseline_stage_payload,
        ARM_NAME_PROMOTED_V6_BASELINE: _build_arm_stage_payload(
            arm_payload=_find_arm_payload(arm_matrix, ARM_NAME_PROMOTED_V6_BASELINE),
            failing_source_clip_id=failing_source_clip_id,
            baseline_selected_cluster_after=baseline_selected_cluster_after,
        ),
        ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN: _build_arm_stage_payload(
            arm_payload=_find_arm_payload(arm_matrix, ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN),
            failing_source_clip_id=failing_source_clip_id,
            baseline_selected_cluster_after=baseline_selected_cluster_after,
        ),
    }

    winning_arm_name = str(validation_summary.get("winningArmName") or ARM_NAME_PROMOTED_V6_BASELINE)
    winning_arm_stage_payload = arm_stage_payloads[winning_arm_name]
    primary_retention_blocker_class, selected_cluster_step_implicated, next_batch_recommendation = (
        _classify_retention_blocker(winning_arm_stage_payload=winning_arm_stage_payload)
    )
    winning_final_source_summary = dict(winning_arm_stage_payload.get("finalSourceSummary") or {})

    selected_cluster_follow_through_delta = {
        "generatedAt": _utc_now_iso(),
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "arms": [
            {
                "armName": arm_name,
                "before": arm_stage_payloads[arm_name]["selectedClusterBefore"],
                "after": arm_stage_payloads[arm_name]["selectedClusterAfter"],
                "delta": arm_stage_payloads[arm_name]["selectedClusterDelta"],
                "meta": arm_stage_payloads[arm_name]["selectedClusterMeta"],
            }
            for arm_name in (
                ARM_NAME_BASELINE_CURRENT,
                ARM_NAME_PROMOTED_V6_BASELINE,
                ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN,
            )
        ],
    }
    failing_source_stage_delta = {
        "generatedAt": _utc_now_iso(),
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "winningArmName": winning_arm_name,
        "baselineReference": {
            "selectedClusterAfter": baseline_selected_cluster_after,
        },
        "arms": [
            arm_stage_payloads[arm_name]
            for arm_name in (
                ARM_NAME_BASELINE_CURRENT,
                ARM_NAME_PROMOTED_V6_BASELINE,
                ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN,
            )
        ],
    }
    retention_delta_summary = {
        "generatedAt": _utc_now_iso(),
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "trainingCandidateName": validation_summary.get("trainingCandidateName")
        or evaluation_summary.get("trainingCandidateName"),
        "winningArmName": winning_arm_name,
        "primaryRetentionBlockerClass": primary_retention_blocker_class,
        "acceptedRetentionRatio": round(
            _safe_float(winning_final_source_summary.get("acceptedRetentionRatio"), 0.0),
            3,
        ),
        "controlledRetentionRatio": round(
            _safe_float(winning_final_source_summary.get("controlledRetentionRatio"), 0.0),
            3,
        ),
        "selectedClusterStepImplicated": selected_cluster_step_implicated,
        "nextImplementationBatchRecommendation": next_batch_recommendation,
        "goalAchieved": False,
        "roadmapAdvanceAllowed": False,
        "nextRecommendedNextLever": run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "winningArmName": winning_arm_name,
        "winningPromotionBlockers": list(validation_summary.get("winningPromotionBlockers") or []),
        "winningFailingSourceEdgeShareImprovement": round(
            _safe_float(validation_summary.get("winningFailingSourceEdgeShareImprovement"), 0.0),
            3,
        ),
        "classificationRules": {
            PRIMARY_BLOCKER_ACCEPTED_SIGNAL: (
                "accepted retention below guardrail and selected-cluster before already shows low accepted count"
            ),
            PRIMARY_BLOCKER_SELECTED_CLUSTER: (
                "accepted retention acceptable before cluster selection but controlled retention collapses after selected-cluster follow-through"
            ),
            PRIMARY_BLOCKER_CONTROLLED_POSSESSION: (
                "accepted retention acceptable but controlled retention still fails without cluster-step collapse"
            ),
            PRIMARY_BLOCKER_UNRESOLVED: "saved evidence does not isolate the first collapse point cleanly",
        },
        "resolvedDecision": {
            "primaryRetentionBlockerClass": primary_retention_blocker_class,
            "selectedClusterStepImplicated": selected_cluster_step_implicated,
            "nextImplementationBatchRecommendation": next_batch_recommendation,
        },
        "winningArmEvidence": winning_arm_stage_payload,
    }
    batch_outcome_analysis = {
        "batchGoal": (
            "Explain the promoted-v6 failing-source retention collapse from saved artifacts only and harden truth surfaces."
        ),
        "goalAchieved": False,
        "roadmapAdvanceAllowed": False,
        "winningArmName": winning_arm_name,
        "primaryRetentionBlockerClass": primary_retention_blocker_class,
        "nextImplementationBatchRecommendation": next_batch_recommendation,
        "nextRecommendedNextLever": run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
        "englishSummary": (
            "promoted_touchline_detector_candidate_retention_delta_analysis_v1 found that promoted v6 cleaned up failing-source edge share, but the winning arm still collapsed on retention before the repo could treat it as robust."
        ),
        "englishDecision": (
            "Runtime defaults stay frozen. The active lane remains promote_touchline_detector_candidate, and the next honest implementation batch is "
            f"{next_batch_recommendation}."
        ),
    }

    analysis_root.mkdir(parents=True, exist_ok=True)
    _write_json(analysis_root / "retention_delta_summary.json", retention_delta_summary)
    _write_json(analysis_root / "failing_source_stage_delta.json", failing_source_stage_delta)
    _write_json(
        analysis_root / "selected_cluster_follow_through_delta.json",
        selected_cluster_follow_through_delta,
    )
    _write_json(analysis_root / "decision_matrix.json", decision_matrix)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome_analysis)
    _write_batch_outcome_markdown(analysis_root / "batch_outcome_analysis.md", batch_outcome_analysis)
    return {
        **retention_delta_summary,
        "batchOutcomeAnalysis": batch_outcome_analysis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a saved-artifact promoted-v6 failing-source retention delta analysis."
    )
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT))
    parser.add_argument("--evaluation-root", default=str(DEFAULT_EVALUATION_ROOT))
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    args = parser.parse_args()

    payload = run_promoted_touchline_detector_candidate_retention_delta_analysis(
        storage_root=Path(args.storage_root),
        validation_root=Path(args.validation_root),
        analysis_root=Path(args.analysis_root),
        evaluation_root=Path(args.evaluation_root),
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
