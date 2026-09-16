from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_finish_line_route_polish as polish


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_route_polish_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    backlog_root = root / "video_to_analysis_product_hardening_backlog_v1"
    _write_json(
        backlog_root / "product_hardening_backlog_summary.json",
        {
            "batchName": "video_to_analysis_product_hardening_backlog",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "productHardeningBacklogReady": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_route_polish",
        },
    )
    _write_json(
        backlog_root / "product_hardening_backlog.json",
        {
            "priorityOrder": ["finish_line_route_polish"],
            "backlogItems": [{"id": "finish_line_route_polish", "nextLever": "video_to_analysis_finish_line_route_polish"}],
        },
    )
    binding_root = root / "video_to_analysis_finish_line_product_binding_v1"
    _write_json(
        binding_root / "finish_line_product_view_model.json",
        {
            "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
            "title": "Video To Analysis Finish Line",
            "subtitle": "Old copy",
            "scoreboard": [{"label": "Product smoke", "value": "passed"}],
        },
    )
    _write_json(
        binding_root / "finish_line_product_route_contract.json",
        {
            "apiRoutePath": "/api/video-to-analysis/finish-line",
            "htmlRoutePath": "/video-to-analysis/finish-line",
            "routeImplementationReady": True,
        },
    )
    (binding_root / "finish_line_product_render_smoke.html").write_text(
        "<html><body><h1>Video To Analysis Finish Line</h1></body></html>",
        encoding="utf-8",
    )


def test_route_polish_updates_binding_and_live_route(tmp_path: Path) -> None:
    _seed_route_polish_inputs(tmp_path)

    payload = polish.run_video_to_analysis_finish_line_route_polish(storage_root=tmp_path)

    binding_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_product_binding_v1"
    view_model = json.loads((binding_root / "finish_line_product_view_model.json").read_text(encoding="utf-8"))

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/finish-line")
            html_response = await client.get("/video-to-analysis/finish-line")
        return api_response.json(), html_response.text

    route_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["finishLineRoutePolished"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_suite_prep"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert view_model["status"] == "ready_for_product_hardening_acceptance"
    assert "operatorActions" in view_model
    assert route_payload["status"] == "ready_for_product_hardening_acceptance"
    assert "Open this page after a video upload/export smoke" in html


def test_route_polish_blocks_without_backlog(tmp_path: Path) -> None:
    payload = polish.run_video_to_analysis_finish_line_route_polish(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_product_hardening_backlog_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_product_hardening_backlog"
