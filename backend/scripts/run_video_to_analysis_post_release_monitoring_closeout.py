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

DEFAULT_ROUTE_DIR_NAME = "video_to_analysis_post_release_monitoring_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_post_release_monitoring_closeout_v1"

BLOCKER_ROUTE_MISSING = "video_to_analysis_post_release_monitoring_route_binding_missing"
NEXT_ROUTE_BINDING = "video_to_analysis_post_release_monitoring_route_binding"
NEXT_DETECTOR_REENTRY_PLAN = "video_to_analysis_detector_evaluation_reentry_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_post_release_monitoring_closeout",
                "successCriteria": ["close monitoring route truth", "route to detector-evaluation reentry planning only"],
                "failureAdaptation": "If route truth is missing, route back to monitoring route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "post_release_monitoring_closeout_evidence_repair",
                "successCriteria": ["repair only monitoring closeout evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "post_release_monitoring_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to monitoring route binding, evidence repair, or detector reentry plan.",
            },
        ],
    }


def _route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("postReleaseMonitoringRouteReady") is True
        and summary.get("apiRoutePath") == "/api/video-to-analysis/post-release-monitoring"
        and summary.get("htmlRoutePath") == "/video-to-analysis/post-release-monitoring"
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


def run_video_to_analysis_post_release_monitoring_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    route_summary = load_json(route_root / "post_release_monitoring_route_binding_summary.json")
    ready = _route_ready(route_summary)

    if ready:
        primary_blocker = None
        next_lever = NEXT_DETECTOR_REENTRY_PLAN
        goal = True
        english = "Post-release monitoring is closed. Plan detector-evaluation reentry next; do not execute detector evaluation yet."
    else:
        primary_blocker = BLOCKER_ROUTE_MISSING
        next_lever = NEXT_ROUTE_BINDING
        goal = False
        english = "Post-release monitoring route binding is missing or unsafe; bind monitoring route before closeout."

    capability_matrix = {
        "schemaVersion": "video_to_analysis_post_release_monitoring_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "closedCapabilities": {
            "postReleaseMonitoringRouteReady": ready,
            "operatorHandoffRouteReady": ready,
            "acceptanceReportRouteReady": ready,
            "productLaneClosed": ready,
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
    reentry_gate = {
        "schemaVersion": "video_to_analysis_detector_evaluation_reentry_gate_v1",
        "generatedAt": utc_now_iso(),
        "detectorEvaluationExecutionReady": False,
        "detectorEvaluationReentryPlanReady": ready,
        "requiredNextLever": NEXT_DETECTOR_REENTRY_PLAN if ready else NEXT_ROUTE_BINDING,
        "blockedExecutions": ["detector_evaluation", "training", "promotion", "runtime_default_mutation", "downloads"],
    }
    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = goal
    false_flags["runtimeDefaultMutationAllowed"] = goal
    summary = {
        "batchName": "video_to_analysis_post_release_monitoring_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "postReleaseMonitoringClosed": goal,
        "postReleaseMonitoringRouteReady": goal,
        **false_flags,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "runtimeDefaultRolloutClosed": goal,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="post_release_monitoring_closeout_summary.json",
        summary=summary,
        artifacts={
            "post_release_monitoring_capability_matrix.json": capability_matrix,
            "detector_evaluation_reentry_gate.json": reentry_gate,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Post Release Monitoring Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis post-release monitoring.", run_video_to_analysis_post_release_monitoring_closeout)


if __name__ == "__main__":
    main()
