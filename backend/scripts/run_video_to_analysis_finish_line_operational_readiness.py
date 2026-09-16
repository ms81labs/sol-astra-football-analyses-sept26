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
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_finish_line_normal_storage_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_operational_readiness_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_finish_line_normal_storage_closeout_missing"
BLOCKER_READINESS_GAP = "video_to_analysis_finish_line_operational_readiness_gap"
NEXT_CLOSEOUT = "video_to_analysis_finish_line_normal_storage_closeout"
NEXT_READINESS_REPAIR = "video_to_analysis_finish_line_operational_readiness_repair"
NEXT_COMPLETION_SUMMARY = "video_to_analysis_finish_line_completion_summary"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "finish_line_operational_readiness",
                "successCriteria": [
                    "normal-storage closeout passed",
                    "operator runbook and product route inventory are written",
                    "no additional storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, or runtime-default mutation",
                ],
                "failureAdaptation": "If closeout truth is missing, route back to normal-storage closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "finish_line_operational_readiness_repair",
                "successCriteria": ["repair only runbook or route inventory"],
                "failureAdaptation": "If readiness remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "finish_line_operational_readiness_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to closeout, readiness repair, or completion summary.",
            },
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None, capability: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("normalStorageCloseoutPassed") is True
        and summary.get("normalStorageProductSmokePassed") is True
        and summary.get("apiUploadJobSmokePassed") is True
        and summary.get("existingVideoBundleSmokePassed") is True
        and summary.get("normalMatchStorageMutationExecuted") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(capability, dict)
        and capability.get("operationalReadinessReady") is True
    )


def run_video_to_analysis_finish_line_operational_readiness(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "finish_line_normal_storage_closeout_summary.json")
    closeout_capability = load_json(closeout_root / "normal_storage_closeout_capability_matrix.json")
    ready = _closeout_ready(closeout_summary, closeout_capability)

    route_inventory = {
        "schemaVersion": "video_to_analysis_finish_line_route_inventory_v1",
        "generatedAt": utc_now_iso(),
        "apiRoute": "/api/video-to-analysis/finish-line",
        "htmlRoute": "/video-to-analysis/finish-line",
        "normalStorageSmokeOutput": "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/product_video_to_analysis_smoke_v1",
        "candidateTruthRoot": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7",
    }
    runbook = {
        "schemaVersion": "video_to_analysis_finish_line_operator_runbook_v1",
        "generatedAt": utc_now_iso(),
        "operatorRoute": "/video-to-analysis/finish-line",
        "apiRoute": "/api/video-to-analysis/finish-line",
        "recommendedOperatorChecks": [
            "open finish-line HTML route",
            "confirm scoreboard shows product smoke, API upload/export, and video bundle export passed",
            "inspect normal-storage product smoke artifacts if the route looks stale",
        ],
        "blockedUntilExplicitApproval": [
            "detector_evaluation",
            "training",
            "promotion",
            "candidate_evaluation_readiness",
            "runtime_default_mutation",
        ],
    }
    readiness_audit = {
        "schemaVersion": "video_to_analysis_finish_line_operational_readiness_audit_v1",
        "generatedAt": utc_now_iso(),
        "normalStorageCloseoutReady": ready,
        "routeInventoryWritten": True,
        "operatorRunbookWritten": True,
        "operationalReadinessPassed": ready,
    }

    if closeout_summary is None:
        primary_blocker = BLOCKER_CLOSEOUT_MISSING
        next_lever = NEXT_CLOSEOUT
        goal = False
        english = "Normal-storage closeout truth is missing; close out normal-storage execution first."
    elif not ready:
        primary_blocker = BLOCKER_READINESS_GAP
        next_lever = NEXT_READINESS_REPAIR
        goal = False
        english = "Finish-line operational readiness is incomplete; repair runbook or route inventory."
    else:
        primary_blocker = None
        next_lever = NEXT_COMPLETION_SUMMARY
        goal = True
        english = "Finish-line operational readiness is ready. Write completion summary next."

    summary = {
        "batchName": "video_to_analysis_finish_line_operational_readiness",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "operationalReadinessPassed": goal,
        "normalStorageProductSmokePassed": ready,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "normal_storage_closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "operational_readiness_gap", "selected": primary_blocker == BLOCKER_READINESS_GAP, "primaryBlocker": BLOCKER_READINESS_GAP, "nextRecommendedNextLever": NEXT_READINESS_REPAIR},
            {"condition": "operational_readiness_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_COMPLETION_SUMMARY},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_operational_readiness_summary.json",
        summary=summary,
        artifacts={
            "finish_line_route_inventory.json": route_inventory,
            "finish_line_operator_runbook.json": runbook,
            "operational_readiness_audit.json": readiness_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Operational Readiness",
    )


def main() -> None:
    main_for("Prepare finish-line operational readiness.", run_video_to_analysis_finish_line_operational_readiness)


if __name__ == "__main__":
    main()
