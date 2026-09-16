from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_normal_storage_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_normal_storage_smoke(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "product_video_to_analysis_normal_storage_smoke_v1"
    _write_json(
        root / "product_video_to_analysis_normal_storage_smoke_summary.json",
        {
            "batchName": "product_video_to_analysis_normal_storage_smoke",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
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
            "nextRecommendedNextLever": "video_to_analysis_finish_line_normal_storage_closeout",
        },
    )
    _write_json(
        root / "normal_storage_execution_audit.json",
        {
            "approvalReady": True,
            "normalStorageProductSmokePassed": True,
            "apiUploadJobSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "normalMatchStorageMutationExecuted": True,
        },
    )


def test_normal_storage_closeout_advances_to_operational_readiness(tmp_path: Path) -> None:
    _seed_normal_storage_smoke(tmp_path)

    payload = closeout.run_video_to_analysis_finish_line_normal_storage_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_normal_storage_closeout_v1"
    capability = json.loads((output_root / "normal_storage_closeout_capability_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["normalStorageCloseoutPassed"] is True
    assert payload["normalStorageProductSmokePassed"] is True
    assert payload["normalMatchStorageMutationExecuted"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_operational_readiness"
    assert capability["operationalReadinessReady"] is True


def test_normal_storage_closeout_blocks_without_smoke(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_finish_line_normal_storage_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "product_video_to_analysis_normal_storage_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_normal_storage_smoke"
