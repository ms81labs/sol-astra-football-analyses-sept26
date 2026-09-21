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

DEFAULT_ROUTE_DIR_NAME = "video_to_analysis_detector_evaluation_report_route_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_lane_closeout_v1"

BLOCKER_ROUTE_MISSING = "video_to_analysis_detector_evaluation_report_route_binding_missing"
NEXT_ROUTE_BINDING = "video_to_analysis_detector_evaluation_report_route_binding"
NEXT_ROADMAP_SNAPSHOT = "video_to_analysis_next_roadmap_direction_snapshot"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "detector_evaluation_lane_closeout",
                "successCriteria": ["close detector-evaluation report lane", "select next roadmap direction snapshot"],
                "failureAdaptation": "If route truth is missing, route back to report route binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "detector_evaluation_closeout_evidence_repair",
                "successCriteria": ["repair only closeout references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "detector_evaluation_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to route binding, evidence repair, or roadmap snapshot.",
            },
        ],
    }


def _route_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("detectorEvaluationReportRouteReady") is True
        and summary.get("apiRouteStatusCode") == 200
        and summary.get("htmlRouteStatusCode") == 200
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
    )


def run_video_to_analysis_detector_evaluation_lane_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    route_root = root / DEFAULT_ROUTE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    route_summary = load_json(route_root / "detector_evaluation_report_route_binding_summary.json")
    ready = _route_ready(route_summary)

    if ready:
        primary_blocker = None
        next_lever = NEXT_ROADMAP_SNAPSHOT
        goal = True
        english = "Detector-evaluation report lane is closed. Snapshot the next roadmap direction."
    else:
        primary_blocker = BLOCKER_ROUTE_MISSING
        next_lever = NEXT_ROUTE_BINDING
        goal = False
        english = "Detector-evaluation report route binding is missing or unsafe; bind route before lane closeout."

    capability_matrix = {
        "schemaVersion": "video_to_analysis_detector_evaluation_lane_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "closedCapabilities": {
            "detectorEvaluationReportRouteReady": ready,
            "detectorEvaluationLaneClosed": ready,
            "v7_3RuntimeDefaultActive": ready,
        },
        "guardrails": {
            "candidateReadyForEvaluation": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
            "downloadsReady": False,
        },
    }
    remaining_gap = {
        "schemaVersion": "video_to_analysis_detector_evaluation_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "remainingGap": "promotion_review_design_required",
        "notes": [
            "Detector-evaluation report lane is product-visible.",
            "Promotion remains unready until a separate promotion review design gate is built and passed.",
        ],
    }
    summary = {
        "batchName": "video_to_analysis_detector_evaluation_lane_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "detectorEvaluationLaneClosed": goal,
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": goal,
        "runtimeDefaultRolloutClosed": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_lane_closeout_summary.json",
        summary=summary,
        artifacts={
            "detector_evaluation_lane_capability_matrix.json": capability_matrix,
            "detector_evaluation_remaining_gap_analysis.json": remaining_gap,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Lane Closeout",
    )


def main() -> None:
    main_for("Close video-to-analysis detector evaluation lane.", run_video_to_analysis_detector_evaluation_lane_closeout)


if __name__ == "__main__":
    main()
