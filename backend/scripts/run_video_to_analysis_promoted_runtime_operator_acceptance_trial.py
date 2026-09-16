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
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_promotion_review_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"

BLOCKER_PROMOTION_CLOSEOUT_MISSING = "video_to_analysis_promotion_review_closeout_missing"
BLOCKER_RUNTIME_REGISTRY_GAP = "video_to_analysis_promoted_runtime_registry_gap"
BLOCKER_OPERATOR_ROUTE_GAP = "video_to_analysis_promoted_runtime_operator_route_gap"
NEXT_PROMOTION_CLOSEOUT = "video_to_analysis_promotion_review_closeout"
NEXT_REGISTRY_REPAIR = "video_to_analysis_promoted_runtime_registry_repair"
NEXT_ROUTE_REPAIR = "video_to_analysis_operator_surface_route_repair"
NEXT_RELEASE_CLOSEOUT = "video_to_analysis_promoted_runtime_release_closeout"

OPERATOR_VISIBLE_ROUTES = [
    {
        "id": "finish_line",
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "expectedSchemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
        "expectedHtmlText": "Video To Analysis Finish Line",
    },
    {
        "id": "acceptance_report",
        "apiRoutePath": "/api/video-to-analysis/acceptance-report",
        "htmlRoutePath": "/video-to-analysis/acceptance-report",
        "expectedSchemaVersion": "video_to_analysis_acceptance_report_view_model_v1",
        "expectedHtmlText": "Acceptance Report",
    },
    {
        "id": "operator_handoff",
        "apiRoutePath": "/api/video-to-analysis/operator-handoff",
        "htmlRoutePath": "/video-to-analysis/operator-handoff",
        "expectedSchemaVersion": "video_to_analysis_operator_handoff_view_model_v1",
        "expectedHtmlText": "Operator Handoff",
    },
    {
        "id": "detector_evaluation_report",
        "apiRoutePath": "/api/video-to-analysis/detector-evaluation-report",
        "htmlRoutePath": "/video-to-analysis/detector-evaluation-report",
        "expectedSchemaVersion": "video_to_analysis_detector_evaluation_report_view_model_v1",
        "expectedHtmlText": "Detector Evaluation Report",
    },
    {
        "id": "promotion_review",
        "apiRoutePath": "/api/video-to-analysis/promotion-review",
        "htmlRoutePath": "/video-to-analysis/promotion-review",
        "expectedSchemaVersion": "video_to_analysis_promotion_review_report_view_model_v1",
        "expectedHtmlText": "Promotion Review",
    },
]


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_operator_acceptance_trial",
                "successCriteria": [
                    "promotion review closeout is complete",
                    "promoted runtime registry points at v7.2 default runtime",
                    "operator-visible routes are readable through API and HTML",
                    "no training, promotion mutation, or runtime-default mutation is executed by this trial",
                ],
                "failureAdaptation": "If promotion closeout is missing, route back to promotion review closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promoted_runtime_registry_or_route_repair",
                "successCriteria": ["repair only registry evidence references or operator route bindings"],
                "failureAdaptation": "If registry is wrong, route to registry repair; if routes fail, route to route repair.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promoted_runtime_operator_acceptance_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force release closeout.",
            },
        ],
    }


def _promotion_closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotionReviewClosed") is True
        and summary.get("promotionReviewPassed") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _registry_audit(storage_root: Path) -> dict[str, Any]:
    registry_path = storage_root / "runtime" / "promoted_touchline_detector_candidate.json"
    registry = load_json(registry_path)
    checks = {
        "registryPresent": isinstance(registry, dict),
        "candidateNameMatches": isinstance(registry, dict)
        and registry.get("trainingCandidateName") == "touchline_detector_candidate_v7",
        "candidateVersionMatches": isinstance(registry, dict) and registry.get("trainingCandidateVersion") == "v7.2",
        "runtimeUseDefault": isinstance(registry, dict) and registry.get("runtimeUse") == "default_runtime",
        "promotionValidated": isinstance(registry, dict) and registry.get("promotionValidated") is True,
        "promotionReady": isinstance(registry, dict) and registry.get("promotionReady") is True,
        "candidateReadyForEvaluation": isinstance(registry, dict) and registry.get("candidateReadyForEvaluation") is True,
        "runtimeDefaultMutationExecutedPreviously": isinstance(registry, dict)
        and registry.get("runtimeDefaultMutationExecuted") is True,
        "postRuntimeDefaultSourceRobustnessValidated": isinstance(registry, dict)
        and registry.get("postRuntimeDefaultSourceRobustnessValidated") is True,
        "activeFailingSourceNotViableBlockerAbsent": isinstance(registry, dict)
        and registry.get("activeFailingSourceNotViableBlockerPresent") is False,
    }
    return {
        "schemaVersion": "video_to_analysis_promoted_runtime_registry_audit_v1",
        "generatedAt": utc_now_iso(),
        "registryPath": str(registry_path),
        "checks": checks,
        "registryMatchesPromotedV7_2DefaultRuntime": all(checks.values()),
    }


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    smokes: list[dict[str, Any]] = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        for route in OPERATOR_VISIBLE_ROUTES:
            api_response = await client.get(route["apiRoutePath"])
            html_response = await client.get(route["htmlRoutePath"])
            api_payload: dict[str, Any] = {}
            if api_response.headers.get("content-type", "").startswith("application/json"):
                api_payload = api_response.json()
            api_title = str(api_payload.get("title") or "")
            html_text_matches = route["expectedHtmlText"] in html_response.text or (bool(api_title) and api_title in html_response.text)
            checks = {
                "apiRouteReadable": api_response.status_code == 200,
                "htmlRouteReadable": html_response.status_code == 200,
                "apiSchemaVersionMatches": api_payload.get("schemaVersion") == route["expectedSchemaVersion"],
                "htmlContainsExpectedText": html_text_matches,
            }
            smokes.append(
                {
                    "id": route["id"],
                    "apiRoutePath": route["apiRoutePath"],
                    "htmlRoutePath": route["htmlRoutePath"],
                    "apiRouteStatusCode": api_response.status_code,
                    "htmlRouteStatusCode": html_response.status_code,
                    "apiSchemaVersion": api_payload.get("schemaVersion"),
                    "checks": checks,
                    "routeSmokePassed": all(checks.values()),
                }
            )
    return {
        "schemaVersion": "video_to_analysis_operator_visible_route_smoke_audit_v1",
        "generatedAt": utc_now_iso(),
        "routeSmokes": smokes,
        "routeSmokePassedCount": sum(1 for row in smokes if row["routeSmokePassed"]),
        "operatorVisibleRouteSmokePassed": all(row["routeSmokePassed"] for row in smokes),
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_promoted_runtime_operator_acceptance_trial(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "promotion_review_closeout_summary.json")
    closeout_ready = _promotion_closeout_ready(closeout_summary)
    registry_audit = _registry_audit(storage_root)
    route_audit = _route_smoke(storage_root) if closeout_ready else {
        "schemaVersion": "video_to_analysis_operator_visible_route_smoke_audit_v1",
        "generatedAt": utc_now_iso(),
        "routeSmokes": [],
        "routeSmokePassedCount": 0,
        "operatorVisibleRouteSmokePassed": False,
        "skipReason": BLOCKER_PROMOTION_CLOSEOUT_MISSING,
    }

    registry_ready = registry_audit["registryMatchesPromotedV7_2DefaultRuntime"] is True
    routes_ready = route_audit["operatorVisibleRouteSmokePassed"] is True
    goal = bool(closeout_ready and registry_ready and routes_ready)
    if not closeout_ready:
        primary_blocker = BLOCKER_PROMOTION_CLOSEOUT_MISSING
        next_lever = NEXT_PROMOTION_CLOSEOUT
        english = "Promotion review closeout is missing or unsafe; close promotion review before operator acceptance."
    elif not registry_ready:
        primary_blocker = BLOCKER_RUNTIME_REGISTRY_GAP
        next_lever = NEXT_REGISTRY_REPAIR
        english = "Promoted runtime registry does not match the v7.2 default-runtime contract."
    elif not routes_ready:
        primary_blocker = BLOCKER_OPERATOR_ROUTE_GAP
        next_lever = NEXT_ROUTE_REPAIR
        english = "One or more operator-visible product routes failed promoted-runtime acceptance smoke."
    else:
        primary_blocker = None
        next_lever = NEXT_RELEASE_CLOSEOUT
        english = "Promoted-runtime operator acceptance passed. Close the promoted runtime release next."

    checklist = {
        "schemaVersion": "video_to_analysis_promoted_runtime_operator_acceptance_checklist_v1",
        "generatedAt": utc_now_iso(),
        "checks": {
            "promotionReviewCloseoutReady": closeout_ready,
            "registryMatchesPromotedV7_2DefaultRuntime": registry_ready,
            "operatorVisibleRouteSmokePassed": routes_ready,
            "trainingNotExecutedByTrial": True,
            "promotionMutationNotExecutedByTrial": True,
            "runtimeDefaultMutationNotExecutedByTrial": True,
        },
    }
    checklist["allChecklistItemsPassed"] = all(checklist["checks"].values())

    summary = {
        "batchName": "video_to_analysis_promoted_runtime_operator_acceptance_trial",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotedRuntimeOperatorAcceptancePassed": goal,
        "registryMatchesPromotedV7_2DefaultRuntime": registry_ready,
        "operatorVisibleRouteSmokePassed": routes_ready,
        "routeSmokePassedCount": route_audit.get("routeSmokePassedCount", 0),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_operator_acceptance_trial_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_registry_audit.json": registry_audit,
            "operator_visible_route_smoke_audit.json": route_audit,
            "operator_acceptance_checklist.json": checklist,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Operator Acceptance Trial",
    )


def main() -> None:
    main_for(
        "Run video-to-analysis promoted runtime operator acceptance trial.",
        run_video_to_analysis_promoted_runtime_operator_acceptance_trial,
    )


if __name__ == "__main__":
    main()
