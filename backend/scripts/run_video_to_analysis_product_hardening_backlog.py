from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

DEFAULT_COMPLETION_DIR_NAME = "video_to_analysis_finish_line_completion_summary_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_product_hardening_backlog_v1"

BLOCKER_COMPLETION_MISSING = "video_to_analysis_finish_line_completion_summary_missing"
NEXT_COMPLETION = "video_to_analysis_finish_line_completion_summary"
NEXT_ROUTE_POLISH = "video_to_analysis_finish_line_route_polish"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_product_hardening_backlog",
                "successCriteria": ["write prioritized product hardening backlog", "select route polish first"],
                "failureAdaptation": "If completion truth is missing, route back to completion summary.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "video_to_analysis_product_hardening_backlog_repair",
                "successCriteria": ["repair only backlog ordering and scope"],
                "failureAdaptation": "If backlog remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "video_to_analysis_product_hardening_backlog_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to completion summary, backlog repair, or route polish.",
            },
        ],
    }


def _completion_ready(summary: dict[str, Any] | None, next_steps: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineMilestoneComplete") is True
        and summary.get("videoToAnalysisProductPathReady") is True
        and guardrails_false(summary)
        and isinstance(next_steps, dict)
        and next_steps.get("recommendedNextLever") == "video_to_analysis_product_hardening_backlog"
    )


def run_video_to_analysis_product_hardening_backlog(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    completion_root = root / DEFAULT_COMPLETION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    completion_summary = load_json(completion_root / "finish_line_completion_summary.json")
    next_steps = load_json(completion_root / "finish_line_next_steps_roadmap.json")
    ready = _completion_ready(completion_summary, next_steps)

    hardening_backlog = {
        "schemaVersion": "video_to_analysis_product_hardening_backlog_v1",
        "generatedAt": utc_now_iso(),
        "priorityOrder": [
            "finish_line_route_polish",
            "upload_to_analysis_walkthrough",
            "broader_real_video_acceptance_suite",
            "detector_training_lane_boundary",
        ],
        "backlogItems": [
            {
                "id": "finish_line_route_polish",
                "title": "Polish finish-line route UI copy and empty states",
                "nextLever": NEXT_ROUTE_POLISH,
                "scope": "product_route_artifacts_only",
            },
            {
                "id": "upload_to_analysis_walkthrough",
                "title": "Add product-facing upload-to-analysis walkthrough",
                "nextLever": "video_to_analysis_upload_walkthrough",
                "scope": "product_documentation_and_ui",
            },
            {
                "id": "broader_real_video_acceptance_suite",
                "title": "Prepare broader real-video acceptance suite",
                "nextLever": "video_to_analysis_broader_real_video_acceptance_suite_prep",
                "scope": "bounded_acceptance_design",
            },
            {
                "id": "detector_training_lane_boundary",
                "title": "Keep detector training and promotion lanes separate",
                "nextLever": "detector_lane_boundary_review",
                "scope": "governance_only",
            },
        ],
    }
    scope_guardrail = {
        "schemaVersion": "video_to_analysis_product_hardening_scope_guardrail_v1",
        "generatedAt": utc_now_iso(),
        "normalMatchStorageMutationAllowed": False,
        "detectorEvaluationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "scopeGuardrailPassed": True,
    }

    if not ready:
        primary_blocker = BLOCKER_COMPLETION_MISSING
        next_lever = NEXT_COMPLETION
        goal = False
        english = "Finish-line completion summary is missing or unsafe; complete the milestone summary first."
    else:
        primary_blocker = None
        next_lever = NEXT_ROUTE_POLISH
        goal = True
        english = "Product hardening backlog is ready. Polish the finish-line route first."

    summary = {
        "batchName": "video_to_analysis_product_hardening_backlog",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "productHardeningBacklogReady": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "completion_summary_missing", "selected": primary_blocker == BLOCKER_COMPLETION_MISSING, "primaryBlocker": BLOCKER_COMPLETION_MISSING, "nextRecommendedNextLever": NEXT_COMPLETION},
            {"condition": "backlog_ready", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ROUTE_POLISH},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="product_hardening_backlog_summary.json",
        summary=summary,
        artifacts={
            "product_hardening_backlog.json": hardening_backlog,
            "hardening_scope_guardrail.json": scope_guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Product Hardening Backlog",
    )


def main() -> None:
    main_for("Build video-to-analysis product hardening backlog.", run_video_to_analysis_product_hardening_backlog)


if __name__ == "__main__":
    main()
