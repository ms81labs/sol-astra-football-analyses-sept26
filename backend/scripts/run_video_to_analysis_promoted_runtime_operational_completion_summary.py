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

DEFAULT_ROUTE_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_operational_completion_summary_v1"

BLOCKER_ROUTE_MISSING = "video_to_analysis_promoted_runtime_monitoring_route_missing"
NEXT_ROUTE_BINDING = "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding"
NEXT_STEADY_STATE = "video_to_analysis_steady_state_monitoring_cycle"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_operational_completion_summary",
                "successCriteria": ["monitoring route passed", "release is operationally complete"],
                "failureAdaptation": "If monitoring route is missing, route back to route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operational_completion_evidence_repair",
                "successCriteria": ["repair only completion evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operational_completion_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary.",
            },
        ],
    }


def _route_ready(summary: dict[str, Any] | None, view_model: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotedRuntimeMonitoringRouteReady") is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and isinstance(view_model, dict)
        and view_model.get("promotedRuntimeHealthPassed") is True
    )


def run_video_to_analysis_promoted_runtime_operational_completion_summary(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    route_summary = load_json(route_root / "promoted_runtime_post_release_monitoring_route_binding_summary.json")
    view_model = load_json(route_root / "promoted_runtime_monitoring_view_model.json")
    ready = _route_ready(route_summary, view_model)

    if ready:
        primary_blocker = None
        next_lever = NEXT_STEADY_STATE
        goal = True
        english = "Video-to-analysis promoted v7.2 runtime is operationally complete. Continue with steady-state monitoring cycles."
    else:
        primary_blocker = BLOCKER_ROUTE_MISSING
        next_lever = NEXT_ROUTE_BINDING
        goal = False
        english = "Promoted-runtime monitoring route is missing or unhealthy; bind monitoring route before operational completion."

    manifest = {
        "schemaVersion": "video_to_analysis_promoted_runtime_operational_completion_manifest_v1",
        "generatedAt": utc_now_iso(),
        "videoToAnalysisPromotedRuntimeOperationallyComplete": goal,
        "releasedRuntimeVersion": "v7.2" if goal else None,
        "steadyStateMonitoringReady": goal,
        "nextOperatingMode": "steady_state_monitoring_cycle" if goal else "monitoring_route_repair",
    }
    summary = {
        "batchName": "video_to_analysis_promoted_runtime_operational_completion_summary",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "videoToAnalysisPromotedRuntimeOperationallyComplete": goal,
        "releasedRuntimeVersion": "v7.2" if goal else None,
        "steadyStateMonitoringReady": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_operational_completion_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_operational_completion_manifest.json": manifest,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Operational Completion Summary",
    )


def main() -> None:
    main_for(
        "Write video-to-analysis promoted runtime operational completion summary.",
        run_video_to_analysis_promoted_runtime_operational_completion_summary,
    )


if __name__ == "__main__":
    main()
