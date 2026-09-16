from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_analysis_product_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_route_implementation(storage_root: Path, *, ready: bool = True) -> Path:
    route_root = _candidate_root(storage_root) / "football_external_soccernet_analysis_product_ui_route_implementation_v1"
    _write_json(
        route_root / "analysis_product_ui_route_implementation_summary.json",
        {
            "batchName": "football_external_soccernet_analysis_product_ui_route_implementation",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_soccernet_analysis_product_ui_route_contract_gap",
            "productUiRouteReady": ready,
            "apiRoutePath": "/api/external/soccernet/full-analysis",
            "htmlRoutePath": "/external/soccernet/full-analysis",
            "reportedFrameCount": 146893 if ready else 0,
            "segmentCount": 196 if ready else 0,
            "trainingExecuted": False,
            "candidateReadyForEvaluation": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        route_root / "analysis_product_ui_route_smoke_audit.json",
        {
            "schemaVersion": "soccernet_full_analysis_ui_route_smoke_audit_v1",
            "sourceUiBindingReady": ready,
            "apiRouteStatusCode": 200 if ready else 404,
            "htmlRouteStatusCode": 200 if ready else 404,
            "apiRouteSmokePassed": ready,
            "htmlRouteSmokePassed": ready,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
    )
    _write_json(
        route_root / "analysis_product_ui_route_response_fixture.json",
        {
            "statusCode": 200 if ready else 404,
            "body": {
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
        },
    )
    return route_root


def test_product_lane_closeout_writes_capability_matrix_and_next_safe_lever(tmp_path: Path) -> None:
    _write_route_implementation(tmp_path)

    payload = closeout.run_football_external_soccernet_analysis_product_lane_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_analysis_product_lane_closeout_v1"
    capability = json.loads((output_root / "analysis_product_capability_matrix.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisProductLaneClosed"] is True
    assert payload["productUiRouteReady"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["segmentCount"] == 196
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_adapter_smoke_test"
    assert capability["routeCapabilityReady"] is True
    assert capability["fullVideoAnalysisProductReady"] is True
    assert capability["detectorEvaluationReady"] is False
    assert gaps["remainingPrimaryGap"] == "external_safe_source_adapter_smoke_not_currently_closed"


def test_product_lane_closeout_blocks_without_route_implementation(tmp_path: Path) -> None:
    payload = closeout.run_football_external_soccernet_analysis_product_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_analysis_product_ui_route_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_ui_route_implementation"


def test_product_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_route_implementation(tmp_path)

    payload = closeout.run_football_external_soccernet_analysis_product_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_analysis_product_lane_closeout",
        "soccernet_analysis_product_route_closeout_repair",
        "soccernet_analysis_product_lane_blocker_summary",
    ]
