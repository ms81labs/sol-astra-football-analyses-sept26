from concurrent.futures import ThreadPoolExecutor
import os
import stat
import threading

import pytest

from backend.app.storage import Storage, StorageDeleteOutcomeUncertain


def test_list_review_bundles_surfaces_corrupt_file(tmp_path):
    storage = Storage(tmp_path)
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    (bundles / "broken.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(RuntimeError, match="broken") as error:
        storage.list_review_bundles()

    assert type(error.value).__name__ == "ReviewBundleCorruptError"


def test_concurrent_non_conflicting_bundle_updates_both_survive(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    bundle = storage.create_review_bundle("original", description="original")
    start = threading.Barrier(2)
    snapshots = threading.Barrier(2)
    original_read = storage._read_json

    def overlapping_read(path):
        value = original_read(path)
        try:
            snapshots.wait(timeout=0.15)
        except threading.BrokenBarrierError:
            pass  # A transaction lock correctly prevents the second read entering.
        return value

    def update(changes):
        start.wait(timeout=2)
        return storage.update_review_bundle(bundle.id, **changes)

    monkeypatch.setattr(storage, "_read_json", overlapping_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(update, [{"name": "renamed"}, {"description": "rewritten"}]))

    saved = storage.get_review_bundle(bundle.id)
    assert saved.name == "renamed"
    assert saved.description == "rewritten"


def test_delete_commit_failure_restores_bundle(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    bundle = storage.create_review_bundle("keep me")
    original_fsync = os.fsync
    directory_syncs = 0

    def fail_delete_commit(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            if directory_syncs == 1:
                raise OSError("injected delete fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_delete_commit)
    with pytest.raises(OSError, match="injected delete fsync failure"):
        storage.delete_review_bundle(bundle.id)

    assert storage.get_review_bundle(bundle.id).name == "keep me"
    assert list((tmp_path / "bundles").iterdir()) == [
        tmp_path / "bundles" / f"{bundle.id}.json"
    ]


def test_failed_delete_rollback_is_explicit_and_retains_bundle_bytes(
    tmp_path, monkeypatch
):
    storage = Storage(tmp_path)
    bundle = storage.create_review_bundle("recover me")
    bundle_path = tmp_path / "bundles" / f"{bundle.id}.json"
    before = bundle_path.read_bytes()
    original_fsync = os.fsync
    original_replace = os.replace
    directory_syncs = replacements = 0

    def fail_delete_commit(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            if directory_syncs == 1:
                raise OSError("injected delete fsync failure")
        return original_fsync(fd)

    def fail_rollback(source, destination):
        nonlocal replacements
        replacements += 1
        if replacements == 2:
            raise OSError("injected delete rollback failure")
        return original_replace(source, destination)

    monkeypatch.setattr(os, "fsync", fail_delete_commit)
    monkeypatch.setattr(os, "replace", fail_rollback)
    with pytest.raises(StorageDeleteOutcomeUncertain, match="inspect before retrying"):
        storage.delete_review_bundle(bundle.id)

    assert not bundle_path.exists()
    retained = list((tmp_path / "bundles").iterdir())
    assert len(retained) == 1
    assert retained[0].suffix == ".deleted"
    assert retained[0].read_bytes() == before
