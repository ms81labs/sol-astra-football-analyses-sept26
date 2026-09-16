from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_post_release_monitoring_plan as monitoring


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_product_lane_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_product_lane_closeout_v1"
    _write_json(
        root / "product_lane_closeout_summary.json",
        {
            "batchName": "video_to_analysis_product_lane_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "videoToAnalysisProductLaneClosed": True,
            "videoToAnalysisProductPathReady": True,
            "operatorHandoffRouteReady": True,
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
            "nextRecommendedNextLever": "video_to_analysis_post_release_monitoring_plan",
        },
    )
    _write_json(
        root / "product_lane_capability_matrix.json",
        {
            "schemaVersion": "video_to_analysis_product_lane_capability_matrix_v1",
            "closedCapabilities": {
                "operatorHandoffRouteReady": True,
                "releaseCandidateClosed": True,
                "acceptanceReportRouteReady": True,
                "broaderRealVideoAcceptancePassed": True,
                "normalStorageProductSmokeCovered": True,
                "v7_3RuntimeDefaultActive": True,
            },
            "guardrails": {
                "detectorEvaluationReady": False,
                "candidateEvaluationReady": False,
                "downloadsReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": True,
            },
        },
    )


def test_post_release_monitoring_plan_writes_health_checks_and_next_route_binding(tmp_path: Path) -> None:
    _seed_product_lane_closeout(tmp_path)

    payload = monitoring.run_video_to_analysis_post_release_monitoring_plan(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_post_release_monitoring_plan_v1"
    plan = json.loads((output_root / "post_release_monitoring_plan.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "post_release_monitoring_route_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["postReleaseMonitoringPlanReady"] is True
    assert payload["monitoringCheckCount"] >= 4
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_post_release_monitoring_route_binding"
    assert plan["monitoringChecks"][0]["id"] == "operator_handoff_route_smoke"
    assert plan["activeRuntimeDefaultVersion"] == "v7.3"
    assert contract["apiRoutePath"] == "/api/video-to-analysis/post-release-monitoring"
    assert contract["htmlRoutePath"] == "/video-to-analysis/post-release-monitoring"


def test_post_release_monitoring_plan_blocks_without_product_lane_closeout(tmp_path: Path) -> None:
    payload = monitoring.run_video_to_analysis_post_release_monitoring_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_product_lane_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_product_lane_closeout"
