from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_roadmap_state_reconciliation as reconciliation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"


def _seed_reconciled_state(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    suite_root = _suite_root(storage_root)
    _write_json(
        storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
        {
            "trainingCandidateVersion": "v7.3",
            "runtimeUse": "default_runtime",
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
        },
    )
    _write_json(
        suite_root / "v7_3_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "runtimeDefaultRolloutClosed": True},
    )
    _write_json(
        root / "video_to_analysis_release_candidate_closeout_v1" / "release_candidate_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "videoToAnalysisReleaseCandidateClosed": True},
    )
    _write_json(
        root / "video_to_analysis_operator_handoff_route_binding_v1" / "operator_handoff_route_binding_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "operatorHandoffRouteReady": True},
    )
    _write_json(
        root / "video_to_analysis_product_lane_closeout_v1" / "product_lane_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "videoToAnalysisProductLaneClosed": True},
    )
    _write_json(
        root / "video_to_analysis_post_release_monitoring_closeout_v1" / "post_release_monitoring_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "postReleaseMonitoringClosed": True},
    )
    _write_json(
        root / "video_to_analysis_detector_evaluation_lane_closeout_v1" / "detector_evaluation_lane_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "detectorEvaluationLaneClosed": True},
    )
    _write_json(
        root / "video_to_analysis_promotion_review_closeout_v1" / "promotion_review_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None, "promotionReviewClosed": True},
    )
    _write_json(
        root / "football_external_soccernet_full_analysis_lane_closeout_v1" / "full_analysis_lane_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )
    _write_json(
        root / "football_external_soccertrack_analysis_product_lane_closeout_v1" / "analysis_product_lane_closeout_summary.json",
        {"goalAchieved": True, "primaryBlocker": None},
    )
    _write_json(
        root / "video_to_analysis_growth_lane_closeout_readout_v64" / "growth_lane_closeout_readout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "growthLaneCloseoutReady": True,
            "manualStrategicChoiceRequired": True,
            "autoContinueBoundedGrowthRecommended": False,
        },
    )
    _write_json(
        root / "video_to_analysis_next_strategic_lane_selection_v2" / "next_strategic_lane_selection_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "selectedStrategicLane": "manual_strategic_lane_selection_required",
            "nextRecommendedNextLever": "manual_strategic_lane_selection_required",
        },
    )


def test_reconciliation_resolves_manual_sentinel_to_release_archive(tmp_path: Path) -> None:
    _seed_reconciled_state(tmp_path)

    payload = reconciliation.run_video_to_analysis_roadmap_state_reconciliation(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_roadmap_state_reconciliation_v1"
    next_five = json.loads((output_root / "next_five_step_plan.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["manualStrategicSentinelResolved"] is True
    assert payload["growthLaneAutoResumeAllowed"] is False
    assert payload["selectedStrategicLane"] == "release_acceptance_archive"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_acceptance_archive"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert next_five["steps"][0]["lever"] == "video_to_analysis_release_acceptance_archive"


def test_reconciliation_routes_to_runtime_rollout_when_v7_3_default_is_not_active(tmp_path: Path) -> None:
    _seed_reconciled_state(tmp_path)
    _write_json(
        tmp_path / "runtime" / "promoted_touchline_detector_candidate.json",
        {
            "trainingCandidateVersion": "v7.2",
            "runtimeUse": "default_runtime",
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
        },
    )

    payload = reconciliation.run_video_to_analysis_roadmap_state_reconciliation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_reconciliation_runtime_rollout_incomplete"
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_closeout"


def test_reconciliation_refuses_archive_without_growth_closeout(tmp_path: Path) -> None:
    _seed_reconciled_state(tmp_path)
    closeout_path = (
        _candidate_root(tmp_path)
        / "video_to_analysis_growth_lane_closeout_readout_v64"
        / "growth_lane_closeout_readout_summary.json"
    )
    closeout_path.unlink()

    payload = reconciliation.run_video_to_analysis_roadmap_state_reconciliation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_reconciliation_growth_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_strategic_lane_selection"
