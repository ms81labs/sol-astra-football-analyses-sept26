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

DEFAULT_OPERATIONAL_COMPLETION_DIR_NAME = "video_to_analysis_promoted_runtime_operational_completion_summary_v1"
DEFAULT_RELEASE_ARCHIVE_DIR_NAME = "video_to_analysis_release_acceptance_archive_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_steady_state_monitoring_cycle_v1"

BLOCKER_OPERATIONAL_COMPLETION_MISSING = "video_to_analysis_steady_state_operational_completion_missing"
BLOCKER_REGISTRY_MISMATCH = "video_to_analysis_steady_state_runtime_registry_mismatch"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_steady_state_route_smoke_failed"
BLOCKER_SOURCE_ROBUSTNESS_REGRESSION = "video_to_analysis_steady_state_source_robustness_regression"

NEXT_OPERATIONAL_COMPLETION = "video_to_analysis_promoted_runtime_operational_completion_summary"
NEXT_REGISTRY_REPAIR = "promoted_runtime_registry_repair"
NEXT_ROUTE_REPAIR = "promoted_runtime_route_binding_repair"
NEXT_SOURCE_REGRESSION_DEBUG = "source_robustness_regression_debug"
NEXT_OPERATIONAL_BACKLOG = "video_to_analysis_operational_backlog_prioritization"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "steady_state_runtime_health_cycle",
                "successCriteria": [
                    "operational completion truth is present",
                    "promoted active runtime registry is still active",
                    "five operator-visible routes still smoke",
                    "old failing_source_not_viable blocker remains inactive",
                ],
                "failureAdaptation": "If one health surface fails, route to the exact repair family instead of mutating runtime state.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "steady_state_route_or_artifact_repair",
                "successCriteria": ["repair only stale route/report wiring or missing saved-truth references"],
                "failureAdaptation": "Do not train, download data, or alter runtime defaults; rerun the health cycle after repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "steady_state_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary and preserve promoted runtime guardrails.",
            },
        ],
    }


def _operational_completion_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisPromotedRuntimeOperationallyComplete") is True
        and summary.get("releasedRuntimeVersion") == "v7.2"
        and summary.get("steadyStateMonitoringReady") is True
    )


def _release_archive_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisReleaseAcceptanceArchived") is True
        and summary.get("currentReleaseFinished") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultMutationExecutedByThisBatch") is False
    )


def _select_outcome(
    *,
    operational_ready: bool,
    registry: dict[str, Any],
    routes: dict[str, Any],
    active_runtime_version: str | None,
) -> tuple[bool, str | None, str, str]:
    registry_ok = registry.get("registryMatchesActiveDefaultRuntime", registry["registryMatchesPromotedV7_2DefaultRuntime"])
    source_blocker_dead = registry["checks"]["activeFailingSourceNotViableBlockerAbsent"]
    routes_ok = routes["operatorVisibleRouteSmokePassed"]

    if not operational_ready:
        return (
            False,
            BLOCKER_OPERATIONAL_COMPLETION_MISSING,
            NEXT_OPERATIONAL_COMPLETION,
            "Operational completion truth is missing; complete promoted-runtime operational closeout before steady-state monitoring.",
        )
    if not registry_ok:
        return (
            False,
            BLOCKER_REGISTRY_MISMATCH,
            NEXT_REGISTRY_REPAIR,
            "Steady-state monitoring found the promoted active runtime registry is no longer authoritative.",
        )
    if not source_blocker_dead:
        return (
            False,
            BLOCKER_SOURCE_ROBUSTNESS_REGRESSION,
            NEXT_SOURCE_REGRESSION_DEBUG,
            "The old failing_source_not_viable blocker appears active again; debug source-robustness regression before continuing.",
        )
    if not routes_ok:
        return (
            False,
            BLOCKER_ROUTE_SMOKE_FAILED,
            NEXT_ROUTE_REPAIR,
            "Steady-state monitoring found an operator-visible route smoke failure; repair route/report binding only.",
        )
    return (
        True,
        None,
        NEXT_OPERATIONAL_BACKLOG,
        f"Promoted {active_runtime_version or 'active'} runtime steady-state monitoring passed. Continue with operational backlog prioritization.",
    )


def run_video_to_analysis_steady_state_monitoring_cycle(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)
    operational_summary = load_json(
        root / DEFAULT_OPERATIONAL_COMPLETION_DIR_NAME / "promoted_runtime_operational_completion_summary.json"
    )
    release_archive_summary = load_json(root / DEFAULT_RELEASE_ARCHIVE_DIR_NAME / "release_acceptance_archive_summary.json")
    release_archive_ready = _release_archive_ready(release_archive_summary)
    operational_ready = release_archive_ready or _operational_completion_ready(operational_summary)
    registry = registry_audit(storage_root)
    routes = route_smoke(storage_root)
    goal, primary_blocker, next_lever, english = _select_outcome(
        operational_ready=operational_ready,
        registry=registry,
        routes=routes,
        active_runtime_version=registry.get("activeRuntimeDefaultVersion"),
    )
    guardrail_checks = {
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
    }
    source_blocker_dead = bool(registry["checks"]["activeFailingSourceNotViableBlockerAbsent"])
    steady_state_checks = {
        "operationalCompletionReady": operational_ready,
        "registryMatchesPromotedV7_2DefaultRuntime": registry["registryMatchesPromotedV7_2DefaultRuntime"],
        "operatorVisibleRouteSmokePassed": routes["operatorVisibleRouteSmokePassed"],
        "oldFailingSourceNotViableBlockerDead": source_blocker_dead,
        "noTrainingExecuted": not guardrail_checks["trainingExecuted"],
        "noPromotionMutationExecuted": not guardrail_checks["promotionMutationExecuted"],
        "noRuntimeDefaultMutationExecuted": not guardrail_checks["runtimeDefaultMutationExecuted"],
        "noVideoDownloadExecuted": not guardrail_checks["videoDownloadExecuted"],
        "noDataDownloadExecuted": not guardrail_checks["dataDownloadExecuted"],
    }
    audit = {
        "schemaVersion": "video_to_analysis_steady_state_monitoring_cycle_audit_v1",
        "generatedAt": utc_now_iso(),
        "operationalCompletionSummaryPath": str(
            root / DEFAULT_OPERATIONAL_COMPLETION_DIR_NAME / "promoted_runtime_operational_completion_summary.json"
        ),
        "releaseArchiveSummaryPath": str(root / DEFAULT_RELEASE_ARCHIVE_DIR_NAME / "release_acceptance_archive_summary.json"),
        "releaseArchiveReady": release_archive_ready,
        "registryAudit": registry,
        "routeSmokeAudit": routes,
        "guardrailChecks": guardrail_checks,
        "steadyStateChecks": steady_state_checks,
        "allSteadyStateChecksPassed": all(steady_state_checks.values()),
    }
    summary = {
        "batchName": "video_to_analysis_steady_state_monitoring_cycle",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "steadyStateMonitoringCyclePassed": goal,
        "promotedRuntimeHealthy": goal,
        "releasedRuntimeVersion": registry.get("activeRuntimeDefaultVersion") if operational_ready else None,
        "registryMatchesPromotedV7_2DefaultRuntime": registry["registryMatchesPromotedV7_2DefaultRuntime"],
        "registryMatchesActiveDefaultRuntime": registry["registryMatchesActiveDefaultRuntime"],
        "routeSmokePassedCount": routes["routeSmokePassedCount"],
        "oldFailingSourceNotViableBlockerDead": source_blocker_dead,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="steady_state_monitoring_cycle_summary.json",
        summary=summary,
        artifacts={
            "steady_state_monitoring_cycle_audit.json": audit,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
                "failureRouting": {
                    BLOCKER_OPERATIONAL_COMPLETION_MISSING: NEXT_OPERATIONAL_COMPLETION,
                    BLOCKER_REGISTRY_MISMATCH: NEXT_REGISTRY_REPAIR,
                    BLOCKER_ROUTE_SMOKE_FAILED: NEXT_ROUTE_REPAIR,
                    BLOCKER_SOURCE_ROBUSTNESS_REGRESSION: NEXT_SOURCE_REGRESSION_DEBUG,
                },
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Steady State Monitoring Cycle",
    )


def main() -> None:
    main_for(
        "Run video-to-analysis promoted runtime steady-state monitoring cycle.",
        run_video_to_analysis_steady_state_monitoring_cycle,
    )


if __name__ == "__main__":
    main()
