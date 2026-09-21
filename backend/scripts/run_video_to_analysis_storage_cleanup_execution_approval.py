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
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_DRY_RUN_DIR_NAME = "video_to_analysis_storage_cleanup_dry_run_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_cleanup_execution_approval_v1"

BLOCKER_DRY_RUN_MISSING = "video_to_analysis_storage_cleanup_dry_run_missing"
BLOCKER_EMPTY_SCOPE = "video_to_analysis_storage_cleanup_execution_scope_empty"
BLOCKER_GUARDRAIL_GAP = "video_to_analysis_storage_cleanup_execution_approval_guardrail_gap"
NEXT_DRY_RUN = "video_to_analysis_storage_cleanup_dry_run_execution"
NEXT_GUARDRAIL_REPAIR = "video_to_analysis_storage_cleanup_execution_approval_repair"
NEXT_BOUNDED_EXECUTION = "video_to_analysis_storage_cleanup_bounded_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_cleanup_execution_approval",
                "successCriteria": [
                    "consume completed dry-run cleanup report",
                    "approve only the dry-run candidate scope for a future bounded runner",
                    "do not delete files in the approval batch",
                ],
                "failureAdaptation": "If dry-run truth is missing or empty, route back to dry-run execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_cleanup_execution_scope_repair",
                "successCriteria": ["repair only candidate scope metadata and guardrails"],
                "failureAdaptation": "If scope remains unsafe, keep execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_cleanup_execution_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not run cleanup execution.",
            },
        ],
    }


def _dry_run_ready(summary: dict[str, Any] | None, report: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("storageCleanupDryRunExecuted") is True
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and summary.get("actualDeletedPathCount") == 0
        and summary.get("actualReclaimedBytes") == 0
        and isinstance(report, dict)
        and report.get("actualDeletedPathCount") == 0
        and report.get("actualReclaimedBytes") == 0
        and report.get("cleanupMutationExecuted") is False
        and report.get("generatedTruthDeleteAllowed") is False
    )


def _candidate_rows(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    rows = report.get("simulatedRows")
    if not isinstance(rows, list):
        return []
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("relativePath"):
            continue
        cleaned.append(
            {
                "relativePath": row["relativePath"],
                "approvedAction": "delete_or_archive_generated_truth_candidate",
                "approvedBytes": int(row.get("simulatedBytes") or 0),
                "sourceDryRunAction": row.get("simulatedAction"),
            }
        )
    return cleaned


def _approved_scope(dry_run_dir: Path, rows: list[dict[str, Any]], ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_approved_execution_scope_v1",
        "generatedAt": utc_now_iso(),
        "sourceDryRunDir": dry_run_dir.name,
        "cleanupExecutionApproved": ready and bool(rows),
        "approvedExecutionMode": "bounded_generated_truth_archive_delete" if ready and rows else None,
        "approvedRunner": "backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py",
        "approvedCandidateRows": rows,
        "approvedCandidateCount": len(rows),
        "approvedCandidateBytes": sum(row["approvedBytes"] for row in rows),
        "cleanupMutationAllowedInApprovalBatch": False,
        "generatedTruthDeleteAllowedInApprovalBatch": False,
        "normalMatchStorageMutationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "requiresFinalRunnerGuardrailAudit": True,
        "requiresCandidatePathExistenceCheck": True,
        "requiresNoLatestVersionDeletionCheck": True,
    }


def _guardrail_audit(dry_run_ready: bool, scope: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "dryRunReady": dry_run_ready,
        "scopeHasCandidates": scope["approvedCandidateCount"] > 0,
        "approvalBatchDidNotAllowMutation": scope["cleanupMutationAllowedInApprovalBatch"] is False,
        "approvalBatchDidNotAllowGeneratedTruthDeletion": scope["generatedTruthDeleteAllowedInApprovalBatch"] is False,
        "normalStorageStillBlocked": scope["normalMatchStorageMutationAllowed"] is False,
        "trainingStillBlocked": scope["trainingAllowed"] is False,
        "promotionStillBlocked": scope["promotionAllowed"] is False,
        "runtimeMutationStillBlocked": scope["runtimeDefaultMutationAllowed"] is False,
        "boundedRunnerRequired": scope["approvedRunner"] == "backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py",
        "finalGuardrailAuditRequired": scope["requiresFinalRunnerGuardrailAudit"] is True,
    }
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_execution_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "approvalGuardrailPassed": all(checks.values()),
    }


def run_video_to_analysis_storage_cleanup_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    dry_run_dir = root / DEFAULT_DRY_RUN_DIR_NAME

    dry_run_summary = load_json(dry_run_dir / "storage_cleanup_dry_run_execution_summary.json")
    dry_run_report = load_json(dry_run_dir / "cleanup_dry_run_report.json")
    dry_run_ready = _dry_run_ready(dry_run_summary, dry_run_report)
    rows = _candidate_rows(dry_run_report)
    scope = _approved_scope(dry_run_dir, rows, dry_run_ready)
    guardrail = _guardrail_audit(dry_run_ready, scope)

    if not dry_run_ready:
        goal = False
        primary_blocker = BLOCKER_DRY_RUN_MISSING
        next_lever = NEXT_DRY_RUN
        english = "Storage cleanup dry-run truth is missing or unsafe; rerun dry-run execution before approval."
    elif not rows:
        goal = False
        primary_blocker = BLOCKER_EMPTY_SCOPE
        next_lever = NEXT_DRY_RUN
        english = "Storage cleanup dry-run produced no candidate scope; rerun dry-run or close the cleanup lane."
    elif guardrail["approvalGuardrailPassed"] is not True:
        goal = False
        primary_blocker = BLOCKER_GUARDRAIL_GAP
        next_lever = NEXT_GUARDRAIL_REPAIR
        english = "Storage cleanup execution approval guardrails are unsafe; repair approval scope before execution."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_BOUNDED_EXECUTION
        english = "Storage cleanup execution scope is approved for a future bounded runner. No cleanup mutation happened in this approval batch."

    summary = {
        "batchName": "video_to_analysis_storage_cleanup_execution_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "cleanupExecutionApproved": goal,
        "approvedExecutionMode": scope["approvedExecutionMode"] if goal else None,
        "approvedCandidateCount": scope["approvedCandidateCount"],
        "approvedCandidateBytes": scope["approvedCandidateBytes"],
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_storage_cleanup_execution_approval_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "dry_run_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_DRY_RUN_MISSING,
                "primaryBlocker": BLOCKER_DRY_RUN_MISSING,
                "nextRecommendedNextLever": NEXT_DRY_RUN,
            },
            {
                "condition": "execution_scope_empty",
                "selected": primary_blocker == BLOCKER_EMPTY_SCOPE,
                "primaryBlocker": BLOCKER_EMPTY_SCOPE,
                "nextRecommendedNextLever": NEXT_DRY_RUN,
            },
            {
                "condition": "execution_approval_guardrail_gap",
                "selected": primary_blocker == BLOCKER_GUARDRAIL_GAP,
                "primaryBlocker": BLOCKER_GUARDRAIL_GAP,
                "nextRecommendedNextLever": NEXT_GUARDRAIL_REPAIR,
            },
            {
                "condition": "execution_scope_approved",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_BOUNDED_EXECUTION,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_cleanup_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_cleanup_execution_scope.json": scope,
            "cleanup_execution_approval_guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Cleanup Execution Approval",
    )


def main() -> None:
    main_for("Approve bounded storage cleanup execution scope without deleting anything.", run_video_to_analysis_storage_cleanup_execution_approval)


if __name__ == "__main__":
    main()
