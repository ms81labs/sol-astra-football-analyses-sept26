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

DEFAULT_MONITORING_CLOSEOUT_DIR_NAME = "video_to_analysis_post_release_monitoring_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_reentry_plan_v1"

BLOCKER_MONITORING_CLOSEOUT_MISSING = "video_to_analysis_post_release_monitoring_closeout_missing"
NEXT_MONITORING_CLOSEOUT = "video_to_analysis_post_release_monitoring_closeout"
NEXT_APPROVAL = "video_to_analysis_detector_evaluation_reentry_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "detector_evaluation_reentry_plan",
                "successCriteria": [
                    "confirm post-release monitoring closeout",
                    "scope detector evaluation to existing v7.2 artifacts only",
                ],
                "failureAdaptation": "If monitoring closeout truth is missing, route back to monitoring closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "bounded_existing_artifact_scope_repair",
                "successCriteria": ["repair only the detector-evaluation scope contract"],
                "failureAdaptation": "If scope cannot be made bounded, keep detector evaluation blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "detector_reentry_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to monitoring closeout, scope repair, or approval.",
            },
        ],
    }


def _monitoring_ready(summary: dict[str, Any] | None, gate: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("postReleaseMonitoringClosed") is True
        and summary.get("postReleaseMonitoringRouteReady") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(gate, dict)
        and gate.get("detectorEvaluationReentryPlanReady") is True
        and gate.get("detectorEvaluationExecutionReady") is False
        and gate.get("requiredNextLever") == "video_to_analysis_detector_evaluation_reentry_plan"
    )


def run_video_to_analysis_detector_evaluation_reentry_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    monitoring_root = root / DEFAULT_MONITORING_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    monitoring_summary = load_json(monitoring_root / "post_release_monitoring_closeout_summary.json")
    reentry_gate = load_json(monitoring_root / "detector_evaluation_reentry_gate.json")
    ready = _monitoring_ready(monitoring_summary, reentry_gate)

    if ready:
        primary_blocker = None
        next_lever = NEXT_APPROVAL
        goal = True
        english = "Detector-evaluation reentry is scoped to bounded existing v7.2 artifacts. Approve that scope next."
    else:
        primary_blocker = BLOCKER_MONITORING_CLOSEOUT_MISSING
        next_lever = NEXT_MONITORING_CLOSEOUT
        goal = False
        english = "Post-release monitoring closeout is missing or unsafe; close monitoring before detector-evaluation reentry."

    scope = {
        "schemaVersion": "video_to_analysis_bounded_existing_artifact_detector_scope_v1",
        "generatedAt": utc_now_iso(),
        "executionMode": "bounded_existing_v7_2_artifact_detector_evaluation",
        "allowedSourceBatches": [
            "v7_2_bounded_retrain",
            "v7_2_crop_probe_precision_guardrail_audit",
            "v7_2_full_pipeline_non_promotion_eval",
        ],
        "trainingAllowed": False,
        "downloadsAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "normalStorageMutationAllowed": False,
    }
    plan = {
        "schemaVersion": "video_to_analysis_detector_evaluation_reentry_plan_v1",
        "generatedAt": utc_now_iso(),
        "detectorEvaluationReentryPlanReady": goal,
        "approvalRequired": True,
        "approvalLever": NEXT_APPROVAL,
        "boundedExistingArtifactScope": scope,
    }
    summary = {
        "batchName": "video_to_analysis_detector_evaluation_reentry_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "detectorEvaluationReentryPlanReady": goal,
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": goal,
        "runtimeDefaultRolloutClosed": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_reentry_plan_summary.json",
        summary=summary,
        artifacts={
            "detector_evaluation_reentry_plan.json": plan,
            "bounded_existing_artifact_scope.json": scope,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Reentry Plan",
    )


def main() -> None:
    main_for("Plan video-to-analysis detector-evaluation reentry.", run_video_to_analysis_detector_evaluation_reentry_plan)


if __name__ == "__main__":
    main()
