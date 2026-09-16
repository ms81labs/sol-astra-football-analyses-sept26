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
    write_json,
    write_outcome,
)

DEFAULT_STORAGE_HYGIENE_DIR_NAME = "video_to_analysis_storage_retention_and_artifact_hygiene_v1"
DEFAULT_STEADY_STATE_DIR_NAME = "video_to_analysis_steady_state_monitoring_cycle_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_operator_dashboard_polish_v1"
DEFAULT_RELEASED_RUNTIME_VERSION = "v7.3"

BLOCKER_STORAGE_HYGIENE_MISSING = "video_to_analysis_operator_dashboard_storage_hygiene_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_operator_dashboard_route_smoke_failed"
NEXT_STORAGE_HYGIENE = "video_to_analysis_storage_retention_and_artifact_hygiene"
NEXT_ROUTE_REPAIR = "video_to_analysis_operator_dashboard_route_repair"
NEXT_EXTERNAL_SOURCE_PATH = "football_external_benchmark_real_source_path_consolidation"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "operator_dashboard_polish",
                "successCriteria": [
                    "bind current runtime health",
                    "bind storage hygiene truth",
                    "serve operator dashboard API and HTML",
                ],
                "failureAdaptation": "If storage hygiene truth is missing, route back to storage hygiene.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operator_dashboard_route_repair",
                "successCriteria": ["repair only saved view model, route contract, or HTML rendering"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operator_dashboard_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not mutate runtime state.",
            },
        ],
    }


def _storage_hygiene_ready(summary: dict[str, Any] | None, policy: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("storageHygienePlanReady") is True
        and summary.get("artifactInventoryReady") is True
        and summary.get("retentionPolicyReady") is True
        and summary.get("cleanupMutationExecuted") is False
        and summary.get("generatedTruthDeleteAllowed") is False
        and isinstance(policy, dict)
        and policy.get("retentionPolicyReady") is True
        and policy.get("generatedTruthDeleteAllowed") is False
    )


def _view_model(storage_summary: dict[str, Any], steady_summary: dict[str, Any] | None) -> dict[str, Any]:
    steady_summary = steady_summary if isinstance(steady_summary, dict) else {}
    released_runtime_version = steady_summary.get("releasedRuntimeVersion") or DEFAULT_RELEASED_RUNTIME_VERSION
    return {
        "schemaVersion": "video_to_analysis_operator_dashboard_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Video-to-analysis operator dashboard",
        "releasedRuntimeVersion": released_runtime_version,
        "promotedRuntimeHealthy": steady_summary.get("promotedRuntimeHealthy") is True,
        "steadyStateMonitoringCyclePassed": steady_summary.get("steadyStateMonitoringCyclePassed") is True,
        "routeSmokePassedCount": steady_summary.get("routeSmokePassedCount"),
        "oldFailingSourceNotViableBlockerDead": steady_summary.get("oldFailingSourceNotViableBlockerDead") is True,
        "storageHygienePlanReady": storage_summary.get("storageHygienePlanReady") is True,
        "totalInventoriedBytes": storage_summary.get("totalInventoriedBytes"),
        "cleanupExecutionReady": storage_summary.get("cleanupExecutionReady") is True,
        "cleanupMutationExecuted": storage_summary.get("cleanupMutationExecuted") is True,
        "generatedTruthDeleteAllowed": storage_summary.get("generatedTruthDeleteAllowed") is True,
        "operatorStatusCards": [
            {
                "id": "runtime",
                "label": "Runtime",
                "value": released_runtime_version,
                "state": "healthy" if steady_summary.get("promotedRuntimeHealthy") is True else "unknown",
            },
            {
                "id": "routes",
                "label": "Route smoke",
                "value": str(steady_summary.get("routeSmokePassedCount") or 0),
                "state": "healthy" if steady_summary.get("routeSmokePassedCount") == 5 else "attention",
            },
            {
                "id": "storage",
                "label": "Storage inventory",
                "value": str(storage_summary.get("inventoryRowCount") or 0),
                "state": "healthy" if storage_summary.get("storageHygienePlanReady") is True else "attention",
            },
        ],
        "nextRecommendedNextLever": NEXT_EXTERNAL_SOURCE_PATH,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    cards = "\n".join(
        "<li>"
        f"<strong>{escape(str(card.get('label')))}</strong>: "
        f"{escape(str(card.get('value')))} "
        f"<span>{escape(str(card.get('state')))}</span>"
        "</li>"
        for card in view_model.get("operatorStatusCards", [])
        if isinstance(card, dict)
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Video-to-analysis operator dashboard</title></head>",
            "<body>",
            "<h1>Video-to-analysis operator dashboard</h1>",
            f"<p>Released runtime: <strong>{escape(str(view_model.get('releasedRuntimeVersion')))}</strong></p>",
            f"<p>Next: <code>{escape(str(view_model.get('nextRecommendedNextLever')))}</code></p>",
            f"<ul>{cards}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/operator-dashboard")
        html_response = await client.get("/video-to-analysis/operator-dashboard")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/operator-dashboard",
        "htmlRoutePath": "/video-to-analysis/operator-dashboard",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "htmlContainsTitle": "Video-to-analysis operator dashboard" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_operator_dashboard_polish(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    storage_root_artifacts = root / DEFAULT_STORAGE_HYGIENE_DIR_NAME
    steady_root = root / DEFAULT_STEADY_STATE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    storage_summary = load_json(storage_root_artifacts / "storage_retention_and_artifact_hygiene_summary.json")
    retention_policy = load_json(storage_root_artifacts / "artifact_retention_policy.json")
    steady_summary = load_json(steady_root / "steady_state_monitoring_cycle_summary.json")
    storage_ready = _storage_hygiene_ready(storage_summary, retention_policy)

    if storage_ready and isinstance(storage_summary, dict):
        view_model = _view_model(storage_summary, steady_summary)
        route_contract = {
            "schemaVersion": "video_to_analysis_operator_dashboard_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/operator-dashboard",
            "htmlRoutePath": "/video-to-analysis/operator-dashboard",
            "operatorDashboardRouteReady": True,
            "allowsTraining": False,
            "allowsPromotionMutation": False,
            "allowsRuntimeDefaultMutation": False,
        }
        write_json(output_root / "operator_dashboard_view_model.json", view_model)
        write_json(output_root / "operator_dashboard_route_contract.json", route_contract)
        (output_root / "operator_dashboard_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
        smoke = _route_smoke(storage_root)
    else:
        smoke = {
            "apiRoutePath": "/api/video-to-analysis/operator-dashboard",
            "htmlRoutePath": "/video-to-analysis/operator-dashboard",
            "apiRouteStatusCode": 0,
            "htmlRouteStatusCode": 0,
            "apiSchemaVersion": None,
            "htmlContainsTitle": False,
        }

    route_ready = bool(
        storage_ready
        and smoke["apiRouteStatusCode"] == 200
        and smoke["htmlRouteStatusCode"] == 200
        and smoke["apiSchemaVersion"] == "video_to_analysis_operator_dashboard_view_model_v1"
        and smoke["htmlContainsTitle"] is True
    )
    if not storage_ready:
        primary_blocker = BLOCKER_STORAGE_HYGIENE_MISSING
        next_lever = NEXT_STORAGE_HYGIENE
        goal = False
        english = "Storage hygiene truth is missing or unsafe; complete storage retention before dashboard polish."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
        goal = False
        english = "Operator dashboard route smoke failed; repair dashboard route binding only."
    else:
        primary_blocker = None
        next_lever = NEXT_EXTERNAL_SOURCE_PATH
        goal = True
        english = "Operator dashboard is polished and route-smoked. Continue to external benchmark real-source path consolidation."

    summary = {
        "batchName": "video_to_analysis_operator_dashboard_polish",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "operatorDashboardPolished": goal,
        "operatorDashboardRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/operator-dashboard",
        "htmlRoutePath": "/video-to-analysis/operator-dashboard",
        "apiRouteStatusCode": smoke["apiRouteStatusCode"],
        "htmlRouteStatusCode": smoke["htmlRouteStatusCode"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="operator_dashboard_polish_summary.json",
        summary=summary,
        artifacts={
            "operator_dashboard_route_smoke_audit.json": smoke,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Operator Dashboard Polish",
    )


def main() -> None:
    main_for("Polish video-to-analysis operator dashboard.", run_video_to_analysis_operator_dashboard_polish)


if __name__ == "__main__":
    main()
