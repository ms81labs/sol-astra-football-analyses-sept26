from __future__ import annotations

import asyncio
from html import escape
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

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_broader_real_video_acceptance_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_acceptance_report_route_binding_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_broader_real_video_acceptance_closeout_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_acceptance_report_route_smoke_failed"
NEXT_CLOSEOUT = "video_to_analysis_broader_real_video_acceptance_closeout"
NEXT_ROUTE_REPAIR = "video_to_analysis_acceptance_report_route_binding_repair"
NEXT_PRODUCT_BACKLOG = "video_to_analysis_acceptance_report_product_backlog"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_acceptance_report_route_binding",
                "successCriteria": [
                    "bind the broader acceptance report to API and HTML routes",
                    "smoke the saved route payloads",
                    "preserve detector/download/training/promotion/runtime guardrails",
                ],
                "failureAdaptation": "If closeout truth is missing, route back to closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "acceptance_report_route_binding_repair",
                "successCriteria": ["repair only route contract, saved view model, or HTML rendering"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "acceptance_report_route_binding_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to closeout, route repair, or acceptance report product backlog.",
            },
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None, report: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("broaderRealVideoAcceptanceClosed") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
        and summary.get("normalStorageMutationObservedFromExecution") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(report, dict)
        and report.get("schemaVersion") == "video_to_analysis_broader_real_video_acceptance_report_v1"
        and report.get("acceptanceResult") == "passed"
        and report.get("acceptanceCaseCount") == 5
        and report.get("acceptancePassedCaseCount") == 5
    )


def _build_view_model(report: dict[str, Any]) -> dict[str, Any]:
    passed = int(report.get("acceptancePassedCaseCount") or 0)
    total = int(report.get("acceptanceCaseCount") or 0)
    return {
        "schemaVersion": "video_to_analysis_acceptance_report_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Broader Real-Video Acceptance",
        "subtitle": "Five-case product acceptance report",
        "acceptanceResult": report.get("acceptanceResult"),
        "scoreboard": [
            {"label": "Acceptance cases passed", "value": f"{passed} / {total}"},
            {
                "label": "Normal storage mutation",
                "value": "observed in approved execution" if report.get("normalStorageMutationObservedFromExecution") else "not observed",
            },
            {"label": "Next lever", "value": NEXT_PRODUCT_BACKLOG},
        ],
        "guardrails": {
            "detectorEvaluationReady": False,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
            "downloadsReady": False,
        },
        "operatorActions": [
            "Use this page to review the broader real-video acceptance result.",
            "Move next into acceptance-report product backlog hardening.",
            "Do not start detector evaluation, training, promotion, or runtime mutation from this report.",
        ],
    }


def _render_html(view_model: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<li><strong>{escape(str(row.get('label')))}</strong>: {escape(str(row.get('value')))}</li>"
        for row in view_model.get("scoreboard", [])
        if isinstance(row, dict)
    )
    actions = "\n".join(f"<li>{escape(str(action))}</li>" for action in view_model.get("operatorActions", []))
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Broader Real-Video Acceptance</title></head>",
            "<body>",
            f"<h1>{escape(str(view_model.get('title')))}</h1>",
            f"<p>{escape(str(view_model.get('subtitle')))}</p>",
            "<section><h2>Scoreboard</h2><ul>",
            rows,
            "</ul></section>",
            "<section><h2>Operator actions</h2><ul>",
            actions,
            "</ul></section>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/acceptance-report")
        html_response = await client.get("/video-to-analysis/acceptance-report")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/acceptance-report",
        "htmlRoutePath": "/video-to-analysis/acceptance-report",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "apiAcceptanceResult": api_payload.get("acceptanceResult"),
        "htmlContainsTitle": "Broader Real-Video Acceptance" in html_response.text,
        "htmlContainsScore": "5 / 5" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_acceptance_report_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "broader_real_video_acceptance_closeout_summary.json")
    closeout_report = load_json(closeout_root / "broader_real_video_acceptance_report.json")
    closeout_ready = _closeout_ready(closeout_summary, closeout_report)

    if closeout_ready and isinstance(closeout_report, dict):
        view_model = _build_view_model(closeout_report)
        route_contract = {
            "schemaVersion": "video_to_analysis_acceptance_report_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/acceptance-report",
            "htmlRoutePath": "/video-to-analysis/acceptance-report",
            "acceptanceReportRouteReady": True,
            "allowsDetectorEvaluation": False,
            "allowsCandidateEvaluationReadiness": False,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "allowsDownloads": False,
        }
        html = _render_html(view_model)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "acceptance_report_render_smoke.html").write_text(html, encoding="utf-8")
        from backend.scripts.football_external_real_eval_chain_common import write_json

        write_json(output_root / "acceptance_report_view_model.json", view_model)
        write_json(output_root / "acceptance_report_route_contract.json", route_contract)
        smoke = _route_smoke(Path(storage_root))
    else:
        view_model = {}
        route_contract = {}
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0}

    route_ready = bool(
        closeout_ready
        and smoke.get("apiRouteStatusCode") == 200
        and smoke.get("htmlRouteStatusCode") == 200
        and smoke.get("apiSchemaVersion") == "video_to_analysis_acceptance_report_view_model_v1"
        and smoke.get("apiAcceptanceResult") == "passed"
        and smoke.get("htmlContainsTitle") is True
        and smoke.get("htmlContainsScore") is True
    )

    if not closeout_ready:
        primary_blocker = BLOCKER_CLOSEOUT_MISSING
        next_lever = NEXT_CLOSEOUT
        english = "Broader real-video acceptance closeout is missing or unsafe; close acceptance before route binding."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
        english = "Acceptance report route binding wrote artifacts but route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_PRODUCT_BACKLOG
        english = "Acceptance report API and HTML routes are bound and smoked. Build the product backlog next."

    summary = {
        "batchName": "video_to_analysis_acceptance_report_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "acceptanceReportRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/acceptance-report",
        "htmlRoutePath": "/video-to-analysis/acceptance-report",
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        "acceptanceCaseCount": 5 if route_ready else 0,
        "acceptancePassedCaseCount": 5 if route_ready else 0,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "closeout_missing",
                "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING,
                "primaryBlocker": BLOCKER_CLOSEOUT_MISSING,
                "nextRecommendedNextLever": NEXT_CLOSEOUT,
            },
            {
                "condition": "route_smoke_failed",
                "selected": primary_blocker == BLOCKER_ROUTE_SMOKE_FAILED,
                "primaryBlocker": BLOCKER_ROUTE_SMOKE_FAILED,
                "nextRecommendedNextLever": NEXT_ROUTE_REPAIR,
            },
            {
                "condition": "acceptance_report_route_ready",
                "selected": route_ready,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_PRODUCT_BACKLOG,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="acceptance_report_route_binding_summary.json",
        summary=summary,
        artifacts={
            "acceptance_report_route_smoke_audit.json": smoke,
            "acceptance_report_guardrail_audit.json": {
                "generatedAt": utc_now_iso(),
                "closeoutReady": closeout_ready,
                "routeReady": route_ready,
                "detectorEvaluationStillBlocked": True,
                "downloadsStillBlocked": True,
                "trainingStillBlocked": True,
                "promotionStillBlocked": True,
                "runtimeMutationStillBlocked": True,
            },
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Acceptance Report Route Binding",
    )


def main() -> None:
    main_for("Bind broader real-video acceptance report to product routes.", run_video_to_analysis_acceptance_report_route_binding)


if __name__ == "__main__":
    main()
