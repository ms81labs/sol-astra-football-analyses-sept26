from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

DEFAULT_PRODUCT_CLOSEOUT_DIR_NAME = "video_to_analysis_product_lane_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_post_release_monitoring_plan_v1"

BLOCKER_PRODUCT_CLOSEOUT_MISSING = "video_to_analysis_product_lane_closeout_missing"
NEXT_PRODUCT_CLOSEOUT = "video_to_analysis_product_lane_closeout"
NEXT_ROUTE_BINDING = "video_to_analysis_post_release_monitoring_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_post_release_monitoring_plan",
                "successCriteria": ["define post-release health checks", "keep all mutation/evaluation lanes closed"],
                "failureAdaptation": "If product lane closeout truth is missing, route back to product lane closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "post_release_monitoring_scope_repair",
                "successCriteria": ["repair only monitoring check scope and route contract"],
                "failureAdaptation": "If monitoring scope remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "post_release_monitoring_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to closeout, scope repair, or monitoring route binding.",
            },
        ],
    }


def _product_closeout_ready(summary: dict[str, Any] | None, matrix: dict[str, Any] | None) -> bool:
    caps = matrix.get("closedCapabilities") if isinstance(matrix, dict) else {}
    guardrails = matrix.get("guardrails") if isinstance(matrix, dict) else {}
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisProductLaneClosed") is True
        and summary.get("videoToAnalysisProductPathReady") is True
        and summary.get("operatorHandoffRouteReady") is True
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
        and caps.get("operatorHandoffRouteReady") is True
        and caps.get("releaseCandidateClosed") is True
        and caps.get("v7_3RuntimeDefaultActive") is True
        and guardrails.get("detectorEvaluationReady") is False
        and guardrails.get("trainingReady") is False
        and guardrails.get("promotionReady") is False
        and guardrails.get("runtimeDefaultMutationReady") is True
    )


def _monitoring_plan() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_post_release_monitoring_plan_v1",
        "generatedAt": utc_now_iso(),
        "activeRuntimeDefaultVersion": "v7.3",
        "runtimeDefaultRolloutClosed": True,
        "monitoringCadence": "per_release_and_daily_smoke",
        "monitoringChecks": [
            {
                "id": "operator_handoff_route_smoke",
                "route": "/api/video-to-analysis/operator-handoff",
                "expected": "200 with operator handoff view model",
            },
            {
                "id": "acceptance_report_route_smoke",
                "route": "/api/video-to-analysis/acceptance-report",
                "expected": "200 with 5 / 5 acceptance result",
            },
            {
                "id": "finish_line_route_smoke",
                "route": "/api/video-to-analysis/finish-line",
                "expected": "200 with finish-line view model",
            },
            {
                "id": "guardrail_false_flags",
                "expected": "detector evaluation, downloads, training, promotion, and candidate readiness remain false while v7.3 remains active",
            },
        ],
        "escalationPolicy": {
            "routeSmokeFailure": "video_to_analysis_post_release_route_regression_debug",
            "guardrailRegression": "video_to_analysis_post_release_guardrail_regression_debug",
        },
    }


def run_video_to_analysis_post_release_monitoring_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_PRODUCT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "product_lane_closeout_summary.json")
    capability_matrix = load_json(closeout_root / "product_lane_capability_matrix.json")
    ready = _product_closeout_ready(closeout_summary, capability_matrix)

    if ready:
        primary_blocker = None
        next_lever = NEXT_ROUTE_BINDING
        goal = True
        english = "Post-release monitoring plan is ready. Bind the monitoring route next."
    else:
        primary_blocker = BLOCKER_PRODUCT_CLOSEOUT_MISSING
        next_lever = NEXT_PRODUCT_CLOSEOUT
        goal = False
        english = "Product lane closeout is missing or unsafe; close product lane before monitoring plan."

    plan = _monitoring_plan() if ready else {"schemaVersion": "video_to_analysis_post_release_monitoring_plan_v1", "generatedAt": utc_now_iso(), "monitoringChecks": []}
    route_contract = {
        "schemaVersion": "video_to_analysis_post_release_monitoring_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/post-release-monitoring",
        "htmlRoutePath": "/video-to-analysis/post-release-monitoring",
        "postReleaseMonitoringRouteReady": ready,
        "allowsDetectorEvaluation": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsDownloads": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "activeRuntimeDefaultVersion": "v7.3" if ready else None,
    }
    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = goal
    false_flags["runtimeDefaultMutationAllowed"] = goal
    summary = {
        "batchName": "video_to_analysis_post_release_monitoring_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "postReleaseMonitoringPlanReady": goal,
        "videoToAnalysisProductPathReady": goal,
        "monitoringCheckCount": len(plan.get("monitoringChecks", [])),
        **false_flags,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "runtimeDefaultRolloutClosed": goal,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="post_release_monitoring_plan_summary.json",
        summary=summary,
        artifacts={
            "post_release_monitoring_plan.json": plan,
            "post_release_monitoring_route_contract.json": route_contract,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Post Release Monitoring Plan",
    )


def main() -> None:
    main_for("Plan video-to-analysis post-release monitoring.", run_video_to_analysis_post_release_monitoring_plan)


if __name__ == "__main__":
    main()
