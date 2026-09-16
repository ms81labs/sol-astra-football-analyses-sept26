from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_operator_dashboard_polish as dashboard
import backend.scripts.run_video_to_analysis_storage_retention_and_artifact_hygiene as hygiene
from backend.tests.test_run_video_to_analysis_storage_retention_and_artifact_hygiene import _seed_operational_backlog
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root


def _seed_storage_hygiene(storage_root: Path) -> None:
    _seed_operational_backlog(storage_root)
    hygiene.run_video_to_analysis_storage_retention_and_artifact_hygiene(storage_root=storage_root)


def _promote_seeded_steady_state_to_v7_3(storage_root: Path) -> None:
    steady_state_path = (
        _candidate_root(storage_root)
        / "video_to_analysis_steady_state_monitoring_cycle_v1"
        / "steady_state_monitoring_cycle_summary.json"
    )
    steady_state = json.loads(steady_state_path.read_text(encoding="utf-8"))
    steady_state["releasedRuntimeVersion"] = "v7.3"
    steady_state_path.write_text(json.dumps(steady_state, indent=2) + "\n", encoding="utf-8")


def test_operator_dashboard_polish_binds_current_runtime_health_and_storage_truth(tmp_path: Path) -> None:
    _seed_storage_hygiene(tmp_path)
    _promote_seeded_steady_state_to_v7_3(tmp_path)

    payload = dashboard.run_video_to_analysis_operator_dashboard_polish(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_operator_dashboard_polish_v1"
    view_model = json.loads((output_root / "operator_dashboard_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "operator_dashboard_route_contract.json").read_text(encoding="utf-8"))

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/operator-dashboard")
            html_response = await client.get("/video-to-analysis/operator-dashboard")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operatorDashboardPolished"] is True
    assert payload["operatorDashboardRouteReady"] is True
    assert payload["apiRouteStatusCode"] == 200
    assert payload["htmlRouteStatusCode"] == 200
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_real_source_path_consolidation"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert view_model["schemaVersion"] == "video_to_analysis_operator_dashboard_view_model_v1"
    assert view_model["releasedRuntimeVersion"] == "v7.3"
    assert view_model["promotedRuntimeHealthy"] is True
    assert view_model["storageHygienePlanReady"] is True
    assert view_model["nextRecommendedNextLever"] == "football_external_benchmark_real_source_path_consolidation"
    assert route_contract["apiRoutePath"] == "/api/video-to-analysis/operator-dashboard"
    assert route_contract["htmlRoutePath"] == "/video-to-analysis/operator-dashboard"
    assert api_payload["schemaVersion"] == "video_to_analysis_operator_dashboard_view_model_v1"
    assert api_payload["releasedRuntimeVersion"] == "v7.3"
    assert "Video-to-analysis operator dashboard" in html
    assert "v7.3" in html


def test_operator_dashboard_polish_blocks_without_storage_hygiene_truth(tmp_path: Path) -> None:
    payload = dashboard.run_video_to_analysis_operator_dashboard_polish(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_operator_dashboard_storage_hygiene_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_retention_and_artifact_hygiene"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
