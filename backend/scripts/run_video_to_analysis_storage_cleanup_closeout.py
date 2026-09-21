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
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_storage_cleanup_bounded_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_storage_cleanup_closeout_v1"

BLOCKER_EXECUTION_MISSING = "video_to_analysis_storage_cleanup_bounded_execution_missing"
BLOCKER_EXECUTION_GAP = "video_to_analysis_storage_cleanup_bounded_execution_gap"
NEXT_BOUNDED_EXECUTION = "video_to_analysis_storage_cleanup_bounded_execution"
NEXT_SCOPE_REPAIR = "video_to_analysis_storage_cleanup_bounded_scope_repair"
NEXT_STRATEGIC_SELECTION = "video_to_analysis_next_strategic_lane_selection"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "storage_cleanup_closeout",
                "successCriteria": [
                    "bounded cleanup execution passed",
                    "latest-version and path guardrails had zero failures",
                    "write closeout evidence and route to strategic lane selection",
                ],
                "failureAdaptation": "If bounded execution truth is missing, route back to bounded execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "storage_cleanup_closeout_evidence_repair",
                "successCriteria": ["repair only closeout evidence references"],
                "failureAdaptation": "If evidence remains incomplete, route to scope repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "storage_cleanup_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, report: dict[str, Any] | None, guardrail: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("cleanupMutationExecuted") is True
        and summary.get("generatedTruthDeleteAllowed") is True
        and summary.get("actualDeletedPathCount", 0) > 0
        and summary.get("actualReclaimedBytes", 0) > 0
        and summary.get("latestVersionDeletionBlockedCount") == 0
        and summary.get("pathGuardrailFailureCount") == 0
        and isinstance(report, dict)
        and report.get("actualDeletedPathCount") == summary.get("actualDeletedPathCount")
        and report.get("actualReclaimedBytes") == summary.get("actualReclaimedBytes")
        and report.get("latestVersionDeletionBlockedCount") == 0
        and report.get("pathGuardrailFailureCount") == 0
        and isinstance(guardrail, dict)
        and guardrail.get("boundedExecutionGuardrailPassed") is True
    )


def run_video_to_analysis_storage_cleanup_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    execution_dir = root / DEFAULT_EXECUTION_DIR_NAME

    execution_summary = load_json(execution_dir / "storage_cleanup_bounded_execution_summary.json")
    execution_report = load_json(execution_dir / "cleanup_bounded_execution_report.json")
    execution_guardrail = load_json(execution_dir / "cleanup_bounded_execution_guardrail_audit.json")
    ready = _execution_ready(execution_summary, execution_report, execution_guardrail)

    if execution_summary is None:
        goal = False
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_BOUNDED_EXECUTION
        english = "Bounded storage cleanup execution truth is missing; run bounded execution first."
    elif not ready:
        goal = False
        primary_blocker = BLOCKER_EXECUTION_GAP
        next_lever = NEXT_SCOPE_REPAIR
        english = "Bounded storage cleanup execution evidence has a gap; repair scope/evidence before closeout."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_STRATEGIC_SELECTION
        english = "Storage cleanup lane is closed out. Return to strategic lane selection for the next roadmap move."

    closeout_report = {
        "schemaVersion": "video_to_analysis_storage_cleanup_closeout_report_v1",
        "generatedAt": utc_now_iso(),
        "sourceExecutionDir": execution_dir.name,
        "storageCleanupCloseoutReady": goal,
        "actualDeletedPathCount": (execution_summary or {}).get("actualDeletedPathCount", 0),
        "actualReclaimedBytes": (execution_summary or {}).get("actualReclaimedBytes", 0),
        "latestVersionDeletionBlockedCount": (execution_summary or {}).get("latestVersionDeletionBlockedCount", 0),
        "pathGuardrailFailureCount": (execution_summary or {}).get("pathGuardrailFailureCount", 0),
        "nextStrategicAction": NEXT_STRATEGIC_SELECTION if goal else next_lever,
    }
    summary = {
        "batchName": "video_to_analysis_storage_cleanup_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "storageCleanupCloseoutReady": goal,
        "actualDeletedPathCount": closeout_report["actualDeletedPathCount"],
        "actualReclaimedBytes": closeout_report["actualReclaimedBytes"],
        "latestVersionDeletionBlockedCount": closeout_report["latestVersionDeletionBlockedCount"],
        "pathGuardrailFailureCount": closeout_report["pathGuardrailFailureCount"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_storage_cleanup_closeout_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "bounded_execution_missing",
                "selected": primary_blocker == BLOCKER_EXECUTION_MISSING,
                "primaryBlocker": BLOCKER_EXECUTION_MISSING,
                "nextRecommendedNextLever": NEXT_BOUNDED_EXECUTION,
            },
            {
                "condition": "bounded_execution_evidence_gap",
                "selected": primary_blocker == BLOCKER_EXECUTION_GAP,
                "primaryBlocker": BLOCKER_EXECUTION_GAP,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
            {
                "condition": "storage_cleanup_closeout_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STRATEGIC_SELECTION,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="storage_cleanup_closeout_summary.json",
        summary=summary,
        artifacts={
            "storage_cleanup_closeout_report.json": closeout_report,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Storage Cleanup Closeout",
    )


def main() -> None:
    main_for("Close out storage cleanup lane.", run_video_to_analysis_storage_cleanup_closeout)


if __name__ == "__main__":
    main()
