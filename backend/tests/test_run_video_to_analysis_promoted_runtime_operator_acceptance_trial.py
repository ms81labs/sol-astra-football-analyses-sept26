from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_promoted_runtime_operator_acceptance_trial as trial


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
            "promotionReviewPassed": True,
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


def _seed_promoted_runtime_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root / "video_to_analysis_promotion_review_closeout_v1" / "promotion_review_closeout_summary.json",
        {
            "batchName": "video_to_analysis_promotion_review_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "promotionReviewClosed": True,
            "promotionReviewPassed": True,
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateReadyForEvaluation": False,
            "nextRecommendedNextLever": "video_to_analysis_promoted_runtime_operator_acceptance_trial",
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


def test_promoted_runtime_operator_acceptance_trial_passes_from_registry_and_routes(tmp_path: Path) -> None:
    _seed_promoted_runtime_inputs(tmp_path)

    payload = trial.run_video_to_analysis_promoted_runtime_operator_acceptance_trial(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_promoted_runtime_operator_acceptance_trial_v1"
    route_audit = json.loads((output_root / "operator_visible_route_smoke_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["promotedRuntimeOperatorAcceptancePassed"] is True
    assert payload["registryMatchesPromotedV7_2DefaultRuntime"] is True
    assert payload["operatorVisibleRouteSmokePassed"] is True
    assert payload["routeSmokePassedCount"] == 5
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_release_closeout"
    assert all(row["apiRouteStatusCode"] == 200 and row["htmlRouteStatusCode"] == 200 for row in route_audit["routeSmokes"])


def test_promoted_runtime_operator_acceptance_trial_blocks_without_promotion_closeout(tmp_path: Path) -> None:
    payload = trial.run_video_to_analysis_promoted_runtime_operator_acceptance_trial(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_promotion_review_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_closeout"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
