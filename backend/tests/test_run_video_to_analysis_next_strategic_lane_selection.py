from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_next_strategic_lane_selection as selector


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_release_readout_route(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    pack = root / "video_to_analysis_release_readout_pack_v1"
    _write_json(
        pack / "next_strategic_lane_matrix.json",
        {
            "schemaVersion": "video_to_analysis_next_strategic_lane_matrix_v1",
            "recommendedLane": "external_benchmark_expansion_or_release_readout",
            "candidateStrategicLanes": [
                {
                    "id": "external_benchmark_expansion",
                    "label": "External benchmark expansion",
                    "nextLever": "football_external_benchmark_real_evaluation_design",
                },
                {
                    "id": "user_facing_release_readout",
                    "label": "User-facing release/readout",
                    "nextLever": "video_to_analysis_user_facing_release_readout",
                },
                {
                    "id": "bounded_growth_v38_continuation",
                    "label": "Continue bounded growth from v38",
                    "nextLever": "video_to_analysis_bounded_next_sample_execution_approval",
                },
            ],
        },
    )
    route = root / "video_to_analysis_release_readout_route_binding_v1"
    _write_json(
        route / "release_readout_route_binding_summary.json",
        {
            "batchName": "video_to_analysis_release_readout_route_binding",
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "releaseReadoutRouteReady": True,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_next_strategic_lane_selection",
        },
    )


def _seed_external_benchmark_already_satisfied(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "football_external_benchmark_real_report_and_product_binding_v1"
        / "real_report_and_product_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "productBindingReady": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def _seed_completed_user_readout(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_user_facing_release_readout_v1"
        / "user_facing_release_readout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "userFacingReleaseReadoutReady": True,
            "nextRecommendedNextLever": "video_to_analysis_storage_cleanup_approval",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def _seed_completed_operator_dashboard(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_operator_dashboard_polish_v1"
        / "operator_dashboard_polish_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "operatorDashboardRouteReady": True,
            "nextRecommendedNextLever": "football_external_benchmark_real_source_path_consolidation",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def _seed_completed_storage_cleanup(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
        / "video_to_analysis_storage_cleanup_closeout_v1"
        / "storage_cleanup_closeout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "storageCleanupCloseoutReady": True,
            "nextRecommendedNextLever": "video_to_analysis_next_strategic_lane_selection",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def _seed_growth_lane_closeout_requiring_manual_choice(storage_root: Path) -> None:
    _write_json(
        _candidate_root(storage_root)
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
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )


def test_selector_routes_to_user_facing_readout_when_external_benchmark_is_satisfied(tmp_path: Path) -> None:
    _seed_release_readout_route(tmp_path)
    _seed_external_benchmark_already_satisfied(tmp_path)

    payload = selector.run_video_to_analysis_next_strategic_lane_selection(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_next_strategic_lane_selection_v1"
    selection = json.loads((output_root / "strategic_lane_selection.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedStrategicLane"] == "user_facing_release_readout"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_user_facing_release_readout"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert selection["reason"] == "external_benchmark_already_satisfied_release_readout_route_live"


def test_selector_skips_completed_readout_dashboard_and_storage_then_resumes_bounded_growth(tmp_path: Path) -> None:
    _seed_release_readout_route(tmp_path)
    _seed_external_benchmark_already_satisfied(tmp_path)
    _seed_completed_user_readout(tmp_path)
    _seed_completed_operator_dashboard(tmp_path)
    _seed_completed_storage_cleanup(tmp_path)

    payload = selector.run_video_to_analysis_next_strategic_lane_selection(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_next_strategic_lane_selection_v1"
    selection = json.loads((output_root / "strategic_lane_selection.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedStrategicLane"] == "bounded_growth_v38_continuation"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_bounded_next_sample_execution_approval"
    assert selection["reason"] == "strategic_housekeeping_complete_resume_bounded_growth"


def test_selector_stops_at_manual_choice_when_growth_lane_closeout_exists(tmp_path: Path) -> None:
    _seed_release_readout_route(tmp_path)
    _seed_external_benchmark_already_satisfied(tmp_path)
    _seed_completed_user_readout(tmp_path)
    _seed_completed_operator_dashboard(tmp_path)
    _seed_completed_storage_cleanup(tmp_path)
    _seed_growth_lane_closeout_requiring_manual_choice(tmp_path)

    payload = selector.run_video_to_analysis_next_strategic_lane_selection(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_next_strategic_lane_selection_v1"
    selection = json.loads((output_root / "strategic_lane_selection.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedStrategicLane"] == "manual_strategic_lane_selection_required"
    assert payload["nextRecommendedNextLever"] == "manual_strategic_lane_selection_required"
    assert payload["growthLaneCloseoutManualStrategicChoiceRequired"] is True
    assert payload["growthLaneClosedAtSnapshotDir"] == "video_to_analysis_next_sample_selection_snapshot_v57"
    assert selection["reason"] == "growth_lane_closeout_requires_operator_strategic_choice"


def test_selector_blocks_without_release_readout_route(tmp_path: Path) -> None:
    payload = selector.run_video_to_analysis_next_strategic_lane_selection(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_next_strategic_lane_release_readout_route_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_readout_route_binding"
