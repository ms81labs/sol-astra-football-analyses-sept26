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

DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_operational_sprint_closeout_v1"
NEXT_SNAPSHOT = "video_to_analysis_growth_lane_decision_snapshot"
BLOCKER_INCOMPLETE = "video_to_analysis_operational_sprint_incomplete"

REQUIRED_BATCHES = [
    ("football_external_benchmark_real_source_path_consolidation_v1", "real_source_path_consolidation_summary.json"),
    ("video_to_analysis_real_video_scaleout_plan_v1", "real_video_scaleout_plan_summary.json"),
    ("video_to_analysis_steady_state_monitoring_recurring_schedule_v1", "steady_state_monitoring_recurring_schedule_summary.json"),
    ("video_to_analysis_operator_dashboard_polish_v1", "operator_dashboard_polish_summary.json"),
]


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "operational_sprint_closeout"},
            {"attemptNumber": 2, "attemptApproachFamily": "operational_sprint_evidence_repair"},
            {"attemptNumber": 3, "attemptApproachFamily": "operational_sprint_blocker_summary"},
        ],
    }


def run_video_to_analysis_operational_sprint_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    completed = []
    for dirname, filename in REQUIRED_BATCHES:
        payload = load_json(root / dirname / filename)
        if isinstance(payload, dict) and payload.get("goalAchieved") is True and payload.get("primaryBlocker") is None:
            completed.append(dirname.removesuffix("_v1"))
    ready = len(completed) == len(REQUIRED_BATCHES)
    manifest = {
        "schemaVersion": "video_to_analysis_operational_sprint_closeout_manifest_v1",
        "generatedAt": utc_now_iso(),
        "completedOperationalItems": completed,
        "completedOperationalItemCount": len(completed),
        "operationalSprintClosed": ready,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_operational_sprint_closeout",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_INCOMPLETE,
        next_lever=NEXT_SNAPSHOT if ready else "video_to_analysis_operational_backlog_prioritization",
        english=(
            "Operational roadmap sprint is closed; choose the next growth lane."
            if ready
            else "Operational sprint evidence is incomplete."
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"operationalSprintClosed": ready, "completedOperationalItemCount": len(completed)},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="operational_sprint_closeout_summary.json",
        summary=summary,
        artifacts={
            "operational_sprint_closeout_manifest.json": manifest,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Operational Sprint Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis operational roadmap sprint.", run_video_to_analysis_operational_sprint_closeout)


if __name__ == "__main__":
    main()
