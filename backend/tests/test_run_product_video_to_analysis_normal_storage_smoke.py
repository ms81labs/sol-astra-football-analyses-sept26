from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_product_video_to_analysis_normal_storage_smoke as smoke
from backend.tests.test_run_product_video_to_analysis_smoke import _seed_ready_video_match


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_normal_storage_approval(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_normal_storage_execution_approval_v1"
    _write_json(
        root / "finish_line_normal_storage_execution_approval_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_normal_storage_execution_approval",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "normalStorageExecutionApproved": True,
            "approvedExecutionMode": "controlled_product_video_to_analysis_normal_storage_smoke",
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
            "nextRecommendedNextLever": "product_video_to_analysis_normal_storage_smoke",
        },
    )
    _write_json(
        root / "approved_normal_storage_execution_scope.json",
        {
            "normalStorageExecutionApproved": True,
            "approvedExecutionMode": "controlled_product_video_to_analysis_normal_storage_smoke",
            "normalMatchStorageMutationAllowed": True,
            "allowedRunner": "backend/scripts/run_product_video_to_analysis_smoke.py",
            "detectorEvaluationAllowed": False,
            "dataDownloadAllowed": False,
            "videoDownloadAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )


def test_normal_storage_smoke_runs_existing_product_smoke_after_approval(tmp_path: Path) -> None:
    _seed_ready_video_match(tmp_path)
    _seed_normal_storage_approval(tmp_path)

    payload = smoke.run_product_video_to_analysis_normal_storage_smoke(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "product_video_to_analysis_normal_storage_smoke_v1"
    nested = json.loads((output_root / "normal_storage_product_smoke_summary.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["normalStorageProductSmokePassed"] is True
    assert payload["apiUploadJobSmokePassed"] is True
    assert payload["existingVideoBundleSmokePassed"] is True
    assert payload["normalMatchStorageMutationExecuted"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_normal_storage_closeout"
    assert nested["goalAchieved"] is True


def test_normal_storage_smoke_blocks_without_approval(tmp_path: Path) -> None:
    payload = smoke.run_product_video_to_analysis_normal_storage_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_normal_storage_execution_approval_missing"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_normal_storage_execution_approval"
