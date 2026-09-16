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

DEFAULT_BACKLOG_DIR_NAME = "video_to_analysis_operational_backlog_prioritization_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_retention_and_artifact_hygiene_v1"

BLOCKER_BACKLOG_MISSING = "video_to_analysis_storage_hygiene_operational_backlog_missing"
NEXT_BACKLOG = "video_to_analysis_operational_backlog_prioritization"
NEXT_OPERATOR_DASHBOARD = "video_to_analysis_operator_dashboard_polish"

CACHE_DIR_NAMES = {".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
TEMP_DIR_NAMES = {"tmp", "temp", "scratch"}


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_artifact_inventory_and_retention_policy",
                "successCriteria": [
                    "inventory generated artifacts",
                    "write retention classes",
                    "write cleanup candidate audit without deleting files",
                ],
                "failureAdaptation": "If backlog truth is missing, route back to operational backlog prioritization.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_hygiene_scope_repair",
                "successCriteria": ["repair only inventory classification or retention policy metadata"],
                "failureAdaptation": "Do not delete artifacts; rerun inventory after policy repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_hygiene_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; no cleanup execution.",
            },
        ],
    }


def _backlog_ready(summary: dict[str, Any] | None, backlog: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operationalBacklogPrioritized") is True
        and summary.get("selectedOperationalLever") == "video_to_analysis_storage_retention_and_artifact_hygiene"
        and isinstance(backlog, dict)
        and backlog.get("selectedOperationalLever") == "video_to_analysis_storage_retention_and_artifact_hygiene"
    )


def _directory_size(path: Path) -> tuple[int, int]:
    total_bytes = 0
    total_files = 0
    if not path.exists():
        return 0, 0
    if path.is_file():
        return path.stat().st_size, 1
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total_bytes += child.stat().st_size
                total_files += 1
            except OSError:
                continue
    return total_bytes, total_files


def _classify_path(path: Path, storage_root: Path) -> str:
    rel_parts = path.relative_to(storage_root).parts
    if not rel_parts:
        return "storage_root"
    if any(part in CACHE_DIR_NAMES for part in rel_parts):
        return "cache_cleanup_candidate"
    if any(part in TEMP_DIR_NAMES for part in rel_parts):
        return "temporary_cleanup_candidate"
    if rel_parts[0] in {"trained_detector_candidates", "benchmark_suites", "runtime", "automation"}:
        return "generated_truth"
    if rel_parts[0] in {"matches", "pod_cycles"}:
        return "operational_artifact"
    return "review_required"


def _inventory(storage_root: Path, output_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if storage_root.exists():
        for path in sorted(storage_root.iterdir()):
            if path == output_root or output_root in path.parents:
                continue
            size_bytes, file_count = _directory_size(path)
            rows.append(
                {
                    "relativePath": str(path.relative_to(storage_root)),
                    "pathKind": "directory" if path.is_dir() else "file",
                    "retentionClass": _classify_path(path, storage_root),
                    "sizeBytes": size_bytes,
                    "fileCount": file_count,
                }
            )
    return {
        "schemaVersion": "video_to_analysis_storage_artifact_inventory_v1",
        "generatedAt": utc_now_iso(),
        "storageRoot": str(storage_root),
        "inventoryRows": rows,
        "inventoryRowCount": len(rows),
        "totalInventoriedBytes": sum(row["sizeBytes"] for row in rows),
        "artifactInventoryReady": True,
    }


def _retention_policy() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_artifact_retention_policy_v1",
        "generatedAt": utc_now_iso(),
        "retentionClasses": {
            "generated_truth": {
                "description": "Generated JSON/markdown truth, runtime registry, roadmap automation, and candidate evidence.",
                "deleteAllowed": False,
                "cleanupRequiresExplicitBatch": True,
            },
            "operational_artifact": {
                "description": "Match, pod, or runtime artifacts that may be needed for reproducibility.",
                "deleteAllowed": False,
                "cleanupRequiresExplicitBatch": True,
            },
            "cache_cleanup_candidate": {
                "description": "Tool caches that can be removed after verification.",
                "deleteAllowed": True,
                "cleanupRequiresExplicitBatch": True,
            },
            "temporary_cleanup_candidate": {
                "description": "Scratch files that can be removed only after a bounded cleanup approval batch.",
                "deleteAllowed": True,
                "cleanupRequiresExplicitBatch": True,
            },
            "review_required": {
                "description": "Unclassified files requiring review before any cleanup.",
                "deleteAllowed": False,
                "cleanupRequiresExplicitBatch": True,
            },
        },
        "fullDatasetDownloadAllowed": False,
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationAllowedInThisBatch": False,
        "retentionPolicyReady": True,
    }


def _cleanup_audit(inventory: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        row
        for row in inventory["inventoryRows"]
        if row["retentionClass"] in {"cache_cleanup_candidate", "temporary_cleanup_candidate"}
    ]
    return {
        "schemaVersion": "video_to_analysis_cleanup_candidate_audit_v1",
        "generatedAt": utc_now_iso(),
        "cleanupCandidateRows": candidates,
        "cleanupCandidateCount": len(candidates),
        "cleanupCandidateBytes": sum(row["sizeBytes"] for row in candidates),
        "cleanupExecutionReady": False,
        "cleanupMutationExecuted": False,
        "nextCleanupAction": "write_bounded_cleanup_execution_approval_before_deleting_anything",
    }


def run_video_to_analysis_storage_retention_and_artifact_hygiene(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    backlog_root = root / DEFAULT_BACKLOG_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    backlog_summary = load_json(backlog_root / "operational_backlog_prioritization_summary.json")
    backlog = load_json(backlog_root / "operational_backlog_prioritization.json")
    ready = _backlog_ready(backlog_summary, backlog)
    inventory = _inventory(storage_root, output_root)
    policy = _retention_policy()
    cleanup = _cleanup_audit(inventory)

    if ready:
        goal = True
        primary_blocker = None
        next_lever = NEXT_OPERATOR_DASHBOARD
        english = "Storage retention and artifact hygiene policy is ready. Continue to operator dashboard polish."
    else:
        goal = False
        primary_blocker = BLOCKER_BACKLOG_MISSING
        next_lever = NEXT_BACKLOG
        english = "Operational backlog truth is missing or did not select storage hygiene; prioritize backlog first."

    summary = {
        "batchName": "video_to_analysis_storage_retention_and_artifact_hygiene",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "storageHygienePlanReady": goal,
        "artifactInventoryReady": inventory["artifactInventoryReady"],
        "retentionPolicyReady": policy["retentionPolicyReady"],
        "cleanupExecutionReady": cleanup["cleanupExecutionReady"],
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": policy["generatedTruthDeleteAllowed"],
        "inventoryRowCount": inventory["inventoryRowCount"],
        "totalInventoriedBytes": inventory["totalInventoriedBytes"],
        "cleanupCandidateCount": cleanup["cleanupCandidateCount"],
        "cleanupCandidateBytes": cleanup["cleanupCandidateBytes"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_retention_and_artifact_hygiene_summary.json",
        summary=summary,
        artifacts={
            "storage_artifact_inventory.json": inventory,
            "artifact_retention_policy.json": policy,
            "cleanup_candidate_audit.json": cleanup,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
                "decisions": [
                    {
                        "condition": "operational_backlog_missing",
                        "selected": not ready,
                        "primaryBlocker": BLOCKER_BACKLOG_MISSING,
                        "nextRecommendedNextLever": NEXT_BACKLOG,
                    },
                    {
                        "condition": "storage_hygiene_plan_ready",
                        "selected": ready,
                        "primaryBlocker": None,
                        "nextRecommendedNextLever": NEXT_OPERATOR_DASHBOARD,
                    },
                ],
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Retention And Artifact Hygiene",
    )


def main() -> None:
    main_for(
        "Write video-to-analysis storage retention and artifact hygiene plan.",
        run_video_to_analysis_storage_retention_and_artifact_hygiene,
    )


if __name__ == "__main__":
    main()
