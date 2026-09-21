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

DEFAULT_PLAN_DIR_NAME = "video_to_analysis_finish_line_product_execution_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_product_execution_approval_v1"

BLOCKER_PLAN_MISSING = "video_to_analysis_finish_line_product_execution_plan_missing"
BLOCKER_SCOPE_GAP = "video_to_analysis_finish_line_product_execution_scope_gap"
NEXT_PLAN = "video_to_analysis_finish_line_product_execution_plan"
NEXT_SCOPE_REPAIR = "video_to_analysis_finish_line_product_execution_scope_repair"
NEXT_PRODUCT_EXECUTION = "product_video_to_analysis_finish_line_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_approval",
                "successCriteria": [
                    "approve bounded product route and bundle smoke only",
                    "keep normal match storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, and runtime-default mutation blocked",
                ],
                "failureAdaptation": "If product execution-plan truth is missing, route back to product execution planning.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_scope_repair",
                "successCriteria": [
                    "repair only bounded product execution scope",
                    "do not execute route or bundle smoke inside the approval batch",
                ],
                "failureAdaptation": "If the scope cannot stay bounded and mutation-free, keep execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "video_to_analysis_finish_line_product_execution_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to product execution plan, scope repair, or bounded product execution.",
            },
        ],
    }


def _plan_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineProductExecutionPlanReady") is True
        and summary.get("allowedExecutionMode") == "bounded_product_route_and_bundle_smoke"
        and guardrails_false(summary)
        and isinstance(scope, dict)
        and scope.get("executionPlanReady") is True
        and scope.get("allowedExecutionMode") == "bounded_product_route_and_bundle_smoke"
        and scope.get("sourceRoutePaths", {}).get("api") == "/api/video-to-analysis/finish-line"
        and scope.get("sourceRoutePaths", {}).get("html") == "/video-to-analysis/finish-line"
        and scope.get("normalMatchStorageMutationAllowed") is False
        and scope.get("isolatedBenchmarkStorageMutationAllowed") is True
        and scope.get("dataDownloadAllowed") is False
        and scope.get("videoDownloadAllowed") is False
        and scope.get("trainingAllowed") is False
        and scope.get("promotionAllowed") is False
        and scope.get("runtimeDefaultMutationAllowed") is False
    )


def run_video_to_analysis_finish_line_product_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    plan_root = root / DEFAULT_PLAN_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    plan_summary = load_json(plan_root / "finish_line_product_execution_plan_summary.json")
    plan_scope = load_json(plan_root / "finish_line_product_execution_scope.json")
    ready = _plan_ready(plan_summary, plan_scope)

    approved_scope = {
        "schemaVersion": "video_to_analysis_finish_line_product_approved_execution_scope_v1",
        "generatedAt": utc_now_iso(),
        "finishLineProductExecutionApproved": ready,
        "approvedExecutionMode": "bounded_product_route_and_bundle_smoke" if ready else None,
        "allowedApiRoutePath": "/api/video-to-analysis/finish-line",
        "allowedHtmlRoutePath": "/video-to-analysis/finish-line",
        "allowedRunner": "product_video_to_analysis_finish_line_execution",
        "allowedInputPlanDir": DEFAULT_PLAN_DIR_NAME,
        "allowedOutputDir": "product_video_to_analysis_finish_line_execution_v1",
        "normalMatchStorageMutationAllowed": False,
        "isolatedBenchmarkStorageMutationAllowed": ready,
        "detectorEvaluationAllowed": False,
        "candidateEvaluationAllowed": False,
        "candidateReadyForEvaluationAllowed": False,
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }
    guardrail_checks = {
        "productExecutionPlanReady": ready,
        "boundedRouteSmokeOnly": approved_scope["approvedExecutionMode"] == "bounded_product_route_and_bundle_smoke" if ready else False,
        "normalMatchStorageMutationStillBlocked": approved_scope["normalMatchStorageMutationAllowed"] is False,
        "detectorEvaluationStillBlocked": approved_scope["detectorEvaluationAllowed"] is False,
        "downloadStillBlocked": approved_scope["dataDownloadAllowed"] is False and approved_scope["videoDownloadAllowed"] is False,
        "trainingStillBlocked": approved_scope["trainingAllowed"] is False,
        "promotionStillBlocked": approved_scope["promotionAllowed"] is False,
        "candidateReadinessStillBlocked": approved_scope["candidateReadyForEvaluationAllowed"] is False,
        "runtimeMutationStillBlocked": approved_scope["runtimeDefaultMutationAllowed"] is False,
    }
    guardrail = {
        "schemaVersion": "video_to_analysis_finish_line_product_execution_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **guardrail_checks,
        "approvalGuardrailPassed": all(guardrail_checks.values()),
    }

    if not ready:
        primary_blocker = BLOCKER_PLAN_MISSING
        next_lever = NEXT_PLAN
        goal = False
        english = "Finish-line product execution-plan truth is missing or unsafe; rerun product execution planning."
    elif guardrail["approvalGuardrailPassed"] is not True:
        primary_blocker = BLOCKER_SCOPE_GAP
        next_lever = NEXT_SCOPE_REPAIR
        goal = False
        english = "Finish-line product execution approval scope is unsafe; repair scope before execution."
    else:
        primary_blocker = None
        next_lever = NEXT_PRODUCT_EXECUTION
        goal = True
        english = "Finish-line product execution is approved for bounded route and bundle smoke only. Normal match storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, and runtime mutation remain blocked."

    summary = {
        "batchName": "video_to_analysis_finish_line_product_execution_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineProductExecutionApproved": goal,
        "finishLineProductExecutionReady": goal,
        "approvedExecutionMode": "bounded_product_route_and_bundle_smoke" if goal else None,
        "normalMatchStorageMutationApproved": False,
        "isolatedBenchmarkStorageMutationApproved": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "product_execution_plan_missing", "selected": primary_blocker == BLOCKER_PLAN_MISSING, "primaryBlocker": BLOCKER_PLAN_MISSING, "nextRecommendedNextLever": NEXT_PLAN},
            {"condition": "product_execution_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "bounded_product_execution_approved", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_EXECUTION},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_product_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_finish_line_product_execution_scope.json": approved_scope,
            "product_execution_approval_guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Product Execution Approval",
    )


def main() -> None:
    main_for("Approve bounded product finish-line execution.", run_video_to_analysis_finish_line_product_execution_approval)


if __name__ == "__main__":
    main()
