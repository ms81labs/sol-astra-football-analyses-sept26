from __future__ import annotations

from collections import defaultdict
from contextlib import ExitStack
import os
from pathlib import Path
import re
import stat
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

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_storage_cleanup_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_cleanup_bounded_execution_v1"
APPROVED_DELETE_ACTION = "delete_or_archive_generated_truth_candidate"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_storage_cleanup_execution_approval_missing"
BLOCKER_EMPTY_SCOPE = "video_to_analysis_storage_cleanup_bounded_scope_empty"
BLOCKER_PATH_GUARDRAIL = "video_to_analysis_storage_cleanup_path_guardrail"
BLOCKER_LATEST_VERSION = "video_to_analysis_storage_cleanup_latest_version_guardrail"
BLOCKER_AUTOMATIC_DELETION_DISABLED = "video_to_analysis_storage_cleanup_automatic_deletion_disabled"
NEXT_APPROVAL = "video_to_analysis_storage_cleanup_execution_approval"
NEXT_SCOPE_REPAIR = "video_to_analysis_storage_cleanup_bounded_scope_repair"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_cleanup_bounded_execution",
                "successCriteria": [
                    "consume approved cleanup execution scope",
                    "report approved old-version candidates without deleting",
                    "preserve latest version in every artifact family",
                    "write the automatic-deletion blocker and zero deletion counts",
                ],
                "failureAdaptation": "If approval or guardrails fail, route to approval or scope repair without deleting.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_cleanup_bounded_scope_repair",
                "successCriteria": ["repair only approved candidate scope or latest-version classification"],
                "failureAdaptation": "If scope remains unsafe, keep deletion blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_cleanup_bounded_execution_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not delete.",
            },
        ],
    }


def _version_suffix(name: str) -> int:
    match = re.search(r"_v(\d+)$", name)
    return int(match.group(1)) if match else 0


def _version_prefix(name: str) -> str:
    return re.sub(r"_v\d+$", "", name)


def _open_root(root: Path, opened: ExitStack) -> int:
    absolute_root = root.absolute()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent_fd = os.open(absolute_root.anchor, flags)
    opened.callback(os.close, parent_fd)
    for part in absolute_root.parts[1:]:
        parent_fd = os.open(part, flags, dir_fd=parent_fd)
        opened.callback(os.close, parent_fd)
    return parent_fd


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("cleanupExecutionApproved") is True
        and summary.get("approvedExecutionMode") == "bounded_generated_truth_archive_delete"
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and isinstance(scope, dict)
        and scope.get("cleanupExecutionApproved") is True
        and scope.get("approvedExecutionMode") == "bounded_generated_truth_archive_delete"
        and scope.get("cleanupMutationAllowedInApprovalBatch") is False
        and scope.get("generatedTruthDeleteAllowedInApprovalBatch") is False
        and scope.get("requiresFinalRunnerGuardrailAudit") is True
    )


def _approved_rows(scope: dict[str, Any] | None) -> list[Any]:
    if not isinstance(scope, dict):
        return []
    rows = scope.get("approvedCandidateRows")
    if not isinstance(rows, list):
        return []
    return rows


def _latest_names_by_family(root_fd: int) -> set[str]:
    groups: dict[str, list[str]] = defaultdict(list)
    for name in os.listdir(root_fd):
        if not re.fullmatch(r".+_v\d+", name):
            continue
        entry_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        if stat.S_ISDIR(entry_stat.st_mode):
            groups[_version_prefix(name)].append(name)
    latest_names = set()
    for names in groups.values():
        latest_version = max(map(_version_suffix, names))
        latest_names.update(name for name in names if _version_suffix(name) == latest_version)
    return latest_names


def _validated_targets(
    root_fd: int,
    rows: list[Any],
    output_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    latest_names = _latest_names_by_family(root_fd)
    valid: list[dict[str, Any]] = []
    path_errors: list[dict[str, Any]] = []
    latest_errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            path_errors.append({"guardrailFailure": "approved_row_not_object"})
            continue
        approved_bytes = row.get("approvedBytes", 0)
        if type(approved_bytes) is not int or approved_bytes < 0:
            path_errors.append({**row, "guardrailFailure": "approved_bytes_invalid"})
            continue
        name = row.get("relativePath")
        if not isinstance(name, str) or not name or Path(name).name != name:
            path_errors.append({**row, "guardrailFailure": "path_must_be_one_canonical_child_name"})
            continue
        if name in seen:
            path_errors.append({**row, "guardrailFailure": "duplicate_target"})
            continue
        seen.add(name)
        if name == output_name:
            path_errors.append({**row, "guardrailFailure": "runner_output_delete_blocked"})
            continue
        if row.get("approvedAction") != APPROVED_DELETE_ACTION:
            path_errors.append({**row, "guardrailFailure": "delete_action_not_approved"})
            continue
        if not re.fullmatch(r".+_v\d+", name):
            path_errors.append({**row, "guardrailFailure": "target_name_not_versioned"})
            continue
        try:
            target_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except (OSError, ValueError):
            path_errors.append({**row, "guardrailFailure": "path_missing_or_unsafe"})
            continue
        if not stat.S_ISDIR(target_stat.st_mode):
            path_errors.append({**row, "guardrailFailure": "target_not_directory"})
            continue
        if name in latest_names:
            latest_errors.append({**row, "guardrailFailure": "latest_version_delete_blocked"})
            continue
        valid.append(row)
    return valid, path_errors, latest_errors


def _guardrail_audit(
    *,
    approval_ready: bool,
    rows: list[Any],
    path_errors: list[dict[str, Any]],
    latest_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "automaticDeletionEnabled": False,
        "approvalReady": approval_ready,
        "approvedScopeNonEmpty": len(rows) > 0,
        "allApprovedPathsContainedAndExisting": len(path_errors) == 0,
        "latestVersionDeletionBlockedCountIsZero": len(latest_errors) == 0,
        "deletedOnlyValidatedTargets": True,
        "normalStorageStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
    }
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_bounded_execution_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "boundedExecutionGuardrailPassed": all(checks.values()),
    }


def run_video_to_analysis_storage_cleanup_bounded_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    approval_dir = root / DEFAULT_APPROVAL_DIR_NAME
    approval_summary = load_json(approval_dir / "storage_cleanup_execution_approval_summary.json")
    approval_scope = load_json(approval_dir / "approved_cleanup_execution_scope.json")
    approval_ready = _approval_ready(approval_summary, approval_scope)
    rows = _approved_rows(approval_scope)
    with ExitStack() as opened:
        try:
            root_fd = _open_root(root, opened)
            output_parts = output_root.resolve().relative_to(root.resolve()).parts
            output_name = output_parts[0] if output_parts else ""
            valid_targets, path_errors, latest_errors = _validated_targets(root_fd, rows, output_name)
        except (OSError, ValueError):
            valid_targets = []
            path_errors = [{"guardrailFailure": "candidate_root_cannot_be_pinned_safely"}]
            latest_errors = []

        goal = False
        if not approval_ready:
            primary_blocker = BLOCKER_APPROVAL_MISSING
            next_lever = NEXT_APPROVAL
            english = "Storage cleanup execution approval is missing or unsafe; rerun execution approval before deletion."
        elif not rows:
            primary_blocker = BLOCKER_EMPTY_SCOPE
            next_lever = NEXT_SCOPE_REPAIR
            english = "Approved cleanup execution scope is empty; repair dry-run/approval scope before deletion."
        elif path_errors:
            primary_blocker = BLOCKER_PATH_GUARDRAIL
            next_lever = NEXT_SCOPE_REPAIR
            english = "Approved cleanup scope contains missing or unsafe paths; repair scope before deletion."
        elif latest_errors:
            primary_blocker = BLOCKER_LATEST_VERSION
            next_lever = NEXT_SCOPE_REPAIR
            english = "Approved cleanup scope attempted to delete a latest artifact version; execution blocked."
        else:
            primary_blocker = BLOCKER_AUTOMATIC_DELETION_DISABLED
            next_lever = NEXT_SCOPE_REPAIR
            english = "Automatic cleanup is disabled: this runner cannot preserve latest versions against uncoordinated storage writers. Candidates were validated but no paths were deleted."

    report = {
        "schemaVersion": "video_to_analysis_storage_cleanup_bounded_execution_report_v1",
        "generatedAt": utc_now_iso(),
        "sourceApprovalDir": approval_dir.name,
        "approvedCandidateCount": len(rows),
        "validatedTargetCount": len(valid_targets),
        "pathGuardrailFailureCount": len(path_errors),
        "latestVersionDeletionBlockedCount": len(latest_errors),
        "actualDeletedPathCount": 0,
        "actualReclaimedBytes": 0,
        "deletedRows": [],
        "pathGuardrailFailures": path_errors,
        "latestVersionDeletionBlocks": latest_errors,
        "cleanupMutationExecuted": goal,
        "generatedTruthDeleteAllowed": goal,
    }
    guardrail = _guardrail_audit(
        approval_ready=approval_ready,
        rows=rows,
        path_errors=path_errors,
        latest_errors=latest_errors,
    )
    summary = {
        "batchName": "video_to_analysis_storage_cleanup_bounded_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "approvedCandidateCount": len(rows),
        "validatedTargetCount": len(valid_targets),
        "actualDeletedPathCount": report["actualDeletedPathCount"],
        "actualReclaimedBytes": report["actualReclaimedBytes"],
        "latestVersionDeletionBlockedCount": report["latestVersionDeletionBlockedCount"],
        "pathGuardrailFailureCount": report["pathGuardrailFailureCount"],
        "cleanupMutationExecuted": goal,
        "generatedTruthDeleteAllowed": goal,
        **standard_false_flags(),
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_storage_cleanup_bounded_execution_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "execution_approval_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_APPROVAL_MISSING,
                "primaryBlocker": BLOCKER_APPROVAL_MISSING,
                "nextRecommendedNextLever": NEXT_APPROVAL,
            },
            {
                "condition": "approved_scope_empty",
                "selected": primary_blocker == BLOCKER_EMPTY_SCOPE,
                "primaryBlocker": BLOCKER_EMPTY_SCOPE,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
            {
                "condition": "path_guardrail_failure",
                "selected": primary_blocker == BLOCKER_PATH_GUARDRAIL,
                "primaryBlocker": BLOCKER_PATH_GUARDRAIL,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
            {
                "condition": "latest_version_deletion_blocked",
                "selected": primary_blocker == BLOCKER_LATEST_VERSION,
                "primaryBlocker": BLOCKER_LATEST_VERSION,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
            {
                "condition": "automatic_deletion_disabled",
                "selected": primary_blocker == BLOCKER_AUTOMATIC_DELETION_DISABLED,
                "primaryBlocker": BLOCKER_AUTOMATIC_DELETION_DISABLED,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_cleanup_bounded_execution_summary.json",
        summary=summary,
        artifacts={
            "cleanup_bounded_execution_report.json": report,
            "cleanup_bounded_execution_guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Cleanup Bounded Execution",
    )


def main() -> None:
    main_for("Report approved cleanup candidates; automatic deletion is disabled.", run_video_to_analysis_storage_cleanup_bounded_execution)


if __name__ == "__main__":
    main()
