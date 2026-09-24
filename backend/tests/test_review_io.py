"""Real overlay transactions; syscall faults never replace the filesystem."""

from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import stat
import threading

import pytest
from backend.scripts.review_io import ReviewWriteError


MODULES = [
    "serve_promoted_v6_manual_review_ui",
    "serve_v7_1_positive_diversity_review_ui",
    "serve_football_external_soccernet_detector_miss_review_ui",
]


@pytest.fixture(params=MODULES)
def consumer(request, tmp_path):
    module = importlib.import_module(f"backend.scripts.{request.param}")
    root = tmp_path / "reviews"
    path = (root / "reviewed_label_overlay.json" if request.param == MODULES[0]
            else module._overlay_path(root))
    path.parent.mkdir(parents=True)
    rows = [{"reviewItemId": name, "candidateId": name, "decision": "pending_review",
             "reviewStatus": "pending_review", "lineageComplete": True,
             "seedBBox": {"x1": 1, "y1": 2, "x2": 11, "y2": 12}}
            for name in ("one", "two")]
    path.write_text(json.dumps({"schemaVersion": "retain-me", "reviewItems": rows}))

    def update(name="one"):
        if request.param == MODULES[0]:
            return module.update_review_item(review_root=root, review_item_id=name, decision="accept_seed")
        arguments = {"candidate_id" if request.param == MODULES[1] else "review_item_id": name}
        return module.update_review_item(candidate_root=root, **arguments, review_status=module.POSITIVE_STATUS,
                                         source_frame_bbox={"x1": 1, "y1": 2, "x2": 11, "y2": 12})

    return module, path, update


def test_concurrent_different_item_edits_both_survive(consumer, monkeypatch):
    # Break: a lock around replace alone lets two accepted edits overwrite each other.
    module, path, update = consumer
    start = threading.Barrier(2)
    snapshots = threading.Barrier(2)
    original_load = module._load_json_dict

    def overlapping_read(path):
        value = original_load(path)
        try:
            snapshots.wait(timeout=0.15)
        except threading.BrokenBarrierError:
            pass  # The transaction lock correctly prevents the second read entering.
        return value

    def edit(name):
        start.wait(timeout=2)
        return update(name)

    monkeypatch.setattr(module, "_load_json_dict", overlapping_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, ["one", "two"]))
    assert len(results) == 2
    saved = json.loads(path.read_text())
    field = "decision" if module.__name__.endswith(MODULES[0]) else "reviewStatus"
    expected = "accept_seed" if field == "decision" else module.POSITIVE_STATUS
    assert [item[field] for item in saved["reviewItems"]] == [expected, expected]
    assert saved["pendingReviewCount"] == 0
    assert saved["schemaVersion"] == "retain-me"


@pytest.mark.parametrize("invalid", ["{broken", "[]", "null", "{}", '{"reviewItems":{}}',
                                      '{"reviewItems":[{"reviewItemId":"one","candidateId":"one"},null]}',
                                      '{"reviewItems":[{"reviewItemId":"one","candidateId":"one"},3]}'])
def test_invalid_overlay_is_rejected_without_losing_bytes(consumer, invalid):
    # Break: silently filtering malformed rows turns a save into data loss.
    module, path, update = consumer
    path.write_text(invalid)
    before = path.read_bytes()
    with pytest.raises(module.ReviewUpdateError, match="invalid_review_document|invalid_review_items"):
        update()
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_writer_fdopen_failure_closes_raw_descriptor(consumer, monkeypatch):
    # Break: fdopen can fail before a with statement owns its raw descriptor.
    module, path, _ = consumer
    before = path.read_bytes()
    descriptors = []

    def fail_fdopen(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("private-path/fdopen")

    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    try:
        with pytest.raises(ReviewWriteError):
            module._write_json_atomic(path, {"new": True})
        assert path.read_bytes() == before
        assert list(path.parent.iterdir()) == [path]
        assert descriptors
        for fd in descriptors:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        for fd in descriptors:
            try:
                os.close(fd)
            except OSError:
                pass


@pytest.mark.parametrize("fault", ["parent_open", "parent_component_open", "destination_stat", "temp_open",
                                    "encode", "write", "flush", "stream_close", "file_fsync",
                                    "backup_link", "backup_stat", "backup_fsync", "replace"])
def test_prepublication_failure_preserves_prior_bytes_and_cleans_names(consumer, monkeypatch, fault):
    # Break: touching the prior file or leaking temp/backup names on any preparation failure.
    module, path, _ = consumer
    before = path.read_bytes()
    payload = {"new": object()} if fault == "encode" else {"new": True}
    original_open, original_fdopen = os.open, os.fdopen
    original_fsync, original_stat = os.fsync, os.stat

    def fail(*args, **kwargs):
        raise OSError("private-path/injected-failure")

    def open_with_fault(name, flags, *args, **kwargs):
        if fault == "parent_open" and flags & os.O_DIRECTORY:
            fail()
        if fault == "parent_component_open" and flags & os.O_DIRECTORY and kwargs.get("dir_fd") is not None:
            fail()
        if fault == "temp_open" and flags & os.O_CREAT:
            fail()
        return original_open(name, flags, *args, **kwargs)

    def stat_with_fault(name, *args, **kwargs):
        if ((fault == "destination_stat" and name == path.name)
                or (fault == "backup_stat" and str(name).endswith(".bak"))):
            fail()
        return original_stat(name, *args, **kwargs)

    class FaultyStream:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            result = self.handle.__exit__(*args)
            if fault == "stream_close":
                fail()
            return result

        def write(self, value):
            self.handle.write(value)
            if fault == "write":
                fail()

        def flush(self):
            if fault == "flush":
                fail()
            self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    def fsync_with_fault(fd):
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if (fault == "file_fsync" and not directory) or (fault == "backup_fsync" and directory):
            fail()
        return original_fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", open_with_fault)
        patch.setattr(os, "stat", stat_with_fault)
        patch.setattr(os, "fsync", fsync_with_fault)
        if fault in {"write", "flush", "stream_close"}:
            patch.setattr(os, "fdopen", lambda *a, **kw: FaultyStream(original_fdopen(*a, **kw)))
        if fault == "backup_link":
            patch.setattr(os, "link", fail)
        if fault == "replace":
            patch.setattr(os, "replace", fail)
        with pytest.raises(Exception) as error:
            module._write_json_atomic(path, payload)
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]
    assert str(error.value) == "review_write_failed"


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("rollback_sync_fails", [True, False])
def test_commit_fsync_failure_restores_visible_prior_state(consumer, monkeypatch, existing, rollback_sync_fails):
    # Break: reporting a failed save after replace leaves the new edit silently published.
    module, path, _ = consumer
    before = path.read_bytes() if existing else None
    if not existing:
        path.unlink()
    original_fsync = os.fsync
    directory_syncs = 0

    def fail_commit_sync(fd):
        nonlocal directory_syncs
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_syncs += 1
            commit_call = 2 if existing else 1
            if directory_syncs == commit_call or (rollback_sync_fails and directory_syncs > commit_call):
                raise OSError("private-path/directory-fsync")
        original_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_commit_sync)
    with pytest.raises(Exception) as error:
        module._write_json_atomic(path, {"new": True})
    assert path.read_bytes() == before if existing else not path.exists()
    assert list(path.parent.iterdir()) == ([path] if existing else [])
    assert str(error.value) == "review_write_failed"
    assert directory_syncs == (3 if existing else 2)


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("close_fails", [False, True])
def test_failed_rollback_has_distinct_uncertain_outcome_and_retains_recovery_bytes(consumer, monkeypatch, existing, close_fails):
    # Break: a failed restore must not be mistaken for a safe retryable failure.
    module, path, _ = consumer
    before = path.read_bytes() if existing else None
    if not existing:
        path.unlink()
    original_fsync, original_replace, original_unlink = os.fsync, os.replace, os.unlink
    original_close = os.close
    parent_fd = None
    replaced = False

    def replace_once(*args, **kwargs):
        nonlocal replaced, parent_fd
        parent_fd = kwargs.get("src_dir_fd")
        if replaced:
            raise OSError("private-path/rollback-replace")
        original_replace(*args, **kwargs)
        replaced = True

    def fail_commit(fd):
        if replaced and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("private-path/directory-fsync")
        original_fsync(fd)

    def fail_removal(name, *args, **kwargs):
        if replaced and Path(name).name == path.name:
            raise OSError("private-path/rollback-unlink")
        original_unlink(name, *args, **kwargs)

    def close_with_fault(fd):
        original_close(fd)
        if close_fails and fd == parent_fd:
            raise OSError("private-path/parent-close")

    monkeypatch.setattr(os, "replace", replace_once)
    monkeypatch.setattr(os, "fsync", fail_commit)
    monkeypatch.setattr(os, "unlink", fail_removal)
    monkeypatch.setattr(os, "close", close_with_fault)
    with pytest.raises(Exception) as error:
        module._write_json_atomic(path, {"new": True})
    assert type(error.value).__name__ == "ReviewWriteOutcomeUncertain"
    assert str(error.value) == "review_write_outcome_uncertain_do_not_retry"
    assert json.loads(path.read_text()) == {"new": True}
    leftovers = [file for file in path.parent.iterdir() if file != path]
    assert len(leftovers) == (1 if existing else 0)
    if existing:
        assert leftovers[0].read_bytes() == before


def test_parent_close_failure_preserves_durable_success(consumer, monkeypatch):
    # Break: descriptor cleanup cannot change an already durable save into a failed edit.
    module, path, _ = consumer
    parent_inode = path.parent.stat().st_ino
    original_close = os.close

    def close_with_fault(fd):
        descriptor = os.fstat(fd)
        is_parent = stat.S_ISDIR(descriptor.st_mode) and descriptor.st_ino == parent_inode
        original_close(fd)
        if is_parent:
            raise OSError("private-path/parent-close")

    monkeypatch.setattr(os, "close", close_with_fault)
    module._write_json_atomic(path, {"new": True})
    assert json.loads(path.read_text()) == {"new": True}
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("link_kind", ["destination", "parent", "ancestor"])
def test_writer_never_follows_symlinks(consumer, tmp_path, link_kind):
    # Break: path-based temporary creation or parent opens can write outside the owned directory.
    module, path, _ = consumer
    before = path.read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / path.name
    sentinel.write_bytes(b"outside-sentinel")
    if link_kind == "destination":
        path.unlink()
        path.symlink_to(sentinel)
        target = path
    elif link_kind == "parent":
        link = tmp_path / "linked"
        link.symlink_to(outside, target_is_directory=True)
        target = link / path.name
    else:
        (outside / "nested").mkdir()
        link = tmp_path / "linked"
        link.symlink_to(outside, target_is_directory=True)
        target = link / "nested" / path.name
    with pytest.raises(Exception) as error:
        module._write_json_atomic(target, {"new": True})
    assert str(error.value) == "review_write_failed"
    assert sentinel.read_bytes() == b"outside-sentinel"
    assert sorted(file.name for file in outside.iterdir()) == (sorted(["nested", path.name]) if link_kind == "ancestor" else [path.name])
    if link_kind != "destination":
        assert path.read_bytes() == before


def test_writer_success_fsyncs_data_backup_and_commit_in_order(consumer, monkeypatch):
    # Break: a save returning before file/backup/replacement syncs is not durable.
    module, path, _ = consumer
    before = path.read_bytes()
    original_fsync = os.fsync
    stages = []

    def inspect_sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            others = [file for file in path.parent.iterdir() if file != path]
            backups = [file for file in others if file.stat().st_ino == path.stat().st_ino]
            if path.read_bytes() == before:
                assert len(backups) == 1
                stages.append("backup")
            else:
                assert any(file.read_bytes() == before for file in others)
                stages.append("commit")
        else:
            assert path.read_bytes() == before
            assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
            stages.append("data")
        original_fsync(fd)

    monkeypatch.setattr(os, "fsync", inspect_sync)
    module._write_json_atomic(path, {"new": True})
    assert stages == ["data", "backup", "commit"]
    assert json.loads(path.read_text()) == {"new": True}
    assert list(path.parent.iterdir()) == [path]


def test_overlay_fdopen_failure_closes_raw_descriptor(consumer, monkeypatch):
    # Break: secure overlay reads must not introduce an fd leak before the writer runs.
    _, path, update = consumer
    before = path.read_bytes()
    descriptors = []

    def fail_fdopen(fd, *args, **kwargs):
        descriptors.append(fd)
        raise OSError("private-path/read-fdopen")

    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    try:
        with pytest.raises(OSError, match="review_write_failed"):
            update()
        assert path.read_bytes() == before
        assert list(path.parent.iterdir()) == [path]
        assert descriptors
        for fd in descriptors:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        for fd in descriptors:
            try:
                os.close(fd)
            except OSError:
                pass


def test_different_server_modules_share_the_whole_transaction(tmp_path, monkeypatch):
    # Break: one lock per module still loses updates when two tools share an overlay.
    first, second = [importlib.import_module(f"backend.scripts.{name}") for name in MODULES[1:]]
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps({"reviewItems": [
        {"reviewItemId": name, "candidateId": name, "reviewStatus": "pending_review"}
        for name in ("one", "two")]}))
    start, snapshots = threading.Barrier(2), threading.Barrier(2)

    def overlap(loader):
        def load(path):
            result = loader(path)
            try:
                snapshots.wait(timeout=0.15)
            except threading.BrokenBarrierError:
                pass
            return result
        return load

    for module in (first, second):
        monkeypatch.setattr(module, "_overlay_path", lambda root: path)
        monkeypatch.setattr(module, "_load_json_dict", overlap(module._load_json_dict))

    def edit(index):
        start.wait(timeout=2)
        module = (first, second)[index]
        key, name = ("candidate_id", "one") if index == 0 else ("review_item_id", "two")
        return module.update_review_item(candidate_root=tmp_path, **{key: name},
                                         review_status=module.POSITIVE_STATUS,
                                         source_frame_bbox={"x1": 1, "y1": 2, "x2": 11, "y2": 12})

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(list(pool.map(edit, [0, 1]))) == 2
    assert [item["reviewStatus"] for item in json.loads(path.read_text())["reviewItems"]] == [
        "reviewed_positive_ball", "reviewed_real_detector_miss_positive"]


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_non_regular_destination_is_rejected_without_opening_it(consumer, kind):
    # Break: non-regular overlay paths can block or replace special filesystem nodes.
    module, path, _ = consumer
    path.unlink()
    path.mkdir() if kind == "directory" else os.mkfifo(path)
    before = path.lstat()
    with pytest.raises(OSError, match="review_write_failed"):
        module._write_json_atomic(path, {"new": True})
    assert path.lstat().st_ino == before.st_ino
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("suffix", ["tmp", "bak"])
def test_private_name_collision_never_removes_existing_file(consumer, monkeypatch, suffix):
    # Break: cleaning a proposed name before actually acquiring it deletes someone else's file.
    from backend.scripts import review_io

    module, path, _ = consumer
    before = path.read_bytes()
    collision = path.parent / f".{path.name}.collision.{suffix}"
    collision.write_bytes(b"existing-private-name")
    monkeypatch.setattr(review_io.secrets, "token_hex", lambda size: "collision")
    with pytest.raises(OSError, match="review_write_failed"):
        module._write_json_atomic(path, {"new": True})
    assert path.read_bytes() == before
    assert collision.read_bytes() == b"existing-private-name"
    assert set(path.parent.iterdir()) == {path, collision}


def test_backup_cleanup_failure_rolls_back_without_false_error_after_commit(consumer, monkeypatch):
    # Break: a cleanup exception after durable commit otherwise reports error with new bytes.
    module, path, _ = consumer
    before = path.read_bytes()
    original_unlink = os.unlink

    def fail_backup_unlink(name, *args, **kwargs):
        if str(name).endswith(".bak"):
            raise OSError("private-path/backup-cleanup")
        original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", fail_backup_unlink)
    with pytest.raises(OSError, match="review_write_failed"):
        module._write_json_atomic(path, {"new": True})
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_parent_is_not_reopened_after_publication(consumer, monkeypatch):
    # Break: reopening the directory after replace can fail too late to pin rollback.
    module, path, _ = consumer
    original_open, original_replace = os.open, os.replace
    published = False

    def publish(*args, **kwargs):
        nonlocal published
        original_replace(*args, **kwargs)
        published = True

    def refuse_late_open(name, flags, *args, **kwargs):
        if published and flags & os.O_DIRECTORY:
            raise OSError("private-path/late-parent-open")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "replace", publish)
    monkeypatch.setattr(os, "open", refuse_late_open)
    module._write_json_atomic(path, {"new": True})
    assert json.loads(path.read_text()) == {"new": True}
    assert list(path.parent.iterdir()) == [path]


def test_parent_swap_cannot_redirect_temporary_or_publication(consumer, monkeypatch, tmp_path):
    # Break: a path-based tempfile/replace escapes the pinned directory after a symlink swap.
    module, path, _ = consumer
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / path.name
    sentinel.write_bytes(b"outside-sentinel")
    moved = path.parent.with_name(path.parent.name + "-pinned")
    original_open = os.open
    swapped = False

    def swap_before_create(name, flags, *args, **kwargs):
        nonlocal swapped
        if flags & os.O_CREAT and not swapped:
            path.parent.rename(moved)
            path.parent.symlink_to(outside, target_is_directory=True)
            swapped = True
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_create)
    module._write_json_atomic(path, {"new": True})
    assert sentinel.read_bytes() == b"outside-sentinel"
    assert list(outside.iterdir()) == [sentinel]
    assert json.loads((moved / path.name).read_text()) == {"new": True}
    assert list(moved.iterdir()) == [moved / path.name]


def test_symlink_swap_before_backup_never_reads_or_writes_target(consumer, monkeypatch, tmp_path):
    # Break: a check followed by a symlink-following backup can retain unowned content.
    module, path, _ = consumer
    sentinel = tmp_path / "outside.json"
    sentinel.write_bytes(b"outside-sentinel")
    original_link = os.link

    def swap_before_link(*args, **kwargs):
        path.unlink()
        path.symlink_to(sentinel)
        original_link(*args, **kwargs)

    monkeypatch.setattr(os, "link", swap_before_link)
    with pytest.raises(OSError, match="review_write_failed"):
        module._write_json_atomic(path, {"new": True})
    assert path.is_symlink()
    assert sentinel.read_bytes() == b"outside-sentinel"
    assert list(path.parent.iterdir()) == [path]


def test_normalized_item_lookup_does_not_fail_after_publication(consumer):
    # Break: matching IDs as strings then looking them up by exact type fails after saving.
    module, path, update = consumer
    value = json.loads(path.read_text())
    value["reviewItems"][0].update({"reviewItemId": 7, "candidateId": 7})
    path.write_text(json.dumps(value))
    result = update("7")
    saved = json.loads(path.read_text())["reviewItems"][0]
    assert result["reviewItem"] == saved
    assert saved["decision" if module.__name__.endswith(MODULES[0]) else "reviewStatus"] != "pending_review"


def test_overlay_read_failure_preserves_bytes_and_closes_descriptor(consumer, monkeypatch):
    # Break: an I/O failure while loading must leave no publication artifacts or open fd.
    _, path, update = consumer
    before = path.read_bytes()
    original_fdopen = os.fdopen
    descriptors = []

    class FailedRead:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self):
            self.handle.read(1)
            raise OSError("private-path/read-failure")

    def fail_after_open(fd, *args, **kwargs):
        descriptors.append(fd)
        return FailedRead(original_fdopen(fd, *args, **kwargs))

    monkeypatch.setattr(os, "fdopen", fail_after_open)
    with pytest.raises(OSError, match="review_write_failed"):
        update()
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
