"""Bounded file identity hashing with a metadata-validated persistent cache."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import fcntl


class FileIdentityRecord(TypedDict):
    sha256: str
    size: int
    mtime_ns: int
    inode: int | None


@dataclass(frozen=True)
class FileIdentity:
    sha256: str
    size: int
    mtime_ns: int
    inode: int | None


def stream_sha256(path: Path, *, chunk_size: int = 1 << 20) -> FileIdentity:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise RuntimeError("file changed while hashing")
    return FileIdentity(
        sha256=digest.hexdigest(),
        size=after.st_size,
        mtime_ns=after.st_mtime_ns,
        inode=getattr(after, "st_ino", None),
    )


class HashCache:
    def __init__(self, storage_root: Path):
        self.path = Path(storage_root) / ".hash-cache.json"
        self.lock_path = Path(storage_root) / ".hash-cache.lock"
        self._thread_lock = threading.Lock()

    def identity(self, path: Path) -> FileIdentity:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        key = str(resolved)
        cached = self._load().get(key)
        if cached is not None and (
            cached.get("size"),
            cached.get("mtime_ns"),
            cached.get("inode"),
        ) == (stat.st_size, stat.st_mtime_ns, getattr(stat, "st_ino", None)):
            return FileIdentity(**cached)
        identity = stream_sha256(resolved)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock, self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            payload = self._load()
            payload[key] = {"sha256": identity.sha256, "size": identity.size,
                            "mtime_ns": identity.mtime_ns, "inode": identity.inode}
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, sort_keys=True)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return identity

    def _load(self) -> dict[str, FileIdentityRecord]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}
