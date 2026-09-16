from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_post_release_monitoring_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_monitoring_route(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_post_release_monitoring_route_binding_v1"
    _write_json(
        root / "post_release_monitoring_route_binding_summary.json",
        {
            "batchName": "video_to_analysis_post_release_monitoring_route_binding",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "postReleaseMonitoringRouteReady": True,
            "apiRoutePath": "/api/video-to-analysis/post-release-monitoring",
            "htmlRoutePath": "/video-to-analysis/post-release-monitoring",
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
            "nextRecommendedNextLever": "video_to_analysis_post_release_monitoring_closeout",
        },
    )


def test_post_release_monitoring_closeout_selects_detector_reentry_plan(tmp_path: Path) -> None:
    _seed_monitoring_route(tmp_path)

    payload = closeout.run_video_to_analysis_post_release_monitoring_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_post_release_monitoring_closeout_v1"
    matrix = json.loads((output_root / "post_release_monitoring_capability_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["postReleaseMonitoringClosed"] is True
    assert payload["postReleaseMonitoringRouteReady"] is True
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_reentry_plan"
    assert matrix["closedCapabilities"]["postReleaseMonitoringRouteReady"] is True
    assert matrix["closedCapabilities"]["v7_3RuntimeDefaultActive"] is True
    assert matrix["guardrails"]["detectorEvaluationReady"] is False


def test_post_release_monitoring_closeout_blocks_without_route(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_post_release_monitoring_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_post_release_monitoring_route_binding_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_post_release_monitoring_route_binding"
