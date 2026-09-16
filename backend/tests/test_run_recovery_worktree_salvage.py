from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.scripts.run_recovery_worktree_salvage as salvage_module  # noqa: E402
from backend.scripts.run_recovery_worktree_salvage import (  # noqa: E402
    OUTPUT_FILENAMES,
    SalvageError,
    _validate_repo_path,
    main,
    run_recovery_worktree_salvage,
)


def _git(cwd: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def _write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mode is not None:
        path.chmod(mode)


@pytest.fixture
def worktrees(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Salvage Tests")
    _write(root / "binary.dat", b"base\x00binary\xff")
    _write(root / "integrated.txt", b"base\n")
    _write(root / "deleted.txt", b"meaningful deletion\n")
    _write(root / ".venv" / "package.bin", b"ENV-BLOB\x00\xff-SHOULD-NOT-BE-IN-PATCH")
    _write(root / "backend" / "venv" / "nested.bin", b"nested env")
    _write(root / "web" / "node_modules" / "package.js", b"dependency")
    _write(root / "script.sh", b"#!/bin/sh\nexit 0\n", 0o644)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    source = tmp_path / "paused"
    _git(root, "worktree", "add", "-b", "paused", str(source), "HEAD")
    return root, source


def _snapshot_source(source: Path) -> dict[str, object]:
    git_dir = Path(_git(source, "rev-parse", "--absolute-git-dir").decode().strip())
    index = git_dir / "index"
    paths: dict[str, tuple[str, int, str]] = {}
    status = _git(source, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    for raw in status[:-1].split(b"\0") if status else []:
        path = raw[3:].decode("utf-8")
        candidate = source / path
        if not candidate.exists() and not candidate.is_symlink():
            paths[path] = ("missing", 0, "")
        elif candidate.is_symlink():
            target = os.readlink(candidate).encode("utf-8")
            paths[path] = (
                "symlink",
                stat.S_IMODE(candidate.lstat().st_mode),
                hashlib.sha256(target).hexdigest(),
            )
        else:
            paths[path] = (
                "regular",
                stat.S_IMODE(candidate.stat().st_mode),
                hashlib.sha256(candidate.read_bytes()).hexdigest(),
            )
    return {
        "head": _git(source, "rev-parse", "HEAD"),
        "status": status,
        "index": hashlib.sha256(index.read_bytes()).hexdigest(),
        "paths": paths,
    }


def _dirty_success_fixture(root: Path, source: Path) -> bytes:
    binary = bytes(range(256)) + b"\x00\xffnew binary payload"
    _write(source / "binary.dat", binary)
    _write(source / "integrated.txt", b"same in both worktrees\n")
    _write(root / "integrated.txt", b"same in both worktrees\n")
    (source / "deleted.txt").unlink()
    (source / ".venv" / "package.bin").unlink()
    (source / "backend" / "venv" / "nested.bin").unlink()
    (source / "web" / "node_modules" / "package.js").unlink()
    (source / "script.sh").chmod(0o755)
    _write(source / "notes" / "line\nbreak.bin", b"untracked\x00bytes", 0o640)
    os.symlink("line\nbreak.bin", source / "notes" / "alias")
    _write(root / "notes" / "shared.txt", b"identical untracked")
    _write(source / "notes" / "shared.txt", b"identical untracked")
    return binary


def test_salvage_captures_binary_safe_outputs_and_never_mutates_source(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    binary = _dirty_success_fixture(root, source)
    before = _snapshot_source(source)
    output = tmp_path / "salvage"

    payload = run_recovery_worktree_salvage(
        worktree=source,
        output_dir=output,
        comparison_root=root,
        generated_at="2026-08-19T00:00:00Z",
    )

    assert _snapshot_source(source) == before
    assert set(path.name for path in output.iterdir()) == set(OUTPUT_FILENAMES)
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata == payload["metadata"]
    assert metadata["schemaVersion"] == "recovery-worktree-salvage-v1"
    assert metadata["commandVersion"] == "1.0.0"
    assert metadata["source"]["absolutePath"] == str(source.resolve())
    assert metadata["source"]["branchRef"] == "refs/heads/paused"
    assert metadata["source"]["detached"] is False
    assert metadata["source"]["head"] == _git(source, "rev-parse", "HEAD").decode().strip()
    assert metadata["comparison"]["absolutePath"] == str(root.resolve())
    assert metadata["comparison"]["head"] == _git(root, "rev-parse", "HEAD").decode().strip()
    assert metadata["generatedAt"] == "2026-08-19T00:00:00Z"
    assert metadata["statusCounts"] == {
        "deleted": 4,
        "modified": 3,
        "otherTracked": 0,
        "total": 10,
        "tracked": 7,
        "untracked": 3,
    }
    assert metadata["sourceStateBefore"] == metadata["sourceStateAfter"]
    assert len(metadata["porcelainStatusNulSha256"]) == 64
    assert len(metadata["porcelainStatusNulBase64"]) > 0

    patch = (output / "meaningful-tracked.patch").read_bytes()
    assert b"GIT binary patch" in patch
    assert b"index " in patch
    assert b"old mode 100644\nnew mode 100755" in patch
    assert b".venv/package.bin" not in patch
    assert b"backend/venv/nested.bin" not in patch
    assert b"node_modules" not in patch
    roundtrip = tmp_path / "roundtrip"
    subprocess.run(
        ["git", "clone", "--quiet", str(root), str(roundtrip)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    _git(roundtrip, "apply", "--binary", str(output / "meaningful-tracked.patch"))
    assert (roundtrip / "binary.dat").read_bytes() == binary
    assert not (roundtrip / "deleted.txt").exists()
    assert stat.S_IMODE((roundtrip / "script.sh").stat().st_mode) == 0o755

    environment = json.loads((output / "environment-deletions.json").read_text())
    assert [row["path"] for row in environment["deletions"]] == [
        ".venv/package.bin",
        "backend/venv/nested.bin",
        "web/node_modules/package.js",
    ]
    expected_blob = _git(source, "rev-parse", "HEAD:.venv/package.bin").decode().strip()
    env_row = environment["deletions"][0]
    assert env_row["headBlobId"] == expected_blob
    assert env_row["headBlobSize"] == len(b"ENV-BLOB\x00\xff-SHOULD-NOT-BE-IN-PATCH")
    assert env_row["headObjectType"] == "blob"

    with tarfile.open(output / "untracked.tar.gz", "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        assert set(members) == {
            "notes/alias",
            "notes/line\nbreak.bin",
            "notes/shared.txt",
        }
        assert members["notes/alias"].issym()
        assert members["notes/alias"].linkname == "line\nbreak.bin"
        assert members["notes/line\nbreak.bin"].isfile()
        assert members["notes/line\nbreak.bin"].mode == 0o640
        assert archive.extractfile(members["notes/line\nbreak.bin"]).read() == b"untracked\x00bytes"

    comparison = json.loads((output / "comparison.json").read_text())
    by_path = {row["path"]: row for row in comparison["paths"]}
    assert set(by_path) == {
        "binary.dat",
        "deleted.txt",
        "integrated.txt",
        "notes/alias",
        "notes/line\nbreak.bin",
        "notes/shared.txt",
        "script.sh",
    }
    assert by_path["integrated.txt"]["disposition"] == "integrated"
    assert by_path["notes/shared.txt"]["disposition"] == "integrated"
    assert by_path["binary.dat"]["disposition"] == "unique_unresolved"
    assert by_path["deleted.txt"]["disposition"] == "unique_unresolved"
    assert by_path["notes/alias"]["disposition"] == "unique_unresolved"
    assert by_path["integrated.txt"]["evidence"]["sourceSha256"] == by_path[
        "integrated.txt"
    ]["evidence"]["comparisonSha256"]

    checksums = json.loads((output / "checksums.json").read_text())
    assert set(checksums["sha256"]) == set(OUTPUT_FILENAMES) - {"checksums.json"}
    for name, digest in checksums["sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


def test_tracked_patch_uses_initial_snapshot_not_transient_live_bytes(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    intended = b"initial intended postimage\x00\xff"
    wrong = b"WRONG transient reread\x00"
    _write(source / "binary.dat", intended)
    before = _snapshot_source(source)
    real_git = salvage_module._git
    injected = False

    def transient_git(cwd: Path, *args: str, **kwargs: object) -> bytes:
        nonlocal injected
        if cwd == source and args[:1] == ("diff",) and "--binary" in args:
            injected = True
            _write(source / "binary.dat", wrong)
            try:
                return real_git(cwd, *args, **kwargs)
            finally:
                _write(source / "binary.dat", intended)
        return real_git(cwd, *args, **kwargs)

    monkeypatch.setattr(salvage_module, "_git", transient_git)
    output = tmp_path / "snapshot-patch"
    run_recovery_worktree_salvage(
        worktree=source, output_dir=output, comparison_root=root
    )

    assert injected
    assert _snapshot_source(source) == before
    roundtrip = tmp_path / "snapshot-roundtrip"
    subprocess.run(
        ["git", "clone", "--quiet", str(root), str(roundtrip)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    _git(roundtrip, "apply", "--binary", str(output / "meaningful-tracked.patch"))
    assert (roundtrip / "binary.dat").read_bytes() == intended
    assert wrong not in (output / "meaningful-tracked.patch").read_bytes()
    metadata = json.loads((output / "metadata.json").read_text())
    snapshot = metadata["meaningfulTrackedSnapshot"]
    assert snapshot["head"] == metadata["source"]["head"]
    assert len(snapshot["sha256"]) == 64


def test_output_is_deterministic_without_timestamp(worktrees: tuple[Path, Path], tmp_path: Path) -> None:
    root, source = worktrees
    _write(source / "untracked.bin", b"same bytes")
    first = tmp_path / "first"
    second = tmp_path / "second"
    run_recovery_worktree_salvage(worktree=source, output_dir=first, comparison_root=root)
    run_recovery_worktree_salvage(worktree=source, output_dir=second, comparison_root=root)
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {
        p.name: p.read_bytes() for p in second.iterdir()
    }
    assert "generatedAt" not in json.loads((first / "metadata.json").read_text())


def test_environment_deletion_object_lookup_is_batched(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    (source / ".venv" / "package.bin").unlink()
    (source / "backend" / "venv" / "nested.bin").unlink()
    (source / "web" / "node_modules" / "package.js").unlink()
    real_git = salvage_module._git
    calls: list[tuple[str, ...]] = []

    def recording_git(cwd: Path, *args: str, **kwargs: object) -> bytes:
        calls.append(args)
        return real_git(cwd, *args, **kwargs)

    monkeypatch.setattr(salvage_module, "_git", recording_git)
    run_recovery_worktree_salvage(
        worktree=source,
        output_dir=tmp_path / "output",
        comparison_root=root,
    )

    assert sum(args[:1] == ("ls-tree",) for args in calls) == 1
    assert sum(args[:1] == ("cat-file",) for args in calls) == 1


def test_nested_dot_venv_deletion_is_blob_provenance_not_patch_content(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    _write(source / "tools" / ".venv" / "nested.bin", b"nested dot venv")
    _git(source, "add", "tools/.venv/nested.bin")
    _git(source, "commit", "-m", "nested environment")
    (source / "tools" / ".venv" / "nested.bin").unlink()
    (source / "tools" / ".venv").rmdir()
    (source / "tools").rmdir()
    output = tmp_path / "output"

    run_recovery_worktree_salvage(
        worktree=source, output_dir=output, comparison_root=root
    )

    environment = json.loads((output / "environment-deletions.json").read_text())
    assert [row["path"] for row in environment["deletions"]] == [
        "tools/.venv/nested.bin"
    ]
    assert b"tools/.venv/nested.bin" not in (output / "meaningful-tracked.patch").read_bytes()


def test_explicit_valid_supersession_records_commit_and_blob_evidence(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    _write(source / "old.bin", b"unique old bytes")
    _write(root / "replacement.bin", b"replacement bytes")
    _git(root, "add", "replacement.bin")
    _git(root, "commit", "-m", "replacement")
    replacement_commit = _git(root, "rev-parse", "HEAD").decode().strip()
    replacement_blob = _git(root, "rev-parse", "HEAD:replacement.bin").decode().strip()
    supersession = tmp_path / "supersession.json"
    supersession.write_text(
        json.dumps(
            [
                {
                    "path": "old.bin",
                    "replacementCommit": replacement_commit,
                    "replacementPath": "replacement.bin",
                }
            ]
        )
    )
    output = tmp_path / "output"

    run_recovery_worktree_salvage(
        worktree=source,
        output_dir=output,
        comparison_root=root,
        supersession_input=supersession,
    )

    row = json.loads((output / "comparison.json").read_text())["paths"][0]
    assert row["path"] == "old.bin"
    assert row["disposition"] == "superseded"
    assert row["evidence"] == {
        "replacementBlobId": replacement_blob,
        "replacementCommit": replacement_commit,
        "replacementObjectType": "blob",
        "replacementPath": "replacement.bin",
    }


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"path": "old.bin", "replacementCommit": "HEAD"},
        {"path": "old.bin", "replacementPath": "replacement.bin"},
        {
            "path": "old.bin",
            "replacementCommit": "0" * 40,
            "replacementPath": "replacement.bin",
        },
        {
            "path": "missing.bin",
            "replacementCommit": "HEAD",
            "replacementPath": "replacement.bin",
        },
        {
            "path": "old.bin",
            "replacementCommit": "HEAD",
            "replacementPath": "../replacement.bin",
        },
    ],
)
def test_invalid_supersession_fails_closed_without_output(
    worktrees: tuple[Path, Path], tmp_path: Path, record: dict[str, str]
) -> None:
    root, source = worktrees
    _write(source / "old.bin", b"unique")
    _write(root / "replacement.bin", b"replacement")
    _git(root, "add", "replacement.bin")
    _git(root, "commit", "-m", "replacement")
    supersession = tmp_path / "supersession.json"
    supersession.write_text(json.dumps([record]))
    output = tmp_path / "output"

    with pytest.raises(SalvageError, match="supersession|replacement"):
        run_recovery_worktree_salvage(
            worktree=source,
            output_dir=output,
            comparison_root=root,
            supersession_input=supersession,
        )
    assert not output.exists()


def test_duplicate_supersession_path_is_rejected(worktrees: tuple[Path, Path], tmp_path: Path) -> None:
    root, source = worktrees
    _write(source / "old.bin", b"unique")
    _write(root / "replacement.bin", b"replacement")
    _git(root, "add", "replacement.bin")
    _git(root, "commit", "-m", "replacement")
    replacement_commit = _git(root, "rev-parse", "HEAD").decode().strip()
    record = {
        "path": "old.bin",
        "replacementCommit": replacement_commit,
        "replacementPath": "replacement.bin",
    }
    supersession = tmp_path / "supersession.json"
    supersession.write_text(json.dumps([record, record]))
    with pytest.raises(SalvageError, match="duplicate"):
        run_recovery_worktree_salvage(
            worktree=source,
            output_dir=tmp_path / "output",
            comparison_root=root,
            supersession_input=supersession,
        )


@pytest.mark.parametrize("bad_path", ["", "../escape", "/absolute", "a/../../escape", "a\\b"])
def test_repository_paths_reject_absolute_traversal_and_noncanonical_names(bad_path: str) -> None:
    with pytest.raises(SalvageError, match="unsafe"):
        _validate_repo_path(bad_path)


def test_special_untracked_file_is_rejected_and_temp_is_cleaned(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    fifo = source / "unsafe.fifo"
    os.mkfifo(fifo)
    output = tmp_path / "output"
    try:
        with pytest.raises(SalvageError, match="unsupported.*FIFO"):
            run_recovery_worktree_salvage(
                worktree=source, output_dir=output, comparison_root=root
            )
        assert not output.exists()
        assert not list(tmp_path.glob(".output.salvage-tmp-*"))
    finally:
        fifo.unlink()


@pytest.mark.parametrize("target", ["../../outside", "/absolute/outside"])
def test_untracked_symlink_target_cannot_escape_archive_root(
    worktrees: tuple[Path, Path], tmp_path: Path, target: str
) -> None:
    root, source = worktrees
    (source / "links").mkdir()
    os.symlink(target, source / "links" / "escape")
    output = tmp_path / "output"
    with pytest.raises(SalvageError, match="symlink target"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )
    assert not output.exists()


def test_regular_to_outside_symlink_race_fails_without_archiving_secret(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    candidate = source / "race.bin"
    backup = source / "race.bin.safe"
    outside = tmp_path / "outside-secret.bin"
    safe_bytes = b"safe untracked bytes"
    secret_bytes = b"OUTSIDE SECRET MUST NEVER ENTER ARCHIVE"
    _write(candidate, safe_bytes)
    _write(outside, secret_bytes)
    output = tmp_path / "output"
    real_open = salvage_module.os.open
    raced = False

    def racing_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal raced
        is_final_nofollow = (
            path == "race.bin"
            and dir_fd is not None
            and bool(flags & getattr(os, "O_NOFOLLOW", 0))
            and not bool(flags & getattr(os, "O_DIRECTORY", 0))
        )
        if is_final_nofollow and not raced:
            raced = True
            candidate.rename(backup)
            os.symlink(outside, candidate)
            try:
                return real_open(path, flags, mode, dir_fd=dir_fd)
            finally:
                candidate.unlink()
                backup.rename(candidate)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(salvage_module.os, "open", racing_open)
    with pytest.raises(SalvageError, match="changed|symlink|no-follow"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert raced is True
    assert candidate.read_bytes() == safe_bytes
    assert not output.exists()
    assert not list(tmp_path.glob(".output.*"))
    assert secret_bytes not in b"".join(
        path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() and path != outside
    )


def test_untracked_archive_reuses_initial_descriptor_snapshot(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "snapshot.bin", b"captured exactly once for archive")
    real_open = salvage_module.os.open
    final_opens = 0

    def counting_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal final_opens
        if (
            path == "snapshot.bin"
            and dir_fd is not None
            and bool(flags & getattr(os, "O_NOFOLLOW", 0))
            and not bool(flags & getattr(os, "O_DIRECTORY", 0))
        ):
            final_opens += 1
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(salvage_module.os, "open", counting_open)
    run_recovery_worktree_salvage(
        worktree=source,
        output_dir=tmp_path / "output",
        comparison_root=root,
    )

    assert final_opens == 2  # initial capture and final mutation verification


@pytest.mark.parametrize("kind", ["repo-root", "inside-source", "registered", "filesystem-root"])
def test_unsafe_source_and_output_locations_are_rejected(
    worktrees: tuple[Path, Path], tmp_path: Path, kind: str
) -> None:
    root, source = worktrees
    worktree = root if kind == "repo-root" else source
    output = {
        "repo-root": tmp_path / "repo-root-output",
        "inside-source": source / "output",
        "registered": root,
        "filesystem-root": Path("/"),
    }[kind]
    with pytest.raises(SalvageError):
        run_recovery_worktree_salvage(
            worktree=worktree, output_dir=output, comparison_root=root
        )


def test_glob_source_unregistered_source_nonroot_comparison_and_nonempty_output_fail(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    with pytest.raises(SalvageError, match="glob"):
        run_recovery_worktree_salvage(
            worktree=Path(str(source) + "*"),
            output_dir=tmp_path / "one",
            comparison_root=root,
        )
    with pytest.raises(SalvageError, match="registered"):
        run_recovery_worktree_salvage(
            worktree=tmp_path,
            output_dir=tmp_path / "two",
            comparison_root=root,
        )
    with pytest.raises(SalvageError, match="root worktree"):
        run_recovery_worktree_salvage(
            worktree=source,
            output_dir=tmp_path / "three",
            comparison_root=source,
        )
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    _write(nonempty / "sentinel", b"preserve")
    with pytest.raises(SalvageError, match="absent or empty"):
        run_recovery_worktree_salvage(
            worktree=source,
            output_dir=nonempty,
            comparison_root=root,
        )
    assert (nonempty / "sentinel").read_bytes() == b"preserve"


def test_unmerged_and_rename_statuses_fail_closed(worktrees: tuple[Path, Path], tmp_path: Path) -> None:
    root, source = worktrees
    _git(source, "mv", "binary.dat", "renamed.dat")
    with pytest.raises(SalvageError, match="rename|unsupported"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=tmp_path / "rename", comparison_root=root
        )

    _git(source, "reset", "--hard", "HEAD")
    _git(root, "checkout", "-b", "other")
    _write(root / "integrated.txt", b"other\n")
    _git(root, "commit", "-am", "other")
    other = _git(root, "rev-parse", "HEAD").decode().strip()
    _git(root, "checkout", "main")
    _write(root / "integrated.txt", b"main\n")
    _git(root, "commit", "-am", "main")
    _write(source / "integrated.txt", b"paused\n")
    _git(source, "commit", "-am", "paused")
    result = subprocess.run(
        ["git", "-C", str(source), "merge", other],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode != 0
    with pytest.raises(SalvageError, match="unmerged"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=tmp_path / "unmerged", comparison_root=root
        )


def test_verification_failure_and_source_mutation_leave_no_partial_target(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output = tmp_path / "output"

    def fail_verification(*args: object, **kwargs: object) -> None:
        raise SalvageError("injected checksum verification failure")

    monkeypatch.setattr(salvage_module, "_verify_staged_output", fail_verification)
    with pytest.raises(SalvageError, match="retained quarantine") as error:
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".output.salvage-tmp-*"))
    quarantines = list(tmp_path.glob(".output.salvage-quarantine-*"))
    assert len(quarantines) == 1
    assert str(quarantines[0]) in str(error.value)
    assert {path.name for path in quarantines[0].iterdir()} == set(OUTPUT_FILENAMES)

    monkeypatch.undo()
    real_fingerprint = salvage_module._source_fingerprint
    calls = 0

    def changing_fingerprint(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        result = real_fingerprint(*args, **kwargs)
        if args[0] == source:
            calls += 1
        if args[0] == source and calls == 2:
            result = dict(result)
            result["head"] = "f" * 40
        return result

    monkeypatch.setattr(salvage_module, "_source_fingerprint", changing_fingerprint)
    with pytest.raises(SalvageError, match="source worktree changed"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".output.salvage-tmp-*"))


def test_output_collision_created_before_publish_is_never_displaced(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output = tmp_path / "output"
    sentinel_bytes = b"user-owned collision"
    real_verify = salvage_module._verify_staged_output

    def create_collision_after_verify(*args: object, **kwargs: object) -> None:
        real_verify(*args, **kwargs)
        output.mkdir()
        (output / "sentinel").write_bytes(sentinel_bytes)

    monkeypatch.setattr(
        salvage_module, "_verify_staged_output", create_collision_after_verify
    )
    with pytest.raises(SalvageError, match="quarantine") as error:
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert output.is_dir()
    assert {path.name for path in output.iterdir()} == {"sentinel"}
    assert (output / "sentinel").read_bytes() == sentinel_bytes
    assert not list(tmp_path.glob(".output.salvage-tmp-*"))
    assert not list(tmp_path.glob(".output.empty-backup-*"))
    quarantines = list(tmp_path.glob(".output.salvage-quarantine-*"))
    assert len(quarantines) == 1
    assert str(quarantines[0]) in str(error.value)
    assert {path.name for path in quarantines[0].iterdir()} == set(OUTPUT_FILENAMES)


def test_output_parent_swap_to_source_symlink_fails_without_redirected_writes(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output_parent = tmp_path / "outside-parent"
    pinned_parent = tmp_path / "outside-parent-pinned"
    output_parent.mkdir()
    output = output_parent / "bundle"
    before = _snapshot_source(source)
    real_publish = salvage_module._publish

    def swap_parent_before_publish(*args: object, **kwargs: object) -> None:
        output_parent.rename(pinned_parent)
        os.symlink(source, output_parent, target_is_directory=True)
        real_publish(*args, **kwargs)

    monkeypatch.setattr(salvage_module, "_publish", swap_parent_before_publish)
    with pytest.raises(SalvageError, match="output parent|identity|symlink"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert _snapshot_source(source) == before
    assert output_parent.is_symlink()
    assert pinned_parent.is_dir() and not any(pinned_parent.iterdir())
    assert not (source / "bundle").exists()
    assert not list(pinned_parent.glob(".bundle.salvage-tmp-*"))
    assert not list(source.glob(".bundle.salvage-tmp-*"))


def test_verified_staging_swap_is_not_published_or_deleted(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output = tmp_path / "bundle"
    verified_aside = tmp_path / "verified-staging-aside"
    evil = b"attacker-owned"
    before = _snapshot_source(source)
    real_rename = salvage_module._rename_noreplace
    swapped_name: str | None = None

    def swap_staging_before_rename(
        source_dir_fd: int,
        source_name: str,
        destination_dir_fd: int,
        destination_name: str,
    ) -> None:
        nonlocal swapped_name
        if swapped_name is None:
            swapped_name = source_name
            (tmp_path / source_name).rename(verified_aside)
            replacement = tmp_path / source_name
            replacement.mkdir()
            (replacement / "evil.txt").write_bytes(evil)
        real_rename(
            source_dir_fd, source_name, destination_dir_fd, destination_name
        )

    monkeypatch.setattr(salvage_module, "_rename_noreplace", swap_staging_before_rename)
    with pytest.raises(SalvageError, match="quarantine") as error:
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert _snapshot_source(source) == before
    assert not output.exists()
    assert not verified_aside.exists()
    quarantines = list(tmp_path.glob(".bundle.salvage-quarantine-*"))
    assert len(quarantines) == 1
    assert str(quarantines[0]) in str(error.value)
    assert {path.name for path in quarantines[0].iterdir()} == set(OUTPUT_FILENAMES)
    assert swapped_name is not None
    attacker_directory = tmp_path / swapped_name
    assert attacker_directory.is_dir()
    assert {path.name for path in attacker_directory.iterdir()} == {"evil.txt"}
    assert (attacker_directory / "evil.txt").read_bytes() == evil


def test_cleanup_file_swap_preserves_replacement_in_reported_quarantine(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output = tmp_path / "output"
    attacker_bytes = b"attacker replacement must survive"
    before = _snapshot_source(source)
    real_verify = salvage_module._verify_staged_output
    verification_calls = 0

    def fail_after_verified(*args: object, **kwargs: object) -> None:
        nonlocal verification_calls
        real_verify(*args, **kwargs)
        verification_calls += 1
        if verification_calls == 1:
            staging = Path(os.readlink(f"/proc/self/fd/{args[0]}"))
            (staging / "attacker-extra.txt").write_bytes(attacker_bytes)
            raise SalvageError("injected failure requiring cleanup")

    monkeypatch.setattr(salvage_module, "_verify_staged_output", fail_after_verified)
    with pytest.raises(SalvageError, match="retained quarantine") as error:
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert _snapshot_source(source) == before
    assert not output.exists()
    quarantines = list(tmp_path.glob(".output.salvage-quarantine-*"))
    assert len(quarantines) == 1
    assert str(quarantines[0]) in str(error.value)
    assert any(
        path.is_file() and path.read_bytes() == attacker_bytes
        for path in quarantines[0].iterdir()
    )


def test_cleanup_name_swap_after_identity_check_is_never_unlinked(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "unique.bin", b"unique")
    output = tmp_path / "output"
    attacker_bytes = b"replacement after cleanup rename"
    before = _snapshot_source(source)
    real_verify = salvage_module._verify_staged_output
    real_entry_identity = salvage_module._entry_identity
    verification_calls = 0
    swapped = False

    def fail_after_verified(*args: object, **kwargs: object) -> None:
        nonlocal verification_calls
        real_verify(*args, **kwargs)
        verification_calls += 1
        if verification_calls == 1:
            staging = Path(os.readlink(f"/proc/self/fd/{args[0]}"))
            (staging / ".salvage-cleanup-attacker").write_bytes(attacker_bytes)
            raise SalvageError("injected failure requiring cleanup")

    def swap_cleanup_name_after_identity(parent_fd: int, name: str):
        nonlocal swapped
        identity = real_entry_identity(parent_fd, name)
        if name.startswith(".salvage-cleanup-") and identity is not None and not swapped:
            directory = Path(os.readlink(f"/proc/self/fd/{parent_fd}"))
            swapped = True
            (directory / name).rename(directory / "verified-cleanup-file-aside")
            (directory / name).write_bytes(attacker_bytes)
        return identity

    monkeypatch.setattr(salvage_module, "_verify_staged_output", fail_after_verified)
    monkeypatch.setattr(
        salvage_module, "_entry_identity", swap_cleanup_name_after_identity
    )
    with pytest.raises(SalvageError, match="retained quarantine") as error:
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )

    assert not swapped
    assert _snapshot_source(source) == before
    assert not output.exists()
    quarantines = list(tmp_path.glob(".output.salvage-quarantine-*"))
    assert len(quarantines) == 1
    assert str(quarantines[0]) in str(error.value)
    assert any(
        path.is_file() and path.read_bytes() == attacker_bytes
        for path in quarantines[0].iterdir()
    )


def test_comparison_mutation_fails_closed_before_publish(
    worktrees: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source = worktrees
    _write(source / "same.txt", b"same")
    _write(root / "same.txt", b"same")
    output = tmp_path / "output"
    real_fingerprint = salvage_module._source_fingerprint
    comparison_calls = 0

    def changing_comparison(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal comparison_calls
        result = real_fingerprint(*args, **kwargs)
        if args[0] == root:
            comparison_calls += 1
        if args[0] == root and comparison_calls == 2:
            result = dict(result)
            result["head"] = "e" * 40
        return result

    monkeypatch.setattr(salvage_module, "_source_fingerprint", changing_comparison)
    with pytest.raises(SalvageError, match="comparison root changed"):
        run_recovery_worktree_salvage(
            worktree=source, output_dir=output, comparison_root=root
        )
    assert not output.exists()


def test_cli_requires_exact_inputs_and_writes_only_six_outputs(
    worktrees: tuple[Path, Path], tmp_path: Path
) -> None:
    root, source = worktrees
    with pytest.raises(SystemExit):
        main(["--worktree", str(source)])
    output = tmp_path / "output"
    assert main(
        [
            "--worktree",
            str(source),
            "--output-dir",
            str(output),
            "--comparison-root",
            str(root),
            "--generated-at",
            "caller timestamp",
        ]
    ) == 0
    assert set(path.name for path in output.iterdir()) == set(OUTPUT_FILENAMES)
    assert json.loads((output / "metadata.json").read_text())["generatedAt"] == "caller timestamp"
