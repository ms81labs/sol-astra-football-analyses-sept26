from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_real_source_path_consolidation as source_paths
import backend.scripts.run_video_to_analysis_growth_lane_decision_snapshot as growth_snapshot
import backend.scripts.run_video_to_analysis_operator_dashboard_polish as dashboard
import backend.scripts.run_video_to_analysis_operational_sprint_closeout as closeout
import backend.scripts.run_video_to_analysis_real_video_scaleout_plan as scaleout
import backend.scripts.run_video_to_analysis_steady_state_monitoring_recurring_schedule as recurring
from backend.tests.test_run_video_to_analysis_operator_dashboard_polish import _seed_storage_hygiene
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root


def _seed_dashboard(tmp_path: Path) -> None:
    _seed_storage_hygiene(tmp_path)
    dashboard.run_video_to_analysis_operator_dashboard_polish(storage_root=tmp_path)


def test_operational_roadmap_sprint_executes_five_item_chain(tmp_path: Path) -> None:
    _seed_dashboard(tmp_path)

    source_payload = source_paths.run_football_external_benchmark_real_source_path_consolidation(storage_root=tmp_path)
    scaleout_payload = scaleout.run_video_to_analysis_real_video_scaleout_plan(storage_root=tmp_path)
    recurring_payload = recurring.run_video_to_analysis_steady_state_monitoring_recurring_schedule(storage_root=tmp_path)
    closeout_payload = closeout.run_video_to_analysis_operational_sprint_closeout(storage_root=tmp_path)
    snapshot_payload = growth_snapshot.run_video_to_analysis_growth_lane_decision_snapshot(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    source_manifest = json.loads(
        (
            root
            / "football_external_benchmark_real_source_path_consolidation_v1"
            / "real_source_path_consolidation_manifest.json"
        ).read_text(encoding="utf-8")
    )
    scaleout_plan = json.loads(
        (root / "video_to_analysis_real_video_scaleout_plan_v1" / "real_video_scaleout_plan.json").read_text(
            encoding="utf-8"
        )
    )
    schedule = json.loads(
        (
            root
            / "video_to_analysis_steady_state_monitoring_recurring_schedule_v1"
            / "steady_state_monitoring_recurring_schedule.json"
        ).read_text(encoding="utf-8")
    )

    assert source_payload["goalAchieved"] is True
    assert source_payload["primaryBlocker"] is None
    assert source_payload["sourcePathConsolidationReady"] is True
    assert source_payload["sourcePathCount"] == 2
    assert source_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_plan"
    assert source_manifest["sourcePaths"][0]["sourceId"] == "soccernet"
    assert source_manifest["sourcePaths"][1]["sourceId"] == "soccertrack"

    assert scaleout_payload["goalAchieved"] is True
    assert scaleout_payload["realVideoScaleoutPlanReady"] is True
    assert scaleout_payload["scaleoutCaseCount"] == 5
    assert scaleout_payload["nextRecommendedNextLever"] == "video_to_analysis_steady_state_monitoring_recurring_schedule"
    assert scaleout_plan["scaleoutCases"][0]["executionMode"] == "bounded_existing_or_approved_sample_only"

    assert recurring_payload["goalAchieved"] is True
    assert recurring_payload["recurringScheduleReady"] is True
    assert recurring_payload["monitoringCadence"] == "per_operational_batch_and_daily_when_active"
    assert recurring_payload["nextRecommendedNextLever"] == "video_to_analysis_operational_sprint_closeout"
    assert schedule["failureRouting"]["route_smoke_failure"] == "promoted_runtime_route_binding_repair"

    assert closeout_payload["goalAchieved"] is True
    assert closeout_payload["operationalSprintClosed"] is True
    assert closeout_payload["completedOperationalItemCount"] == 4
    assert closeout_payload["nextRecommendedNextLever"] == "video_to_analysis_growth_lane_decision_snapshot"

    assert snapshot_payload["goalAchieved"] is True
    assert snapshot_payload["growthLaneDecisionSnapshotReady"] is True
    assert snapshot_payload["selectedGrowthLever"] == "video_to_analysis_real_video_scaleout_execution_approval"
    assert snapshot_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_execution_approval"

    for payload in [source_payload, scaleout_payload, recurring_payload, closeout_payload, snapshot_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False
        assert payload["videoDownloadExecuted"] is False
        assert payload["dataDownloadExecuted"] is False


def test_operational_roadmap_sprint_blocks_first_step_without_dashboard_truth(tmp_path: Path) -> None:
    payload = source_paths.run_football_external_benchmark_real_source_path_consolidation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_real_source_path_operator_dashboard_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_dashboard_polish"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
