from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest

import backend.scripts.run_video_to_analysis_storage_cleanup_approval as approval
import backend.scripts.run_video_to_analysis_storage_cleanup_bounded_execution as bounded
import backend.scripts.run_video_to_analysis_storage_cleanup_dry_run_execution as dry_run
import backend.scripts.run_video_to_analysis_storage_cleanup_execution_approval as execution_approval
from backend.tests.test_run_video_to_analysis_storage_cleanup_approval import (
    _candidate_root,
    _seed_cleanup_map,
    _seed_user_facing_readout,
    _seed_versioned_artifacts,
)


def _write_execution_approval(root: Path, rows: list[object]) -> None:
    approval_root = root / "video_to_analysis_storage_cleanup_execution_approval_v1"
    approval_root.mkdir(parents=True, exist_ok=True)
    (approval_root / "storage_cleanup_execution_approval_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "cleanupExecutionApproved": True,
                "approvedExecutionMode": "bounded_generated_truth_archive_delete",
                "cleanupMutationExecuted": False,
                "generatedTruthDeleteAllowed": False,
            }
        ),
        encoding="utf-8",
    )
    (approval_root / "approved_cleanup_execution_scope.json").write_text(
        json.dumps(
            {
                "cleanupExecutionApproved": True,
                "approvedExecutionMode": "bounded_generated_truth_archive_delete",
                "approvedCandidateRows": rows,
                "cleanupMutationAllowedInApprovalBatch": False,
                "generatedTruthDeleteAllowedInApprovalBatch": False,
                "requiresFinalRunnerGuardrailAudit": True,
            }
        ),
        encoding="utf-8",
    )


def _approved_row(relative_path: str, action: str = "delete_or_archive_generated_truth_candidate") -> dict[str, object]:
    return {"relativePath": relative_path, "approvedAction": action, "approvedBytes": 4}


def _assert_cleanup_blocked(payload: dict[str, object]) -> None:
    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_path_guardrail"
    assert payload["actualDeletedPathCount"] == 0
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False


@pytest.mark.parametrize("relative_path", [".", "family_v2/keep.txt"])
def test_cleanup_rejects_root_and_latest_descendant(tmp_path: Path, relative_path: str) -> None:
    root = _candidate_root(tmp_path)
    latest = root / "family_v2"
    latest.mkdir(parents=True)
    root_sentinel = root / "keep-root.txt"
    latest_sentinel = latest / "keep.txt"
    root_sentinel.write_text("keep", encoding="utf-8")
    latest_sentinel.write_text("keep", encoding="utf-8")
    _write_execution_approval(root, [_approved_row(relative_path)])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert root_sentinel.read_text(encoding="utf-8") == "keep"
    assert latest_sentinel.read_text(encoding="utf-8") == "keep"
    _assert_cleanup_blocked(payload)


@pytest.mark.parametrize(
    ("relative_path", "action", "target_kind"),
    [
        ("family_v1", "keep", "directory"),
        ("unversioned", "delete_or_archive_generated_truth_candidate", "directory"),
        ("unversioned.txt", "delete_or_archive_generated_truth_candidate", "file"),
    ],
)
def test_cleanup_rejects_wrong_action_and_nonversioned_target(
    tmp_path: Path,
    relative_path: str,
    action: str,
    target_kind: str,
) -> None:
    root = _candidate_root(tmp_path)
    (root / "family_v2").mkdir(parents=True)
    target = root / relative_path
    if target_kind == "directory":
        target.mkdir()
        sentinel = target / "keep.txt"
    else:
        sentinel = target
    sentinel.write_text("keep", encoding="utf-8")
    _write_execution_approval(root, [_approved_row(relative_path, action)])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "keep"
    _assert_cleanup_blocked(payload)


@pytest.mark.parametrize("case", ["absolute", "parent_alias", "nested", "duplicate", "dot_alias"])
def test_cleanup_rejects_noncanonical_and_duplicate_target_aliases(tmp_path: Path, case: str) -> None:
    root = _candidate_root(tmp_path)
    old = root / "family_v1"
    old.mkdir(parents=True)
    (root / "family_v2").mkdir()
    sentinel = old / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    child = old / "child"
    child.mkdir()
    (child / "keep.txt").write_text("keep", encoding="utf-8")
    paths = {
        "absolute": [str(old)],
        "parent_alias": ["holder/../family_v1"],
        "nested": ["family_v1/child"],
        "duplicate": ["family_v1", "family_v1"],
        "dot_alias": ["family_v1", "./family_v1"],
    }[case]
    _write_execution_approval(root, [_approved_row(path) for path in paths])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (child / "keep.txt").read_text(encoding="utf-8") == "keep"
    _assert_cleanup_blocked(payload)


def test_cleanup_rejects_symlink_target(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path)
    referent = root / "target_v1"
    referent.mkdir(parents=True)
    (root / "target_v2").mkdir()
    (root / "alias_v2").mkdir()
    sentinel = referent / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    link = root / "alias_v1"
    link.symlink_to(referent, target_is_directory=True)
    _write_execution_approval(root, [_approved_row(link.name)])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert link.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"
    _assert_cleanup_blocked(payload)


def test_cleanup_ancestor_swap_preserves_outside_sentinel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stable_parent = tmp_path / "stable"
    root = _candidate_root(stable_parent)
    (root / "family_v1").mkdir(parents=True)
    (root / "family_v2").mkdir()
    (root / "family_v1" / "keep.txt").write_text("approved")
    _write_execution_approval(root, [_approved_row("family_v1")])
    outside = tmp_path / "outside"
    outside_old = _candidate_root(outside) / "family_v1"
    outside_old.mkdir(parents=True)
    (outside_old / "keep.txt").write_text("outside")
    moved_parent = tmp_path / "moved"
    real_validate = bounded._validated_targets

    def swap_then_validate(root_fd, rows, output_name):
        stable_parent.rename(moved_parent)
        stable_parent.symlink_to(outside, target_is_directory=True)
        return real_validate(root_fd, rows, output_name)

    monkeypatch.setattr(bounded, "_validated_targets", swap_then_validate)
    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=stable_parent)

    assert payload["goalAchieved"] is False
    assert payload["actualDeletedPathCount"] == 0
    assert (outside_old / "keep.txt").read_text() == "outside"
    assert (_candidate_root(moved_parent) / "family_v1" / "keep.txt").read_text() == "approved"


@pytest.mark.parametrize("bad_row", [None, "family_v1", [], {}, {"relativePath": "family_v1", "approvedBytes": "bad"}])
def test_cleanup_malformed_row_blocks_entire_batch(tmp_path: Path, bad_row: object) -> None:
    root = _candidate_root(tmp_path)
    (root / "family_v1").mkdir(parents=True)
    (root / "family_v2").mkdir()
    sentinel = root / "family_v1" / "keep.txt"
    sentinel.write_text("keep")
    _write_execution_approval(root, [_approved_row("family_v1"), bad_row])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    _assert_cleanup_blocked(payload)
    assert sentinel.read_text() == "keep"


def test_cleanup_protects_tied_maximum_versions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _candidate_root(tmp_path)
    for name in ["family_v1", "family_v01"]:
        (root / name).mkdir(parents=True)
        (root / name / "keep.txt").write_text("keep")
    _write_execution_approval(root, [_approved_row("family_v01")])
    real_listdir = os.listdir
    monkeypatch.setattr(bounded.os, "listdir", lambda path: sorted(real_listdir(path), reverse=True))

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["actualDeletedPathCount"] == 0
    for name in ["family_v1", "family_v01"]:
        assert (root / name / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize("output_name", [bounded.DEFAULT_OUTPUT_DIR_NAME, "reports_v1"])
def test_cleanup_rejects_own_report_directory(tmp_path: Path, output_name: str) -> None:
    root = _candidate_root(tmp_path)
    (root / output_name).mkdir(parents=True)
    (root / output_name.replace("_v1", "_v2")).mkdir()
    sentinel = root / output_name / "keep.txt"
    sentinel.write_text("keep")
    _write_execution_approval(root, [_approved_row(output_name)])

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(
        storage_root=tmp_path, output_dir_name=output_name,
    )

    _assert_cleanup_blocked(payload)
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("change", ["replacement", "missing", "newest_removed", "scan_error"])
def test_cleanup_retains_batch_when_targets_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    root = _candidate_root(tmp_path)
    for name in ["first_v1", "first_v2", "last_v1", "last_v2"]:
        (root / name).mkdir(parents=True)
        (root / name / "keep.txt").write_text(name)
    _write_execution_approval(root, [_approved_row("first_v1"), _approved_row("last_v1")])
    real_validate = bounded._validated_targets

    def change_then_return(root_fd, rows, output_name):
        result = real_validate(root_fd, rows, output_name)
        if change in {"replacement", "missing"}:
            (root / "last_v1").rename(root / "saved-last")
            if change == "replacement":
                (root / "last_v1").mkdir()
                (root / "last_v1" / "replacement.txt").write_text("unapproved")
        elif change == "newest_removed":
            shutil.rmtree(root / "last_v2")
        else:
            raise OSError("scan failed")
        return result

    monkeypatch.setattr(bounded, "_validated_targets", change_then_return)
    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["actualDeletedPathCount"] == 0
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert (root / "first_v1" / "keep.txt").read_text() == "first_v1"
    last_location = "saved-last" if change in {"replacement", "missing"} else "last_v1"
    assert (root / last_location / "keep.txt").read_text() == "last_v1"
    if change == "replacement":
        assert (root / "last_v1" / "replacement.txt").read_text() == "unapproved"


def test_storage_cleanup_bounded_execution_retains_approved_old_versions(tmp_path: Path) -> None:
    _seed_user_facing_readout(tmp_path)
    _seed_cleanup_map(tmp_path, version=147)
    _seed_versioned_artifacts(tmp_path)
    old_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v1"
    latest_artifact = _candidate_root(tmp_path) / "video_to_analysis_bounded_next_sample_execution_v2"
    approval.run_video_to_analysis_storage_cleanup_approval(storage_root=tmp_path)
    dry_run.run_video_to_analysis_storage_cleanup_dry_run_execution(storage_root=tmp_path)
    execution_approval.run_video_to_analysis_storage_cleanup_execution_approval(storage_root=tmp_path)

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_storage_cleanup_bounded_execution_v1"
    execution_report = json.loads((output_root / "cleanup_bounded_execution_report.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "cleanup_bounded_execution_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_automatic_deletion_disabled"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
    assert payload["actualDeletedPathCount"] == 0
    assert payload["actualReclaimedBytes"] == 0
    assert payload["approvedCandidateCount"] >= 1
    assert payload["validatedTargetCount"] >= 1
    assert old_artifact.exists()
    assert latest_artifact.exists()
    assert execution_report["latestVersionDeletionBlockedCount"] == 0
    assert guardrail["automaticDeletionEnabled"] is False
    assert guardrail["boundedExecutionGuardrailPassed"] is False


def test_storage_cleanup_bounded_execution_blocks_without_execution_approval(tmp_path: Path) -> None:
    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_execution_approval_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_cleanup_execution_approval"
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False


def test_storage_cleanup_bounded_execution_blocks_latest_version_deletion(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path)
    latest = root / "video_to_analysis_bounded_next_sample_execution_v2"
    latest.mkdir(parents=True)
    (latest / "artifact.json").write_text('{"ok": true}\n', encoding="utf-8")
    approval_root = root / "video_to_analysis_storage_cleanup_execution_approval_v1"
    approval_root.mkdir(parents=True)
    (approval_root / "storage_cleanup_execution_approval_summary.json").write_text(
        json.dumps(
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "cleanupExecutionApproved": True,
                "approvedExecutionMode": "bounded_generated_truth_archive_delete",
                "approvedCandidateCount": 1,
                "approvedCandidateBytes": 12,
                "cleanupMutationExecuted": False,
                "generatedTruthDeleteAllowed": False,
            }
        ),
        encoding="utf-8",
    )
    (approval_root / "approved_cleanup_execution_scope.json").write_text(
        json.dumps(
            {
                "cleanupExecutionApproved": True,
                "approvedExecutionMode": "bounded_generated_truth_archive_delete",
                "approvedCandidateRows": [
                    {
                        "relativePath": "video_to_analysis_bounded_next_sample_execution_v2",
                        "approvedAction": "delete_or_archive_generated_truth_candidate",
                        "approvedBytes": 12,
                    }
                ],
                "cleanupMutationAllowedInApprovalBatch": False,
                "generatedTruthDeleteAllowedInApprovalBatch": False,
                "requiresFinalRunnerGuardrailAudit": True,
            }
        ),
        encoding="utf-8",
    )

    payload = bounded.run_video_to_analysis_storage_cleanup_bounded_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_storage_cleanup_latest_version_guardrail"
    assert latest.exists()
    assert payload["cleanupMutationExecuted"] is False
    assert payload["generatedTruthDeleteAllowed"] is False
