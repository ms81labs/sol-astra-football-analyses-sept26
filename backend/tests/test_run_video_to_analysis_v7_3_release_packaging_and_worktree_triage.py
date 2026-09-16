from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_v7_3_release_packaging_and_worktree_triage as triage


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_manual_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_manual_operator_release_decision_v1"
    _write_json(
        root / "manual_operator_release_decision_summary.json",
        {
            "batchName": "video_to_analysis_manual_operator_release_decision",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "selectedOperatorDecision": "declare_current_milestone_done",
            "v7_3CurrentMilestoneDeclaredDone": True,
            "optionalCoverageLoopDeferred": True,
            "releasedRuntimeVersion": "v7.3",
            "activeRuntimeDefaultVersion": "v7.3",
            "nextRecommendedNextLever": "video_to_analysis_current_milestone_done",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "cleanupDeletionExecuted": False,
        },
    )


def test_release_packaging_triage_classifies_dirty_worktree_without_gpu_actions(tmp_path: Path) -> None:
    _seed_manual_closeout(tmp_path)

    payload = triage.run_video_to_analysis_v7_3_release_packaging_and_worktree_triage(
        storage_root=tmp_path,
        git_status_lines=[
            " M backend/app/main.py",
            "?? backend/scripts/run_video_to_analysis_manual_operator_release_decision.py",
            "?? backend/tests/test_run_video_to_analysis_manual_operator_release_decision.py",
            "?? docs/project-review-2026-07-06.md",
            " D backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_old/artifact.json",
            "?? backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/generated_batch/file.json",
        ],
        large_artifact_rows=[
            {
                "path": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/external/big.json",
                "sizeBytes": 2_500_000_000,
            }
        ],
        disk_info={"freeBytes": 65_000_000_000, "usedPercent": 56},
    )

    output_root = _candidate_root(tmp_path) / "video_to_analysis_v7_3_release_packaging_and_worktree_triage_v1"
    worktree = json.loads((output_root / "worktree_classification.json").read_text(encoding="utf-8"))
    packaging = json.loads((output_root / "release_packaging_plan.json").read_text(encoding="utf-8"))
    no_gpu = json.loads((output_root / "no_gpu_readiness_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["v7_3CurrentMilestoneDeclaredDone"] is True
    assert payload["worktreeTriageReady"] is True
    assert payload["totalDirtyPathCount"] == 6
    assert payload["sourceOrTestCandidateCount"] == 4
    assert payload["generatedTruthCandidateCount"] == 2
    assert payload["deletedTrackedPathCount"] == 1
    assert payload["largeArtifactCount"] == 1
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["gpuRequired"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_v7_3_release_packaging_commit_plan"

    assert worktree["statusCounts"]["modified"] == 1
    assert worktree["statusCounts"]["untracked"] == 4
    assert worktree["statusCounts"]["deleted"] == 1
    assert packaging["recommendedCommitGroups"][0]["id"] == "source_tests_docs"
    assert no_gpu["noGpuRequiredForPackaging"] is True
    assert no_gpu["runPodPodsExpected"] == []


def test_release_packaging_triage_blocks_without_manual_closeout(tmp_path: Path) -> None:
    payload = triage.run_video_to_analysis_v7_3_release_packaging_and_worktree_triage(
        storage_root=tmp_path,
        git_status_lines=[],
        large_artifact_rows=[],
        disk_info={"freeBytes": 1, "usedPercent": 1},
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_v7_3_release_packaging_manual_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_manual_operator_release_decision"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
