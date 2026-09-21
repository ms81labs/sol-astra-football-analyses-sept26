from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

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
from backend.scripts.video_to_analysis_operational_sprint_common import latest_versioned_dir  # noqa: E402

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_detector_evaluation_lane_closeout_v1"
DEFAULT_SOURCE_SAMPLING_DIR_NAME = "video_to_analysis_real_video_scaleout_source_sampling_expansion_v1"
DEFAULT_PLAN_REFRESH_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_refresh_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_next_roadmap_direction_snapshot_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_detector_evaluation_lane_closeout_missing"
NEXT_CLOSEOUT = "video_to_analysis_detector_evaluation_lane_closeout"
NEXT_PROMOTION_REVIEW_DESIGN = "video_to_analysis_promotion_review_design"
NEXT_SOURCE_POOL_REPLENISHMENT = "video_to_analysis_source_pool_replenishment_plan"
NEXT_SCALEOUT_EXECUTION_APPROVAL = "video_to_analysis_real_video_scaleout_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "next_roadmap_direction_snapshot",
                "successCriteria": ["select the next explicit roadmap family after detector-evaluation closeout"],
                "failureAdaptation": "If detector lane closeout is missing, route back to closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "roadmap_direction_snapshot_repair",
                "successCriteria": ["repair only next-family generated truth"],
                "failureAdaptation": "If next-family selection remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "roadmap_direction_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to closeout, snapshot repair, or promotion review design.",
            },
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("detectorEvaluationLaneClosed") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
    )


def _ready_scaleout_plan(summary: dict[str, Any] | None, plan: dict[str, Any] | None) -> bool:
    summary = summary if isinstance(summary, dict) else {}
    plan = plan if isinstance(plan, dict) else {}
    available = int(summary.get("availableFreshScaleoutCaseCount") or plan.get("availableFreshScaleoutCaseCount") or 0)
    required = int(summary.get("requiredFreshScaleoutCaseCount") or plan.get("requiredFreshScaleoutCaseCount") or 5)
    cases = int(summary.get("scaleoutCaseCount") or plan.get("scaleoutCaseCount") or 0)
    return bool(
        summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and (plan.get("realVideoScaleoutPlanReady") is True or cases >= required)
        and available >= required
        and cases >= required
    )


def run_video_to_analysis_next_roadmap_direction_snapshot(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "detector_evaluation_lane_closeout_summary.json")
    source_sampling_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_source_sampling_expansion",
        DEFAULT_SOURCE_SAMPLING_DIR_NAME,
    )
    plan_refresh_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_plan_refresh",
        DEFAULT_PLAN_REFRESH_DIR_NAME,
    )
    source_sampling_summary = load_json(
        source_sampling_dir / "real_video_scaleout_source_sampling_expansion_summary.json"
    )
    plan_refresh_summary = load_json(plan_refresh_dir / "real_video_scaleout_plan_refresh_summary.json")
    plan_refresh_plan = load_json(plan_refresh_dir / "real_video_scaleout_plan.json")
    source_sampling_exhausted = bool(
        isinstance(source_sampling_summary, dict)
        and source_sampling_summary.get("primaryBlocker")
        == "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted"
        and source_sampling_summary.get("roadmapAdvanceAllowed") is True
        and source_sampling_summary.get("generatedSourceSamplingPoolExhausted") is True
    )
    ready_scaleout_plan = _ready_scaleout_plan(plan_refresh_summary, plan_refresh_plan)
    ready = _closeout_ready(closeout_summary)

    if source_sampling_exhausted and ready_scaleout_plan:
        primary_blocker = None
        next_lever = NEXT_SCALEOUT_EXECUTION_APPROVAL
        goal = True
        selected_next_family = NEXT_SCALEOUT_EXECUTION_APPROVAL
        english = "Generated source sampling is exhausted, but a refreshed bounded scaleout plan is ready; approve execution next."
    elif source_sampling_exhausted:
        primary_blocker = None
        next_lever = NEXT_SOURCE_POOL_REPLENISHMENT
        goal = True
        selected_next_family = NEXT_SOURCE_POOL_REPLENISHMENT
        english = "Generated source sampling is exhausted; replenish the bounded source pool before more scaleout."
    elif ready:
        primary_blocker = None
        next_lever = NEXT_PROMOTION_REVIEW_DESIGN
        goal = True
        selected_next_family = NEXT_PROMOTION_REVIEW_DESIGN
        english = "Next roadmap direction is promotion review design. This is design-only; no promotion mutation is allowed yet."
    else:
        primary_blocker = BLOCKER_CLOSEOUT_MISSING
        next_lever = NEXT_CLOSEOUT
        goal = False
        selected_next_family = None
        english = "Detector-evaluation lane closeout is missing or unsafe; close that lane before selecting the next roadmap direction."

    snapshot = {
        "schemaVersion": "video_to_analysis_next_roadmap_direction_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "nextRoadmapDirectionSnapshotReady": goal,
        "selectedNextFamily": selected_next_family,
        "sourceSamplingDir": source_sampling_dir.name if source_sampling_dir.exists() else None,
        "sourceSamplingPoolExhausted": source_sampling_exhausted,
        "readyScaleoutPlanDir": plan_refresh_dir.name if ready_scaleout_plan and plan_refresh_dir.exists() else None,
        "rationale": [
            "Generated source sampling is exhausted.",
            "A refreshed bounded scaleout plan is already ready.",
            "Approve bounded execution next; no download, training, promotion, or runtime-default mutation is allowed by this snapshot.",
        ]
        if source_sampling_exhausted and ready_scaleout_plan
        else [
            "Generated source sampling is exhausted.",
            "Bounded growth must be replenished from approved source-pool planning.",
            "No download, training, promotion, or runtime-default mutation is allowed by this snapshot.",
        ]
        if source_sampling_exhausted
        else [
            "Post-release monitoring is closed.",
            "Bounded existing-artifact detector evaluation report is route-bound and closed.",
            "v7.3 is the active runtime default.",
            "Promotion still needs an explicit review-design gate before any mutation.",
        ]
        if goal
        else [],
    }
    summary = {
        "batchName": "video_to_analysis_next_roadmap_direction_snapshot",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "nextRoadmapDirectionSnapshotReady": goal,
        "selectedNextFamily": selected_next_family,
        "sourceSamplingDir": source_sampling_dir.name if source_sampling_dir.exists() else None,
        "sourceSamplingPoolExhausted": source_sampling_exhausted,
        "readyScaleoutPlanDir": plan_refresh_dir.name if ready_scaleout_plan and plan_refresh_dir.exists() else None,
        **standard_false_flags(),
        "runtimeDefaultRolloutClosed": ready,
        "activeRuntimeDefaultVersion": "v7.3" if ready else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="next_roadmap_direction_snapshot_summary.json",
        summary=summary,
        artifacts={
            "next_roadmap_direction_snapshot.json": snapshot,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Next Roadmap Direction Snapshot",
    )


def main() -> None:
    main_for("Snapshot next video-to-analysis roadmap direction.", run_video_to_analysis_next_roadmap_direction_snapshot)


if __name__ == "__main__":
    main()
