from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_real_video_scaleout_execution_approval as approval
import backend.scripts.run_video_to_analysis_real_video_scaleout_bounded_execution as execution
import backend.scripts.run_video_to_analysis_real_video_scaleout_report_route_binding as route_binding
import backend.scripts.run_video_to_analysis_real_video_scaleout_lane_closeout as closeout
import backend.scripts.run_video_to_analysis_next_sample_selection_snapshot as next_snapshot
import backend.scripts.run_video_to_analysis_real_video_scaleout_plan_refresh as plan_refresh
import backend.scripts.run_video_to_analysis_real_video_scaleout_source_sampling_expansion as source_sampling
from backend.tests.test_run_video_to_analysis_operational_roadmap_sprint import _seed_dashboard
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root
import backend.scripts.run_football_external_benchmark_real_source_path_consolidation as source_paths
import backend.scripts.run_video_to_analysis_growth_lane_decision_snapshot as growth_snapshot
import backend.scripts.run_video_to_analysis_operational_sprint_closeout as sprint_closeout
import backend.scripts.run_video_to_analysis_real_video_scaleout_plan as scaleout_plan
import backend.scripts.run_video_to_analysis_steady_state_monitoring_recurring_schedule as recurring


def _seed_growth_snapshot(storage_root: Path) -> None:
    _seed_dashboard(storage_root)
    source_paths.run_football_external_benchmark_real_source_path_consolidation(storage_root=storage_root)
    scaleout_plan.run_video_to_analysis_real_video_scaleout_plan(storage_root=storage_root)
    recurring.run_video_to_analysis_steady_state_monitoring_recurring_schedule(storage_root=storage_root)
    sprint_closeout.run_video_to_analysis_operational_sprint_closeout(storage_root=storage_root)
    growth_snapshot.run_video_to_analysis_growth_lane_decision_snapshot(storage_root=storage_root)


def test_real_video_scaleout_execution_chain_approves_executes_reports_and_selects_next_sample(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)

    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_payload = route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout_payload = closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)
    snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    approval_contract = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_execution_approval_v1"
            / "real_video_scaleout_execution_approval_contract.json"
        ).read_text(encoding="utf-8")
    )
    execution_audit = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_bounded_execution_v1"
            / "real_video_scaleout_execution_audit.json"
        ).read_text(encoding="utf-8")
    )

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/real-video-scaleout-report")
            html_response = await client.get("/video-to-analysis/real-video-scaleout-report")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert approval_payload["goalAchieved"] is True
    assert approval_payload["approvedExecutionMode"] == "bounded_existing_artifact_real_video_scaleout"
    assert approval_payload["approvedScaleoutCaseCount"] == 5
    assert approval_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_bounded_execution"
    assert approval_contract["fullDatasetDownloadApproved"] is False
    assert approval_contract["normalMatchStorageMutationApproved"] is False

    assert execution_payload["goalAchieved"] is True
    assert execution_payload["boundedRealVideoScaleoutExecuted"] is True
    assert execution_payload["scaleoutResultRowCount"] == 5
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert execution_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_report_route_binding"
    assert execution_audit["executionMode"] == "bounded_existing_artifact_real_video_scaleout"
    assert len(execution_audit["scaleoutResults"]) == 5

    assert route_payload["goalAchieved"] is True
    assert route_payload["scaleoutReportRouteReady"] is True
    assert route_payload["apiRouteStatusCode"] == 200
    assert route_payload["htmlRouteStatusCode"] == 200
    assert api_payload["schemaVersion"] == "video_to_analysis_real_video_scaleout_report_view_model_v1"
    assert "Real-video scaleout report" in html

    assert closeout_payload["goalAchieved"] is True
    assert closeout_payload["realVideoScaleoutLaneClosed"] is True
    assert closeout_payload["nextRecommendedNextLever"] == "video_to_analysis_next_sample_selection_snapshot"

    assert snapshot_payload["goalAchieved"] is True
    assert snapshot_payload["nextSampleSelectionSnapshotReady"] is True
    assert snapshot_payload["selectedNextLever"] == "video_to_analysis_bounded_next_sample_execution_approval"

    for payload in [approval_payload, execution_payload, route_payload, closeout_payload, snapshot_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False
        assert payload["videoDownloadExecuted"] is False
        assert payload["dataDownloadExecuted"] is False


def test_real_video_scaleout_approval_blocks_without_growth_snapshot(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_real_video_scaleout_growth_snapshot_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_growth_lane_decision_snapshot"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_refresh_chain_uses_new_cases_and_latest_routes(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)
    pool_exhaustion_root = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_approval_v4"
    pool_exhaustion_root.mkdir(parents=True)
    (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted",
            }
        ),
        encoding="utf-8",
    )

    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v2",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v2",
    )
    route_payload = route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v2",
    )
    closeout_payload = closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v2",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v2",
    )

    root = _candidate_root(tmp_path)
    refreshed_plan = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_plan_refresh_v1"
            / "real_video_scaleout_plan.json"
        ).read_text(encoding="utf-8")
    )
    original_ids = {
        "promoted_runtime_reference_video",
        "soccernet_bounded_224p_member",
        "soccertrack_materialized_fixture",
        "normal_storage_recent_upload",
        "operator_selected_canary_video",
    }
    refreshed_ids = {row["id"] for row in refreshed_plan["scaleoutCases"]}

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/real-video-scaleout-report")
            html_response = await client.get("/video-to-analysis/real-video-scaleout-report")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert refresh_payload["goalAchieved"] is True
    assert refresh_payload["refreshedScaleoutCaseCount"] == 5
    assert not refreshed_ids.intersection(original_ids)
    assert "soccernet_third_bounded_member" in refreshed_ids

    assert approval_payload["goalAchieved"] is True
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v1"
    assert approval_payload["approvedScaleoutCaseCount"] == 5

    assert execution_payload["goalAchieved"] is True
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v2"
    assert execution_payload["scaleoutPassedCaseCount"] == 5

    assert route_payload["goalAchieved"] is True
    assert route_payload["apiRouteStatusCode"] == 200
    assert closeout_payload["goalAchieved"] is True
    assert next_snapshot_payload["goalAchieved"] is True
    assert next_snapshot_payload["candidateSampleCount"] == 3
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_followup_clip",
        "soccernet_third_bounded_member",
        "normal_storage_followup_upload",
    ]
    assert api_payload["sourceExecutionDir"] == "video_to_analysis_real_video_scaleout_bounded_execution_v2"
    assert api_payload["scaleoutPassedCaseCount"] == 5
    assert "Real-video scaleout report" in html

    for payload in [refresh_payload, approval_payload, execution_payload, route_payload, closeout_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False
        assert payload["videoDownloadExecuted"] is False
        assert payload["dataDownloadExecuted"] is False


def test_real_video_scaleout_second_refresh_excludes_prior_refresh_cases(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v2",
    )
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v2",
    )
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v2",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v2",
    )

    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2",
    )
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v3",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v3",
    )
    route_payload = route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v3",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v3",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v3",
    )

    first_plan = json.loads((root / "video_to_analysis_real_video_scaleout_plan_v1" / "real_video_scaleout_plan.json").read_text())
    refresh_one = json.loads((root / "video_to_analysis_real_video_scaleout_plan_refresh_v1" / "real_video_scaleout_plan.json").read_text())
    refresh_two = json.loads((root / "video_to_analysis_real_video_scaleout_plan_refresh_v2" / "real_video_scaleout_plan.json").read_text())
    prior_ids = {row["id"] for row in first_plan["scaleoutCases"] + refresh_one["scaleoutCases"]}
    refresh_two_ids = {row["id"] for row in refresh_two["scaleoutCases"]}

    assert refresh_payload["goalAchieved"] is True
    assert refresh_payload["refreshedScaleoutCaseCount"] == 5
    assert not refresh_two_ids.intersection(prior_ids)
    assert "soccernet_fourth_bounded_member" in refresh_two_ids
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v2"
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v3"
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert route_payload["goalAchieved"] is True
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_second_followup_clip",
        "soccernet_fourth_bounded_member",
        "normal_storage_second_followup_upload",
    ]


def test_real_video_scaleout_third_refresh_blocks_when_candidate_pool_is_insufficient(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8", "v12"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2",
    )
    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v3",
    )

    refresh_plan = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_plan_refresh_v3"
            / "real_video_scaleout_plan.json"
        ).read_text(encoding="utf-8")
    )

    assert refresh_payload["goalAchieved"] is False
    assert refresh_payload["roadmapAdvanceAllowed"] is True
    assert refresh_payload["primaryBlocker"] == "video_to_analysis_real_video_scaleout_candidate_pool_insufficient"
    assert refresh_payload["availableFreshScaleoutCaseCount"] == 2
    assert refresh_payload["requiredFreshScaleoutCaseCount"] == 5
    assert refresh_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_source_sampling_expansion"
    assert refresh_plan["scaleoutCases"] == []
    assert refresh_plan["availableFreshScaleoutCases"] == [
        {
            "id": "promoted_runtime_alternate_reference_video",
            "executionMode": "bounded_existing_or_approved_sample_only",
            "sourceFamily": "promoted_runtime",
        },
        {
            "id": "soccernet_sixth_bounded_member",
            "executionMode": "bounded_existing_or_approved_sample_only",
            "sourceFamily": "soccernet",
        },
    ]
    assert refresh_payload["trainingExecuted"] is False
    assert refresh_payload["promotionMutationExecuted"] is False
    assert refresh_payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_approval_routes_exhausted_generated_pool_to_roadmap_snapshot(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    root = _candidate_root(tmp_path)
    refresh_root = root / "video_to_analysis_real_video_scaleout_plan_refresh_v1"
    refresh_root.mkdir(parents=True)
    (refresh_root / "real_video_scaleout_plan.json").write_text(
        json.dumps(
            {
                "schemaVersion": "video_to_analysis_real_video_scaleout_plan_refresh_v1",
                "realVideoScaleoutPlanReady": False,
                "scaleoutCaseCount": 0,
                "scaleoutCases": [],
                "availableFreshScaleoutCaseCount": 3,
                "requiredFreshScaleoutCaseCount": 5,
            }
        ),
        encoding="utf-8",
    )
    source_sampling_root = root / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v1"
    source_sampling_root.mkdir(parents=True)
    (source_sampling_root / "real_video_scaleout_source_sampling_expansion_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
                "generatedSourceSamplingPoolExhausted": True,
                "expandedScaleoutCandidateCount": 0,
            }
        ),
        encoding="utf-8",
    )

    payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_real_video_scaleout_plan_insufficient"
    assert payload["sourceSamplingPoolExhausted"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_roadmap_direction_snapshot"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_approval_uses_fresh_base_plan_over_stale_exhausted_refresh(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path)
    refresh_root = root / "video_to_analysis_real_video_scaleout_plan_refresh_v99"
    refresh_root.mkdir(parents=True)
    (refresh_root / "real_video_scaleout_plan.json").write_text(
        json.dumps(
            {
                "schemaVersion": "video_to_analysis_real_video_scaleout_plan_refresh_v1",
                "generatedAt": "2026-05-12T09:03:03.085008+00:00",
                "realVideoScaleoutPlanReady": False,
                "scaleoutCaseCount": 0,
                "scaleoutCases": [],
                "availableFreshScaleoutCaseCount": 2,
                "requiredFreshScaleoutCaseCount": 5,
            }
        ),
        encoding="utf-8",
    )
    source_sampling_root = root / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v99"
    source_sampling_root.mkdir(parents=True)
    (source_sampling_root / "real_video_scaleout_source_sampling_expansion_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": False,
                "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
                "generatedAt": "2026-05-12T09:04:03.085008+00:00",
                "generatedSourceSamplingPoolExhausted": True,
                "expandedScaleoutCandidateCount": 0,
            }
        ),
        encoding="utf-8",
    )
    _seed_growth_snapshot(tmp_path)

    payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_v1"
    assert payload["approvedScaleoutCaseCount"] == 5
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_bounded_execution"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_source_sampling_expansion_unlocks_next_refresh(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8", "v12"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2",
    )
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v3",
    )

    expansion_payload = source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(
        storage_root=tmp_path
    )
    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v4",
    )
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v4",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v4",
    )
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v4",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v4",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v4",
    )

    refresh_plan = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_plan_refresh_v4"
            / "real_video_scaleout_plan.json"
        ).read_text(encoding="utf-8")
    )

    assert expansion_payload["goalAchieved"] is True
    assert expansion_payload["expandedScaleoutCandidateCount"] >= 5
    assert expansion_payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_execution_approval"
    assert refresh_payload["goalAchieved"] is True
    assert refresh_payload["refreshedScaleoutCaseCount"] == 5
    assert [row["id"] for row in refresh_plan["scaleoutCases"]] == [
        "operator_canary_third_followup_clip",
        "soccernet_seventh_bounded_member",
        "normal_storage_third_followup_upload",
        "soccertrack_fourth_materialized_fixture",
        "promoted_runtime_second_alternate_reference_video",
    ]
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v4"
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v4"
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_third_followup_clip",
        "soccernet_seventh_bounded_member",
        "normal_storage_third_followup_upload",
    ]
    for payload in [expansion_payload, refresh_payload, approval_payload, execution_payload, next_snapshot_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_second_source_sampling_expansion_unlocks_followup_refresh(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8", "v12", "v16"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2",
    )
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v3",
    )
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v4",
    )
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v5",
    )

    expansion_payload = source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v2",
    )
    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v6",
    )
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v5",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v5",
    )
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v5",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v5",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v5",
    )

    refresh_plan = json.loads(
        (
            root
            / "video_to_analysis_real_video_scaleout_plan_refresh_v6"
            / "real_video_scaleout_plan.json"
        ).read_text(encoding="utf-8")
    )

    assert expansion_payload["goalAchieved"] is True
    assert expansion_payload["sourceInsufficientRefreshDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v5"
    assert expansion_payload["expandedScaleoutCandidateCount"] == 6
    assert refresh_payload["goalAchieved"] is True
    assert [row["id"] for row in refresh_plan["scaleoutCases"]] == [
        "operator_canary_fourth_followup_clip",
        "soccernet_ninth_bounded_member",
        "normal_storage_fourth_followup_upload",
        "soccertrack_fifth_materialized_fixture",
        "promoted_runtime_third_alternate_reference_video",
    ]
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v6"
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v5"
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_fourth_followup_clip",
        "soccernet_ninth_bounded_member",
        "normal_storage_fourth_followup_upload",
    ]
    for payload in [expansion_payload, refresh_payload, approval_payload, execution_payload, next_snapshot_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_third_source_sampling_expansion_unlocks_another_refresh(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8", "v12", "v16", "v20"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v3")
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v4")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v5")
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v2")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v6")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v7")

    expansion_payload = source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v3",
    )
    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v8",
    )
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v6",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v6",
    )
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v6",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v6",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v6",
    )

    refresh_plan = json.loads((root / "video_to_analysis_real_video_scaleout_plan_refresh_v8" / "real_video_scaleout_plan.json").read_text())

    assert expansion_payload["goalAchieved"] is True
    assert expansion_payload["sourceInsufficientRefreshDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v7"
    assert refresh_payload["goalAchieved"] is True
    assert [row["id"] for row in refresh_plan["scaleoutCases"]] == [
        "operator_canary_fifth_followup_clip",
        "soccernet_eleventh_bounded_member",
        "normal_storage_fifth_followup_upload",
        "soccertrack_sixth_materialized_fixture",
        "promoted_runtime_fourth_alternate_reference_video",
    ]
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v8"
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v6"
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_fifth_followup_clip",
        "soccernet_eleventh_bounded_member",
        "normal_storage_fifth_followup_upload",
    ]
    for payload in [expansion_payload, refresh_payload, approval_payload, execution_payload, next_snapshot_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False


def test_real_video_scaleout_fourth_source_sampling_uses_generated_tranche_and_dynamic_snapshot(tmp_path: Path) -> None:
    _seed_growth_snapshot(tmp_path)
    approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    for version in ("v4", "v8", "v12", "v16", "v20", "v24"):
        pool_exhaustion_root = root / f"video_to_analysis_bounded_next_sample_execution_approval_{version}"
        pool_exhaustion_root.mkdir(parents=True)
        (pool_exhaustion_root / "bounded_next_sample_execution_approval_summary.json").write_text(
            json.dumps({"goalAchieved": False, "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted"}),
            encoding="utf-8",
        )

    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v2")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v3")
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path)
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v4")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v5")
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v2")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v6")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v7")
    source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v3")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v8")
    plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(storage_root=tmp_path, output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v9")

    expansion_payload = source_sampling.run_video_to_analysis_real_video_scaleout_source_sampling_expansion(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_source_sampling_expansion_v4",
    )
    refresh_payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v10",
    )
    approval_payload = approval.run_video_to_analysis_real_video_scaleout_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_execution_approval_v7",
    )
    execution_payload = execution.run_video_to_analysis_real_video_scaleout_bounded_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_bounded_execution_v7",
    )
    route_binding.run_video_to_analysis_real_video_scaleout_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_report_route_binding_v7",
    )
    closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_lane_closeout_v7",
    )
    next_snapshot_payload = next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_sample_selection_snapshot_v7",
    )

    refresh_plan = json.loads((root / "video_to_analysis_real_video_scaleout_plan_refresh_v10" / "real_video_scaleout_plan.json").read_text())

    assert expansion_payload["goalAchieved"] is True
    assert expansion_payload["sourceInsufficientRefreshDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v9"
    assert refresh_payload["goalAchieved"] is True
    assert [row["id"] for row in refresh_plan["scaleoutCases"]] == [
        "operator_canary_sixth_followup_clip",
        "soccernet_thirteenth_bounded_member",
        "normal_storage_sixth_followup_upload",
        "soccertrack_seventh_materialized_fixture",
        "promoted_runtime_fifth_alternate_reference_video",
    ]
    assert approval_payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v10"
    assert execution_payload["sourceApprovalDir"] == "video_to_analysis_real_video_scaleout_execution_approval_v7"
    assert execution_payload["scaleoutPassedCaseCount"] == 5
    assert next_snapshot_payload["candidateSampleIds"] == [
        "operator_canary_sixth_followup_clip",
        "soccernet_thirteenth_bounded_member",
        "normal_storage_sixth_followup_upload",
    ]
