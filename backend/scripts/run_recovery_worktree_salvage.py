from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
import ctypes
import errno
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import tarfile
import tempfile
from typing import Any


SCHEMA_VERSION = "recovery-worktree-salvage-v1"
COMMAND_VERSION = "1.0.0"
OUTPUT_FILENAMES = (
    "metadata.json",
    "meaningful-tracked.patch",
    "environment-deletions.json",
    "untracked.tar.gz",
    "checksums.json",
    "comparison.json",
)

_UNMERGED_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
_SUPPORTED_TRACKED_CODES = {
    " M",
    " T",
    " D",
    "M ",
    "T ",
    "D ",
    "A ",
    "AM",
    "AT",
}
_DELETE_CODES = {" D", "D "}
_GLOB_META = frozenset("*?[]")
_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SECURE_PATH_PRIMITIVES_AVAILABLE = (
    all(
        function in os.supports_dir_fd
        for function in (os.open, os.stat, os.readlink, os.mkdir, os.rmdir, os.unlink)
    )
    and os.listdir in os.supports_fd
    and os.stat in os.supports_follow_symlinks
    and bool(getattr(os, "O_NOFOLLOW", 0))
    and bool(getattr(os, "O_DIRECTORY", 0))
    and bool(getattr(os, "O_NONBLOCK", 0))
)


class SalvageError(ValueError):
    """Raised when worktree evidence cannot be salvaged without guessing."""


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value:
        raise SalvageError(f"unsafe repository path: {value!r}")
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or str(candidate) != value
    ):
        raise SalvageError(f"unsafe repository path: {value!r}")
    return value


def _git(
    cwd: Path,
    *args: str,
    input_bytes: bytes | None = None,
    allow_failure: bool = False,
    environment_overrides: Mapping[str, str] | None = None,
) -> bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    if environment_overrides is not None:
        environment.update(environment_overrides)
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(cwd), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    if result.returncode and not allow_failure:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SalvageError(f"Git command failed ({' '.join(args)}): {detail}")
    if allow_failure and result.returncode:
        return b""
    return result.stdout


def _decode_utf8(value: bytes, label: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SalvageError(f"{label} is not valid UTF-8") from exc


def _canonical_existing(value: Path, label: str) -> Path:
    try:
        return Path(value).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SalvageError(f"{label} does not exist or cannot be canonicalized: {value}") from exc


def _canonical_output(value: Path) -> Path:
    try:
        return Path(value).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise SalvageError(f"output directory cannot be canonicalized: {value}") from exc


def _canonical_git_path(worktree: Path, raw_value: bytes, label: str) -> Path:
    path = Path(_decode_utf8(raw_value, label).strip())
    if not path.is_absolute():
        path = worktree / path
    return _canonical_existing(path, label)


def _parse_worktree_list(data: bytes) -> list[dict[str, str]]:
    if not data.endswith(b"\0"):
        raise SalvageError("Git worktree list is not NUL terminated")
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for field_bytes in data.split(b"\0"):
        if not field_bytes:
            if current:
                records.append(current)
                current = {}
            continue
        field = _decode_utf8(field_bytes, "Git worktree record")
        key, separator, value = field.partition(" ")
        if key == "detached" and not separator:
            current["detached"] = "true"
        elif separator and key in {"worktree", "HEAD", "branch", "locked", "prunable"}:
            if key in current:
                raise SalvageError(f"duplicate Git worktree field: {key}")
            current[key] = value
        else:
            raise SalvageError(f"unsupported Git worktree record: {field!r}")
    if current:
        records.append(current)
    if not records or any("worktree" not in row or "HEAD" not in row for row in records):
        raise SalvageError("incomplete Git worktree registration data")
    seen: set[Path] = set()
    for row in records:
        path = _canonical_existing(Path(row["worktree"]), "registered worktree")
        if path in seen:
            raise SalvageError(f"duplicate registered worktree: {path}")
        seen.add(path)
        row["worktree"] = str(path)
    return records


def _parse_status(data: bytes) -> list[dict[str, str]]:
    if data and not data.endswith(b"\0"):
        raise SalvageError("porcelain status is not NUL terminated")
    raw_rows = data[:-1].split(b"\0") if data else []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_rows:
        if len(raw) < 4 or raw[2:3] != b" ":
            raise SalvageError("unsupported status or rename shape")
        code = _decode_utf8(raw[:2], "porcelain status code")
        if code in _UNMERGED_CODES or "U" in code:
            raise SalvageError(f"unmerged status is unsafe to salvage: {code!r}")
        if "R" in code or "C" in code:
            raise SalvageError(f"rename/copy status is unsupported: {code!r}")
        if code != "??" and code not in _SUPPORTED_TRACKED_CODES:
            raise SalvageError(f"unsupported porcelain status: {code!r}")
        path = _validate_repo_path(_decode_utf8(raw[3:], "porcelain status path"))
        if path in seen:
            raise SalvageError(f"duplicate porcelain status path: {path}")
        seen.add(path)
        rows.append({"code": code, "path": path})
    return rows


def _status_bytes(worktree: Path) -> bytes:
    return _git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all")


def _validate_symlink_target(member_path: str, target: str) -> str:
    if not target or "\0" in target or "\\" in target:
        raise SalvageError(f"unsafe symlink target for {member_path}: {target!r}")
    target_path = PurePosixPath(target)
    if target_path.is_absolute():
        raise SalvageError(f"unsafe symlink target for {member_path}: {target!r}")
    resolved_parts = list(PurePosixPath(member_path).parent.parts)
    for part in target_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved_parts:
                raise SalvageError(f"escaping symlink target for {member_path}: {target!r}")
            resolved_parts.pop()
        else:
            resolved_parts.append(part)
    return target


def _is_ignored(worktree: Path, relative_path: str) -> bool:
    encoded = relative_path.encode("utf-8") + b"\0"
    return (
        _git(
            worktree,
            "check-ignore",
            "-z",
            "--stdin",
            input_bytes=encoded,
            allow_failure=True,
        )
        == encoded
    )


def _reject_nonignored_special_files(worktree: Path) -> None:
    for directory, directory_names, file_names in os.walk(worktree, followlinks=False):
        directory_path = Path(directory)
        kept_directories: list[str] = []
        for name in directory_names:
            candidate = directory_path / name
            relative = candidate.relative_to(worktree).as_posix()
            try:
                mode = candidate.lstat().st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(mode) and not _is_ignored(worktree, relative):
                kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in [*directory_names, *file_names]:
            candidate = directory_path / name
            relative = candidate.relative_to(worktree).as_posix()
            _validate_repo_path(relative)
            try:
                mode = candidate.lstat().st_mode
            except FileNotFoundError:
                continue
            type_name = (
                "FIFO"
                if stat.S_ISFIFO(mode)
                else "socket"
                if stat.S_ISSOCK(mode)
                else "device"
                if stat.S_ISCHR(mode) or stat.S_ISBLK(mode)
                else None
            )
            if type_name is not None and not _is_ignored(worktree, relative):
                raise SalvageError(f"unsupported non-ignored {type_name}: {relative}")


def _blob_id(worktree: Path, data: bytes) -> str:
    value = _decode_utf8(_git(worktree, "hash-object", "--stdin", input_bytes=data), "blob ID")
    value = value.strip()
    if not _OBJECT_ID.fullmatch(value):
        raise SalvageError("Git returned an invalid blob ID")
    return value


def _require_secure_path_primitives() -> None:
    if not _SECURE_PATH_PRIMITIVES_AVAILABLE:
        raise SalvageError("secure descriptor-relative no-follow path primitives are unavailable")


def _stat_signature(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _open_parent_fd(root: Path, relative_path: str) -> tuple[int | None, str]:
    _require_secure_path_primitives()
    parts = PurePosixPath(_validate_repo_path(relative_path)).parts
    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        current_fd = os.open(os.fspath(root), directory_flags)
    except OSError as exc:
        raise SalvageError(f"cannot securely open worktree root for {relative_path}: {exc}") from exc
    try:
        for component in parts[:-1]:
            try:
                next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            except FileNotFoundError:
                os.close(current_fd)
                return None, parts[-1]
            except OSError as exc:
                raise SalvageError(
                    f"path changed or has unsafe parent while opening {relative_path}: {exc}"
                ) from exc
            os.close(current_fd)
            current_fd = next_fd
        return current_fd, parts[-1]
    except BaseException:
        os.close(current_fd)
        raise


def _read_regular_fd(parent_fd: int, name: str, relative_path: str) -> tuple[os.stat_result, bytes]:
    file_flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        file_fd = os.open(name, file_flags, dir_fd=parent_fd)
    except OSError as exc:
        raise SalvageError(
            f"path changed or no-follow open failed for {relative_path}: {exc}"
        ) from exc
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise SalvageError(f"path changed from regular file: {relative_path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_fd)
        if _stat_signature(before) != _stat_signature(after):
            raise SalvageError(f"regular file changed while reading: {relative_path}")
        data = b"".join(chunks)
        if len(data) != before.st_size:
            raise SalvageError(f"regular file size changed while reading: {relative_path}")
        return before, data
    finally:
        os.close(file_fd)


def _path_snapshot(
    root: Path, relative_path: str, *, hash_worktree: Path
) -> tuple[dict[str, object], bytes | None]:
    parent_fd, name = _open_parent_fd(root, relative_path)
    if parent_fd is None:
        return {"type": "missing"}, None
    try:
        try:
            classified = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return {"type": "missing"}, None
        except OSError as exc:
            raise SalvageError(f"cannot classify dirty path {relative_path}: {exc}") from exc
        if stat.S_ISREG(classified.st_mode):
            opened, data = _read_regular_fd(parent_fd, name, relative_path)
            if _stat_signature(classified) != _stat_signature(opened):
                raise SalvageError(f"regular file changed before reading: {relative_path}")
            return (
                {
                    "type": "regular",
                    "mode": stat.S_IMODE(opened.st_mode),
                    "size": len(data),
                    "sha256": _sha256(data),
                    "gitBlobId": _blob_id(hash_worktree, data),
                },
                data,
            )
        if stat.S_ISLNK(classified.st_mode):
            try:
                target = os.readlink(name, dir_fd=parent_fd)
                verified = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                target_bytes = target.encode("utf-8")
            except (OSError, UnicodeEncodeError) as exc:
                raise SalvageError(f"cannot securely read UTF-8 symlink {relative_path}: {exc}") from exc
            if _stat_signature(classified) != _stat_signature(verified):
                raise SalvageError(f"symlink changed while reading: {relative_path}")
            _validate_symlink_target(relative_path, target)
            return (
                {
                    "type": "symlink",
                    "mode": stat.S_IMODE(verified.st_mode),
                    "size": len(target_bytes),
                    "sha256": _sha256(target_bytes),
                    "gitBlobId": _blob_id(hash_worktree, target_bytes),
                    "linkTarget": target,
                },
                None,
            )
        type_name = (
            "FIFO"
            if stat.S_ISFIFO(classified.st_mode)
            else "socket"
            if stat.S_ISSOCK(classified.st_mode)
            else "device"
            if stat.S_ISCHR(classified.st_mode) or stat.S_ISBLK(classified.st_mode)
            else "directory"
            if stat.S_ISDIR(classified.st_mode)
            else "unknown"
        )
        raise SalvageError(f"unsupported dirty path type {type_name}: {relative_path}")
    finally:
        os.close(parent_fd)


def _path_state(root: Path, relative_path: str, *, hash_worktree: Path) -> dict[str, object]:
    state, _ = _path_snapshot(root, relative_path, hash_worktree=hash_worktree)
    return state


def _capture_path_snapshots(
    worktree: Path, paths: Sequence[str]
) -> dict[str, tuple[dict[str, object], bytes | None]]:
    ordered = sorted(paths)
    if len(ordered) != len(set(ordered)):
        raise SalvageError("duplicate path requested for descriptor snapshot")
    return {
        path: _path_snapshot(worktree, path, hash_worktree=worktree)
        for path in ordered
    }


def _index_state(worktree: Path) -> dict[str, object]:
    raw_path = _decode_utf8(_git(worktree, "rev-parse", "--git-path", "index"), "index path")
    index_path = Path(raw_path.strip())
    if not index_path.is_absolute():
        index_path = worktree / index_path
    index_path = _canonical_existing(index_path, "Git index")
    data = index_path.read_bytes()
    info = index_path.stat()
    return {
        "absolutePath": str(index_path),
        "mode": stat.S_IMODE(info.st_mode),
        "size": len(data),
        "sha256": _sha256(data),
    }


def _source_fingerprint(
    worktree: Path,
    status_data: bytes | None = None,
    status_rows: Sequence[Mapping[str, str]] | None = None,
    path_snapshots: Mapping[str, tuple[Mapping[str, object], bytes | None]] | None = None,
) -> dict[str, object]:
    if status_data is None:
        status_data = _status_bytes(worktree)
    if status_rows is None:
        status_rows = _parse_status(status_data)
    ordered_paths = sorted(row["path"] for row in status_rows)
    if path_snapshots is None:
        path_snapshots = _capture_path_snapshots(worktree, ordered_paths)
    if set(path_snapshots) != set(ordered_paths):
        raise SalvageError("fingerprint snapshots do not exactly match dirty paths")
    dirty_paths = {path: dict(path_snapshots[path][0]) for path in ordered_paths}
    branch_bytes = _git(worktree, "symbolic-ref", "-q", "HEAD", allow_failure=True)
    branch_ref = _decode_utf8(branch_bytes, "branch ref").strip() or None
    fingerprint: dict[str, object] = {
        "head": _decode_utf8(_git(worktree, "rev-parse", "HEAD"), "HEAD").strip(),
        "branchRef": branch_ref,
        "detached": branch_ref is None,
        "index": _index_state(worktree),
        "porcelainStatusNulSha256": _sha256(status_data),
        "dirtyPaths": dirty_paths,
    }
    digest_payload = _json_bytes(fingerprint)
    fingerprint["fingerprintSha256"] = _sha256(digest_payload)
    return fingerprint


def _is_environment_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool(parts) and (
        parts[0] in {".venv", "venv", "node_modules"}
        or ".venv" in parts
        or "venv" in parts
        or "node_modules" in parts
    )


def _head_blob_records(worktree: Path, paths: Sequence[str]) -> list[dict[str, object]]:
    if not paths:
        return []
    requested = set(paths)
    tree_records: dict[str, tuple[str, str, str]] = {}
    output = _git(worktree, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    if output and not output.endswith(b"\0"):
        raise SalvageError("HEAD tree listing is not NUL terminated")
    for raw_row in output[:-1].split(b"\0") if output else []:
        metadata, separator, raw_path = raw_row.partition(b"\t")
        path = _decode_utf8(raw_path, "HEAD tree path")
        if path not in requested:
            continue
        fields = metadata.split(b" ")
        if not separator or len(fields) != 3 or path in tree_records:
            raise SalvageError(f"invalid or duplicate HEAD tree record: {path}")
        mode, object_type, object_id = (
            _decode_utf8(value, "HEAD tree field") for value in fields
        )
        if object_type != "blob" or not _OBJECT_ID.fullmatch(object_id):
            raise SalvageError(f"environment deletion does not reference a blob: {path}")
        tree_records[path] = (mode, object_type, object_id)
    missing = requested - set(tree_records)
    if missing:
        raise SalvageError(
            f"missing HEAD objects for environment deletions: {sorted(missing)!r}"
        )

    object_ids = sorted({row[2] for row in tree_records.values()})
    batch_input = b"".join(object_id.encode("ascii") + b"\n" for object_id in object_ids)
    batch_output = _git(
        worktree,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_bytes=batch_input,
    )
    batch_rows = batch_output.splitlines()
    if len(batch_rows) != len(object_ids):
        raise SalvageError("Git batch object response count mismatch")
    object_sizes: dict[str, int] = {}
    for expected_id, raw_row in zip(object_ids, batch_rows, strict=True):
        fields = raw_row.split(b" ")
        if len(fields) != 3:
            raise SalvageError(f"invalid Git batch object response for {expected_id}")
        object_id, object_type, size_text = (
            _decode_utf8(value, "Git batch object field") for value in fields
        )
        try:
            size = int(size_text)
        except ValueError as exc:
            raise SalvageError(f"invalid HEAD blob size for {expected_id}") from exc
        if object_id != expected_id or object_type != "blob" or size < 0:
            raise SalvageError(f"missing or invalid reachable HEAD blob: {expected_id}")
        object_sizes[object_id] = size

    records: list[dict[str, object]] = []
    for path in sorted(paths):
        mode, object_type, object_id = tree_records[path]
        records.append(
            {
                "path": path,
                "headMode": mode,
                "headObjectType": object_type,
                "headBlobId": object_id,
                "headBlobSize": object_sizes[object_id],
            }
        )
    return records


def _snapshot_blob_bytes(
    path: str, snapshot: tuple[Mapping[str, object], bytes | None]
) -> bytes | None:
    state, data = snapshot
    if state["type"] == "missing":
        return None
    if state["type"] == "regular":
        if data is None:
            raise SalvageError(f"regular tracked snapshot has no bytes: {path}")
        return data
    if state["type"] == "symlink":
        target = state.get("linkTarget")
        if not isinstance(target, str):
            raise SalvageError(f"symlink tracked snapshot has no target: {path}")
        return target.encode("utf-8")
    raise SalvageError(f"unsupported meaningful tracked snapshot type: {path}")


def _snapshot_index_mode(path: str, state: Mapping[str, object]) -> str | None:
    type_name = state.get("type")
    if type_name == "missing":
        return None
    if type_name == "symlink":
        return "120000"
    if type_name != "regular":
        raise SalvageError(f"unsupported meaningful tracked snapshot type: {path}")
    mode = state.get("mode")
    if mode not in {0o644, 0o755}:
        raise SalvageError(f"unsupported tracked regular-file mode for {path}: {mode!r}")
    return "100755" if mode == 0o755 else "100644"


def _temporary_git_environment(
    common_dir: Path, object_dir: Path, index_path: Path
) -> dict[str, str]:
    object_dir.mkdir(mode=0o700)
    return {
        "GIT_INDEX_FILE": str(index_path),
        "GIT_OBJECT_DIRECTORY": str(object_dir),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(common_dir / "objects"),
    }


def _verify_snapshot_index(
    worktree: Path,
    environment: Mapping[str, str],
    paths: Sequence[str],
    snapshots: Mapping[str, tuple[Mapping[str, object], bytes | None]],
) -> None:
    raw = _git(
        worktree,
        "ls-files",
        "--stage",
        "-z",
        "--",
        *paths,
        environment_overrides=environment,
    )
    rows: dict[str, tuple[str, str]] = {}
    for record in raw[:-1].split(b"\0") if raw else []:
        metadata, separator, raw_path = record.partition(b"\t")
        fields = metadata.split(b" ")
        path = _validate_repo_path(_decode_utf8(raw_path, "temporary index path"))
        if not separator or len(fields) != 3 or fields[2] != b"0" or path in rows:
            raise SalvageError(f"invalid temporary index record: {path}")
        rows[path] = (
            _decode_utf8(fields[0], "temporary index mode"),
            _decode_utf8(fields[1], "temporary index blob"),
        )
    for path in paths:
        state = snapshots[path][0]
        expected_mode = _snapshot_index_mode(path, state)
        if expected_mode is None:
            if path in rows:
                raise SalvageError(f"deleted path remains in patch reconstruction: {path}")
            continue
        expected_blob = state.get("gitBlobId")
        if rows.get(path) != (expected_mode, expected_blob):
            raise SalvageError(f"patch reconstruction differs from captured snapshot: {path}")
        reconstructed = _git(
            worktree,
            "cat-file",
            "blob",
            str(expected_blob),
            environment_overrides=environment,
        )
        if reconstructed != _snapshot_blob_bytes(path, snapshots[path]):
            raise SalvageError(f"patch reconstruction bytes differ from snapshot: {path}")


def _meaningful_patch(
    worktree: Path,
    common_dir: Path,
    head: str,
    paths: Sequence[str],
    snapshots: Mapping[str, tuple[Mapping[str, object], bytes | None]],
) -> bytes:
    if not paths:
        return b""
    ordered = sorted(paths)
    if set(snapshots) != set(ordered):
        raise SalvageError("meaningful tracked snapshots do not exactly match paths")
    with tempfile.TemporaryDirectory(prefix="salvage-patch-") as temporary:
        temp_root = Path(temporary)
        environment = _temporary_git_environment(
            common_dir, temp_root / "objects", temp_root / "index"
        )
        _git(worktree, "read-tree", head, environment_overrides=environment)
        for path in ordered:
            state = snapshots[path][0]
            index_mode = _snapshot_index_mode(path, state)
            data = _snapshot_blob_bytes(path, snapshots[path])
            if index_mode is None:
                _git(
                    worktree,
                    "update-index",
                    "--force-remove",
                    "--",
                    path,
                    environment_overrides=environment,
                )
                continue
            object_id = _decode_utf8(
                _git(
                    worktree,
                    "hash-object",
                    "-w",
                    "--stdin",
                    input_bytes=data,
                    environment_overrides=environment,
                ),
                "temporary snapshot blob ID",
            ).strip()
            if object_id != state.get("gitBlobId"):
                raise SalvageError(f"temporary snapshot blob mismatch: {path}")
            _git(
                worktree,
                "update-index",
                "--add",
                "--cacheinfo",
                index_mode,
                object_id,
                path,
                environment_overrides=environment,
            )
        changed = _git(
            worktree,
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--no-ext-diff",
            "--no-renames",
            head,
            "--",
            *ordered,
            environment_overrides=environment,
        )
        changed_paths = [
            _validate_repo_path(_decode_utf8(value, "diff path"))
            for value in (changed[:-1].split(b"\0") if changed else [])
        ]
        if changed_paths != ordered:
            raise SalvageError("meaningful tracked diff does not exactly match status paths")
        patch = _git(
            worktree,
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            head,
            "--",
            *ordered,
            environment_overrides=environment,
        )

        verification_environment = _temporary_git_environment(
            common_dir, temp_root / "verify-objects", temp_root / "verify-index"
        )
        _git(worktree, "read-tree", head, environment_overrides=verification_environment)
        _git(
            worktree,
            "apply",
            "--cached",
            "--binary",
            "--whitespace=nowarn",
            "-",
            input_bytes=patch,
            environment_overrides=verification_environment,
        )
        _verify_snapshot_index(
            worktree, verification_environment, ordered, snapshots
        )
        return patch


def _archive_record(
    path: str, snapshot: tuple[Mapping[str, object], bytes | None]
) -> tuple[dict[str, object], bytes | None]:
    state, data = snapshot
    if state["type"] == "missing":
        raise SalvageError(f"untracked path disappeared during salvage: {path}")
    record = {key: value for key, value in state.items() if key != "gitBlobId"}
    record["path"] = path
    return record, data


def _build_untracked_archive(
    worktree: Path,
    paths: Sequence[str],
    path_snapshots: Mapping[str, tuple[Mapping[str, object], bytes | None]] | None = None,
) -> tuple[bytes, list[dict[str, object]]]:
    ordered_paths = sorted(paths)
    if path_snapshots is None:
        path_snapshots = _capture_path_snapshots(worktree, ordered_paths)
    if set(path_snapshots) != set(ordered_paths):
        raise SalvageError("archive snapshots do not exactly match untracked paths")
    records_with_data = [
        _archive_record(path, path_snapshots[path]) for path in ordered_paths
    ]
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for record, data in records_with_data:
                info = tarfile.TarInfo(str(record["path"]))
                info.mode = int(record["mode"])
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                if record["type"] == "regular":
                    assert data is not None
                    info.type = tarfile.REGTYPE
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
                elif record["type"] == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.size = 0
                    info.linkname = str(record["linkTarget"])
                    archive.addfile(info)
                else:
                    raise SalvageError(f"unsupported archive member type: {record['type']}")
    records = [record for record, _ in records_with_data]
    archive_bytes = buffer.getvalue()
    _verify_archive(archive_bytes, records)
    return archive_bytes, records


def _verify_archive(data: bytes, expected: Sequence[Mapping[str, object]]) -> None:
    expected_by_path = {str(row["path"]): row for row in expected}
    if len(expected_by_path) != len(expected):
        raise SalvageError("duplicate expected archive path")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            actual_names = [_validate_repo_path(member.name) for member in members]
            if len(actual_names) != len(set(actual_names)):
                raise SalvageError("duplicate archive member path")
            if actual_names != sorted(expected_by_path):
                raise SalvageError("archive member paths do not match untracked paths")
            for member in members:
                expected_row = expected_by_path[member.name]
                if member.mode != expected_row["mode"]:
                    raise SalvageError(f"archive mode mismatch: {member.name}")
                if expected_row["type"] == "regular":
                    if not member.isreg() or member.size != expected_row["size"]:
                        raise SalvageError(f"archive regular-file metadata mismatch: {member.name}")
                    extracted = archive.extractfile(member)
                    if extracted is None or _sha256(extracted.read()) != expected_row["sha256"]:
                        raise SalvageError(f"archive regular-file checksum mismatch: {member.name}")
                elif expected_row["type"] == "symlink":
                    try:
                        link_bytes = member.linkname.encode("utf-8")
                    except UnicodeEncodeError as exc:
                        raise SalvageError(f"archive symlink target is not UTF-8: {member.name}") from exc
                    _validate_symlink_target(member.name, member.linkname)
                    if (
                        not member.issym()
                        or member.linkname != expected_row["linkTarget"]
                        or len(link_bytes) != expected_row["size"]
                        or _sha256(link_bytes) != expected_row["sha256"]
                    ):
                        raise SalvageError(f"archive symlink metadata mismatch: {member.name}")
                else:
                    raise SalvageError(f"unsupported verified archive type: {member.name}")
    except (tarfile.TarError, OSError) as exc:
        raise SalvageError(f"cannot verify untracked archive: {exc}") from exc


def _read_supersessions(path: Path | None) -> tuple[list[dict[str, str]], str | None]:
    if path is None:
        return [], None
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SalvageError(f"cannot read supersession input: {exc}") from exc
    if not isinstance(value, list):
        raise SalvageError("supersession input must be a JSON array")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {
            "path",
            "replacementCommit",
            "replacementPath",
        }:
            raise SalvageError("invalid supersession record fields")
        source_path = _validate_repo_path(item["path"]) if isinstance(item["path"], str) else ""
        replacement_path = (
            _validate_repo_path(item["replacementPath"])
            if isinstance(item["replacementPath"], str)
            else ""
        )
        commit = item["replacementCommit"]
        if source_path in seen:
            raise SalvageError(f"duplicate supersession path: {source_path}")
        seen.add(source_path)
        if not isinstance(commit, str) or not _OBJECT_ID.fullmatch(commit):
            raise SalvageError(f"invalid explicit replacement commit for supersession: {source_path}")
        records.append(
            {
                "path": source_path,
                "replacementCommit": commit,
                "replacementPath": replacement_path,
            }
        )
    return sorted(records, key=lambda row: row["path"]), _sha256(raw)


def _replacement_evidence(
    repository: Path, record: Mapping[str, str]
) -> dict[str, str]:
    commit = record["replacementCommit"]
    path = record["replacementPath"]
    try:
        _git(repository, "cat-file", "-e", f"{commit}^{{commit}}")
    except SalvageError as exc:
        raise SalvageError(f"replacement commit object does not exist: {commit}") from exc
    resolved = _decode_utf8(
        _git(repository, "rev-parse", "--verify", f"{commit}^{{commit}}"), "replacement commit"
    ).strip()
    if resolved != commit:
        raise SalvageError(f"replacement commit is not canonical: {commit}")
    tree = _git(repository, "ls-tree", "-z", commit, "--", path)
    rows = tree[:-1].split(b"\0") if tree.endswith(b"\0") else []
    if len(rows) != 1:
        raise SalvageError(f"replacement path has no unique object at commit: {path}")
    metadata, separator, raw_path = rows[0].partition(b"\t")
    fields = metadata.split(b" ")
    if not separator or len(fields) != 3 or _decode_utf8(raw_path, "replacement path") != path:
        raise SalvageError(f"invalid replacement tree evidence: {path}")
    _, object_type_bytes, object_id_bytes = fields
    object_type = _decode_utf8(object_type_bytes, "replacement object type")
    object_id = _decode_utf8(object_id_bytes, "replacement blob ID")
    if object_type != "blob" or not _OBJECT_ID.fullmatch(object_id):
        raise SalvageError(f"replacement path is not a blob: {path}")
    _git(repository, "cat-file", "-e", f"{object_id}^{{blob}}")
    return {
        "replacementCommit": commit,
        "replacementPath": path,
        "replacementObjectType": object_type,
        "replacementBlobId": object_id,
    }


def _states_equal(source: Mapping[str, object], comparison: Mapping[str, object]) -> bool:
    if source.get("type") != comparison.get("type"):
        return False
    if source.get("type") == "missing":
        return True
    return all(
        source.get(key) == comparison.get(key)
        for key in ("mode", "size", "sha256", "gitBlobId")
    )


def _comparison_fingerprint(
    comparison_root: Path, paths: Sequence[str]
) -> dict[str, object]:
    status_data = _status_bytes(comparison_root)
    status_rows = _parse_status(status_data)
    dirty_paths = [row["path"] for row in status_rows]
    all_paths = sorted(set(dirty_paths) | set(paths))
    snapshots = _capture_path_snapshots(comparison_root, all_paths)
    fingerprint = _source_fingerprint(
        comparison_root,
        status_data,
        status_rows,
        {path: snapshots[path] for path in dirty_paths},
    )
    fingerprint["comparisonPaths"] = {
        path: dict(snapshots[path][0])
        for path in sorted(paths)
    }
    fingerprint.pop("fingerprintSha256", None)
    fingerprint["fingerprintSha256"] = _sha256(_json_bytes(fingerprint))
    return fingerprint


def _comparison_rows(
    *,
    comparison_root: Path,
    meaningful_paths: Sequence[str],
    source_fingerprint: Mapping[str, object],
    comparison_fingerprint: Mapping[str, object],
    supersessions: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    supersession_by_path = {row["path"]: row for row in supersessions}
    meaningful_set = set(meaningful_paths)
    extras = set(supersession_by_path) - meaningful_set
    if extras:
        raise SalvageError(f"supersession paths are not meaningful dirty paths: {sorted(extras)!r}")
    dirty_states = source_fingerprint.get("dirtyPaths")
    if not isinstance(dirty_states, Mapping):
        raise SalvageError("source fingerprint has no dirty-path states")
    comparison_states = comparison_fingerprint.get("comparisonPaths")
    if not isinstance(comparison_states, Mapping):
        raise SalvageError("comparison fingerprint has no comparison-path states")
    rows: list[dict[str, object]] = []
    for path in sorted(meaningful_paths):
        source_state = dirty_states[path]
        if not isinstance(source_state, Mapping):
            raise SalvageError(f"source state is invalid: {path}")
        comparison_state = comparison_states[path]
        if not isinstance(comparison_state, Mapping):
            raise SalvageError(f"comparison state is invalid: {path}")
        if path in supersession_by_path:
            disposition = "superseded"
            evidence: dict[str, object] = _replacement_evidence(
                comparison_root, supersession_by_path[path]
            )
        elif _states_equal(source_state, comparison_state):
            disposition = "integrated"
            evidence = {
                "sourceType": source_state["type"],
                "comparisonType": comparison_state["type"],
            }
            if source_state["type"] != "missing":
                evidence.update(
                    {
                        "sourceMode": source_state["mode"],
                        "comparisonMode": comparison_state["mode"],
                        "sourceSize": source_state["size"],
                        "comparisonSize": comparison_state["size"],
                        "sourceSha256": source_state["sha256"],
                        "comparisonSha256": comparison_state["sha256"],
                        "sourceBlobId": source_state["gitBlobId"],
                        "comparisonBlobId": comparison_state["gitBlobId"],
                    }
                )
        else:
            disposition = "unique_unresolved"
            evidence = {
                "sourceState": dict(source_state),
                "comparisonState": comparison_state,
            }
        rows.append({"path": path, "disposition": disposition, "evidence": evidence})
    return rows


def _status_counts(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    tracked = [row for row in rows if row["code"] != "??"]
    deleted = sum(row["code"] in _DELETE_CODES for row in tracked)
    modified = sum(row["code"] in {" M", " T", "M ", "T "} for row in tracked)
    return {
        "total": len(rows),
        "tracked": len(tracked),
        "untracked": len(rows) - len(tracked),
        "modified": modified,
        "deleted": deleted,
        "otherTracked": len(tracked) - modified - deleted,
    }


def _verify_rendered_output(
    rendered: Mapping[str, bytes], archive_records: Sequence[Mapping[str, object]]
) -> None:
    if set(rendered) != set(OUTPUT_FILENAMES):
        raise SalvageError("rendered output file set is not exact")
    try:
        checksums = json.loads(rendered["checksums.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SalvageError("invalid rendered checksums") from exc
    expected_names = set(OUTPUT_FILENAMES) - {"checksums.json"}
    if not isinstance(checksums, Mapping) or set(checksums) != {"schemaVersion", "sha256"}:
        raise SalvageError("invalid checksum manifest shape")
    digest_map = checksums["sha256"]
    if not isinstance(digest_map, Mapping) or set(digest_map) != expected_names:
        raise SalvageError("checksum manifest file set mismatch")
    for name in expected_names:
        if digest_map[name] != _sha256(rendered[name]):
            raise SalvageError(f"rendered checksum mismatch: {name}")
    _verify_archive(rendered["untracked.tar.gz"], archive_records)
    for name in ("metadata.json", "environment-deletions.json", "comparison.json"):
        try:
            json.loads(rendered[name].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SalvageError(f"invalid rendered JSON: {name}") from exc


def _directory_flags() -> int:
    _require_secure_path_primitives()
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _open_absolute_directory(path: Path, label: str) -> int:
    if not path.is_absolute():
        raise SalvageError(f"{label} must be absolute: {path}")
    flags = _directory_flags()
    try:
        current_fd = os.open("/", flags)
    except OSError as exc:
        raise SalvageError(f"cannot securely open filesystem root for {label}: {exc}") from exc
    try:
        for component in path.parts[1:]:
            try:
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except OSError as exc:
                raise SalvageError(
                    f"{label} changed, contains a symlink, or is unavailable: {path}"
                ) from exc
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _directory_identity(directory_fd: int) -> tuple[int, int]:
    info = os.fstat(directory_fd)
    if not stat.S_ISDIR(info.st_mode):
        raise SalvageError("pinned output parent is not a directory")
    return info.st_dev, info.st_ino


def _inode_identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode


def _entry_identity(parent_fd: int, name: str) -> tuple[int, int, int] | None:
    try:
        return _inode_identity(os.stat(name, dir_fd=parent_fd, follow_symlinks=False))
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SalvageError(f"cannot securely inspect directory entry {name}: {exc}") from exc


def _require_directory_entry_identity(
    parent_fd: int,
    name: str,
    expected: tuple[int, int, int],
    label: str,
) -> None:
    actual = _entry_identity(parent_fd, name)
    if actual != expected or actual is None or not stat.S_ISDIR(actual[2]):
        raise SalvageError(f"{label} identity or type changed: {name}")


def _assert_output_parent_identity(path: Path, expected: tuple[int, int]) -> None:
    check_fd = _open_absolute_directory(path, "output parent")
    try:
        if _directory_identity(check_fd) != expected:
            raise SalvageError("output parent identity changed during salvage")
    finally:
        os.close(check_fd)


def _target_is_empty_directory(parent_fd: int, name: str) -> bool:
    try:
        classified = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise SalvageError(f"cannot securely inspect output target {name}: {exc}") from exc
    if not stat.S_ISDIR(classified.st_mode):
        raise SalvageError(f"output collision is not an empty directory: {name}")
    try:
        target_fd = os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise SalvageError(f"output target changed during validation: {name}") from exc
    try:
        if _stat_signature(classified) != _stat_signature(os.fstat(target_fd)):
            raise SalvageError(f"output target identity changed during validation: {name}")
        if os.listdir(target_fd):
            raise SalvageError(
                f"nonempty output collision; target must be absent or empty: {name}"
            )
    finally:
        os.close(target_fd)
    return True


def _read_fd_bytes(file_fd: int, name: str) -> bytes:
    before = os.fstat(file_fd)
    if not stat.S_ISREG(before.st_mode):
        raise SalvageError(f"staged output is not a regular file: {name}")
    chunks: list[bytes] = []
    while True:
        chunk = os.read(file_fd, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    after = os.fstat(file_fd)
    data = b"".join(chunks)
    if _stat_signature(before) != _stat_signature(after) or len(data) != before.st_size:
        raise SalvageError(f"staged output changed while reading: {name}")
    return data


def _verify_staged_output(
    staging_fd: int, archive_records: Sequence[Mapping[str, object]]
) -> None:
    if set(os.listdir(staging_fd)) != set(OUTPUT_FILENAMES):
        raise SalvageError("staged output file set is not exact")
    rendered: dict[str, bytes] = {}
    for name in OUTPUT_FILENAMES:
        try:
            file_fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0),
                dir_fd=staging_fd,
            )
        except OSError as exc:
            raise SalvageError(f"cannot securely open staged output {name}: {exc}") from exc
        try:
            rendered[name] = _read_fd_bytes(file_fd, name)
        finally:
            os.close(file_fd)
    _verify_rendered_output(rendered, archive_records)


def _validate_output_location(
    output: Path, source: Path, registered_worktrees: Sequence[Path]
) -> tuple[int, int]:
    if output == Path("/"):
        raise SalvageError("output directory cannot be the filesystem root")
    if output == source or source in output.parents:
        raise SalvageError("output directory cannot be inside the source worktree")
    for worktree in registered_worktrees:
        if output == worktree or worktree in output.parents:
            raise SalvageError(f"output directory cannot be inside a registered worktree: {worktree}")
    parent_fd = _open_absolute_directory(output.parent, "output parent")
    try:
        identity = _directory_identity(parent_fd)
        _target_is_empty_directory(parent_fd, output.name)
        return identity
    finally:
        os.close(parent_fd)


def _load_renameat2() -> Any:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        renameat2 = library.renameat2
    except (AttributeError, OSError) as exc:
        raise SalvageError("atomic no-replace rename primitive is unavailable") from exc
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    return renameat2


def _rename_noreplace(
    source_dir_fd: int,
    source_name: str,
    destination_dir_fd: int,
    destination_name: str,
) -> None:
    renameat2 = _load_renameat2()
    result = renameat2(
        source_dir_fd,
        os.fsencode(source_name),
        destination_dir_fd,
        os.fsencode(destination_name),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY, errno.EISDIR, errno.ENOTDIR}:
        raise SalvageError(f"output collision appeared before publish: {destination_name}")
    raise SalvageError(
        f"atomic no-replace publish failed for {destination_name}: {os.strerror(error_number)}"
    )


def _create_staging_directory(parent_fd: int, output_name: str) -> tuple[str, int]:
    for _ in range(100):
        name = f".{output_name}.salvage-tmp-{secrets.token_hex(8)}"
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        try:
            return name, os.open(name, _directory_flags(), dir_fd=parent_fd)
        except BaseException:
            os.rmdir(name, dir_fd=parent_fd)
            raise
    raise SalvageError("cannot allocate a unique sibling staging directory")


def _write_staged_output(staging_fd: int, rendered: Mapping[str, bytes]) -> None:
    for name in OUTPUT_FILENAMES:
        try:
            file_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=staging_fd,
            )
        except OSError as exc:
            raise SalvageError(f"cannot securely create staged output {name}: {exc}") from exc
        try:
            remaining = memoryview(rendered[name])
            while remaining:
                written = os.write(file_fd, remaining)
                if written <= 0:
                    raise SalvageError(f"short write for staged output: {name}")
                remaining = remaining[written:]
        finally:
            os.close(file_fd)


def _capture_staged_file_identities(staging_fd: int) -> dict[str, tuple[int, int, int]]:
    identities: dict[str, tuple[int, int, int]] = {}
    if set(os.listdir(staging_fd)) != set(OUTPUT_FILENAMES):
        raise SalvageError("staged output file set is not exact")
    for filename in OUTPUT_FILENAMES:
        try:
            info = os.stat(filename, dir_fd=staging_fd, follow_symlinks=False)
        except OSError as exc:
            raise SalvageError(f"cannot securely inspect staged output {filename}: {exc}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise SalvageError(f"staged output is not a regular file: {filename}")
        identities[filename] = _inode_identity(info)
    return identities


def _quarantine_failed_staging(
    parent_fd: int,
    staging_fd: int,
    staging_identity: tuple[int, int, int],
    output: Path,
    staging_name: str,
) -> None:
    if _inode_identity(os.fstat(staging_fd)) != staging_identity:
        candidates = sorted(
            name
            for name in os.listdir(parent_fd)
            if name == staging_name or name == output.name
        )
        raise SalvageError(
            "held staging directory identity changed; preserved candidate entries: "
            f"{[str(output.parent / name) for name in candidates]!r}"
        )
    matches = [
        name
        for name in os.listdir(parent_fd)
        if _entry_identity(parent_fd, name) == staging_identity
    ]
    if len(matches) != 1:
        candidate_names = sorted(
            name
            for name in os.listdir(parent_fd)
            if name == staging_name
            or name == output.name
            or name.startswith(f".{output.name}.salvage-")
        )
        raise SalvageError(
            "cannot identity-bind failed staging directory; preserved candidate entries: "
            f"{[str(output.parent / name) for name in candidate_names]!r}"
        )

    source_name = matches[0]
    for _ in range(100):
        quarantine_name = f".{output.name}.salvage-quarantine-{secrets.token_hex(8)}"
        try:
            _rename_noreplace(parent_fd, source_name, parent_fd, quarantine_name)
        except SalvageError as exc:
            if "collision" in str(exc):
                continue
            raise SalvageError(
                "failed staging directory was preserved at "
                f"{output.parent / source_name}: {exc}"
            ) from exc
        quarantine_path = output.parent / quarantine_name
        if _entry_identity(parent_fd, quarantine_name) != staging_identity:
            raise SalvageError(
                "staging directory changed during quarantine rename; preserved candidates: "
                f"{[str(quarantine_path), str(output.parent / source_name)]!r}"
            )
        raise SalvageError(f"failed salvage retained quarantine: {quarantine_path}")
    raise SalvageError(
        f"failed staging directory was preserved at {output.parent / source_name}; "
        "cannot allocate quarantine name"
    )


def _restore_unexpected_published_entry(
    parent_fd: int,
    output_name: str,
    staging_name: str,
    unexpected_identity: tuple[int, int, int],
) -> None:
    if _entry_identity(parent_fd, staging_name) is not None:
        raise SalvageError(
            "cannot safely restore unexpected published entry because staging name is occupied"
        )
    _rename_noreplace(parent_fd, output_name, parent_fd, staging_name)
    if _entry_identity(parent_fd, staging_name) != unexpected_identity:
        raise SalvageError("unexpected published entry changed during rollback")


def _publish(
    output: Path,
    rendered: Mapping[str, bytes],
    archive_records: Sequence[Mapping[str, object]],
    expected_parent_identity: tuple[int, int],
) -> None:
    _load_renameat2()
    parent_fd = _open_absolute_directory(output.parent, "output parent")
    staging_name: str | None = None
    staging_fd: int | None = None
    staging_identity: tuple[int, int, int] | None = None
    file_identities: dict[str, tuple[int, int, int]] = {}
    success = False
    try:
        if _directory_identity(parent_fd) != expected_parent_identity:
            raise SalvageError("output parent identity changed before publication")
        _assert_output_parent_identity(output.parent, expected_parent_identity)
        staging_name, staging_fd = _create_staging_directory(parent_fd, output.name)
        staging_identity = _inode_identity(os.fstat(staging_fd))
        if not stat.S_ISDIR(staging_identity[2]):
            raise SalvageError("created staging entry is not a directory")
        _write_staged_output(staging_fd, rendered)
        file_identities = _capture_staged_file_identities(staging_fd)
        _verify_staged_output(staging_fd, archive_records)
        _assert_output_parent_identity(output.parent, expected_parent_identity)
        _require_directory_entry_identity(
            parent_fd, staging_name, staging_identity, "verified staging directory"
        )
        if _target_is_empty_directory(parent_fd, output.name):
            try:
                os.rmdir(output.name, dir_fd=parent_fd)
            except OSError as exc:
                raise SalvageError(f"output collision changed before publish: {output}") from exc
        _rename_noreplace(parent_fd, staging_name, parent_fd, output.name)
        published_identity = _entry_identity(parent_fd, output.name)
        if published_identity != staging_identity:
            if published_identity is not None:
                _restore_unexpected_published_entry(
                    parent_fd, output.name, staging_name, published_identity
                )
            raise SalvageError("published staging identity or type changed")
        _verify_staged_output(staging_fd, archive_records)
        if _capture_staged_file_identities(staging_fd) != file_identities:
            raise SalvageError("published staged file identity changed")
        _assert_output_parent_identity(output.parent, expected_parent_identity)
        _require_directory_entry_identity(
            parent_fd, output.name, staging_identity, "published staging directory"
        )
        success = True
    finally:
        try:
            if (
                not success
                and staging_fd is not None
                and staging_identity is not None
                and staging_name is not None
            ):
                _quarantine_failed_staging(
                    parent_fd, staging_fd, staging_identity, output, staging_name
                )
        finally:
            if staging_fd is not None:
                os.close(staging_fd)
            os.close(parent_fd)


def run_recovery_worktree_salvage(
    *,
    worktree: Path,
    output_dir: Path,
    comparison_root: Path,
    supersession_input: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    raw_source = os.fspath(worktree)
    if any(character in raw_source for character in _GLOB_META):
        raise SalvageError(f"source worktree contains unresolved glob metacharacters: {raw_source}")
    source = _canonical_existing(Path(worktree), "source worktree")
    comparison = _canonical_existing(Path(comparison_root), "comparison root")
    output = _canonical_output(Path(output_dir))
    supersession_path = (
        _canonical_existing(Path(supersession_input), "supersession input")
        if supersession_input is not None
        else None
    )

    comparison_top = _canonical_existing(
        Path(_decode_utf8(_git(comparison, "rev-parse", "--show-toplevel"), "repository root").strip()),
        "comparison repository root",
    )
    if comparison != comparison_top:
        raise SalvageError("comparison root must be an exact registered root worktree")
    worktree_records = _parse_worktree_list(
        _git(comparison, "worktree", "list", "--porcelain", "-z")
    )
    registered = [Path(row["worktree"]) for row in worktree_records]
    root_worktree = registered[0]
    if comparison != root_worktree:
        raise SalvageError("comparison root must be the registered current/root worktree")
    if source not in registered:
        raise SalvageError(f"source is not a registered Git worktree: {source}")
    if source == root_worktree:
        raise SalvageError("source worktree cannot be the repository root")
    source_top = _canonical_existing(
        Path(_decode_utf8(_git(source, "rev-parse", "--show-toplevel"), "source root").strip()),
        "source repository root",
    )
    if source != source_top:
        raise SalvageError("source must name the exact registered worktree root")
    source_common = _canonical_git_path(
        source,
        _git(source, "rev-parse", "--git-common-dir"),
        "repository common directory",
    )
    comparison_common = _canonical_git_path(
        comparison,
        _git(comparison, "rev-parse", "--git-common-dir"),
        "comparison common directory",
    )
    if source_common != comparison_common:
        raise SalvageError("source and comparison worktrees do not share a repository common dir")
    output_parent_identity = _validate_output_location(output, source, registered)

    _reject_nonignored_special_files(source)
    status_before = _status_bytes(source)
    rows_before = _parse_status(status_before)
    initial_snapshots = _capture_path_snapshots(
        source, [row["path"] for row in rows_before]
    )
    fingerprint_before = _source_fingerprint(
        source, status_before, rows_before, initial_snapshots
    )
    environment_paths = sorted(
        row["path"]
        for row in rows_before
        if row["code"] in _DELETE_CODES and _is_environment_path(row["path"])
    )
    tracked_paths = [row["path"] for row in rows_before if row["code"] != "??"]
    meaningful_tracked = sorted(set(tracked_paths) - set(environment_paths))
    untracked_paths = sorted(row["path"] for row in rows_before if row["code"] == "??")
    meaningful_paths = sorted(meaningful_tracked + untracked_paths)
    if len(meaningful_paths) != len(set(meaningful_paths)):
        raise SalvageError("duplicate meaningful path")

    environment_records = _head_blob_records(source, environment_paths)
    meaningful_snapshots = {
        path: initial_snapshots[path] for path in meaningful_tracked
    }
    meaningful_snapshot_payload: dict[str, object] = {
        "head": fingerprint_before["head"],
        "paths": {
            path: dict(meaningful_snapshots[path][0]) for path in meaningful_tracked
        },
    }
    meaningful_snapshot_payload["sha256"] = _sha256(
        _json_bytes(meaningful_snapshot_payload)
    )
    patch = _meaningful_patch(
        source,
        source_common,
        str(fingerprint_before["head"]),
        meaningful_tracked,
        meaningful_snapshots,
    )
    archive, archive_records = _build_untracked_archive(
        source,
        untracked_paths,
        {path: initial_snapshots[path] for path in untracked_paths},
    )
    supersessions, supersession_digest = _read_supersessions(supersession_path)
    comparison_fingerprint_before = _comparison_fingerprint(comparison, meaningful_paths)
    comparison_rows = _comparison_rows(
        comparison_root=comparison,
        meaningful_paths=meaningful_paths,
        source_fingerprint=fingerprint_before,
        comparison_fingerprint=comparison_fingerprint_before,
        supersessions=supersessions,
    )

    _reject_nonignored_special_files(source)
    status_after = _status_bytes(source)
    rows_after = _parse_status(status_after)
    fingerprint_after = _source_fingerprint(source, status_after, rows_after)
    if fingerprint_after != fingerprint_before or status_after != status_before:
        raise SalvageError("source worktree changed during salvage")
    comparison_fingerprint_after = _comparison_fingerprint(comparison, meaningful_paths)
    if comparison_fingerprint_after != comparison_fingerprint_before:
        raise SalvageError("comparison root changed during salvage")

    source_record = next(row for row in worktree_records if Path(row["worktree"]) == source)
    comparison_head = str(comparison_fingerprint_before["head"])
    metadata: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "commandVersion": COMMAND_VERSION,
        "source": {
            "absolutePath": str(source),
            "branchRef": fingerprint_before["branchRef"],
            "detached": fingerprint_before["detached"],
            "head": fingerprint_before["head"],
            "registeredHead": source_record["HEAD"],
        },
        "comparison": {
            "absolutePath": str(comparison),
            "head": comparison_head,
            "stateBefore": comparison_fingerprint_before,
            "stateAfter": comparison_fingerprint_after,
        },
        "repositoryCommonDir": str(source_common),
        "porcelainStatus": rows_before,
        "porcelainStatusNulBase64": base64.b64encode(status_before).decode("ascii"),
        "porcelainStatusNulSha256": _sha256(status_before),
        "statusCounts": _status_counts(rows_before),
        "meaningfulTrackedSnapshot": meaningful_snapshot_payload,
        "sourceStateBefore": fingerprint_before,
        "sourceStateAfter": fingerprint_after,
    }
    if generated_at is not None:
        if not isinstance(generated_at, str) or not generated_at:
            raise SalvageError("generated_at must be a non-empty caller-supplied string")
        metadata["generatedAt"] = generated_at
    if supersession_path is not None:
        metadata["supersessionInput"] = {
            "absolutePath": str(supersession_path),
            "sha256": supersession_digest,
        }
    environment_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "deletions": environment_records,
    }
    comparison_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "defaultDisposition": "unique_unresolved",
        "paths": comparison_rows,
    }
    rendered: dict[str, bytes] = {
        "metadata.json": _json_bytes(metadata),
        "meaningful-tracked.patch": patch,
        "environment-deletions.json": _json_bytes(environment_payload),
        "untracked.tar.gz": archive,
        "comparison.json": _json_bytes(comparison_payload),
    }
    checksums = {
        "schemaVersion": SCHEMA_VERSION,
        "sha256": {name: _sha256(rendered[name]) for name in sorted(rendered)},
    }
    rendered["checksums.json"] = _json_bytes(checksums)
    _verify_rendered_output(rendered, archive_records)
    _publish(output, rendered, archive_records, output_parent_identity)
    return {
        "metadata": metadata,
        "environmentDeletions": environment_payload,
        "comparison": comparison_payload,
        "checksums": checksums,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a verified, read-only salvage bundle for one exact Git worktree."
    )
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--comparison-root", type=Path, required=True)
    parser.add_argument("--supersession-input", type=Path)
    parser.add_argument("--generated-at")
    arguments = parser.parse_args(argv)
    run_recovery_worktree_salvage(
        worktree=arguments.worktree,
        output_dir=arguments.output_dir,
        comparison_root=arguments.comparison_root,
        supersession_input=arguments.supersession_input,
        generated_at=arguments.generated_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
