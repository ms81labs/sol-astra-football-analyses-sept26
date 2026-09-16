from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_broader_real_video_acceptance_suite_prep as prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_route_polish(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_route_polish_v1"
    _write_json(
        root / "finish_line_route_polish_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_route_polish",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineRoutePolished": True,
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
            "nextRecommendedNextLever": "video_to_analysis_broader_real_video_acceptance_suite_prep",
        },
    )
    _write_json(
        root / "finish_line_route_polish_audit.json",
        {
            "backlogReady": True,
            "bindingReady": True,
            "viewModelUpdated": True,
            "htmlUpdated": True,
            "apiRoutePath": "/api/video-to-analysis/finish-line",
            "htmlRoutePath": "/video-to-analysis/finish-line",
        },
    )


def test_broader_real_video_acceptance_suite_prep_writes_suite_contract(tmp_path: Path) -> None:
    _seed_route_polish(tmp_path)

    payload = prep.run_video_to_analysis_broader_real_video_acceptance_suite_prep(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_broader_real_video_acceptance_suite_prep_v1"
    suite = json.loads((output_root / "broader_real_video_acceptance_suite_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["broaderRealVideoAcceptanceSuiteReady"] is True
    assert payload["acceptanceCaseCount"] == 5
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_approval"
    assert suite["acceptanceScope"] == "bounded_existing_or_user_supplied_real_videos"
    assert len(suite["acceptanceCases"]) == 5


def test_broader_real_video_acceptance_suite_prep_blocks_without_route_polish(tmp_path: Path) -> None:
    payload = prep.run_video_to_analysis_broader_real_video_acceptance_suite_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_route_polish_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_route_polish"
