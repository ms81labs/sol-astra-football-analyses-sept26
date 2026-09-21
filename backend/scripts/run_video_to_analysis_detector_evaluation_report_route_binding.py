from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
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

DEFAULT_REPORT_DIR_NAME = "video_to_analysis_detector_evaluation_report_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_report_route_binding_v1"

BLOCKER_REPORT_MISSING = "video_to_analysis_detector_evaluation_report_binding_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_detector_evaluation_report_route_smoke_failed"
NEXT_REPORT_BINDING = "video_to_analysis_detector_evaluation_report_binding"
NEXT_ROUTE_REPAIR = "video_to_analysis_detector_evaluation_report_route_repair"
NEXT_CLOSEOUT = "video_to_analysis_detector_evaluation_lane_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "detector_evaluation_report_route_binding",
                "successCriteria": ["serve detector evaluation API and HTML report routes"],
                "failureAdaptation": "If report binding truth is missing, route back to report binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "detector_evaluation_report_route_repair",
                "successCriteria": ["repair only route-bound report artifacts or app route contract"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "detector_evaluation_route_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to report binding, route repair, or lane closeout.",
            },
        ],
    }


def _report_ready(summary: dict[str, Any] | None, view_model: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("detectorEvaluationReportReady") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(view_model, dict)
        and view_model.get("schemaVersion") == "video_to_analysis_detector_evaluation_report_view_model_v1"
        and view_model.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/detector-evaluation-report"
        and contract.get("htmlRoutePath") == "/video-to-analysis/detector-evaluation-report"
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/detector-evaluation-report")
        html_response = await client.get("/video-to-analysis/detector-evaluation-report")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/detector-evaluation-report",
        "htmlRoutePath": "/video-to-analysis/detector-evaluation-report",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "htmlContainsTitle": "Detector Evaluation Report" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_detector_evaluation_report_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    report_root = root / DEFAULT_REPORT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    report_summary = load_json(report_root / "detector_evaluation_report_binding_summary.json")
    view_model = load_json(report_root / "detector_evaluation_report_view_model.json")
    contract = load_json(report_root / "detector_evaluation_report_route_contract.json")
    html_path = report_root / "detector_evaluation_report_render_smoke.html"
    report_ready = _report_ready(report_summary, view_model, contract) and html_path.exists()

    if report_ready and isinstance(view_model, dict) and isinstance(contract, dict):
        write_json(output_root / "detector_evaluation_report_view_model.json", view_model)
        bound_contract = dict(contract)
        bound_contract["schemaVersion"] = "video_to_analysis_detector_evaluation_report_bound_route_contract_v1"
        bound_contract["detectorEvaluationReportRouteReady"] = True
        write_json(output_root / "detector_evaluation_report_bound_route_contract.json", bound_contract)
        shutil.copyfile(html_path, output_root / "detector_evaluation_report_render_smoke.html")
        smoke = _route_smoke(Path(storage_root))
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0, "apiSchemaVersion": None, "htmlContainsTitle": False}

    route_ready = bool(
        report_ready
        and smoke.get("apiRouteStatusCode") == 200
        and smoke.get("htmlRouteStatusCode") == 200
        and smoke.get("apiSchemaVersion") == "video_to_analysis_detector_evaluation_report_view_model_v1"
        and smoke.get("htmlContainsTitle") is True
    )

    if not report_ready:
        primary_blocker = BLOCKER_REPORT_MISSING
        next_lever = NEXT_REPORT_BINDING
        english = "Detector evaluation report binding is missing or unsafe; bind report before route smoke."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
        english = "Detector evaluation report route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_CLOSEOUT
        english = "Detector evaluation report route is bound and smoked. Close the detector evaluation lane next."

    summary = {
        "batchName": "video_to_analysis_detector_evaluation_report_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "detectorEvaluationReportRouteReady": route_ready,
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": route_ready,
        "runtimeDefaultRolloutClosed": route_ready,
        "activeRuntimeDefaultVersion": "v7.3" if route_ready else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_report_route_binding_summary.json",
        summary=summary,
        artifacts={
            "detector_evaluation_report_route_smoke_audit.json": smoke,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Report Route Binding",
    )


def main() -> None:
    main_for(
        "Bind video-to-analysis detector evaluation report route.",
        run_video_to_analysis_detector_evaluation_report_route_binding,
    )


if __name__ == "__main__":
    main()
