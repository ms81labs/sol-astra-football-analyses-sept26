from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from backend.app.main import create_app
from backend.scripts.football_external_real_eval_chain_common import load_json, utc_now_iso

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


def registry_audit(storage_root: Path) -> dict[str, Any]:
    registry_path = storage_root / "runtime" / "promoted_touchline_detector_candidate.json"
    registry = load_json(registry_path)
    active_version = registry.get("trainingCandidateVersion") if isinstance(registry, dict) else None
    checks = {
        "registryPresent": isinstance(registry, dict),
        "candidateNameMatches": isinstance(registry, dict)
        and registry.get("trainingCandidateName") == "touchline_detector_candidate_v7",
        "candidateVersionMatches": active_version in {"v7.2", "v7.3"},
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
        "activeRuntimeDefaultVersion": active_version,
        "checks": checks,
        "registryMatchesPromotedV7_2DefaultRuntime": all(checks.values()),
        "registryMatchesActiveDefaultRuntime": all(checks.values()),
    }


async def route_smoke_async(storage_root: Path) -> dict[str, Any]:
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


def route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(route_smoke_async(storage_root))
