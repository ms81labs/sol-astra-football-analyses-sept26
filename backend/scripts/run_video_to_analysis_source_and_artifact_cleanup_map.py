from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    load_json,
    paired_or_latest_versioned_dir,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_DECISION_DIR_NAME = "video_to_analysis_scaleout_or_backlog_decision_snapshot_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_source_and_artifact_cleanup_map_v1"
BLOCKER_DECISION_MISSING = "video_to_analysis_cleanup_map_decision_snapshot_missing"
NEXT_DECISION = "video_to_analysis_scaleout_or_backlog_decision_snapshot"
NEXT_SAMPLE_APPROVAL = "video_to_analysis_bounded_next_sample_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "source_and_artifact_cleanup_map"},
        {"attemptNumber": 2, "attemptApproachFamily": "cleanup_map_inventory_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "cleanup_map_blocker_summary"},
    ]}


def _inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        files = [p for p in path.rglob("*") if p.is_file()]
        rows.append({
            "artifactDir": path.name,
            "fileCount": len(files),
            "totalBytes": sum(p.stat().st_size for p in files),
            "cleanupClass": "generated_truth_preserve",
        })
    return rows


def run_video_to_analysis_source_and_artifact_cleanup_map(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)
    decision_dir = paired_or_latest_versioned_dir(
        root,
        output_dir_name=output_dir_name,
        input_prefix="video_to_analysis_scaleout_or_backlog_decision_snapshot",
        default_dir_name=DEFAULT_DECISION_DIR_NAME,
    )
    decision = load_json(decision_dir / "scaleout_or_backlog_decision_snapshot_summary.json")
    ready = bool(
        isinstance(decision, dict)
        and decision.get("goalAchieved") is True
        and decision.get("selectedNextLever") == "video_to_analysis_source_and_artifact_cleanup_map"
    )
    inventory = _inventory(root) if ready else []
    cleanup_map = {
        "schemaVersion": "video_to_analysis_source_and_artifact_cleanup_map_v1",
        "generatedAt": utc_now_iso(),
        "sourceDecisionDir": decision_dir.name,
        "cleanupMapReady": ready,
        "cleanupMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "sourceCodeCleanupRecommendation": "commit_or_stage_current_chain_source_files_separately_from_generated_truth",
        "artifactInventoryRowCount": len(inventory),
        "artifactInventoryTotalBytes": sum(row["totalBytes"] for row in inventory),
        "artifactInventory": inventory,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_source_and_artifact_cleanup_map",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_DECISION_MISSING,
        next_lever=NEXT_SAMPLE_APPROVAL if ready else NEXT_DECISION,
        english="Source/artifact cleanup map is ready; no generated truth was deleted." if ready else "Cleanup decision snapshot missing.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "cleanupMapReady": ready,
            "cleanupMutationExecuted": False,
            "generatedTruthDeleteAllowed": False,
            "artifactInventoryRowCount": len(inventory),
            "artifactInventoryTotalBytes": cleanup_map["artifactInventoryTotalBytes"],
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="source_and_artifact_cleanup_map_summary.json",
        summary=summary,
        artifacts={
            "source_and_artifact_cleanup_map.json": cleanup_map,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Source And Artifact Cleanup Map",
    )


def main() -> None:
    main_for("Map source and artifact cleanup state.", run_video_to_analysis_source_and_artifact_cleanup_map)


if __name__ == "__main__":
    main()
