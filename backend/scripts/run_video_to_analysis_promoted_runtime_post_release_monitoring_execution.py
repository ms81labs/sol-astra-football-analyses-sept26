from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)
from backend.scripts.video_to_analysis_promoted_runtime_monitoring_common import (  # noqa: E402
    registry_audit,
    route_smoke,
)

DEFAULT_PLAN_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_execution_v1"

BLOCKER_PLAN_MISSING = "video_to_analysis_promoted_runtime_post_release_monitoring_plan_missing"
BLOCKER_HEALTH_FAILED = "video_to_analysis_promoted_runtime_post_release_monitoring_health_failed"
NEXT_PLAN = "video_to_analysis_promoted_runtime_post_release_monitoring_plan"
NEXT_REPAIR = "video_to_analysis_promoted_runtime_monitoring_repair"
NEXT_ROUTE_BINDING = "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_post_release_monitoring_execution",
                "successCriteria": ["registry and five operator-visible routes pass post-release monitoring"],
                "failureAdaptation": "If monitoring plan is missing, route back to monitoring plan.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promoted_runtime_monitoring_repair",
                "successCriteria": ["repair only registry evidence references or route bindings"],
                "failureAdaptation": "If monitoring health still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promoted_runtime_monitoring_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force operational completion.",
            },
        ],
    }


def _plan_ready(summary: dict[str, Any] | None, plan: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotedRuntimePostReleaseMonitoringPlanReady") is True
        and summary.get("monitoringCheckCount") == 6
        and isinstance(plan, dict)
        and len(plan.get("monitoringChecks", [])) == 6
    )


def run_video_to_analysis_promoted_runtime_post_release_monitoring_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    plan_root = root / DEFAULT_PLAN_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    plan_summary = load_json(plan_root / "promoted_runtime_post_release_monitoring_plan_summary.json")
    monitoring_plan = load_json(plan_root / "promoted_runtime_post_release_monitoring_plan.json")
    plan_ready = _plan_ready(plan_summary, monitoring_plan)
    registry = registry_audit(storage_root)
    routes = route_smoke(storage_root) if plan_ready else {
        "operatorVisibleRouteSmokePassed": False,
        "routeSmokePassedCount": 0,
        "routeSmokes": [],
    }
    health_passed = bool(plan_ready and registry["registryMatchesPromotedV7_2DefaultRuntime"] and routes["operatorVisibleRouteSmokePassed"])

    if not plan_ready:
        primary_blocker = BLOCKER_PLAN_MISSING
        next_lever = NEXT_PLAN
        goal = False
        english = "Promoted-runtime monitoring plan is missing or unsafe; build plan before execution."
    elif not health_passed:
        primary_blocker = BLOCKER_HEALTH_FAILED
        next_lever = NEXT_REPAIR
        goal = False
        english = "Promoted-runtime post-release monitoring found registry or route health gaps."
    else:
        primary_blocker = None
        next_lever = NEXT_ROUTE_BINDING
        goal = True
        english = "Promoted-runtime post-release monitoring passed. Bind monitoring report route next."

    audit = {
        "schemaVersion": "video_to_analysis_promoted_runtime_monitoring_execution_audit_v1",
        "generatedAt": utc_now_iso(),
        "registryAudit": registry,
        "routeSmokeAudit": routes,
        "monitoringChecks": {
            "planReady": plan_ready,
            "registryMatchesPromotedV7_2DefaultRuntime": registry["registryMatchesPromotedV7_2DefaultRuntime"],
            "operatorVisibleRouteSmokePassed": routes["operatorVisibleRouteSmokePassed"],
            "noTrainingExecuted": True,
            "noPromotionMutationExecuted": True,
            "noRuntimeDefaultMutationExecuted": True,
        },
    }
    audit["allMonitoringChecksPassed"] = all(audit["monitoringChecks"].values())
    summary = {
        "batchName": "video_to_analysis_promoted_runtime_post_release_monitoring_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotedRuntimePostReleaseMonitoringExecuted": plan_ready,
        "promotedRuntimeHealthPassed": health_passed,
        "registryMatchesPromotedV7_2DefaultRuntime": registry["registryMatchesPromotedV7_2DefaultRuntime"],
        "routeSmokePassedCount": routes["routeSmokePassedCount"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_post_release_monitoring_execution_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_monitoring_execution_audit.json": audit,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Post Release Monitoring Execution",
    )


def main() -> None:
    main_for(
        "Execute video-to-analysis promoted runtime post-release monitoring.",
        run_video_to_analysis_promoted_runtime_post_release_monitoring_execution,
    )


if __name__ == "__main__":
    main()
