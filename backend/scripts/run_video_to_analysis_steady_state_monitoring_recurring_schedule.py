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
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SCALEOUT_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_steady_state_monitoring_recurring_schedule_v1"
BLOCKER_SCALEOUT_MISSING = "video_to_analysis_recurring_schedule_scaleout_plan_missing"
NEXT_SCALEOUT = "video_to_analysis_real_video_scaleout_plan"
NEXT_CLOSEOUT = "video_to_analysis_operational_sprint_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "steady_state_monitoring_recurring_schedule"},
            {"attemptNumber": 2, "attemptApproachFamily": "recurring_schedule_scope_repair"},
            {"attemptNumber": 3, "attemptApproachFamily": "recurring_schedule_blocker_summary"},
        ],
    }


def run_video_to_analysis_steady_state_monitoring_recurring_schedule(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    scaleout_summary = load_json(root / DEFAULT_SCALEOUT_DIR_NAME / "real_video_scaleout_plan_summary.json")
    ready = bool(isinstance(scaleout_summary, dict) and scaleout_summary.get("goalAchieved") is True)
    schedule = {
        "schemaVersion": "video_to_analysis_steady_state_monitoring_recurring_schedule_v1",
        "generatedAt": utc_now_iso(),
        "monitoringCadence": "per_operational_batch_and_daily_when_active",
        "failureRouting": {
            "route_smoke_failure": "promoted_runtime_route_binding_repair",
            "runtime_registry_mismatch": "promoted_runtime_registry_repair",
            "source_robustness_regression": "source_robustness_regression_debug",
            "storage_policy_regression": "video_to_analysis_storage_retention_and_artifact_hygiene",
        },
        "recurringScheduleReady": ready,
        "schedulerDeploymentExecuted": False,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_steady_state_monitoring_recurring_schedule",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_SCALEOUT_MISSING,
        next_lever=NEXT_CLOSEOUT if ready else NEXT_SCALEOUT,
        english=(
            "Recurring steady-state monitoring schedule is ready."
            if ready
            else "Scaleout plan is missing; write it before recurring schedule."
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"recurringScheduleReady": ready, "monitoringCadence": schedule["monitoringCadence"], "schedulerDeploymentExecuted": False},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="steady_state_monitoring_recurring_schedule_summary.json",
        summary=summary,
        artifacts={
            "steady_state_monitoring_recurring_schedule.json": schedule,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Steady State Monitoring Recurring Schedule",
    )


def main() -> None:
    main_for("Write video-to-analysis recurring steady-state monitoring schedule.", run_video_to_analysis_steady_state_monitoring_recurring_schedule)


if __name__ == "__main__":
    main()
