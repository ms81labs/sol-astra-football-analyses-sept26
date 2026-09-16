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
        / "football_external_soccernet_analysis_product_ui_binding_v1"
    )


def _write_binding_artifacts(storage_root: Path) -> Path:
    binding_root = _binding_root(storage_root)
    _write_json(
        binding_root / "analysis_product_ui_view_model.json",
        {
            "schemaVersion": "soccernet_full_analysis_ui_view_model_v1",
            "hero": {
                "title": "SoccerNet full 224p analysis",
                "subtitle": "Full extracted SoccerNet video summarized with lightweight frame-signal timelines.",
            },
            "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
            "cards": [
                {"label": "Frames analyzed", "value": 146893},
                {"label": "Timeline segments", "value": 196},
            ],
            "readiness": {
                "productFullAnalysisReady": True,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitations": ["not detector evaluation"],
        },
    )
    (binding_root / "analysis_product_ui_render_smoke.html").write_text(
        "<!doctype html><html><body><h1>SoccerNet full 224p analysis</h1><p>Frames analyzed</p><p>not detector evaluation</p></body></html>",
        encoding="utf-8",
    )
    return binding_root


async def _client(storage_root: Path):
    app = create_app(storage_root=storage_root)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1")


def test_external_soccernet_full_analysis_api_route_serves_saved_view_model(tmp_path: Path) -> None:
    _run(_test_external_soccernet_full_analysis_api_route_serves_saved_view_model, tmp_path)


async def _test_external_soccernet_full_analysis_api_route_serves_saved_view_model(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_binding_artifacts(storage_root)

    async with await _client(storage_root) as client:
        response = await client.get("/api/external/soccernet/full-analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "soccernet_full_analysis_ui_view_model_v1"
    assert payload["hero"]["title"] == "SoccerNet full 224p analysis"
    assert payload["cards"][0]["label"] == "Frames analyzed"
    assert payload["readiness"]["candidateEvaluationReady"] is False
    assert payload["readiness"]["trainingReady"] is False
    assert payload["readiness"]["promotionReady"] is False
    assert payload["readiness"]["runtimeDefaultMutationReady"] is False


def test_external_soccernet_full_analysis_page_serves_saved_html(tmp_path: Path) -> None:
    _run(_test_external_soccernet_full_analysis_page_serves_saved_html, tmp_path)


async def _test_external_soccernet_full_analysis_page_serves_saved_html(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    _write_binding_artifacts(storage_root)

    async with await _client(storage_root) as client:
        response = await client.get("/external/soccernet/full-analysis")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SoccerNet full 224p analysis" in response.text
    assert "Frames analyzed" in response.text
    assert "not detector evaluation" in response.text


def test_external_soccernet_full_analysis_routes_fail_closed_without_binding_artifacts(tmp_path: Path) -> None:
    _run(_test_external_soccernet_full_analysis_routes_fail_closed_without_binding_artifacts, tmp_path)


async def _test_external_soccernet_full_analysis_routes_fail_closed_without_binding_artifacts(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"

    async with await _client(storage_root) as client:
        api_response = await client.get("/api/external/soccernet/full-analysis")
        page_response = await client.get("/external/soccernet/full-analysis")

    assert api_response.status_code == 404
    assert api_response.json()["detail"] == "SoccerNet analysis product UI binding not ready"
    assert page_response.status_code == 404
    assert page_response.json()["detail"] == "SoccerNet analysis product UI binding not ready"
