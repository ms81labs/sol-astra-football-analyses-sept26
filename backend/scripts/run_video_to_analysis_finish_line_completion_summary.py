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

DEFAULT_READINESS_DIR_NAME = "video_to_analysis_finish_line_operational_readiness_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_completion_summary_v1"

BLOCKER_READINESS_MISSING = "video_to_analysis_finish_line_operational_readiness_missing"
BLOCKER_COMPLETION_GAP = "video_to_analysis_finish_line_completion_summary_gap"
NEXT_READINESS = "video_to_analysis_finish_line_operational_readiness"
NEXT_COMPLETION_REPAIR = "video_to_analysis_finish_line_completion_summary_repair"
NEXT_PRODUCT_HARDENING = "video_to_analysis_product_hardening_backlog"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "finish_line_completion_summary",
                "successCriteria": [
                    "operational readiness passed",
                    "video-to-analysis product path is summarized with routes, artifacts, and next backlog lever",
                    "no additional storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, or runtime-default mutation",
                ],
                "failureAdaptation": "If operational readiness truth is missing, route back to operational readiness.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "finish_line_completion_summary_repair",
                "successCriteria": ["repair only completion summary and roadmap facts"],
                "failureAdaptation": "If completion truth remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "finish_line_completion_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to readiness, summary repair, or product hardening backlog.",
            },
        ],
    }


def _readiness_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operationalReadinessPassed") is True
        and summary.get("normalStorageProductSmokePassed") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("operationalReadinessPassed") is True
        and audit.get("routeInventoryWritten") is True
        and audit.get("operatorRunbookWritten") is True
    )


def run_video_to_analysis_finish_line_completion_summary(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    readiness_root = root / DEFAULT_READINESS_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    readiness_summary = load_json(readiness_root / "finish_line_operational_readiness_summary.json")
    readiness_audit = load_json(readiness_root / "operational_readiness_audit.json")
    ready = _readiness_ready(readiness_summary, readiness_audit)

    milestone_inventory = {
        "schemaVersion": "video_to_analysis_finish_line_milestone_inventory_v1",
        "generatedAt": utc_now_iso(),
        "videoToAnalysisProductPathReady": ready,
        "completedCapabilities": [
            "finish_line_api_route",
            "finish_line_html_route",
            "isolated_product_bundle_smoke",
            "normal_storage_product_smoke",
            "operator_runbook",
        ],
        "apiRoute": "/api/video-to-analysis/finish-line",
        "htmlRoute": "/video-to-analysis/finish-line",
    }
    next_steps = {
        "schemaVersion": "video_to_analysis_finish_line_next_steps_roadmap_v1",
        "generatedAt": utc_now_iso(),
        "recommendedNextLever": NEXT_PRODUCT_HARDENING if ready else None,
        "candidateNextSteps": [
            "polish finish-line route UI copy and empty states",
            "add product-facing upload-to-analysis walkthrough",
            "prepare a broader real-video acceptance suite",
            "keep detector training/promotion lanes separate from product path hardening",
        ],
    }

    if readiness_summary is None:
        primary_blocker = BLOCKER_READINESS_MISSING
        next_lever = NEXT_READINESS
        goal = False
        english = "Operational readiness truth is missing; prepare readiness before final completion summary."
    elif not ready:
        primary_blocker = BLOCKER_COMPLETION_GAP
        next_lever = NEXT_COMPLETION_REPAIR
        goal = False
        english = "Finish-line completion summary has incomplete readiness evidence; repair summary facts."
    else:
        primary_blocker = None
        next_lever = NEXT_PRODUCT_HARDENING
        goal = True
        english = "Video-to-analysis finish-line product path reached the normal-storage smoke milestone. Advance to product hardening backlog."

    summary = {
        "batchName": "video_to_analysis_finish_line_completion_summary",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "finishLineMilestoneComplete": goal,
        "videoToAnalysisProductPathReady": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "operational_readiness_missing", "selected": primary_blocker == BLOCKER_READINESS_MISSING, "primaryBlocker": BLOCKER_READINESS_MISSING, "nextRecommendedNextLever": NEXT_READINESS},
            {"condition": "completion_summary_gap", "selected": primary_blocker == BLOCKER_COMPLETION_GAP, "primaryBlocker": BLOCKER_COMPLETION_GAP, "nextRecommendedNextLever": NEXT_COMPLETION_REPAIR},
            {"condition": "finish_line_milestone_complete", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_HARDENING},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_completion_summary.json",
        summary=summary,
        artifacts={
            "finish_line_milestone_inventory.json": milestone_inventory,
            "finish_line_next_steps_roadmap.json": next_steps,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Completion Summary",
    )


def main() -> None:
    main_for("Summarize video-to-analysis finish-line completion.", run_video_to_analysis_finish_line_completion_summary)


if __name__ == "__main__":
    main()
