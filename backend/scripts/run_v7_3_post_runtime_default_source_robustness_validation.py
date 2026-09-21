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
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_CHANGE_DIR_NAME = "v7_3_runtime_default_change_validation_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_post_runtime_default_source_robustness_validation_v1"

BLOCKER_SOURCE_TRUTH_MISSING = "v7_3_post_default_source_truth_missing"
BLOCKER_REGISTRY = "v7_3_post_default_registry_contract_gap"
BLOCKER_FAILING_SOURCE_RESURRECTED = "v7_3_post_default_failing_source_not_viable_resurrected"
BLOCKER_SOURCE_REGRESSION = "v7_3_post_default_source_robustness_regression"

NEXT_SOURCE_REGENERATION = "v7_3_post_default_source_robustness_regeneration"
NEXT_REGISTRY_REPAIR = "v7_3_post_default_registry_contract_repair"
NEXT_SOURCE_DEBUG = "v7_3_post_default_source_robustness_regression_debug"
NEXT_CLOSEOUT = "v7_3_runtime_default_rollout_closeout"


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _runtime_registry_path(storage_root: Path) -> Path:
    return Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json"


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "post_default_source_robustness_validation",
            "successCriteria": [
                "active runtime registry points to touchline_detector_candidate_v7 / v7.3",
                "runtimeUse is default_runtime",
                "post-mutation source-robustness artifact has no failing_source_not_viable blocker",
            ],
            "failureAdaptation": "If source truth is missing, regenerate post-default source robustness from the active runtime default.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "post_default_registry_contract_repair",
            "successCriteria": [
                "repair stale or incomplete runtime registry metadata",
                "do not change detector weights or train",
                "rerun post-default validation from registry truth",
            ],
            "failureAdaptation": "If registry is current but the source gate regressed, route to source-robustness regression debug.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "post_default_blocker_summary",
            "successCriteria": [
                "write exactly one blocker or close out the runtime-default rollout",
                "keep training and promotion mutation unexecuted",
            ],
            "failureAdaptation": "Stop with blocker truth if the old source blocker returns.",
        },
    ]


def _list_blockers(*payloads: dict[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in (
            "runtimeDefaultMutationBlockers",
            "runtimeDefaultChangeBlockers",
            "sourceRobustnessPromotionBlockers",
            "promotionBlockers",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                blockers.extend(str(item) for item in value if str(item).strip())
    return blockers


def _registry_audit(registry: dict[str, Any] | None) -> dict[str, Any]:
    blockers = _list_blockers(registry)
    checks = {
        "registryExists": isinstance(registry, dict),
        "registryPointsToV7_3": bool(
            isinstance(registry, dict)
            and registry.get("trainingCandidateName") == DEFAULT_CANDIDATE_NAME
            and registry.get("trainingCandidateVersion") == "v7.3"
        ),
        "promotionValidated": bool(isinstance(registry, dict) and registry.get("promotionValidated")),
        "promotedForControlledRuns": bool(isinstance(registry, dict) and registry.get("promotedForControlledRuns")),
        "runtimeUseDefault": bool(isinstance(registry, dict) and registry.get("runtimeUse") == "default_runtime"),
        "runtimeDefaultChanged": bool(isinstance(registry, dict) and registry.get("runtimeDefaultChanged")),
        "runtimeDefaultMutationExecuted": bool(
            isinstance(registry, dict) and registry.get("runtimeDefaultMutationExecuted")
        ),
        "runtimeDefaultBlockersClear": not blockers,
    }
    return {
        "checks": checks,
        "activeRuntimeDefaultRegistryPassed": all(checks.values()),
        "activeRuntimeDefaultBlockers": blockers,
        "registry": registry or {},
    }


def _source_truth_audit(
    *,
    change_summary: dict[str, Any] | None,
    source_regeneration: dict[str, Any] | None,
    mutation_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers = _list_blockers(change_summary, source_regeneration)
    checks = {
        "changeSummaryExists": isinstance(change_summary, dict),
        "sourceRegenerationAuditExists": isinstance(source_regeneration, dict),
        "mutationAuditExists": isinstance(mutation_audit, dict),
        "changeGoalAchieved": bool((change_summary or {}).get("goalAchieved")),
        "changePrimaryBlockerClear": (change_summary or {}).get("primaryBlocker") is None,
        "sourceGatePassed": bool((change_summary or {}).get("sourceRobustnessDefaultChangeGatePassed")),
        "changeMutationExecuted": bool((change_summary or {}).get("runtimeDefaultMutationExecuted")),
        "changeTrainingNotExecuted": not bool((change_summary or {}).get("trainingExecuted")),
        "changePromotionMutationNotExecuted": not bool((change_summary or {}).get("promotionMutationExecuted")),
        "sourceRegenerationPassed": bool((source_regeneration or {}).get("sourceRobustnessRegenerationPassed")),
        "sourceRegenerationNoBlockers": not _list_blockers(source_regeneration),
        "mutationAuditExecuted": bool((mutation_audit or {}).get("runtimeDefaultMutationExecuted")),
    }
    return {
        "checks": checks,
        "postMutationSourceTruthPresent": all(
            checks[key]
            for key in ("changeSummaryExists", "sourceRegenerationAuditExists", "mutationAuditExists")
        ),
        "postMutationSourceRobustnessPassed": all(checks.values()),
        "postMutationSourceBlockers": blockers,
        "sourceRobustnessOutcome": (change_summary or {}).get("sourceRobustnessOutcome")
        or (source_regeneration or {}).get("regeneratedSourceRobustnessOutcome"),
    }


def _legacy_suite_audit(suite_summary: dict[str, Any] | None) -> dict[str, Any]:
    blockers = _list_blockers(suite_summary)
    return {
        "suiteSummaryExists": isinstance(suite_summary, dict),
        "legacySuiteBlockers": blockers,
        "legacySuiteBlockerStillPresent": "failing_source_not_viable" in blockers,
        "legacySuiteSummaryUsedAsPostMutationTruth": False,
    }


def _classify(
    *,
    registry_audit: dict[str, Any],
    source_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    blockers = set(source_audit["postMutationSourceBlockers"])
    if "failing_source_not_viable" in blockers:
        return (
            BLOCKER_FAILING_SOURCE_RESURRECTED,
            NEXT_SOURCE_DEBUG,
            False,
            "The old failing_source_not_viable blocker returned in post-default source truth.",
        )
    if not registry_audit["activeRuntimeDefaultRegistryPassed"]:
        return (
            BLOCKER_REGISTRY,
            NEXT_REGISTRY_REPAIR,
            False,
            "The active runtime registry is not a validated v7.3 default-runtime entry.",
        )
    if not source_audit["postMutationSourceTruthPresent"]:
        return (
            BLOCKER_SOURCE_TRUTH_MISSING,
            NEXT_SOURCE_REGENERATION,
            False,
            "Post-default source-robustness truth is missing; regenerate from the active runtime default.",
        )
    if not source_audit["postMutationSourceRobustnessPassed"] or blockers:
        return (
            BLOCKER_SOURCE_REGRESSION,
            NEXT_SOURCE_DEBUG,
            False,
            "Post-default source-robustness truth regressed after the runtime-default mutation.",
        )
    return (
        None,
        NEXT_CLOSEOUT,
        True,
        "The active v7.3 runtime default preserves source robustness and the old failing_source_not_viable blocker remains cleared.",
    )


def _registry_after_validation(registry: dict[str, Any], summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    updated = dict(registry)
    updated.update(
        {
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "postRuntimeDefaultSourceRobustnessValidationBatchName": "v7_3_post_runtime_default_source_robustness_validation",
            "postRuntimeDefaultSourceRobustnessValidatedAt": summary["generatedAt"],
            "failingSourceNotViableBlockerPresent": False,
            "sourceRobustnessOutcome": summary["sourceRobustnessOutcome"],
            "nextRecommendedNextLever": summary["nextRecommendedNextLever"],
            "postRuntimeDefaultEvidence": {
                "summaryPath": str(output_root / "post_runtime_default_source_robustness_summary.json"),
                "registryAuditPath": str(output_root / "active_runtime_default_registry_audit.json"),
                "sourceGateAuditPath": str(output_root / "post_mutation_source_robustness_gate_audit.json"),
            },
        }
    )
    return updated


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Post Runtime Default Source Robustness Validation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Post-default source robustness validated: `{summary.get('postRuntimeDefaultSourceRobustnessValidated')}`",
            f"- Failing source blocker present: `{summary.get('failingSourceNotViableBlockerPresent')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_post_runtime_default_source_robustness_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "post_default_source_robustness_validation",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    change_root = suite_root / DEFAULT_CHANGE_DIR_NAME
    registry_payload = _load_json(_runtime_registry_path(storage_root))
    change_summary = _load_json(change_root / "runtime_default_change_summary.json")
    source_regeneration = _load_json(change_root / "runtime_default_source_robustness_regeneration_audit.json")
    mutation_audit = _load_json(change_root / "runtime_default_registry_mutation_audit.json")
    suite_summary = _load_json(suite_root / "suite_summary.json")

    registry_audit = _registry_audit(registry_payload)
    source_audit = _source_truth_audit(
        change_summary=change_summary,
        source_regeneration=source_regeneration,
        mutation_audit=mutation_audit,
    )
    legacy_audit = _legacy_suite_audit(suite_summary)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        registry_audit=registry_audit,
        source_audit=source_audit,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    blockers = list(registry_audit["activeRuntimeDefaultBlockers"]) + list(source_audit["postMutationSourceBlockers"])
    failing_source_present = "failing_source_not_viable" in set(blockers)
    summary: dict[str, Any] = {
        "batchName": "v7_3_post_runtime_default_source_robustness_validation",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "runtimeDefaultChanged": bool((registry_payload or {}).get("runtimeDefaultChanged")),
        "runtimeDefaultMutationExecuted": bool((registry_payload or {}).get("runtimeDefaultMutationExecuted")),
        "postRuntimeDefaultSourceRobustnessValidated": goal_achieved,
        "failingSourceNotViableBlockerPresent": failing_source_present,
        "runtimeDefaultMutationBlockers": blockers,
        "legacySuiteBlockerStillPresent": legacy_audit["legacySuiteBlockerStillPresent"],
        "sourceRobustnessOutcome": source_audit["sourceRobustnessOutcome"],
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationAllowed": False,
        "promotionMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    registry_after = registry_audit["registry"]
    if goal_achieved:
        registry_after = _registry_after_validation(registry_audit["registry"], summary, output_root)
        _write_json(_runtime_registry_path(storage_root), registry_after)

    resurrection_audit = {
        "generatedAt": generated_at,
        "failingSourceNotViableBlockerPresent": failing_source_present,
        "activeRuntimeDefaultBlockers": registry_audit["activeRuntimeDefaultBlockers"],
        "postMutationSourceBlockers": source_audit["postMutationSourceBlockers"],
        "legacySuiteBlockerStillPresent": legacy_audit["legacySuiteBlockerStillPresent"],
        "legacySuiteSummaryUsedAsPostMutationTruth": False,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {
                "condition": "active_runtime_registry_contract_gap",
                "selected": primary_blocker == BLOCKER_REGISTRY,
                "nextRecommendedNextLever": NEXT_REGISTRY_REPAIR,
            },
            {
                "condition": "post_default_source_truth_missing",
                "selected": primary_blocker == BLOCKER_SOURCE_TRUTH_MISSING,
                "nextRecommendedNextLever": NEXT_SOURCE_REGENERATION,
            },
            {
                "condition": "failing_source_not_viable_resurrected",
                "selected": primary_blocker == BLOCKER_FAILING_SOURCE_RESURRECTED,
                "nextRecommendedNextLever": NEXT_SOURCE_DEBUG,
            },
            {
                "condition": "post_default_source_robustness_regression",
                "selected": primary_blocker == BLOCKER_SOURCE_REGRESSION,
                "nextRecommendedNextLever": NEXT_SOURCE_DEBUG,
            },
            {
                "condition": "post_default_source_robustness_validated",
                "selected": goal_achieved,
                "nextRecommendedNextLever": NEXT_CLOSEOUT,
            },
        ],
    }

    _write_json(output_root / "post_runtime_default_source_robustness_summary.json", summary)
    _write_json(output_root / "active_runtime_default_registry_audit.json", registry_audit)
    _write_json(output_root / "post_mutation_source_robustness_gate_audit.json", source_audit)
    _write_json(output_root / "runtime_registry_post_validation_audit.json", {"registryBefore": registry_audit["registry"], "registryAfter": registry_after})
    _write_json(output_root / "failing_source_blocker_resurrection_audit.json", resurrection_audit)
    _write_json(output_root / "legacy_suite_summary_audit.json", legacy_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "registryAudit": registry_audit,
            "sourceGateAudit": source_audit,
            "resurrectionAudit": resurrection_audit,
            "legacySuiteAudit": legacy_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate source robustness after the v7.3 runtime-default mutation."
    )
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="post_default_source_robustness_validation")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_3_post_runtime_default_source_robustness_validation(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
