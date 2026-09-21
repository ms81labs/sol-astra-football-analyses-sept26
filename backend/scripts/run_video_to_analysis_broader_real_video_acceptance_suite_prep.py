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

DEFAULT_POLISH_DIR_NAME = "video_to_analysis_finish_line_route_polish_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_suite_prep_v1"

BLOCKER_POLISH_MISSING = "video_to_analysis_finish_line_route_polish_missing"
NEXT_POLISH = "video_to_analysis_finish_line_route_polish"
NEXT_APPROVAL = "video_to_analysis_broader_real_video_acceptance_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "broader_real_video_acceptance_suite_prep",
                "successCriteria": ["write bounded acceptance suite contract", "do not execute videos or downloads"],
                "failureAdaptation": "If route polish truth is missing, route back to route polish.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "acceptance_suite_scope_repair",
                "successCriteria": ["repair only acceptance case scope and guardrails"],
                "failureAdaptation": "If scope remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "acceptance_suite_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to route polish, suite repair, or acceptance approval.",
            },
        ],
    }


def _polish_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineRoutePolished") is True
        and guardrails_false(summary)
        and isinstance(audit, dict)
        and audit.get("viewModelUpdated") is True
        and audit.get("htmlUpdated") is True
        and audit.get("apiRoutePath") == "/api/video-to-analysis/finish-line"
    )


def run_video_to_analysis_broader_real_video_acceptance_suite_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    polish_root = root / DEFAULT_POLISH_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    polish_summary = load_json(polish_root / "finish_line_route_polish_summary.json")
    polish_audit = load_json(polish_root / "finish_line_route_polish_audit.json")
    ready = _polish_ready(polish_summary, polish_audit)

    suite_contract = {
        "schemaVersion": "video_to_analysis_broader_real_video_acceptance_suite_contract_v1",
        "generatedAt": utc_now_iso(),
        "acceptanceScope": "bounded_existing_or_user_supplied_real_videos",
        "executionRequiresApproval": True,
        "acceptanceCases": [
            {"caseId": "short_user_upload_smoke", "source": "user_supplied", "expectedSignal": "upload_job_export_bundle"},
            {"caseId": "existing_ready_video_bundle", "source": "normal_storage", "expectedSignal": "match_bundle_v1"},
            {"caseId": "report_html_export", "source": "normal_storage", "expectedSignal": "report_html_readable"},
            {"caseId": "csv_exports", "source": "normal_storage", "expectedSignal": "frames_and_events_csv_readable"},
            {"caseId": "finish_line_route_payload", "source": "product_route", "expectedSignal": "route_payload_readable"},
        ],
    }
    guardrail = {
        "schemaVersion": "video_to_analysis_broader_real_video_acceptance_guardrail_v1",
        "generatedAt": utc_now_iso(),
        "dataDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "executionRequiresApproval": True,
        "guardrailPassed": True,
    }

    if not ready:
        primary_blocker = BLOCKER_POLISH_MISSING
        next_lever = NEXT_POLISH
        goal = False
        english = "Finish-line route polish is missing or unsafe; polish route before broader acceptance prep."
    else:
        primary_blocker = None
        next_lever = NEXT_APPROVAL
        goal = True
        english = "Broader real-video acceptance suite is prepared. Approve bounded execution next."

    summary = {
        "batchName": "video_to_analysis_broader_real_video_acceptance_suite_prep",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "broaderRealVideoAcceptanceSuiteReady": goal,
        "acceptanceCaseCount": len(suite_contract["acceptanceCases"]) if goal else 0,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "route_polish_missing", "selected": primary_blocker == BLOCKER_POLISH_MISSING, "primaryBlocker": BLOCKER_POLISH_MISSING, "nextRecommendedNextLever": NEXT_POLISH},
            {"condition": "acceptance_suite_ready", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_APPROVAL},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="broader_real_video_acceptance_suite_prep_summary.json",
        summary=summary,
        artifacts={
            "broader_real_video_acceptance_suite_contract.json": suite_contract,
            "broader_real_video_acceptance_guardrail.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Broader Real Video Acceptance Suite Prep",
    )


def main() -> None:
    main_for("Prepare broader real-video acceptance suite.", run_video_to_analysis_broader_real_video_acceptance_suite_prep)


if __name__ == "__main__":
    main()
