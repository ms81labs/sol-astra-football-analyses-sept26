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

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_promotion_readiness_validation_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"

BLOCKER_MISSING_TRUTH = "v7_3_promotion_readiness_missing_upstream_truth"
BLOCKER_CHECKPOINT = "v7_3_promotion_checkpoint_contract_failure"
BLOCKER_EXPORT = "v7_3_promotion_export_contract_failure"
BLOCKER_BOUNDED = "v7_3_promotion_bounded_metric_failure"
BLOCKER_GUARDRAIL = "v7_3_promotion_guardrail_metric_failure"
BLOCKER_PIPELINE_FLOOD = "v7_3_promotion_full_pipeline_flood_regression"
BLOCKER_POSITIVE_RECALL = "v7_3_promotion_positive_recall_insufficient"
BLOCKER_PIPELINE_CONTRACT = "v7_3_promotion_pipeline_contract_failure"

NEXT_FULL_PIPELINE = "v7_3_full_pipeline_non_promotion_eval"
NEXT_RUNTIME_INTEGRATION = "v7_3_runtime_integration_fix"
NEXT_POSITIVE_DIVERSITY = "v7_3_positive_diversity_refresh"
NEXT_HARD_NEGATIVE = "v7_3_hard_negative_expansion"
NEXT_TRAINING_DEBUG = "v7_3_training_signal_regression_debug"
NEXT_CONTROLLED_SOURCE_ROBUSTNESS = "promoted_v7_3_source_robustness_validation"
NEXT_RUNTIME_DEFAULT = "v7_3_runtime_default_change_validation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return storage_root / "trained_detector_candidates" / candidate_name


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _truth_paths(candidate_root: Path, storage_root: Path) -> dict[str, Path]:
    return {
        "export": candidate_root / "v7_3_export_label_overlay_audit_v1" / "v7_3_label_overlay_audit.json",
        "bounded": candidate_root / "v7_3_bounded_retrain_v1" / "v7_3_bounded_retrain_summary.json",
        "guardrail": candidate_root
        / "v7_3_crop_probe_precision_guardrail_audit_v1"
        / "v7_3_crop_probe_precision_guardrail_summary.json",
        "pipeline": candidate_root
        / "v7_3_full_pipeline_non_promotion_eval_v1"
        / "v7_3_full_pipeline_non_promotion_summary.json",
        "suite": _suite_root(storage_root) / "suite_summary.json",
    }


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "controlled_candidate_promotion_readiness_validation",
            "successCriteria": [
                "v7.3 export, bounded, guardrail, and full-pipeline truth exist",
                "verified local trained checkpoint exists",
                "source-frame localization and observed-ball acceptance are >= 0.90",
                "old top-left, canary, sampled-frame, giant-box, and low-confidence floods are absent",
            ],
            "failureAdaptation": "If generated-artifact contracts are incomplete, move to promotion_readiness_contract_repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "promotion_readiness_contract_repair",
            "successCriteria": [
                "summary path and checkpoint-key mismatches are normalized",
                "missing generated-truth inputs are named exactly",
                "metric thresholds are not weakened",
            ],
            "failureAdaptation": "If model/runtime metrics fail after contract repair, stop with blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "promotion_readiness_blocker_summary",
            "successCriteria": [
                "blocker summary written",
                "exactly one next corrective family selected",
                "runtime-default switch is not executed by this batch",
            ],
            "failureAdaptation": "Stop after blocker summary; do not force controlled promotion.",
        },
    ]


def _float(payload: dict[str, Any] | None, key: str, default: float = 0.0) -> float:
    if payload is None:
        return default
    value = payload.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(payload: dict[str, Any] | None, key: str, default: bool = False) -> bool:
    if payload is None:
        return default
    return bool(payload.get(key, default))


def _checkpoint_path(bounded: dict[str, Any] | None) -> Path | None:
    if bounded is None:
        return None
    for key in (
        "bestWeightsPathLocal",
        "bestWeightsLocalPath",
        "lastWeightsPathLocal",
        "lastWeightsLocalPath",
    ):
        value = bounded.get(key)
        if not value:
            continue
        path = Path(str(value)).expanduser()
        if path.exists():
            return path
    return None


def _source_robustness_evidence(storage_root: Path, suite: dict[str, Any] | None) -> dict[str, Any]:
    """Prefer current runtime/source robustness truth over the legacy suite snapshot."""

    evidence_paths = [
        storage_root
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / "v7_2_post_runtime_default_source_robustness_validation_v1"
        / "post_runtime_default_source_robustness_summary.json",
        storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
    ]
    for path in evidence_paths:
        payload = _load_json(path)
        if payload is None:
            continue
        blockers = payload.get("runtimeDefaultMutationBlockers")
        if blockers is None:
            blockers = payload.get("sourceRobustnessPromotionBlockers")
        if not isinstance(blockers, list):
            blockers = []
        return {
            "sourceRobustnessEvidencePath": str(path),
            "sourceRobustnessOutcome": payload.get("sourceRobustnessOutcome"),
            "suiteVerdict": payload.get("suiteVerdict"),
            "runtimeDefaultMutationBlockers": [str(item) for item in blockers if str(item).strip()],
        }

    if suite is None:
        return {
            "sourceRobustnessEvidencePath": None,
            "sourceRobustnessOutcome": None,
            "suiteVerdict": None,
            "runtimeDefaultMutationBlockers": ["source_robustness_truth_missing"],
        }
    blockers = suite.get("sourceRobustnessPromotionBlockers")
    if not isinstance(blockers, list):
        blockers = ["source_robustness_promotion_blockers_missing"]
    return {
        "sourceRobustnessEvidencePath": str(_suite_root(storage_root) / "suite_summary.json"),
        "sourceRobustnessOutcome": suite.get("sourceRobustnessOutcome"),
        "suiteVerdict": suite.get("suiteVerdict"),
        "runtimeDefaultMutationBlockers": [str(item) for item in blockers if str(item).strip()],
    }


def _gate_audit(
    *,
    export: dict[str, Any] | None,
    bounded: dict[str, Any] | None,
    guardrail: dict[str, Any] | None,
    pipeline: dict[str, Any] | None,
    checkpoint: Path | None,
) -> dict[str, Any]:
    export_checks = {
        "exportGoalAchieved": _bool(export, "goalAchieved"),
        "positiveCropExampleCount": int(_float(export, "positiveCropExampleCount")),
        "positiveLabelsComplete": _float(export, "positiveLabelFilesWithExactlyOneBall")
        == _float(export, "positiveCropExampleCount"),
        "localHardNegativeCropCount": int(_float(export, "localHardNegativeCropCount")),
        "heldoutHardNegativeCanaryCount": int(_float(export, "heldoutHardNegativeCanaryCount")),
        "splitLeakageCount": int(_float(export, "splitLeakageCount")),
        "canaryLeakageCount": int(_float(export, "canaryLeakageCount")),
        "unsafeFullFrameNegativeExportCount": int(_float(export, "unsafeFullFrameNegativeExportCount")),
        "positiveLabelRoundTripMaxErrorPx": _float(export, "positiveLabelRoundTripMaxErrorPx", 999.0),
    }
    export_checks["exportGatePassed"] = bool(
        export_checks["exportGoalAchieved"]
        and export_checks["positiveCropExampleCount"] >= 414
        and export_checks["positiveLabelsComplete"]
        and export_checks["localHardNegativeCropCount"] >= 180
        and export_checks["heldoutHardNegativeCanaryCount"] >= 20
        and export_checks["splitLeakageCount"] == 0
        and export_checks["canaryLeakageCount"] == 0
        and export_checks["unsafeFullFrameNegativeExportCount"] == 0
        and export_checks["positiveLabelRoundTripMaxErrorPx"] <= 1.0
    )

    bounded_checks = {
        "boundedGoalAchieved": _bool(bounded, "goalAchieved"),
        "trainingCompleted": _bool(bounded, "trainingCompleted"),
        "checkpointContractPassed": _bool(bounded, "checkpointContractPassed"),
        "inferenceUsedTrainedWeights": _bool(bounded, "inferenceUsedTrainedWeights"),
        "inferenceUsedRemotePath": _bool(bounded, "inferenceUsedRemotePath"),
        "inferenceUsedBaseModel": _bool(bounded, "inferenceUsedBaseModel"),
        "localCheckpointExists": checkpoint is not None,
        "boundedTrainPositiveLocalizationHitRate": _float(bounded, "boundedTrainPositiveLocalizationHitRate"),
        "boundedValPositiveLocalizationHitRate": _float(bounded, "boundedValPositiveLocalizationHitRate"),
        "boundedValNegativeFalsePositiveFrameRate": _float(bounded, "boundedValNegativeFalsePositiveFrameRate"),
        "heldoutCanaryFalsePositiveFrameRate": _float(bounded, "heldoutCanaryFalsePositiveFrameRate"),
        "medianValPositiveConfidence": _float(bounded, "medianValPositiveConfidence"),
        "topLeftArtifactShare": _float(bounded, "topLeftArtifactShare"),
        "giantBoxShare": _float(bounded, "giantBoxShare"),
        "nearConstantLowConfidenceFlood": _bool(bounded, "nearConstantLowConfidenceFlood"),
    }
    bounded_checks["boundedGatePassed"] = bool(
        bounded_checks["boundedGoalAchieved"]
        and bounded_checks["trainingCompleted"]
        and bounded_checks["checkpointContractPassed"]
        and bounded_checks["inferenceUsedTrainedWeights"]
        and not bounded_checks["inferenceUsedRemotePath"]
        and not bounded_checks["inferenceUsedBaseModel"]
        and bounded_checks["localCheckpointExists"]
        and bounded_checks["boundedTrainPositiveLocalizationHitRate"] >= 0.85
        and bounded_checks["boundedValPositiveLocalizationHitRate"] >= 0.70
        and bounded_checks["boundedValNegativeFalsePositiveFrameRate"] <= 0.05
        and bounded_checks["heldoutCanaryFalsePositiveFrameRate"] <= 0.10
        and bounded_checks["medianValPositiveConfidence"] > 0.10
        and bounded_checks["topLeftArtifactShare"] == 0.0
        and bounded_checks["giantBoxShare"] == 0.0
        and not bounded_checks["nearConstantLowConfidenceFlood"]
    )

    guardrail_checks = {
        "guardrailGoalAchieved": _bool(guardrail, "goalAchieved"),
        "precisionGuardrailPassed": _bool(guardrail, "precisionGuardrailPassed"),
        "checkpointContractPassed": _bool(guardrail, "checkpointContractPassed"),
        "inferenceUsedTrainedWeights": _bool(guardrail, "inferenceUsedTrainedWeights"),
        "boundedValPositiveLocalizationHitRate": _float(guardrail, "boundedValPositiveLocalizationHitRate"),
        "oldTopLeftArtifactFalsePositiveFrameRate": _float(guardrail, "oldTopLeftArtifactFalsePositiveFrameRate"),
        "heldoutCanaryFalsePositiveFrameRate": _float(guardrail, "heldoutCanaryFalsePositiveFrameRate"),
        "topLeftArtifactShare": _float(guardrail, "topLeftArtifactShare"),
        "giantBoxShare": _float(guardrail, "giantBoxShare"),
        "nearConstantLowConfidenceFlood": _bool(guardrail, "nearConstantLowConfidenceFlood"),
    }
    guardrail_checks["guardrailGatePassed"] = bool(
        guardrail_checks["guardrailGoalAchieved"]
        and guardrail_checks["precisionGuardrailPassed"]
        and guardrail_checks["checkpointContractPassed"]
        and guardrail_checks["inferenceUsedTrainedWeights"]
        and guardrail_checks["boundedValPositiveLocalizationHitRate"] >= 0.70
        and guardrail_checks["oldTopLeftArtifactFalsePositiveFrameRate"] == 0.0
        and guardrail_checks["heldoutCanaryFalsePositiveFrameRate"] == 0.0
        and guardrail_checks["topLeftArtifactShare"] == 0.0
        and guardrail_checks["giantBoxShare"] == 0.0
        and not guardrail_checks["nearConstantLowConfidenceFlood"]
    )

    pipeline_checks = {
        "pipelineGoalAchieved": _bool(pipeline, "goalAchieved"),
        "checkpointContractPassed": _bool(pipeline, "checkpointContractPassed"),
        "inferenceUsedTrainedWeights": _bool(pipeline, "inferenceUsedTrainedWeights"),
        "inferenceUsedRemotePath": _bool(pipeline, "inferenceUsedRemotePath"),
        "inferenceUsedBaseModel": _bool(pipeline, "inferenceUsedBaseModel"),
        "pipelineCropContractMatchesTraining": _bool(pipeline, "pipelineCropContractMatchesTraining"),
        "projectionAuditPassed": _bool(pipeline, "projectionAuditPassed"),
        "candidateCropCoverageRate": _float(pipeline, "candidateCropCoverageRate"),
        "sourceFrameLocalizationHitRate": _float(pipeline, "sourceFrameLocalizationHitRate"),
        "observedBallAcceptanceRate": _float(pipeline, "observedBallAcceptanceRate"),
        "oldTopLeftArtifactFalsePositiveFrameRate": _float(pipeline, "oldTopLeftArtifactFalsePositiveFrameRate"),
        "heldoutCanaryFalsePositiveFrameRate": _float(pipeline, "heldoutCanaryFalsePositiveFrameRate"),
        "sampledFrameDetectionRate": _float(pipeline, "sampledFrameDetectionRate"),
        "topLeftArtifactShare": _float(pipeline, "topLeftArtifactShare"),
        "giantBoxShare": _float(pipeline, "giantBoxShare"),
        "nearConstantLowConfidenceFlood": _bool(pipeline, "nearConstantLowConfidenceFlood"),
    }
    pipeline_checks["pipelineGatePassed"] = bool(
        pipeline_checks["pipelineGoalAchieved"]
        and pipeline_checks["checkpointContractPassed"]
        and pipeline_checks["inferenceUsedTrainedWeights"]
        and not pipeline_checks["inferenceUsedRemotePath"]
        and not pipeline_checks["inferenceUsedBaseModel"]
        and pipeline_checks["pipelineCropContractMatchesTraining"]
        and pipeline_checks["projectionAuditPassed"]
        and pipeline_checks["candidateCropCoverageRate"] >= 0.90
        and pipeline_checks["sourceFrameLocalizationHitRate"] >= 0.90
        and pipeline_checks["observedBallAcceptanceRate"] >= 0.90
        and pipeline_checks["oldTopLeftArtifactFalsePositiveFrameRate"] == 0.0
        and pipeline_checks["heldoutCanaryFalsePositiveFrameRate"] == 0.0
        and pipeline_checks["sampledFrameDetectionRate"] <= 0.25
        and pipeline_checks["topLeftArtifactShare"] == 0.0
        and pipeline_checks["giantBoxShare"] == 0.0
        and not pipeline_checks["nearConstantLowConfidenceFlood"]
    )
    return {
        "export": export_checks,
        "bounded": bounded_checks,
        "guardrail": guardrail_checks,
        "pipeline": pipeline_checks,
    }


def _classify(gate_audit: dict[str, Any], missing_inputs: list[str]) -> tuple[str | None, str, bool, str]:
    if missing_inputs:
        return (
            BLOCKER_MISSING_TRUTH,
            NEXT_FULL_PIPELINE,
            False,
            "Promotion readiness cannot run because one or more generated v7.3 truth artifacts are missing.",
        )
    bounded = gate_audit["bounded"]
    pipeline = gate_audit["pipeline"]
    if not bounded["localCheckpointExists"] or not bounded["checkpointContractPassed"]:
        return (
            BLOCKER_CHECKPOINT,
            NEXT_TRAINING_DEBUG,
            False,
            "No verified local v7.3 trained checkpoint is available for promotion readiness.",
        )
    if not gate_audit["export"]["exportGatePassed"]:
        return (
            BLOCKER_EXPORT,
            "v7_3_export_label_overlay_audit",
            False,
            "The v7.3 physical export contract no longer clears promotion-readiness requirements.",
        )
    if not bounded["boundedGatePassed"]:
        return (
            BLOCKER_BOUNDED,
            NEXT_TRAINING_DEBUG,
            False,
            "The v7.3 bounded retrain metrics do not clear promotion-readiness requirements.",
        )
    if not gate_audit["guardrail"]["guardrailGatePassed"]:
        return (
            BLOCKER_GUARDRAIL,
            NEXT_HARD_NEGATIVE,
            False,
            "The v7.3 crop precision guardrail no longer clears promotion-readiness requirements.",
        )
    if (
        pipeline["oldTopLeftArtifactFalsePositiveFrameRate"] > 0.0
        or pipeline["topLeftArtifactShare"] > 0.0
        or pipeline["giantBoxShare"] > 0.0
        or pipeline["sampledFrameDetectionRate"] > 0.25
        or pipeline["nearConstantLowConfidenceFlood"]
    ):
        return (
            BLOCKER_PIPELINE_FLOOD,
            NEXT_RUNTIME_INTEGRATION,
            False,
            "The full-pipeline gate shows a v7.3 flood/artifact regression.",
        )
    if pipeline["sourceFrameLocalizationHitRate"] < 0.90 or pipeline["observedBallAcceptanceRate"] < 0.90:
        return (
            BLOCKER_POSITIVE_RECALL,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "The full-pipeline gate does not localize/accept enough reviewed positives for promotion readiness.",
        )
    if not pipeline["pipelineGatePassed"]:
        return (
            BLOCKER_PIPELINE_CONTRACT,
            NEXT_RUNTIME_INTEGRATION,
            False,
            "The full-pipeline runtime/projection contract failed promotion readiness.",
        )
    return (
        None,
        "",
        True,
        "v7.3 cleared controlled promotion-readiness gates from generated export, bounded, guardrail, and full-pipeline truth.",
    )


def _runtime_contract(candidate_name: str, checkpoint: Path | None, bounded: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "trainingCandidateName": candidate_name,
        "trainingCandidateVersion": "v7.3",
        "primaryDetectorModelPath": "yolov10n.pt",
        "auxiliaryBallModelPath": str(checkpoint) if checkpoint is not None else None,
        "auxiliaryBallModelProfile": "ball_probe_only_v7_3_crop_256",
        "detectorInputSize": 256,
        "selectedCheckpointForVerdict": bounded.get("selectedCheckpointForVerdict") if bounded else None,
        "selectedAuditConf": bounded.get("selectedAuditConf") if bounded else None,
        "runtimeUse": "controlled_internal_candidate_runs",
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# V7.3 Promotion Readiness Validation",
        "",
        f"- Goal achieved: `{summary.get('goalAchieved')}`",
        f"- Primary blocker: `{summary.get('primaryBlocker')}`",
        f"- Promotion validated: `{summary.get('promotionValidated')}`",
        f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
        f"- Promotion ready: `{summary.get('promotionReady')}`",
        f"- Promoted for controlled runs: `{summary.get('promotedForControlledRuns')}`",
        f"- Controlled runtime registry updated: `{summary.get('controlledRuntimeRegistryUpdated')}`",
        f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
        f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
        f"- Next: `{summary.get('nextRecommendedNextLever')}`",
        "",
        str(summary.get("englishDecision") or ""),
        "",
    ]
    blockers = list(summary.get("promotionValidationBlockers") or [])
    if blockers:
        lines.extend(["## Promotion Validation Blockers", ""])
        lines.extend([f"- {blocker}" for blocker in blockers])
        lines.append("")
    runtime_blockers = list(summary.get("runtimeDefaultMutationBlockers") or [])
    if runtime_blockers:
        lines.extend(["## Runtime Default Mutation Blockers", ""])
        lines.extend([f"- {blocker}" for blocker in runtime_blockers])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_v7_3_promotion_readiness_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "controlled_candidate_promotion_readiness_validation",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    output_root = reset_output(candidate_root, output_dir_name)

    paths = _truth_paths(candidate_root, storage_root)
    truth = {name: _load_json(path) for name, path in paths.items()}
    missing_inputs = [name for name, payload in truth.items() if payload is None]
    export = truth["export"]
    bounded = truth["bounded"]
    guardrail = truth["guardrail"]
    pipeline = truth["pipeline"]
    suite = truth["suite"]
    checkpoint = _checkpoint_path(bounded)
    gate_audit = _gate_audit(
        export=export,
        bounded=bounded,
        guardrail=guardrail,
        pipeline=pipeline,
        checkpoint=checkpoint,
    )
    primary_blocker, next_lever, promotion_validated, english = _classify(gate_audit, missing_inputs)
    source_evidence = _source_robustness_evidence(storage_root, suite)
    runtime_blockers = source_evidence["runtimeDefaultMutationBlockers"]
    runtime_default_mutation_allowed = bool(promotion_validated and not runtime_blockers)
    if promotion_validated:
        next_lever = NEXT_RUNTIME_DEFAULT if runtime_default_mutation_allowed else NEXT_CONTROLLED_SOURCE_ROBUSTNESS

    attempts = _attempt_plan()
    runtime_contract = _runtime_contract(candidate_name, checkpoint, bounded)
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "v7_3_promotion_readiness_validation",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "generatedAt": generated_at,
        "trainingCandidateName": candidate_name,
        "trainingCandidateVersion": "v7.3",
        "goalAchieved": promotion_validated,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "promotionValidationBlockers": [] if promotion_validated else [primary_blocker],
        "promotionValidated": promotion_validated,
        "candidateReadyForEvaluation": promotion_validated,
        "promotionReady": promotion_validated,
        "promotedForControlledRuns": promotion_validated,
        "controlledRuntimeRegistryUpdated": promotion_validated,
        "runtimeDefaultMutationEvaluated": True,
        "runtimeDefaultMutationAllowed": runtime_default_mutation_allowed,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": runtime_blockers,
        "nextRecommendedNextLever": next_lever,
        "missingInputNames": missing_inputs,
        "englishDecision": english
        if not promotion_validated
        else (
            "v7.3 is validated for controlled promotion use. Runtime-default mutation was evaluated separately and "
            + (
                "is allowed for the next strict default-change validation gate, but was not executed here."
                if runtime_default_mutation_allowed
                else "remains blocked by source-robustness truth; no default switch was executed."
            )
        ),
        "sourceRobustnessEvidencePath": source_evidence["sourceRobustnessEvidencePath"],
        "sourceRobustnessOutcome": source_evidence["sourceRobustnessOutcome"],
        "suiteVerdict": source_evidence["suiteVerdict"],
        "sourceRobustnessPromotionBlockers": runtime_blockers,
        "runtimeContract": runtime_contract,
        "gateHighlights": {
            "positiveCropExampleCount": gate_audit["export"]["positiveCropExampleCount"],
            "boundedValPositiveLocalizationHitRate": gate_audit["bounded"][
                "boundedValPositiveLocalizationHitRate"
            ],
            "guardrailValPositiveLocalizationHitRate": gate_audit["guardrail"][
                "boundedValPositiveLocalizationHitRate"
            ],
            "sourceFrameLocalizationHitRate": gate_audit["pipeline"]["sourceFrameLocalizationHitRate"],
            "observedBallAcceptanceRate": gate_audit["pipeline"]["observedBallAcceptanceRate"],
            "oldTopLeftArtifactFalsePositiveFrameRate": gate_audit["pipeline"][
                "oldTopLeftArtifactFalsePositiveFrameRate"
            ],
            "sampledFrameDetectionRate": gate_audit["pipeline"]["sampledFrameDetectionRate"],
        },
    }

    readiness_contract = {
        "generatedAt": generated_at,
        "candidateReadyForEvaluation": promotion_validated,
        "promotionReady": promotion_validated,
        "promotionValidated": promotion_validated,
        "trainingCandidateName": candidate_name,
        "trainingCandidateVersion": "v7.3",
        "sourceTruth": {name: str(path) for name, path in paths.items()},
        "runtimeContract": runtime_contract,
    }
    runtime_default_audit = {
        "generatedAt": generated_at,
        "runtimeDefaultMutationEvaluated": True,
        "runtimeDefaultMutationAllowed": runtime_default_mutation_allowed,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": runtime_blockers,
        "nextRecommendedNextLever": next_lever,
    }
    controlled_registry_entry = {
        "generatedAt": generated_at,
        "trainingCandidateName": candidate_name,
        "trainingCandidateVersion": "v7.3",
        "promotionBatchName": "v7_3_promotion_readiness_validation",
        "promotionValidated": promotion_validated,
        "promotionReady": promotion_validated,
        "candidateReadyForEvaluation": promotion_validated,
        "promotedForControlledRuns": promotion_validated,
        "runtimeDefaultChanged": False,
        "runtimeDefaultChangeAllowed": runtime_default_mutation_allowed,
        "runtimeDefaultChangeBlockers": runtime_blockers,
        "runtimeDefaultMutationAllowed": runtime_default_mutation_allowed,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": runtime_blockers,
        "runtimeContract": runtime_contract,
        "evidence": {
            "promotionReadinessSummaryPath": str(output_root / "v7_3_promotion_readiness_summary.json"),
            "fullPipelineSummaryPath": str(paths["pipeline"]),
            "guardrailSummaryPath": str(paths["guardrail"]),
            "boundedRetrainSummaryPath": str(paths["bounded"]),
            "exportSummaryPath": str(paths["export"]),
        },
        "nextRecommendedNextLever": next_lever,
    }
    suite_promotion_payload = {
        **controlled_registry_entry,
        "batchOutcomeAnalysis": {
            "batchGoal": "Validate v7.3 for controlled promotion readiness from generated truth.",
            "goalAchieved": promotion_validated,
            "roadmapAdvanceAllowed": True,
            "promotionValidated": promotion_validated,
            "promotedForControlledRuns": promotion_validated,
            "runtimeDefaultChanged": False,
            "runtimeDefaultChangeAllowed": runtime_default_mutation_allowed,
            "runtimeDefaultChangeBlockers": runtime_blockers,
            "primaryBlocker": primary_blocker,
            "nextRecommendedNextLever": next_lever,
            "englishDecision": summary["englishDecision"],
        },
    }

    _write_json(output_root / "v7_3_promotion_readiness_summary.json", summary)
    _write_json(output_root / "promotion_gate_audit.json", {"summary": summary, "gateAudit": gate_audit})
    _write_json(output_root / "runtime_contract_audit.json", runtime_contract)
    _write_json(output_root / "candidate_evaluation_readiness_contract.json", readiness_contract)
    _write_json(output_root / "controlled_runtime_registry_entry.json", controlled_registry_entry)
    _write_json(output_root / "runtime_default_mutation_audit.json", runtime_default_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": generated_at, "summary": summary, "attempts": attempts})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "gateAudit": gate_audit,
            "runtimeDefaultMutationAudit": runtime_default_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")

    suite_readiness_path = _suite_root(storage_root) / "v7_3_detector_candidate_promotion_readiness.json"
    _write_json(
        suite_readiness_path,
        {**summary, "summary": summary, "controlledRuntimeRegistryEntry": controlled_registry_entry},
    )
    _write_json(_suite_root(storage_root) / "detector_candidate_promotion.json", suite_promotion_payload)
    if promotion_validated:
        _write_json(storage_root / "runtime" / "promoted_touchline_detector_candidate.json", controlled_registry_entry)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate v7.3 controlled promotion readiness from generated truth.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="controlled_candidate_promotion_readiness_validation",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    payload = run_v7_3_promotion_readiness_validation(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
