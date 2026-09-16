from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_operational_readiness as readiness


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_normal_storage_closeout_v1"
    _write_json(
        root / "finish_line_normal_storage_closeout_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_normal_storage_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "normalStorageCloseoutPassed": True,
            "normalStorageProductSmokePassed": True,
            "apiUploadJobSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "normalMatchStorageMutationExecuted": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_operational_readiness",
        },
    )
    _write_json(
        root / "normal_storage_closeout_capability_matrix.json",
        {
            "operationalReadinessReady": True,
            "normalStorageProductSmokePassed": True,
            "apiUploadJobSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "normalMatchStorageMutationExecuted": True,
        },
    )


def test_operational_readiness_writes_runbook_and_completion_next(tmp_path: Path) -> None:
    _seed_closeout(tmp_path)

    payload = readiness.run_video_to_analysis_finish_line_operational_readiness(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_operational_readiness_v1"
    runbook = json.loads((output_root / "finish_line_operator_runbook.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operationalReadinessPassed"] is True
    assert payload["normalStorageProductSmokePassed"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_completion_summary"
    assert runbook["operatorRoute"] == "/video-to-analysis/finish-line"
    assert runbook["apiRoute"] == "/api/video-to-analysis/finish-line"


def test_operational_readiness_blocks_without_closeout(tmp_path: Path) -> None:
    payload = readiness.run_video_to_analysis_finish_line_operational_readiness(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_normal_storage_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_normal_storage_closeout"
