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
from backend.scripts.football_external_real_eval_chain_common import main_for, write_json  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    load_json,
    paired_or_latest_versioned_dir,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_bounded_next_sample_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_bounded_next_sample_report_route_binding_v1"
BLOCKER_EXECUTION_MISSING = "video_to_analysis_bounded_next_sample_execution_missing"
BLOCKER_ROUTE_FAILED = "video_to_analysis_bounded_next_sample_report_route_failed"
NEXT_EXECUTION = "video_to_analysis_bounded_next_sample_execution"
NEXT_REPAIR = "video_to_analysis_bounded_next_sample_report_route_repair"
NEXT_CLOSEOUT = "video_to_analysis_bounded_next_sample_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "bounded_next_sample_report_route_binding"},
        {"attemptNumber": 2, "attemptApproachFamily": "bounded_next_sample_report_route_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "bounded_next_sample_report_blocker_summary"},
    ]}


def _render_html(view_model: dict[str, Any]) -> str:
    result = view_model.get("executionResult", {}) if isinstance(view_model.get("executionResult"), dict) else {}
    return "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head><meta charset=\"utf-8\"><title>Bounded next-sample report</title></head>",
        "<body>",
        "<h1>Bounded next-sample report</h1>",
        f"<p>Sample: {escape(str(view_model.get('sampleId')))}</p>",
        f"<p>Status: {escape(str(result.get('status')))}</p>",
        "</body>",
        "</html>",
        "",
    ])


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/bounded-next-sample-report")
        html_response = await client.get("/video-to-analysis/bounded-next-sample-report")
    payload = api_response.json() if api_response.headers.get("content-type", "").startswith("application/json") else {}
    return {
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": payload.get("schemaVersion"),
        "htmlContainsTitle": "Bounded next-sample report" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_bounded_next_sample_report_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)
    execution_dir = paired_or_latest_versioned_dir(
        root,
        output_dir_name=output_dir_name,
        input_prefix="video_to_analysis_bounded_next_sample_execution",
        default_dir_name=DEFAULT_EXECUTION_DIR_NAME,
    )
    execution_summary = load_json(execution_dir / "bounded_next_sample_execution_summary.json")
    audit = load_json(execution_dir / "bounded_next_sample_execution_audit.json")
    execution_ready = bool(
        isinstance(execution_summary, dict)
        and execution_summary.get("goalAchieved") is True
        and isinstance(audit, dict)
        and audit.get("boundedNextSampleExecuted") is True
    )
    if execution_ready:
        result = audit.get("executionResult", {})
        view_model = {
            "schemaVersion": "video_to_analysis_bounded_next_sample_report_view_model_v1",
            "generatedAt": utc_now_iso(),
            "title": "Bounded next-sample report",
            "sourceExecutionDir": execution_dir.name,
            "sampleId": audit.get("executedSampleId"),
            "executionResult": result,
            "nextRecommendedNextLever": NEXT_CLOSEOUT,
        }
        contract = {
            "schemaVersion": "video_to_analysis_bounded_next_sample_report_route_contract_v1",
            "apiRoutePath": "/api/video-to-analysis/bounded-next-sample-report",
            "htmlRoutePath": "/video-to-analysis/bounded-next-sample-report",
        }
        write_json(output_root / "bounded_next_sample_report_view_model.json", view_model)
        write_json(output_root / "bounded_next_sample_report_route_contract.json", contract)
        (output_root / "bounded_next_sample_report_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
        smoke = _route_smoke(storage_root)
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0, "apiSchemaVersion": None, "htmlContainsTitle": False}
    route_ready = bool(
        execution_ready
        and smoke["apiRouteStatusCode"] == 200
        and smoke["htmlRouteStatusCode"] == 200
        and smoke["apiSchemaVersion"] == "video_to_analysis_bounded_next_sample_report_view_model_v1"
        and smoke["htmlContainsTitle"] is True
    )
    blocker = None if route_ready else (BLOCKER_EXECUTION_MISSING if not execution_ready else BLOCKER_ROUTE_FAILED)
    next_lever = NEXT_CLOSEOUT if route_ready else (NEXT_EXECUTION if not execution_ready else NEXT_REPAIR)
    summary = guarded_summary(
        batch_name="video_to_analysis_bounded_next_sample_report_route_binding",
        goal=route_ready,
        primary_blocker=blocker,
        next_lever=next_lever,
        english="Bounded next-sample report route is bound and smoked." if route_ready else "Bounded next-sample report route is not ready.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"boundedNextSampleReportRouteReady": route_ready, "apiRouteStatusCode": smoke["apiRouteStatusCode"], "htmlRouteStatusCode": smoke["htmlRouteStatusCode"]},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="bounded_next_sample_report_route_binding_summary.json",
        summary=summary,
        artifacts={
            "bounded_next_sample_report_route_smoke_audit.json": smoke,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": blocker, "nextRecommendedNextLever": next_lever},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Bounded Next Sample Report Route Binding",
    )


def main() -> None:
    main_for("Bind bounded next-sample report route.", run_video_to_analysis_bounded_next_sample_report_route_binding)


if __name__ == "__main__":
    main()
