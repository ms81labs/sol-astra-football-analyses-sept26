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

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_runtime_default_change_validation_v1"

BLOCKER_CANDIDATE_CONTRACT = "v7_3_runtime_default_candidate_contract_gap"
BLOCKER_GUARDRAIL = "v7_3_runtime_default_guardrail_regression"
BLOCKER_SOURCE_REGENERATION = "v7_3_runtime_default_source_robustness_regeneration_failed"
BLOCKER_REGISTRY = "v7_3_runtime_default_registry_contract_gap"

NEXT_CONTRACT_FIX = "v7_3_runtime_default_contract_fix"
NEXT_PIPELINE_REPAIR = "v7_3_runtime_default_pipeline_guardrail_repair"
NEXT_SOURCE_DEBUG = "v7_3_source_robustness_regression_debug"
NEXT_POST_MUTATION = "v7_3_post_runtime_default_source_robustness_validation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _candidate_root(storage_root: Path) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME


def _runtime_registry_path(storage_root: Path) -> Path:
    return Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json"


def _source_robustness_path(storage_root: Path) -> Path:
    return (
        _suite_root(storage_root)
        / "v7_2_post_runtime_default_source_robustness_validation_v1"
        / "post_runtime_default_source_robustness_summary.json"
    )


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "runtime_default_candidate_contract_validation",
            "successCriteria": [
                "v7.3 promotion-readiness truth allows runtime-default validation",
                "controlled runtime registry points to v7.3 with default mutation not yet executed",
                "full-pipeline guardrails remain clean",
            ],
            "failureAdaptation": "If the candidate/default contract is incomplete, keep defaults unchanged and select v7_3_runtime_default_contract_fix.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "runtime_default_source_robustness_regeneration",
            "successCriteria": [
                "current source-robustness evidence has no runtime-default blockers",
                "top-left, canary, sampled-frame, projection, and checkpoint guardrails remain clean",
                "runtime default registry mutation is allowed only after generated truth clears",
            ],
            "failureAdaptation": "If source robustness or pipeline truth regresses, keep defaults unchanged and select the matching debug lane.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "runtime_default_change_blocker_summary",
            "successCriteria": [
                "write exactly one blocker or execute exactly one validated default mutation",
                "write exactly one next family",
                "no training or retraining is triggered",
            ],
            "failureAdaptation": "Stop after blocker summary unless the default-change gate is fully clear.",
        },
    ]


def _candidate_contract_audit(readiness: dict[str, Any] | None, suite_readiness: dict[str, Any] | None) -> dict[str, Any]:
    runtime_contract = readiness.get("runtimeContract") if isinstance(readiness, dict) else None
    checkpoint_path = Path(str(runtime_contract.get("auxiliaryBallModelPath"))) if isinstance(runtime_contract, dict) and runtime_contract.get("auxiliaryBallModelPath") else None
    checks = {
        "readinessExists": isinstance(readiness, dict),
        "suiteReadinessExists": isinstance(suite_readiness, dict),
        "readinessGoalAchieved": bool((readiness or {}).get("goalAchieved")),
        "promotionValidated": bool((readiness or {}).get("promotionValidated")),
        "promotionReady": bool((readiness or {}).get("promotionReady")),
        "candidateReadyForEvaluation": bool((readiness or {}).get("candidateReadyForEvaluation")),
        "runtimeDefaultMutationAllowed": bool((readiness or {}).get("runtimeDefaultMutationAllowed")),
        "runtimeDefaultNotAlreadyMutated": not bool((readiness or {}).get("runtimeDefaultMutationExecuted")),
        "trainingCandidateVersionV7_3": (readiness or {}).get("trainingCandidateVersion") == "v7.3",
        "runtimeContractPresent": isinstance(runtime_contract, dict),
        "runtimeContractVersionV7_3": bool(
            isinstance(runtime_contract, dict) and runtime_contract.get("trainingCandidateVersion") == "v7.3"
        ),
        "runtimeContractCheckpointExists": bool(checkpoint_path and checkpoint_path.exists()),
        "suitePromotionReady": bool(
            isinstance(suite_readiness, dict)
            and suite_readiness.get("promotionReady")
            and suite_readiness.get("candidateReadyForEvaluation")
            and suite_readiness.get("trainingCandidateVersion") == "v7.3"
        ),
    }
    return {
        "checks": checks,
        "candidateContractPassed": all(checks.values()),
        "runtimeContract": runtime_contract or {},
    }


def _pipeline_guardrail_audit(pipeline: dict[str, Any] | None) -> dict[str, Any]:
    checks = {
        "pipelineExists": isinstance(pipeline, dict),
        "pipelineGoalAchieved": bool((pipeline or {}).get("goalAchieved")),
        "checkpointContractPassed": bool((pipeline or {}).get("checkpointContractPassed")),
        "inferenceUsedTrainedWeights": bool((pipeline or {}).get("inferenceUsedTrainedWeights")),
        "inferenceUsedRemotePathFalse": not bool((pipeline or {}).get("inferenceUsedRemotePath")),
        "inferenceUsedBaseModelFalse": not bool((pipeline or {}).get("inferenceUsedBaseModel")),
        "pipelineCropContractMatchesTraining": bool((pipeline or {}).get("pipelineCropContractMatchesTraining")),
        "projectionAuditPassed": bool((pipeline or {}).get("projectionAuditPassed")),
        "candidateCropCoverageRateStrong": float((pipeline or {}).get("candidateCropCoverageRate") or 0.0) >= 0.90,
        "sourceFrameLocalizationHitRateStrong": float((pipeline or {}).get("sourceFrameLocalizationHitRate") or 0.0) >= 0.90,
        "observedBallAcceptanceRateStrong": float((pipeline or {}).get("observedBallAcceptanceRate") or 0.0) >= 0.90,
        "oldTopLeftArtifactClear": float((pipeline or {}).get("oldTopLeftArtifactFalsePositiveFrameRate") or 0.0) == 0.0,
        "heldoutCanaryClear": float((pipeline or {}).get("heldoutCanaryFalsePositiveFrameRate") or 0.0) == 0.0,
        "sampledFrameFloodClear": float((pipeline or {}).get("sampledFrameDetectionRate") or 0.0) <= 0.25,
        "topLeftArtifactShareClear": float((pipeline or {}).get("topLeftArtifactShare") or 0.0) == 0.0,
        "giantBoxShareClear": float((pipeline or {}).get("giantBoxShare") or 0.0) == 0.0,
        "lowConfidenceFloodClear": not bool((pipeline or {}).get("nearConstantLowConfidenceFlood")),
    }
    return {
        "checks": checks,
        "pipelineGuardrailPassed": all(checks.values()),
        "sourceFrameLocalizationHitRate": (pipeline or {}).get("sourceFrameLocalizationHitRate"),
        "observedBallAcceptanceRate": (pipeline or {}).get("observedBallAcceptanceRate"),
    }


def _source_regeneration_audit(source: dict[str, Any] | None) -> dict[str, Any]:
    blockers = (source or {}).get("runtimeDefaultMutationBlockers")
    if not isinstance(blockers, list):
        blockers = ["source_robustness_truth_missing"] if source is None else ["source_robustness_blocker_contract_missing"]
    checks = {
        "sourceEvidenceExists": isinstance(source, dict),
        "sourceGoalAchieved": bool((source or {}).get("goalAchieved", True)),
        "sourceRobustnessViable": (source or {}).get("sourceRobustnessOutcome")
        == "source_robustness_viable_by_validated_inboard_recovery",
        "runtimeDefaultMutationBlockersClear": len(blockers) == 0,
    }
    passed = all(checks.values())
    return {
        "checks": checks,
        "sourceRobustnessRegenerationPassed": passed,
        "regeneratedSourceRobustnessOutcome": (source or {}).get("sourceRobustnessOutcome")
        if passed
        else "source_robustness_regeneration_failed",
        "runtimeDefaultMutationReady": passed,
        "runtimeDefaultMutationBlockers": [] if passed else [str(item) for item in blockers if str(item).strip()],
    }


def _registry_audit(registry: dict[str, Any] | None) -> dict[str, Any]:
    runtime_contract = registry.get("runtimeContract") if isinstance(registry, dict) else None
    checks = {
        "registryExists": isinstance(registry, dict),
        "registryPointsToV7_3": bool(
            isinstance(registry, dict)
            and registry.get("trainingCandidateName") == DEFAULT_CANDIDATE_NAME
            and registry.get("trainingCandidateVersion") == "v7.3"
        ),
        "registryPromotionValidated": bool(isinstance(registry, dict) and registry.get("promotionValidated")),
        "registryPromotedForControlledRuns": bool(isinstance(registry, dict) and registry.get("promotedForControlledRuns")),
        "registryDefaultNotAlreadyMutated": not bool(isinstance(registry, dict) and registry.get("runtimeDefaultMutationExecuted")),
        "runtimeContractPresent": isinstance(runtime_contract, dict),
        "runtimeContractVersionV7_3": bool(isinstance(runtime_contract, dict) and runtime_contract.get("trainingCandidateVersion") == "v7.3"),
    }
    return {
        "checks": checks,
        "runtimeRegistryContractPassed": all(checks.values()),
        "registryBefore": registry or {},
    }


def _classify(
    *,
    candidate_contract: dict[str, Any],
    pipeline_guardrail: dict[str, Any],
    source_regeneration: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not candidate_contract["candidateContractPassed"]:
        return (
            BLOCKER_CANDIDATE_CONTRACT,
            NEXT_CONTRACT_FIX,
            False,
            "The v7.3 promotion-readiness contract is incomplete; defaults remain unchanged.",
        )
    if not pipeline_guardrail["pipelineGuardrailPassed"]:
        return (
            BLOCKER_GUARDRAIL,
            NEXT_PIPELINE_REPAIR,
            False,
            "The v7.3 full-pipeline guardrail regressed; defaults remain unchanged.",
        )
    if not source_regeneration["sourceRobustnessRegenerationPassed"]:
        return (
            BLOCKER_SOURCE_REGENERATION,
            NEXT_SOURCE_DEBUG,
            False,
            "The runtime-default source-robustness evidence is blocked; defaults remain unchanged.",
        )
    if not registry["runtimeRegistryContractPassed"]:
        return (
            BLOCKER_REGISTRY,
            NEXT_CONTRACT_FIX,
            False,
            "The controlled runtime registry is stale or incomplete; defaults remain unchanged.",
        )
    return (
        None,
        NEXT_POST_MUTATION,
        True,
        "Runtime-default validation passed and the default registry was updated to the validated v7.3 candidate contract.",
    )


def _runtime_default_registry_entry(
    *,
    registry_before: dict[str, Any],
    summary: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    entry = dict(registry_before)
    entry.update(
        {
            "runtimeDefaultChanged": True,
            "runtimeDefaultChangeAllowed": True,
            "runtimeDefaultChangeBlockers": [],
            "runtimeDefaultMutationAllowed": True,
            "runtimeDefaultMutationReady": True,
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultMutationBlockers": [],
            "runtimeDefaultChangeBatchName": "v7_3_runtime_default_change_validation",
            "runtimeUse": "default_runtime",
            "sourceRobustnessOutcome": summary["sourceRobustnessOutcome"],
            "nextRecommendedNextLever": summary["nextRecommendedNextLever"],
            "runtimeDefaultEvidence": {
                "runtimeDefaultChangeSummaryPath": str(output_root / "runtime_default_change_summary.json"),
                "candidateContractAuditPath": str(output_root / "runtime_default_candidate_contract_audit.json"),
                "sourceRobustnessRegenerationAuditPath": str(
                    output_root / "runtime_default_source_robustness_regeneration_audit.json"
                ),
            },
        }
    )
    return entry


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Runtime Default Change Validation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Runtime default changed: `{summary.get('runtimeDefaultChanged')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Promotion mutation executed: `{summary.get('promotionMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_runtime_default_change_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "runtime_default_candidate_contract_validation",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    candidate_root = _candidate_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    readiness = _load_json(
        candidate_root
        / "v7_3_promotion_readiness_validation_v1"
        / "v7_3_promotion_readiness_summary.json"
    )
    suite_readiness = _load_json(suite_root / "v7_3_detector_candidate_promotion_readiness.json")
    pipeline = _load_json(
        candidate_root
        / "v7_3_full_pipeline_non_promotion_eval_v1"
        / "v7_3_full_pipeline_non_promotion_summary.json"
    )
    source_evidence = _load_json(_source_robustness_path(storage_root))
    registry_payload = _load_json(_runtime_registry_path(storage_root))

    candidate_contract = _candidate_contract_audit(readiness, suite_readiness)
    pipeline_guardrail = _pipeline_guardrail_audit(pipeline)
    source_regeneration = _source_regeneration_audit(source_evidence)
    registry = _registry_audit(registry_payload)
    primary_blocker, next_lever, mutation_allowed, english = _classify(
        candidate_contract=candidate_contract,
        pipeline_guardrail=pipeline_guardrail,
        source_regeneration=source_regeneration,
        registry=registry,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    mutation_executed = primary_blocker is None and mutation_allowed
    source_outcome = source_regeneration["regeneratedSourceRobustnessOutcome"]
    summary: dict[str, Any] = {
        "batchName": "v7_3_runtime_default_change_validation",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in attempts],
        "goalAchieved": mutation_executed,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "runtimeDefaultChanged": mutation_executed,
        "runtimeDefaultMutationAllowed": mutation_allowed,
        "runtimeDefaultMutationReady": mutation_allowed,
        "runtimeDefaultMutationExecuted": mutation_executed,
        "runtimeDefaultMutationBlockers": [] if mutation_executed else [primary_blocker],
        "sourceRobustnessOutcome": source_outcome,
        "sourceRobustnessDefaultChangeGatePassed": mutation_executed,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationAllowed": False,
        "promotionMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    registry_after = registry["registryBefore"]
    if mutation_executed:
        registry_after = _runtime_default_registry_entry(
            registry_before=registry["registryBefore"],
            summary=summary,
            output_root=output_root,
        )
        _write_json(_runtime_registry_path(storage_root), registry_after)

    mutation_audit = {
        "generatedAt": generated_at,
        "runtimeDefaultMutationAllowed": mutation_allowed,
        "runtimeDefaultMutationExecuted": mutation_executed,
        "runtimeDefaultRegistryPath": str(_runtime_registry_path(storage_root)),
        "registryBefore": registry["registryBefore"],
        "registryAfter": registry_after,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {
                "condition": "candidate_contract_gap",
                "selected": primary_blocker == BLOCKER_CANDIDATE_CONTRACT,
                "nextRecommendedNextLever": NEXT_CONTRACT_FIX,
            },
            {
                "condition": "pipeline_guardrail_regression",
                "selected": primary_blocker == BLOCKER_GUARDRAIL,
                "nextRecommendedNextLever": NEXT_PIPELINE_REPAIR,
            },
            {
                "condition": "source_robustness_regeneration_failed",
                "selected": primary_blocker == BLOCKER_SOURCE_REGENERATION,
                "nextRecommendedNextLever": NEXT_SOURCE_DEBUG,
            },
            {
                "condition": "registry_contract_gap",
                "selected": primary_blocker == BLOCKER_REGISTRY,
                "nextRecommendedNextLever": NEXT_CONTRACT_FIX,
            },
            {
                "condition": "runtime_default_mutation_executed",
                "selected": mutation_executed,
                "nextRecommendedNextLever": NEXT_POST_MUTATION,
            },
        ],
    }

    _write_json(output_root / "runtime_default_change_summary.json", summary)
    _write_json(output_root / "runtime_default_candidate_contract_audit.json", candidate_contract)
    _write_json(output_root / "runtime_default_guardrail_audit.json", pipeline_guardrail)
    _write_json(output_root / "runtime_default_source_robustness_regeneration_audit.json", source_regeneration)
    _write_json(output_root / "runtime_default_registry_contract_audit.json", registry)
    _write_json(output_root / "runtime_default_registry_mutation_audit.json", mutation_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "candidateContractAudit": candidate_contract,
            "pipelineGuardrailAudit": pipeline_guardrail,
            "sourceRobustnessRegenerationAudit": source_regeneration,
            "registryContractAudit": registry,
            "registryMutationAudit": mutation_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and execute the v7.3 runtime-default mutation gate.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="runtime_default_candidate_contract_validation")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_3_runtime_default_change_validation(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
