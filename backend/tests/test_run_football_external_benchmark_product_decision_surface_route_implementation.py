from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_football_external_benchmark_product_decision_surface_route_implementation as route_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_decision_surface(storage_root: Path, *, ready: bool = True) -> None:
    root = _candidate_root(storage_root) / "football_external_benchmark_product_decision_surface_v1"
    _write_json(
        root / "external_benchmark_product_decision_surface_summary.json",
        {
            "batchName": "football_external_benchmark_product_decision_surface",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_benchmark_product_decision_surface_contract_gap",
            "productDecisionSurfaceReady": ready,
            "productDecisionRouteImplementationReady": ready,
            "externalBenchmarkLaneClosed": ready,
            "externalSourceCount": 2 if ready else 0,
            "apiRoutePath": "/api/external/benchmark/decision",
            "htmlRoutePath": "/external/benchmark/decision",
            "recommendedNextDesignLever": "football_external_benchmark_real_evaluation_design",
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
        },
    )
    _write_json(
        root / "product_decision_surface_view_model.json",
        {
            "schemaVersion": "external_benchmark_product_decision_surface_view_model_v1",
            "hero": {"title": "External Benchmark Decision Surface"},
            "cards": [{"label": "Sources", "value": 2}],
            "limitationsBanner": "This is generated-truth smoke, not detector evaluation.",
            "recommendations": [{"decisionId": "design_real_detector_benchmark", "nextLever": "football_external_benchmark_real_evaluation_design"}],
            "readiness": {
                "productDecisionSurfaceReady": ready,
                "productDecisionRouteImplementationReady": ready,
                "detectorEvaluationReady": False,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
                "dataDownloadReady": False,
                "normalMatchStorageMutationReady": False,
            },
        },
    )
    _write_json(
        root / "product_decision_surface_route_contract.json",
        {
            "schemaVersion": "external_benchmark_product_decision_surface_route_contract_v1",
            "apiRoutePath": "/api/external/benchmark/decision",
            "htmlRoutePath": "/external/benchmark/decision",
            "productDecisionSurfaceReady": ready,
            "productDecisionRouteImplementationReady": ready,
            "allowsDetectorEvaluationReadiness": False,
            "allowsCandidateEvaluationReadiness": False,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "allowsDataDownload": False,
            "allowsVideoDownload": False,
            "allowsNormalMatchStorageMutation": False,
        },
    )
    (root / "product_decision_surface_render_smoke.html").write_text(
        "<!doctype html><html><body>External Benchmark Decision Surface not detector evaluation real detector benchmark</body></html>",
        encoding="utf-8",
    )


def test_decision_surface_route_implementation_smokes_live_routes_and_writes_artifacts(tmp_path: Path) -> None:
    _write_decision_surface(tmp_path)

    payload = route_batch.run_football_external_benchmark_product_decision_surface_route_implementation(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_product_decision_surface_route_implementation_v1"
    audit = json.loads((output_root / "product_decision_surface_route_smoke_audit.json").read_text(encoding="utf-8"))
    response_fixture = json.loads((output_root / "product_decision_surface_route_response_fixture.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productDecisionRouteReady"] is True
    assert payload["apiRoutePath"] == "/api/external/benchmark/decision"
    assert payload["htmlRoutePath"] == "/external/benchmark/decision"
    assert payload["externalSourceCount"] == 2
    assert payload["recommendedNextDesignLever"] == "football_external_benchmark_real_evaluation_design"
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["dataDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_real_evaluation_design"
    assert audit["apiRouteStatusCode"] == 200
    assert audit["htmlRouteStatusCode"] == 200
    assert audit["apiRouteSmokePassed"] is True
    assert audit["htmlRouteSmokePassed"] is True
    assert response_fixture["body"]["hero"]["title"] == "External Benchmark Decision Surface"


def test_decision_surface_route_implementation_blocks_without_surface(tmp_path: Path) -> None:
    payload = route_batch.run_football_external_benchmark_product_decision_surface_route_implementation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_product_decision_surface_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_decision_surface"


def test_decision_surface_route_implementation_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_decision_surface(tmp_path)

    payload = route_batch.run_football_external_benchmark_product_decision_surface_route_implementation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_product_decision_route_smoke",
        "external_benchmark_product_decision_route_contract_repair",
        "external_benchmark_product_decision_route_blocker_summary",
    ]


def test_decision_surface_route_implementation_rejects_parent_output_without_deleting_it(tmp_path: Path) -> None:
    _write_decision_surface(tmp_path)
    sentinel = tmp_path / "trained_detector_candidates" / "sentinel"
    sentinel.mkdir(parents=True)
    marker = sentinel / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        route_batch.run_football_external_benchmark_product_decision_surface_route_implementation(
            storage_root=tmp_path,
            output_dir_name="../sentinel",
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_decision_surface_route_implementation_rejects_unsafe_output_before_missing_inputs_can_delete_it(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "trained_detector_candidates" / "sentinel"
    sentinel.mkdir(parents=True)
    marker = sentinel / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        route_batch.run_football_external_benchmark_product_decision_surface_route_implementation(
            storage_root=tmp_path,
            output_dir_name="../sentinel",
        )

    assert marker.read_text(encoding="utf-8") == "keep"
