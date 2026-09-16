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
    load_json,
    paired_or_latest_versioned_dir,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_bounded_next_sample_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_scaleout_or_backlog_decision_snapshot_v1"
BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_scaleout_or_backlog_next_sample_closeout_missing"
NEXT_CLOSEOUT = "video_to_analysis_bounded_next_sample_closeout"
NEXT_CLEANUP = "video_to_analysis_source_and_artifact_cleanup_map"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "scaleout_or_backlog_decision_snapshot"},
        {"attemptNumber": 2, "attemptApproachFamily": "scaleout_or_backlog_decision_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "scaleout_or_backlog_blocker_summary"},
    ]}


def run_video_to_analysis_scaleout_or_backlog_decision_snapshot(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    closeout_dir = paired_or_latest_versioned_dir(
        root,
        output_dir_name=output_dir_name,
        input_prefix="video_to_analysis_bounded_next_sample_closeout",
        default_dir_name=DEFAULT_CLOSEOUT_DIR_NAME,
    )
    closeout = load_json(closeout_dir / "bounded_next_sample_closeout_summary.json")
    ready = bool(isinstance(closeout, dict) and closeout.get("goalAchieved") is True and closeout.get("boundedNextSampleLaneClosed") is True)
    snapshot = {
        "schemaVersion": "video_to_analysis_scaleout_or_backlog_decision_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "sourceCloseoutDir": closeout_dir.name,
        "scaleoutOrBacklogDecisionSnapshotReady": ready,
        "selectedNextLever": NEXT_CLEANUP if ready else None,
        "decisionReason": "cleanup_map_requested_after_bounded_sample_chain" if ready else "bounded_next_sample_closeout_missing",
        "candidateNextLevers": [
            "video_to_analysis_bounded_next_sample_execution_approval",
            "video_to_analysis_real_video_scaleout_execution_approval",
            "video_to_analysis_source_and_artifact_cleanup_map",
        ],
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_scaleout_or_backlog_decision_snapshot",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_CLOSEOUT_MISSING,
        next_lever=NEXT_CLEANUP if ready else NEXT_CLOSEOUT,
        english="Scaleout/backlog decision snapshot selected cleanup mapping before more scaleout." if ready else "Bounded next-sample closeout missing.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"scaleoutOrBacklogDecisionSnapshotReady": ready, "selectedNextLever": NEXT_CLEANUP if ready else None},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="scaleout_or_backlog_decision_snapshot_summary.json",
        summary=summary,
        artifacts={
            "scaleout_or_backlog_decision_snapshot.json": snapshot,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Scaleout Or Backlog Decision Snapshot",
    )


def main() -> None:
    main_for("Write scaleout-or-backlog decision snapshot.", run_video_to_analysis_scaleout_or_backlog_decision_snapshot)


if __name__ == "__main__":
    main()
