from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)
from backend.scripts.video_to_analysis_operational_sprint_common import latest_versioned_dir  # noqa: E402

DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_current_release_acceptance_decision_surface_v1"

NEXT_SOCCERNET_VALIDATION_PLAN = "football_external_soccernet_bounded_product_validation_plan"
NEXT_RELEASE_READOUT_ROUTE = "video_to_analysis_release_readout_route_binding"
NEXT_ACCEPTANCE_REPORT_ROUTE = "video_to_analysis_acceptance_report_route_binding"
NEXT_RELEASE_COMPLETION = "video_to_analysis_release_completion_summary"
NEXT_OPERATOR_DASHBOARD = "video_to_analysis_operator_dashboard_polish"
NEXT_MANUAL_DECISION_SURFACE = "video_to_analysis_current_release_acceptance_decision_surface"
NEXT_MANUAL_OPERATOR_RELEASE_DECISION = "manual_operator_release_decision_required"

BLOCKER_RELEASE_ROUTE_STALE = "video_to_analysis_current_release_route_stale"
BLOCKER_ACCEPTANCE_TRUTH_MISSING = "video_to_analysis_current_acceptance_truth_missing"
BLOCKER_OPERATOR_DECISION_SURFACE_GAP = "video_to_analysis_current_operator_decision_surface_gap"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "current_release_acceptance_decision_surface",
                "successCriteria": [
                    "release completion truth is current",
                    "operator dashboard route is ready",
                    "acceptance and release/readout routes are ready",
                    "latest growth closeout is reflected",
                    "manual strategic choice is reflected",
                    "all mutation guardrails remain false",
                ],
                "failureAdaptation": "If current truth is complete, write a current operator decision surface.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "route_truth_reference_repair",
                "successCriteria": ["repair only route/view-model references to generated truth"],
                "failureAdaptation": "If a route surface is stale or missing, route to exactly that route binding.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_acceptance_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop without training, promotion, runtime mutation, downloads, or storage mutation.",
            },
        ],
    }


def _base_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and guardrails_false(summary)
    )


def _archive_guardrails_preserved(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    return bool(
        summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecutedByThisBatch") is False
    )


def _route_ready(summary: dict[str, Any] | None, flag: str) -> bool:
    return bool(
        _base_ready(summary)
        and summary.get(flag) is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
    )


def _release_runtime_complete(summary: dict[str, Any] | None) -> bool:
    return bool(_base_ready(summary) and summary.get("releasedRuntimeVersion") == "v7.2")


def _release_archive_complete(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and (
            summary.get("currentReleaseFinished") is True
            or summary.get("videoToAnalysisReleaseAcceptanceArchived") is True
        )
        and _archive_guardrails_preserved(summary)
    )


def _growth_closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        _base_ready(summary)
        and summary.get("growthLaneCloseoutReady") is True
        and isinstance(summary.get("growthLaneClosedAtVersion"), int)
        and isinstance(summary.get("growthLaneClosedAtSnapshotDir"), str)
        and summary.get("manualStrategicChoiceRequired") is True
        and summary.get("autoContinueBoundedGrowthRecommended") is False
    )


def _selector_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        _base_ready(summary)
        and summary.get("selectedStrategicLane") == "manual_strategic_lane_selection_required"
        and summary.get("growthLaneCloseoutManualStrategicChoiceRequired") is True
        and summary.get("nextRecommendedNextLever") == "manual_strategic_lane_selection_required"
    )


def _post_release_monitoring_closed(summary: dict[str, Any] | None) -> bool:
    return bool(
        _base_ready(summary)
        and (
            summary.get("postReleaseMonitoringCloseoutReady") is True
            or summary.get("steadyStateMonitoringCyclePassed") is True
        )
    )


def _source_pool_cycle_still_present(summary: dict[str, Any] | None) -> bool:
    return bool(
        _base_ready(summary)
        and summary.get("sourceSamplingPoolExhausted") is True
        and summary.get("nextRecommendedNextLever") == "video_to_analysis_source_pool_replenishment_plan"
    )


def _operator_decision_model(
    *,
    released_runtime_version: str,
    growth_summary: dict[str, Any] | None,
    selector_summary: dict[str, Any] | None,
    source_pool_cycle_still_present: bool,
) -> dict[str, Any]:
    if source_pool_cycle_still_present and released_runtime_version == "v7.3":
        return {
            "schemaVersion": "video_to_analysis_current_operator_decision_model_v1",
            "generatedAt": utc_now_iso(),
            "title": "Video-to-analysis current release and strategic decision surface",
            "currentState": "current_release_done_optional_coverage_loop",
            "releasedRuntimeVersion": released_runtime_version,
            "growthLaneClosedAtSnapshotDir": (growth_summary or {}).get("growthLaneClosedAtSnapshotDir"),
            "growthLaneClosedAtVersion": (growth_summary or {}).get("growthLaneClosedAtVersion"),
            "selectedStrategicLane": (selector_summary or {}).get("selectedStrategicLane"),
            "sourcePoolCycleStillPresent": True,
            "currentOperatorReading": (
                "The v7.3 runtime/release surfaces are packaged. The remaining source-pool loop is optional "
                "coverage work and should not auto-advance without an explicit operator decision."
            ),
            "recommendedStrategicChoice": "manual_operator_release_decision",
            "recommendedNextLever": NEXT_MANUAL_OPERATOR_RELEASE_DECISION,
            "availableStrategicChoices": [
                "declare_current_milestone_done",
                "resume_source_pool_replenishment_as_optional_coverage",
                "package_release_readout",
                "acquire_new_sources_before_more_scaleout",
            ],
            "choiceRationale": [
                {
                    "choice": "declare_current_milestone_done",
                    "priority": "P0",
                    "status": "recommended_operator_choice",
                    "reason": "Current release truth is complete; more source sampling is no longer required for this milestone.",
                },
                {
                    "choice": "resume_source_pool_replenishment_as_optional_coverage",
                    "priority": "P2",
                    "status": "available_but_manual",
                    "reason": "The replenishment loop can continue as coverage expansion, not as a finish-line blocker.",
                },
                {
                    "choice": "package_release_readout",
                    "priority": "P1",
                    "status": "available_if_operator_wants_external_artifact",
                    "reason": "Release facts can be packaged without consuming more samples.",
                },
                {
                    "choice": "acquire_new_sources_before_more_scaleout",
                    "priority": "P2",
                    "status": "available_if_scaleout_continues",
                    "reason": "Generated truth shows the current autonomous source pool has been exhausted repeatedly.",
                },
            ],
        }

    return {
        "schemaVersion": "video_to_analysis_current_operator_decision_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Video-to-analysis current release and strategic decision surface",
        "currentState": "release_operational_growth_lane_closed",
        "releasedRuntimeVersion": released_runtime_version,
        "growthLaneClosedAtSnapshotDir": (growth_summary or {}).get("growthLaneClosedAtSnapshotDir"),
        "growthLaneClosedAtVersion": (growth_summary or {}).get("growthLaneClosedAtVersion"),
        "selectedStrategicLane": (selector_summary or {}).get("selectedStrategicLane"),
        "currentOperatorReading": (
            "The v7.2 runtime/release surfaces are complete enough to operate. "
            "The bounded growth lane is closed at v57. The next action is a deliberate strategic choice, "
            "not automatic bounded queue execution."
        ),
        "recommendedStrategicChoice": "external_benchmark_soccernet_lane",
        "recommendedNextLever": NEXT_SOCCERNET_VALIDATION_PLAN,
        "availableStrategicChoices": [
            "product_operator_polish",
            "external_benchmark_soccernet_lane",
            "resume_bounded_growth_intentionally",
            "release_acceptance_packaging",
        ],
        "choiceRationale": [
            {
                "choice": "product_operator_polish",
                "priority": "P0",
                "status": "current_decision_surface_packaged",
                "reason": "Operator/readout clarity is needed before more growth.",
            },
            {
                "choice": "external_benchmark_soccernet_lane",
                "priority": "P1",
                "status": "recommended_next",
                "reason": "External/SoccerNet validation is the next meaningful credibility step after current release packaging.",
            },
            {
                "choice": "resume_bounded_growth_intentionally",
                "priority": "P3",
                "status": "optional_future_input",
                "reason": "The v57 queue remains valid, but generated truth says not to auto-consume it.",
            },
            {
                "choice": "release_acceptance_packaging",
                "priority": "P0",
                "status": "current_batch",
                "reason": "This batch packages the current acceptance/release surface.",
            },
        ],
    }


def run_video_to_analysis_current_release_acceptance_decision_surface(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)

    growth_dir = latest_versioned_dir(
        root, "video_to_analysis_growth_lane_closeout_readout", "video_to_analysis_growth_lane_closeout_readout_v57"
    )
    selector_dir = latest_versioned_dir(
        root, "video_to_analysis_next_strategic_lane_selection", "video_to_analysis_next_strategic_lane_selection_v1"
    )
    release_archive_dir = latest_versioned_dir(
        root, "video_to_analysis_release_acceptance_archive", "video_to_analysis_release_acceptance_archive_v1"
    )
    release_completion_dir = latest_versioned_dir(
        root, "video_to_analysis_release_completion_summary", "video_to_analysis_release_completion_summary_v1"
    )
    dashboard_dir = latest_versioned_dir(
        root, "video_to_analysis_operator_dashboard_polish", "video_to_analysis_operator_dashboard_polish_v1"
    )
    acceptance_dir = latest_versioned_dir(
        root, "video_to_analysis_acceptance_report_route_binding", "video_to_analysis_acceptance_report_route_binding_v1"
    )
    readout_dir = latest_versioned_dir(
        root, "video_to_analysis_release_readout_route_binding", "video_to_analysis_release_readout_route_binding_v1"
    )
    monitoring_dir = latest_versioned_dir(
        root, "video_to_analysis_steady_state_monitoring_cycle", "video_to_analysis_steady_state_monitoring_cycle_v1"
    )
    if not (monitoring_dir / "steady_state_monitoring_cycle_summary.json").exists():
        monitoring_dir = latest_versioned_dir(
            root,
            "video_to_analysis_post_release_monitoring_closeout",
            "video_to_analysis_post_release_monitoring_closeout_v1",
        )
    roadmap_dir = latest_versioned_dir(
        root, "video_to_analysis_next_roadmap_direction_snapshot", "video_to_analysis_next_roadmap_direction_snapshot_v1"
    )

    growth_summary = load_json(growth_dir / "growth_lane_closeout_readout_summary.json")
    selector_summary = load_json(selector_dir / "next_strategic_lane_selection_summary.json")
    release_archive_summary = load_json(release_archive_dir / "release_acceptance_archive_summary.json")
    release_summary = load_json(release_completion_dir / "release_completion_summary.json")
    dashboard_summary = load_json(dashboard_dir / "operator_dashboard_polish_summary.json")
    acceptance_summary = load_json(acceptance_dir / "acceptance_report_route_binding_summary.json")
    readout_summary = load_json(readout_dir / "release_readout_route_binding_summary.json")
    monitoring_summary = load_json(monitoring_dir / "steady_state_monitoring_cycle_summary.json") or load_json(
        monitoring_dir / "post_release_monitoring_closeout_summary.json"
    )
    roadmap_summary = load_json(roadmap_dir / "next_roadmap_direction_snapshot_summary.json")

    archive_complete = _release_archive_complete(release_archive_summary)
    release_complete = archive_complete or _release_runtime_complete(release_summary)
    released_runtime_version = (
        (release_archive_summary or {}).get("activeRuntimeDefaultVersion")
        if archive_complete
        else (release_summary or {}).get("releasedRuntimeVersion")
    )
    dashboard_ready = _route_ready(dashboard_summary, "operatorDashboardRouteReady")
    acceptance_ready = _route_ready(acceptance_summary, "acceptanceReportRouteReady")
    readout_ready = _route_ready(readout_summary, "releaseReadoutRouteReady")
    monitoring_closed = _post_release_monitoring_closed(monitoring_summary)
    growth_ready = _growth_closeout_ready(growth_summary)
    selector_manual = _selector_ready(selector_summary)
    source_pool_cycle_still_present = _source_pool_cycle_still_present(roadmap_summary)
    release_guardrails_preserved = guardrails_false(release_summary) or _archive_guardrails_preserved(
        release_archive_summary
    )

    route_audit = {
        "schemaVersion": "video_to_analysis_current_route_readiness_audit_v1",
        "generatedAt": utc_now_iso(),
        "operatorDashboardRouteReady": dashboard_ready,
        "acceptanceReportRouteReady": acceptance_ready,
        "releaseReadoutRouteReady": readout_ready,
        "allCurrentRoutesReady": bool(dashboard_ready and acceptance_ready and readout_ready),
        "routeStatusCodes": {
            "operatorDashboard": {
                "api": (dashboard_summary or {}).get("apiRouteStatusCode"),
                "html": (dashboard_summary or {}).get("htmlRouteStatusCode"),
            },
            "acceptanceReport": {
                "api": (acceptance_summary or {}).get("apiRouteStatusCode"),
                "html": (acceptance_summary or {}).get("htmlRouteStatusCode"),
            },
            "releaseReadout": {
                "api": (readout_summary or {}).get("apiRouteStatusCode"),
                "html": (readout_summary or {}).get("htmlRouteStatusCode"),
            },
        },
    }
    guardrail_audit = {
        "schemaVersion": "video_to_analysis_current_release_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "releaseGuardrailsPreserved": release_guardrails_preserved,
        "dashboardGuardrailsPreserved": guardrails_false(dashboard_summary),
        "acceptanceGuardrailsPreserved": guardrails_false(acceptance_summary),
        "readoutGuardrailsPreserved": guardrails_false(readout_summary),
        "monitoringGuardrailsPreserved": guardrails_false(monitoring_summary),
        "growthCloseoutGuardrailsPreserved": guardrails_false(growth_summary),
        "selectorGuardrailsPreserved": guardrails_false(selector_summary),
        "allMutationGuardrailsPreserved": bool(
            release_guardrails_preserved
            and guardrails_false(dashboard_summary)
            and guardrails_false(acceptance_summary)
            and guardrails_false(readout_summary)
            and guardrails_false(monitoring_summary)
            and guardrails_false(growth_summary)
            and guardrails_false(selector_summary)
        ),
        **standard_false_flags(),
    }

    if not release_complete or not monitoring_closed:
        goal = False
        primary_blocker = BLOCKER_ACCEPTANCE_TRUTH_MISSING
        next_lever = NEXT_RELEASE_COMPLETION
        english = "Current release or monitoring truth is missing; rebuild release/acceptance truth before choosing the next strategic lane."
    elif not readout_ready:
        goal = False
        primary_blocker = BLOCKER_RELEASE_ROUTE_STALE
        next_lever = NEXT_RELEASE_READOUT_ROUTE
        english = "Release/readout route truth is missing or stale; bind the current release readout before advancing."
    elif not acceptance_ready:
        goal = False
        primary_blocker = BLOCKER_RELEASE_ROUTE_STALE
        next_lever = NEXT_ACCEPTANCE_REPORT_ROUTE
        english = "Acceptance report route truth is missing or stale; bind acceptance report routes before advancing."
    elif not dashboard_ready:
        goal = False
        primary_blocker = BLOCKER_OPERATOR_DECISION_SURFACE_GAP
        next_lever = NEXT_OPERATOR_DASHBOARD
        english = "Operator dashboard truth is missing or stale; refresh the dashboard before advancing."
    elif not growth_ready or not selector_manual:
        goal = False
        primary_blocker = BLOCKER_OPERATOR_DECISION_SURFACE_GAP
        next_lever = NEXT_MANUAL_DECISION_SURFACE
        english = "Growth closeout or strategic selector truth is missing; regenerate the current decision surface inputs."
    else:
        goal = True
        primary_blocker = None
        if source_pool_cycle_still_present and released_runtime_version == "v7.3":
            next_lever = NEXT_MANUAL_OPERATOR_RELEASE_DECISION
            english = (
                "Current v7.3 release is packaged; source-pool replenishment is optional coverage and requires "
                "an operator decision."
            )
        else:
            next_lever = NEXT_SOCCERNET_VALIDATION_PLAN
            english = (
                "Current release, acceptance, operator, and growth closeout truth are packaged. "
                "Advance to bounded SoccerNet/external product validation; do not auto-resume bounded growth."
            )

    decision_model = (
        _operator_decision_model(
            released_runtime_version=str(released_runtime_version or "v7.2"),
            growth_summary=growth_summary,
            selector_summary=selector_summary,
            source_pool_cycle_still_present=source_pool_cycle_still_present,
        )
        if goal
        else {
            "schemaVersion": "video_to_analysis_current_operator_decision_model_v1",
            "generatedAt": utc_now_iso(),
            "currentState": "blocked",
            "recommendedStrategicChoice": None,
            "recommendedNextLever": next_lever,
            "availableStrategicChoices": [],
        }
    )
    decision_matrix = {
        "schemaVersion": "video_to_analysis_current_release_acceptance_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "lanes": [
            {
                "id": "release_acceptance_packaging",
                "priority": "P0",
                "selectedNow": goal,
                "status": "packaged" if goal else "blocked",
            },
            {
                "id": "product_operator_polish",
                "priority": "P0",
                "selectedNow": False,
                "status": "ready" if dashboard_ready else "blocked",
            },
            {
                "id": "external_benchmark_soccernet_lane",
                "priority": "P1",
                "selectedNow": bool(goal and next_lever == NEXT_SOCCERNET_VALIDATION_PLAN),
                "nextRecommendedNextLever": NEXT_SOCCERNET_VALIDATION_PLAN,
            },
            {
                "id": "manual_operator_release_decision",
                "priority": "P0",
                "selectedNow": bool(goal and next_lever == NEXT_MANUAL_OPERATOR_RELEASE_DECISION),
                "nextRecommendedNextLever": NEXT_MANUAL_OPERATOR_RELEASE_DECISION,
            },
            {
                "id": "resume_bounded_growth_intentionally",
                "priority": "P3",
                "selectedNow": False,
                "status": "optional_future_input",
                "requiresManualChoice": True,
            },
        ],
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
    }

    summary = {
        "batchName": "video_to_analysis_current_release_acceptance_decision_surface",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "releaseRuntimeComplete": release_complete,
        "releasedRuntimeVersion": released_runtime_version,
        "activeRuntimeDefaultVersion": released_runtime_version,
        "currentReleaseFinished": bool(archive_complete or release_complete),
        "operatorDashboardRouteReady": dashboard_ready,
        "acceptanceReportRouteReady": acceptance_ready,
        "releaseReadoutRouteReady": readout_ready,
        "postReleaseMonitoringClosed": monitoring_closed,
        "growthLaneCloseoutReady": growth_ready,
        "growthLaneClosedAtSnapshotDir": (growth_summary or {}).get("growthLaneClosedAtSnapshotDir"),
        "growthLaneClosedAtVersion": (growth_summary or {}).get("growthLaneClosedAtVersion"),
        "selectedStrategicLane": (selector_summary or {}).get("selectedStrategicLane"),
        "sourcePoolCycleStillPresent": source_pool_cycle_still_present,
        "growthLaneCloseoutDir": growth_dir.name,
        "strategicLaneSelectionDir": selector_dir.name,
        "releaseArchiveDir": release_archive_dir.name if release_archive_summary else None,
        "releaseCompletionDir": release_completion_dir.name,
        "operatorDashboardDir": dashboard_dir.name,
        "sourceRoadmapDirectionDir": roadmap_dir.name if roadmap_summary else None,
        "recommendedStrategicChoice": decision_model.get("recommendedStrategicChoice"),
        "availableStrategicChoices": decision_model.get("availableStrategicChoices"),
        "currentReleaseDecisionSurfaceReady": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="current_release_acceptance_decision_surface_summary.json",
        summary=summary,
        artifacts={
            "current_operator_decision_model.json": decision_model,
            "current_route_readiness_audit.json": route_audit,
            "current_guardrail_audit.json": guardrail_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Current Release Acceptance Decision Surface",
    )


def main() -> None:
    main_for(
        "Package current video-to-analysis release/acceptance strategic decision surface.",
        run_video_to_analysis_current_release_acceptance_decision_surface,
    )


if __name__ == "__main__":
    main()
