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
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_finish_line_product_acceptance_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_user_acceptance_trial_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_finish_line_product_acceptance_closeout_missing"
BLOCKER_UAT_GAP = "video_to_analysis_finish_line_user_acceptance_gap"
NEXT_CLOSEOUT = "video_to_analysis_finish_line_product_acceptance_closeout"
NEXT_UAT_REPAIR = "video_to_analysis_finish_line_user_acceptance_repair"
NEXT_NORMAL_STORAGE_APPROVAL = "video_to_analysis_finish_line_normal_storage_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "finish_line_user_acceptance_trial",
                "successCriteria": [
                    "finish-line API and HTML routes are readable",
                    "product payload exposes title, subtitle, scoreboard, and next-step status",
                    "no normal match storage mutation, downloads, detector evaluation, training, promotion, candidate readiness, or runtime-default mutation",
                ],
                "failureAdaptation": "If closeout truth is missing, route back to product acceptance closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "finish_line_user_acceptance_copy_or_payload_repair",
                "successCriteria": ["repair only product route copy/payload clarity", "do not mutate normal storage or run detector/training/proof"],
                "failureAdaptation": "If payload clarity remains weak, keep normal-storage approval blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "finish_line_user_acceptance_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to closeout, UAT repair, or normal-storage execution approval.",
            },
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None, capability: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineProductAcceptanceClosed") is True
        and summary.get("productRouteAndBundleSmokePassed") is True
        and guardrails_false(summary)
        and isinstance(capability, dict)
        and capability.get("productUserAcceptanceTrialReady") is True
        and capability.get("productRouteAndBundleSmokePassed") is True
        and capability.get("normalMatchStorageMutationExecuted") is False
    )


async def _route_trial(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/finish-line")
        html_response = await client.get("/video-to-analysis/finish-line")
    try:
        payload = api_response.json()
    except ValueError:
        payload = None
    payload_is_dict = isinstance(payload, dict)
    scoreboard = payload.get("scoreboard") if payload_is_dict else None
    checks = {
        "apiRouteReadable": api_response.status_code == 200,
        "htmlRouteReadable": html_response.status_code == 200,
        "schemaValid": payload_is_dict and payload.get("schemaVersion") == "video_to_analysis_finish_line_product_view_model_v1",
        "titlePresent": payload_is_dict and bool(payload.get("title")),
        "subtitlePresent": payload_is_dict and bool(payload.get("subtitle")),
        "scoreboardPresent": isinstance(scoreboard, list) and len(scoreboard) >= 3,
        "htmlHeadlinePresent": "Video To Analysis Finish Line" in html_response.text,
    }
    return {
        "schemaVersion": "video_to_analysis_finish_line_user_acceptance_route_trial_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "checks": checks,
        "routeTrialPassed": all(checks.values()),
    }


def run_video_to_analysis_finish_line_user_acceptance_trial(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "finish_line_product_acceptance_closeout_summary.json")
    capability = load_json(closeout_root / "finish_line_product_acceptance_capability_matrix.json")
    closeout_ready = _closeout_ready(closeout_summary, capability)
    route_trial = asyncio.run(_route_trial(Path(storage_root))) if closeout_ready else {
        "schemaVersion": "video_to_analysis_finish_line_user_acceptance_route_trial_v1",
        "generatedAt": utc_now_iso(),
        "routeTrialPassed": False,
        "skipReason": BLOCKER_CLOSEOUT_MISSING,
    }
    checklist_items = {
        "productAcceptanceCloseoutReady": closeout_ready,
        "routeTrialPassed": route_trial.get("routeTrialPassed") is True,
        "normalMatchStorageMutationStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeDefaultMutationStillBlocked": True,
    }
    checklist = {
        "schemaVersion": "video_to_analysis_finish_line_user_acceptance_checklist_v1",
        "generatedAt": utc_now_iso(),
        "checks": checklist_items,
        "allChecklistItemsPassed": all(checklist_items.values()),
    }

    if not closeout_ready:
        primary_blocker = BLOCKER_CLOSEOUT_MISSING
        next_lever = NEXT_CLOSEOUT
        goal = False
        english = "Finish-line product acceptance closeout is missing or unsafe; close product acceptance before UAT."
    elif route_trial.get("routeTrialPassed") is not True:
        primary_blocker = BLOCKER_UAT_GAP
        next_lever = NEXT_UAT_REPAIR
        goal = False
        english = "Finish-line user acceptance trial found product route or payload clarity gaps."
    else:
        primary_blocker = None
        next_lever = NEXT_NORMAL_STORAGE_APPROVAL
        goal = True
        english = "Finish-line user acceptance trial passed. Prepare controlled normal-storage execution approval next."

    summary = {
        "batchName": "video_to_analysis_finish_line_user_acceptance_trial",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "userAcceptanceTrialPassed": goal,
        "normalStorageExecutionApprovalReady": goal,
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "product_acceptance_closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "user_acceptance_gap", "selected": primary_blocker == BLOCKER_UAT_GAP, "primaryBlocker": BLOCKER_UAT_GAP, "nextRecommendedNextLever": NEXT_UAT_REPAIR},
            {"condition": "user_acceptance_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_NORMAL_STORAGE_APPROVAL},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_user_acceptance_trial_summary.json",
        summary=summary,
        artifacts={
            "user_acceptance_route_trial_audit.json": route_trial,
            "user_acceptance_checklist.json": checklist,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line User Acceptance Trial",
    )


def main() -> None:
    main_for("Run finish-line user acceptance trial.", run_video_to_analysis_finish_line_user_acceptance_trial)


if __name__ == "__main__":
    main()
