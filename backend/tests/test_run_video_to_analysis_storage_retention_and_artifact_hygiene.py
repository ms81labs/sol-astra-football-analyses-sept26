from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_operational_backlog_prioritization as backlog
import backend.scripts.run_video_to_analysis_promoted_runtime_operational_completion_summary as completion
import backend.scripts.run_video_to_analysis_steady_state_monitoring_cycle as steady_state
import backend.scripts.run_video_to_analysis_storage_retention_and_artifact_hygiene as hygiene
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root, _seed_route


def _seed_operational_backlog(storage_root: Path) -> None:
    _seed_route(storage_root)
    completion.run_video_to_analysis_promoted_runtime_operational_completion_summary(storage_root=storage_root)
    steady_state.run_video_to_analysis_steady_state_monitoring_cycle(storage_root=storage_root)
    backlog.run_video_to_analysis_operational_backlog_prioritization(storage_root=storage_root)


def test_storage_hygiene_writes_retention_policy_and_cleanup_plan_without_deleting(tmp_path: Path) -> None:
    _seed_operational_backlog(tmp_path)
    cache_file = tmp_path / ".pytest_cache" / "stale" / "node.txt"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("cache", encoding="utf-8")
    temp_file = tmp_path / "tmp" / "scratch.bin"
    temp_file.parent.mkdir(parents=True)
    temp_file.write_bytes(b"123456789")

    payload = hygiene.run_video_to_analysis_storage_retention_and_artifact_hygiene(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_storage_retention_and_artifact_hygiene_v1"
    inventory = json.loads((output_root / "storage_artifact_inventory.json").read_text(encoding="utf-8"))
    policy = json.loads((output_root / "artifact_retention_policy.json").read_text(encoding="utf-8"))
    cleanup = json.loads((output_root / "cleanup_candidate_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["storageHygienePlanReady"] is True
    assert payload["artifactInventoryReady"] is True
    assert payload["retentionPolicyReady"] is True
    assert payload["cleanupExecutionReady"] is False
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_dashboard_polish"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert cache_file.exists()
    assert temp_file.exists()
    assert inventory["totalInventoriedBytes"] > 0
    assert policy["retentionClasses"]["generated_truth"]["deleteAllowed"] is False
    assert cleanup["cleanupCandidateCount"] >= 2
    assert cleanup["cleanupMutationExecuted"] is False


def test_storage_hygiene_blocks_without_operational_backlog_truth(tmp_path: Path) -> None:
    payload = hygiene.run_video_to_analysis_storage_retention_and_artifact_hygiene(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_hygiene_operational_backlog_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operational_backlog_prioritization"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
