from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx

from backend.app.main import create_app


def _run(coro, *args):
    return anyio.run(coro, *args)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _binding_root(storage_root: Path) -> Path:
    return (
        storage_root
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "football_external_soccertrack_analysis_product_ui_binding_v1"
    )


def _write_ui_binding(storage_root: Path, *, match_id: str = "117092") -> Path:
    binding_root = _binding_root(storage_root)
    _write_json(
        binding_root / "analysis_product_ui_view_model.json",
        {
            "schemaVersion": "soccertrack_analysis_product_ui_view_model_v1",
            "hero": {"title": f"SoccerTrack {match_id} external fixture"},
            "cards": [{"label": "Events", "value": 3142}],
            "readiness": {
                "analysisProductUiReady": True,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
        },
    )
    _write_json(
        binding_root / "analysis_product_ui_route_contract.json",
        {
            "schemaVersion": "soccertrack_analysis_product_ui_route_contract_v1",
            "routePath": f"/external/soccertrack/{match_id}/analysis",
            "apiRoutePath": f"/api/external/soccertrack/{match_id}/analysis",
            "productUiBindingReady": True,
        },
    )
    (binding_root / "analysis_product_ui_render_smoke.html").write_text(
        f"<!doctype html><html><body>SoccerTrack {match_id} external fixture Events not detector evaluation</body></html>",
        encoding="utf-8",
    )
    return binding_root


async def _client(storage_root: Path):
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1")


def test_external_soccertrack_analysis_api_route_serves_saved_view_model(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_analysis_api_route_serves_saved_view_model, tmp_path)


async def _test_external_soccertrack_analysis_api_route_serves_saved_view_model(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_ui_binding(storage_root)

    async with await _client(storage_root) as client:
        response = await client.get("/api/external/soccertrack/117092/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "soccertrack_analysis_product_ui_view_model_v1"
    assert payload["hero"]["title"] == "SoccerTrack 117092 external fixture"
    assert payload["cards"][0]["label"] == "Events"
    assert payload["readiness"]["candidateEvaluationReady"] is False
    assert payload["readiness"]["trainingReady"] is False
    assert payload["readiness"]["promotionReady"] is False
    assert payload["readiness"]["runtimeDefaultMutationReady"] is False


def test_external_soccertrack_analysis_page_serves_saved_html(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_analysis_page_serves_saved_html, tmp_path)


async def _test_external_soccertrack_analysis_page_serves_saved_html(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_ui_binding(storage_root)

    async with await _client(storage_root) as client:
        response = await client.get("/external/soccertrack/117092/analysis")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SoccerTrack 117092 external fixture" in response.text
    assert "Events" in response.text
    assert "not detector evaluation" in response.text


def test_external_soccertrack_analysis_routes_fail_closed_without_binding(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_analysis_routes_fail_closed_without_binding, tmp_path)


async def _test_external_soccertrack_analysis_routes_fail_closed_without_binding(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"

    async with await _client(storage_root) as client:
        api_response = await client.get("/api/external/soccertrack/117092/analysis")
        page_response = await client.get("/external/soccertrack/117092/analysis")

    assert api_response.status_code == 404
    assert api_response.json()["detail"] == "SoccerTrack analysis product UI binding not ready"
    assert page_response.status_code == 404
    assert page_response.json()["detail"] == "SoccerTrack analysis product UI binding not ready"


def test_external_soccertrack_analysis_routes_reject_mismatched_match_id(tmp_path: Path) -> None:
    _run(_test_external_soccertrack_analysis_routes_reject_mismatched_match_id, tmp_path)


async def _test_external_soccertrack_analysis_routes_reject_mismatched_match_id(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_ui_binding(storage_root, match_id="117092")

    async with await _client(storage_root) as client:
        api_response = await client.get("/api/external/soccertrack/999999/analysis")
        page_response = await client.get("/external/soccertrack/999999/analysis")

    assert api_response.status_code == 404
    assert api_response.json()["detail"] == "SoccerTrack analysis product UI binding not found"
    assert page_response.status_code == 404
    assert page_response.json()["detail"] == "SoccerTrack analysis product UI binding not found"
