from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

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
    write_json,
    write_outcome,
)

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding_v1"

BLOCKER_EXECUTION_MISSING = "video_to_analysis_promoted_runtime_post_release_monitoring_execution_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_promoted_runtime_monitoring_report_route_failed"
NEXT_EXECUTION = "video_to_analysis_promoted_runtime_post_release_monitoring_execution"
NEXT_ROUTE_REPAIR = "video_to_analysis_promoted_runtime_monitoring_report_route_repair"
NEXT_COMPLETION = "video_to_analysis_promoted_runtime_operational_completion_summary"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promoted_runtime_monitoring_route_binding",
                "successCriteria": ["bind and smoke promoted-runtime monitoring report route"],
                "failureAdaptation": "If execution truth is missing, route back to monitoring execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promoted_runtime_monitoring_route_repair",
                "successCriteria": ["repair only route-bound view model, HTML, or app route"],
                "failureAdaptation": "If route smoke remains broken, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promoted_runtime_monitoring_route_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force operational completion.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("promotedRuntimeHealthPassed") is True
        and summary.get("routeSmokePassedCount") == 5
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("allMonitoringChecksPassed") is True
    )


def _view_model(summary: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_promoted_runtime_monitoring_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Promoted Runtime Monitoring",
        "promotedRuntimeHealthPassed": summary.get("promotedRuntimeHealthPassed") is True,
        "registryMatchesPromotedV7_2DefaultRuntime": summary.get("registryMatchesPromotedV7_2DefaultRuntime") is True,
        "routeSmokePassedCount": summary.get("routeSmokePassedCount"),
        "monitoringChecks": audit.get("monitoringChecks", {}),
        "nextRecommendedNextLever": NEXT_COMPLETION,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    checks = view_model.get("monitoringChecks") if isinstance(view_model.get("monitoringChecks"), dict) else {}
    rows = "\n".join(f"<li>{escape(str(key))}: {escape(str(value))}</li>" for key, value in checks.items())
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Promoted Runtime Monitoring</title></head>",
            "<body>",
            "<h1>Promoted Runtime Monitoring</h1>",
            f"<p>Health passed: {escape(str(view_model.get('promotedRuntimeHealthPassed')))}</p>",
            f"<ul>{rows}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/promoted-runtime-monitoring")
        html_response = await client.get("/video-to-analysis/promoted-runtime-monitoring")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "htmlContainsTitle": "Promoted Runtime Monitoring" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "promoted_runtime_post_release_monitoring_execution_summary.json")
    audit = load_json(execution_root / "promoted_runtime_monitoring_execution_audit.json")
    execution_ready = _execution_ready(execution_summary, audit)

    if execution_ready and isinstance(execution_summary, dict) and isinstance(audit, dict):
        view_model = _view_model(execution_summary, audit)
        route_contract = {
            "schemaVersion": "video_to_analysis_promoted_runtime_monitoring_bound_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/promoted-runtime-monitoring",
            "htmlRoutePath": "/video-to-analysis/promoted-runtime-monitoring",
        }
        write_json(output_root / "promoted_runtime_monitoring_view_model.json", view_model)
        write_json(output_root / "promoted_runtime_monitoring_bound_route_contract.json", route_contract)
        (output_root / "promoted_runtime_monitoring_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
        smoke = _route_smoke(Path(storage_root))
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0, "apiSchemaVersion": None, "htmlContainsTitle": False}

    route_ready = bool(
        execution_ready
        and smoke["apiRouteStatusCode"] == 200
        and smoke["htmlRouteStatusCode"] == 200
        and smoke["apiSchemaVersion"] == "video_to_analysis_promoted_runtime_monitoring_view_model_v1"
        and smoke["htmlContainsTitle"] is True
    )
    if not execution_ready:
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_EXECUTION
        english = "Promoted-runtime monitoring execution is missing or unsafe; execute monitoring before route binding."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
        english = "Promoted-runtime monitoring report route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_COMPLETION
        english = "Promoted-runtime monitoring report route is bound and smoked. Write operational completion next."

    summary = {
        "batchName": "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "promotedRuntimeMonitoringRouteReady": route_ready,
        "apiRouteStatusCode": smoke["apiRouteStatusCode"],
        "htmlRouteStatusCode": smoke["htmlRouteStatusCode"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promoted_runtime_post_release_monitoring_route_binding_summary.json",
        summary=summary,
        artifacts={
            "promoted_runtime_monitoring_route_smoke_audit.json": smoke,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promoted Runtime Post Release Monitoring Route Binding",
    )


def main() -> None:
    main_for(
        "Bind video-to-analysis promoted runtime post-release monitoring route.",
        run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding,
    )


if __name__ == "__main__":
    main()
