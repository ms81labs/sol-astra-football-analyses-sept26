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

DEFAULT_READOUT_PACK_DIR_NAME = "video_to_analysis_release_readout_pack_v1"
DEFAULT_READOUT_ROUTE_DIR_NAME = "video_to_analysis_release_readout_route_binding_v1"
DEFAULT_EXTERNAL_BINDING_DIR_NAME = "football_external_benchmark_real_report_and_product_binding_v1"
DEFAULT_USER_READOUT_DIR_NAME = "video_to_analysis_user_facing_release_readout_v1"
DEFAULT_OPERATOR_DASHBOARD_DIR_NAME = "video_to_analysis_operator_dashboard_polish_v1"
DEFAULT_STORAGE_CLEANUP_CLOSEOUT_DIR_NAME = "video_to_analysis_storage_cleanup_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_next_strategic_lane_selection_v1"

BLOCKER_RELEASE_READOUT_ROUTE_MISSING = "video_to_analysis_next_strategic_lane_release_readout_route_missing"
NEXT_RELEASE_READOUT_ROUTE = "video_to_analysis_release_readout_route_binding"
NEXT_USER_FACING_READOUT = "video_to_analysis_user_facing_release_readout"
NEXT_EXTERNAL_BENCHMARK = "football_external_benchmark_real_evaluation_design"
NEXT_MANUAL_STRATEGIC_CHOICE = "manual_strategic_lane_selection_required"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_next_strategic_lane_selection",
                "successCriteria": [
                    "release/readout route is live",
                    "next strategic lane matrix is valid",
                    "choose the highest-value unfulfilled lane",
                    "preserve all guardrails",
                ],
                "failureAdaptation": "If release/readout route is missing, route back to route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "strategic_lane_selection_reference_repair",
                "successCriteria": ["repair only source references or selection facts"],
                "failureAdaptation": "If the matrix remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "strategic_lane_selection_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop; do not auto-continue bounded growth without a valid selection.",
            },
        ],
    }


def _release_route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("releaseReadoutRouteReady") is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _external_benchmark_satisfied(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _user_readout_satisfied(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("userFacingReleaseReadoutReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _operator_dashboard_satisfied(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operatorDashboardRouteReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _storage_cleanup_satisfied(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("storageCleanupCloseoutReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _versioned_dir_number(path: Path) -> int:
    try:
        return int(path.name.rsplit("_v", 1)[1])
    except (IndexError, ValueError):
        return 0


def _latest_growth_closeout_summary(root: Path) -> dict[str, Any] | None:
    dirs = sorted(
        root.glob("video_to_analysis_growth_lane_closeout_readout_v*"),
        key=_versioned_dir_number,
        reverse=True,
    )
    for path in dirs:
        summary = load_json(path / "growth_lane_closeout_readout_summary.json")
        if isinstance(summary, dict):
            return summary
    return None


def _growth_closeout_requires_manual_choice(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("growthLaneCloseoutReady") is True
        and summary.get("manualStrategicChoiceRequired") is True
        and summary.get("autoContinueBoundedGrowthRecommended") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _matrix_valid(matrix: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(matrix, dict)
        and matrix.get("schemaVersion") == "video_to_analysis_next_strategic_lane_matrix_v1"
        and isinstance(matrix.get("candidateStrategicLanes"), list)
        and matrix.get("candidateStrategicLanes")
    )


def _select_lane(
    matrix: dict[str, Any],
    *,
    external_satisfied: bool,
    user_readout_satisfied: bool,
    operator_dashboard_satisfied: bool,
    storage_cleanup_satisfied: bool,
) -> dict[str, Any]:
    lanes = matrix.get("candidateStrategicLanes") or []
    by_id = {row.get("id"): row for row in lanes if isinstance(row, dict)}
    if external_satisfied and not user_readout_satisfied and "user_facing_release_readout" in by_id:
        row = by_id["user_facing_release_readout"]
        return {
            "selectedStrategicLane": "user_facing_release_readout",
            "selectedNextLever": row.get("nextLever") or NEXT_USER_FACING_READOUT,
            "reason": "external_benchmark_already_satisfied_release_readout_route_live",
        }
    if not operator_dashboard_satisfied and "operator_dashboard_polish" in by_id:
        row = by_id["operator_dashboard_polish"]
        return {
            "selectedStrategicLane": "operator_dashboard_polish",
            "selectedNextLever": row.get("nextLever") or "video_to_analysis_operator_dashboard_polish",
            "reason": "operator_dashboard_not_yet_completed",
        }
    if not storage_cleanup_satisfied and "storage_cleanup_approval" in by_id:
        row = by_id["storage_cleanup_approval"]
        return {
            "selectedStrategicLane": "storage_cleanup_approval",
            "selectedNextLever": row.get("nextLever") or "video_to_analysis_storage_cleanup_approval",
            "reason": "storage_cleanup_not_yet_closed_out",
        }
    if "external_benchmark_expansion" in by_id:
        if external_satisfied and user_readout_satisfied and operator_dashboard_satisfied and storage_cleanup_satisfied:
            row = by_id.get("bounded_growth_v38_continuation") or {}
            return {
                "selectedStrategicLane": "bounded_growth_v38_continuation",
                "selectedNextLever": row.get("nextLever") or "video_to_analysis_bounded_next_sample_execution_approval",
                "reason": "strategic_housekeeping_complete_resume_bounded_growth",
            }
        row = by_id["external_benchmark_expansion"]
        return {
            "selectedStrategicLane": "external_benchmark_expansion",
            "selectedNextLever": row.get("nextLever") or NEXT_EXTERNAL_BENCHMARK,
            "reason": "external_benchmark_not_yet_satisfied",
        }
    return {
        "selectedStrategicLane": "bounded_growth_v38_continuation",
        "selectedNextLever": "video_to_analysis_bounded_next_sample_execution_approval",
        "reason": "fallback_to_existing_v38_queue",
    }


def run_video_to_analysis_next_strategic_lane_selection(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)

    matrix = load_json(root / DEFAULT_READOUT_PACK_DIR_NAME / "next_strategic_lane_matrix.json")
    route_summary = load_json(root / DEFAULT_READOUT_ROUTE_DIR_NAME / "release_readout_route_binding_summary.json")
    external_summary = load_json(
        root / DEFAULT_EXTERNAL_BINDING_DIR_NAME / "real_report_and_product_binding_summary.json"
    )
    user_readout_summary = load_json(root / DEFAULT_USER_READOUT_DIR_NAME / "user_facing_release_readout_summary.json")
    operator_dashboard_summary = load_json(root / DEFAULT_OPERATOR_DASHBOARD_DIR_NAME / "operator_dashboard_polish_summary.json")
    storage_cleanup_summary = load_json(root / DEFAULT_STORAGE_CLEANUP_CLOSEOUT_DIR_NAME / "storage_cleanup_closeout_summary.json")
    growth_closeout_summary = _latest_growth_closeout_summary(root)

    route_ready = _release_route_ready(route_summary)
    matrix_ready = _matrix_valid(matrix)
    external_satisfied = _external_benchmark_satisfied(external_summary)
    user_readout_done = _user_readout_satisfied(user_readout_summary)
    operator_dashboard_done = _operator_dashboard_satisfied(operator_dashboard_summary)
    storage_cleanup_done = _storage_cleanup_satisfied(storage_cleanup_summary)
    growth_closeout_manual_choice = _growth_closeout_requires_manual_choice(growth_closeout_summary)

    if not route_ready:
        goal = False
        primary_blocker = BLOCKER_RELEASE_READOUT_ROUTE_MISSING
        next_lever = NEXT_RELEASE_READOUT_ROUTE
        selection = {
            "selectedStrategicLane": None,
            "selectedNextLever": next_lever,
            "reason": "release_readout_route_missing_or_unsafe",
        }
        english = "Release/readout route is missing or unsafe; bind it before selecting the next strategic lane."
    elif not matrix_ready:
        goal = False
        primary_blocker = "video_to_analysis_next_strategic_lane_matrix_missing"
        next_lever = "video_to_analysis_release_readout_pack"
        selection = {
            "selectedStrategicLane": None,
            "selectedNextLever": next_lever,
            "reason": "strategic_lane_matrix_missing_or_invalid",
        }
        english = "Strategic lane matrix is missing or invalid; rebuild release/readout pack."
    elif growth_closeout_manual_choice:
        goal = True
        primary_blocker = None
        next_lever = NEXT_MANUAL_STRATEGIC_CHOICE
        selection = {
            "selectedStrategicLane": "manual_strategic_lane_selection_required",
            "selectedNextLever": next_lever,
            "reason": "growth_lane_closeout_requires_operator_strategic_choice",
        }
        english = (
            "Growth-lane closeout is already verified; choose the next strategic lane manually instead of "
            "auto-consuming another bounded growth queue."
        )
    else:
        goal = True
        primary_blocker = None
        selection = _select_lane(
            matrix or {},
            external_satisfied=external_satisfied,
            user_readout_satisfied=user_readout_done,
            operator_dashboard_satisfied=operator_dashboard_done,
            storage_cleanup_satisfied=storage_cleanup_done,
        )
        next_lever = str(selection["selectedNextLever"])
        english = f"Selected `{selection['selectedStrategicLane']}` as the next roadmap lane."

    selection_artifact = {
        "schemaVersion": "video_to_analysis_next_strategic_lane_selection_v1",
        "generatedAt": utc_now_iso(),
        "releaseReadoutRouteReady": route_ready,
        "externalBenchmarkAlreadySatisfied": external_satisfied,
        "userFacingReleaseReadoutAlreadySatisfied": user_readout_done,
        "operatorDashboardAlreadySatisfied": operator_dashboard_done,
        "storageCleanupAlreadySatisfied": storage_cleanup_done,
        "growthLaneCloseoutManualStrategicChoiceRequired": growth_closeout_manual_choice,
        "growthLaneClosedAtSnapshotDir": growth_closeout_summary.get("growthLaneClosedAtSnapshotDir")
        if isinstance(growth_closeout_summary, dict)
        else None,
        "growthLaneClosedAtVersion": growth_closeout_summary.get("growthLaneClosedAtVersion")
        if isinstance(growth_closeout_summary, dict)
        else None,
        **selection,
    }
    summary = {
        "batchName": "video_to_analysis_next_strategic_lane_selection",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "selectedStrategicLane": selection.get("selectedStrategicLane"),
        "externalBenchmarkAlreadySatisfied": external_satisfied,
        "userFacingReleaseReadoutAlreadySatisfied": user_readout_done,
        "operatorDashboardAlreadySatisfied": operator_dashboard_done,
        "storageCleanupAlreadySatisfied": storage_cleanup_done,
        "growthLaneCloseoutManualStrategicChoiceRequired": growth_closeout_manual_choice,
        "growthLaneClosedAtSnapshotDir": growth_closeout_summary.get("growthLaneClosedAtSnapshotDir")
        if isinstance(growth_closeout_summary, dict)
        else None,
        "growthLaneClosedAtVersion": growth_closeout_summary.get("growthLaneClosedAtVersion")
        if isinstance(growth_closeout_summary, dict)
        else None,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_next_strategic_lane_selection_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "release_readout_route_missing",
                "selected": primary_blocker == BLOCKER_RELEASE_READOUT_ROUTE_MISSING,
                "primaryBlocker": BLOCKER_RELEASE_READOUT_ROUTE_MISSING,
                "nextRecommendedNextLever": NEXT_RELEASE_READOUT_ROUTE,
            },
            {
                "condition": "external_benchmark_satisfied_choose_release_readout",
                "selected": goal and selection.get("selectedStrategicLane") == "user_facing_release_readout",
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_USER_FACING_READOUT,
            },
            {
                "condition": "external_benchmark_not_satisfied",
                "selected": goal and selection.get("selectedStrategicLane") == "external_benchmark_expansion",
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_EXTERNAL_BENCHMARK,
            },
            {
                "condition": "growth_lane_closeout_requires_manual_strategic_choice",
                "selected": goal
                and selection.get("selectedStrategicLane") == "manual_strategic_lane_selection_required",
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_MANUAL_STRATEGIC_CHOICE,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="next_strategic_lane_selection_summary.json",
        summary=summary,
        artifacts={
            "strategic_lane_selection.json": selection_artifact,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Next Strategic Lane Selection",
    )


def main() -> None:
    main_for("Select next video-to-analysis strategic lane.", run_video_to_analysis_next_strategic_lane_selection)


if __name__ == "__main__":
    main()
