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

DEFAULT_ARCHIVE_DIR_NAME = "video_to_analysis_release_acceptance_archive_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_broader_validation_choice_v1"

BLOCKER_ARCHIVE_MISSING = "football_external_soccernet_broader_choice_release_archive_missing"
BLOCKER_SOCCERNET_FULL_ANALYSIS_MISSING = "football_external_soccernet_broader_choice_full_analysis_missing"
NEXT_ARCHIVE = "video_to_analysis_release_acceptance_archive"
NEXT_FULL_ANALYSIS = "football_external_soccernet_full_analysis_execution_approval"
NEXT_UPLOAD_WALKTHROUGH = "video_to_analysis_upload_to_analysis_walkthrough"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_broader_validation_choice",
                "successCriteria": [
                    "release archive exists",
                    "SoccerNet full-analysis lane is already closed",
                    "choose whether broader validation should run now or be held as optional future growth",
                ],
                "failureAdaptation": "If full-analysis truth is missing, route to the exact SoccerNet execution approval gate.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_validation_choice_reference_repair",
                "successCriteria": ["repair only stale SoccerNet artifact references"],
                "failureAdaptation": "Do not download data, train, promote, or mutate runtime defaults.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_validation_choice_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Stop with bounded validation choice truth.",
            },
        ],
    }


def _archive_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisReleaseAcceptanceArchived") is True
        and summary.get("currentReleaseFinished") is True
    )


def _full_analysis_ready(summary: dict[str, Any] | None) -> bool:
    return bool(isinstance(summary, dict) and summary.get("goalAchieved") is True and summary.get("primaryBlocker") is None)


def run_football_external_soccernet_broader_validation_choice(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    archive_summary = load_json(root / DEFAULT_ARCHIVE_DIR_NAME / "release_acceptance_archive_summary.json")
    full_analysis_summary = load_json(
        root / "football_external_soccernet_full_analysis_lane_closeout_v1" / "full_analysis_lane_closeout_summary.json"
    )
    bounded_report_summary = load_json(
        root
        / "football_external_soccernet_bounded_product_validation_report_binding_v1"
        / "soccernet_bounded_product_validation_report_binding_summary.json"
    )
    real_training_decision = load_json(
        root
        / "football_external_soccernet_real_sample_product_pipeline_training_decision_v1"
        / "soccernet_real_sample_product_pipeline_training_decision_summary.json"
    )

    archive_ready = _archive_ready(archive_summary)
    full_analysis_ready = _full_analysis_ready(full_analysis_summary)
    bounded_report_ready = _full_analysis_ready(bounded_report_summary)
    training_decision_ready = _full_analysis_ready(real_training_decision)

    if not archive_ready:
        goal = False
        primary_blocker = BLOCKER_ARCHIVE_MISSING
        next_lever = NEXT_ARCHIVE
        english = "Release acceptance archive is missing; archive the current release before choosing broader SoccerNet validation."
    elif not full_analysis_ready:
        goal = False
        primary_blocker = BLOCKER_SOCCERNET_FULL_ANALYSIS_MISSING
        next_lever = NEXT_FULL_ANALYSIS
        english = "SoccerNet full-analysis lane closeout is missing; finish bounded full-analysis before product walkthrough work."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_UPLOAD_WALKTHROUGH
        english = "SoccerNet broader validation is already sufficiently bound for this archive; polish the upload-to-analysis walkthrough next."

    choice = {
        "schemaVersion": "football_external_soccernet_broader_validation_choice_v1",
        "generatedAt": utc_now_iso(),
        "releaseArchiveReady": archive_ready,
        "soccernetFullAnalysisClosed": full_analysis_ready,
        "boundedProductValidationReportReady": bounded_report_ready,
        "realSampleTrainingDecisionReady": training_decision_ready,
        "broaderValidationRunNow": False,
        "broaderValidationHeldAsOptionalFutureGrowth": goal,
        "selectedNextLever": next_lever,
    }
    summary = {
        "batchName": "football_external_soccernet_broader_validation_choice",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "releaseArchiveReady": archive_ready,
        "soccernetFullAnalysisClosed": full_analysis_ready,
        "boundedProductValidationReportReady": bounded_report_ready,
        "broaderValidationRunNow": False,
        "broaderValidationHeldAsOptionalFutureGrowth": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_broader_validation_choice_summary.json",
        summary=summary,
        artifacts={
            "soccernet_broader_validation_choice.json": choice,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Broader Validation Choice",
    )


def main() -> None:
    main_for("Choose broader SoccerNet validation posture.", run_football_external_soccernet_broader_validation_choice)


if __name__ == "__main__":
    main()
