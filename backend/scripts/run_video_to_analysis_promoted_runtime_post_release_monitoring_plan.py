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

DEFAULT_COMPLETION_DIR_NAME = "video_to_analysis_release_completion_summary_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_plan_v1"

BLOCKER_COMPLETION_MISSING = "video_to_analysis_release_completion_summary_missing"
NEXT_COMPLETION = "video_to_analysis_release_completion_summary"
NEXT_EXECUTION = "video_to_analysis_promoted_runtime_post_release_monitoring_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_post_release_monitoring_plan",
                "successCriteria": ["release completion exists", "define promoted-runtime registry and route monitoring"],
                "failureAdaptation": "If release completion is missing, route back to release completion summary.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promoted_runtime_monitoring_scope_repair",
                "successCriteria": ["repair only monitoring scope and evidence references"],
                "failureAdaptation": "If monitoring scope remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promoted_runtime_monitoring_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force monitoring execution.",
            },
        ],
    }


def _completion_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisPromotedRuntimeReleaseComplete") is True
        and summary.get("releasedRuntimeVersion") == "v7.2"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def run_video_to_analysis_promoted_runtime_post_release_monitoring_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    completion_root = root / DEFAULT_COMPLETION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    completion_summary = load_json(completion_root / "release_completion_summary.json")
    ready = _completion_ready(completion_summary)

    if ready:
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        goal = True
        english = "Promoted-runtime post-release monitoring plan is ready. Execute the first monitoring check next."
    else:
        primary_blocker = BLOCKER_COMPLETION_MISSING
        next_lever = NEXT_COMPLETION
        goal = False
        english = "Release completion summary is missing or unsafe; complete release before monitoring plan."

    monitoring_plan = {
        "schemaVersion": "video_to_analysis_promoted_runtime_post_release_monitoring_plan_v1",
        "generatedAt": utc_now_iso(),
        "monitoringCadence": "per_release_and_daily_smoke",
        "monitoringChecks": [
            {"id": "release_completion_truth", "expected": "v7.2 release completion summary passed"},
            {"id": "promoted_runtime_registry", "expected": "registry points at v7.2 default_runtime"},
            {"id": "finish_line_route", "expected": "finish-line API and HTML routes are readable"},
            {"id": "acceptance_report_route", "expected": "acceptance report API and HTML routes are readable"},
            {"id": "detector_and_promotion_reports", "expected": "detector evaluation and promotion review reports are readable"},
            {"id": "guardrail_no_new_mutation", "expected": "monitoring executes no training, promotion mutation, or runtime-default mutation"},
        ],
    }
    summary = {
        "batchName": "video_to_analysis_promoted_runtime_post_release_monitoring_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotedRuntimePostReleaseMonitoringPlanReady": goal,
        "monitoringCheckCount": len(monitoring_plan["monitoringChecks"]),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_post_release_monitoring_plan_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_post_release_monitoring_plan.json": monitoring_plan,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Post Release Monitoring Plan",
    )


def main() -> None:
    main_for(
        "Plan video-to-analysis promoted runtime post-release monitoring.",
        run_video_to_analysis_promoted_runtime_post_release_monitoring_plan,
    )


if __name__ == "__main__":
    main()
