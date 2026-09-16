from __future__ import annotations

import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_finish_line_closeout as closeout
import backend.scripts.run_video_to_analysis_finish_line_product_binding as binding
import backend.scripts.run_video_to_analysis_finish_line_route_implementation as route_impl
import backend.scripts.run_video_to_analysis_finish_line_product_execution_plan as execution_plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_product_smoke(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "product_video_to_analysis_smoke_isolated_v1"
    _write_json(
        root / "product_video_to_analysis_smoke_summary.json",
        {
            "batchName": "product_video_to_analysis_smoke",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "productVideoToAnalysisSmokePassed": True,
            "apiUploadJobSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "normalMatchStorageMutationApproved": False,
            "normalMatchStorageMutationExecuted": False,
            "isolatedBenchmarkStorageMutationApproved": True,
            "isolatedBenchmarkStorageMutationExecuted": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_closeout",
        },
    )
    _write_json(
        root / "isolated_storage_audit.json",
        {
            "isolatedStorageRoot": str(root / "isolated_storage_root"),
            "normalStorageRootUsedForSmoke": False,
            "isolatedBenchmarkStorageMutationExecuted": True,
            "nestedSmokeSummaryExists": True,
        },
    )


def test_finish_line_closeout_binding_and_route_chain(tmp_path: Path) -> None:
    _seed_product_smoke(tmp_path)

    closeout_payload = closeout.run_video_to_analysis_finish_line_closeout(storage_root=tmp_path)
    binding_payload = binding.run_video_to_analysis_finish_line_product_binding(storage_root=tmp_path)
    route_payload = route_impl.run_video_to_analysis_finish_line_route_implementation(storage_root=tmp_path)
    plan_payload = execution_plan.run_video_to_analysis_finish_line_product_execution_plan(storage_root=tmp_path)

    assert closeout_payload["finishLineClosed"] is True
    assert closeout_payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_binding"
    assert binding_payload["finishLineProductBindingReady"] is True
    assert binding_payload["apiRoutePath"] == "/api/video-to-analysis/finish-line"
    assert binding_payload["htmlRoutePath"] == "/video-to-analysis/finish-line"
    assert route_payload["finishLineRouteReady"] is True
    assert route_payload["apiRouteStatusCode"] == 200
    assert route_payload["htmlRouteStatusCode"] == 200
    assert route_payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_execution_plan"
    assert plan_payload["finishLineProductExecutionPlanReady"] is True
    assert plan_payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_execution_approval"


def test_finish_line_route_serves_binding(tmp_path: Path) -> None:
    _seed_product_smoke(tmp_path)
    closeout.run_video_to_analysis_finish_line_closeout(storage_root=tmp_path)
    binding.run_video_to_analysis_finish_line_product_binding(storage_root=tmp_path)

    app = create_app(storage_root=tmp_path)

    async def _check() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/finish-line")
            html_response = await client.get("/video-to-analysis/finish-line")
        assert api_response.status_code == 200
        assert api_response.json()["schemaVersion"] == "video_to_analysis_finish_line_product_view_model_v1"
        assert html_response.status_code == 200
        assert "Video To Analysis Finish Line" in html_response.text

    import asyncio

    asyncio.run(_check())


def test_finish_line_closeout_blocks_without_smoke(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_finish_line_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_product_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_smoke"
