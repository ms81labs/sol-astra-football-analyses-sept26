from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_analysis_product_ui_route_implementation as route_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_ui_binding(storage_root: Path, *, ready: bool = True) -> Path:
    binding_root = _candidate_root(storage_root) / "football_external_soccernet_analysis_product_ui_binding_v1"
    _write_json(
        binding_root / "analysis_product_ui_binding_summary.json",
        {
            "batchName": "football_external_soccernet_analysis_product_ui_binding",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "football_external_soccernet_analysis_product_ui_contract_gap",
            "roadmapAdvanceAllowed": ready,
            "productUiBindingReady": ready,
            "reportedFrameCount": 146893 if ready else 0,
            "segmentCount": 196 if ready else 0,
            "candidateReadyForEvaluation": False,
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        binding_root / "analysis_product_ui_route_contract.json",
        {
            "schemaVersion": "soccernet_full_analysis_ui_route_contract_v1",
            "routePath": "/external/soccernet/full-analysis",
            "productUiBindingReady": ready,
            "allowsCandidateEvaluationReadiness": False,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
        },
    )
    _write_json(
        binding_root / "analysis_product_ui_view_model.json",
        {
            "schemaVersion": "soccernet_full_analysis_ui_view_model_v1",
            "hero": {"title": "SoccerNet full 224p analysis"},
            "cards": [{"label": "Frames analyzed", "value": 146893}],
            "readiness": {
                "productFullAnalysisReady": ready,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    (binding_root / "analysis_product_ui_render_smoke.html").write_text(
        "<!doctype html><html><body>SoccerNet full 224p analysis Frames analyzed not detector evaluation</body></html>",
        encoding="utf-8",
    )
    return binding_root


def test_route_implementation_smokes_live_routes_and_writes_artifacts(tmp_path: Path) -> None:
    _write_ui_binding(tmp_path)

    payload = route_batch.run_football_external_soccernet_analysis_product_ui_route_implementation(
        storage_root=tmp_path
    )

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_analysis_product_ui_route_implementation_v1"
    audit = json.loads((output_root / "analysis_product_ui_route_smoke_audit.json").read_text(encoding="utf-8"))
    response_fixture = json.loads((output_root / "analysis_product_ui_route_response_fixture.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productUiRouteReady"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["segmentCount"] == 196
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_lane_closeout"
    assert audit["apiRouteStatusCode"] == 200
    assert audit["htmlRouteStatusCode"] == 200
    assert audit["apiRouteSmokePassed"] is True
    assert audit["htmlRouteSmokePassed"] is True
    assert response_fixture["body"]["hero"]["title"] == "SoccerNet full 224p analysis"


def test_route_implementation_blocks_without_ui_binding(tmp_path: Path) -> None:
    payload = route_batch.run_football_external_soccernet_analysis_product_ui_route_implementation(
        storage_root=tmp_path
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_analysis_product_ui_binding_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_ui_binding"


def test_route_implementation_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_ui_binding(tmp_path)

    payload = route_batch.run_football_external_soccernet_analysis_product_ui_route_implementation(
        storage_root=tmp_path
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_analysis_product_ui_route_smoke",
        "soccernet_analysis_product_ui_route_contract_repair",
        "soccernet_analysis_product_ui_route_blocker_summary",
    ]
