from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_product_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_handoff_route(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_operator_handoff_route_binding_v1"
    _write_json(
        root / "operator_handoff_route_binding_summary.json",
        {
            "batchName": "video_to_analysis_operator_handoff_route_binding",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "operatorHandoffRouteReady": True,
            "apiRoutePath": "/api/video-to-analysis/operator-handoff",
            "htmlRoutePath": "/video-to-analysis/operator-handoff",
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultRolloutClosed": True,
            "activeRuntimeDefaultVersion": "v7.3",
            "nextRecommendedNextLever": "video_to_analysis_product_lane_closeout",
        },
    )


def test_product_lane_closeout_marks_lane_complete(tmp_path: Path) -> None:
    _seed_handoff_route(tmp_path)

    payload = closeout.run_video_to_analysis_product_lane_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_product_lane_closeout_v1"
    capability_matrix = json.loads((output_root / "product_lane_capability_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoToAnalysisProductLaneClosed"] is True
    assert payload["videoToAnalysisProductPathReady"] is True
    assert payload["operatorHandoffRouteReady"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_post_release_monitoring_plan"
    assert capability_matrix["closedCapabilities"]["operatorHandoffRouteReady"] is True
    assert capability_matrix["closedCapabilities"]["releaseCandidateClosed"] is True
    assert capability_matrix["closedCapabilities"]["v7_3RuntimeDefaultActive"] is True


def test_product_lane_closeout_blocks_without_handoff_route(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_product_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_operator_handoff_route_binding_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_handoff_route_binding"
