from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_user_acceptance_trial as trial


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_acceptance_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    closeout_root = root / "video_to_analysis_finish_line_product_acceptance_closeout_v1"
    _write_json(
        closeout_root / "finish_line_product_acceptance_closeout_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_product_acceptance_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineProductAcceptanceClosed": True,
            "productRouteAndBundleSmokePassed": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_user_acceptance_trial",
        },
    )
    _write_json(
        closeout_root / "finish_line_product_acceptance_capability_matrix.json",
        {
            "productUserAcceptanceTrialReady": True,
            "productRouteAndBundleSmokePassed": True,
            "normalMatchStorageMutationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    binding_root = root / "video_to_analysis_finish_line_product_binding_v1"
    _write_json(
        binding_root / "finish_line_product_view_model.json",
        {
            "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
            "title": "Video To Analysis Finish Line",
            "subtitle": "Isolated product smoke proved upload, analysis exports, and canonical match bundle output.",
            "scoreboard": [
                {"label": "Product smoke", "value": "passed"},
                {"label": "API upload/export", "value": "True"},
                {"label": "Video bundle export", "value": "True"},
                {"label": "Normal storage mutation", "value": "not executed"},
            ],
            "nextRecommendedNextLever": "video_to_analysis_finish_line_route_implementation",
        },
    )
    _write_json(
        binding_root / "finish_line_product_route_contract.json",
        {
            "apiRoutePath": "/api/video-to-analysis/finish-line",
            "htmlRoutePath": "/video-to-analysis/finish-line",
            "routeImplementationReady": True,
        },
    )
    (binding_root / "finish_line_product_render_smoke.html").write_text(
        "<html><body><h1>Video To Analysis Finish Line</h1><p>Product smoke</p></body></html>",
        encoding="utf-8",
    )


def test_user_acceptance_trial_passes_when_route_payload_is_understandable(tmp_path: Path) -> None:
    _seed_acceptance_inputs(tmp_path)

    payload = trial.run_video_to_analysis_finish_line_user_acceptance_trial(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_user_acceptance_trial_v1"
    checklist = json.loads((output_root / "user_acceptance_checklist.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["userAcceptanceTrialPassed"] is True
    assert payload["normalStorageExecutionApprovalReady"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_normal_storage_execution_approval"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert checklist["allChecklistItemsPassed"] is True


def test_user_acceptance_trial_blocks_without_product_acceptance_closeout(tmp_path: Path) -> None:
    payload = trial.run_video_to_analysis_finish_line_user_acceptance_trial(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_product_acceptance_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_product_acceptance_closeout"
