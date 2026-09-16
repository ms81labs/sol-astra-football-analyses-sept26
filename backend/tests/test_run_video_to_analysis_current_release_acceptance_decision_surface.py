from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_current_release_acceptance_decision_surface as surface


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _false_guardrails() -> dict[str, bool]:
    return {
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "promotionReady": False,
        "runtimeDefaultMutationAllowed": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
    }


def _seed_current_release_truth(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    guardrails = _false_guardrails()
    _write_json(
        root
        / "video_to_analysis_growth_lane_closeout_readout_v57"
        / "growth_lane_closeout_readout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "growthLaneCloseoutReady": True,
            "growthLaneClosedAtSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v57",
            "growthLaneClosedAtVersion": 57,
            "autoContinueBoundedGrowthRecommended": False,
            "manualStrategicChoiceRequired": True,
            "nextRecommendedNextLever": "manual_strategic_lane_selection_required",
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_next_strategic_lane_selection_v1"
        / "next_strategic_lane_selection_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "selectedStrategicLane": "manual_strategic_lane_selection_required",
            "growthLaneCloseoutManualStrategicChoiceRequired": True,
            "growthLaneClosedAtSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v57",
            "growthLaneClosedAtVersion": 57,
            "nextRecommendedNextLever": "manual_strategic_lane_selection_required",
            **guardrails,
        },
    )
    _write_json(
        root / "video_to_analysis_release_completion_summary_v1" / "release_completion_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "releasedRuntimeVersion": "v7.2",
            "nextRecommendedNextLever": "video_to_analysis_promoted_runtime_post_release_monitoring_plan",
            **guardrails,
        },
    )
    _write_json(
        root / "video_to_analysis_operator_dashboard_polish_v1" / "operator_dashboard_polish_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "operatorDashboardRouteReady": True,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_acceptance_report_route_binding_v1"
        / "acceptance_report_route_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "acceptanceReportRouteReady": True,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            **guardrails,
        },
    )
    _write_json(
        root / "video_to_analysis_release_readout_route_binding_v1" / "release_readout_route_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "releaseReadoutRouteReady": True,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            **guardrails,
        },
    )
    _write_json(
        root / "video_to_analysis_post_release_monitoring_closeout_v1" / "post_release_monitoring_closeout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "postReleaseMonitoringCloseoutReady": True,
            **guardrails,
        },
    )


def test_current_release_acceptance_surface_packages_v57_manual_decision(tmp_path: Path) -> None:
    _seed_current_release_truth(tmp_path)

    payload = surface.run_video_to_analysis_current_release_acceptance_decision_surface(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_current_release_acceptance_decision_surface_v1"
    decision_model = json.loads((output_root / "current_operator_decision_model.json").read_text(encoding="utf-8"))
    route_audit = json.loads((output_root / "current_route_readiness_audit.json").read_text(encoding="utf-8"))
    guardrail_audit = json.loads((output_root / "current_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["releaseRuntimeComplete"] is True
    assert payload["operatorDashboardRouteReady"] is True
    assert payload["acceptanceReportRouteReady"] is True
    assert payload["releaseReadoutRouteReady"] is True
    assert payload["growthLaneClosedAtVersion"] == 57
    assert payload["selectedStrategicLane"] == "manual_strategic_lane_selection_required"
    assert payload["recommendedStrategicChoice"] == "external_benchmark_soccernet_lane"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_plan"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert decision_model["currentState"] == "release_operational_growth_lane_closed"
    assert decision_model["recommendedStrategicChoice"] == "external_benchmark_soccernet_lane"
    assert "resume_bounded_growth_intentionally" in decision_model["availableStrategicChoices"]
    assert route_audit["allCurrentRoutesReady"] is True
    assert guardrail_audit["allMutationGuardrailsPreserved"] is True


def test_current_release_acceptance_surface_uses_latest_v7_3_closeout_truth(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path)
    guardrails = _false_guardrails()
    _seed_current_release_truth(tmp_path)

    _write_json(
        root
        / "video_to_analysis_growth_lane_closeout_readout_v66"
        / "growth_lane_closeout_readout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "growthLaneCloseoutReady": True,
            "growthLaneClosedAtSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v110",
            "growthLaneClosedAtVersion": 110,
            "autoContinueBoundedGrowthRecommended": False,
            "manualStrategicChoiceRequired": True,
            "nextRecommendedNextLever": "manual_strategic_lane_selection_required",
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_next_strategic_lane_selection_v5"
        / "next_strategic_lane_selection_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "selectedStrategicLane": "manual_strategic_lane_selection_required",
            "growthLaneCloseoutManualStrategicChoiceRequired": True,
            "growthLaneClosedAtSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v110",
            "growthLaneClosedAtVersion": 110,
            "nextRecommendedNextLever": "manual_strategic_lane_selection_required",
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_release_acceptance_archive_v2"
        / "release_acceptance_archive_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "currentReleaseFinished": True,
            "videoToAnalysisReleaseAcceptanceArchived": True,
            "activeRuntimeDefaultVersion": "v7.3",
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultMutationExecutedByThisBatch": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )
    _write_json(
        root
        / "video_to_analysis_operator_dashboard_polish_v2"
        / "operator_dashboard_polish_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "operatorDashboardRouteReady": True,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_steady_state_monitoring_cycle_v2"
        / "steady_state_monitoring_cycle_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "steadyStateMonitoringCyclePassed": True,
            **guardrails,
        },
    )
    _write_json(
        root
        / "video_to_analysis_next_roadmap_direction_snapshot_v76"
        / "next_roadmap_direction_snapshot_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "sourceSamplingPoolExhausted": True,
            "selectedNextFamily": "video_to_analysis_source_pool_replenishment_plan",
            "nextRecommendedNextLever": "video_to_analysis_source_pool_replenishment_plan",
            **guardrails,
        },
    )

    payload = surface.run_video_to_analysis_current_release_acceptance_decision_surface(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_current_release_acceptance_decision_surface_v2",
    )

    output_root = _candidate_root(tmp_path) / "video_to_analysis_current_release_acceptance_decision_surface_v2"
    decision_model = json.loads((output_root / "current_operator_decision_model.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["releasedRuntimeVersion"] == "v7.3"
    assert payload["growthLaneClosedAtVersion"] == 110
    assert payload["sourcePoolCycleStillPresent"] is True
    assert payload["recommendedStrategicChoice"] == "manual_operator_release_decision"
    assert payload["nextRecommendedNextLever"] == "manual_operator_release_decision_required"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert decision_model["currentState"] == "current_release_done_optional_coverage_loop"
    assert decision_model["recommendedNextLever"] == "manual_operator_release_decision_required"


def test_current_release_acceptance_surface_blocks_when_readout_route_is_missing(tmp_path: Path) -> None:
    _seed_current_release_truth(tmp_path)
    missing = (
        _candidate_root(tmp_path)
        / "video_to_analysis_release_readout_route_binding_v1"
        / "release_readout_route_binding_summary.json"
    )
    missing.unlink()

    payload = surface.run_video_to_analysis_current_release_acceptance_decision_surface(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_current_release_route_stale"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_readout_route_binding"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
