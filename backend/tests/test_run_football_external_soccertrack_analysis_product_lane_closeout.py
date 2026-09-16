from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_analysis_product_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_route_implementation(storage_root: Path, *, ready: bool = True) -> Path:
    route_root = _candidate_root(storage_root) / "football_external_soccertrack_analysis_product_ui_route_implementation_v1"
    _write_json(
        route_root / "analysis_product_ui_route_implementation_summary.json",
        {
            "batchName": "football_external_soccertrack_analysis_product_ui_route_implementation",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_soccertrack_analysis_product_ui_route_contract_gap",
            "productUiRouteReady": ready,
            "selectedMatchId": "117092" if ready else None,
            "apiRoutePath": "/api/external/soccertrack/117092/analysis",
            "htmlRoutePath": "/external/soccertrack/117092/analysis",
            "reportedEventCount": 3142 if ready else 0,
            "reportedFrameCount": 20 if ready else 0,
            "trainingExecuted": False,
            "candidateReadyForEvaluation": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
        },
    )
    _write_json(
        route_root / "analysis_product_ui_route_smoke_audit.json",
        {
            "schemaVersion": "soccertrack_analysis_product_ui_route_smoke_audit_v1",
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
                "schemaVersion": "soccertrack_analysis_product_ui_view_model_v1",
                "hero": {"title": "SoccerTrack 117092 external fixture"},
                "cards": [{"label": "Events", "value": 3142}],
                "readiness": {
                    "analysisProductUiReady": ready,
                    "candidateEvaluationReady": False,
                    "trainingReady": False,
                    "promotionReady": False,
                    "runtimeDefaultMutationReady": False,
                },
            },
        },
    )
    return route_root


def test_soccertrack_product_lane_closeout_writes_capability_matrix_and_next_safe_lever(tmp_path: Path) -> None:
    _write_route_implementation(tmp_path)

    payload = closeout.run_football_external_soccertrack_analysis_product_lane_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccertrack_analysis_product_lane_closeout_v1"
    capability = json.loads((output_root / "analysis_product_capability_matrix.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisProductLaneClosed"] is True
    assert payload["productUiRouteReady"] is True
    assert payload["selectedMatchId"] == "117092"
    assert payload["reportedEventCount"] == 3142
    assert payload["reportedFrameCount"] == 20
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_lane_closeout"
    assert capability["routeCapabilityReady"] is True
    assert capability["externalFixtureAnalysisProductReady"] is True
    assert capability["detectorEvaluationReady"] is False
    assert gaps["remainingPrimaryGap"] == "soccertrack_lane_closeout_ready"


def test_soccertrack_product_lane_closeout_blocks_without_route_implementation(tmp_path: Path) -> None:
    payload = closeout.run_football_external_soccertrack_analysis_product_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_analysis_product_ui_route_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_product_ui_route_implementation"


def test_soccertrack_product_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_route_implementation(tmp_path)

    payload = closeout.run_football_external_soccertrack_analysis_product_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_analysis_product_lane_closeout",
        "soccertrack_analysis_product_route_closeout_repair",
        "soccertrack_analysis_product_lane_blocker_summary",
    ]
