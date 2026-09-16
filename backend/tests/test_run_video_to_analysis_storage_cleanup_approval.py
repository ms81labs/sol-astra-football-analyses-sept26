from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_storage_cleanup_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_user_facing_readout(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_user_facing_release_readout_v1"
    _write_json(
        root / "user_facing_release_readout_summary.json",
        {
            "batchName": "video_to_analysis_user_facing_release_readout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "userFacingReleaseReadoutReady": True,
            "shareableReadoutPath": "docs/video-to-analysis-user-facing-release-readout-2026-05-09.md",
            "nextRecommendedNextLever": "video_to_analysis_storage_cleanup_approval",
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
            "generatedTruthDeleteAllowed": False,
            "cleanupMutationExecuted": False,
        },
    )


def _seed_cleanup_map(storage_root: Path, version: int = 147) -> None:
    root = _candidate_root(storage_root) / f"video_to_analysis_source_and_artifact_cleanup_map_v{version}"
    _write_json(
        root / "source_and_artifact_cleanup_map_summary.json",
        {
            "batchName": "video_to_analysis_source_and_artifact_cleanup_map",
            "goalAchieved": True,
            "primaryBlocker": None,
            "cleanupMapReady": True,
            "artifactInventoryRowCount": 11,
            "artifactInventoryTotalBytes": 12345,
            "cleanupMutationExecuted": False,
            "generatedTruthDeleteAllowed": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        root / "source_and_artifact_cleanup_map.json",
        {
            "cleanupMapReady": True,
            "cleanupMutationExecuted": False,
            "generatedTruthDeleteAllowed": False,
            "artifactInventoryRowCount": 11,
            "artifactInventoryTotalBytes": 12345,
            "artifactInventory": [
                {
                    "artifactDir": "video_to_analysis_source_and_artifact_cleanup_map_v146",
                    "fileCount": 2,
                    "totalBytes": 100,
                    "cleanupClass": "generated_truth_preserve",
                }
            ],
        },
    )


def _seed_versioned_artifacts(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    for name in [
        "video_to_analysis_bounded_next_sample_execution_v1",
        "video_to_analysis_bounded_next_sample_execution_v2",
        "video_to_analysis_next_sample_selection_snapshot_v38",
    ]:
        artifact = root / name / "artifact.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"ok": true}\n', encoding="utf-8")


def test_storage_cleanup_approval_writes_plan_without_deleting_generated_truth(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)
    _seed_cleanup_map(tmp_path, version=147)
    _seed_versioned_artifacts(tmp_path)
    old_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v1"
    latest_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v2"

    payload = approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_storage_cleanup_approval_v1"
    contract = json.loads((output_root / "storage_cleanup_approval_contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "cleanup_candidate_manifest.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["storageCleanupApprovalReady"] is True
    assert payload["storageCleanupDryRunApproved"] is True
    assert payload["cleanupExecutionApproved"] is False
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_dry_run_execution"
    assert old_artifact.exists()
    assert latest_artifact.exists()
    assert contract["cleanupExecutionApproved"] is False
    assert contract["approvedNextAction"] == "dry_run_only_no_deletion"
    assert manifest["cleanupCandidateCount"] >= 1
    assert any(row["relativePath"].endswith("_v1") for row in manifest["cleanupCandidateRows"])
    assert guardrail["approvalGuardrailPassed"] is True


def test_storage_cleanup_approval_blocks_without_user_facing_readout(tmp_path: Path) -> None:
    _seed_cleanup_map(tmp_path, version=147)

    payload = approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_release_readout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_user_facing_release_readout"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_storage_cleanup_approval_blocks_without_cleanup_map_inventory(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)

    payload = approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_inventory_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_and_artifact_cleanup_map"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
