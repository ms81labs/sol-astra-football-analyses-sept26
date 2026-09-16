from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_operator_handoff_route_binding as route_binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_handoff_pack(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_operator_handoff_pack_v1"
    _write_json(
        root / "operator_handoff_pack_summary.json",
        {
            "batchName": "video_to_analysis_operator_handoff_pack",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "operatorHandoffPackReady": True,
            "videoToAnalysisProductPathReady": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultRolloutClosed": True,
            "activeRuntimeDefaultVersion": "v7.3",
            "nextRecommendedNextLever": "video_to_analysis_operator_handoff_route_binding",
        },
    )
    _write_json(
        root / "operator_handoff_pack.json",
        {
            "schemaVersion": "video_to_analysis_operator_handoff_pack_v1",
            "primaryOperatorRoute": "/video-to-analysis/acceptance-report",
            "primaryApiRoute": "/api/video-to-analysis/acceptance-report",
            "activeRuntimeDefaultVersion": "v7.3",
            "runtimeDefaultRolloutClosed": True,
            "operatorChecklist": [{"id": "open_acceptance_report", "label": "Open the acceptance report"}],
            "guardrails": {
                "trainingAllowed": False,
                "promotionAllowed": False,
                "runtimeDefaultMutationAlreadyExecuted": True,
                "runtimeDefaultMutationAllowedFromHandoff": False,
            },
        },
    )
    _write_json(
        root / "operator_handoff_route_contract.json",
        {
            "apiRoutePath": "/api/video-to-analysis/operator-handoff",
            "htmlRoutePath": "/video-to-analysis/operator-handoff",
            "operatorHandoffRouteReady": True,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
        },
    )
    (root / "operator_quickstart.md").write_text("# Video-to-analysis operator handoff\n", encoding="utf-8")


def test_operator_handoff_route_binding_serves_api_and_html(tmp_path: Path) -> None:
    _seed_handoff_pack(tmp_path)

    payload = route_binding.run_video_to_analysis_operator_handoff_route_binding(storage_root=tmp_path)

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/operator-handoff")
            html_response = await client.get("/video-to-analysis/operator-handoff")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operatorHandoffRouteReady"] is True
    assert payload["apiRouteStatusCode"] == 200
    assert payload["htmlRouteStatusCode"] == 200
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_product_lane_closeout"
    assert api_payload["schemaVersion"] == "video_to_analysis_operator_handoff_view_model_v1"
    assert api_payload["primaryOperatorRoute"] == "/video-to-analysis/acceptance-report"
    assert api_payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert "Video-to-analysis operator handoff" in html


def test_operator_handoff_route_binding_blocks_without_pack(tmp_path: Path) -> None:
    payload = route_binding.run_video_to_analysis_operator_handoff_route_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_operator_handoff_pack_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_handoff_pack"
