from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (
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

DEFAULT_INTEGRATION_DIR_NAME = "video_to_analysis_finish_line_integration_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_execution_approval_v1"

BLOCKER_INTEGRATION_MISSING = "video_to_analysis_finish_line_integration_plan_missing"
BLOCKER_SCOPE_GAP = "video_to_analysis_finish_line_execution_scope_gap"
NEXT_INTEGRATION_PLAN = "video_to_analysis_finish_line_integration_plan"
NEXT_SCOPE_REPAIR = "video_to_analysis_finish_line_scope_repair"
NEXT_PRODUCT_SMOKE = "product_video_to_analysis_smoke"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_finish_line_execution_approval",
                "successCriteria": [
                    "approve isolated product video-to-analysis smoke only",
                    "keep normal match storage mutation, training, promotion, candidate readiness, downloads, and runtime-default mutation blocked",
                ],
                "failureAdaptation": "If integration-plan truth is missing, route back to finish-line integration planning.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "video_to_analysis_finish_line_scope_repair",
                "successCriteria": [
                    "repair only execution scope and allowed runner contract",
                    "do not execute the product smoke in the approval batch",
                ],
                "failureAdaptation": "If the scope cannot stay isolated, keep execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "video_to_analysis_finish_line_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to integration plan, scope repair, or product video-to-analysis smoke.",
            },
        ],
    }


def _integration_ready(summary: dict[str, Any] | None, readiness: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineIntegrationPlanReady") is True
        and summary.get("finishLineExecutionApprovalReady") is True
        and summary.get("sourceReportReady") is True
        and summary.get("productGoal") == "video_to_auditable_match_analysis_data"
        and guardrails_false(summary)
        and isinstance(readiness, dict)
        and readiness.get("executionApprovalReady") is True
        and readiness.get("requiresNoPromotionBoundary") is True
        and readiness.get("requiresRunPodHygieneCheck") is True
    )


def run_video_to_analysis_finish_line_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    integration_root = root / DEFAULT_INTEGRATION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    integration_summary = load_json(integration_root / "finish_line_integration_plan_summary.json")
    readiness = load_json(integration_root / "finish_line_execution_readiness.json")
    integration_ready = _integration_ready(integration_summary, readiness)

    approved_scope = {
        "schemaVersion": "video_to_analysis_finish_line_approved_execution_scope_v1",
        "generatedAt": utc_now_iso(),
        "finishLineExecutionApproved": integration_ready,
        "approvedExecutionMode": "isolated_product_video_to_analysis_smoke" if integration_ready else None,
        "allowedRunner": "backend/scripts/run_product_video_to_analysis_smoke.py",
        "allowedOutputRoot": "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/product_video_to_analysis_smoke_v1",
        "normalMatchStorageMutationAllowed": False,
        "isolatedBenchmarkStorageMutationAllowed": integration_ready,
        "detectorEvaluationAllowed": False,
        "candidateEvaluationAllowed": False,
        "candidateReadyForEvaluationAllowed": False,
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "requiresRunPodHygieneCheck": True,
    }
    guardrail_checks = {
        "integrationReady": integration_ready,
        "isolatedBenchmarkStorageMutationScoped": approved_scope["isolatedBenchmarkStorageMutationAllowed"] is integration_ready,
        "normalMatchStorageMutationStillBlocked": approved_scope["normalMatchStorageMutationAllowed"] is False,
        "detectorEvaluationStillBlocked": approved_scope["detectorEvaluationAllowed"] is False,
        "downloadStillBlocked": approved_scope["dataDownloadAllowed"] is False and approved_scope["videoDownloadAllowed"] is False,
        "trainingStillBlocked": approved_scope["trainingAllowed"] is False,
        "promotionStillBlocked": approved_scope["promotionAllowed"] is False,
        "runtimeMutationStillBlocked": approved_scope["runtimeDefaultMutationAllowed"] is False,
    }
    guardrail = {
        "schemaVersion": "video_to_analysis_finish_line_execution_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **guardrail_checks,
        "approvalGuardrailPassed": all(guardrail_checks.values()),
    }
    if not integration_ready:
        primary_blocker = BLOCKER_INTEGRATION_MISSING
        next_lever = NEXT_INTEGRATION_PLAN
        goal = False
        english = "Finish-line integration-plan truth is missing or unsafe; rerun integration planning."
    elif guardrail["approvalGuardrailPassed"] is not True:
        primary_blocker = BLOCKER_SCOPE_GAP
        next_lever = NEXT_SCOPE_REPAIR
        goal = False
        english = "Finish-line execution approval scope is unsafe; repair scope before execution."
    else:
        primary_blocker = None
        next_lever = NEXT_PRODUCT_SMOKE
        goal = True
        english = "Finish-line execution is approved for the isolated product video-to-analysis smoke only. Normal match storage mutation, downloads, training, promotion, candidate readiness, and runtime mutation remain blocked."
    summary = {
        "batchName": "video_to_analysis_finish_line_execution_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineExecutionApproved": goal,
        "finishLineExecutionReady": goal,
        "approvedExecutionMode": "isolated_product_video_to_analysis_smoke" if goal else None,
        "normalMatchStorageMutationApproved": False,
        "isolatedBenchmarkStorageMutationApproved": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "integration_plan_missing", "selected": primary_blocker == BLOCKER_INTEGRATION_MISSING, "primaryBlocker": BLOCKER_INTEGRATION_MISSING, "nextRecommendedNextLever": NEXT_INTEGRATION_PLAN},
            {"condition": "execution_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "isolated_product_smoke_approved", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_SMOKE},
        ],
    }
    artifacts = {
        "approved_finish_line_execution_scope.json": approved_scope,
        "approval_guardrail_audit.json": guardrail,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_execution_approval_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Video To Analysis Finish Line Execution Approval",
    )


def main() -> None:
    main_for("Approve isolated product video-to-analysis finish-line execution.", run_video_to_analysis_finish_line_execution_approval)


if __name__ == "__main__":
    main()
