from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_product_ui_route_implementation as route_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_ui_binding(storage_root: Path, *, ready: bool = True) -> Path:
    binding_root = _candidate_root(storage_root) / "football_external_benchmark_product_ui_binding_v1"
    _write_json(
        binding_root / "external_benchmark_product_ui_binding_summary.json",
        {
            "batchName": "football_external_benchmark_product_ui_binding",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "football_external_benchmark_product_ui_contract_gap",
            "roadmapAdvanceAllowed": ready,
            "productUiBindingReady": ready,
            "productRouteImplementationReady": ready,
            "sourceCount": 2 if ready else 0,
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "candidateReadyForEvaluation": False,
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )
    _write_json(
        binding_root / "external_benchmark_product_ui_route_contract.json",
        {
            "schemaVersion": "football_external_benchmark_product_ui_route_contract_v1",
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "productUiBindingReady": ready,
            "allowsDetectorEvaluation": False,
            "allowsCandidateEvaluationReadiness": False,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "allowsVideoDownload": False,
            "allowsNormalMatchStorageMutation": False,
        },
    )
    _write_json(
        binding_root / "external_benchmark_product_ui_view_model.json",
        {
            "schemaVersion": "football_external_benchmark_product_ui_view_model_v1",
            "hero": {"title": "External Benchmark"},
            "cards": [{"label": "Sources", "value": 2}],
            "sources": [{"sourceId": "soccernet"}, {"sourceId": "soccertrack"}],
            "readiness": {
                "productUiBindingReady": ready,
                "productRouteImplementationReady": ready,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
        },
    )
    (binding_root / "external_benchmark_product_ui_render_smoke.html").write_text(
        "<!doctype html><html><body>External Benchmark soccernet soccertrack not detector evaluation</body></html>",
        encoding="utf-8",
    )
    return binding_root


def test_benchmark_ui_route_implementation_smokes_live_routes_and_writes_artifacts(tmp_path: Path) -> None:
    _write_ui_binding(tmp_path)

    payload = route_batch.run_football_external_benchmark_product_ui_route_implementation(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_product_ui_route_implementation_v1"
    audit = json.loads((output_root / "external_benchmark_product_ui_route_smoke_audit.json").read_text(encoding="utf-8"))
    response_fixture = json.loads((output_root / "external_benchmark_product_ui_route_response_fixture.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productUiRouteReady"] is True
    assert payload["apiRoutePath"] == "/api/external/benchmark/report"
    assert payload["htmlRoutePath"] == "/external/benchmark/report"
    assert payload["sourceCount"] == 2
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_lane_closeout"
    assert audit["apiRouteStatusCode"] == 200
    assert audit["htmlRouteStatusCode"] == 200
    assert audit["apiRouteSmokePassed"] is True
    assert audit["htmlRouteSmokePassed"] is True
    assert response_fixture["body"]["hero"]["title"] == "External Benchmark"


def test_benchmark_ui_route_implementation_blocks_without_ui_binding(tmp_path: Path) -> None:
    payload = route_batch.run_football_external_benchmark_product_ui_route_implementation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_product_ui_binding_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_ui_binding"


def test_benchmark_ui_route_implementation_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_ui_binding(tmp_path)

    payload = route_batch.run_football_external_benchmark_product_ui_route_implementation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_product_ui_route_smoke",
        "external_benchmark_product_ui_route_contract_repair",
        "external_benchmark_product_ui_route_blocker_summary",
    ]
