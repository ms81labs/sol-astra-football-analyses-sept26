"""Provider-neutral local worker for sealed football video bundles.

The canonical request file lives directly in the bundle root. Every other
input is addressed relative to that root by the request and receipt contracts.
Output paths must also be confined beneath the same root.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import sys
from tempfile import TemporaryDirectory
from typing import TextIO

from .release_manifest import load_release_manifest
from .remote_contracts import (
    CompletionReceipt,
    FileEntry,
    JobReceipt,
    JobRequest,
    MAX_PROCESSOR_METADATA_LINE_BYTES,
    MAX_PROCESSOR_RESULT_BYTES,
    MAX_PROCESSOR_ROW_LINE_BYTES,
    MAX_RESULT_BYTES,
    MAX_PROGRESS_EVENTS,
    MAX_PROGRESS_LINE_BYTES,
    MAX_PROGRESS_TOTAL_BYTES,
    PROCESSOR_RESULT_FORMAT,
    ProgressEvent,
    ResultBundle,
    StreamIdentity,
    canonical_json_bytes,
    confined_path,
    load_canonical_json,
    remote_diagnostics_contain_credentials,
    stream_identity,
    validate_completion,
    validate_receipt_files,
    validate_result,
)
from .runtime_options import ProofRuntimeOptions, validate_primary_acquisition_mode


class WorkerError(RuntimeError):
    """Fail-closed worker error with bounded, input-independent messages."""


class WorkerRollbackIndeterminate(WorkerError):
    """Filesystem lifecycle or publication state could not be determined safely."""


_STAGE_PROGRESS = {
    "modelLoad": 5,
    "videoOpenAndHomography": 10,
    "trackingPass": 35,
    "probeObservedPass": 55,
    "recoverySelection": 75,
    "truthLayerFinalize": 90,
    "resultSerialize": 98,
}

LIVE_PROGRESS_PREFIX = "FOOTBALL_ANALYST_PROGRESS "

MAX_PROCESSOR_RESULT_DEPTH = 64
MAX_PROCESSOR_RESULT_KEY_CHARS = 1024
MAX_PROCESSOR_RESULT_STRING_CHARS = 64 * 1024
MAX_PROCESSOR_RESULT_NODES = 20_000_000

_GENERATION_DIR_FD_SUPPORTED = (
    getattr(os, "O_DIRECTORY", None) is not None
    and getattr(os, "O_NOFOLLOW", None) is not None
    and all(
        operation in os.supports_dir_fd
        for operation in (os.open, os.mkdir, os.stat, os.link)
    )
    and all(
        operation in os.supports_follow_symlinks
        for operation in (os.stat, os.link)
    )
)

_MAX_RELATIVE_PATH_CHARS = 1024
_MAX_FILESYSTEM_IDENTITY_COMPONENT = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class _GenerationLayout:
    namespace: PurePosixPath
    generation: PurePosixPath
    result: PurePosixPath
    processor: PurePosixPath
    progress: PurePosixPath
    completion: PurePosixPath


@dataclass(frozen=True, slots=True)
class _OwnedGeneration:
    layout: _GenerationLayout
    root_identity: tuple[int, int]
    namespace_identity: tuple[int, int]
    generation_identity: tuple[int, int]


def _new_generation_id() -> str:
    return secrets.token_hex(16)


def _validated_pure_relative(value: PurePosixPath, label: str) -> PurePosixPath:
    if type(value) is not PurePosixPath:
        raise WorkerError(f"{label} path is unsafe")
    raw = value.as_posix()
    parts = raw.split("/")
    drive_prefix = (
        len(parts[0]) >= 2
        and parts[0][0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        and parts[0][1] == ":"
    )
    if (
        not raw
        or len(raw) > _MAX_RELATIVE_PATH_CHARS
        or raw.startswith(("/", "~"))
        or "\\" in raw
        or "\0" in raw
        or any(part in ("", ".", "..") for part in parts)
        or drive_prefix
        or value.is_absolute()
        or value.as_posix() != raw
    ):
        raise WorkerError(f"{label} path is unsafe")
    return value


def _generation_layout(
    logical_result: PurePosixPath,
    generation_id: str,
) -> _GenerationLayout:
    logical_result = _validated_pure_relative(logical_result, "logical result")
    if (
        not logical_result.name.endswith(".json")
        or not logical_result.name[:-5]
    ):
        raise WorkerError("logical result path is unsafe")
    if (
        type(generation_id) is not str
        or len(generation_id) != 32
        or any(character not in "0123456789abcdef" for character in generation_id)
    ):
        raise WorkerError("generation id is unsafe")
    namespace = logical_result.with_name(f"{logical_result.name}.generations")
    generation = namespace / generation_id
    layout = _GenerationLayout(
        namespace=namespace,
        generation=generation,
        result=generation / "result.json",
        processor=generation / "result.processor-result.jsonl",
        progress=generation / "result.progress.jsonl",
        completion=generation / "completion.json",
    )
    for value in (
        layout.namespace,
        layout.generation,
        layout.result,
        layout.processor,
        layout.progress,
        layout.completion,
    ):
        _validated_pure_relative(value, "generation layout")
    return layout


def _logical_result_for_layout(layout: _GenerationLayout) -> PurePosixPath:
    if type(layout) is not _GenerationLayout or any(
        type(value) is not PurePosixPath
        for value in (
            layout.namespace,
            layout.generation,
            layout.result,
            layout.processor,
            layout.progress,
            layout.completion,
        )
    ):
        raise WorkerError("generation layout is unsafe")
    for value in (
        layout.namespace,
        layout.generation,
        layout.result,
        layout.processor,
        layout.progress,
        layout.completion,
    ):
        _validated_pure_relative(value, "generation layout")
    suffix = ".generations"
    if not layout.namespace.name.endswith(suffix):
        raise WorkerError("generation layout is unsafe")
    logical_name = layout.namespace.name[:-len(suffix)]
    if not logical_name:
        raise WorkerError("generation layout is unsafe")
    logical_result = layout.namespace.with_name(logical_name)
    if layout != _generation_layout(logical_result, layout.generation.name):
        raise WorkerError("generation layout is unsafe")
    return logical_result


def _path_relation(left: PurePosixPath, right: PurePosixPath) -> bool:
    shorter = min(len(left.parts), len(right.parts))
    return left.parts[:shorter] == right.parts[:shorter]


def _validated_reserved_path(value: PurePosixPath, label: str) -> PurePosixPath:
    return _validated_pure_relative(value, label)


def _validated_identity(value: object) -> tuple[int, int]:
    if (
        type(value) is not tuple
        or len(value) != 2
        or any(type(component) is not int for component in value)
        or any(
            component < 0 or component > _MAX_FILESYSTEM_IDENTITY_COMPONENT
            for component in value
        )
    ):
        raise WorkerRollbackIndeterminate("publication ownership is indeterminate")
    return value


def _validate_owned_generation(owned_generation: object) -> _OwnedGeneration:
    if type(owned_generation) is not _OwnedGeneration:
        raise WorkerRollbackIndeterminate("generation ownership is indeterminate")
    try:
        _logical_result_for_layout(owned_generation.layout)
    except WorkerError:
        raise WorkerRollbackIndeterminate("generation ownership is indeterminate") from None
    try:
        _validated_identity(owned_generation.root_identity)
        _validated_identity(owned_generation.namespace_identity)
        _validated_identity(owned_generation.generation_identity)
    except WorkerRollbackIndeterminate:
        raise WorkerRollbackIndeterminate(
            "generation ownership is indeterminate"
        ) from None
    return owned_generation


def _validate_generation_reservations(
    layout: _GenerationLayout,
    completion: PurePosixPath,
    request: PurePosixPath,
    receipt: PurePosixPath,
    sealed_files: tuple[PurePosixPath, ...] | set[PurePosixPath],
) -> None:
    """Purely reject path reservations before any publication mutation."""

    logical_result = _logical_result_for_layout(layout)
    completion = _validated_reserved_path(completion, "completion")
    request = _validated_reserved_path(request, "request")
    receipt = _validated_reserved_path(receipt, "receipt")
    sealed = tuple(_validated_reserved_path(item, "sealed input") for item in sealed_files)
    internal = (layout.result, layout.processor, layout.progress, layout.completion)
    if len(set(internal)) != len(internal):
        raise WorkerError("generation publication paths must be distinct")
    if _path_relation(logical_result, completion):
        raise WorkerError("result and completion paths overlap")
    if _path_relation(layout.namespace, completion):
        raise WorkerError("completion path overlaps generation namespace")
    protected = (request, receipt, *sealed)
    for anchor in (logical_result, completion):
        if any(_path_relation(anchor, item) for item in protected):
            raise WorkerError("output path overlaps a sealed input")
    if any(_path_relation(layout.namespace, item) for item in protected):
        raise WorkerError("generation namespace overlaps a sealed input")


def _require_generation_dir_fd_support() -> None:
    if not _GENERATION_DIR_FD_SUPPORTED:
        raise WorkerRollbackIndeterminate("generation lifecycle is indeterminate")


def _identity(value) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _open_generation_namespace(root_fd: int, namespace: PurePosixPath) -> int:
    current_fd = os.dup(root_fd)
    flags = _publication_open_flags()
    try:
        for part in namespace.parts:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            previous_fd = current_fd
            current_fd = next_fd
            os.close(previous_fd)
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _generation_binding_is_current(
    root_path: Path,
    layout: _GenerationLayout,
    root_identity: tuple[int, int],
    namespace_identity: tuple[int, int],
    generation_identity: tuple[int, int] | None = None,
) -> bool:
    root_fd = namespace_fd = generation_fd = None
    try:
        root_fd = os.open(root_path, _publication_open_flags())
        if _identity(os.fstat(root_fd)) != root_identity:
            return False
        namespace_fd = _open_generation_namespace(root_fd, layout.namespace)
        if _identity(os.fstat(namespace_fd)) != namespace_identity:
            return False
        if generation_identity is not None:
            generation_fd = os.open(
                layout.generation.name,
                _publication_open_flags(),
                dir_fd=namespace_fd,
            )
            if _identity(os.fstat(generation_fd)) != generation_identity:
                return False
        return True
    except Exception:
        return False
    finally:
        for fd in (generation_fd, namespace_fd, root_fd):
            if fd is not None:
                os.close(fd)


def _create_owned_generation(root: Path, layout: _GenerationLayout) -> _OwnedGeneration:
    _require_generation_dir_fd_support()
    _logical_result_for_layout(layout)
    generation_id = layout.generation.name
    root_path = Path(root).resolve(strict=True)
    root_fd = current_fd = generation_fd = None
    try:
        root_fd = os.open(root_path, _publication_open_flags())
        root_identity = _identity(os.fstat(root_fd))
        current_fd = os.dup(root_fd)
        for part in layout.namespace.parts:
            try:
                os.mkdir(part, 0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            else:
                os.fsync(current_fd)
            next_fd = os.open(part, _publication_open_flags(), dir_fd=current_fd)
            previous_fd = current_fd
            current_fd = next_fd
            os.close(previous_fd)
        namespace_identity = _identity(os.fstat(current_fd))
        if not _generation_binding_is_current(
            root_path, layout, root_identity, namespace_identity,
        ):
            raise WorkerRollbackIndeterminate("generation namespace binding is indeterminate")
        try:
            os.mkdir(generation_id, 0o700, dir_fd=current_fd)
        except FileExistsError:
            raise WorkerError("generation id collision") from None
        created_generation_identity = _identity(os.stat(
            generation_id,
            dir_fd=current_fd,
            follow_symlinks=False,
        ))
        os.fsync(current_fd)
        generation_fd = os.open(
            generation_id,
            _publication_open_flags(),
            dir_fd=current_fd,
        )
        generation_identity = _identity(os.fstat(generation_fd))
        if generation_identity != created_generation_identity:
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        if not _generation_binding_is_current(
            root_path,
            layout,
            root_identity,
            namespace_identity,
            generation_identity,
        ):
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        owned = _OwnedGeneration(
            layout,
            root_identity,
            namespace_identity,
            generation_identity,
        )
        return owned
    except (WorkerError, WorkerRollbackIndeterminate):
        raise
    except Exception:
        raise WorkerRollbackIndeterminate("generation creation is indeterminate") from None
    finally:
        if generation_fd is not None:
            try:
                os.close(generation_fd)
            except OSError:
                pass
            generation_fd = None
        for fd in (generation_fd, current_fd, root_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _output_relative(root: Path, path: Path, label: str) -> PurePosixPath:
    try:
        resolved = path.resolve(strict=False)
        relative = resolved.relative_to(root)
    except (OSError, ValueError):
        raise WorkerError(f"{label} must be confined beneath bundle root") from None
    if not relative.parts:
        raise WorkerError(f"{label} must name a file")
    return PurePosixPath(*relative.parts)


def _publication_open_flags() -> int:
    directory = getattr(os, "O_DIRECTORY", None)
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if directory is None or no_follow is None:
        raise WorkerRollbackIndeterminate("publication lifecycle is indeterminate")
    return os.O_RDONLY | directory | no_follow


def _publication_parent_fd(root_fd: int, relative: PurePosixPath) -> int | None:
    flags = _publication_open_flags()
    current_fd = os.dup(root_fd)
    try:
        for part in relative.parts[:-1]:
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except FileNotFoundError:
                os.close(current_fd)
                return None
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _validate_processor_result(value: object) -> None:
    """Validate a large processor JSON graph without copying or recursing."""

    if type(value) is not dict:
        raise WorkerError("processor result is unsafe")
    nodes = 0
    active: set[int] = set()
    stack: list[tuple[str, object, int]] = [("value", value, 0)]
    while stack:
        operation, item, depth = stack.pop()
        if operation == "exit":
            active.remove(id(item))
            continue
        if operation == "dict-items":
            iterator = item
            try:
                key, child = next(iterator)  # type: ignore[arg-type]
            except StopIteration:
                continue
            stack.append(("dict-items", iterator, depth))
            if type(key) is not str:
                raise WorkerError("processor result keys must be strings")
            if (
                len(key) > MAX_PROCESSOR_RESULT_KEY_CHARS
                or "\0" in key
                or remote_diagnostics_contain_credentials({key: None})
            ):
                raise WorkerError("processor result contains an unsafe key")
            stack.append(("value", child, depth + 1))
            continue
        if operation == "list-items":
            iterator = item
            try:
                child = next(iterator)  # type: ignore[arg-type]
            except StopIteration:
                continue
            stack.append(("list-items", iterator, depth))
            stack.append(("value", child, depth + 1))
            continue
        nodes += 1
        if nodes > MAX_PROCESSOR_RESULT_NODES or depth > MAX_PROCESSOR_RESULT_DEPTH:
            raise WorkerError("processor result exceeds complexity limits")
        item_type = type(item)
        if item is None or item_type is bool:
            continue
        if item_type is int:
            if abs(item) > 2**53 - 1:
                raise WorkerError("processor result contains an unsafe integer")
            continue
        if item_type is float:
            if not math.isfinite(item):
                raise WorkerError("processor result contains a non-finite number")
            continue
        if item_type is str:
            if (
                len(item) > MAX_PROCESSOR_RESULT_STRING_CHARS
                or "\0" in item
                or remote_diagnostics_contain_credentials(item)
            ):
                raise WorkerError("processor result contains unsafe text")
            continue
        if item_type not in (dict, list):
            raise WorkerError("processor result contains an unsupported value")
        identity = id(item)
        if identity in active:
            raise WorkerError("processor result contains a cycle")
        active.add(identity)
        stack.append(("exit", item, depth))
        if item_type is dict:
            stack.append(("dict-items", iter(dict.items(item)), depth))
        else:
            stack.append(("list-items", iter(item), depth))


def _write_stream(handle, payload: bytes) -> int:
    return handle.write(payload)


def _write_all(handle, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = _write_stream(handle, payload[offset:])
        remaining = len(payload) - offset
        if (
            isinstance(written, bool)
            or not isinstance(written, int)
            or written <= 0
            or written > remaining
        ):
            raise OSError("short stream write")
        offset += written


def _flush_stream(handle) -> None:
    handle.flush()


def _stream_parent_fd(root_fd: int, relative: PurePosixPath) -> int:
    flags = _publication_open_flags()
    current_fd = os.dup(root_fd)
    try:
        for part in relative.parts[:-1]:
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o700, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _stream_binding_is_current(
    root_path: Path,
    root_fd: int,
    relative: PurePosixPath,
    parent_fd: int,
) -> bool:
    current_root_fd = None
    current_parent_fd = None
    try:
        current_root_fd = os.open(root_path, _publication_open_flags())
        expected_root = os.fstat(root_fd)
        current_root = os.fstat(current_root_fd)
        if (expected_root.st_dev, expected_root.st_ino) != (current_root.st_dev, current_root.st_ino):
            return False
        current_parent_fd = _publication_parent_fd(current_root_fd, relative)
        if current_parent_fd is None:
            return False
        expected_parent = os.fstat(parent_fd)
        current_parent = os.fstat(current_parent_fd)
        return (expected_parent.st_dev, expected_parent.st_ino) == (
            current_parent.st_dev,
            current_parent.st_ino,
        )
    except Exception:
        return False
    finally:
        if current_parent_fd is not None:
            os.close(current_parent_fd)
        if current_root_fd is not None:
            os.close(current_root_fd)


def _same_stream_inode(left, right) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _open_owned_generation_descriptors(
    root: Path,
    owned_generation: _OwnedGeneration,
) -> tuple[int, int, int]:
    """Open the owned generation through verified, no-follow descriptors."""

    owned = _validate_owned_generation(owned_generation)
    root_path = Path(root).resolve(strict=True)
    root_fd = namespace_fd = generation_fd = None
    try:
        root_fd = os.open(root_path, _publication_open_flags())
        if _identity(os.fstat(root_fd)) != owned.root_identity:
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        namespace_fd = _open_generation_namespace(root_fd, owned.layout.namespace)
        if _identity(os.fstat(namespace_fd)) != owned.namespace_identity:
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        generation_fd = os.open(
            owned.layout.generation.name,
            _publication_open_flags(),
            dir_fd=namespace_fd,
        )
        if _identity(os.fstat(generation_fd)) != owned.generation_identity:
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        result = (root_fd, namespace_fd, generation_fd)
        root_fd = namespace_fd = generation_fd = None
        return result
    except (WorkerError, WorkerRollbackIndeterminate):
        raise
    except Exception:
        raise WorkerRollbackIndeterminate("generation binding is indeterminate") from None
    finally:
        for descriptor in (generation_fd, namespace_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _generation_member_name(
    owned_generation: _OwnedGeneration,
    relative: PurePosixPath,
) -> str:
    owned = _validate_owned_generation(owned_generation)
    if type(relative) is not PurePosixPath or relative not in (
        owned.layout.processor,
        owned.layout.progress,
        owned.layout.result,
        owned.layout.completion,
    ):
        raise WorkerError("generation artifact path is unsafe")
    if relative.parent != owned.layout.generation:
        raise WorkerError("generation artifact path is unsafe")
    return relative.name


def _write_generation_stream(
    root: Path,
    owned_generation: _OwnedGeneration,
    relative: PurePosixPath,
    chunks,
    *,
    maximum_bytes: int,
) -> StreamIdentity:
    """Directly create one fixed generation member; retain partial bytes on error."""

    name = _generation_member_name(owned_generation, relative)
    root_path = Path(root).resolve(strict=True)
    root_fd = namespace_fd = generation_fd = file_fd = None
    handle = None
    digest = hashlib.sha256()
    size = 0
    try:
        root_fd, namespace_fd, generation_fd = _open_owned_generation_descriptors(
            root, owned_generation,
        )
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        file_fd = os.open(name, flags, 0o600, dir_fd=generation_fd)
        created = os.fstat(file_fd)
        if not stat.S_ISREG(created.st_mode):
            raise WorkerRollbackIndeterminate("generation artifact identity is indeterminate")
        handle = os.fdopen(file_fd, "wb")
        file_fd = None
        for payload in chunks:
            if type(payload) is not bytes:
                raise WorkerError("stream encoder returned unsafe bytes")
            if len(payload) > maximum_bytes - size:
                raise WorkerError("stream artifact exceeds size limit")
            _write_all(handle, payload)
            digest.update(payload)
            size += len(payload)
        _flush_stream(handle)
        os.fsync(handle.fileno())
        written = os.fstat(handle.fileno())
        if not _same_stream_inode(created, written) or written.st_size != size:
            raise WorkerRollbackIndeterminate("generation artifact identity is indeterminate")
        handle.close()
        handle = None
        os.fsync(generation_fd)
        current = os.stat(name, dir_fd=generation_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(current.st_mode)
            or not _same_stream_inode(created, current)
            or current.st_size != size
        ):
            raise WorkerRollbackIndeterminate("generation artifact identity is indeterminate")
        if not _generation_binding_is_current(
            root_path,
            owned_generation.layout,
            owned_generation.root_identity,
            owned_generation.namespace_identity,
            owned_generation.generation_identity,
        ):
            raise WorkerRollbackIndeterminate("generation binding is indeterminate")
        return StreamIdentity(size, digest.hexdigest())
    except (WorkerError, WorkerRollbackIndeterminate):
        raise
    except Exception:
        raise WorkerError("generation artifact write failed") from None
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if file_fd is not None:
            try:
                os.close(file_fd)
            except OSError:
                pass
        for descriptor in (generation_fd, namespace_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _write_generation_processor(
    root: Path,
    owned_generation: _OwnedGeneration,
    processor_result: object,
) -> FileEntry:
    chunks, _ = _processor_result_v2_chunks(processor_result)
    identity = _write_generation_stream(
        root,
        owned_generation,
        owned_generation.layout.processor,
        chunks,
        maximum_bytes=MAX_PROCESSOR_RESULT_BYTES,
    )
    return FileEntry(
        "result_artifact",
        owned_generation.layout.processor,
        identity.size_bytes,
        identity.sha256,
    )


def _processor_result_v2_chunks(value: object) -> tuple[Iterator[bytes], int]:
    """Return the canonical metadata line and bounded row lines."""

    _validate_processor_result(value)
    metadata = dict(value)
    rows = metadata.pop("rows", None)
    if type(rows) is not list or not rows:
        raise WorkerError("processor result rows are invalid")
    header = _processor_json_line(
        {"schemaVersion": 1, "rowCount": len(rows), "metadata": metadata},
        maximum=MAX_PROCESSOR_METADATA_LINE_BYTES,
    )

    def chunks() -> Iterator[bytes]:
        yield header
        for row in rows:
            if type(row) is not dict:
                raise WorkerError("processor result row is invalid")
            yield _processor_json_line(row, maximum=MAX_PROCESSOR_ROW_LINE_BYTES)

    return chunks(), len(rows)


def _processor_json_line(value: object, *, maximum: int) -> bytes:
    encoded = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > maximum:
        raise WorkerError("processor result line exceeds size limit")
    return encoded


def _write_generation_progress(
    root: Path,
    owned_generation: _OwnedGeneration,
    events: tuple[ProgressEvent, ...],
    job_id: str,
) -> tuple[FileEntry, int]:
    previous_sequence = -1
    previous_progress = -math.inf
    count = 0
    total = 0

    def chunks():
        nonlocal previous_sequence, previous_progress, count, total
        for event in events:
            if type(event) is not ProgressEvent or event.job_id != job_id:
                raise WorkerError("progress event identity mismatch")
            if event.sequence <= previous_sequence or event.progress < previous_progress:
                raise WorkerError("progress event order is invalid")
            if count >= MAX_PROGRESS_EVENTS:
                raise WorkerError("progress event count exceeds limit")
            payload = canonical_json_bytes(event.to_mapping())
            if len(payload) > MAX_PROGRESS_LINE_BYTES:
                raise WorkerError("progress line exceeds limit")
            if len(payload) > MAX_PROGRESS_TOTAL_BYTES - total:
                raise WorkerError("progress total size exceeds limit")
            previous_sequence = event.sequence
            previous_progress = event.progress
            count += 1
            total += len(payload)
            yield payload

    identity = _write_generation_stream(
        root,
        owned_generation,
        owned_generation.layout.progress,
        chunks(),
        maximum_bytes=MAX_PROGRESS_TOTAL_BYTES,
    )
    return (
        FileEntry(
            "result_artifact",
            owned_generation.layout.progress,
            identity.size_bytes,
            identity.sha256,
        ),
        count,
    )


def _write_generation_json(
    root: Path,
    owned_generation: _OwnedGeneration,
    relative: PurePosixPath,
    value: object,
) -> StreamIdentity:
    payload = canonical_json_bytes(value, max_bytes=MAX_RESULT_BYTES)
    return _write_generation_stream(
        root,
        owned_generation,
        relative,
        (payload,),
        maximum_bytes=MAX_RESULT_BYTES,
    )


def _write_generation_completion(
    root: Path,
    owned_generation: _OwnedGeneration,
    completion: CompletionReceipt,
) -> StreamIdentity:
    payload = canonical_json_bytes(completion.to_mapping(), max_bytes=MAX_RESULT_BYTES)
    loaded = CompletionReceipt.from_mapping(json.loads(payload))
    if loaded != completion or canonical_json_bytes(loaded.to_mapping()) != payload:
        raise WorkerError("completion receipt bytes are invalid")
    return _write_generation_stream(
        root,
        owned_generation,
        owned_generation.layout.completion,
        (payload,),
        maximum_bytes=MAX_RESULT_BYTES,
    )


def _validate_generation_snapshot(
    root: Path,
    owned_generation: _OwnedGeneration,
    expected: Mapping[PurePosixPath, StreamIdentity],
    *,
    sealed: bool,
) -> None:
    expected_paths = {
        owned_generation.layout.processor,
        owned_generation.layout.progress,
        owned_generation.layout.result,
        owned_generation.layout.completion,
    }
    if type(expected) is not dict or set(expected) != expected_paths:
        raise WorkerRollbackIndeterminate("generation contents are indeterminate")
    root_fd = namespace_fd = generation_fd = None
    try:
        root_fd, namespace_fd, generation_fd = _open_owned_generation_descriptors(
            root, owned_generation,
        )
        if set(os.listdir(generation_fd)) != {path.name for path in expected_paths}:
            raise WorkerRollbackIndeterminate("generation contents are indeterminate")
        for relative, identity in expected.items():
            if type(identity) is not StreamIdentity:
                raise WorkerRollbackIndeterminate("generation contents are indeterminate")
            file_fd = None
            try:
                file_fd = os.open(
                    relative.name,
                    os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=generation_fd,
                )
                metadata = os.fstat(file_fd)
                if not stat.S_ISREG(metadata.st_mode):
                    raise WorkerRollbackIndeterminate("generation contents are indeterminate")
                if sealed and stat.S_IMODE(metadata.st_mode) != 0o400:
                    raise WorkerRollbackIndeterminate("generation permissions are indeterminate")
                with os.fdopen(file_fd, "rb", closefd=False) as handle:
                    stream_identity(
                        handle,
                        expected_size=identity.size_bytes,
                        expected_sha256=identity.sha256,
                        max_bytes=(
                            MAX_PROCESSOR_RESULT_BYTES
                            if relative == owned_generation.layout.processor
                            else MAX_PROGRESS_TOTAL_BYTES
                            if relative == owned_generation.layout.progress
                            else MAX_RESULT_BYTES
                        ),
                    )
            finally:
                if file_fd is not None:
                    os.close(file_fd)
        if sealed and stat.S_IMODE(os.fstat(generation_fd).st_mode) != 0o500:
            raise WorkerRollbackIndeterminate("generation permissions are indeterminate")
    finally:
        for descriptor in (generation_fd, namespace_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _seal_generation_read_only(
    root: Path,
    owned_generation: _OwnedGeneration,
    expected: Mapping[PurePosixPath, StreamIdentity],
) -> None:
    _validate_generation_snapshot(root, owned_generation, expected, sealed=False)
    root_fd = namespace_fd = generation_fd = None
    file_fds: list[int] = []
    try:
        root_fd, namespace_fd, generation_fd = _open_owned_generation_descriptors(
            root, owned_generation,
        )
        for relative in (
            owned_generation.layout.processor,
            owned_generation.layout.progress,
            owned_generation.layout.result,
            owned_generation.layout.completion,
        ):
            descriptor = os.open(
                relative.name,
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                dir_fd=generation_fd,
            )
            file_fds.append(descriptor)
        for descriptor in file_fds:
            os.fchmod(descriptor, 0o400)
            os.fsync(descriptor)
        os.fchmod(generation_fd, 0o500)
        os.fsync(generation_fd)
        os.fsync(namespace_fd)
    except (WorkerError, WorkerRollbackIndeterminate):
        raise
    except Exception:
        raise WorkerError("generation sealing failed") from None
    finally:
        for descriptor in (*file_fds, generation_fd, namespace_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    _validate_generation_snapshot(root, owned_generation, expected, sealed=True)


def _commit_completion_link(
    root: Path,
    owned_generation: _OwnedGeneration,
    completion_relative: PurePosixPath,
) -> None:
    completion_relative = _validated_reserved_path(completion_relative, "completion")
    root_path = Path(root).resolve(strict=True)
    root_fd = namespace_fd = generation_fd = parent_fd = source_fd = None
    linked = False
    try:
        root_fd, namespace_fd, generation_fd = _open_owned_generation_descriptors(
            root, owned_generation,
        )
        parent_fd = _stream_parent_fd(root_fd, completion_relative)
        if not _stream_binding_is_current(
            root_path, root_fd, completion_relative, parent_fd,
        ):
            raise WorkerRollbackIndeterminate("completion publication is indeterminate")
        source_fd = os.open(
            owned_generation.layout.completion.name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=generation_fd,
        )
        source_before = os.fstat(source_fd)
        if not stat.S_ISREG(source_before.st_mode):
            raise WorkerRollbackIndeterminate("completion publication is indeterminate")
        try:
            os.link(
                owned_generation.layout.completion.name,
                completion_relative.name,
                src_dir_fd=generation_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except Exception as link_error:
            try:
                source_after_error = os.stat(
                    owned_generation.layout.completion.name,
                    dir_fd=generation_fd,
                    follow_symlinks=False,
                )
            except Exception:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            try:
                source_before_identity = _validated_identity(
                    (source_before.st_dev, source_before.st_ino)
                )
                source_after_identity = _validated_identity(
                    (source_after_error.st_dev, source_after_error.st_ino)
                )
                if (
                    type(source_after_error.st_mode) is not int
                    or not stat.S_ISREG(source_after_error.st_mode)
                ):
                    raise WorkerRollbackIndeterminate(
                        "completion publication is indeterminate"
                    )
            except Exception:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            if source_before_identity != source_after_identity:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            try:
                destination_after_error = os.stat(
                    completion_relative.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                raise WorkerError("completion publication failed") from link_error
            except Exception:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            try:
                destination_identity = _validated_identity(
                    (destination_after_error.st_dev, destination_after_error.st_ino)
                )
            except Exception:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            if source_after_identity == destination_identity:
                raise WorkerRollbackIndeterminate(
                    "completion publication is indeterminate"
                ) from link_error
            raise WorkerError("completion marker already exists") from link_error
        linked = True
        try:
            os.fsync(parent_fd)
            source_after = os.stat(
                owned_generation.layout.completion.name,
                dir_fd=generation_fd,
                follow_symlinks=False,
            )
            destination = os.stat(
                completion_relative.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            if (
                not _same_stream_inode(source_before, source_after)
                or not _same_stream_inode(source_after, destination)
                or not stat.S_ISREG(destination.st_mode)
            ):
                raise WorkerRollbackIndeterminate("completion publication is indeterminate")
            if not _stream_binding_is_current(
                root_path, root_fd, completion_relative, parent_fd,
            ):
                raise WorkerRollbackIndeterminate("completion publication is indeterminate")
            if not _generation_binding_is_current(
                root_path,
                owned_generation.layout,
                owned_generation.root_identity,
                owned_generation.namespace_identity,
                owned_generation.generation_identity,
            ):
                raise WorkerRollbackIndeterminate("completion publication is indeterminate")
        except WorkerRollbackIndeterminate:
            raise
        except Exception as error:
            raise WorkerRollbackIndeterminate(
                "completion publication is indeterminate"
            ) from error
    except (WorkerError, WorkerRollbackIndeterminate):
        raise
    except Exception as error:
        if linked:
            raise WorkerRollbackIndeterminate(
                "completion publication is indeterminate"
            ) from error
        raise WorkerError("completion publication failed") from error
    finally:
        for descriptor in (source_fd, parent_fd, generation_fd, namespace_fd, root_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def process_video_input(*args, **kwargs):
    """Load the heavy local CV pipeline only when an already-validated job runs."""

    from .video_pipeline import process_video_input as implementation

    return implementation(*args, **kwargs)


def _match_config(value: Mapping[str, object]):
    from .schemas import MatchConfig

    if set(value) - frozenset(MatchConfig.model_fields):
        raise WorkerError("match config contains unknown fields")
    try:
        return MatchConfig.model_validate(dict(value))
    except Exception:
        raise WorkerError("match config is invalid") from None


def _artifact_references(options: ProofRuntimeOptions) -> tuple[object, ...]:
    return tuple(
        reference
        for reference in (
            options.primary_model,
            options.auxiliary_ball_model,
            options.baseline_guided_rescue_reference,
            options.proposal_selection_truth_seed,
            options.reviewed_positive_anchor_seed,
        )
        if reference is not None
    )


def _materialize_local_options(options: ProofRuntimeOptions, paths_by_id: Mapping[str, Path]) -> dict[str, str | None]:
    validate_primary_acquisition_mode(options.primary_acquisition_mode)
    def resolve(reference) -> str | None:
        if reference is None:
            return None
        path = paths_by_id.get(reference.artifact_id)
        if path is None:
            raise WorkerError("runtime options reference an unsealed artifact")
        return str(path)

    primary = resolve(options.primary_model)
    assert primary is not None
    materialized: dict[str, str | None] = {
        "model_path": primary,
        "primary_model_path": primary,
        "primary_acquisition_mode": options.primary_acquisition_mode,
        "auxiliary_ball_model_profile": options.auxiliary_ball_model_profile,
        "edge_share_repair_profile": options.edge_share_repair_profile,
    }
    for key, reference in (
        ("auxiliary_ball_model_path", options.auxiliary_ball_model),
        ("baseline_guided_rescue_reference_path", options.baseline_guided_rescue_reference),
        ("proposal_selection_truth_seed_path", options.proposal_selection_truth_seed),
        ("reviewed_positive_anchor_seed_path", options.reviewed_positive_anchor_seed),
    ):
        resolved = resolve(reference)
        if resolved is not None:
            materialized[key] = resolved
    return materialized


def _prepare_runtime(
    root: Path,
    receipt: JobReceipt,
    manifest_path: Path,
    temporary_root: Path,
) -> dict[str, str | None]:
    manifest_entry = next(item for item in receipt.files if item.role == "manifest")
    manifest_snapshot = temporary_root / "manifest.json"
    shutil.copyfile(manifest_path, manifest_snapshot)
    with manifest_snapshot.open("rb") as handle:
        stream_identity(
            handle,
            expected_size=manifest_entry.size_bytes,
            expected_sha256=manifest_entry.sha256,
        )
    manifest = load_release_manifest(manifest_snapshot, expected_source_commit=receipt.source_commit)
    if canonical_json_bytes(manifest.runtime_options) != canonical_json_bytes(receipt.requested_runtime_options):
        raise WorkerError("manifest runtime options mismatch")
    try:
        options = ProofRuntimeOptions.from_mapping(receipt.requested_runtime_options)
    except Exception:
        raise WorkerError("runtime options are invalid") from None
    references = _artifact_references(options)
    if any(getattr(reference, "kind", None) != "artifact" for reference in references):
        raise WorkerError("worker accepts only sealed local artifact references")
    referenced_ids = {getattr(reference, "artifact_id", None) for reference in references}
    manifest_ids = {artifact.id for artifact in manifest.artifacts}
    if not referenced_ids <= manifest_ids:
        raise WorkerError("runtime options reference an unsealed artifact")

    receipt_artifacts = tuple(item for item in receipt.files if item.role == "runtime_artifact")
    if len(receipt_artifacts) != len(manifest.artifacts):
        raise WorkerError("sealed runtime artifact set mismatch")
    remaining = list(receipt_artifacts)
    resolver_root = temporary_root / "resolver"
    resolver_root.mkdir()
    for artifact in manifest.artifacts:
        declared_relative = PurePosixPath(artifact.local_relative_path)
        explicit = next((item for item in remaining if item.relative_path == declared_relative), None)
        if explicit is not None:
            if explicit.size_bytes != artifact.size_bytes or explicit.sha256 != artifact.sha256:
                raise WorkerError("sealed runtime artifact identity mismatch")
            entry = explicit
        else:
            matches = sorted(
                (
                    item for item in remaining
                    if item.size_bytes == artifact.size_bytes and item.sha256 == artifact.sha256
                ),
                key=lambda item: item.relative_path.as_posix(),
            )
            if not matches:
                raise WorkerError("sealed runtime artifact identity mismatch")
            entry = matches[0]
        remaining.remove(entry)
        source = confined_path(root, entry.relative_path)
        destination = resolver_root.joinpath(*PurePosixPath(artifact.local_relative_path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        with destination.open("rb") as handle:
            stream_identity(handle, expected_size=artifact.size_bytes, expected_sha256=artifact.sha256)
    if remaining:
        raise WorkerError("sealed runtime artifact set mismatch")
    paths_by_id = {
        artifact.id: resolver_root.joinpath(*PurePosixPath(artifact.local_relative_path).parts)
        for artifact in manifest.artifacts
    }
    return _materialize_local_options(options, paths_by_id)


def _emit_live_progress(event: ProgressEvent, output: TextIO) -> None:
    output.write(
        LIVE_PROGRESS_PREFIX
        + canonical_json_bytes(event.to_mapping()).decode("utf-8")
    )
    output.flush()


def _progress_collector(job_id: str, *, output: TextIO | None = None):
    output = sys.stdout if output is None else output
    events: list[ProgressEvent] = []
    state: dict[str, object] = {"error": False, "progress": 0.0, "total_bytes": 0}

    def callback(payload: object) -> None:
        try:
            if state["error"]:
                return
            if len(events) >= MAX_PROGRESS_EVENTS:
                raise WorkerError("progress event count exceeds limit")
            if not isinstance(payload, Mapping) or remote_diagnostics_contain_credentials(payload):
                raise WorkerError("progress payload is unsafe")
            canonical_json_bytes(payload, max_bytes=MAX_PROGRESS_LINE_BYTES)
            supplied_job = payload.get("jobId")
            if supplied_job is not None and supplied_job != job_id:
                raise WorkerError("progress job mismatch")
            stage_value = payload.get("stage", payload.get("workerStage", "progress"))
            message_value = payload.get("message", payload.get("stageStatus", "progress"))
            progress_value = payload.get("progress")
            if progress_value is None and isinstance(stage_value, str):
                progress_value = _STAGE_PROGRESS.get(stage_value)
            if progress_value is None:
                progress_value = state["progress"]
            event = ProgressEvent(
                1, job_id, len(events) + 1, progress_value, stage_value, message_value,
                datetime.now(timezone.utc),
            )
            if event.progress < state["progress"]:
                raise WorkerError("progress must not decrease")
            event_bytes = canonical_json_bytes(event.to_mapping(), max_bytes=MAX_PROGRESS_LINE_BYTES)
            total_bytes = int(state["total_bytes"]) + len(event_bytes)
            if total_bytes > MAX_PROGRESS_TOTAL_BYTES:
                raise WorkerError("progress total size exceeds limit")
            events.append(event)
            state["progress"] = event.progress
            state["total_bytes"] = total_bytes
            try:
                _emit_live_progress(event, output)
            except Exception:
                pass
        except Exception:
            state["error"] = True

    return events, state, callback


def _validated_progress(events: list[ProgressEvent], state: Mapping[str, object], job_id: str) -> tuple[ProgressEvent, ...]:
    if state["error"]:
        raise WorkerError("progress callback payload failed validation")
    previous_sequence = -1
    previous_progress = -math.inf
    for event in events:
        if event.job_id != job_id or event.sequence <= previous_sequence or event.progress < previous_progress:
            raise WorkerError("progress callback payload failed validation")
        previous_sequence = event.sequence
        previous_progress = event.progress
    return tuple(events)


def run_worker(request_path: Path, result_path: Path, completion_receipt_path: Path) -> None:
    """Run one sealed bundle and commit one immutable-by-policy generation."""

    request_path = Path(request_path).resolve(strict=False)
    root = request_path.parent.resolve(strict=True)
    logical_result_relative = _output_relative(root, Path(result_path), "result path")
    completion_relative = _output_relative(root, Path(completion_receipt_path), "completion receipt path")

    request = JobRequest.from_mapping(load_canonical_json(request_path))
    receipt_path = confined_path(root, request.receipt_path)
    receipt = JobReceipt.from_mapping(load_canonical_json(receipt_path))
    validate_receipt_files(root, request, receipt)
    request_entry = next(item for item in receipt.files if item.role == "job_request")
    request_relative = PurePosixPath(request_path.name)
    if request_entry.relative_path != request_relative:
        raise WorkerError("request path binding mismatch")
    sealed_relatives = {
        request_relative,
        request.receipt_path,
        *(item.relative_path for item in receipt.files),
    }
    layout = _generation_layout(logical_result_relative, _new_generation_id())
    _validate_generation_reservations(
        layout,
        completion_relative,
        request_relative,
        request.receipt_path,
        sealed_relatives,
    )
    _require_generation_dir_fd_support()

    manifest_entry = next(item for item in receipt.files if item.role == "manifest")
    manifest_path = confined_path(root, manifest_entry.relative_path)
    match_config = _match_config(request.config)
    primary_error: Exception | None = None
    exit_error: Exception | None = None
    try:
        with TemporaryDirectory(prefix="football-gpu-worker-", dir=root) as temporary:
            try:
                temporary_root = Path(temporary)
                video_entry = next(item for item in receipt.files if item.role == "input_video")
                video_snapshot = temporary_root / f"input{Path(request.input_video_path.name).suffix}"
                sealed_video = confined_path(root, request.input_video_path)
                os.replace(sealed_video, video_snapshot)
                try:
                    with video_snapshot.open("rb") as handle:
                        stream_identity(
                            handle,
                            expected_size=video_entry.size_bytes,
                            expected_sha256=video_entry.sha256,
                        )
                    runtime_kwargs = _prepare_runtime(root, receipt, manifest_path, temporary_root)
                    progress_events, progress_state, progress_callback = _progress_collector(request.job_id)
                    processor_result = process_video_input(
                        video_snapshot, match_config, **runtime_kwargs,
                        progress_callback=progress_callback, match_id=request.match_id, job_id=request.job_id,
                    )
                    validated_events = _validated_progress(progress_events, progress_state, request.job_id)
                finally:
                    os.replace(video_snapshot, sealed_video)
            except Exception as error:
                primary_error = error
    except Exception as error:
        exit_error = error

    error = primary_error or exit_error
    if error is not None:
        cause = exit_error if primary_error is not None and exit_error is not None else None
        raise error.with_traceback(error.__traceback__) from cause

    owned_generation = _create_owned_generation(root, layout)
    processor_entry = _write_generation_processor(
        root, owned_generation, processor_result,
    )
    processor_row_count = len(processor_result["rows"])
    progress_entry, progress_count = _write_generation_progress(
        root, owned_generation, validated_events, request.job_id,
    )
    receipt_sha = hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest()
    result = ResultBundle(
        2,
        request.job_id,
        request.match_id,
        receipt.source_commit,
        receipt.manifest_sha256,
        receipt_sha,
        receipt.requested_runtime_options,
        {
            "processorResultPath": layout.processor.as_posix(),
            "processorResultFormat": PROCESSOR_RESULT_FORMAT,
            "processorRowCount": processor_row_count,
            "progressPath": layout.progress.as_posix(),
            "progressEventCount": progress_count,
        },
        (processor_entry, progress_entry),
    )
    result_identity = _write_generation_json(
        root, owned_generation, layout.result, result.to_mapping(),
    )
    validate_result(request, receipt, result, output_root=root)
    completion = CompletionReceipt(
        1,
        request.job_id,
        request.match_id,
        layout.result,
        result_identity.size_bytes,
        result_identity.sha256,
        receipt.source_commit,
        receipt.manifest_sha256,
        datetime.now(timezone.utc),
    )
    validate_completion(root, request, receipt, result, completion)
    completion_identity = _write_generation_completion(
        root, owned_generation, completion,
    )
    expected = {
        layout.processor: StreamIdentity(processor_entry.size_bytes, processor_entry.sha256),
        layout.progress: StreamIdentity(progress_entry.size_bytes, progress_entry.sha256),
        layout.result: result_identity,
        layout.completion: completion_identity,
    }
    _seal_generation_read_only(root, owned_generation, expected)
    _commit_completion_link(root, owned_generation, completion_relative)
    return


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise WorkerError("invalid command line")

    def parse_args(self, args=None, namespace=None):
        supplied = list(sys.argv[1:] if args is None else args)
        option_names = [item.split("=", 1)[0] for item in supplied if item.startswith("--")]
        if any(option_names.count(name) > 1 for name in {"--request", "--result", "--completion-receipt"}):
            self.error("duplicate argument")
        return super().parse_args(supplied, namespace)


def _parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(
        description="Process one sealed local football video bundle",
        allow_abbrev=False,
    )
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--completion-receipt", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        run_worker(args.request, args.result, args.completion_receipt)
    except WorkerRollbackIndeterminate:
        sys.stderr.write("gpu worker rollback indeterminate\n")
        return 3
    except Exception:
        sys.stderr.write("gpu worker failed\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
