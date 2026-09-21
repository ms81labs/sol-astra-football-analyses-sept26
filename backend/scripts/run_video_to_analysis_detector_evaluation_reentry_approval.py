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

DEFAULT_PLAN_DIR_NAME = "video_to_analysis_detector_evaluation_reentry_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_reentry_approval_v1"

BLOCKER_PLAN_MISSING = "video_to_analysis_detector_evaluation_reentry_plan_missing"
NEXT_PLAN = "video_to_analysis_detector_evaluation_reentry_plan"
NEXT_EXECUTION = "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "detector_evaluation_reentry_approval",
                "successCriteria": ["approve only bounded existing-artifact detector evaluation"],
                "failureAdaptation": "If plan truth is missing, route back to detector-evaluation reentry plan.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "detector_evaluation_scope_approval_repair",
                "successCriteria": ["repair only approval metadata and guardrail flags"],
                "failureAdaptation": "If approval cannot stay bounded, keep execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "detector_evaluation_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to reentry plan, approval repair, or bounded execution.",
            },
        ],
    }


def _plan_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("detectorEvaluationReentryPlanReady") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(scope, dict)
        and scope.get("executionMode") == "bounded_existing_v7_2_artifact_detector_evaluation"
        and scope.get("trainingAllowed") is False
        and scope.get("promotionAllowed") is False
        and scope.get("runtimeDefaultMutationAllowed") is False
    )


def run_video_to_analysis_detector_evaluation_reentry_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    plan_root = root / DEFAULT_PLAN_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    plan_summary = load_json(plan_root / "detector_evaluation_reentry_plan_summary.json")
    scope = load_json(plan_root / "bounded_existing_artifact_scope.json")
    ready = _plan_ready(plan_summary, scope)

    if ready:
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        goal = True
        english = "Bounded existing-artifact detector evaluation is approved. Execute the bounded artifact aggregation next."
    else:
        primary_blocker = BLOCKER_PLAN_MISSING
        next_lever = NEXT_PLAN
        goal = False
        english = "Detector-evaluation reentry plan is missing or unsafe; rebuild the plan before approval."

    approved_scope = {
        "schemaVersion": "video_to_analysis_detector_evaluation_approved_scope_v1",
        "generatedAt": utc_now_iso(),
        "detectorEvaluationApproved": goal,
        "approvedExecutionMode": "bounded_existing_v7_2_artifact_detector_evaluation" if goal else None,
        "sourceScope": scope if isinstance(scope, dict) else {},
        "executionGuardrails": {
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
            "downloadsAllowed": False,
        },
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "runtimeDefaultRolloutClosed": goal,
    }
    summary = {
        "batchName": "video_to_analysis_detector_evaluation_reentry_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "detectorEvaluationApproved": goal,
        "approvedExecutionMode": "bounded_existing_v7_2_artifact_detector_evaluation" if goal else None,
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": goal,
        "runtimeDefaultRolloutClosed": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_reentry_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_detector_evaluation_scope.json": approved_scope,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Reentry Approval",
    )


def main() -> None:
    main_for("Approve video-to-analysis detector-evaluation reentry.", run_video_to_analysis_detector_evaluation_reentry_approval)


if __name__ == "__main__":
    main()
