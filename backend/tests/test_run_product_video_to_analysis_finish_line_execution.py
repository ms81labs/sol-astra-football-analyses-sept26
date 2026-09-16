from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_product_video_to_analysis_finish_line_execution as execution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_product_execution_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    approval_root = root / "video_to_analysis_finish_line_product_execution_approval_v1"
    _write_json(
        approval_root / "finish_line_product_execution_approval_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_product_execution_approval",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineProductExecutionApproved": True,
            "finishLineProductExecutionReady": True,
            "approvedExecutionMode": "bounded_product_route_and_bundle_smoke",
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
            "nextRecommendedNextLever": "product_video_to_analysis_finish_line_execution",
        },
    )
    _write_json(
        approval_root / "approved_finish_line_product_execution_scope.json",
        {
            "finishLineProductExecutionApproved": True,
            "approvedExecutionMode": "bounded_product_route_and_bundle_smoke",
            "allowedApiRoutePath": "/api/video-to-analysis/finish-line",
            "allowedHtmlRoutePath": "/video-to-analysis/finish-line",
            "normalMatchStorageMutationAllowed": False,
            "isolatedBenchmarkStorageMutationAllowed": True,
            "dataDownloadAllowed": False,
            "videoDownloadAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    binding_root = root / "video_to_analysis_finish_line_product_binding_v1"
    _write_json(
        binding_root / "finish_line_product_view_model.json",
        {
            "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
            "headline": "Video To Analysis Finish Line",
            "status": "ready",
            "finishLineClosed": True,
            "routePaths": {
                "api": "/api/video-to-analysis/finish-line",
                "html": "/video-to-analysis/finish-line",
            },
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
    (binding_root / "finish_line_product_render_smoke.html").parent.mkdir(parents=True, exist_ok=True)
    (binding_root / "finish_line_product_render_smoke.html").write_text(
        "<html><body><h1>Video To Analysis Finish Line</h1></body></html>",
        encoding="utf-8",
    )
    isolated_root = root / "product_video_to_analysis_smoke_isolated_v1"
    _write_json(
        isolated_root / "product_video_to_analysis_smoke_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "productVideoToAnalysisSmokePassed": True,
            "apiUploadJobSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "normalMatchStorageMutationExecuted": False,
            "isolatedBenchmarkStorageMutationExecuted": True,
        },
    )
    _write_json(
        isolated_root / "isolated_storage_audit.json",
        {
            "normalStorageRootUsedForSmoke": False,
            "isolatedBenchmarkStorageMutationExecuted": True,
            "nestedSmokeSummaryExists": True,
        },
    )


def test_product_finish_line_execution_smokes_route_and_bundle(tmp_path: Path) -> None:
    _seed_product_execution_inputs(tmp_path)

    payload = execution.run_product_video_to_analysis_finish_line_execution(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "product_video_to_analysis_finish_line_execution_v1"
    route_audit = json.loads((output_root / "finish_line_product_route_execution_audit.json").read_text(encoding="utf-8"))
    bundle_audit = json.loads((output_root / "finish_line_bundle_consistency_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["finishLineProductExecutionPassed"] is True
    assert payload["boundedRouteSmokePassed"] is True
    assert payload["bundleConsistencyPassed"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_acceptance_closeout"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert route_audit["apiRouteStatusCode"] == 200
    assert route_audit["htmlRouteStatusCode"] == 200
    assert bundle_audit["productVideoToAnalysisSmokePassed"] is True


def test_product_finish_line_execution_blocks_without_approval(tmp_path: Path) -> None:
    payload = execution.run_product_video_to_analysis_finish_line_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_product_execution_approval_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_execution_approval"
