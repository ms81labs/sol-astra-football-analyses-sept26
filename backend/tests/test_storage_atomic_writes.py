import os
from pathlib import Path
import stat

import pytest

from backend.app.storage import Storage, StorageWriteOutcomeUncertain


def test_parent_open_failure_preserves_existing_json(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"old": true}', encoding="utf-8")
    before = path.read_bytes()
    original_open = os.open

    def fail_parent_open(name, flags, *args, **kwargs):
        if flags & getattr(os, "O_DIRECTORY", 0):
            raise OSError("injected parent open failure")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail_parent_open)
    with pytest.raises(OSError, match="injected parent open failure"):
        Storage._write_json(path, {"new": True})

    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_commit_fsync_failure_restores_existing_json(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"old": true}', encoding="utf-8")
    before = path.read_bytes()
    original_fsync = os.fsync
    directory_syncs = 0

    def fail_commit_sync(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            if directory_syncs == 2:
                raise OSError("injected commit fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_commit_sync)
    with pytest.raises(OSError, match="injected commit fsync failure"):
        Storage._write_json(path, {"new": True})

    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_commit_fsync_failure_removes_new_json(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    original_fsync = os.fsync
    directory_syncs = 0

    def fail_commit_sync(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            if directory_syncs == 1:
                raise OSError("injected commit fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_commit_sync)
    with pytest.raises(OSError, match="injected commit fsync failure"):
        Storage._write_json(path, {"new": True})

    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_failed_rollback_is_explicit_and_retains_prior_bytes(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"old": true}', encoding="utf-8")
    before = path.read_bytes()
    original_fsync = os.fsync
    original_replace = os.replace
    directory_syncs = replacements = 0

    def fail_commit_sync(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            if directory_syncs == 2:
                raise OSError("injected commit fsync failure")
        return original_fsync(fd)

    def fail_rollback(source, destination):
        nonlocal replacements
        replacements += 1
        if replacements == 2:
            raise OSError("injected rollback failure")
        return original_replace(source, destination)

    monkeypatch.setattr(os, "fsync", fail_commit_sync)
    monkeypatch.setattr(os, "replace", fail_rollback)
    with pytest.raises(StorageWriteOutcomeUncertain, match="inspect before retrying"):
        Storage._write_json(path, {"new": True})

    assert path.read_text(encoding="utf-8") == '{\n  "new": true\n}'
    retained = [candidate for candidate in tmp_path.iterdir() if candidate != path]
    assert len(retained) == 1
    assert retained[0].suffix == ".bak"
    assert retained[0].read_bytes() == before
