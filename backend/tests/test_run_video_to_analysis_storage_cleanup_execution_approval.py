from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_storage_cleanup_approval as approval
import backend.scripts.run_video_to_analysis_storage_cleanup_dry_run_execution as dry_run
import backend.scripts.run_video_to_analysis_storage_cleanup_execution_approval as execution_approval
from backend.tests.test_run_video_to_analysis_storage_cleanup_approval import (
    _candidate_root,
    _seed_cleanup_map,
    _seed_user_facing_readout,
    _seed_versioned_artifacts,
)


def test_storage_cleanup_execution_approval_approves_only_dry_run_scope_without_deleting(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)
    _seed_cleanup_map(tmp_path, version=147)
    _seed_versioned_artifacts(tmp_path)
    old_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v1"
    latest_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v2"
    approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)
    dry_run.run_video_to_analysis_storage_cleanup_dry_run_execution(storage_root=tmp_path)

    payload = execution_approval.run_video_to_analysis_storage_cleanup_execution_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_storage_cleanup_execution_approval_v1"
    scope = json.loads((output_root / "approved_cleanup_execution_scope.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "cleanup_execution_approval_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["cleanupExecutionApproved"] is True
    assert payload["approvedExecutionMode"] == "bounded_generated_truth_archive_delete"
    assert payload["approvedCandidateCount"] >= 1
    assert payload["approvedCandidateBytes"] > 0
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_bounded_execution"
    assert old_artifact.exists()
    assert latest_artifact.exists()
    assert scope["approvedRunner"] == "backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py"
    assert scope["sourceDryRunDir"] == "video_to_analysis_storage_cleanup_dry_run_execution_v1"
    assert scope["approvedCandidateCount"] == payload["approvedCandidateCount"]
    assert scope["cleanupMutationAllowedInApprovalBatch"] is False
    assert scope["generatedTruthDeleteAllowedInApprovalBatch"] is False
    assert scope["requiresFinalRunnerGuardrailAudit"] is True
    assert guardrail["approvalGuardrailPassed"] is True


def test_storage_cleanup_execution_approval_blocks_without_dry_run(tmp_path: Path) -> None:
    payload = execution_approval.run_video_to_analysis_storage_cleanup_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_dry_run_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_dry_run_execution"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False


def test_storage_cleanup_execution_approval_blocks_empty_scope(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path) / "video_to_analysis_storage_cleanup_dry_run_execution_v1"
    root.mkdir(parents=True)
    (root / "storage_cleanup_dry_run_execution_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "storageCleanupDryRunExecuted": True,
                "cleanupCandidateCount": 0,
                "cleanupCandidateBytes": 0,
                "simulatedDeletedPathCount": 0,
                "actualDeletedPathCount": 0,
                "actualReclaimedBytes": 0,
                "cleanupMutationExecuted": False,
                "generatedTruthDeleteAllowed": False,
            }
        ),
        encoding="utf-8",
    )
    (root / "cleanup_dry_run_report.json").write_text(
        json.dumps(
            {
                "simulatedRows": [],
                "actualDeletedPathCount": 0,
                "actualReclaimedBytes": 0,
                "cleanupMutationExecuted": False,
                "generatedTruthDeleteAllowed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = execution_approval.run_video_to_analysis_storage_cleanup_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_execution_scope_empty"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_dry_run_execution"
