from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "promoted_v7_2_source_robustness_validation_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"

BLOCKER_REGISTRY = "v7_2_runtime_registry_contract_gap"
BLOCKER_PROMOTION_TRUTH = "v7_2_promotion_readiness_truth_missing"
BLOCKER_SOURCE = "v7_2_source_robustness_default_mutation_blocked"

NEXT_REGISTRY_FIX = "v7_2_runtime_registry_contract_fix"
NEXT_MANUAL = "manual_review_required"
NEXT_BLOCKER_ANALYSIS = "v7_2_source_robustness_default_blocker_analysis"
NEXT_DEFAULT_CHANGE = "v7_2_runtime_default_change_validation"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "promoted_v7_2_controlled_source_robustness_validation",
            "successCriteria": [
                "controlled runtime registry points to touchline_detector_candidate_v7 / v7.2",
                "v7.2 promotion-readiness truth is valid",
                "source-robustness truth is read and default-mutation blockers are named",
            ],
            "failureAdaptation": "If registry or suite route truth is stale, move to v7_2_source_robustness_route_repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "v7_2_source_robustness_route_repair",
            "successCriteria": [
                "route mismatch diagnostics are written",
                "v7.2 controlled-promotion truth remains authoritative",
                "runtime default mutation is not executed",
            ],
            "failureAdaptation": "If source blockers remain, stop with default blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "v7_2_runtime_default_blocker_summary",
            "successCriteria": [
                "blocker summary written",
                "exactly one next corrective family selected",
                "runtime-default mutation remains unexecuted",
            ],
            "failureAdaptation": "Stop after blocker summary; do not force a runtime-default switch.",
        },
    ]


def _source_blockers(suite_summary: dict[str, Any] | None) -> list[str]:
    if suite_summary is None:
        return ["source_robustness_truth_missing"]
    for key in ("sourceRobustnessPromotionBlockers", "promotionBlockers"):
        value = suite_summary.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
    return ["source_robustness_promotion_blockers_missing"]


def _registry_audit(registry: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "registryExists": isinstance(registry, dict),
        "trainingCandidateName": registry.get("trainingCandidateName") if isinstance(registry, dict) else None,
        "trainingCandidateVersion": registry.get("trainingCandidateVersion") if isinstance(registry, dict) else None,
        "promotionValidated": bool(registry.get("promotionValidated")) if isinstance(registry, dict) else False,
        "promotedForControlledRuns": bool(registry.get("promotedForControlledRuns")) if isinstance(registry, dict) else False,
        "runtimeDefaultMutationExecuted": bool(registry.get("runtimeDefaultMutationExecuted"))
        if isinstance(registry, dict)
        else False,
        "registryPointsToV7_2": bool(
            isinstance(registry, dict)
            and registry.get("trainingCandidateName") == DEFAULT_CANDIDATE_NAME
            and registry.get("trainingCandidateVersion") == "v7.2"
            and registry.get("promotionValidated")
            and registry.get("promotedForControlledRuns")
        ),
    }


def _promotion_audit(readiness: dict[str, Any] | None, suite_readiness: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "candidateReadinessExists": isinstance(readiness, dict),
        "suiteReadinessExists": isinstance(suite_readiness, dict),
        "promotionValidated": bool(readiness.get("promotionValidated")) if isinstance(readiness, dict) else False,
        "promotionReady": bool(readiness.get("promotionReady")) if isinstance(readiness, dict) else False,
        "candidateReadyForEvaluation": bool(readiness.get("candidateReadyForEvaluation"))
        if isinstance(readiness, dict)
        else False,
        "suitePromotionReady": bool(suite_readiness.get("promotionReady")) if isinstance(suite_readiness, dict) else False,
        "promotionTruthValid": bool(
            isinstance(readiness, dict)
            and readiness.get("promotionValidated")
            and readiness.get("promotionReady")
            and readiness.get("candidateReadyForEvaluation")
            and isinstance(suite_readiness, dict)
            and suite_readiness.get("promotionReady")
        ),
    }


def _source_audit(suite_summary: dict[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    passed_source_gate = bool(suite_summary and suite_summary.get("passedPromotionGate"))
    return {
        "suiteSummaryExists": isinstance(suite_summary, dict),
        "suiteVerdict": suite_summary.get("suiteVerdict") if isinstance(suite_summary, dict) else None,
        "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome")
        if isinstance(suite_summary, dict)
        else None,
        "sourceRobustnessDominantFailureSignal": suite_summary.get("sourceRobustnessDominantFailureSignal")
        if isinstance(suite_summary, dict)
        else None,
        "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever")
        if isinstance(suite_summary, dict)
        else None,
        "passedPromotionGate": passed_source_gate,
        "runtimeDefaultMutationBlockers": blockers,
        "runtimeDefaultMutationReady": passed_source_gate and not blockers,
        "routeMismatchDetected": bool(
            isinstance(suite_summary, dict)
            and suite_summary.get("sourceRobustnessRecommendedNextLever") == "evaluate_touchline_detector_candidate"
            and blockers
        ),
    }


def _classify(
    *,
    registry_audit: dict[str, Any],
    promotion_audit: dict[str, Any],
    source_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not promotion_audit["promotionTruthValid"]:
        return (
            BLOCKER_PROMOTION_TRUTH,
            NEXT_MANUAL,
            False,
            "v7.2 promotion-readiness truth is missing or no longer valid.",
        )
    if not registry_audit["registryPointsToV7_2"]:
        return (
            BLOCKER_REGISTRY,
            NEXT_REGISTRY_FIX,
            False,
            "Controlled runtime registry does not point to the v7.2 promoted candidate.",
        )
    if not source_audit["runtimeDefaultMutationReady"]:
        return (
            BLOCKER_SOURCE,
            NEXT_BLOCKER_ANALYSIS,
            False,
            "v7.2 remains controlled-promotion valid, but source robustness still blocks runtime-default mutation.",
        )
    return (
        None,
        NEXT_DEFAULT_CHANGE,
        True,
        "v7.2 controlled promotion remains valid and source robustness no longer blocks runtime-default validation.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Promoted V7.2 Source Robustness Validation",
        "",
        f"- Validation completed: `{summary.get('validationCompleted')}`",
        f"- Goal achieved: `{summary.get('goalAchieved')}`",
        f"- Primary blocker: `{summary.get('primaryBlocker')}`",
        f"- Controlled promotion valid: `{summary.get('controlledPromotionValid')}`",
        f"- Runtime default mutation ready: `{summary.get('runtimeDefaultMutationReady')}`",
        f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
        f"- Runtime default mutation blockers: `{summary.get('runtimeDefaultMutationBlockers')}`",
        f"- Next: `{summary.get('nextRecommendedNextLever')}`",
        "",
        str(summary.get("englishDecision") or ""),
        "",
    ]
    return "\n".join(lines)


def run_promoted_v7_2_source_robustness_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "promoted_v7_2_controlled_source_robustness_validation",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    readiness = _load_json(
        _candidate_root(storage_root)
        / "v7_2_promotion_readiness_validation_v1"
        / "v7_2_promotion_readiness_summary.json"
    )
    suite_readiness = _load_json(suite_root / "v7_2_detector_candidate_promotion_readiness.json")
    registry = _load_json(storage_root / "runtime" / "promoted_touchline_detector_candidate.json")
    suite_summary = _load_json(suite_root / "suite_summary.json")
    blockers = _source_blockers(suite_summary)

    attempts = _attempt_plan()
    registry_check = _registry_audit(registry)
    promotion_check = _promotion_audit(readiness, suite_readiness)
    source_check = _source_audit(suite_summary, blockers)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        registry_audit=registry_check,
        promotion_audit=promotion_check,
        source_audit=source_check,
    )
    controlled_promotion_valid = bool(registry_check["registryPointsToV7_2"] and promotion_check["promotionTruthValid"])
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "promoted_v7_2_source_robustness_validation",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in attempts],
        "generatedAt": generated_at,
        "validationCompleted": True,
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "controlledPromotionValid": controlled_promotion_valid,
        "runtimeDefaultMutationReady": bool(source_check["runtimeDefaultMutationReady"] and controlled_promotion_valid),
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": blockers,
        "sourceRobustnessOutcome": source_check["sourceRobustnessOutcome"],
        "sourceRobustnessDominantFailureSignal": source_check["sourceRobustnessDominantFailureSignal"],
        "sourceRobustnessRecommendedNextLever": source_check["sourceRobustnessRecommendedNextLever"],
        "sourceRobustnessRouteMismatchDetected": source_check["routeMismatchDetected"],
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    runtime_default_blocker_audit = {
        "generatedAt": generated_at,
        "runtimeDefaultMutationReady": summary["runtimeDefaultMutationReady"],
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": blockers,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
    }
    _write_json(output_root / "promoted_v7_2_source_robustness_validation_summary.json", summary)
    _write_json(output_root / "controlled_registry_audit.json", registry_check)
    _write_json(
        output_root / "source_robustness_gate_audit.json",
        {
            "promotionAudit": promotion_check,
            "sourceAudit": source_check,
            "suiteSummary": suite_summary or {},
        },
    )
    _write_json(output_root / "runtime_default_blocker_audit.json", runtime_default_blocker_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": generated_at, "summary": summary, "attempts": attempts})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "controlledRegistryAudit": registry_check,
            "sourceRobustnessGateAudit": source_check,
            "runtimeDefaultBlockerAudit": runtime_default_blocker_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate promoted v7.2 against source robustness/default mutation gates.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="promoted_v7_2_controlled_source_robustness_validation",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_promoted_v7_2_source_robustness_validation(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
