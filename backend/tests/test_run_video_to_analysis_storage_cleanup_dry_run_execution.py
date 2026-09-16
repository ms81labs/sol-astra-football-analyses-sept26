from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_storage_cleanup_approval as approval
import backend.scripts.run_video_to_analysis_storage_cleanup_dry_run_execution as dry_run
from backend.tests.test_run_video_to_analysis_storage_cleanup_approval import (
    _candidate_root,
    _seed_cleanup_map,
    _seed_user_facing_readout,
    _seed_versioned_artifacts,
)


def test_storage_cleanup_dry_run_simulates_candidates_without_deleting(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)
    _seed_cleanup_map(tmp_path, version=147)
    _seed_versioned_artifacts(tmp_path)
    old_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v1"
    latest_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v2"
    approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)

    payload = dry_run.run_video_to_analysis_storage_cleanup_dry_run_execution(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_storage_cleanup_dry_run_execution_v1"
    plan = json.loads((output_root / "cleanup_dry_run_execution_plan.json").read_text(encoding="utf-8"))
    report = json.loads((output_root / "cleanup_dry_run_report.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["storageCleanupDryRunExecuted"] is True
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["cleanupDeletionReady"] is False
    assert payload["cleanupCandidateCount"] >= 1
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_execution_approval"
    assert old_artifact.exists()
    assert latest_artifact.exists()
    assert plan["executionMode"] == "dry_run_no_deletion"
    assert report["simulatedDeletedPathCount"] == payload["cleanupCandidateCount"]
    assert report["actualDeletedPathCount"] == 0
    assert guardrail["dryRunGuardrailPassed"] is True


def test_storage_cleanup_dry_run_blocks_without_approval(tmp_path: Path) -> None:
    payload = dry_run.run_video_to_analysis_storage_cleanup_dry_run_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_dry_run_approval_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_approval"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
