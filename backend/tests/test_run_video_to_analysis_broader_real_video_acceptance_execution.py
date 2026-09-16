from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_broader_real_video_acceptance_execution as execution
from backend.tests.test_run_product_video_to_analysis_smoke import _seed_ready_video_match


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_execution_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    approval_root = root / "video_to_analysis_broader_real_video_acceptance_approval_v1"
    _write_json(
        approval_root / "broader_real_video_acceptance_approval_summary.json",
        {
            "batchName": "video_to_analysis_broader_real_video_acceptance_approval",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "broaderRealVideoAcceptanceApproved": True,
            "approvedAcceptanceCaseCount": 5,
            "approvedExecutionMode": "bounded_existing_or_user_supplied_real_video_acceptance",
            "normalMatchStorageMutationApproved": True,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_broader_real_video_acceptance_execution",
        },
    )
    _write_json(
        approval_root / "approved_broader_real_video_acceptance_scope.json",
        {
            "broaderRealVideoAcceptanceApproved": True,
            "approvedExecutionMode": "bounded_existing_or_user_supplied_real_video_acceptance",
            "acceptedCaseCount": 5,
            "normalMatchStorageMutationAllowed": True,
            "detectorEvaluationAllowed": False,
            "dataDownloadAllowed": False,
            "videoDownloadAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    binding_root = root / "video_to_analysis_finish_line_product_binding_v1"
    _write_json(
        binding_root / "finish_line_product_view_model.json",
        {
            "schemaVersion": "video_to_analysis_finish_line_product_view_model_v1",
            "title": "Video To Analysis Finish Line",
            "subtitle": "Ready",
            "status": "ready_for_product_hardening_acceptance",
            "scoreboard": [{"label": "Route smoke", "value": "passed"}],
        },
    )
    _write_json(
        binding_root / "finish_line_product_route_contract.json",
        {"apiRoutePath": "/api/video-to-analysis/finish-line", "htmlRoutePath": "/video-to-analysis/finish-line"},
    )
    (binding_root / "finish_line_product_render_smoke.html").write_text(
        "<html><body><h1>Video To Analysis Finish Line</h1></body></html>",
        encoding="utf-8",
    )


def test_broader_real_video_acceptance_execution_runs_five_cases(tmp_path: Path) -> None:
    _seed_ready_video_match(tmp_path)
    _seed_execution_inputs(tmp_path)

    payload = execution.run_video_to_analysis_broader_real_video_acceptance_execution(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_broader_real_video_acceptance_execution_v1"
    case_results = json.loads((output_root / "acceptance_case_results.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["broaderRealVideoAcceptanceExecuted"] is True
    assert payload["acceptanceCaseCount"] == 5
    assert payload["acceptancePassedCaseCount"] == 5
    assert payload["normalMatchStorageMutationExecuted"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_closeout"
    assert len(case_results["cases"]) == 5
    assert all(case["passed"] is True for case in case_results["cases"])


def test_broader_real_video_acceptance_execution_blocks_without_approval(tmp_path: Path) -> None:
    payload = execution.run_video_to_analysis_broader_real_video_acceptance_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_broader_real_video_acceptance_approval_missing"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_approval"
