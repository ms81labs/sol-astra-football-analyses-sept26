from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SNAPSHOT_DIR_NAME = "video_to_analysis_next_sample_selection_snapshot_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_bounded_next_sample_execution_approval_v1"
BLOCKER_SNAPSHOT_MISSING = "video_to_analysis_bounded_next_sample_selection_snapshot_missing"
BLOCKER_POOL_EXHAUSTED = "video_to_analysis_bounded_next_sample_pool_exhausted"
NEXT_SNAPSHOT = "video_to_analysis_next_sample_selection_snapshot"
NEXT_EXECUTION = "video_to_analysis_bounded_next_sample_execution"
NEXT_SCALEOUT = "video_to_analysis_real_video_scaleout_plan_refresh"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "bounded_next_sample_execution_approval"},
        {"attemptNumber": 2, "attemptApproachFamily": "bounded_next_sample_approval_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "bounded_next_sample_approval_blocker_summary"},
    ]}


def _select_sample(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    priority = ["operator_selected_canary_video", "soccernet_second_bounded_member", "normal_storage_recent_upload"]
    by_id = {str(row.get("id")): row for row in candidates if isinstance(row, dict)}
    for sample_id in priority:
        if sample_id in by_id:
            return by_id[sample_id]
    return candidates[0] if candidates else None


def _executed_sample_ids(root: Path) -> set[str]:
    executed: set[str] = set()
    for execution_dir in root.glob("video_to_analysis_bounded_next_sample_execution_v*"):
        summary = load_json(execution_dir / "bounded_next_sample_execution_summary.json")
        if isinstance(summary, dict) and summary.get("goalAchieved") is True and summary.get("executedSampleId"):
            executed.add(str(summary["executedSampleId"]))
    return executed


def run_video_to_analysis_bounded_next_sample_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    snapshot_dir = latest_versioned_dir(root, "video_to_analysis_next_sample_selection_snapshot", DEFAULT_SNAPSHOT_DIR_NAME)
    snapshot_summary = load_json(snapshot_dir / "next_sample_selection_snapshot_summary.json")
    snapshot = load_json(snapshot_dir / "next_sample_selection_snapshot.json")
    raw_candidates = snapshot.get("candidateSamples", []) if isinstance(snapshot, dict) else []
    snapshot_ready = bool(
        isinstance(snapshot_summary, dict)
        and snapshot_summary.get("goalAchieved") is True
        and isinstance(snapshot, dict)
        and snapshot.get("nextSampleSelectionSnapshotReady") is True
    )
    executed_ids = _executed_sample_ids(root)
    candidates = [row for row in raw_candidates if str(row.get("id")) not in executed_ids] if isinstance(raw_candidates, list) else []
    selected = _select_sample(candidates)
    ready = bool(snapshot_ready and selected)
    pool_exhausted = bool(snapshot_ready and not selected)
    blocker = None if ready else (BLOCKER_POOL_EXHAUSTED if pool_exhausted else BLOCKER_SNAPSHOT_MISSING)
    next_lever = NEXT_EXECUTION if ready else (NEXT_SCALEOUT if pool_exhausted else NEXT_SNAPSHOT)
    contract = {
        "schemaVersion": "video_to_analysis_bounded_next_sample_execution_approval_contract_v1",
        "generatedAt": utc_now_iso(),
        "sourceSnapshotDir": snapshot_dir.name,
        "approvedExecutionMode": "bounded_existing_artifact_next_sample" if ready else None,
        "approvedNextSample": selected if ready else None,
        "approvedNextSampleId": str(selected.get("id")) if ready and selected else None,
        "normalMatchStorageMutationApproved": False,
        "fullDatasetDownloadApproved": False,
        "trainingApproved": False,
        "runtimeDefaultMutationApproved": False,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_bounded_next_sample_execution_approval",
        goal=ready,
        primary_blocker=blocker,
        next_lever=next_lever,
        english=(
            "Bounded next-sample execution approved."
            if ready
            else (
                "Bounded next-sample pool exhausted; return to broader real-video scaleout."
                if pool_exhausted
                else "Next-sample selection snapshot missing."
            )
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "boundedNextSampleExecutionApproved": ready,
            "approvedExecutionMode": contract["approvedExecutionMode"],
            "approvedNextSampleId": contract["approvedNextSampleId"],
            "sourceSnapshotDir": snapshot_dir.name,
            "previouslyExecutedSampleIds": sorted(executed_ids),
            "remainingCandidateSampleCount": len(candidates),
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="bounded_next_sample_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "bounded_next_sample_execution_approval_contract.json": contract,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Bounded Next Sample Execution Approval",
    )


def main() -> None:
    main_for("Approve bounded next-sample execution.", run_video_to_analysis_bounded_next_sample_execution_approval)


if __name__ == "__main__":
    main()
