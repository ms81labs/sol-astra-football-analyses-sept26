from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_acceptance_report_route_binding as route_binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_broader_real_video_acceptance_closeout_v1"
    _write_json(
        root / "broader_real_video_acceptance_closeout_summary.json",
        {
            "batchName": "video_to_analysis_broader_real_video_acceptance_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "broaderRealVideoAcceptanceClosed": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "normalStorageMutationObservedFromExecution": True,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_acceptance_report_route_binding",
        },
    )
    _write_json(
        root / "broader_real_video_acceptance_report.json",
        {
            "schemaVersion": "video_to_analysis_broader_real_video_acceptance_report_v1",
            "acceptanceResult": "passed",
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "normalStorageMutationObservedFromExecution": True,
            "closedByBatch": "video_to_analysis_broader_real_video_acceptance_closeout",
            "nextRecommendedNextLever": "video_to_analysis_acceptance_report_route_binding",
        },
    )


def test_acceptance_report_route_binding_serves_api_and_html(tmp_path: Path) -> None:
    _seed_closeout(tmp_path)

    payload = route_binding.run_video_to_analysis_acceptance_report_route_binding(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_acceptance_report_route_binding_v1"
    view_model = json.loads((output_root / "acceptance_report_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "acceptance_report_route_contract.json").read_text(encoding="utf-8"))

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/acceptance-report")
            html_response = await client.get("/video-to-analysis/acceptance-report")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["acceptanceReportRouteReady"] is True
    assert payload["apiRouteStatusCode"] == 200
    assert payload["htmlRouteStatusCode"] == 200
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_acceptance_report_product_backlog"
    assert view_model["schemaVersion"] == "video_to_analysis_acceptance_report_view_model_v1"
    assert view_model["acceptanceResult"] == "passed"
    assert view_model["scoreboard"][0]["value"] == "5 / 5"
    assert route_contract["apiRoutePath"] == "/api/video-to-analysis/acceptance-report"
    assert route_contract["htmlRoutePath"] == "/video-to-analysis/acceptance-report"
    assert api_payload["schemaVersion"] == "video_to_analysis_acceptance_report_view_model_v1"
    assert api_payload["acceptanceResult"] == "passed"
    assert "Broader Real-Video Acceptance" in html
    assert "5 / 5" in html


def test_acceptance_report_route_binding_blocks_without_closeout(tmp_path: Path) -> None:
    payload = route_binding.run_video_to_analysis_acceptance_report_route_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_broader_real_video_acceptance_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_closeout"
