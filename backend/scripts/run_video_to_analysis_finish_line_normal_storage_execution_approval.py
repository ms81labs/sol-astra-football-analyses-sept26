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
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_UAT_DIR_NAME = "video_to_analysis_finish_line_user_acceptance_trial_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_normal_storage_execution_approval_v1"

BLOCKER_UAT_MISSING = "video_to_analysis_finish_line_user_acceptance_trial_missing"
BLOCKER_SCOPE_GAP = "video_to_analysis_finish_line_normal_storage_execution_scope_gap"
NEXT_UAT = "video_to_analysis_finish_line_user_acceptance_trial"
NEXT_SCOPE_REPAIR = "video_to_analysis_finish_line_normal_storage_execution_scope_repair"
NEXT_NORMAL_STORAGE_SMOKE = "product_video_to_analysis_normal_storage_smoke"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "normal_storage_execution_approval",
                "successCriteria": [
                    "approve only controlled product video-to-analysis normal-storage smoke",
                    "keep detector evaluation, downloads, training, promotion, candidate readiness, and runtime-default mutation blocked",
                    "do not execute normal match storage mutation in the approval batch",
                ],
                "failureAdaptation": "If UAT truth is missing, route back to user acceptance trial.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "normal_storage_execution_scope_repair",
                "successCriteria": ["repair only scope and runner contract", "do not execute the smoke"],
                "failureAdaptation": "If the scope cannot stay controlled, keep normal storage execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "normal_storage_execution_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to UAT, scope repair, or controlled normal-storage smoke.",
            },
        ],
    }


def _uat_ready(summary: dict[str, Any] | None, checklist: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("userAcceptanceTrialPassed") is True
        and summary.get("normalStorageExecutionApprovalReady") is True
        and guardrails_false(summary)
        and isinstance(checklist, dict)
        and checklist.get("allChecklistItemsPassed") is True
    )


def run_video_to_analysis_finish_line_normal_storage_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    uat_root = root / DEFAULT_UAT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    uat_summary = load_json(uat_root / "finish_line_user_acceptance_trial_summary.json")
    checklist = load_json(uat_root / "user_acceptance_checklist.json")
    ready = _uat_ready(uat_summary, checklist)

    approved_scope = {
        "schemaVersion": "video_to_analysis_finish_line_normal_storage_approved_execution_scope_v1",
        "generatedAt": utc_now_iso(),
        "normalStorageExecutionApproved": ready,
        "approvedExecutionMode": "controlled_product_video_to_analysis_normal_storage_smoke" if ready else None,
        "allowedRunner": "backend/scripts/run_product_video_to_analysis_smoke.py",
        "allowedOutputRoot": "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/product_video_to_analysis_smoke_v1",
        "normalMatchStorageMutationAllowed": ready,
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
        "userAcceptanceTrialReady": ready,
        "normalStorageMutationApprovedButNotExecuted": ready,
        "detectorEvaluationStillBlocked": approved_scope["detectorEvaluationAllowed"] is False,
        "downloadsStillBlocked": approved_scope["dataDownloadAllowed"] is False and approved_scope["videoDownloadAllowed"] is False,
        "trainingStillBlocked": approved_scope["trainingAllowed"] is False,
        "promotionStillBlocked": approved_scope["promotionAllowed"] is False,
        "candidateReadinessStillBlocked": approved_scope["candidateReadyForEvaluationAllowed"] is False,
        "runtimeMutationStillBlocked": approved_scope["runtimeDefaultMutationAllowed"] is False,
    }
    guardrail = {
        "schemaVersion": "video_to_analysis_finish_line_normal_storage_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **guardrail_checks,
        "approvalGuardrailPassed": all(guardrail_checks.values()),
    }

    if not ready:
        primary_blocker = BLOCKER_UAT_MISSING
        next_lever = NEXT_UAT
        goal = False
        english = "Finish-line user acceptance trial is missing or unsafe; run UAT before normal-storage execution approval."
    elif guardrail["approvalGuardrailPassed"] is not True:
        primary_blocker = BLOCKER_SCOPE_GAP
        next_lever = NEXT_SCOPE_REPAIR
        goal = False
        english = "Normal-storage execution approval scope is unsafe; repair scope before execution."
    else:
        primary_blocker = None
        next_lever = NEXT_NORMAL_STORAGE_SMOKE
        goal = True
        english = "Controlled normal-storage product smoke is approved. Detector evaluation, downloads, training, promotion, candidate readiness, and runtime mutation remain blocked."

    summary = {
        "batchName": "video_to_analysis_finish_line_normal_storage_execution_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "normalStorageExecutionApproved": goal,
        "approvedExecutionMode": "controlled_product_video_to_analysis_normal_storage_smoke" if goal else None,
        "normalMatchStorageMutationApproved": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "user_acceptance_trial_missing", "selected": primary_blocker == BLOCKER_UAT_MISSING, "primaryBlocker": BLOCKER_UAT_MISSING, "nextRecommendedNextLever": NEXT_UAT},
            {"condition": "normal_storage_execution_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "normal_storage_execution_approved", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_NORMAL_STORAGE_SMOKE},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_normal_storage_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_normal_storage_execution_scope.json": approved_scope,
            "normal_storage_execution_approval_guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Normal Storage Execution Approval",
    )


def main() -> None:
    main_for("Approve controlled normal-storage product smoke.", run_video_to_analysis_finish_line_normal_storage_execution_approval)


if __name__ == "__main__":
    main()
