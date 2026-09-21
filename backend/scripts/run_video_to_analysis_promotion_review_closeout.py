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

DEFAULT_ROUTE_DIR_NAME = "video_to_analysis_promotion_review_report_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promotion_review_closeout_v1"

BLOCKER_ROUTE_MISSING = "video_to_analysis_promotion_review_report_route_binding_missing"
NEXT_ROUTE_BINDING = "video_to_analysis_promotion_review_report_route_binding"
NEXT_OPERATOR_TRIAL = "video_to_analysis_promoted_runtime_operator_acceptance_trial"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promotion_review_closeout",
                "successCriteria": ["close promotion review report lane", "select promoted-runtime operator acceptance trial"],
                "failureAdaptation": "If route truth is missing, route back to promotion review report route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promotion_review_closeout_evidence_repair",
                "successCriteria": ["repair only closeout evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promotion_review_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to route binding, evidence repair, or operator acceptance trial.",
            },
        ],
    }


def _route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotionReviewReportRouteReady") is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def run_video_to_analysis_promotion_review_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    route_summary = load_json(route_root / "promotion_review_report_route_binding_summary.json")
    view_model = load_json(route_root / "promotion_review_report_view_model.json")
    ready = _route_ready(route_summary)
    review_passed = bool(isinstance(view_model, dict) and view_model.get("promotionReviewPassed") is True)

    if ready and review_passed:
        primary_blocker = None
        next_lever = NEXT_OPERATOR_TRIAL
        goal = True
        english = "Promotion review is closed. Run a promoted-runtime operator acceptance trial next."
    else:
        primary_blocker = BLOCKER_ROUTE_MISSING
        next_lever = NEXT_ROUTE_BINDING
        goal = False
        english = "Promotion review route binding is missing, unsafe, or failed review; bind report route before closeout."

    capability_matrix = {
        "schemaVersion": "video_to_analysis_promotion_review_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "closedCapabilities": {
            "promotionReviewReportRouteReady": ready,
            "promotionReviewClosed": goal,
            "promotionReviewPassed": review_passed,
        },
        "nextCapability": NEXT_OPERATOR_TRIAL if goal else NEXT_ROUTE_BINDING,
    }
    summary = {
        "batchName": "video_to_analysis_promotion_review_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotionReviewClosed": goal,
        "promotionReviewPassed": review_passed,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promotion_review_closeout_summary.json",
        summary=summary,
        artifacts={
            "promotion_review_capability_matrix.json": capability_matrix,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promotion Review Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis promotion review.", run_video_to_analysis_promotion_review_closeout)


if __name__ == "__main__":
    main()
