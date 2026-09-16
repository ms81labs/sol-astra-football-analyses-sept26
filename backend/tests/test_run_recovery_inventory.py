from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.scripts.run_recovery_inventory as inventory_module  # noqa: E402
from backend.scripts.run_recovery_inventory import (
    ALLOWED_CLASSIFICATIONS,
    InventoryError,
    build_inventory,
    main,
    run_recovery_inventory,
    write_inventory_output,
)


def _nul(*values: str) -> bytes:
    return b"".join(value.encode("utf-8") + b"\0" for value in values)


def _status(*rows: tuple[str, str]) -> bytes:
    return _nul(*(f"{code} {path}" for code, path in rows))


def _build(
    rows: list[tuple[str, str]],
    *,
    tracked: list[str] | None = None,
    untracked: list[str] | None = None,
    **kwargs: object,
) -> dict[str, object]:
    paths = [path for _, path in rows]
    tracked = tracked if tracked is not None else [path for code, path in rows if code != "??"]
    untracked = untracked if untracked is not None else [path for code, path in rows if code == "??"]
    return build_inventory(
        status_data=_status(*rows),
        path_list_data=_nul(*paths),
        tracked_path_list_data=_nul(*tracked),
        untracked_path_list_data=_nul(*untracked),
        **kwargs,
    )


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_classifies_every_allowed_class_and_uses_manual_review_fallback() -> None:
    rows = [
        (" M", "backend/app/service.py"),
        ("??", "backend/tests/test_service.py"),
        ("??", "backend/scripts/football_chain_common.py"),
        ("??", "backend/scripts/run_one_time_probe.py"),
        ("??", "backend/release/v7.3.json"),
        ("??", "backend/storage/runs/result.json"),
        ("??", "artifacts/best.pt"),
        ("??", ".vscode/settings.json"),
        ("??", "notes/unrecognized.xyz"),
        (" D", "backend/app/retired.py"),
    ]
    payload = _build(
        rows,
        artifact_records={
            "artifacts/best.pt": {
                "identifier": "best-model",
                "sha256": "a" * 64,
                "size": 123,
                "origin": "bounded retrain",
                "retentionClass": "required-local-ignored",
            }
        },
    )

    by_path = {row["path"]: row for row in payload["rows"]}
    assert set(ALLOWED_CLASSIFICATIONS) == {
        "product_source",
        "reusable_workflow",
        "one_shot_batch_entrypoint",
        "essential_release_truth",
        "regenerable_truth",
        "large_local_artifact",
        "editor_or_cache_material",
        "manual_review",
        "tracked_deletion",
    }
    assert {row["classification"] for row in payload["rows"]} == set(ALLOWED_CLASSIFICATIONS)
    assert by_path["notes/unrecognized.xyz"]["disposition"] == "manual_review"
    assert by_path["backend/app/retired.py"]["classification"] == "tracked_deletion"
    assert by_path["backend/app/retired.py"]["disposition"] == "manual_review"


def test_rows_have_required_fields_and_stable_path_order() -> None:
    payload = _build(
        [("??", "z/unknown.xyz"), (" M", "backend/app/a.py")],
        tracked=["backend/app/a.py"],
        untracked=["z/unknown.xyz"],
    )

    assert [row["path"] for row in payload["rows"]] == ["backend/app/a.py", "z/unknown.xyz"]
    for row in payload["rows"]:
        assert set(row) == {
            "path",
            "originalStatus",
            "inferredClassification",
            "classification",
            "classificationOverridden",
            "classificationOverrideReason",
            "disposition",
            "commitGroup",
            "evidence",
            "references",
        }
        assert isinstance(row["evidence"], list)
        assert isinstance(row["references"], list)


def test_deterministic_output_has_no_implicit_timestamp_and_group_manifests(tmp_path: Path) -> None:
    first = _build([("??", "backend/scripts/run_z.py"), (" M", "backend/app/a.py")])
    second = _build([("??", "backend/scripts/run_z.py"), (" M", "backend/app/a.py")])
    assert first == second
    assert "generatedAt" not in first

    one = tmp_path / "one"
    two = tmp_path / "two"
    write_inventory_output(first, one)
    write_inventory_output(second, two)
    assert _snapshot(one) == _snapshot(two)
    assert (one / "inventory.json").read_bytes() == (two / "inventory.json").read_bytes()
    assert (one / "inventory.md").read_bytes() == (two / "inventory.md").read_bytes()
    assert (one / "commit-groups" / "product-source.paths.nul").read_bytes() == _nul(
        "backend/app/a.py"
    )
    assert (one / "commit-groups" / "one-shot-batches.paths.nul").read_bytes() == _nul(
        "backend/scripts/run_z.py"
    )


def test_explicit_timestamp_is_preserved() -> None:
    payload = _build([("??", "notes/unknown.xyz")], generated_at="2026-08-19T00:00:00Z")
    assert payload["generatedAt"] == "2026-08-19T00:00:00Z"


def test_deletion_requires_complete_evidence_before_acceptance() -> None:
    rows = [(" D", "backend/app/old.py")]
    without_evidence = _build(rows)
    incomplete = _build(
        rows,
        deletion_evidence={
            "backend/app/old.py": {"decision": "retirement", "reason": "obsolete"}
        },
    )
    complete = _build(
        rows,
        deletion_evidence={
            "backend/app/old.py": {
                "decision": "replacement",
                "reason": "superseded by new module",
                "replacementPath": "backend/app/new.py",
                "lastReachableBlobId": "1" * 40,
            }
        },
    )

    assert without_evidence["rows"][0]["disposition"] == "manual_review"
    assert incomplete["rows"][0]["disposition"] == "manual_review"
    assert complete["rows"][0]["disposition"] == "accept_deletion"
    assert complete["deletionEvidence"][0]["lastReachableBlobId"] == "1" * 40


def test_rejects_unsafe_deletion_replacement_path() -> None:
    with pytest.raises(InventoryError, match="unsafe path"):
        _build(
            [(" D", "backend/app/old.py")],
            deletion_evidence={
                "backend/app/old.py": {
                    "decision": "replacement",
                    "reason": "claimed replacement",
                    "replacementPath": "../outside.py",
                    "lastReachableBlobId": "1" * 40,
                }
            },
        )


def test_all_fourteen_deletions_get_evidence_records() -> None:
    rows = [(" D", f"backend/app/deleted_{index:02d}.py") for index in range(14)]
    payload = _build(rows)
    assert len(payload["deletionEvidence"]) == 14
    assert all(record["disposition"] == "manual_review" for record in payload["deletionEvidence"])


def test_reconciles_only_one_for_one_collapsed_untracked_directories() -> None:
    payload = build_inventory(
        status_data=_status(("??", ".vscode/"), ("??", "review/"), (" M", "backend/app/a.py")),
        path_list_data=_nul(
            ".vscode/settings.json", "backend/app/a.py", "review/index.html"
        ),
        tracked_path_list_data=_nul("backend/app/a.py"),
        untracked_path_list_data=_nul(".vscode/settings.json", "review/index.html"),
    )
    by_path = {row["path"]: row for row in payload["rows"]}
    assert by_path[".vscode/settings.json"]["originalStatus"] == "??"
    assert by_path["review/index.html"]["originalStatus"] == "??"
    assert payload["reconciliations"] == [
        {"statusPath": ".vscode/", "canonicalPath": ".vscode/settings.json"},
        {"statusPath": "review/", "canonicalPath": "review/index.html"},
    ]


@pytest.mark.parametrize(
    ("status_data", "paths", "tracked", "untracked"),
    [
        (_status(("??", "a/")), ["a/one.py", "a/two.py"], [], ["a/one.py", "a/two.py"]),
        (_status(("??", "a.py")), ["b.py"], [], ["b.py"]),
        (_status(("??", "a.py")), ["a.py", "a.py"], [], ["a.py", "a.py"]),
        (_status(("??", "a.py")), ["a.py"], ["a.py"], ["a.py"]),
    ],
)
def test_rejects_path_list_mismatches_and_duplicates(
    status_data: bytes,
    paths: list[str],
    tracked: list[str],
    untracked: list[str],
) -> None:
    with pytest.raises(InventoryError):
        build_inventory(
            status_data=status_data,
            path_list_data=_nul(*paths),
            tracked_path_list_data=_nul(*tracked),
            untracked_path_list_data=_nul(*untracked),
        )


@pytest.mark.parametrize("bad_path", ["../secret", "/absolute", "a/../../secret", "a\\b"])
def test_rejects_unsafe_paths(bad_path: str) -> None:
    with pytest.raises(InventoryError):
        _build([("??", bad_path)])


def test_rejects_unknown_status_and_invalid_or_disposable_manual_decisions() -> None:
    with pytest.raises(InventoryError, match="status"):
        _build([("ZZ", "a.py")])
    with pytest.raises(InventoryError, match="classification"):
        _build(
            [("??", "a.py")],
            decisions={"a.py": {"classification": "temporary_junk"}},
        )
    with pytest.raises(InventoryError, match="disposable"):
        _build(
            [("??", "a.py")],
            decisions={
                "a.py": {"classification": "manual_review", "disposition": "disposable"}
            },
        )
    with pytest.raises(InventoryError, match="disposable"):
        _build(
            [("??", "a.py")],
            decisions={
                "a.py": {
                    "classification": "editor_or_cache_material",
                    "disposition": "discard",
                    "overrideEvidence": "reviewed as editor material",
                }
            },
        )


@pytest.mark.parametrize(
    "disposition",
    [
        " disposable ",
        "purge",
        "delete",
        "drop",
        "remove",
        "discard",
        "trash",
        "ignore",
        "preserve_commit",
        "unknown_action",
    ],
)
def test_manual_review_rejects_every_action_or_unknown_disposition(disposition: str) -> None:
    with pytest.raises(InventoryError, match="disposition"):
        _build(
            [("??", "notes/unknown.xyz")],
            decisions={"notes/unknown.xyz": {"disposition": disposition}},
        )


def test_dispositions_are_trimmed_and_checked_against_classification_allowlist() -> None:
    manual = _build(
        [("??", "notes/unknown.xyz")],
        decisions={"notes/unknown.xyz": {"disposition": " manual_review "}},
    )
    product = _build(
        [(" M", "backend/app/service.py")],
        decisions={"backend/app/service.py": {"disposition": " preserve_commit "}},
    )
    assert manual["rows"][0]["disposition"] == "manual_review"
    assert product["rows"][0]["disposition"] == "preserve_commit"

    with pytest.raises(InventoryError, match="disposition"):
        _build(
            [(" M", "backend/app/service.py")],
            decisions={"backend/app/service.py": {"disposition": "ship_it"}},
        )


@pytest.mark.parametrize("status", [" M", "??"])
def test_non_deleted_status_cannot_be_classified_as_tracked_deletion(status: str) -> None:
    path = "notes/unknown.xyz"
    with pytest.raises(InventoryError, match="tracked_deletion"):
        _build(
            [(status, path)],
            decisions={"notes/unknown.xyz": {"classification": "tracked_deletion"}},
            deletion_evidence={
                path: {
                    "decision": "retirement",
                    "reason": "not actually a deletion",
                    "lastReachableBlobId": "1" * 40,
                }
            },
        )


def test_accept_deletion_disposition_is_rejected_for_non_deleted_status() -> None:
    with pytest.raises(InventoryError, match="disposition"):
        _build(
            [(" M", "backend/app/service.py")],
            decisions={"backend/app/service.py": {"disposition": "accept_deletion"}},
        )


@pytest.mark.parametrize("status", ["DD", "AU", "UD", "UA", "DU", "AA", "UU"])
def test_unmerged_statuses_are_rejected_at_parse_time(status: str) -> None:
    with pytest.raises(InventoryError, match="unmerged"):
        _build([((status), "backend/app/conflicted.py")])


def test_unmerged_deletion_status_cannot_become_accept_deletion() -> None:
    path = "backend/app/conflicted.py"
    with pytest.raises(InventoryError, match="unmerged"):
        _build(
            [("DD", path)],
            deletion_evidence={
                path: {
                    "decision": "retirement",
                    "reason": "must not accept an unmerged deletion",
                    "lastReachableBlobId": "1" * 40,
                }
            },
        )


def test_ordinary_porcelain_statuses_remain_supported() -> None:
    rows = [
        (" M", "backend/app/worktree_modified.py"),
        ("M ", "backend/app/index_modified.py"),
        ("A ", "backend/app/added.py"),
        (" D", "backend/app/worktree_deleted.py"),
        ("D ", "backend/app/index_deleted.py"),
        ("??", "backend/app/untracked.py"),
    ]
    payload = _build(rows)
    assert {row["originalStatus"] for row in payload["rows"]} == {
        " M",
        "M ",
        "A ",
        " D",
        "D ",
        "??",
    }


def test_classification_override_requires_evidence_and_is_auditable() -> None:
    with pytest.raises(InventoryError, match="override evidence"):
        _build(
            [("??", "notes/reviewed.xyz")],
            decisions={
                "notes/reviewed.xyz": {"classification": "essential_release_truth"}
            },
        )

    payload = _build(
        [("??", "notes/reviewed.xyz")],
        decisions={
            "notes/reviewed.xyz": {
                "classification": "essential_release_truth",
                "overrideEvidence": "reviewed release contract",
            }
        },
    )
    row = payload["rows"][0]
    assert row["inferredClassification"] == "manual_review"
    assert row["classification"] == "essential_release_truth"
    assert row["classificationOverridden"] is True
    assert row["classificationOverrideReason"] == "reviewed release contract"
    assert row["evidence"] == [
        {
            "kind": "inferred_classification_rule",
            "classification": "manual_review",
            "detail": "no unambiguous classification rule matched",
        },
        {
            "kind": "classification_override",
            "from": "manual_review",
            "to": "essential_release_truth",
            "reason": "reviewed release contract",
        },
    ]


def test_unsafe_preserving_to_regenerable_override_is_rejected() -> None:
    with pytest.raises(InventoryError, match="unsafe classification override"):
        _build(
            [(" M", "backend/app/service.py")],
            decisions={
                "backend/app/service.py": {
                    "classification": "regenerable_truth",
                    "overrideEvidence": "claimed generated output",
                }
            },
        )


def test_inapplicable_deletion_and_artifact_evidence_is_rejected() -> None:
    with pytest.raises(InventoryError, match="deletion evidence"):
        _build(
            [(" M", "backend/app/service.py")],
            deletion_evidence={
                "backend/app/service.py": {
                    "decision": "retirement",
                    "reason": "not deleted",
                    "lastReachableBlobId": "1" * 40,
                }
            },
        )
    with pytest.raises(InventoryError, match="artifact record"):
        _build(
            [(" M", "backend/app/service.py")],
            artifact_records={
                "backend/app/service.py": {
                    "identifier": "not-an-artifact",
                    "sha256": "a" * 64,
                    "size": 1,
                    "origin": "invalid",
                    "retentionClass": "none",
                }
            },
        )


def test_input_digests_hash_exact_raw_bytes() -> None:
    status_data = _status(("??", "z/unknown.xyz"), (" M", "backend/app/a.py"))
    path_data = _nul("z/unknown.xyz", "backend/app/a.py")
    tracked_data = _nul("backend/app/a.py")
    untracked_data = _nul("z/unknown.xyz")
    payload = build_inventory(
        status_data=status_data,
        path_list_data=path_data,
        tracked_path_list_data=tracked_data,
        untracked_path_list_data=untracked_data,
    )
    assert payload["inputDigests"] == {
        "statusSha256": hashlib.sha256(status_data).hexdigest(),
        "pathListSha256": hashlib.sha256(path_data).hexdigest(),
        "trackedPathListSha256": hashlib.sha256(tracked_data).hexdigest(),
        "untrackedPathListSha256": hashlib.sha256(untracked_data).hexdigest(),
    }
    assert set(payload["normalizedDigests"]) == {
        "statusSha256",
        "pathListSha256",
        "trackedPathListSha256",
        "untrackedPathListSha256",
    }


def test_reference_relationships_are_emitted_and_attached_to_rows() -> None:
    rows = [
        ("??", "backend/scripts/run_widget.py"),
        ("??", "backend/tests/test_run_widget.py"),
        ("??", "backend/storage/widget/result.json"),
        ("??", "docs/widget.md"),
    ]
    payload = _build(
        rows,
        reference_relationships=[
            {
                "source": "docs/widget.md",
                "target": "backend/storage/widget/result.json",
                "relationship": "documents",
                "evidence": "explicit frozen reference review",
            }
        ],
    )

    assert {
        (row["source"], row["target"], row["relationship"])
        for row in payload["referenceRelationships"]
    } == {
        ("backend/tests/test_run_widget.py", "backend/scripts/run_widget.py", "tests"),
        ("docs/widget.md", "backend/storage/widget/result.json", "documents"),
    }
    by_path = {row["path"]: row for row in payload["rows"]}
    assert "backend/scripts/run_widget.py" in by_path["backend/tests/test_run_widget.py"]["references"]
    assert "backend/storage/widget/result.json" in by_path["docs/widget.md"]["references"]
    markdown = payload["markdown"]
    assert "## Reference relationships" in markdown
    assert "docs/widget.md" in markdown


def test_large_artifact_requires_and_emits_complete_retention_record() -> None:
    with pytest.raises(InventoryError, match="artifact retention"):
        _build([("??", "models/best.pt")])

    payload = _build(
        [("??", "models/best.pt")],
        artifact_records={
            "models/best.pt": {
                "identifier": "model-v1",
                "sha256": "b" * 64,
                "size": 42,
                "origin": "training run 1",
                "retentionClass": "required-local",
            }
        },
    )
    assert payload["artifactRetentionRecords"] == [
        {
            "path": "models/best.pt",
            "identifier": "model-v1",
            "sha256": "b" * 64,
            "size": 42,
            "origin": "training run 1",
            "retentionClass": "required-local",
            "disposition": "retain_external",
        }
    ]


def test_run_is_read_only_for_inputs_and_writes_only_explicit_output(tmp_path: Path) -> None:
    input_root = tmp_path / "freeze"
    input_root.mkdir()
    status = input_root / "status.nul"
    paths = input_root / "paths.nul"
    tracked = input_root / "tracked.nul"
    untracked = input_root / "untracked.nul"
    status.write_bytes(_status((" M", "backend/app/a.py"), ("??", "notes/a.xyz")))
    paths.write_bytes(_nul("backend/app/a.py", "notes/a.xyz"))
    tracked.write_bytes(_nul("backend/app/a.py"))
    untracked.write_bytes(_nul("notes/a.xyz"))
    before = _snapshot(input_root)
    output = tmp_path / "output"

    run_recovery_inventory(
        status_input=status,
        path_list_input=paths,
        tracked_path_list_input=tracked,
        untracked_path_list_input=untracked,
        output_dir=output,
    )

    assert _snapshot(input_root) == before
    assert output.is_dir()
    assert set(path.name for path in tmp_path.iterdir()) == {"freeze", "output"}
    with pytest.raises(InventoryError, match="inside an input archive"):
        run_recovery_inventory(
            status_input=status,
            path_list_input=paths,
            tracked_path_list_input=tracked,
            untracked_path_list_input=untracked,
            output_dir=input_root / "output",
        )


def test_invalid_commit_group_fails_before_creating_output_and_rerun_succeeds(
    tmp_path: Path,
) -> None:
    payload = _build(
        [(" M", "backend/app/a.py")],
        decisions={"backend/app/a.py": {"commitGroup": "a" * 256}},
    )
    output = tmp_path / "output"
    with pytest.raises(InventoryError, match="commit group"):
        write_inventory_output(payload, output)
    assert not output.exists()

    payload["rows"][0]["commitGroup"] = "product-source"
    write_inventory_output(payload, output)
    assert (output / "inventory.json").is_file()


def test_injected_write_failure_leaves_no_partial_target_and_rerun_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _build([(" M", "backend/app/a.py")])
    output = tmp_path / "output"
    original_write_bytes = Path.write_bytes
    writes = 0

    def fail_second_write(path: Path, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("injected write failure")
        return original_write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_second_write)
    with pytest.raises(OSError, match="injected write failure"):
        write_inventory_output(payload, output)
    assert not output.exists()

    monkeypatch.setattr(Path, "write_bytes", original_write_bytes)
    write_inventory_output(payload, output)
    assert (output / "inventory.json").is_file()
    assert (output / "inventory.md").is_file()


def test_injected_rename_failure_restores_empty_target_and_rerun_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _build([(" M", "backend/app/a.py")])
    output = tmp_path / "output"
    output.mkdir()
    original_replace = inventory_module.os.replace
    calls = 0

    def fail_publish(source: object, target: object) -> None:
        nonlocal calls
        calls += 1
        if Path(target) == output:
            raise OSError("injected rename failure")
        original_replace(source, target)

    monkeypatch.setattr(inventory_module.os, "replace", fail_publish)
    with pytest.raises(OSError, match="injected rename failure"):
        write_inventory_output(payload, output)
    assert output.is_dir()
    assert not any(output.iterdir())

    monkeypatch.setattr(inventory_module.os, "replace", original_replace)
    write_inventory_output(payload, output)
    assert (output / "inventory.json").is_file()


def test_nonempty_output_is_preserved_byte_for_byte(tmp_path: Path) -> None:
    payload = _build([(" M", "backend/app/a.py")])
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "existing.txt"
    sentinel.write_bytes(b"preserve me")
    before = _snapshot(output)

    with pytest.raises(InventoryError, match="absent or empty"):
        write_inventory_output(payload, output)
    assert _snapshot(output) == before


def test_cli_requires_all_explicit_frozen_inputs_and_writes_json_metadata(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--output-dir", str(tmp_path / "out")])

    input_root = tmp_path / "freeze"
    input_root.mkdir()
    files = {
        "status": input_root / "status.nul",
        "paths": input_root / "paths.nul",
        "tracked": input_root / "tracked.nul",
        "untracked": input_root / "untracked.nul",
    }
    files["status"].write_bytes(_status(("??", "notes/a.xyz")))
    files["paths"].write_bytes(_nul("notes/a.xyz"))
    files["tracked"].write_bytes(b"")
    files["untracked"].write_bytes(_nul("notes/a.xyz"))
    output = tmp_path / "out"
    assert main(
        [
            "--status-input",
            str(files["status"]),
            "--path-list-input",
            str(files["paths"]),
            "--tracked-path-list-input",
            str(files["tracked"]),
            "--untracked-path-list-input",
            str(files["untracked"]),
            "--output-dir",
            str(output),
            "--generated-at",
            "2026-08-19T00:00:00Z",
        ]
    ) == 0
    payload = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
    assert payload["generatedAt"] == "2026-08-19T00:00:00Z"


def test_real_frozen_inventory_has_audited_counts_and_reconciliations() -> None:
    freeze = REPO_ROOT / "archive" / "2026-08-19-recovery-freeze"
    required = [
        freeze / "original-status.nul",
        freeze / "original-paths.nul",
        freeze / "original-tracked-paths.nul",
        freeze / "original-untracked-paths.nul",
    ]
    if not all(path.is_file() for path in required):
        pytest.skip("raw recovery freeze archive is absent in this clean environment")

    payload = build_inventory(
        status_data=required[0].read_bytes(),
        path_list_data=required[1].read_bytes(),
        tracked_path_list_data=required[2].read_bytes(),
        untracked_path_list_data=required[3].read_bytes(),
    )
    rows = payload["rows"]
    assert len(rows) == 487
    assert sum(row["originalStatus"] == "??" for row in rows) == 443
    assert sum("D" in row["originalStatus"] for row in rows) == 14
    assert sum(
        row["originalStatus"] != "??" and "D" not in row["originalStatus"]
        for row in rows
    ) == 30
    assert payload["inputDigests"]["statusSha256"] == (
        "52ebd23e63300a406eeec36d902b8545262041bb3708e222bee02b8664b8b2fd"
    )
    assert payload["reconciliations"] == [
        {"statusPath": ".vscode/", "canonicalPath": ".vscode/settings.json"},
        {
            "statusPath": "backend/review_ui/football_external_soccernet_detector_miss_review/",
            "canonicalPath": (
                "backend/review_ui/football_external_soccernet_detector_miss_review/index.html"
            ),
        },
    ]
