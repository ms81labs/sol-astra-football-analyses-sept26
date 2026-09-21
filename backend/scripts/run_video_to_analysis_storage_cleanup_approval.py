from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
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

DEFAULT_READOUT_DIR_NAME = "video_to_analysis_user_facing_release_readout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_cleanup_approval_v1"
DEFAULT_STORAGE_HYGIENE_DIR_NAME = "video_to_analysis_storage_retention_and_artifact_hygiene_v1"
DEFAULT_CLEANUP_MAP_DIR_NAME = "video_to_analysis_source_and_artifact_cleanup_map_v1"

BLOCKER_READOUT_MISSING = "video_to_analysis_storage_cleanup_release_readout_missing"
BLOCKER_INVENTORY_MISSING = "video_to_analysis_storage_cleanup_inventory_missing"
BLOCKER_GUARDRAIL_GAP = "video_to_analysis_storage_cleanup_guardrail_gap"
NEXT_READOUT = "video_to_analysis_user_facing_release_readout"
NEXT_CLEANUP_MAP = "video_to_analysis_source_and_artifact_cleanup_map"
NEXT_GUARDRAIL_REPAIR = "video_to_analysis_storage_cleanup_guardrail_repair"
NEXT_DRY_RUN = "video_to_analysis_storage_cleanup_dry_run_execution"


def _version_suffix(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def _version_prefix(path: Path) -> str:
    return re.sub(r"_v\d+$", "", path.name)


def _latest_versioned_dir(root: Path, prefix: str, default_dir_name: str) -> Path:
    dirs = [path for path in root.glob(f"{prefix}_v*") if path.is_dir()]
    if not dirs:
        return root / default_dir_name
    return max(dirs, key=_version_suffix)


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_cleanup_approval_and_dry_run_scope",
                "successCriteria": [
                    "user-facing release readout selected storage cleanup approval",
                    "latest cleanup-map inventory is ready",
                    "write approval contract for dry-run-only cleanup planning",
                    "do not delete generated truth or execute cleanup",
                ],
                "failureAdaptation": "If readout or cleanup inventory is missing, route back to the missing prerequisite.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_cleanup_guardrail_repair",
                "successCriteria": [
                    "repair only approval metadata or dry-run scope",
                    "keep cleanup execution and generated-truth deletion blocked",
                ],
                "failureAdaptation": "If any guardrail is unsafe, route to cleanup guardrail repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_cleanup_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not delete or archive artifacts.",
            },
        ],
    }


def _readout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("userFacingReleaseReadoutReady") is True
        and summary.get("nextRecommendedNextLever") == "video_to_analysis_storage_cleanup_approval"
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _cleanup_map_ready(summary: dict[str, Any] | None, cleanup_map: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("cleanupMapReady") is True
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and isinstance(cleanup_map, dict)
        and cleanup_map.get("cleanupMapReady") is True
        and cleanup_map.get("cleanupMutationExecuted") is False
        and cleanup_map.get("generatedTruthDeleteAllowed") is False
    )


def _directory_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_file():
        return path.stat().st_size, 1
    size = 0
    files = 0
    for child in path.rglob("*"):
        if not child.is_file():
            continue
        try:
            size += child.stat().st_size
            files += 1
        except OSError:
            continue
    return size, files


def _versioned_artifact_rows(root: Path, output_root: Path) -> list[dict[str, Any]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    if not root.exists():
        return []
    for path in root.iterdir():
        if not path.is_dir() or path == output_root:
            continue
        if re.search(r"_v\d+$", path.name):
            groups[_version_prefix(path)].append(path)

    rows: list[dict[str, Any]] = []
    for prefix, paths in sorted(groups.items()):
        latest = max(paths, key=_version_suffix)
        for path in sorted(paths, key=_version_suffix):
            size_bytes, file_count = _directory_size(path)
            is_latest = path == latest
            rows.append(
                {
                    "relativePath": str(path.relative_to(root)),
                    "artifactFamily": prefix,
                    "version": _version_suffix(path),
                    "isLatestInFamily": is_latest,
                    "sizeBytes": size_bytes,
                    "fileCount": file_count,
                    "retentionDecision": "preserve_latest_or_named_release" if is_latest else "dry_run_archive_candidate",
                    "deleteAllowedInThisBatch": False,
                    "requiresExplicitExecutionApproval": True,
                }
            )
    return rows


def _largest_inventory_rows(cleanup_map: dict[str, Any] | None, limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(cleanup_map, dict):
        return []
    rows = cleanup_map.get("artifactInventory")
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "artifactDir": row.get("artifactDir"),
                "cleanupClass": row.get("cleanupClass"),
                "fileCount": row.get("fileCount", 0),
                "totalBytes": row.get("totalBytes", 0),
            }
        )
    return sorted(normalized, key=lambda row: int(row.get("totalBytes") or 0), reverse=True)[:limit]


def _candidate_manifest(root: Path, output_root: Path, cleanup_map: dict[str, Any] | None) -> dict[str, Any]:
    rows = _versioned_artifact_rows(root, output_root)
    candidates = [
        row
        for row in rows
        if row["retentionDecision"] == "dry_run_archive_candidate"
        and not row["relativePath"].startswith("video_to_analysis_storage_cleanup_approval")
    ]
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_candidate_manifest_v1",
        "generatedAt": utc_now_iso(),
        "storageRoot": str(root),
        "cleanupMode": "dry_run_candidate_manifest_only",
        "cleanupCandidateRows": candidates,
        "cleanupCandidateCount": len(candidates),
        "cleanupCandidateBytes": sum(row["sizeBytes"] for row in candidates),
        "latestPreservedRows": [row for row in rows if row["isLatestInFamily"]],
        "largestInventoryRows": _largest_inventory_rows(cleanup_map),
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "deletionAllowedInThisBatch": False,
    }


def _approval_contract(
    *,
    readout_dir: Path,
    cleanup_map_dir: Path,
    storage_hygiene_dir: Path,
    manifest: dict[str, Any],
    ready: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_approval_contract_v1",
        "generatedAt": utc_now_iso(),
        "storageCleanupApprovalReady": ready,
        "storageCleanupDryRunApproved": ready,
        "cleanupExecutionApproved": False,
        "approvedNextAction": "dry_run_only_no_deletion" if ready else None,
        "approvedRunner": "backend/scripts/run_video_to_analysis_storage_cleanup_dry_run_execution.py" if ready else None,
        "sourceReadoutDir": readout_dir.name,
        "sourceCleanupMapDir": cleanup_map_dir.name,
        "sourceStorageHygieneDir": storage_hygiene_dir.name if storage_hygiene_dir.exists() else None,
        "cleanupCandidateCount": manifest["cleanupCandidateCount"],
        "cleanupCandidateBytes": manifest["cleanupCandidateBytes"],
        "deleteAllowedInThisBatch": False,
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "operatorApprovalRequiredBeforeAnyDeletion": True,
    }


def _guardrail_audit(contract: dict[str, Any], readout_ready: bool, cleanup_map_ready: bool) -> dict[str, Any]:
    checks = {
        "userFacingReadoutReady": readout_ready,
        "cleanupMapInventoryReady": cleanup_map_ready,
        "cleanupExecutionStillBlocked": contract["cleanupExecutionApproved"] is False,
        "generatedTruthDeletionStillBlocked": contract["generatedTruthDeleteAllowed"] is False,
        "cleanupMutationStillBlocked": contract["cleanupMutationExecuted"] is False,
        "normalStorageMutationStillBlocked": contract["normalMatchStorageMutationExecuted"] is False,
        "downloadsStillBlocked": contract["dataDownloadAllowed"] is False and contract["videoDownloadAllowed"] is False,
        "trainingStillBlocked": contract["trainingAllowed"] is False,
        "promotionStillBlocked": contract["promotionAllowed"] is False,
        "runtimeMutationStillBlocked": contract["runtimeDefaultMutationAllowed"] is False,
    }
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "approvalGuardrailPassed": all(checks.values()),
    }


def _retention_decision_matrix(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_storage_cleanup_retention_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "artifactClass": "latest_versioned_generated_truth",
                "decision": "preserve",
                "reason": "latest generated truth remains authoritative for continuation and auditability",
                "deleteAllowedInThisBatch": False,
            },
            {
                "artifactClass": "older_versioned_generated_truth",
                "decision": "dry_run_archive_candidate",
                "reason": "older superseded versions can be reviewed for archive/export only after explicit execution approval",
                "candidateCount": manifest["cleanupCandidateCount"],
                "candidateBytes": manifest["cleanupCandidateBytes"],
                "deleteAllowedInThisBatch": False,
            },
            {
                "artifactClass": "large_external_fixture_or_evidence_package",
                "decision": "review_before_archive",
                "reason": "largest rows are storage pressure but may be reproducibility evidence",
                "deleteAllowedInThisBatch": False,
            },
        ],
    }


def run_video_to_analysis_storage_cleanup_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)

    readout_dir = root / DEFAULT_READOUT_DIR_NAME
    readout_summary = load_json(readout_dir / "user_facing_release_readout_summary.json")
    cleanup_map_dir = _latest_versioned_dir(
        root,
        "video_to_analysis_source_and_artifact_cleanup_map",
        DEFAULT_CLEANUP_MAP_DIR_NAME,
    )
    cleanup_map_summary = load_json(cleanup_map_dir / "source_and_artifact_cleanup_map_summary.json")
    cleanup_map = load_json(cleanup_map_dir / "source_and_artifact_cleanup_map.json")
    storage_hygiene_dir = root / DEFAULT_STORAGE_HYGIENE_DIR_NAME

    readout_ready = _readout_ready(readout_summary)
    cleanup_map_ready = _cleanup_map_ready(cleanup_map_summary, cleanup_map)
    manifest = _candidate_manifest(root, output_root, cleanup_map)
    ready = readout_ready and cleanup_map_ready
    contract = _approval_contract(
        readout_dir=readout_dir,
        cleanup_map_dir=cleanup_map_dir,
        storage_hygiene_dir=storage_hygiene_dir,
        manifest=manifest,
        ready=ready,
    )
    guardrail = _guardrail_audit(contract, readout_ready, cleanup_map_ready)

    if not readout_ready:
        goal = False
        primary_blocker = BLOCKER_READOUT_MISSING
        next_lever = NEXT_READOUT
        english = "User-facing release readout is missing or unsafe; regenerate it before storage cleanup approval."
    elif not cleanup_map_ready:
        goal = False
        primary_blocker = BLOCKER_INVENTORY_MISSING
        next_lever = NEXT_CLEANUP_MAP
        english = "Latest source/artifact cleanup-map inventory is missing or unsafe; regenerate cleanup map before approval."
    elif guardrail["approvalGuardrailPassed"] is not True:
        goal = False
        primary_blocker = BLOCKER_GUARDRAIL_GAP
        next_lever = NEXT_GUARDRAIL_REPAIR
        english = "Storage cleanup approval guardrails are unsafe; repair the approval contract before any dry run."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_DRY_RUN
        english = "Storage cleanup approval is ready for a dry-run-only execution plan. No cleanup, deletion, training, promotion, download, normal storage, or runtime mutation happened."

    summary = {
        "batchName": "video_to_analysis_storage_cleanup_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "storageCleanupApprovalReady": goal,
        "storageCleanupDryRunApproved": goal,
        "cleanupExecutionApproved": False,
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "sourceReadoutDir": readout_dir.name,
        "sourceCleanupMapDir": cleanup_map_dir.name,
        "cleanupCandidateCount": manifest["cleanupCandidateCount"],
        "cleanupCandidateBytes": manifest["cleanupCandidateBytes"],
        "artifactInventoryRowCount": (cleanup_map_summary or {}).get("artifactInventoryRowCount", 0),
        "artifactInventoryTotalBytes": (cleanup_map_summary or {}).get("artifactInventoryTotalBytes", 0),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_storage_cleanup_approval_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "user_facing_release_readout_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_READOUT_MISSING,
                "primaryBlocker": BLOCKER_READOUT_MISSING,
                "nextRecommendedNextLever": NEXT_READOUT,
            },
            {
                "condition": "cleanup_inventory_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_INVENTORY_MISSING,
                "primaryBlocker": BLOCKER_INVENTORY_MISSING,
                "nextRecommendedNextLever": NEXT_CLEANUP_MAP,
            },
            {
                "condition": "cleanup_approval_guardrail_gap",
                "selected": primary_blocker == BLOCKER_GUARDRAIL_GAP,
                "primaryBlocker": BLOCKER_GUARDRAIL_GAP,
                "nextRecommendedNextLever": NEXT_GUARDRAIL_REPAIR,
            },
            {
                "condition": "storage_cleanup_dry_run_approved",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_DRY_RUN,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_cleanup_approval_summary.json",
        summary=summary,
        artifacts={
            "storage_cleanup_approval_contract.json": contract,
            "cleanup_candidate_manifest.json": manifest,
            "artifact_retention_decision_matrix.json": _retention_decision_matrix(manifest),
            "guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Cleanup Approval",
    )


def main() -> None:
    main_for("Approve storage cleanup dry-run scope without deleting anything.", run_video_to_analysis_storage_cleanup_approval)


if __name__ == "__main__":
    main()
