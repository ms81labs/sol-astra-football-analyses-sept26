from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_detector_evaluation_reentry_plan as reentry_plan
import backend.scripts.run_video_to_analysis_detector_evaluation_reentry_approval as reentry_approval
import backend.scripts.run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution as bounded_execution
import backend.scripts.run_video_to_analysis_detector_evaluation_report_binding as report_binding
import backend.scripts.run_video_to_analysis_detector_evaluation_report_route_binding as route_binding
import backend.scripts.run_video_to_analysis_detector_evaluation_lane_closeout as lane_closeout
import backend.scripts.run_video_to_analysis_next_roadmap_direction_snapshot as roadmap_snapshot


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_monitoring_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    monitoring_root = root / "video_to_analysis_post_release_monitoring_closeout_v1"
    _write_json(
        monitoring_root / "post_release_monitoring_closeout_summary.json",
        {
            "batchName": "video_to_analysis_post_release_monitoring_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "postReleaseMonitoringClosed": True,
            "postReleaseMonitoringRouteReady": True,
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
            "nextRecommendedNextLever": "video_to_analysis_detector_evaluation_reentry_plan",
        },
    )
    _write_json(
        monitoring_root / "detector_evaluation_reentry_gate.json",
        {
            "schemaVersion": "video_to_analysis_detector_evaluation_reentry_gate_v1",
            "detectorEvaluationExecutionReady": False,
            "detectorEvaluationReentryPlanReady": True,
            "requiredNextLever": "video_to_analysis_detector_evaluation_reentry_plan",
        },
    )
    _write_json(
        root / "v7_2_bounded_retrain_v1" / "v7_2_bounded_retrain_summary.json",
        {
            "batchName": "v7_2_bounded_retrain",
            "goalAchieved": True,
            "primaryBlocker": None,
            "boundedValPositiveLocalizationHitRate": 0.971014,
            "trainingExecuted": True,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
        },
    )
    _write_json(
        root / "v7_2_crop_probe_precision_guardrail_audit_v1" / "v7_2_crop_probe_precision_guardrail_summary.json",
        {
            "batchName": "v7_2_crop_probe_precision_guardrail_audit",
            "goalAchieved": True,
            "primaryBlocker": None,
            "precisionGuardrailPassed": True,
            "boundedValPositiveLocalizationHitRate": 0.971014,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
        },
    )
    _write_json(
        root / "v7_2_full_pipeline_non_promotion_eval_v1" / "v7_2_full_pipeline_non_promotion_summary.json",
        {
            "batchName": "v7_2_full_pipeline_non_promotion_eval",
            "goalAchieved": True,
            "primaryBlocker": None,
            "sourceFrameLocalizationHitRate": 1.0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
        },
    )


def _seed_plan(storage_root: Path) -> None:
    _seed_monitoring_closeout(storage_root)
    reentry_plan.run_video_to_analysis_detector_evaluation_reentry_plan(storage_root=storage_root)


def _seed_approval(storage_root: Path) -> None:
    _seed_plan(storage_root)
    reentry_approval.run_video_to_analysis_detector_evaluation_reentry_approval(storage_root=storage_root)


def _seed_execution(storage_root: Path) -> None:
    _seed_approval(storage_root)
    bounded_execution.run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution(storage_root=storage_root)


def _seed_report_binding(storage_root: Path) -> None:
    _seed_execution(storage_root)
    report_binding.run_video_to_analysis_detector_evaluation_report_binding(storage_root=storage_root)


def _seed_route_binding(storage_root: Path) -> None:
    _seed_report_binding(storage_root)
    route_binding.run_video_to_analysis_detector_evaluation_report_route_binding(storage_root=storage_root)


def _seed_closeout(storage_root: Path) -> None:
    _seed_route_binding(storage_root)
    lane_closeout.run_video_to_analysis_detector_evaluation_lane_closeout(storage_root=storage_root)


def test_detector_evaluation_reentry_plan_opens_only_bounded_approval(tmp_path: Path) -> None:
    _seed_monitoring_closeout(tmp_path)

    payload = reentry_plan.run_video_to_analysis_detector_evaluation_reentry_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["detectorEvaluationReentryPlanReady"] is True
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_reentry_approval"


def test_detector_evaluation_reentry_approval_approves_bounded_existing_artifacts(tmp_path: Path) -> None:
    _seed_plan(tmp_path)

    payload = reentry_approval.run_video_to_analysis_detector_evaluation_reentry_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["detectorEvaluationApproved"] is True
    assert payload["approvedExecutionMode"] == "bounded_existing_v7_2_artifact_detector_evaluation"
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution"


def test_bounded_existing_artifact_detector_evaluation_executes_without_training(tmp_path: Path) -> None:
    _seed_approval(tmp_path)

    payload = bounded_execution.run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["detectorEvaluationExecuted"] is True
    assert payload["boundedValPositiveLocalizationHitRate"] == 0.971014
    assert payload["sourceFrameLocalizationHitRate"] == 1.0
    assert payload["precisionGuardrailPassed"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_report_binding"


def test_detector_evaluation_report_binding_writes_report_and_route_contract(tmp_path: Path) -> None:
    _seed_execution(tmp_path)

    payload = report_binding.run_video_to_analysis_detector_evaluation_report_binding(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_detector_evaluation_report_binding_v1"
    report = json.loads((output_root / "detector_evaluation_report_view_model.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "detector_evaluation_report_route_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["detectorEvaluationReportReady"] is True
    assert report["schemaVersion"] == "video_to_analysis_detector_evaluation_report_view_model_v1"
    assert contract["apiRoutePath"] == "/api/video-to-analysis/detector-evaluation-report"
    assert contract["htmlRoutePath"] == "/video-to-analysis/detector-evaluation-report"
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_report_route_binding"


def test_detector_evaluation_report_route_binding_serves_api_and_html(tmp_path: Path) -> None:
    _seed_report_binding(tmp_path)

    payload = route_binding.run_video_to_analysis_detector_evaluation_report_route_binding(storage_root=tmp_path)

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/detector-evaluation-report")
            html_response = await client.get("/video-to-analysis/detector-evaluation-report")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["detectorEvaluationReportRouteReady"] is True
    assert api_payload["schemaVersion"] == "video_to_analysis_detector_evaluation_report_view_model_v1"
    assert api_payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert "Detector Evaluation Report" in html
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_detector_evaluation_lane_closeout"


def test_detector_evaluation_lane_closeout_selects_roadmap_direction_snapshot(tmp_path: Path) -> None:
    _seed_route_binding(tmp_path)

    payload = lane_closeout.run_video_to_analysis_detector_evaluation_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["detectorEvaluationLaneClosed"] is True
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_roadmap_direction_snapshot"


def test_next_roadmap_direction_snapshot_selects_promotion_review_design(tmp_path: Path) -> None:
    _seed_closeout(tmp_path)

    payload = roadmap_snapshot.run_video_to_analysis_next_roadmap_direction_snapshot(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["nextRoadmapDirectionSnapshotReady"] is True
    assert payload["selectedNextFamily"] == "video_to_analysis_promotion_review_design"
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_design"


def test_next_roadmap_direction_snapshot_routes_exhausted_source_sampling_to_replenishment(tmp_path: Path) -> None:
    candidate_root = _candidate_root(tmp_path)
    _write_json(
        candidate_root
        / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v14"
        / "real_video_scaleout_source_sampling_expansion_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "roadmapAdvanceAllowed": True,
            "generatedSourceSamplingPoolExhausted": True,
            "expandedScaleoutCandidateCount": 0,
        },
    )

    payload = roadmap_snapshot.run_video_to_analysis_next_roadmap_direction_snapshot(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_next_roadmap_direction_snapshot_v2",
    )

    assert payload["goalAchieved"] is True
    assert payload["nextRoadmapDirectionSnapshotReady"] is True
    assert payload["sourceSamplingPoolExhausted"] is True
    assert payload["selectedNextFamily"] == "video_to_analysis_source_pool_replenishment_plan"
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_pool_replenishment_plan"


def test_next_roadmap_direction_snapshot_carries_active_runtime_when_source_pool_exhausted_after_closeout(
    tmp_path: Path,
) -> None:
    _seed_closeout(tmp_path)
    candidate_root = _candidate_root(tmp_path)
    _write_json(
        candidate_root
        / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v14"
        / "real_video_scaleout_source_sampling_expansion_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "roadmapAdvanceAllowed": True,
            "generatedSourceSamplingPoolExhausted": True,
            "expandedScaleoutCandidateCount": 0,
        },
    )

    payload = roadmap_snapshot.run_video_to_analysis_next_roadmap_direction_snapshot(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["selectedNextFamily"] == "video_to_analysis_source_pool_replenishment_plan"
    assert payload["sourceSamplingPoolExhausted"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_pool_replenishment_plan"


def test_next_roadmap_direction_snapshot_uses_ready_refreshed_scaleout_plan_after_exhaustion(
    tmp_path: Path,
) -> None:
    _seed_closeout(tmp_path)
    candidate_root = _candidate_root(tmp_path)
    _write_json(
        candidate_root
        / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v14"
        / "real_video_scaleout_source_sampling_expansion_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "roadmapAdvanceAllowed": True,
            "generatedSourceSamplingPoolExhausted": True,
            "expandedScaleoutCandidateCount": 0,
        },
    )
    _write_json(
        candidate_root
        / "video_to_analysis_real_video_scaleout_plan_refresh_v15"
        / "real_video_scaleout_plan_refresh_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "availableFreshScaleoutCaseCount": 7,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 5,
            "nextRecommendedNextLever": "video_to_analysis_real_video_scaleout_execution_approval",
        },
    )
    _write_json(
        candidate_root / "video_to_analysis_real_video_scaleout_plan_refresh_v15" / "real_video_scaleout_plan.json",
        {
            "realVideoScaleoutPlanReady": True,
            "availableFreshScaleoutCaseCount": 7,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 5,
        },
    )

    payload = roadmap_snapshot.run_video_to_analysis_next_roadmap_direction_snapshot(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["selectedNextFamily"] == "video_to_analysis_real_video_scaleout_execution_approval"
    assert payload["sourceSamplingPoolExhausted"] is True
    assert payload["readyScaleoutPlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v15"
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_execution_approval"
