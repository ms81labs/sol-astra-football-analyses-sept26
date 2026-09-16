from __future__ import annotations

import os
import stat
from io import BytesIO
from pathlib import Path

import pytest

from backend.app.storage import Storage


class RecordingStream(BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class FailingStream(BytesIO):
    def read(self, size: int = -1) -> bytes:
        if self.tell():
            raise OSError("injected stream failure")
        return super().read(size)


def test_save_upload_stream_reads_bounded_chunks_and_preserves_bytes(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    payload = os.urandom(1024 * 1024 + 37)
    stream = RecordingStream(payload)

    path = storage.save_upload_stream("clip.bin", stream, len(payload))

    assert stream.read_sizes == [1024 * 1024, 1024 * 1024, 1024 * 1024]
    assert path.read_bytes() == payload


def test_save_upload_stream_rejects_limit_plus_one_without_publishing(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    with pytest.raises(ValueError, match="3 bytes"):
        storage.save_upload_stream("clip.bin", BytesIO(b"1234"), 3)

    assert list((tmp_path / "uploads").iterdir()) == []


def test_save_upload_stream_removes_temporary_file_after_stream_failure(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    with pytest.raises(OSError, match="injected stream failure"):
        storage.save_upload_stream("clip.bin", FailingStream(b"partial"), 1024)

    assert list((tmp_path / "uploads").iterdir()) == []


def test_save_upload_stream_removes_temporary_file_after_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Storage(tmp_path)

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        storage.save_upload_stream("clip.bin", BytesIO(b"payload"), 1024)

    assert list((tmp_path / "uploads").iterdir()) == []


def test_save_upload_stream_removes_published_file_after_directory_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Storage(tmp_path)
    upload_dir = tmp_path / "uploads"
    open_fd = os.open

    def fail_directory_open(path: str | os.PathLike[str], flags: int, *args, **kwargs) -> int:
        if Path(path) == upload_dir:
            raise OSError("injected directory open failure")
        return open_fd(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail_directory_open)

    with pytest.raises(OSError, match="injected directory open failure"):
        storage.save_upload_stream("clip.bin", BytesIO(b"payload"), 1024)

    assert list(upload_dir.iterdir()) == []


def test_save_upload_stream_removes_published_file_after_directory_fsync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Storage(tmp_path)
    upload_dir = tmp_path / "uploads"
    fsync = os.fsync

    def fail_directory_fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("injected directory fsync failure")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="injected directory fsync failure"):
        storage.save_upload_stream("clip.bin", BytesIO(b"payload"), 1024)

    assert list(upload_dir.iterdir()) == []


def test_save_upload_uses_only_filename_basename(tmp_path: Path) -> None:
    storage = Storage(tmp_path)

    path = storage.save_upload("../../outside.bin", b"payload")

    assert path.parent == tmp_path / "uploads"
    assert path.name.endswith("_outside.bin")
    assert not (tmp_path.parent / "outside.bin").exists()
