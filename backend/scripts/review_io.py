"""Serialized review edits and recoverable, durable JSON publication."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat
import threading
from typing import Any


# ponytail: one process-wide lock; multi-process writers require an OS/file lock.
REVIEW_UPDATE_LOCK = threading.Lock()


class ReviewWriteError(OSError):
    """The edit failed and the prior destination remains visible."""


class ReviewWriteOutcomeUncertain(ReviewWriteError):
    """Rollback failed; inspect the retained backup before any manual retry."""


def _open_parent(path: Path) -> int:
    if ".." in path.parts:
        raise OSError("parent traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        return parent
    except BaseException:
        os.close(parent)
        raise


def read_review_bytes(path: Path) -> bytes:
    """Read a regular overlay without following any symlink or leaking its fd."""
    path = Path(path).absolute()
    parent = _open_parent(path)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("overlay is not a regular file")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                return handle.read()
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Call with REVIEW_UPDATE_LOCK held across the enclosing read/modify/write."""
    path = Path(path).absolute()
    parent = None
    temporary = backup = None
    replaced = uncertain = False
    try:
        parent = _open_parent(path)
        try:
            prior = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            prior = None
        if prior is not None and not stat.S_ISREG(prior.st_mode):
            raise OSError("destination is not a regular file")

        name = f".{path.name}.{secrets.token_hex(16)}.tmp"
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        temporary = name
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        if prior is not None:
            name = f".{path.name}.{secrets.token_hex(16)}.bak"
            os.link(path.name, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            backup = name
            retained = os.stat(backup, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(retained.st_mode) or (retained.st_dev, retained.st_ino) != (prior.st_dev, prior.st_ino):
                raise OSError("destination changed before backup")
            os.fsync(parent)

        os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        temporary = None
        replaced = True
        os.fsync(parent)
        if backup is not None:
            os.unlink(backup, dir_fd=parent)
            backup = None
    except Exception:
        if replaced:
            try:
                if backup is not None:
                    os.replace(backup, path.name, src_dir_fd=parent, dst_dir_fd=parent)
                    backup = None
                else:
                    os.unlink(path.name, dir_fd=parent)
            except OSError:
                uncertain = True
                raise ReviewWriteOutcomeUncertain("review_write_outcome_uncertain_do_not_retry") from None
            try:
                os.fsync(parent)
            except OSError:
                # The prior bytes are visible; the save still returns a write error.
                pass
        raise ReviewWriteError("review_write_failed") from None
    finally:
        try:
            for name in (temporary, None if uncertain else backup):
                if name is not None:
                    try:
                        os.unlink(name, dir_fd=parent)
                    except OSError:
                        # Already returning an error; retain evidence if cleanup is refused.
                        pass
        finally:
            if parent is not None:
                try:
                    os.close(parent)
                except OSError:
                    # Cleanup must not override durable success or the primary safe error.
                    pass
