from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_broader_real_video_acceptance_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_suite_prep(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_broader_real_video_acceptance_suite_prep_v1"
    _write_json(
        root / "broader_real_video_acceptance_suite_prep_summary.json",
        {
            "batchName": "video_to_analysis_broader_real_video_acceptance_suite_prep",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "broaderRealVideoAcceptanceSuiteReady": True,
            "acceptanceCaseCount": 5,
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
            "nextRecommendedNextLever": "video_to_analysis_broader_real_video_acceptance_approval",
        },
    )
    _write_json(
        root / "broader_real_video_acceptance_suite_contract.json",
        {
            "acceptanceScope": "bounded_existing_or_user_supplied_real_videos",
            "executionRequiresApproval": True,
            "acceptanceCases": [{"caseId": f"case_{idx}"} for idx in range(5)],
        },
    )


def test_broader_real_video_acceptance_approval_allows_only_bounded_suite(tmp_path: Path) -> None:
    _seed_suite_prep(tmp_path)

    payload = approval.run_video_to_analysis_broader_real_video_acceptance_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_broader_real_video_acceptance_approval_v1"
    scope = json.loads((output_root / "approved_broader_real_video_acceptance_scope.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["broaderRealVideoAcceptanceApproved"] is True
    assert payload["approvedAcceptanceCaseCount"] == 5
    assert payload["approvedExecutionMode"] == "bounded_existing_or_user_supplied_real_video_acceptance"
    assert payload["normalMatchStorageMutationApproved"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_execution"
    assert scope["normalMatchStorageMutationAllowed"] is True
    assert scope["acceptedCaseCount"] == 5


def test_broader_real_video_acceptance_approval_blocks_without_suite_prep(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_broader_real_video_acceptance_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_broader_real_video_acceptance_suite_prep_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_suite_prep"
