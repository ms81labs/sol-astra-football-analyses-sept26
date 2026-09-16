from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.main import create_app  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    utc_now_iso,
    write_outcome,
)
from backend.scripts.run_product_video_to_analysis_smoke import run_product_video_to_analysis_smoke  # noqa: E402

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_execution_v1"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_broader_real_video_acceptance_approval_missing"
BLOCKER_ACCEPTANCE_FAILED = "video_to_analysis_broader_real_video_acceptance_failed"
NEXT_APPROVAL = "video_to_analysis_broader_real_video_acceptance_approval"
NEXT_REPAIR = "video_to_analysis_broader_real_video_acceptance_repair"
NEXT_CLOSEOUT = "video_to_analysis_broader_real_video_acceptance_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "bounded_broader_real_video_acceptance_execution", "successCriteria": ["execute five approved acceptance cases"], "failureAdaptation": "If approval is missing, route back to approval."},
            {"attemptNumber": 2, "attemptApproachFamily": "acceptance_execution_repair", "successCriteria": ["repair only product route/export acceptance plumbing"], "failureAdaptation": "If cases still fail, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": "acceptance_execution_blocker_summary", "successCriteria": ["write blocker truth"], "failureAdaptation": "Route to approval, repair, or closeout."},
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("broaderRealVideoAcceptanceApproved") is True
        and summary.get("approvedAcceptanceCaseCount") == 5
        and summary.get("normalMatchStorageMutationApproved") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(scope, dict)
        and scope.get("broaderRealVideoAcceptanceApproved") is True
        and scope.get("acceptedCaseCount") == 5
        and scope.get("normalMatchStorageMutationAllowed") is True
        and scope.get("trainingAllowed") is False
        and scope.get("promotionAllowed") is False
        and scope.get("runtimeDefaultMutationAllowed") is False
    )


async def _route_payload_ok(storage_root: Path) -> bool:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.get("/api/video-to-analysis/finish-line")
    try:
        payload = response.json()
    except ValueError:
        return False
    return response.status_code == 200 and isinstance(payload, dict) and payload.get("schemaVersion") == "video_to_analysis_finish_line_product_view_model_v1"


def run_video_to_analysis_broader_real_video_acceptance_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    approval_summary = load_json(approval_root / "broader_real_video_acceptance_approval_summary.json")
    approval_scope = load_json(approval_root / "approved_broader_real_video_acceptance_scope.json")
    approval_ready = _approval_ready(approval_summary, approval_scope)
    nested_summary = run_product_video_to_analysis_smoke(storage_root=Path(storage_root)) if approval_ready else None
    route_ok = asyncio.run(_route_payload_ok(Path(storage_root))) if approval_ready else False

    api_ok = bool(nested_summary and nested_summary.get("apiUploadJobSmokePassed") is True)
    bundle_ok = bool(nested_summary and nested_summary.get("existingVideoBundleSmokePassed") is True)
    case_results = [
        {"caseId": "short_user_upload_smoke", "passed": api_ok},
        {"caseId": "existing_ready_video_bundle", "passed": bundle_ok},
        {"caseId": "report_html_export", "passed": api_ok},
        {"caseId": "csv_exports", "passed": api_ok},
        {"caseId": "finish_line_route_payload", "passed": route_ok},
    ]
    passed_count = sum(1 for case in case_results if case["passed"])
    all_passed = passed_count == 5

    if not approval_ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        goal = False
        english = "Broader real-video acceptance approval is missing or unsafe; approve before execution."
        normal_mutation = False
    elif not all_passed:
        primary_blocker = BLOCKER_ACCEPTANCE_FAILED
        next_lever = NEXT_REPAIR
        goal = False
        english = "Broader real-video acceptance execution failed one or more bounded cases."
        normal_mutation = True
    else:
        primary_blocker = None
        next_lever = NEXT_CLOSEOUT
        goal = True
        english = "Broader real-video acceptance execution passed all five bounded cases."
        normal_mutation = True

    summary = {
        "batchName": "video_to_analysis_broader_real_video_acceptance_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "broaderRealVideoAcceptanceExecuted": goal,
        "acceptanceCaseCount": 5,
        "acceptancePassedCaseCount": passed_count,
        "normalMatchStorageMutationExecuted": normal_mutation,
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "trainingExecuted": False,
        "trainingAllowed": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="broader_real_video_acceptance_execution_summary.json",
        summary=summary,
        artifacts={
            "acceptance_case_results.json": {"generatedAt": utc_now_iso(), "cases": case_results},
            "normal_storage_product_smoke_summary.json": nested_summary or {},
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": primary_blocker, "nextRecommendedNextLever": next_lever},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Broader Real Video Acceptance Execution",
    )


def main() -> None:
    main_for("Execute broader real-video acceptance suite.", run_video_to_analysis_broader_real_video_acceptance_execution)


if __name__ == "__main__":
    main()
