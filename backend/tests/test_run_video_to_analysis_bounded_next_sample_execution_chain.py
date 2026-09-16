from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root
from backend.tests.test_run_video_to_analysis_real_video_scaleout_execution_chain import _seed_growth_snapshot
import backend.scripts.run_video_to_analysis_bounded_next_sample_execution_approval as approval
import backend.scripts.run_video_to_analysis_bounded_next_sample_execution as execution
import backend.scripts.run_video_to_analysis_bounded_next_sample_report_route_binding as route_binding
import backend.scripts.run_video_to_analysis_bounded_next_sample_closeout as closeout
import backend.scripts.run_video_to_analysis_scaleout_or_backlog_decision_snapshot as decision
import backend.scripts.run_video_to_analysis_source_and_artifact_cleanup_map as cleanup_map
import backend.scripts.run_video_to_analysis_real_video_scaleout_execution_approval as scaleout_approval
import backend.scripts.run_video_to_analysis_real_video_scaleout_bounded_execution as scaleout_execution
import backend.scripts.run_video_to_analysis_real_video_scaleout_report_route_binding as scaleout_route
import backend.scripts.run_video_to_analysis_real_video_scaleout_lane_closeout as scaleout_closeout
import backend.scripts.run_video_to_analysis_next_sample_selection_snapshot as next_snapshot


def _seed_next_sample_snapshot(storage_root: Path) -> None:
    _seed_growth_snapshot(storage_root)
    scaleout_approval.run_video_to_analysis_real_video_scaleout_execution_approval(storage_root=storage_root)
    scaleout_execution.run_video_to_analysis_real_video_scaleout_bounded_execution(storage_root=storage_root)
    scaleout_route.run_video_to_analysis_real_video_scaleout_report_route_binding(storage_root=storage_root)
    scaleout_closeout.run_video_to_analysis_real_video_scaleout_lane_closeout(storage_root=storage_root)
    next_snapshot.run_video_to_analysis_next_sample_selection_snapshot(storage_root=storage_root)


def test_bounded_next_sample_chain_approves_executes_reports_closes_and_maps_cleanup(tmp_path: Path) -> None:
    _seed_next_sample_snapshot(tmp_path)

    approval_payload = approval.run_video_to_analysis_bounded_next_sample_execution_approval(storage_root=tmp_path)
    execution_payload = execution.run_video_to_analysis_bounded_next_sample_execution(storage_root=tmp_path)
    route_payload = route_binding.run_video_to_analysis_bounded_next_sample_report_route_binding(storage_root=tmp_path)
    closeout_payload = closeout.run_video_to_analysis_bounded_next_sample_closeout(storage_root=tmp_path)
    decision_payload = decision.run_video_to_analysis_scaleout_or_backlog_decision_snapshot(storage_root=tmp_path)
    cleanup_payload = cleanup_map.run_video_to_analysis_source_and_artifact_cleanup_map(storage_root=tmp_path)

    root = _candidate_root(tmp_path)
    approval_contract = json.loads(
        (
            root
            / "video_to_analysis_bounded_next_sample_execution_approval_v1"
            / "bounded_next_sample_execution_approval_contract.json"
        ).read_text(encoding="utf-8")
    )
    execution_audit = json.loads(
        (
            root
            / "video_to_analysis_bounded_next_sample_execution_v1"
            / "bounded_next_sample_execution_audit.json"
        ).read_text(encoding="utf-8")
    )

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/bounded-next-sample-report")
            html_response = await client.get("/video-to-analysis/bounded-next-sample-report")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert approval_payload["goalAchieved"] is True
    assert approval_payload["approvedNextSampleId"] == "operator_selected_canary_video"
    assert approval_payload["approvedExecutionMode"] == "bounded_existing_artifact_next_sample"
    assert approval_payload["nextRecommendedNextLever"] == "video_to_analysis_bounded_next_sample_execution"
    assert approval_contract["normalMatchStorageMutationApproved"] is False
    assert approval_contract["fullDatasetDownloadApproved"] is False

    assert execution_payload["goalAchieved"] is True
    assert execution_payload["boundedNextSampleExecuted"] is True
    assert execution_payload["executedSampleId"] == "operator_selected_canary_video"
    assert execution_payload["nextRecommendedNextLever"] == "video_to_analysis_bounded_next_sample_report_route_binding"
    assert execution_audit["executionResult"]["status"] == "passed"

    assert route_payload["goalAchieved"] is True
    assert route_payload["boundedNextSampleReportRouteReady"] is True
    assert route_payload["apiRouteStatusCode"] == 200
    assert route_payload["htmlRouteStatusCode"] == 200
    assert api_payload["schemaVersion"] == "video_to_analysis_bounded_next_sample_report_view_model_v1"
    assert "Bounded next-sample report" in html

    assert closeout_payload["goalAchieved"] is True
    assert closeout_payload["boundedNextSampleLaneClosed"] is True
    assert closeout_payload["nextRecommendedNextLever"] == "video_to_analysis_scaleout_or_backlog_decision_snapshot"

    assert decision_payload["goalAchieved"] is True
    assert decision_payload["scaleoutOrBacklogDecisionSnapshotReady"] is True
    assert decision_payload["selectedNextLever"] == "video_to_analysis_source_and_artifact_cleanup_map"

    assert cleanup_payload["goalAchieved"] is True
    assert cleanup_payload["cleanupMapReady"] is True
    assert cleanup_payload["cleanupMutationExecuted"] is False
    assert cleanup_payload["generatedTruthDeleteAllowed"] is False
    assert cleanup_payload["nextRecommendedNextLever"] == "video_to_analysis_bounded_next_sample_execution_approval"

    for payload in [approval_payload, execution_payload, route_payload, closeout_payload, decision_payload, cleanup_payload]:
        assert payload["trainingExecuted"] is False
        assert payload["promotionMutationExecuted"] is False
        assert payload["runtimeDefaultMutationExecuted"] is False
        assert payload["videoDownloadExecuted"] is False
        assert payload["dataDownloadExecuted"] is False


def test_bounded_next_sample_approval_blocks_without_snapshot(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_bounded_next_sample_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_bounded_next_sample_selection_snapshot_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_sample_selection_snapshot"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_bounded_next_sample_v2_skips_previously_executed_sample(tmp_path: Path) -> None:
    _seed_next_sample_snapshot(tmp_path)

    approval.run_video_to_analysis_bounded_next_sample_execution_approval(storage_root=tmp_path)
    execution.run_video_to_analysis_bounded_next_sample_execution(storage_root=tmp_path)
    route_binding.run_video_to_analysis_bounded_next_sample_report_route_binding(storage_root=tmp_path)
    closeout.run_video_to_analysis_bounded_next_sample_closeout(storage_root=tmp_path)
    decision.run_video_to_analysis_scaleout_or_backlog_decision_snapshot(storage_root=tmp_path)
    cleanup_map.run_video_to_analysis_source_and_artifact_cleanup_map(storage_root=tmp_path)

    approval_payload = approval.run_video_to_analysis_bounded_next_sample_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_bounded_next_sample_execution_approval_v2",
    )
    execution_payload = execution.run_video_to_analysis_bounded_next_sample_execution(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_bounded_next_sample_execution_v2",
    )
    route_payload = route_binding.run_video_to_analysis_bounded_next_sample_report_route_binding(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_bounded_next_sample_report_route_binding_v2",
    )

    async def _fetch() -> dict[str, object]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/bounded-next-sample-report")
        assert api_response.status_code == 200
        return api_response.json()

    api_payload = asyncio.run(_fetch())

    assert approval_payload["goalAchieved"] is True
    assert approval_payload["approvedNextSampleId"] == "soccernet_second_bounded_member"
    assert execution_payload["goalAchieved"] is True
    assert execution_payload["executedSampleId"] == "soccernet_second_bounded_member"
    assert route_payload["goalAchieved"] is True
    assert api_payload["sampleId"] == "soccernet_second_bounded_member"


def test_bounded_next_sample_approval_routes_to_scaleout_when_pool_exhausted(tmp_path: Path) -> None:
    _seed_next_sample_snapshot(tmp_path)

    for version in ("v1", "v2", "v3"):
        approval.run_video_to_analysis_bounded_next_sample_execution_approval(
            storage_root=tmp_path,
            output_dir_name=f"video_to_analysis_bounded_next_sample_execution_approval_{version}",
        )
        execution.run_video_to_analysis_bounded_next_sample_execution(
            storage_root=tmp_path,
            output_dir_name=f"video_to_analysis_bounded_next_sample_execution_{version}",
        )

    payload = approval.run_video_to_analysis_bounded_next_sample_execution_approval(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_bounded_next_sample_execution_approval_v4",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_bounded_next_sample_pool_exhausted"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_plan_refresh"
    assert payload["previouslyExecutedSampleIds"] == [
        "normal_storage_recent_upload",
        "operator_selected_canary_video",
        "soccernet_second_bounded_member",
    ]
