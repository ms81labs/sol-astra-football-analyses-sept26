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

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_closeout_v1"

BLOCKER_EXECUTION_MISSING = "video_to_analysis_broader_real_video_acceptance_execution_missing"
NEXT_EXECUTION = "video_to_analysis_broader_real_video_acceptance_execution"
NEXT_REPORT_ROUTE_BINDING = "video_to_analysis_acceptance_report_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "broader_real_video_acceptance_closeout",
                "successCriteria": [
                    "verify the approved five-case execution passed",
                    "write report/backlog handoff truth",
                ],
                "failureAdaptation": "If execution truth is missing or failed, route back to acceptance execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "acceptance_closeout_evidence_repair",
                "successCriteria": ["repair only closeout evidence references and derived report truth"],
                "failureAdaptation": "If closeout evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "acceptance_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to execution, evidence repair, or report route binding.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, case_results: dict[str, Any] | None) -> bool:
    cases = case_results.get("cases") if isinstance(case_results, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("broaderRealVideoAcceptanceExecuted") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
        and summary.get("normalMatchStorageMutationExecuted") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(cases, list)
        and len(cases) == 5
        and all(isinstance(case, dict) and case.get("passed") is True for case in cases)
    )


def run_video_to_analysis_broader_real_video_acceptance_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "broader_real_video_acceptance_execution_summary.json")
    case_results = load_json(execution_root / "acceptance_case_results.json")
    ready = _execution_ready(execution_summary, case_results)
    cases = case_results.get("cases", []) if isinstance(case_results, dict) else []
    passed_count = sum(1 for case in cases if isinstance(case, dict) and case.get("passed") is True)

    if ready:
        primary_blocker = None
        next_lever = NEXT_REPORT_ROUTE_BINDING
        goal = True
        english = (
            "Broader real-video acceptance closed successfully. Build the acceptance report route and product backlog next; "
            "detector evaluation, training, promotion, downloads, candidate readiness, and runtime mutation remain blocked."
        )
    else:
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_EXECUTION
        goal = False
        english = "Broader real-video acceptance execution is missing or failed; execute the approved suite before closeout."

    report = {
        "schemaVersion": "video_to_analysis_broader_real_video_acceptance_report_v1",
        "generatedAt": utc_now_iso(),
        "acceptanceResult": "passed" if ready else "blocked",
        "acceptanceCaseCount": 5 if ready else len(cases),
        "acceptancePassedCaseCount": passed_count,
        "normalStorageMutationObservedFromExecution": bool(
            isinstance(execution_summary, dict) and execution_summary.get("normalMatchStorageMutationExecuted") is True
        ),
        "closedByBatch": "video_to_analysis_broader_real_video_acceptance_closeout",
        "nextRecommendedNextLever": next_lever,
    }
    capability_matrix = {
        "generatedAt": utc_now_iso(),
        "capabilities": [
            {"capability": "short_user_upload_smoke", "accepted": ready},
            {"capability": "existing_ready_video_bundle", "accepted": ready},
            {"capability": "report_html_export", "accepted": ready},
            {"capability": "csv_exports", "accepted": ready},
            {"capability": "finish_line_route_payload", "accepted": ready},
        ],
        "normalMatchStorageMutationAcceptedFromExecution": ready,
        "detectorEvaluationAccepted": False,
        "trainingAccepted": False,
        "promotionAccepted": False,
        "runtimeDefaultMutationAccepted": False,
    }
    gap_analysis = {
        "generatedAt": utc_now_iso(),
        "remainingGaps": []
        if ready
        else [
            {
                "gapId": BLOCKER_EXECUTION_MISSING,
                "description": "Acceptance execution truth was missing, failed, or incomplete.",
                "nextRecommendedNextLever": NEXT_EXECUTION,
            }
        ],
        "nextProductBacklogTheme": "acceptance_report_and_product_route_binding" if ready else None,
    }

    summary = {
        "batchName": "video_to_analysis_broader_real_video_acceptance_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "broaderRealVideoAcceptanceClosed": goal,
        "acceptanceCaseCount": 5 if goal else len(cases),
        "acceptancePassedCaseCount": passed_count,
        "normalStorageMutationObservedFromExecution": report["normalStorageMutationObservedFromExecution"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "execution_missing_or_failed",
                "selected": primary_blocker == BLOCKER_EXECUTION_MISSING,
                "primaryBlocker": BLOCKER_EXECUTION_MISSING,
                "nextRecommendedNextLever": NEXT_EXECUTION,
            },
            {
                "condition": "acceptance_closed",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_REPORT_ROUTE_BINDING,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="broader_real_video_acceptance_closeout_summary.json",
        summary=summary,
        artifacts={
            "broader_real_video_acceptance_report.json": report,
            "acceptance_closeout_capability_matrix.json": capability_matrix,
            "acceptance_remaining_gap_analysis.json": gap_analysis,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Broader Real Video Acceptance Closeout",
    )


def main() -> None:
    main_for("Close out broader real-video acceptance.", run_video_to_analysis_broader_real_video_acceptance_closeout)


if __name__ == "__main__":
    main()
