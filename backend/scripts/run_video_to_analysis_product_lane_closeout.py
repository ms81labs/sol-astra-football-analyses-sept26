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

DEFAULT_HANDOFF_ROUTE_DIR_NAME = "video_to_analysis_operator_handoff_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_product_lane_closeout_v1"

BLOCKER_HANDOFF_ROUTE_MISSING = "video_to_analysis_operator_handoff_route_binding_missing"
NEXT_HANDOFF_ROUTE = "video_to_analysis_operator_handoff_route_binding"
NEXT_POST_RELEASE_MONITORING = "video_to_analysis_post_release_monitoring_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_product_lane_closeout",
                "successCriteria": [
                    "close the operator-facing video-to-analysis product lane",
                    "preserve detector/download/training/promotion/runtime guardrails",
                ],
                "failureAdaptation": "If handoff route truth is missing, route back to handoff route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "product_lane_closeout_evidence_repair",
                "successCriteria": ["repair only closeout evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "product_lane_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to handoff route binding, evidence repair, or post-release monitoring plan.",
            },
        ],
    }


def _handoff_route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operatorHandoffRouteReady") is True
        and summary.get("apiRoutePath") == "/api/video-to-analysis/operator-handoff"
        and summary.get("htmlRoutePath") == "/video-to-analysis/operator-handoff"
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
    )


def run_video_to_analysis_product_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_HANDOFF_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    handoff_route_summary = load_json(route_root / "operator_handoff_route_binding_summary.json")
    ready = _handoff_route_ready(handoff_route_summary)

    if ready:
        primary_blocker = None
        next_lever = NEXT_POST_RELEASE_MONITORING
        goal = True
        english = "Video-to-analysis product lane is closed. Plan post-release monitoring next."
    else:
        primary_blocker = BLOCKER_HANDOFF_ROUTE_MISSING
        next_lever = NEXT_HANDOFF_ROUTE
        goal = False
        english = "Operator handoff route binding is missing or unsafe; bind handoff route before product lane closeout."

    capability_matrix = {
        "schemaVersion": "video_to_analysis_product_lane_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "closedCapabilities": {
            "operatorHandoffRouteReady": ready,
            "releaseCandidateClosed": ready,
            "acceptanceReportRouteReady": ready,
            "broaderRealVideoAcceptancePassed": ready,
            "normalStorageProductSmokeCovered": ready,
            "v7_3RuntimeDefaultActive": ready,
        },
        "guardrails": {
            "detectorEvaluationReady": False,
            "candidateEvaluationReady": False,
            "downloadsReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": ready,
        },
    }
    remaining_gaps = {
        "schemaVersion": "video_to_analysis_product_lane_remaining_gaps_v1",
        "generatedAt": utc_now_iso(),
        "remainingGaps": []
        if ready
        else [
            {
                "gapId": BLOCKER_HANDOFF_ROUTE_MISSING,
                "description": "Operator handoff route binding was missing or unsafe.",
                "nextRecommendedNextLever": NEXT_HANDOFF_ROUTE,
            }
        ],
        "postReleaseMonitoringPlanReady": ready,
    }
    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = goal
    false_flags["runtimeDefaultMutationAllowed"] = goal
    summary = {
        "batchName": "video_to_analysis_product_lane_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "videoToAnalysisProductLaneClosed": goal,
        "videoToAnalysisProductPathReady": goal,
        "operatorHandoffRouteReady": goal,
        **false_flags,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "runtimeDefaultRolloutClosed": goal,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="product_lane_closeout_summary.json",
        summary=summary,
        artifacts={
            "product_lane_capability_matrix.json": capability_matrix,
            "product_lane_remaining_gap_analysis.json": remaining_gaps,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Product Lane Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis product lane.", run_video_to_analysis_product_lane_closeout)


if __name__ == "__main__":
    main()
