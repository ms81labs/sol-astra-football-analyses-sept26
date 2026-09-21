from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_EXECUTION_DIR_NAME = "product_video_to_analysis_finish_line_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_product_acceptance_closeout_v1"

BLOCKER_EXECUTION_MISSING = "product_video_to_analysis_finish_line_execution_missing"
BLOCKER_ACCEPTANCE_GAP = "video_to_analysis_finish_line_product_acceptance_gap"
NEXT_EXECUTION = "product_video_to_analysis_finish_line_execution"
NEXT_ACCEPTANCE_REPAIR = "video_to_analysis_finish_line_product_acceptance_repair"
NEXT_USER_ACCEPTANCE_TRIAL = "video_to_analysis_finish_line_user_acceptance_trial"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "product_acceptance_closeout",
                "successCriteria": [
                    "bounded product route smoke passed",
                    "isolated bundle consistency passed",
                    "preserve no normal match storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, or runtime-default mutation",
                ],
                "failureAdaptation": "If bounded execution truth is missing, route back to product execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "product_acceptance_gap_repair",
                "successCriteria": ["repair only acceptance evidence inventory", "do not mutate runtime, storage, training, or promotion state"],
                "failureAdaptation": "If acceptance evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "product_acceptance_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to execution, acceptance repair, or user acceptance trial.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, truth: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineProductExecutionPassed") is True
        and summary.get("boundedRouteSmokePassed") is True
        and summary.get("bundleConsistencyPassed") is True
        and guardrails_false(summary)
        and isinstance(truth, dict)
        and truth.get("finishLineProductExecutionPassed") is True
        and truth.get("boundedRouteSmokePassed") is True
        and truth.get("bundleConsistencyPassed") is True
        and truth.get("normalMatchStorageMutationExecuted") is False
        and truth.get("detectorEvaluationExecuted") is False
        and truth.get("trainingExecuted") is False
        and truth.get("promotionMutationExecuted") is False
        and truth.get("runtimeDefaultMutationExecuted") is False
    )


def run_video_to_analysis_finish_line_product_acceptance_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "product_video_to_analysis_finish_line_execution_summary.json")
    acceptance_truth = load_json(execution_root / "finish_line_product_acceptance_truth.json")
    ready = _execution_ready(execution_summary, acceptance_truth)

    capability_matrix = {
        "schemaVersion": "video_to_analysis_finish_line_product_acceptance_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "boundedRouteSmokePassed": bool(execution_summary and execution_summary.get("boundedRouteSmokePassed") is True),
        "bundleConsistencyPassed": bool(execution_summary and execution_summary.get("bundleConsistencyPassed") is True),
        "productRouteAndBundleSmokePassed": ready,
        "productUserAcceptanceTrialReady": ready,
        "normalMatchStorageMutationExecuted": False,
        "dataDownloadExecuted": False,
        "videoDownloadExecuted": False,
        "detectorEvaluationExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
    }
    remaining_gap_analysis = {
        "schemaVersion": "video_to_analysis_finish_line_product_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "remainingTechnicalBlocker": None if ready else (BLOCKER_EXECUTION_MISSING if execution_summary is None else BLOCKER_ACCEPTANCE_GAP),
        "nextHumanFacingAction": "open finish-line product route and run user acceptance trial" if ready else None,
        "nonGoalsStillBlocked": [
            "normal_match_storage_mutation",
            "detector_evaluation",
            "training",
            "promotion",
            "candidate_evaluation_readiness",
            "runtime_default_mutation",
        ],
    }

    if execution_summary is None:
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_EXECUTION
        goal = False
        english = "Product finish-line execution truth is missing; run bounded route and bundle smoke first."
    elif not ready:
        primary_blocker = BLOCKER_ACCEPTANCE_GAP
        next_lever = NEXT_ACCEPTANCE_REPAIR
        goal = False
        english = "Product finish-line execution evidence is incomplete; repair acceptance evidence before user trial."
    else:
        primary_blocker = None
        next_lever = NEXT_USER_ACCEPTANCE_TRIAL
        goal = True
        english = "Finish-line product acceptance is closed from bounded route and bundle smoke. Advance to user acceptance trial."

    summary = {
        "batchName": "video_to_analysis_finish_line_product_acceptance_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineProductAcceptanceClosed": goal,
        "productRouteAndBundleSmokePassed": ready,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "product_execution_missing", "selected": primary_blocker == BLOCKER_EXECUTION_MISSING, "primaryBlocker": BLOCKER_EXECUTION_MISSING, "nextRecommendedNextLever": NEXT_EXECUTION},
            {"condition": "product_acceptance_gap", "selected": primary_blocker == BLOCKER_ACCEPTANCE_GAP, "primaryBlocker": BLOCKER_ACCEPTANCE_GAP, "nextRecommendedNextLever": NEXT_ACCEPTANCE_REPAIR},
            {"condition": "product_acceptance_closed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_USER_ACCEPTANCE_TRIAL},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_product_acceptance_closeout_summary.json",
        summary=summary,
        artifacts={
            "finish_line_product_acceptance_capability_matrix.json": capability_matrix,
            "finish_line_product_remaining_gap_analysis.json": remaining_gap_analysis,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Product Acceptance Closeout",
    )


def main() -> None:
    main_for("Close finish-line product acceptance after bounded execution.", run_video_to_analysis_finish_line_product_acceptance_closeout)


if __name__ == "__main__":
    main()
