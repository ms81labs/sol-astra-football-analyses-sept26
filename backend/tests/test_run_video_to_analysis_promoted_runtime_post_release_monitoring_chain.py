from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_promoted_runtime_post_release_monitoring_plan as plan
import backend.scripts.run_video_to_analysis_promoted_runtime_post_release_monitoring_execution as execution
import backend.scripts.run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding as route_binding
import backend.scripts.run_video_to_analysis_promoted_runtime_operational_completion_summary as completion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_route_binding(
    root: Path,
    dir_name: str,
    *,
    view_filename: str,
    contract_filename: str,
    html_filename: str,
    schema_version: str,
    api_route: str,
    html_route: str,
    title: str,
) -> None:
    binding_root = root / dir_name
    _write_json(
        binding_root / view_filename,
        {
            "schemaVersion": schema_version,
            "title": title,
            "subtitle": f"{title} subtitle",
            "scoreboard": [
                {"label": "status", "value": "ready"},
                {"label": "route", "value": api_route},
                {"label": "runtime", "value": "v7.2"},
            ],
        },
    )
    _write_json(
        binding_root / contract_filename,
        {
            "apiRoutePath": api_route,
            "htmlRoutePath": html_route,
        },
    )
    (binding_root / html_filename).write_text(f"<html><body><h1>{title}</h1></body></html>", encoding="utf-8")


def _seed_release_complete(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root / "video_to_analysis_release_completion_summary_v1" / "release_completion_summary.json",
        {
            "batchName": "video_to_analysis_release_completion_summary",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "videoToAnalysisPromotedRuntimeReleaseComplete": True,
            "releasedRuntimeVersion": "v7.2",
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateReadyForEvaluation": False,
            "nextRecommendedNextLever": "video_to_analysis_promoted_runtime_post_release_monitoring_plan",
        },
    )
    _write_json(
        storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
            "runtimeUse": "default_runtime",
            "promotionValidated": True,
            "promotionReady": True,
            "candidateReadyForEvaluation": True,
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
        },
    )
    _seed_route_binding(
        root,
        "video_to_analysis_finish_line_product_binding_v1",
        view_filename="finish_line_product_view_model.json",
        contract_filename="finish_line_product_route_contract.json",
        html_filename="finish_line_product_render_smoke.html",
        schema_version="video_to_analysis_finish_line_product_view_model_v1",
        api_route="/api/video-to-analysis/finish-line",
        html_route="/video-to-analysis/finish-line",
        title="Video To Analysis Finish Line",
    )
    _seed_route_binding(
        root,
        "video_to_analysis_acceptance_report_route_binding_v1",
        view_filename="acceptance_report_view_model.json",
        contract_filename="acceptance_report_route_contract.json",
        html_filename="acceptance_report_render_smoke.html",
        schema_version="video_to_analysis_acceptance_report_view_model_v1",
        api_route="/api/video-to-analysis/acceptance-report",
        html_route="/video-to-analysis/acceptance-report",
        title="Acceptance Report",
    )
    _seed_route_binding(
        root,
        "video_to_analysis_operator_handoff_route_binding_v1",
        view_filename="operator_handoff_view_model.json",
        contract_filename="operator_handoff_bound_route_contract.json",
        html_filename="operator_handoff_render_smoke.html",
        schema_version="video_to_analysis_operator_handoff_view_model_v1",
        api_route="/api/video-to-analysis/operator-handoff",
        html_route="/video-to-analysis/operator-handoff",
        title="Operator Handoff",
    )
    _seed_route_binding(
        root,
        "video_to_analysis_detector_evaluation_report_route_binding_v1",
        view_filename="detector_evaluation_report_view_model.json",
        contract_filename="detector_evaluation_report_bound_route_contract.json",
        html_filename="detector_evaluation_report_render_smoke.html",
        schema_version="video_to_analysis_detector_evaluation_report_view_model_v1",
        api_route="/api/video-to-analysis/detector-evaluation-report",
        html_route="/video-to-analysis/detector-evaluation-report",
        title="Detector Evaluation Report",
    )
    _seed_route_binding(
        root,
        "video_to_analysis_promotion_review_report_route_binding_v1",
        view_filename="promotion_review_report_view_model.json",
        contract_filename="promotion_review_report_bound_route_contract.json",
        html_filename="promotion_review_report_render_smoke.html",
        schema_version="video_to_analysis_promotion_review_report_view_model_v1",
        api_route="/api/video-to-analysis/promotion-review",
        html_route="/video-to-analysis/promotion-review",
        title="Promotion Review",
    )


def _seed_plan(storage_root: Path) -> None:
    _seed_release_complete(storage_root)
    plan.run_video_to_analysis_promoted_runtime_post_release_monitoring_plan(storage_root=storage_root)


def _seed_execution(storage_root: Path) -> None:
    _seed_plan(storage_root)
    execution.run_video_to_analysis_promoted_runtime_post_release_monitoring_execution(storage_root=storage_root)


def _seed_route(storage_root: Path) -> None:
    _seed_execution(storage_root)
    route_binding.run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding(storage_root=storage_root)


def test_promoted_runtime_monitoring_plan_starts_from_release_completion(tmp_path: Path) -> None:
    _seed_release_complete(tmp_path)

    payload = plan.run_video_to_analysis_promoted_runtime_post_release_monitoring_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["promotedRuntimePostReleaseMonitoringPlanReady"] is True
    assert payload["monitoringCheckCount"] == 6
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_post_release_monitoring_execution"


def test_promoted_runtime_monitoring_execution_smokes_registry_and_routes(tmp_path: Path) -> None:
    _seed_plan(tmp_path)

    payload = execution.run_video_to_analysis_promoted_runtime_post_release_monitoring_execution(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_promoted_runtime_post_release_monitoring_execution_v1"
    monitoring_audit = json.loads((output_root / "promoted_runtime_monitoring_execution_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["promotedRuntimePostReleaseMonitoringExecuted"] is True
    assert payload["promotedRuntimeHealthPassed"] is True
    assert payload["routeSmokePassedCount"] == 5
    assert payload["registryMatchesPromotedV7_2DefaultRuntime"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_post_release_monitoring_route_binding"
    assert monitoring_audit["allMonitoringChecksPassed"] is True


def test_promoted_runtime_monitoring_route_binding_serves_report(tmp_path: Path) -> None:
    _seed_execution(tmp_path)

    payload = route_binding.run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding(storage_root=tmp_path)

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/promoted-runtime-monitoring")
            html_response = await client.get("/video-to-analysis/promoted-runtime-monitoring")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["promotedRuntimeMonitoringRouteReady"] is True
    assert api_payload["schemaVersion"] == "video_to_analysis_promoted_runtime_monitoring_view_model_v1"
    assert api_payload["promotedRuntimeHealthPassed"] is True
    assert "Promoted Runtime Monitoring" in html
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_operational_completion_summary"


def test_operational_completion_summary_marks_release_finished(tmp_path: Path) -> None:
    _seed_route(tmp_path)

    payload = completion.run_video_to_analysis_promoted_runtime_operational_completion_summary(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoToAnalysisPromotedRuntimeOperationallyComplete"] is True
    assert payload["releasedRuntimeVersion"] == "v7.2"
    assert payload["steadyStateMonitoringReady"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_steady_state_monitoring_cycle"
