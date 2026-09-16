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

DEFAULT_HANDOFF_PACK_DIR_NAME = "video_to_analysis_operator_handoff_pack_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_operator_handoff_route_binding_v1"

BLOCKER_PACK_MISSING = "video_to_analysis_operator_handoff_pack_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_operator_handoff_route_smoke_failed"
NEXT_PACK = "video_to_analysis_operator_handoff_pack"
NEXT_REPAIR = "video_to_analysis_operator_handoff_route_repair"
NEXT_LANE_CLOSEOUT = "video_to_analysis_product_lane_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_operator_handoff_route_binding",
                "successCriteria": ["serve operator handoff API and HTML routes", "preserve all guardrails"],
                "failureAdaptation": "If pack truth is missing, route back to operator handoff pack.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operator_handoff_route_repair",
                "successCriteria": ["repair only saved view model, route contract, or HTML rendering"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operator_handoff_route_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to pack, route repair, or product lane closeout.",
            },
        ],
    }


def _pack_ready(summary: dict[str, Any] | None, pack: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("operatorHandoffPackReady") is True
        and summary.get("videoToAnalysisProductPathReady") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
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
        and isinstance(pack, dict)
        and pack.get("schemaVersion") == "video_to_analysis_operator_handoff_pack_v1"
        and pack.get("primaryOperatorRoute") == "/video-to-analysis/acceptance-report"
        and pack.get("activeRuntimeDefaultVersion") == "v7.3"
        and pack.get("runtimeDefaultRolloutClosed") is True
        and isinstance(contract, dict)
        and contract.get("apiRoutePath") == "/api/video-to-analysis/operator-handoff"
        and contract.get("htmlRoutePath") == "/video-to-analysis/operator-handoff"
        and contract.get("operatorHandoffRouteReady") is True
        and contract.get("allowsTraining") is False
        and contract.get("allowsPromotion") is False
        and contract.get("allowsRuntimeDefaultMutation") is False
    )


def _view_model(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_operator_handoff_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Video-to-analysis operator handoff",
        "primaryOperatorRoute": pack.get("primaryOperatorRoute"),
        "primaryApiRoute": pack.get("primaryApiRoute"),
        "activeRuntimeDefaultVersion": pack.get("activeRuntimeDefaultVersion"),
        "runtimeDefaultRolloutClosed": pack.get("runtimeDefaultRolloutClosed"),
        "operatorChecklist": pack.get("operatorChecklist", []),
        "guardrails": pack.get("guardrails", {}),
        "nextRecommendedNextLever": NEXT_LANE_CLOSEOUT,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    checklist = "\n".join(
        f"<li>{escape(str(row.get('label') or row.get('id')))}</li>"
        for row in view_model.get("operatorChecklist", [])
        if isinstance(row, dict)
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Video-to-analysis operator handoff</title></head>",
            "<body>",
            "<h1>Video-to-analysis operator handoff</h1>",
            f"<p>Primary route: <code>{escape(str(view_model.get('primaryOperatorRoute')))}</code></p>",
            f"<p>Active runtime default: <code>{escape(str(view_model.get('activeRuntimeDefaultVersion')))}</code></p>",
            "<h2>Checklist</h2>",
            f"<ol>{checklist}</ol>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/operator-handoff")
        html_response = await client.get("/video-to-analysis/operator-handoff")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/operator-handoff",
        "htmlRoutePath": "/video-to-analysis/operator-handoff",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "htmlContainsTitle": "Video-to-analysis operator handoff" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_operator_handoff_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    pack_root = root / DEFAULT_HANDOFF_PACK_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    pack_summary = load_json(pack_root / "operator_handoff_pack_summary.json")
    pack = load_json(pack_root / "operator_handoff_pack.json")
    route_contract = load_json(pack_root / "operator_handoff_route_contract.json")
    pack_ready = _pack_ready(pack_summary, pack, route_contract)

    if pack_ready and isinstance(pack, dict):
        view_model = _view_model(pack)
        bound_contract = {
            "schemaVersion": "video_to_analysis_operator_handoff_bound_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/operator-handoff",
            "htmlRoutePath": "/video-to-analysis/operator-handoff",
            "operatorHandoffRouteReady": True,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "activeRuntimeDefaultVersion": "v7.3",
        }
        write_json(output_root / "operator_handoff_view_model.json", view_model)
        write_json(output_root / "operator_handoff_bound_route_contract.json", bound_contract)
        (output_root / "operator_handoff_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
        smoke = _route_smoke(Path(storage_root))
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0}

    route_ready = bool(
        pack_ready
        and smoke.get("apiRouteStatusCode") == 200
        and smoke.get("htmlRouteStatusCode") == 200
        and smoke.get("apiSchemaVersion") == "video_to_analysis_operator_handoff_view_model_v1"
        and smoke.get("htmlContainsTitle") is True
    )

    if not pack_ready:
        primary_blocker = BLOCKER_PACK_MISSING
        next_lever = NEXT_PACK
        english = "Operator handoff pack is missing or unsafe; build pack before route binding."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_REPAIR
        english = "Operator handoff route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_LANE_CLOSEOUT
        english = "Operator handoff API and HTML routes are bound and smoked. Close the video-to-analysis product lane next."

    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = route_ready
    false_flags["runtimeDefaultMutationAllowed"] = route_ready
    summary = {
        "batchName": "video_to_analysis_operator_handoff_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "operatorHandoffRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/operator-handoff",
        "htmlRoutePath": "/video-to-analysis/operator-handoff",
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
        summary_filename="operator_handoff_route_binding_summary.json",
        summary=summary,
        artifacts={
            "operator_handoff_route_smoke_audit.json": smoke,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Operator Handoff Route Binding",
    )


def main() -> None:
    main_for("Bind video-to-analysis operator handoff route.", run_video_to_analysis_operator_handoff_route_binding)


if __name__ == "__main__":
    main()
