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

DEFAULT_SUITE_PREP_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_suite_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_approval_v1"

BLOCKER_SUITE_PREP_MISSING = "video_to_analysis_broader_real_video_acceptance_suite_prep_missing"
NEXT_SUITE_PREP = "video_to_analysis_broader_real_video_acceptance_suite_prep"
NEXT_EXECUTION = "video_to_analysis_broader_real_video_acceptance_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "broader_real_video_acceptance_approval",
                "successCriteria": ["approve bounded five-case real-video acceptance execution", "do not execute the suite"],
                "failureAdaptation": "If suite prep truth is missing, route back to suite prep.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "broader_real_video_acceptance_scope_repair",
                "successCriteria": ["repair only approval scope and guardrails"],
                "failureAdaptation": "If approval remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "broader_real_video_acceptance_approval_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to suite prep, scope repair, or bounded execution.",
            },
        ],
    }


def _suite_ready(summary: dict[str, Any] | None, suite: dict[str, Any] | None) -> bool:
    cases = suite.get("acceptanceCases") if isinstance(suite, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("broaderRealVideoAcceptanceSuiteReady") is True
        and summary.get("acceptanceCaseCount") == 5
        and guardrails_false(summary)
        and isinstance(suite, dict)
        and suite.get("acceptanceScope") == "bounded_existing_or_user_supplied_real_videos"
        and suite.get("executionRequiresApproval") is True
        and isinstance(cases, list)
        and len(cases) == 5
    )


def run_video_to_analysis_broader_real_video_acceptance_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    suite_root = root / DEFAULT_SUITE_PREP_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    suite_summary = load_json(suite_root / "broader_real_video_acceptance_suite_prep_summary.json")
    suite_contract = load_json(suite_root / "broader_real_video_acceptance_suite_contract.json")
    ready = _suite_ready(suite_summary, suite_contract)
    case_count = len(suite_contract.get("acceptanceCases", [])) if isinstance(suite_contract, dict) else 0

    approved_scope = {
        "schemaVersion": "video_to_analysis_broader_real_video_acceptance_approved_scope_v1",
        "generatedAt": utc_now_iso(),
        "broaderRealVideoAcceptanceApproved": ready,
        "approvedExecutionMode": "bounded_existing_or_user_supplied_real_video_acceptance" if ready else None,
        "acceptedCaseCount": case_count if ready else 0,
        "normalMatchStorageMutationAllowed": ready,
        "detectorEvaluationAllowed": False,
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }
    approval_guardrail = {
        "schemaVersion": "video_to_analysis_broader_real_video_acceptance_approval_guardrail_v1",
        "generatedAt": utc_now_iso(),
        "suitePrepReady": ready,
        "normalMatchStorageMutationApprovedButNotExecuted": ready,
        "detectorEvaluationStillBlocked": True,
        "downloadsStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "approvalGuardrailPassed": ready,
    }

    if not ready:
        primary_blocker = BLOCKER_SUITE_PREP_MISSING
        next_lever = NEXT_SUITE_PREP
        goal = False
        english = "Broader real-video acceptance suite prep is missing or unsafe; prepare the suite before approval."
    else:
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        goal = True
        english = "Broader real-video acceptance is approved for bounded execution. Downloads, detector evaluation, training, promotion, candidate readiness, and runtime mutation remain blocked."

    summary = {
        "batchName": "video_to_analysis_broader_real_video_acceptance_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "broaderRealVideoAcceptanceApproved": goal,
        "approvedAcceptanceCaseCount": case_count if goal else 0,
        "approvedExecutionMode": "bounded_existing_or_user_supplied_real_video_acceptance" if goal else None,
        "normalMatchStorageMutationApproved": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "suite_prep_missing", "selected": primary_blocker == BLOCKER_SUITE_PREP_MISSING, "primaryBlocker": BLOCKER_SUITE_PREP_MISSING, "nextRecommendedNextLever": NEXT_SUITE_PREP},
            {"condition": "acceptance_approved", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EXECUTION},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="broader_real_video_acceptance_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_broader_real_video_acceptance_scope.json": approved_scope,
            "broader_real_video_acceptance_approval_guardrail.json": approval_guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Broader Real Video Acceptance Approval",
    )


def main() -> None:
    main_for("Approve broader real-video acceptance execution.", run_video_to_analysis_broader_real_video_acceptance_approval)


if __name__ == "__main__":
    main()
