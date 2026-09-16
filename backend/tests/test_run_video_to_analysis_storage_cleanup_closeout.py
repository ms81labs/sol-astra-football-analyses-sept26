from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_storage_cleanup_approval as approval
import backend.scripts.run_video_to_analysis_storage_cleanup_bounded_execution as bounded
import backend.scripts.run_video_to_analysis_storage_cleanup_closeout as closeout
import backend.scripts.run_video_to_analysis_storage_cleanup_dry_run_execution as dry_run
import backend.scripts.run_video_to_analysis_storage_cleanup_execution_approval as execution_approval
from backend.tests.test_run_video_to_analysis_storage_cleanup_approval import (
    _candidate_root,
    _seed_cleanup_map,
    _seed_user_facing_readout,
    _seed_versioned_artifacts,
)


def test_storage_cleanup_closeout_blocks_when_automatic_deletion_is_disabled(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)
    _seed_cleanup_map(tmp_path, version=147)
    _seed_versioned_artifacts(tmp_path)
    approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)
    dry_run.run_video_to_analysis_storage_cleanup_dry_run_execution(storage_root=tmp_path)
    execution_approval.run_video_to_analysis_storage_cleanup_execution_approval(storage_root=tmp_path)
    bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    payload = closeout.run_video_to_analysis_storage_cleanup_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_bounded_execution_gap"
    assert payload["storageCleanupCloseoutReady"] is False
    assert payload["actualDeletedPathCount"] == 0
    assert payload["actualReclaimedBytes"] == 0
    assert (_candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v1").exists()
    assert payload["latestVersionDeletionBlockedCount"] == 0
    assert payload["pathGuardrailFailureCount"] == 0
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_bounded_scope_repair"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_storage_cleanup_closeout_blocks_without_bounded_execution(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_storage_cleanup_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_bounded_execution_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_bounded_execution"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
