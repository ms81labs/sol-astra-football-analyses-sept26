from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_normal_storage_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_user_acceptance_trial(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_user_acceptance_trial_v1"
    _write_json(
        root / "finish_line_user_acceptance_trial_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_user_acceptance_trial",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "userAcceptanceTrialPassed": True,
            "normalStorageExecutionApprovalReady": True,
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
            "nextRecommendedNextLever": "video_to_analysis_finish_line_normal_storage_execution_approval",
        },
    )
    _write_json(
        root / "user_acceptance_checklist.json",
        {
            "allChecklistItemsPassed": True,
            "checks": {
                "productAcceptanceCloseoutReady": True,
                "routeTrialPassed": True,
                "normalMatchStorageMutationStillBlocked": True,
                "trainingStillBlocked": True,
                "promotionStillBlocked": True,
                "runtimeDefaultMutationStillBlocked": True,
            },
        },
    )


def test_normal_storage_execution_approval_allows_only_controlled_product_smoke(tmp_path: Path) -> None:
    _seed_user_acceptance_trial(tmp_path)

    payload = approval.run_video_to_analysis_finish_line_normal_storage_execution_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_normal_storage_execution_approval_v1"
    scope = json.loads((output_root / "approved_normal_storage_execution_scope.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["normalStorageExecutionApproved"] is True
    assert payload["approvedExecutionMode"] == "controlled_product_video_to_analysis_normal_storage_smoke"
    assert payload["normalMatchStorageMutationApproved"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_normal_storage_smoke"
    assert scope["normalMatchStorageMutationAllowed"] is True
    assert scope["allowedRunner"] == "backend/scripts/run_product_video_to_analysis_smoke.py"


def test_normal_storage_execution_approval_blocks_without_user_acceptance(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_finish_line_normal_storage_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_user_acceptance_trial_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_user_acceptance_trial"
