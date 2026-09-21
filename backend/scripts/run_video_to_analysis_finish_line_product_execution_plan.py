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

DEFAULT_ROUTE_DIR_NAME = "video_to_analysis_finish_line_route_implementation_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_product_execution_plan_v1"

BLOCKER_ROUTE_MISSING = "video_to_analysis_finish_line_route_implementation_missing"
NEXT_ROUTE_IMPL = "video_to_analysis_finish_line_route_implementation"
NEXT_EXECUTION_APPROVAL = "video_to_analysis_finish_line_product_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_plan", "successCriteria": ["write bounded product execution plan"], "failureAdaptation": "If route truth is missing, route back to route implementation."},
            {"attemptNumber": 2, "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_plan_repair", "successCriteria": ["repair execution scope only"], "failureAdaptation": "If scope remains unsafe, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_plan_blocker_summary", "successCriteria": ["write blocker truth"], "failureAdaptation": "Route to route implementation, plan repair, or execution approval."},
        ],
    }


def _route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineRouteReady") is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
    )


def run_video_to_analysis_finish_line_product_execution_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    route_summary = load_json(route_root / "finish_line_route_implementation_summary.json")
    ready = _route_ready(route_summary)
    primary_blocker = None if ready else BLOCKER_ROUTE_MISSING
    next_lever = NEXT_EXECUTION_APPROVAL if ready else NEXT_ROUTE_IMPL
    execution_scope = {
        "schemaVersion": "video_to_analysis_finish_line_product_execution_scope_v1",
        "generatedAt": utc_now_iso(),
        "executionPlanReady": ready,
        "sourceRoutePaths": {
            "api": "/api/video-to-analysis/finish-line",
            "html": "/video-to-analysis/finish-line",
        },
        "allowedExecutionMode": "bounded_product_route_and_bundle_smoke",
        "normalMatchStorageMutationAllowed": False,
        "isolatedBenchmarkStorageMutationAllowed": True,
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }
    execution_steps = {
        "schemaVersion": "video_to_analysis_finish_line_product_execution_steps_v1",
        "generatedAt": utc_now_iso(),
        "steps": [
            {"order": 1, "stepId": "route_response_snapshot", "description": "Snapshot finish-line API and HTML route responses."},
            {"order": 2, "stepId": "bundle_export_consistency", "description": "Confirm isolated match bundle export remains readable."},
            {"order": 3, "stepId": "product_acceptance_summary", "description": "Write product acceptance truth without promotion or runtime mutation."},
        ],
    }
    summary = {
        "batchName": "video_to_analysis_finish_line_product_execution_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "finishLineProductExecutionPlanReady": ready,
        "allowedExecutionMode": "bounded_product_route_and_bundle_smoke" if ready else None,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Finish-line product execution plan is ready. Approve bounded product route and bundle smoke next." if ready else "Finish-line route implementation is missing; implement routes first.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "route_missing", "selected": primary_blocker == BLOCKER_ROUTE_MISSING, "primaryBlocker": BLOCKER_ROUTE_MISSING, "nextRecommendedNextLever": NEXT_ROUTE_IMPL},
            {"condition": "execution_plan_ready", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EXECUTION_APPROVAL},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_product_execution_plan_summary.json",
        summary=summary,
        artifacts={
            "finish_line_product_execution_scope.json": execution_scope,
            "finish_line_product_execution_steps.json": execution_steps,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Product Execution Plan",
    )


def main() -> None:
    main_for("Plan bounded product finish-line execution after route implementation.", run_video_to_analysis_finish_line_product_execution_plan)


if __name__ == "__main__":
    main()
