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

DEFAULT_PLAN_DIR_NAME = "video_to_analysis_post_release_monitoring_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_post_release_monitoring_route_binding_v1"

BLOCKER_PLAN_MISSING = "video_to_analysis_post_release_monitoring_plan_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_post_release_monitoring_route_smoke_failed"
NEXT_PLAN = "video_to_analysis_post_release_monitoring_plan"
NEXT_REPAIR = "video_to_analysis_post_release_monitoring_route_repair"
NEXT_CLOSEOUT = "video_to_analysis_post_release_monitoring_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_post_release_monitoring_route_binding",
                "successCriteria": ["serve monitoring API and HTML routes", "preserve all guardrails"],
                "failureAdaptation": "If monitoring plan truth is missing, route back to monitoring plan.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "post_release_monitoring_route_repair",
                "successCriteria": ["repair only view model, route contract, or HTML rendering"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "post_release_monitoring_route_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to monitoring plan, route repair, or monitoring closeout.",
            },
        ],
    }


def _plan_ready(summary: dict[str, Any] | None, plan: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    checks = plan.get("monitoringChecks") if isinstance(plan, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("postReleaseMonitoringPlanReady") is True
        and summary.get("monitoringCheckCount") == 4
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(checks, list)
        and len(checks) == 4
        and isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/post-release-monitoring"
        and contract.get("htmlRoutePath") == "/video-to-analysis/post-release-monitoring"
        and contract.get("allowsTraining") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False
    )


def _view_model(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_post_release_monitoring_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Post-release monitoring",
        "activeRuntimeDefaultVersion": plan.get("activeRuntimeDefaultVersion"),
        "runtimeDefaultRolloutClosed": plan.get("runtimeDefaultRolloutClosed"),
        "monitoringCadence": plan.get("monitoringCadence", "per_release_and_daily_smoke"),
        "monitoringChecks": plan.get("monitoringChecks", []),
        "escalationPolicy": plan.get("escalationPolicy", {}),
        "nextRecommendedNextLever": NEXT_CLOSEOUT,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    checks = "\n".join(
        f"<li><strong>{escape(str(row.get('id')))}</strong>: {escape(str(row.get('expected', row.get('route', ''))))}</li>"
        for row in view_model.get("monitoringChecks", [])
        if isinstance(row, dict)
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Post-release monitoring</title></head>",
            "<body>",
            "<h1>Post-release monitoring</h1>",
            f"<p>Cadence: {escape(str(view_model.get('monitoringCadence')))}</p>",
            f"<p>Active runtime default: <code>{escape(str(view_model.get('activeRuntimeDefaultVersion')))}</code></p>",
            f"<ol>{checks}</ol>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/post-release-monitoring")
        html_response = await client.get("/video-to-analysis/post-release-monitoring")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/post-release-monitoring",
        "htmlRoutePath": "/video-to-analysis/post-release-monitoring",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "monitoringCheckCount": len(api_payload.get("monitoringChecks", [])) if isinstance(api_payload.get("monitoringChecks"), list) else 0,
        "htmlContainsTitle": "Post-release monitoring" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_post_release_monitoring_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    plan_root = root / DEFAULT_PLAN_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    plan_summary = load_json(plan_root / "post_release_monitoring_plan_summary.json")
    plan = load_json(plan_root / "post_release_monitoring_plan.json")
    route_contract = load_json(plan_root / "post_release_monitoring_route_contract.json")
    plan_ready = _plan_ready(plan_summary, plan, route_contract)

    if plan_ready and isinstance(plan, dict):
        view_model = _view_model(plan)
        bound_contract = {
            "schemaVersion": "video_to_analysis_post_release_monitoring_bound_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/post-release-monitoring",
            "htmlRoutePath": "/video-to-analysis/post-release-monitoring",
            "postReleaseMonitoringRouteReady": True,
            "activeRuntimeDefaultVersion": "v7.3",
        }
        write_json(output_root / "post_release_monitoring_view_model.json", view_model)
        write_json(output_root / "post_release_monitoring_bound_route_contract.json", bound_contract)
        (output_root / "post_release_monitoring_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
        smoke = _route_smoke(Path(storage_root))
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0, "monitoringCheckCount": 0}

    route_ready = bool(
        plan_ready
        and smoke.get("apiRouteStatusCode") == 200
        and smoke.get("htmlRouteStatusCode") == 200
        and smoke.get("apiSchemaVersion") == "video_to_analysis_post_release_monitoring_view_model_v1"
        and smoke.get("monitoringCheckCount") == 4
        and smoke.get("htmlContainsTitle") is True
    )

    if not plan_ready:
        primary_blocker = BLOCKER_PLAN_MISSING
        next_lever = NEXT_PLAN
        english = "Post-release monitoring plan is missing or unsafe; build plan before route binding."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_REPAIR
        english = "Post-release monitoring route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_CLOSEOUT
        english = "Post-release monitoring route is bound and smoked. Close monitoring plan next."

    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = route_ready
    false_flags["runtimeDefaultMutationAllowed"] = route_ready
    summary = {
        "batchName": "video_to_analysis_post_release_monitoring_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "postReleaseMonitoringRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/post-release-monitoring",
        "htmlRoutePath": "/video-to-analysis/post-release-monitoring",
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        **false_flags,
        "activeRuntimeDefaultVersion": "v7.3" if route_ready else None,
        "runtimeDefaultRolloutClosed": route_ready,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="post_release_monitoring_route_binding_summary.json",
        summary=summary,
        artifacts={
            "post_release_monitoring_route_smoke_audit.json": smoke,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Post Release Monitoring Route Binding",
    )


def main() -> None:
    main_for("Bind video-to-analysis post-release monitoring route.", run_video_to_analysis_post_release_monitoring_route_binding)


if __name__ == "__main__":
    main()
