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
DEFAULT_OUTPUT_DIR_NAME = "v7_2_runtime_default_change_validation_v1"
DEFAULT_INBOARD_DIR_NAME = "v7_2_default_path_inboard_ball_recovery_v1"

BLOCKER_CANDIDATE_CONTRACT = "v7_2_runtime_default_candidate_contract_gap"
BLOCKER_GUARDRAIL = "v7_2_runtime_default_guardrail_regression"
BLOCKER_SOURCE_REGENERATION = "v7_2_runtime_default_source_robustness_regeneration_failed"
BLOCKER_REGISTRY = "v7_2_runtime_default_registry_contract_gap"

NEXT_CONTRACT_FIX = "v7_2_runtime_default_contract_fix"
NEXT_PROFILE_REPAIR = "v7_2_inboard_recovery_profile_repair"
NEXT_SOURCE_DEBUG = "v7_2_source_robustness_regression_debug"
NEXT_POST_MUTATION = "v7_2_post_runtime_default_source_robustness_validation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _candidate_root(storage_root: Path) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME


def _runtime_registry_path(storage_root: Path) -> Path:
    return Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json"


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "runtime_default_candidate_contract_validation",
            "successCriteria": [
                "inboard recovery generated truth selected runtime-default validation",
                "controlled recovery profile covers all inboard deficits",
                "runtime registry still points to promoted v7.2 controlled candidate",
            ],
            "failureAdaptation": "If the candidate/default contract is incomplete, keep defaults unchanged and select v7_2_runtime_default_contract_fix.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "runtime_default_source_robustness_regeneration",
            "successCriteria": [
                "regenerated default-candidate truth clears near-viable and viable source-robustness projections",
                "top-left, canary, sampled-frame, projection, and checkpoint guardrails remain clean",
                "runtime default registry mutation is allowed only after regenerated truth clears",
            ],
            "failureAdaptation": "If the source-robustness projection regresses, keep defaults unchanged and select v7_2_source_robustness_regression_debug.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "runtime_default_change_blocker_summary",
            "successCriteria": [
                "write exactly one blocker or execute exactly one validated default mutation",
                "write exactly one next family",
                "training and promotion mutation remain unexecuted",
            ],
            "failureAdaptation": "Stop after blocker summary unless the default-change gate is fully clear.",
        },
    ]


def _candidate_contract_audit(
    *,
    summary: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    regeneration_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = {
        "inboardSummaryExists": isinstance(summary, dict),
        "controlledProfileExists": isinstance(profile, dict),
        "regenerationContractExists": isinstance(regeneration_contract, dict),
        "inboardGoalAchieved": bool((summary or {}).get("goalAchieved")),
        "inboardPrimaryBlockerClear": (summary or {}).get("primaryBlocker") is None,
        "nextLeverIsRuntimeDefaultValidation": (summary or {}).get("nextRecommendedNextLever")
        == "v7_2_runtime_default_change_validation",
        "runtimeDefaultReady": bool((summary or {}).get("runtimeDefaultMutationReady")),
        "runtimeDefaultNotAlreadyMutated": not bool((summary or {}).get("runtimeDefaultMutationExecuted")),
        "trainingNotExecuted": not bool((summary or {}).get("trainingExecuted")),
        "promotionMutationNotExecuted": not bool((summary or {}).get("promotionMutationExecuted")),
        "profileNamePresent": bool((profile or {}).get("controlledRecoveryProfileName")),
        "candidateFrameCountPositive": int((profile or {}).get("candidateFrameCount") or 0) > 0,
        "sliceProfilesPresent": bool((profile or {}).get("sliceProfiles")),
        "nearViableDeficitsCovered": bool((profile or {}).get("allSliceNearViableDeficitsCovered")),
        "viableDeficitsCovered": bool((profile or {}).get("allSliceViableDeficitsCovered")),
        "nearViableProjectionClears": bool((profile or {}).get("allSliceProjectedNearViableEdgeShareClearsGate")),
        "contractRequestsRegeneration": bool((regeneration_contract or {}).get("shouldRegenerateSourceRobustness")),
        "contractRuntimeReady": bool((regeneration_contract or {}).get("runtimeDefaultMutationReady")),
        "contractNotAlreadyMutated": not bool((regeneration_contract or {}).get("runtimeDefaultMutationExecuted")),
    }
    return {
        "checks": checks,
        "candidateContractPassed": all(checks.values()),
        "controlledRecoveryProfileName": (profile or {}).get("controlledRecoveryProfileName"),
        "safeInboardCandidateFrameCount": (summary or {}).get("safeInboardCandidateFrameCount"),
        "sliceCount": (summary or {}).get("sliceCount"),
    }


def _guardrail_contract_audit(guardrail: dict[str, Any] | None) -> dict[str, Any]:
    checks = dict(guardrail.get("checks") or {}) if isinstance(guardrail, dict) else {}
    return {
        "guardrailArtifactExists": isinstance(guardrail, dict),
        "requiredInputsPresent": bool((guardrail or {}).get("requiredInputsPresent")),
        "guardrailsPassed": bool((guardrail or {}).get("guardrailsPassed")),
        "checks": checks,
        "guardrailContractPassed": bool(
            isinstance(guardrail, dict)
            and guardrail.get("requiredInputsPresent")
            and guardrail.get("guardrailsPassed")
        ),
    }


def _source_regeneration_audit(profile: dict[str, Any] | None, candidate_contract: dict[str, Any], guardrail: dict[str, Any]) -> dict[str, Any]:
    profile = profile or {}
    slice_profiles = profile.get("sliceProfiles") if isinstance(profile.get("sliceProfiles"), list) else []
    checks = {
        "candidateContractPassed": bool(candidate_contract["candidateContractPassed"]),
        "guardrailContractPassed": bool(guardrail["guardrailContractPassed"]),
        "sliceProfilesPresent": bool(slice_profiles),
        "allNearViableDeficitsCovered": bool(profile.get("allSliceNearViableDeficitsCovered")),
        "allViableDeficitsCovered": bool(profile.get("allSliceViableDeficitsCovered")),
        "allNearViableEdgeShareClears": bool(profile.get("allSliceProjectedNearViableEdgeShareClearsGate")),
        "allViableEdgeShareClears": bool(profile.get("allSliceProjectedViableEdgeShareClearsGate")),
        "everySliceHasViableSelection": all(
            bool(row.get("selectedViableCandidateFrameIds")) or int(row.get("viableAdditionalInboardFramesNeeded") or 0) == 0
            for row in slice_profiles
            if isinstance(row, dict)
        ),
    }
    passed = all(checks.values())
    return {
        "checks": checks,
        "sourceRobustnessRegenerationPassed": passed,
        "regeneratedSourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery"
        if passed
        else "source_robustness_regeneration_failed",
        "runtimeDefaultMutationReady": passed,
        "runtimeDefaultMutationBlockers": [] if passed else ["runtime_default_source_robustness_regeneration_failed"],
    }


def _registry_audit(
    *,
    registry: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    suite_readiness: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime_contract = registry.get("runtimeContract") if isinstance(registry, dict) else None
    checks = {
        "registryExists": isinstance(registry, dict),
        "registryPointsToV7_2": bool(
            isinstance(registry, dict)
            and registry.get("trainingCandidateName") == DEFAULT_CANDIDATE_NAME
            and registry.get("trainingCandidateVersion") == "v7.2"
        ),
        "registryPromotionValidated": bool(isinstance(registry, dict) and registry.get("promotionValidated")),
        "registryPromotedForControlledRuns": bool(isinstance(registry, dict) and registry.get("promotedForControlledRuns")),
        "registryDefaultNotAlreadyMutated": not bool(isinstance(registry, dict) and registry.get("runtimeDefaultMutationExecuted")),
        "runtimeContractPresent": isinstance(runtime_contract, dict),
        "runtimeContractVersionV7_2": bool(isinstance(runtime_contract, dict) and runtime_contract.get("trainingCandidateVersion") == "v7.2"),
        "candidateReadinessValid": bool(
            isinstance(readiness, dict)
            and readiness.get("promotionValidated")
            and readiness.get("promotionReady")
            and readiness.get("candidateReadyForEvaluation")
        ),
        "suiteReadinessValid": bool(
            isinstance(suite_readiness, dict)
            and suite_readiness.get("promotionReady")
            and suite_readiness.get("candidateReadyForEvaluation")
        ),
    }
    return {
        "checks": checks,
        "runtimeRegistryContractPassed": all(checks.values()),
        "registryBefore": registry or {},
    }


def _classify(
    *,
    candidate_contract: dict[str, Any],
    guardrail: dict[str, Any],
    source_regeneration: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not candidate_contract["candidateContractPassed"]:
        return (
            BLOCKER_CANDIDATE_CONTRACT,
            NEXT_CONTRACT_FIX,
            False,
            "The inboard recovery truth does not yet provide a complete runtime-default candidate contract.",
        )
    if not guardrail["guardrailContractPassed"]:
        return (
            BLOCKER_GUARDRAIL,
            NEXT_PROFILE_REPAIR,
            False,
            "The runtime-default candidate is blocked by a guardrail regression; defaults remain unchanged.",
        )
    if not source_regeneration["sourceRobustnessRegenerationPassed"]:
        return (
            BLOCKER_SOURCE_REGENERATION,
            NEXT_SOURCE_DEBUG,
            False,
            "The regenerated runtime-default candidate truth does not clear source robustness.",
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
        "Runtime-default candidate validation passed and the default registry was updated to the validated v7.2 inboard recovery profile.",
    )


def _runtime_default_registry_entry(
    *,
    registry_before: dict[str, Any],
    summary: dict[str, Any],
    profile_name: str,
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
            "runtimeDefaultChangeBatchName": "v7_2_runtime_default_change_validation",
            "runtimeDefaultProfileName": profile_name,
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
            "# V7.2 Runtime Default Change Validation",
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


def run_v7_2_runtime_default_change_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "runtime_default_candidate_contract_validation",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    inboard_root = suite_root / DEFAULT_INBOARD_DIR_NAME
    inboard_summary = _load_json(inboard_root / "inboard_ball_recovery_summary.json")
    profile = _load_json(inboard_root / "controlled_recovery_profile_audit.json")
    guardrail_payload = _load_json(inboard_root / "guardrail_audit.json")
    regeneration_contract = _load_json(inboard_root / "source_robustness_regeneration_contract.json")
    registry_payload = _load_json(_runtime_registry_path(storage_root))
    readiness = _load_json(
        _candidate_root(storage_root)
        / "v7_2_promotion_readiness_validation_v1"
        / "v7_2_promotion_readiness_summary.json"
    )
    suite_readiness = _load_json(suite_root / "v7_2_detector_candidate_promotion_readiness.json")

    candidate_contract = _candidate_contract_audit(
        summary=inboard_summary,
        profile=profile,
        regeneration_contract=regeneration_contract,
    )
    guardrail = _guardrail_contract_audit(guardrail_payload)
    source_regeneration = _source_regeneration_audit(profile, candidate_contract, guardrail)
    registry = _registry_audit(registry=registry_payload, readiness=readiness, suite_readiness=suite_readiness)

    primary_blocker, next_lever, mutation_allowed, english = _classify(
        candidate_contract=candidate_contract,
        guardrail=guardrail,
        source_regeneration=source_regeneration,
        registry=registry,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    mutation_executed = primary_blocker is None and mutation_allowed
    source_outcome = source_regeneration["regeneratedSourceRobustnessOutcome"]
    profile_name = str(candidate_contract.get("controlledRecoveryProfileName") or "")
    summary: dict[str, Any] = {
        "batchName": "v7_2_runtime_default_change_validation",
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
        "runtimeDefaultProfileName": profile_name if mutation_executed else None,
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
            profile_name=profile_name,
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
                "condition": "guardrail_regression",
                "selected": primary_blocker == BLOCKER_GUARDRAIL,
                "nextRecommendedNextLever": NEXT_PROFILE_REPAIR,
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
    _write_json(output_root / "runtime_default_guardrail_audit.json", guardrail)
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
            "guardrailAudit": guardrail,
            "sourceRobustnessRegenerationAudit": source_regeneration,
            "registryContractAudit": registry,
            "registryMutationAudit": mutation_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and execute the v7.2 runtime-default mutation gate.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="runtime_default_candidate_contract_validation")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_2_runtime_default_change_validation(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
