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
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_operational_sprint_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_growth_lane_decision_snapshot_v1"
BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_growth_lane_operational_sprint_closeout_missing"
NEXT_CLOSEOUT = "video_to_analysis_operational_sprint_closeout"
NEXT_SCALEOUT_APPROVAL = "video_to_analysis_real_video_scaleout_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "growth_lane_decision_snapshot"},
            {"attemptNumber": 2, "attemptApproachFamily": "growth_lane_decision_repair"},
            {"attemptNumber": 3, "attemptApproachFamily": "growth_lane_blocker_summary"},
        ],
    }


def run_video_to_analysis_growth_lane_decision_snapshot(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    closeout = load_json(root / DEFAULT_CLOSEOUT_DIR_NAME / "operational_sprint_closeout_summary.json")
    ready = bool(isinstance(closeout, dict) and closeout.get("goalAchieved") is True and closeout.get("operationalSprintClosed") is True)
    snapshot = {
        "schemaVersion": "video_to_analysis_growth_lane_decision_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "selectedGrowthLever": NEXT_SCALEOUT_APPROVAL if ready else None,
        "candidateGrowthLanes": [
            "video_to_analysis_real_video_scaleout_execution_approval",
            "football_external_benchmark_real_execution_expansion",
            "operator_dashboard_metrics_polish",
        ],
        "decisionRationale": "Operational surface is healthy; the next useful dent is approving bounded real-video scaleout.",
        "growthLaneDecisionSnapshotReady": ready,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_growth_lane_decision_snapshot",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_CLOSEOUT_MISSING,
        next_lever=NEXT_SCALEOUT_APPROVAL if ready else NEXT_CLOSEOUT,
        english=(
            "Growth lane decision snapshot selected bounded real-video scaleout execution approval."
            if ready
            else "Operational sprint closeout is missing; close the sprint before selecting growth lane."
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"growthLaneDecisionSnapshotReady": ready, "selectedGrowthLever": NEXT_SCALEOUT_APPROVAL if ready else None},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="growth_lane_decision_snapshot_summary.json",
        summary=summary,
        artifacts={
            "growth_lane_decision_snapshot.json": snapshot,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Growth Lane Decision Snapshot",
    )


def main() -> None:
    main_for("Write video-to-analysis growth lane decision snapshot.", run_video_to_analysis_growth_lane_decision_snapshot)


if __name__ == "__main__":
    main()
