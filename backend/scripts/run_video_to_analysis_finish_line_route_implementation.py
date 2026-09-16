from __future__ import annotations

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

DEFAULT_BINDING_DIR_NAME = "video_to_analysis_finish_line_product_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_route_implementation_v1"

BLOCKER_BINDING_MISSING = "video_to_analysis_finish_line_product_binding_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_finish_line_route_smoke_failed"
NEXT_BINDING = "video_to_analysis_finish_line_product_binding"
NEXT_ROUTE_REPAIR = "video_to_analysis_finish_line_route_repair"
NEXT_EXECUTION_PLAN = "video_to_analysis_finish_line_product_execution_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "video_to_analysis_finish_line_route_implementation", "successCriteria": ["smoke API and HTML routes"], "failureAdaptation": "If binding is missing, route back to product binding."},
            {"attemptNumber": 2, "attemptApproachFamily": "video_to_analysis_finish_line_route_repair", "successCriteria": ["repair route loading/rendering only"], "failureAdaptation": "If routes still fail, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": "video_to_analysis_finish_line_route_blocker_summary", "successCriteria": ["write blocker truth"], "failureAdaptation": "Route to binding, route repair, or product execution plan."},
        ],
    }


def _binding_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("finishLineProductBindingReady") is True
        and isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/finish-line"
        and contract.get("htmlRoutePath") == "/video-to-analysis/finish-line"
    )


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)

    async def _run() -> dict[str, Any]:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/finish-line")
            html_response = await client.get("/video-to-analysis/finish-line")
        return {
            "apiRouteStatusCode": api_response.status_code,
            "htmlRouteStatusCode": html_response.status_code,
            "apiSchemaVersion": api_response.json().get("schemaVersion") if api_response.status_code == 200 else None,
            "htmlContainsTitle": "Video To Analysis Finish Line" in html_response.text,
        }

    import asyncio

    return asyncio.run(_run())


def run_video_to_analysis_finish_line_route_implementation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    binding_root = root / DEFAULT_BINDING_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    binding_summary = load_json(binding_root / "finish_line_product_binding_summary.json")
    route_contract = load_json(binding_root / "finish_line_product_route_contract.json")
    binding_ready = _binding_ready(binding_summary, route_contract)
    route_smoke = _route_smoke(Path(storage_root)) if binding_ready else {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0, "htmlContainsTitle": False}
    route_ready = bool(binding_ready and route_smoke.get("apiRouteStatusCode") == 200 and route_smoke.get("htmlRouteStatusCode") == 200 and route_smoke.get("apiSchemaVersion") == "video_to_analysis_finish_line_product_view_model_v1")
    if not binding_ready:
        primary_blocker = BLOCKER_BINDING_MISSING
        next_lever = NEXT_BINDING
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_ROUTE_REPAIR
    else:
        primary_blocker = None
        next_lever = NEXT_EXECUTION_PLAN
    summary = {
        "batchName": "video_to_analysis_finish_line_route_implementation",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "finishLineRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/finish-line",
        "htmlRoutePath": "/video-to-analysis/finish-line",
        "apiRouteStatusCode": route_smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": route_smoke.get("htmlRouteStatusCode"),
        "normalMatchStorageMutationExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Finish-line API and HTML routes are live. Plan the next bounded product execution step." if route_ready else "Finish-line route smoke failed or binding is missing.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "binding_missing", "selected": primary_blocker == BLOCKER_BINDING_MISSING, "primaryBlocker": BLOCKER_BINDING_MISSING, "nextRecommendedNextLever": NEXT_BINDING},
            {"condition": "route_smoke_failed", "selected": primary_blocker == BLOCKER_ROUTE_SMOKE_FAILED, "primaryBlocker": BLOCKER_ROUTE_SMOKE_FAILED, "nextRecommendedNextLever": NEXT_ROUTE_REPAIR},
            {"condition": "route_ready", "selected": route_ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EXECUTION_PLAN},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_route_implementation_summary.json",
        summary=summary,
        artifacts={
            "finish_line_route_smoke_audit.json": route_smoke,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Route Implementation",
    )


def main() -> None:
    main_for("Smoke the finish-line product API and HTML routes.", run_video_to_analysis_finish_line_route_implementation)


if __name__ == "__main__":
    main()
