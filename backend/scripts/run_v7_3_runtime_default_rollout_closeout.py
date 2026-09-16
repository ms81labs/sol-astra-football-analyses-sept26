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
DEFAULT_OUTPUT_DIR_NAME = "v7_3_runtime_default_rollout_closeout_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"

PROMOTION_DIR_NAME = "v7_3_promotion_readiness_validation_v1"
CHANGE_DIR_NAME = "v7_3_runtime_default_change_validation_v1"
POST_VALIDATION_DIR_NAME = "v7_3_post_runtime_default_source_robustness_validation_v1"

NEXT_RELEASE_CLOSEOUT = "video_to_analysis_release_candidate_closeout"
NEXT_POST_VALIDATION = "v7_3_post_runtime_default_source_robustness_validation"
NEXT_CONTRACT_REPAIR = "v7_3_runtime_default_rollout_contract_repair"

BLOCKER_POST_VALIDATION_MISSING = "v7_3_rollout_closeout_post_validation_missing"
BLOCKER_REGISTRY_DRIFT = "v7_3_rollout_closeout_registry_contract_drift"
BLOCKER_STATUS_DRIFT = "v7_3_rollout_closeout_unattended_status_drift"
BLOCKER_ARTIFACT_CHAIN = "v7_3_rollout_closeout_artifact_chain_gap"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _candidate_root(storage_root: Path) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME


def _runtime_registry_path(storage_root: Path) -> Path:
    return Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json"


def _automation_status_path(storage_root: Path) -> Path:
    return Path(storage_root) / "automation" / "unattended_roadmap_loop_status.json"


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "runtime_default_rollout_artifact_closeout",
            "successCriteria": [
                "promotion readiness, runtime-default mutation, and post-default validation artifacts are present",
                "active runtime registry still points at the v7.3 default contract",
                "legacy suite blocker is archived but not active",
            ],
            "failureAdaptation": "If artifacts or status drift, repair only metadata contracts and rerun closeout.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "runtime_default_rollout_contract_repair",
            "successCriteria": [
                "repair registry/status closeout pointers without changing detector behavior",
                "preserve the validated v7.3 runtime default",
                "do not train or mutate promotion state",
            ],
            "failureAdaptation": "If repaired metadata still conflicts with generated truth, stop with blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "runtime_default_rollout_blocker_summary",
            "successCriteria": [
                "write exactly one blocker family",
                "keep historical and active source-robustness truth separated",
            ],
            "failureAdaptation": "Route to the smallest corrective family instead of changing runtime defaults again.",
        },
    ]


def _list_blockers(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    blockers: list[str] = []
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


def _artifact_inventory(storage_root: Path, suite_root: Path) -> dict[str, Any]:
    artifacts = [
        {
            "artifactName": "v7_3_promotion_readiness_summary",
            "path": _candidate_root(storage_root) / PROMOTION_DIR_NAME / "v7_3_promotion_readiness_summary.json",
            "required": True,
        },
        {
            "artifactName": "runtime_default_change_summary",
            "path": suite_root / CHANGE_DIR_NAME / "runtime_default_change_summary.json",
            "required": True,
        },
        {
            "artifactName": "post_runtime_default_source_robustness_summary",
            "path": suite_root / POST_VALIDATION_DIR_NAME / "post_runtime_default_source_robustness_summary.json",
            "required": True,
        },
    ]
    rows: list[dict[str, Any]] = []
    for item in artifacts:
        path = item["path"]
        payload = _load_json(path)
        rows.append(
            {
                "artifactName": item["artifactName"],
                "path": str(path),
                "required": item["required"],
                "exists": path.exists(),
                "goalAchieved": (payload or {}).get("goalAchieved"),
                "primaryBlocker": (payload or {}).get("primaryBlocker"),
                "nextRecommendedNextLever": (payload or {}).get("nextRecommendedNextLever"),
            }
        )
    missing = [row["artifactName"] for row in rows if row["required"] and not row["exists"]]
    return {
        "artifacts": rows,
        "requiredArtifactCount": len([row for row in rows if row["required"]]),
        "missingRequiredArtifacts": missing,
        "artifactChainComplete": not missing,
    }


def _registry_audit(registry: dict[str, Any] | None) -> dict[str, Any]:
    checks = {
        "registryExists": isinstance(registry, dict),
        "registryPointsToV7_3": bool(
            isinstance(registry, dict)
            and registry.get("trainingCandidateName") == DEFAULT_CANDIDATE_NAME
            and registry.get("trainingCandidateVersion") == "v7.3"
        ),
        "runtimeUseDefault": bool(isinstance(registry, dict) and registry.get("runtimeUse") == "default_runtime"),
        "runtimeDefaultMutationExecuted": bool(
            isinstance(registry, dict) and registry.get("runtimeDefaultMutationExecuted")
        ),
        "postDefaultValidated": bool(
            isinstance(registry, dict) and registry.get("postRuntimeDefaultSourceRobustnessValidated")
        ),
        "failingSourceCleared": bool(
            isinstance(registry, dict) and registry.get("failingSourceNotViableBlockerPresent") is False
        ),
        "closeoutIsNext": bool(
            isinstance(registry, dict) and registry.get("nextRecommendedNextLever") == "v7_3_runtime_default_rollout_closeout"
        ),
    }
    return {
        "checks": checks,
        "registryCloseoutContractPassed": all(checks.values()),
        "registry": registry or {},
    }


def _post_validation_audit(post_summary: dict[str, Any] | None) -> dict[str, Any]:
    checks = {
        "postSummaryExists": isinstance(post_summary, dict),
        "postGoalAchieved": bool((post_summary or {}).get("goalAchieved")),
        "postPrimaryBlockerClear": (post_summary or {}).get("primaryBlocker") is None,
        "postDefaultValidated": bool((post_summary or {}).get("postRuntimeDefaultSourceRobustnessValidated")),
        "failingSourceCleared": (post_summary or {}).get("failingSourceNotViableBlockerPresent") is False,
        "postNextIsCloseout": (post_summary or {}).get("nextRecommendedNextLever")
        == "v7_3_runtime_default_rollout_closeout",
    }
    return {
        "checks": checks,
        "postDefaultValidationPassed": all(checks.values()),
        "postSummary": post_summary or {},
    }


def _unattended_status_audit(status: dict[str, Any] | None) -> dict[str, Any]:
    text = json.dumps(status or {}, sort_keys=True)
    checks = {
        "statusExists": isinstance(status, dict),
        "postValidationBatchRecorded": bool(
            isinstance(status, dict)
            and status.get("activeBatchName") == "v7_3_post_runtime_default_source_robustness_validation"
        ),
        "closeoutMentioned": "v7_3_runtime_default_rollout_closeout" in text,
    }
    return {
        "checks": checks,
        "unattendedStatusCloseoutReady": all(checks.values()),
        "status": status or {},
    }


def _historical_suite_audit(suite_summary: dict[str, Any] | None) -> dict[str, Any]:
    blockers = _list_blockers(suite_summary)
    return {
        "suiteSummaryExists": isinstance(suite_summary, dict),
        "legacySuiteBlockers": blockers,
        "legacySuiteBlockerStillPresent": "failing_source_not_viable" in blockers,
        "historicalSuiteBlockerArchived": "failing_source_not_viable" in blockers,
        "legacySuiteSummaryUsedAsActivePostDefaultTruth": False,
    }


def _classify(
    *,
    artifact_inventory: dict[str, Any],
    registry_audit: dict[str, Any],
    post_audit: dict[str, Any],
    status_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not post_audit["postDefaultValidationPassed"]:
        return (
            BLOCKER_POST_VALIDATION_MISSING,
            NEXT_POST_VALIDATION,
            False,
            "Post-default source-robustness validation is missing or did not pass; rerun that gate first.",
        )
    if not artifact_inventory["artifactChainComplete"]:
        return (
            BLOCKER_ARTIFACT_CHAIN,
            NEXT_CONTRACT_REPAIR,
            False,
            "Runtime-default rollout closeout cannot complete because required rollout artifacts are missing.",
        )
    if not registry_audit["registryCloseoutContractPassed"]:
        return (
            BLOCKER_REGISTRY_DRIFT,
            NEXT_CONTRACT_REPAIR,
            False,
            "Runtime registry does not point at the validated v7.3 closeout-ready default contract.",
        )
    if not status_audit["unattendedStatusCloseoutReady"]:
        return (
            BLOCKER_STATUS_DRIFT,
            NEXT_CONTRACT_REPAIR,
            False,
            "Unattended roadmap status is not aligned with the runtime-default rollout closeout state.",
        )
    return (
        None,
        NEXT_RELEASE_CLOSEOUT,
        True,
        "Runtime-default rollout is closed out: active v7.3 default truth is viable, and the old failing-source blocker is archival only.",
    )


def _registry_after_closeout(registry: dict[str, Any], summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    updated = dict(registry)
    updated.update(
        {
            "runtimeDefaultRolloutCloseoutCompleted": True,
            "runtimeDefaultRolloutCloseoutBatchName": "v7_3_runtime_default_rollout_closeout",
            "runtimeDefaultRolloutCloseoutCompletedAt": summary["generatedAt"],
            "historicalSuiteBlockerArchived": summary["historicalSuiteBlockerArchived"],
            "activeFailingSourceNotViableBlockerPresent": False,
            "nextRecommendedNextLever": summary["nextRecommendedNextLever"],
            "runtimeDefaultRolloutCloseoutEvidence": {
                "summaryPath": str(output_root / "runtime_default_rollout_closeout_summary.json"),
                "artifactInventoryPath": str(output_root / "rollout_artifact_inventory.json"),
                "registryCloseoutAuditPath": str(output_root / "active_runtime_registry_closeout_audit.json"),
            },
        }
    )
    return updated


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Runtime Default Rollout Closeout",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Runtime default rollout closed: `{summary.get('runtimeDefaultRolloutClosed')}`",
            f"- Active failing-source blocker present: `{summary.get('activeFailingSourceNotViableBlockerPresent')}`",
            f"- Historical suite blocker archived: `{summary.get('historicalSuiteBlockerArchived')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_runtime_default_rollout_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "runtime_default_rollout_artifact_closeout",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    post_summary = _load_json(
        suite_root / POST_VALIDATION_DIR_NAME / "post_runtime_default_source_robustness_summary.json"
    )
    registry_payload = _load_json(_runtime_registry_path(storage_root))
    automation_status = _load_json(_automation_status_path(storage_root))
    suite_summary = _load_json(suite_root / "suite_summary.json")

    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    inventory = _artifact_inventory(storage_root, suite_root)
    registry_audit = _registry_audit(registry_payload)
    post_audit = _post_validation_audit(post_summary)
    status_audit = _unattended_status_audit(automation_status)
    historical_audit = _historical_suite_audit(suite_summary)
    primary_blocker, next_lever, goal_achieved, english = _classify(
        artifact_inventory=inventory,
        registry_audit=registry_audit,
        post_audit=post_audit,
        status_audit=status_audit,
    )

    active_failing_source_present = bool(
        registry_audit["registry"].get("failingSourceNotViableBlockerPresent")
        or (post_summary or {}).get("failingSourceNotViableBlockerPresent")
    )
    summary: dict[str, Any] = {
        "batchName": "v7_3_runtime_default_rollout_closeout",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "runtimeDefaultRolloutClosed": goal_achieved,
        "runtimeDefaultMutationExecuted": bool((registry_payload or {}).get("runtimeDefaultMutationExecuted")),
        "runtimeDefaultChanged": bool((registry_payload or {}).get("runtimeDefaultChanged")),
        "postRuntimeDefaultSourceRobustnessValidated": bool(
            (registry_payload or {}).get("postRuntimeDefaultSourceRobustnessValidated")
        ),
        "activeFailingSourceNotViableBlockerPresent": active_failing_source_present,
        "legacySuiteBlockerStillPresent": historical_audit["legacySuiteBlockerStillPresent"],
        "historicalSuiteBlockerArchived": bool(goal_achieved and historical_audit["historicalSuiteBlockerArchived"]),
        "sourceRobustnessOutcome": (post_summary or {}).get("sourceRobustnessOutcome"),
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationAllowed": False,
        "promotionMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    registry_after = registry_audit["registry"]
    if goal_achieved:
        registry_after = _registry_after_closeout(registry_audit["registry"], summary, output_root)
        _write_json(_runtime_registry_path(storage_root), registry_after)

    _write_json(output_root / "runtime_default_rollout_closeout_summary.json", summary)
    _write_json(output_root / "rollout_artifact_inventory.json", inventory)
    _write_json(output_root / "active_runtime_registry_closeout_audit.json", registry_audit)
    _write_json(output_root / "runtime_registry_rollout_closeout_audit.json", {"registryBefore": registry_audit["registry"], "registryAfter": registry_after})
    _write_json(output_root / "unattended_status_closeout_audit.json", status_audit)
    _write_json(output_root / "historical_suite_blocker_audit.json", historical_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(
        output_root / "decision_matrix.json",
        {
            "generatedAt": generated_at,
            "decisions": [
                {
                    "condition": "post_default_validation_missing",
                    "selected": primary_blocker == BLOCKER_POST_VALIDATION_MISSING,
                    "nextRecommendedNextLever": NEXT_POST_VALIDATION,
                },
                {
                    "condition": "runtime_registry_contract_drift",
                    "selected": primary_blocker == BLOCKER_REGISTRY_DRIFT,
                    "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR,
                },
                {
                    "condition": "unattended_status_drift",
                    "selected": primary_blocker == BLOCKER_STATUS_DRIFT,
                    "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR,
                },
                {
                    "condition": "runtime_default_rollout_closed",
                    "selected": goal_achieved,
                    "nextRecommendedNextLever": NEXT_RELEASE_CLOSEOUT,
                },
            ],
        },
    )
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "artifactInventory": inventory,
            "registryCloseoutAudit": registry_audit,
            "postValidationAudit": post_audit,
            "unattendedStatusAudit": status_audit,
            "historicalSuiteAudit": historical_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close out the v7.3 runtime-default rollout.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="runtime_default_rollout_artifact_closeout")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_3_runtime_default_rollout_closeout(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
