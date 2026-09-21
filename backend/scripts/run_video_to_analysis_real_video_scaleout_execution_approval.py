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
    latest_versioned_dir,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_GROWTH_DIR_NAME = "video_to_analysis_growth_lane_decision_snapshot_v1"
DEFAULT_PLAN_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_real_video_scaleout_execution_approval_v1"
BLOCKER_GROWTH_MISSING = "video_to_analysis_real_video_scaleout_growth_snapshot_missing"
BLOCKER_PLAN_INSUFFICIENT = "video_to_analysis_real_video_scaleout_plan_insufficient"
NEXT_GROWTH = "video_to_analysis_growth_lane_decision_snapshot"
NEXT_PLAN_REFRESH = "video_to_analysis_real_video_scaleout_plan_refresh"
NEXT_ROADMAP_DIRECTION = "video_to_analysis_next_roadmap_direction_snapshot"
NEXT_EXECUTION = "video_to_analysis_real_video_scaleout_bounded_execution"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "real_video_scaleout_execution_approval"},
        {"attemptNumber": 2, "attemptApproachFamily": "real_video_scaleout_approval_scope_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "real_video_scaleout_approval_blocker_summary"},
    ]}


def run_video_to_analysis_real_video_scaleout_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    growth = load_json(root / DEFAULT_GROWTH_DIR_NAME / "growth_lane_decision_snapshot_summary.json")
    source_sampling_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_source_sampling_expansion",
        "video_to_analysis_real_video_scaleout_source_sampling_expansion_v1",
    )
    source_sampling_summary = load_json(
        source_sampling_dir / "real_video_scaleout_source_sampling_expansion_summary.json"
    )
    refresh_plan_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_plan_refresh",
        "video_to_analysis_real_video_scaleout_plan_refresh_v1",
    )
    base_plan_dir = latest_versioned_dir(root, "video_to_analysis_real_video_scaleout_plan", DEFAULT_PLAN_DIR_NAME)
    base_plan = load_json(base_plan_dir / "real_video_scaleout_plan.json")
    refresh_plan = load_json(refresh_plan_dir / "real_video_scaleout_plan.json") if refresh_plan_dir.exists() else None
    base_generated_at = str(base_plan.get("generatedAt") or "") if isinstance(base_plan, dict) else ""
    refresh_generated_at = str(refresh_plan.get("generatedAt") or "") if isinstance(refresh_plan, dict) else ""
    if isinstance(refresh_plan, dict) and (
        not isinstance(base_plan, dict)
        or not refresh_generated_at
        or not base_generated_at
        or refresh_generated_at >= base_generated_at
    ):
        plan_dir = refresh_plan_dir
        plan = refresh_plan
    else:
        plan_dir = base_plan_dir
        plan = base_plan
    growth_ready = bool(
        isinstance(growth, dict)
        and growth.get("goalAchieved") is True
        and growth.get("selectedGrowthLever") == "video_to_analysis_real_video_scaleout_execution_approval"
    )
    plan_ready = bool(isinstance(plan, dict) and plan.get("scaleoutCaseCount") == 5)
    ready = growth_ready and plan_ready
    source_sampling_pool_exhausted = bool(
        isinstance(source_sampling_summary, dict)
        and source_sampling_summary.get("generatedSourceSamplingPoolExhausted") is True
    )
    if ready:
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        english = "Bounded real-video scaleout execution approved."
    elif not growth_ready:
        primary_blocker = BLOCKER_GROWTH_MISSING
        next_lever = NEXT_GROWTH
        english = "Growth snapshot is missing or does not select real-video scaleout approval."
    else:
        primary_blocker = BLOCKER_PLAN_INSUFFICIENT
        next_lever = NEXT_ROADMAP_DIRECTION if source_sampling_pool_exhausted else NEXT_PLAN_REFRESH
        english = (
            "Latest real-video scaleout plan is insufficient and generated source sampling is exhausted; choose the next roadmap direction."
            if source_sampling_pool_exhausted
            else "Latest real-video scaleout plan is insufficient; refresh the plan before approving execution."
        )
    cases = plan.get("scaleoutCases", []) if isinstance(plan, dict) else []
    contract = {
        "schemaVersion": "video_to_analysis_real_video_scaleout_execution_approval_contract_v1",
        "generatedAt": utc_now_iso(),
        "approvedExecutionMode": "bounded_existing_artifact_real_video_scaleout" if ready else None,
        "approvedScaleoutCases": cases if ready else [],
        "approvedScaleoutCaseCount": len(cases) if ready else 0,
        "normalMatchStorageMutationApproved": False,
        "fullDatasetDownloadApproved": False,
        "trainingApproved": False,
        "runtimeDefaultMutationApproved": False,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_real_video_scaleout_execution_approval",
        goal=ready,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "scaleoutExecutionApproved": ready,
            "approvedExecutionMode": contract["approvedExecutionMode"],
            "approvedScaleoutCaseCount": contract["approvedScaleoutCaseCount"],
            "sourcePlanDir": plan_dir.name,
            "sourceSamplingDir": source_sampling_dir.name if source_sampling_dir.exists() else None,
            "sourceSamplingPoolExhausted": source_sampling_pool_exhausted,
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="real_video_scaleout_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "real_video_scaleout_execution_approval_contract.json": contract,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Real Video Scaleout Execution Approval",
    )


def main() -> None:
    main_for("Approve bounded real-video scaleout execution.", run_video_to_analysis_real_video_scaleout_execution_approval)


if __name__ == "__main__":
    main()
