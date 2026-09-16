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
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_storage_cleanup_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_cleanup_dry_run_execution_v1"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_storage_cleanup_dry_run_approval_missing"
BLOCKER_GUARDRAIL_GAP = "video_to_analysis_storage_cleanup_dry_run_guardrail_gap"
NEXT_APPROVAL = "video_to_analysis_storage_cleanup_approval"
NEXT_GUARDRAIL_REPAIR = "video_to_analysis_storage_cleanup_dry_run_guardrail_repair"
NEXT_EXECUTION_APPROVAL = "video_to_analysis_storage_cleanup_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_cleanup_dry_run_execution",
                "successCriteria": [
                    "consume storage cleanup approval contract",
                    "simulate cleanup candidate actions without deleting files",
                    "write dry-run report and keep all mutation guardrails false",
                ],
                "failureAdaptation": "If approval truth is missing, route back to storage cleanup approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_cleanup_dry_run_scope_repair",
                "successCriteria": ["repair only dry-run report metadata or candidate accounting"],
                "failureAdaptation": "If dry-run scope becomes unsafe, keep deletion blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_cleanup_dry_run_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not delete artifacts.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("storageCleanupApprovalReady") is True
        and summary.get("storageCleanupDryRunApproved") is True
        and summary.get("cleanupExecutionApproved") is False
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and isinstance(contract, dict)
        and contract.get("storageCleanupDryRunApproved") is True
        and contract.get("approvedNextAction") == "dry_run_only_no_deletion"
        and contract.get("cleanupExecutionApproved") is False
        and contract.get("cleanupMutationExecuted") is False
        and contract.get("generatedTruthDeleteAllowed") is False
        and isinstance(manifest, dict)
        and manifest.get("cleanupMutationExecuted") is False
        and manifest.get("generatedTruthDeleteAllowed") is False
        and manifest.get("deletionAllowedInThisBatch") is False
    )


def _dry_run_plan(
    *,
    approval_dir: Path,
    manifest: dict[str, Any] | None,
    ready: bool,
) -> dict[str, Any]:
    rows = manifest.get("cleanupCandidateRows", []) if isinstance(manifest, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_dry_run_execution_plan_v1",
        "generatedAt": utc_now_iso(),
        "sourceApprovalDir": approval_dir.name,
        "executionMode": "dry_run_no_deletion",
        "dryRunApproved": ready,
        "cleanupCandidateCount": len(rows),
        "cleanupCandidateBytes": sum(int(row.get("sizeBytes") or 0) for row in rows),
        "candidateRows": rows,
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "deletionAllowedInThisBatch": False,
        "requiresSeparateDeletionApproval": True,
    }


def _dry_run_report(plan: dict[str, Any]) -> dict[str, Any]:
    rows = plan["candidateRows"]
    simulated_rows = [
        {
            "relativePath": row.get("relativePath"),
            "simulatedAction": "would_archive_or_delete_after_explicit_execution_approval",
            "simulatedBytes": row.get("sizeBytes", 0),
            "actualDeleted": False,
        }
        for row in rows
    ]
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_dry_run_report_v1",
        "generatedAt": utc_now_iso(),
        "simulatedDeletedPathCount": len(simulated_rows),
        "simulatedReclaimableBytes": sum(int(row.get("simulatedBytes") or 0) for row in simulated_rows),
        "actualDeletedPathCount": 0,
        "actualReclaimedBytes": 0,
        "simulatedRows": simulated_rows,
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "deletionAllowedInThisBatch": False,
    }


def _guardrail_audit(ready: bool, plan: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "approvalReady": ready,
        "executionModeIsDryRun": plan["executionMode"] == "dry_run_no_deletion",
        "cleanupMutationStillBlocked": plan["cleanupMutationExecuted"] is False and report["cleanupMutationExecuted"] is False,
        "generatedTruthDeletionStillBlocked": plan["generatedTruthDeleteAllowed"] is False and report["generatedTruthDeleteAllowed"] is False,
        "noActualDeletion": report["actualDeletedPathCount"] == 0 and report["actualReclaimedBytes"] == 0,
        "separateDeletionApprovalRequired": plan["requiresSeparateDeletionApproval"] is True,
    }
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_dry_run_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "dryRunGuardrailPassed": all(checks.values()),
    }


def run_video_to_analysis_storage_cleanup_dry_run_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    approval_dir = root / DEFAULT_APPROVAL_DIR_NAME

    approval_summary = load_json(approval_dir / "storage_cleanup_approval_summary.json")
    approval_contract = load_json(approval_dir / "storage_cleanup_approval_contract.json")
    approval_manifest = load_json(approval_dir / "cleanup_candidate_manifest.json")
    ready = _approval_ready(approval_summary, approval_contract, approval_manifest)
    plan = _dry_run_plan(approval_dir=approval_dir, manifest=approval_manifest, ready=ready)
    report = _dry_run_report(plan)
    guardrail = _guardrail_audit(ready, plan, report)

    if not ready:
        goal = False
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        english = "Storage cleanup dry run approval is missing or unsafe; run storage cleanup approval first."
    elif guardrail["dryRunGuardrailPassed"] is not True:
        goal = False
        primary_blocker = BLOCKER_GUARDRAIL_GAP
        next_lever = NEXT_GUARDRAIL_REPAIR
        english = "Storage cleanup dry-run guardrails are unsafe; repair dry-run scope before any deletion approval."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_EXECUTION_APPROVAL
        english = "Storage cleanup dry run completed without deleting anything. Next step is a separate execution approval if deletion/archive should happen."

    summary = {
        "batchName": "video_to_analysis_storage_cleanup_dry_run_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "storageCleanupDryRunExecuted": goal,
        "cleanupDeletionReady": False,
        "cleanupCandidateCount": plan["cleanupCandidateCount"],
        "cleanupCandidateBytes": plan["cleanupCandidateBytes"],
        "simulatedDeletedPathCount": report["simulatedDeletedPathCount"],
        "simulatedReclaimableBytes": report["simulatedReclaimableBytes"],
        "actualDeletedPathCount": report["actualDeletedPathCount"],
        "actualReclaimedBytes": report["actualReclaimedBytes"],
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_storage_cleanup_dry_run_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "storage_cleanup_approval_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_APPROVAL_MISSING,
                "primaryBlocker": BLOCKER_APPROVAL_MISSING,
                "nextRecommendedNextLever": NEXT_APPROVAL,
            },
            {
                "condition": "storage_cleanup_dry_run_guardrail_gap",
                "selected": primary_blocker == BLOCKER_GUARDRAIL_GAP,
                "primaryBlocker": BLOCKER_GUARDRAIL_GAP,
                "nextRecommendedNextLever": NEXT_GUARDRAIL_REPAIR,
            },
            {
                "condition": "storage_cleanup_dry_run_completed",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_EXECUTION_APPROVAL,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_cleanup_dry_run_execution_summary.json",
        summary=summary,
        artifacts={
            "cleanup_dry_run_execution_plan.json": plan,
            "cleanup_dry_run_report.json": report,
            "guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Cleanup Dry Run Execution",
    )


def main() -> None:
    main_for("Execute storage cleanup dry run without deleting anything.", run_video_to_analysis_storage_cleanup_dry_run_execution)


if __name__ == "__main__":
    main()
