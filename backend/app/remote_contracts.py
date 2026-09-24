"""Provider-neutral sealed remote execution contracts.

Canonical JSON is UTF-8, sorted and compact, and always ends in one LF byte.
This module validates local trust-boundary data; it does not claim protection
from filesystem races performed by another privileged process.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
from itertools import islice
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from types import MappingProxyType
from typing import Any, BinaryIO


READ_CHUNK_BYTES = 64 * 1024
MAX_JSON_DEPTH = 20
MAX_JSON_NODES = 20_000
MAX_JSON_STRING = 64 * 1024
MAX_CONFIG_BYTES = 512 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024
MAX_PROCESSOR_RESULT_BYTES = 1 << 30
MAX_SEGMENTATION_RESULT_BYTES = 128 * 1024 * 1024
MAX_PROCESSOR_METADATA_LINE_BYTES = 64 * 1024 * 1024
MAX_PROCESSOR_ROW_LINE_BYTES = 64 * 1024
MAX_FILES = 1024
MAX_FILE_BYTES = 1 << 50
MAX_PROGRESS_TOTAL_BYTES = 16 * 1024 * 1024
MAX_PROGRESS_LINE_BYTES = 64 * 1024
MAX_PROGRESS_EVENTS = 100_000
MAX_PROCESSOR_ROW_COUNT = 20_000_000
PROCESSOR_RESULT_FORMAT = "jsonl-v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")
_GENERATION_NAMESPACE_SUFFIX = ".json.generations"
_RESULT_FILENAME = "result.json"
_PROCESSOR_RESULT_FILENAME = "result.processor-result.json"
_PROCESSOR_RESULT_V2_FILENAME = "result.processor-result.jsonl"
_SEGMENTATION_RESULT_FILENAME = "result.segmentation-result.json"
_PROGRESS_FILENAME = "result.progress.jsonl"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_STAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")
_UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z$"
)
_INPUT_ROLES = frozenset({"source_archive", "manifest", "evidence", "runtime_artifact", "input_video", "job_request"})
_FILE_ROLES = _INPUT_ROLES | {"result_artifact"}
_SINGLETON_ROLES = _INPUT_ROLES - {"runtime_artifact"}
_SECRET_KEY_FAMILY = (
    r"(?:api[ _-]?key|(?:access|refresh|auth|id)[ _-]?token|token|secrets?|"
    r"pass(?:[ _-]?word|wd)|authorization|authentication|auth|"
    r"(?:auth|authorization)[ _-]?header|cookies?|credentials?|"
    r"(?:aws[ _-]?)?secret[ _-]?access[ _-]?key|secret[ _-]?key|"
    r"private[ _-]?key|access[ _-]?key[ _-]?id)"
)
_SECRET_KEY = re.compile(rf"(?:^|[^a-z0-9]){_SECRET_KEY_FAMILY}(?:$|[^a-z0-9])", re.I)
_SECRET_KEY_SUFFIX = re.compile(rf"(?:^|[ _-]){_SECRET_KEY_FAMILY}$", re.I)
_SECRET_COMPACT_KEY_SUFFIXES = (
    "apikey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "idtoken",
    "authheader",
    "authorizationheader",
    "authenticationheader",
    "token",
    "secret",
    "secrets",
    "password",
    "passwd",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "authorization",
    "authentication",
    "auth",
    "secretaccesskey",
    "secretkey",
    "privatekey",
    "accesskeyid",
)
_SECRET_TEXT = re.compile(
    rf"(?:daytona[ _-]?api[ _-]?key|bearer\s+\S|(?:set[ _-]?)?cookies?\s*[:=]|"
    rf"{_SECRET_KEY_FAMILY}\s*[:=])",
    re.I,
)


class RemoteContractError(ValueError):
    """A fail-closed contract error whose text contains no supplied values."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    try:
        if not isinstance(value, Mapping):
            raise RemoteContractError(f"{label} must be an object")
        items = list(islice(value.items(), MAX_JSON_NODES + 1))
        if len(items) > MAX_JSON_NODES:
            raise RemoteContractError(f"{label} exceeds object size limit")
        result: dict[str, Any] = {}
        for key, item in items:
            if not isinstance(key, str):
                raise RemoteContractError(f"{label} keys must be strings")
            safe_key = str.__str__(key)
            if len(safe_key) > MAX_JSON_STRING or "\0" in safe_key:
                raise RemoteContractError(f"{label} contains an unsafe or oversized key")
            if safe_key in result:
                raise RemoteContractError(f"{label} contains duplicate keys")
            result[safe_key] = item
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError(f"{label} object cannot be read") from None
    return result


def _exact(value: object, keys: frozenset[str], label: str) -> Mapping[str, Any]:
    result = _mapping(value, label)
    actual = set(result)
    if keys - actual:
        raise RemoteContractError(f"{label} has missing keys")
    if actual - keys:
        raise RemoteContractError(f"{label} has unknown keys")
    return result


def _schema(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RemoteContractError("schemaVersion must be integer 1")
    safe = int.__int__(value)
    if safe != 1:
        raise RemoteContractError("schemaVersion must be integer 1")
    return safe


def _result_schema(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RemoteContractError("result schemaVersion must be integer 1, 2 or 3")
    safe = int.__int__(value)
    if safe not in (1, 2, 3):
        raise RemoteContractError("result schemaVersion must be integer 1, 2 or 3")
    return safe


def _text(value: object, label: str, maximum: int, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str):
        raise RemoteContractError(f"{label} must be bounded non-empty text")
    safe = str.__str__(value)
    if not safe or len(safe) > maximum or "\0" in safe:
        raise RemoteContractError(f"{label} must be bounded non-empty text")
    if pattern is not None and pattern.fullmatch(safe) is None:
        raise RemoteContractError(f"{label} has invalid syntax")
    return safe


def _integer(value: object, label: str, minimum: int = 0, maximum: int = MAX_FILE_BYTES) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RemoteContractError(f"{label} must be an integer in range")
    safe = int.__int__(value)
    if not minimum <= safe <= maximum:
        raise RemoteContractError(f"{label} must be an integer in range")
    return safe


def _digest(value: object, label: str) -> str:
    return _text(value, label, 64, _SHA256)


def _commit(value: object) -> str:
    return _text(value, "sourceCommit", 40, _GIT_SHA1)


def _relative(value: object, label: str) -> PurePosixPath:
    try:
        raw_value = value.as_posix() if isinstance(value, PurePosixPath) else value
        raw = _text(raw_value, label, 1024)
        if raw.startswith(("/", "~")) or "\\" in raw or "\0" in raw:
            raise RemoteContractError(f"{label} must be a normalized relative POSIX path")
        parts = raw.split("/")
        candidate = PurePosixPath(raw)
        if (
            any(part in {"", ".", ".."} for part in parts)
            or re.match(r"^[A-Za-z]:", parts[0])
            or candidate.is_absolute()
            or candidate.as_posix() != raw
        ):
            raise RemoteContractError(f"{label} must be a normalized relative POSIX path")
        return candidate
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError(f"{label} cannot be read") from None


def _generation_path(
    value: object,
    label: str,
    expected_filename: str,
) -> tuple[PurePosixPath, PurePosixPath, str]:
    path = _relative(value, label)
    if len(path.parts) < 3:
        raise RemoteContractError(f"{label} must select a generation artifact")
    if path.name != expected_filename:
        raise RemoteContractError(f"{label} must use the fixed generation filename")
    generation = path.parts[-2]
    if _GENERATION_ID.fullmatch(generation) is None:
        raise RemoteContractError(f"{label} has invalid generation id")
    namespace = path.parent.parent
    if (
        len(namespace.name) <= len(_GENERATION_NAMESPACE_SUFFIX)
        or not namespace.name.endswith(_GENERATION_NAMESPACE_SUFFIX)
    ):
        raise RemoteContractError(f"{label} has invalid generation namespace")
    return path, namespace, generation


def _timestamp(value: object, label: str) -> datetime:
    raw = _text(value, label, 32, _UTC_TIMESTAMP)
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        raise RemoteContractError(f"{label} must be a valid UTC timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RemoteContractError(f"{label} must be UTC")
    if _format_timestamp(parsed) != raw:
        raise RemoteContractError(f"{label} must use canonical UTC form")
    return parsed


def _utc_datetime(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise RemoteContractError(f"{label} must be a datetime")
    try:
        tz = datetime.tzinfo.__get__(value, datetime)
        offset = datetime.utcoffset(value)
        if tz is None or offset is None:
            raise RemoteContractError(f"{label} must be timezone-aware UTC")
        offset_parts = (
            timedelta.days.__get__(offset, timedelta),
            timedelta.seconds.__get__(offset, timedelta),
            timedelta.microseconds.__get__(offset, timedelta),
        )
        if offset_parts != (0, 0, 0):
            raise RemoteContractError(f"{label} must be timezone-aware UTC")
        return datetime(
            datetime.year.__get__(value, datetime),
            datetime.month.__get__(value, datetime),
            datetime.day.__get__(value, datetime),
            datetime.hour.__get__(value, datetime),
            datetime.minute.__get__(value, datetime),
            datetime.second.__get__(value, datetime),
            datetime.microsecond.__get__(value, datetime),
            tzinfo=timezone.utc,
            fold=0,
        )
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError(f"{label} cannot be read safely") from None


def _format_timestamp(value: datetime) -> str:
    safe = _utc_datetime(value, "timestamp")
    return datetime.isoformat(safe, timespec="auto").replace("+00:00", "Z")


def _freeze_json(value: object, label: str, *, _depth: int = 0, _counter: list[int] | None = None) -> object:
    counter = [0] if _counter is None else _counter
    counter[0] += 1
    if counter[0] > MAX_JSON_NODES or _depth > MAX_JSON_DEPTH:
        raise RemoteContractError(f"{label} exceeds JSON complexity limits")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        safe_integer = int.__int__(value)
        if abs(safe_integer) > 2**53 - 1:
            raise RemoteContractError(f"{label} integer is outside portable JSON range")
        return safe_integer
    if isinstance(value, float):
        safe_float = float.__float__(value)
        if not math.isfinite(safe_float):
            raise RemoteContractError(f"{label} contains a non-finite number")
        return safe_float
    if isinstance(value, str):
        safe_text = str.__str__(value)
        if len(safe_text) > MAX_JSON_STRING or "\0" in safe_text:
            raise RemoteContractError(f"{label} contains unsafe or oversized text")
        return safe_text
    try:
        is_mapping = isinstance(value, Mapping)
    except Exception:
        raise RemoteContractError(f"{label} contains unreadable JSON data") from None
    if is_mapping:
        mapping = _mapping(value, label)
        return MappingProxyType({key: _freeze_json(item, label, _depth=_depth + 1, _counter=counter) for key, item in mapping.items()})
    if isinstance(value, (list, tuple)):
        try:
            items = tuple(value)
        except Exception:
            raise RemoteContractError(f"{label} contains unreadable JSON data") from None
        return tuple(_freeze_json(item, label, _depth=_depth + 1, _counter=counter) for item in items)
    raise RemoteContractError(f"{label} contains unsupported JSON data")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def canonical_json_bytes(value: object, *, max_bytes: int = MAX_RESULT_BYTES) -> bytes:
    """Return deterministic compact JSON with exactly one trailing LF."""

    maximum = _integer(max_bytes, "maximum canonical JSON bytes", 1, MAX_RESULT_BYTES)
    frozen = _freeze_json(value, "JSON")
    encoded = bytearray()
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for chunk in encoder.iterencode(_thaw(frozen)):
            raw_chunk = chunk.encode("utf-8")
            if len(encoded) + len(raw_chunk) + 1 > maximum:
                raise RemoteContractError("canonical JSON exceeds size limit")
            encoded.extend(raw_chunk)
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError("JSON cannot be encoded canonically") from None
    encoded.append(0x0A)
    return bytes(encoded)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RemoteContractError("JSON contains a duplicate object key")
        result[key] = value
    return result


def _portable_json_integer(raw: str) -> int:
    if len(raw) > 17:
        raise RemoteContractError("JSON integer is outside portable range") from None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise RemoteContractError("JSON integer is outside portable range") from None
    if abs(value) > 2**53 - 1:
        raise RemoteContractError("JSON integer is outside portable range") from None
    return value


def _load_canonical_json(source: bytes | bytearray | memoryview | BinaryIO | Path | str) -> tuple[object, bytes]:
    binary_source = isinstance(source, (bytes, bytearray, memoryview))
    if binary_source:
        try:
            raw = bytes(source)
        except Exception:
            raise RemoteContractError("canonical JSON bytes cannot be read") from None
        if len(raw) > MAX_RESULT_BYTES:
            raise RemoteContractError("canonical JSON exceeds size limit")
    else:
        try:
            read = source.read  # type: ignore[union-attr]
        except AttributeError:
            read = None
        except Exception:
            raise RemoteContractError("canonical JSON source cannot be inspected") from None
    if not binary_source and read is not None:
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = read(READ_CHUNK_BYTES)
            except Exception:
                raise RemoteContractError("canonical JSON stream read failed") from None
            if not isinstance(chunk, bytes):
                raise RemoteContractError("canonical JSON stream must return bytes")
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESULT_BYTES:
                raise RemoteContractError("canonical JSON exceeds size limit")
            chunks.append(chunk)
        raw = b"".join(chunks)
    elif not binary_source:
        try:
            with Path(source).open("rb") as handle:
                return _load_canonical_json(handle)
        except RemoteContractError:
            raise
        except Exception:
            raise RemoteContractError("cannot read canonical JSON") from None
    if len(raw) > MAX_RESULT_BYTES:
        raise RemoteContractError("canonical JSON exceeds size limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(RemoteContractError("JSON contains a non-finite number")),
            parse_int=_portable_json_integer,
        )
    except RemoteContractError:
        raise
    except (UnicodeError, ValueError, RecursionError, MemoryError):
        raise RemoteContractError("invalid canonical JSON") from None
    if raw != canonical_json_bytes(value):
        raise RemoteContractError("JSON bytes are not canonical")
    return value, raw


def load_canonical_json(source: bytes | bytearray | memoryview | BinaryIO | Path | str) -> object:
    value, _ = _load_canonical_json(source)
    return value


@dataclass(frozen=True, slots=True)
class StreamIdentity:
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "size_bytes", _integer(self.size_bytes, "sizeBytes"))
        object.__setattr__(self, "sha256", _digest(self.sha256, "sha256"))


def stream_identity(stream: BinaryIO, *, expected_size: int | None = None, expected_sha256: str | None = None, max_bytes: int = MAX_FILE_BYTES) -> StreamIdentity:
    if expected_size is not None:
        expected_size = _integer(expected_size, "expected size")
    if expected_sha256 is not None:
        expected_sha256 = _digest(expected_sha256, "expected digest")
    max_bytes = _integer(max_bytes, "maximum size", 0)
    digest = hashlib.sha256(); size = 0
    while True:
        try:
            chunk = stream.read(READ_CHUNK_BYTES)
        except Exception:
            raise RemoteContractError("identity stream read failed") from None
        if not isinstance(chunk, bytes):
            raise RemoteContractError("identity stream must return bytes")
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise RemoteContractError("stream exceeds maximum size")
        digest.update(chunk)
    result = StreamIdentity(size, digest.hexdigest())
    if expected_size is not None and result.size_bytes != expected_size:
        raise RemoteContractError("stream size mismatch")
    if expected_sha256 is not None and result.sha256 != expected_sha256:
        raise RemoteContractError("stream digest mismatch")
    return result


@dataclass(frozen=True, slots=True)
class FileEntry:
    role: str
    relative_path: PurePosixPath
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        role = _text(self.role, "role", 32)
        if role not in _FILE_ROLES:
            raise RemoteContractError("role is not supported")
        size = _integer(self.size_bytes, "sizeBytes")
        if role in _SINGLETON_ROLES and size == 0:
            raise RemoteContractError("sealed singleton files must have positive sizeBytes")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "relative_path", _relative(self.relative_path, "relativePath"))
        object.__setattr__(self, "size_bytes", size)
        object.__setattr__(self, "sha256", _digest(self.sha256, "sha256"))

    @classmethod
    def from_mapping(cls, value: object) -> "FileEntry":
        value = _exact(value, frozenset({"role", "relativePath", "sizeBytes", "sha256"}), "file entry")
        return cls(value["role"], value["relativePath"], value["sizeBytes"], value["sha256"])  # type: ignore[arg-type]

    def to_mapping(self) -> dict[str, object]:
        return {"role": self.role, "relativePath": self.relative_path.as_posix(), "sizeBytes": self.size_bytes, "sha256": self.sha256}


def _files(value: object) -> tuple[FileEntry, ...]:
    try:
        if not isinstance(value, (list, tuple)) or len(value) > MAX_FILES:
            raise RemoteContractError("files must be a bounded array")
        items = tuple(value)
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError("files array cannot be read") from None
    files = tuple(FileEntry.from_mapping(item) for item in items)
    paths = [item.relative_path for item in files]
    if len(paths) != len(set(paths)):
        raise RemoteContractError("duplicate relative file path")
    roles = [item.role for item in files]
    if any(roles.count(role) > 1 for role in _SINGLETON_ROLES):
        raise RemoteContractError("duplicate singleton file role")
    return files


def _direct_files(value: object, label: str) -> tuple[FileEntry, ...]:
    try:
        if not isinstance(value, (list, tuple)) or len(value) > MAX_FILES:
            raise RemoteContractError(f"{label} must be a bounded FileEntry collection")
        items = tuple(value)
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError(f"{label} collection cannot be read") from None
    files: list[FileEntry] = []
    for item in items:
        if type(item) is not FileEntry:
            raise RemoteContractError(f"{label} items must be exact FileEntry values") from None
        try:
            files.append(FileEntry(item.role, item.relative_path, item.size_bytes, item.sha256))
        except RemoteContractError:
            raise
        except Exception:
            raise RemoteContractError(f"{label} item cannot be read") from None
    paths = [item.relative_path for item in files]
    if len(paths) != len(set(paths)):
        raise RemoteContractError("duplicate relative file path")
    roles = [item.role for item in files]
    if any(roles.count(role) > 1 for role in _SINGLETON_ROLES):
        raise RemoteContractError("duplicate singleton file role")
    return tuple(files)


@dataclass(frozen=True, slots=True)
class JobReceipt:
    schema_version: int
    source_commit: str
    manifest_sha256: str
    evidence_sha256: str
    job_request_sha256: str
    requested_runtime_options: Mapping[str, object]
    files: tuple[FileEntry, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema(self.schema_version))
        object.__setattr__(self, "source_commit", _commit(self.source_commit))
        object.__setattr__(self, "manifest_sha256", _digest(self.manifest_sha256, "manifestSha256"))
        object.__setattr__(self, "evidence_sha256", _digest(self.evidence_sha256, "evidenceSha256"))
        object.__setattr__(self, "job_request_sha256", _digest(self.job_request_sha256, "jobRequestSha256"))
        options = _freeze_json(_mapping(self.requested_runtime_options, "requestedRuntimeOptions"), "requestedRuntimeOptions")
        canonical_json_bytes(options, max_bytes=MAX_CONFIG_BYTES)
        object.__setattr__(self, "requested_runtime_options", options)
        object.__setattr__(self, "files", _direct_files(self.files, "files"))
        if any(item.role not in _INPUT_ROLES for item in self.files):
            raise RemoteContractError("job receipt files must use sealed input roles")
        self._validate_role_bindings()
        canonical_json_bytes(self.to_mapping(), max_bytes=MAX_RESULT_BYTES)

    @classmethod
    def from_mapping(cls, value: object) -> "JobReceipt":
        keys = frozenset({"schemaVersion", "sourceCommit", "manifestSha256", "evidenceSha256", "jobRequestSha256", "requestedRuntimeOptions", "files"})
        value = _exact(value, keys, "job receipt")
        files = _files(value["files"])
        return cls(value["schemaVersion"], value["sourceCommit"], value["manifestSha256"], value["evidenceSha256"], value["jobRequestSha256"], value["requestedRuntimeOptions"], files)  # type: ignore[arg-type]

    def _validate_role_bindings(self) -> None:
        by_role = {item.role: item for item in self.files}
        required = {"source_archive", "manifest", "evidence", "input_video", "job_request"}
        if required - set(by_role):
            raise RemoteContractError("receipt is missing a required singleton role")
        for role, digest in (("manifest", self.manifest_sha256), ("evidence", self.evidence_sha256), ("job_request", self.job_request_sha256)):
            if role not in by_role or by_role[role].sha256 != digest:
                raise RemoteContractError(f"{role} identity binding mismatch")

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "sourceCommit": self.source_commit, "manifestSha256": self.manifest_sha256, "evidenceSha256": self.evidence_sha256, "jobRequestSha256": self.job_request_sha256, "requestedRuntimeOptions": _thaw(self.requested_runtime_options), "files": [item.to_mapping() for item in self.files]}


@dataclass(frozen=True, slots=True)
class JobRequest:
    schema_version: int
    job_id: str
    match_id: str
    receipt_path: PurePosixPath
    input_video_path: PurePosixPath
    config: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema(self.schema_version))
        object.__setattr__(self, "job_id", _text(self.job_id, "jobId", 128, _ID))
        object.__setattr__(self, "match_id", _text(self.match_id, "matchId", 128, _ID))
        object.__setattr__(self, "receipt_path", _relative(self.receipt_path, "receiptPath"))
        object.__setattr__(self, "input_video_path", _relative(self.input_video_path, "inputVideoPath"))
        config = _freeze_json(_mapping(self.config, "config"), "config")
        canonical_json_bytes(config, max_bytes=MAX_CONFIG_BYTES)
        object.__setattr__(self, "config", config)
        canonical_json_bytes(self.to_mapping(), max_bytes=MAX_CONFIG_BYTES)

    @classmethod
    def from_mapping(cls, value: object) -> "JobRequest":
        keys = frozenset({"schemaVersion", "jobId", "matchId", "receiptPath", "inputVideoPath", "config"})
        value = _exact(value, keys, "job request")
        return cls(value["schemaVersion"], value["jobId"], value["matchId"], value["receiptPath"], value["inputVideoPath"], value["config"])  # type: ignore[arg-type]

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "jobId": self.job_id, "matchId": self.match_id, "receiptPath": self.receipt_path.as_posix(), "inputVideoPath": self.input_video_path.as_posix(), "config": _thaw(self.config)}


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    schema_version: int
    job_id: str
    sequence: int
    progress: int | float
    stage: str
    message: str
    timestamp: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema(self.schema_version))
        object.__setattr__(self, "job_id", _text(self.job_id, "jobId", 128, _ID))
        object.__setattr__(self, "sequence", _integer(self.sequence, "sequence", 0, 2**63 - 1))
        raw_progress = self.progress
        if isinstance(raw_progress, bool) or not isinstance(raw_progress, (int, float)):
            raise RemoteContractError("progress must be a finite number from 0 to 100")
        progress = int.__int__(raw_progress) if isinstance(raw_progress, int) else float.__float__(raw_progress)
        if not math.isfinite(progress) or not 0 <= progress <= 100:
            raise RemoteContractError("progress must be a finite number from 0 to 100")
        stage = _text(self.stage, "stage", 128, _STAGE)
        message = _text(self.message, "message", 4096)
        if _SECRET_TEXT.search(stage) or _SECRET_TEXT.search(message):
            raise RemoteContractError("progress text must not contain credentials")
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "progress", progress)
        object.__setattr__(self, "timestamp", _utc_datetime(self.timestamp, "timestamp"))

    @classmethod
    def from_mapping(cls, value: object) -> "ProgressEvent":
        keys = frozenset({"schemaVersion", "jobId", "sequence", "progress", "stage", "message", "timestamp"})
        value = _exact(value, keys, "progress event")
        return cls(value["schemaVersion"], value["jobId"], value["sequence"], value["progress"], value["stage"], value["message"], _timestamp(value["timestamp"], "timestamp"))  # type: ignore[arg-type]

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "jobId": self.job_id, "sequence": self.sequence, "progress": self.progress, "stage": self.stage, "message": self.message, "timestamp": _format_timestamp(self.timestamp)}


@dataclass(frozen=True, slots=True)
class ResultBundle:
    schema_version: int
    job_id: str
    match_id: str
    source_commit: str
    manifest_sha256: str
    receipt_sha256: str
    requested_runtime_options: Mapping[str, object]
    result: Mapping[str, object]
    artifacts: tuple[FileEntry, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _result_schema(self.schema_version))
        object.__setattr__(self, "job_id", _text(self.job_id, "jobId", 128, _ID))
        object.__setattr__(self, "match_id", _text(self.match_id, "matchId", 128, _ID))
        object.__setattr__(self, "source_commit", _commit(self.source_commit))
        object.__setattr__(self, "manifest_sha256", _digest(self.manifest_sha256, "manifestSha256"))
        object.__setattr__(self, "receipt_sha256", _digest(self.receipt_sha256, "receiptSha256"))
        options = _freeze_json(_mapping(self.requested_runtime_options, "requestedRuntimeOptions"), "requestedRuntimeOptions")
        if self.schema_version == 1:
            result_value = _exact(
                self.result,
                frozenset({"processorResultPath", "progressPath", "progressEventCount"}),
                "result",
            )
            processor_filename = _PROCESSOR_RESULT_FILENAME
            processor_row_count = None
        elif self.schema_version == 2:
            result_value = _exact(
                self.result,
                frozenset({"processorResultPath", "processorResultFormat", "processorRowCount", "progressPath", "progressEventCount"}),
                "result",
            )
            if _text(result_value["processorResultFormat"], "processorResultFormat", 16) != PROCESSOR_RESULT_FORMAT:
                raise RemoteContractError("processorResultFormat must be jsonl-v1")
            processor_filename = _PROCESSOR_RESULT_V2_FILENAME
            processor_row_count = _integer(
                result_value["processorRowCount"],
                "processorRowCount",
                0,
                MAX_PROCESSOR_ROW_COUNT,
            )
        else:
            result_value = _exact(self.result, frozenset({"maskResultPath", "progressPath", "progressEventCount",
                "generationId", "requestDigest", "sourceSha256", "checkpointDigest", "jobIdentity"}), "result")
            processor_filename = _SEGMENTATION_RESULT_FILENAME
            processor_row_count = None
        primary_key = "maskResultPath" if self.schema_version == 3 else "processorResultPath"
        processor_path, processor_namespace, processor_generation = _generation_path(
            result_value[primary_key], primary_key, processor_filename,
        )
        progress_path, progress_namespace, progress_generation = _generation_path(
            result_value["progressPath"],
            "progressPath",
            _PROGRESS_FILENAME,
        )
        if (processor_namespace, processor_generation) != (progress_namespace, progress_generation):
            raise RemoteContractError("result artifact paths must share one generation")
        progress_count = _integer(
            result_value["progressEventCount"],
            "progressEventCount",
            0,
            MAX_PROGRESS_EVENTS,
        )
        result = {
            primary_key: processor_path.as_posix(),
            "progressPath": progress_path.as_posix(),
            "progressEventCount": progress_count,
        }
        if self.schema_version == 3:
            result.update({key: _digest(result_value[key], key) for key in
                ("requestDigest", "sourceSha256", "checkpointDigest", "jobIdentity")})
            result["generationId"] = _text(result_value["generationId"], "generationId", 32, _GENERATION_ID)
        if processor_row_count is not None:
            result["processorResultFormat"] = PROCESSOR_RESULT_FORMAT
            result["processorRowCount"] = processor_row_count
        result = _freeze_json(result, "result")
        canonical_json_bytes(options, max_bytes=MAX_CONFIG_BYTES)
        canonical_json_bytes(result, max_bytes=MAX_RESULT_BYTES)
        object.__setattr__(self, "requested_runtime_options", options)
        object.__setattr__(self, "result", result)
        artifacts = _direct_files(self.artifacts, "artifacts")
        if len(artifacts) != 2 or any(item.role != "result_artifact" for item in artifacts):
            raise RemoteContractError("result artifacts must contain exactly two result_artifact entries")
        by_path = {item.relative_path: item for item in artifacts}
        if set(by_path) != {processor_path, progress_path}:
            raise RemoteContractError("result artifact path binding mismatch")
        if self.schema_version == 3 and by_path[processor_path].size_bytes > MAX_SEGMENTATION_RESULT_BYTES:
            raise RemoteContractError("segmentation result size exceeds limit")
        object.__setattr__(self, "artifacts", artifacts)
        canonical_json_bytes(self.to_mapping(), max_bytes=MAX_RESULT_BYTES)

    @classmethod
    def from_mapping(cls, value: object) -> "ResultBundle":
        keys = frozenset({"schemaVersion", "jobId", "matchId", "sourceCommit", "manifestSha256", "receiptSha256", "requestedRuntimeOptions", "result", "artifacts"})
        value = _exact(value, keys, "result bundle")
        artifacts = _files(value["artifacts"])
        return cls(value["schemaVersion"], value["jobId"], value["matchId"], value["sourceCommit"], value["manifestSha256"], value["receiptSha256"], value["requestedRuntimeOptions"], value["result"], artifacts)  # type: ignore[arg-type]

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "jobId": self.job_id, "matchId": self.match_id, "sourceCommit": self.source_commit, "manifestSha256": self.manifest_sha256, "receiptSha256": self.receipt_sha256, "requestedRuntimeOptions": _thaw(self.requested_runtime_options), "result": _thaw(self.result), "artifacts": [item.to_mapping() for item in self.artifacts]}

    @property
    def processor_format(self) -> str:
        if self.schema_version == 3:
            raise RemoteContractError("segmentation result has no processor format")
        return PROCESSOR_RESULT_FORMAT if self.schema_version == 2 else "json-v1"

    @property
    def processor_row_count(self) -> int | None:
        return self.result["processorRowCount"] if self.schema_version == 2 else None  # type: ignore[return-value]

    @property
    def primary_artifact_path(self) -> PurePosixPath:
        key = "maskResultPath" if self.schema_version == 3 else "processorResultPath"
        return PurePosixPath(self.result[key])


@dataclass(frozen=True, slots=True)
class CompletionReceipt:
    schema_version: int
    job_id: str
    match_id: str
    result_path: PurePosixPath
    result_size_bytes: int
    result_sha256: str
    source_commit: str
    manifest_sha256: str
    completed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema(self.schema_version))
        object.__setattr__(self, "job_id", _text(self.job_id, "jobId", 128, _ID))
        object.__setattr__(self, "match_id", _text(self.match_id, "matchId", 128, _ID))
        result_path, _, _ = _generation_path(self.result_path, "resultPath", _RESULT_FILENAME)
        object.__setattr__(self, "result_path", result_path)
        size = _integer(self.result_size_bytes, "resultSizeBytes")
        if size == 0:
            raise RemoteContractError("resultSizeBytes must be positive")
        object.__setattr__(self, "result_size_bytes", size)
        object.__setattr__(self, "result_sha256", _digest(self.result_sha256, "resultSha256"))
        object.__setattr__(self, "source_commit", _commit(self.source_commit))
        object.__setattr__(self, "manifest_sha256", _digest(self.manifest_sha256, "manifestSha256"))
        object.__setattr__(self, "completed_at", _utc_datetime(self.completed_at, "completedAt"))

    @classmethod
    def from_mapping(cls, value: object) -> "CompletionReceipt":
        keys = frozenset({"schemaVersion", "jobId", "matchId", "resultPath", "resultSizeBytes", "resultSha256", "sourceCommit", "manifestSha256", "completedAt"})
        value = _exact(value, keys, "completion receipt")
        return cls(value["schemaVersion"], value["jobId"], value["matchId"], value["resultPath"], value["resultSizeBytes"], value["resultSha256"], value["sourceCommit"], value["manifestSha256"], _timestamp(value["completedAt"], "completedAt"))  # type: ignore[arg-type]

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "jobId": self.job_id, "matchId": self.match_id, "resultPath": self.result_path.as_posix(), "resultSizeBytes": self.result_size_bytes, "resultSha256": self.result_sha256, "sourceCommit": self.source_commit, "manifestSha256": self.manifest_sha256, "completedAt": _format_timestamp(self.completed_at)}


def confined_path(root: Path | str, relative: PurePosixPath | str) -> Path:
    rel = _relative(relative, "relative path")
    try:
        root_path = Path(root).resolve(strict=True)
    except Exception:
        raise RemoteContractError("confinement root cannot be resolved") from None
    current = root_path
    try:
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise RemoteContractError("confined path contains a symlink component")
            if current.exists():
                current.resolve(strict=True).relative_to(root_path)
        current.resolve(strict=False).relative_to(root_path)
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError("confined path escapes root") from None
    return current


def _fsync_directory(directory: Path) -> None:
    directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _rollback_published_json(destination: Path) -> bool:
    try:
        destination.unlink()
    except Exception:
        pass
    try:
        os.lstat(destination)
    except FileNotFoundError:
        absent = True
    except Exception:
        absent = False
    else:
        absent = False
    try:
        _fsync_directory(destination.parent)
    except Exception:
        pass
    return absent


def atomic_write_json(root: Path | str, relative: PurePosixPath | str, value: object) -> Path:
    """Durably publish canonical JSON or fail after removing it when confirmed.

    A durability failure after publication is rolled back when possible. If the
    destination's absence cannot be confirmed, the raised error explicitly marks
    the outcome indeterminate so callers can escalate cleanup rather than retrying
    under the assumption that nothing was published.
    """

    payload = canonical_json_bytes(value)
    destination = confined_path(root, relative)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = confined_path(root, relative)
        fd, temp_name = tempfile.mkstemp(prefix=".remote-contract-", suffix=".tmp", dir=destination.parent)
    except RemoteContractError:
        raise
    except Exception:
        raise RemoteContractError("cannot prepare atomic JSON write") from None
    temp_path = Path(temp_name)
    owns_fd = True
    published = False
    try:
        os.fchmod(fd, 0o600)
        handle = os.fdopen(fd, "wb")
        owns_fd = False
        with handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        if destination.is_symlink():
            raise RemoteContractError("atomic destination must not be a symlink")
        os.replace(temp_path, destination)
        published = True
        _fsync_directory(destination.parent)
        return destination
    except RemoteContractError:
        if not published:
            raise
        if _rollback_published_json(destination):
            raise RemoteContractError("atomic JSON write failed") from None
        raise RemoteContractError("atomic JSON write indeterminate after published cleanup failure") from None
    except Exception:
        if published:
            if _rollback_published_json(destination):
                raise RemoteContractError("atomic JSON write failed") from None
            raise RemoteContractError("atomic JSON write indeterminate after published cleanup failure") from None
        raise RemoteContractError("atomic JSON write failed") from None
    finally:
        if owns_fd:
            try: os.close(fd)
            except Exception: pass
        try: temp_path.unlink(missing_ok=True)
        except OSError: pass


def validate_receipt_files(root: Path | str, request: JobRequest, receipt: JobReceipt) -> None:
    receipt._validate_role_bindings()
    by_role = {item.role: item for item in receipt.files}
    if "input_video" not in by_role or by_role["input_video"].relative_path != request.input_video_path:
        raise RemoteContractError("input video path binding mismatch")
    request_bytes = canonical_json_bytes(request.to_mapping())
    request_digest = hashlib.sha256(request_bytes).hexdigest()
    if request_digest != receipt.job_request_sha256:
        raise RemoteContractError("job request identity binding mismatch")
    receipt_path = confined_path(root, request.receipt_path)
    try:
        _, loaded_receipt_bytes = _load_canonical_json(receipt_path)
    except RemoteContractError:
        raise
    except (OSError, ValueError, TypeError):
        raise RemoteContractError("receipt file cannot be read") from None
    if loaded_receipt_bytes != canonical_json_bytes(receipt.to_mapping(), max_bytes=MAX_RESULT_BYTES):
        raise RemoteContractError("receipt payload mismatch")
    for item in receipt.files:
        path = confined_path(root, item.relative_path)
        try:
            with path.open("rb") as handle:
                stream_identity(handle, expected_size=item.size_bytes, expected_sha256=item.sha256)
        except RemoteContractError:
            raise
        except (OSError, ValueError, TypeError):
            raise RemoteContractError("receipt file cannot be read") from None


def validate_progress_jsonl(stream: BinaryIO, *, expected_job_id: str, max_total_bytes: int = MAX_PROGRESS_TOTAL_BYTES, max_line_bytes: int = MAX_PROGRESS_LINE_BYTES, max_events: int = MAX_PROGRESS_EVENTS) -> tuple[ProgressEvent, ...]:
    expected_job_id = _text(expected_job_id, "expected jobId", 128, _ID)
    max_total_bytes = _integer(max_total_bytes, "maximum total bytes", 1, MAX_PROGRESS_TOTAL_BYTES)
    max_line_bytes = _integer(max_line_bytes, "maximum line bytes", 1, MAX_PROGRESS_LINE_BYTES)
    max_events = _integer(max_events, "maximum event count", 1, MAX_PROGRESS_EVENTS)
    buffer = bytearray(); total = 0; events: list[ProgressEvent] = []
    previous_sequence = -1; previous_progress = -math.inf
    while True:
        try:
            chunk = stream.read(min(READ_CHUNK_BYTES, max_total_bytes + 1))
        except Exception:
            raise RemoteContractError("progress stream read failed") from None
        if not isinstance(chunk, bytes): raise RemoteContractError("progress stream must return bytes")
        if not chunk: break
        total += len(chunk)
        if total > max_total_bytes: raise RemoteContractError("progress total size exceeds limit")
        buffer.extend(chunk)
        while b"\n" in buffer:
            raw, _, remainder = buffer.partition(b"\n"); buffer = bytearray(remainder)
            if not raw or len(raw) + 1 > max_line_bytes: raise RemoteContractError("progress line exceeds limit")
            if len(events) >= max_events: raise RemoteContractError("progress event count exceeds limit")
            value = load_canonical_json(bytes(raw) + b"\n")
            event = ProgressEvent.from_mapping(value)
            if event.job_id != expected_job_id: raise RemoteContractError("progress job mismatch")
            if event.sequence <= previous_sequence: raise RemoteContractError("progress sequence must strictly increase")
            if event.progress < previous_progress: raise RemoteContractError("progress value must not decrease")
            events.append(event); previous_sequence = event.sequence; previous_progress = event.progress
        if len(buffer) >= max_line_bytes: raise RemoteContractError("progress line exceeds limit")
    if buffer: raise RemoteContractError("progress stream must end with a complete newline")
    return tuple(events)


def _read_progress_snapshot(stream: BinaryIO) -> bytes:
    snapshot = bytearray()
    while True:
        try:
            chunk = stream.read(
                min(READ_CHUNK_BYTES, MAX_PROGRESS_TOTAL_BYTES + 1 - len(snapshot))
            )
        except Exception:
            raise RemoteContractError("progress stream read failed") from None
        if not isinstance(chunk, bytes):
            raise RemoteContractError("progress stream must return bytes")
        if not chunk:
            return bytes(snapshot)
        snapshot.extend(chunk)
        if len(snapshot) > MAX_PROGRESS_TOTAL_BYTES:
            raise RemoteContractError("progress total size exceeds limit")


def validate_shadow_inputs(request: JobRequest, receipt: JobReceipt) -> Mapping[str, object]:
    shadow = request.config.get("shadowSegmentation")
    rights = request.config.get("rights")
    if request.config.get("jobKind") != "segmentation_shadow" or not isinstance(shadow, Mapping) \
            or not isinstance(rights, Mapping) or rights.get("cloudPermission") is not True \
            or rights.get("processingScope") not in {"local_plus_burst", "hosted"}:
        raise RemoteContractError("shadow job identity or permission is missing")
    shadow = _exact(shadow, frozenset({"schemaVersion", "matchId", "generationId", "requestDigest",
        "sourceSha256", "checkpointDigest", "jobIdentity", "deadlineSeconds"}), "shadow job")
    if shadow.get("schemaVersion") != 1 or shadow.get("matchId") != request.match_id:
        raise RemoteContractError("shadow job identity is invalid")
    _text(shadow.get("generationId"), "generationId", 32, _GENERATION_ID)
    for key in ("requestDigest", "sourceSha256", "checkpointDigest", "jobIdentity"):
        _digest(shadow.get(key), key)
    deadline = shadow.get("deadlineSeconds")
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or not 0 < deadline <= 3600:
        raise RemoteContractError("shadow job deadline is invalid")
    identity_inputs = {key: shadow[key] for key in
        ("matchId", "generationId", "requestDigest", "checkpointDigest")}
    expected = hashlib.sha256(json.dumps(identity_inputs, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if shadow["jobIdentity"] != expected:
        raise RemoteContractError("shadow job identity is invalid")
    by_role = {item.role: item for item in receipt.files if item.role != "runtime_artifact"}
    sealed_inputs = {item.relative_path: item for item in receipt.files if item.role == "runtime_artifact"}
    checkpoint = sealed_inputs.get(PurePosixPath("inputs/checkpoint.bin"))
    segmentation_request = sealed_inputs.get(PurePosixPath("inputs/segmentation-request.json"))
    if by_role["input_video"].sha256 != shadow["sourceSha256"] \
            or checkpoint is None or checkpoint.sha256 != shadow["checkpointDigest"] \
            or segmentation_request is None or segmentation_request.sha256 != shadow["requestDigest"]:
        raise RemoteContractError("shadow input artifact identity mismatch")
    return shadow


def validate_result(request: JobRequest, receipt: JobReceipt, result: ResultBundle, *, output_root: Path | str | None = None) -> None:
    if result.job_id != request.job_id or result.match_id != request.match_id or result.source_commit != receipt.source_commit or result.manifest_sha256 != receipt.manifest_sha256:
        raise RemoteContractError("result identity or options mismatch")
    if canonical_json_bytes(result.requested_runtime_options, max_bytes=MAX_CONFIG_BYTES) != canonical_json_bytes(receipt.requested_runtime_options, max_bytes=MAX_CONFIG_BYTES):
        raise RemoteContractError("result identity or options mismatch")
    request_digest = hashlib.sha256(canonical_json_bytes(request.to_mapping())).hexdigest()
    if request_digest != receipt.job_request_sha256:
        raise RemoteContractError("request and receipt mismatch")
    receipt_digest = hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest()
    if result.receipt_sha256 != receipt_digest:
        raise RemoteContractError("result receipt identity mismatch")
    if result.schema_version == 3:
        shadow = validate_shadow_inputs(request, receipt)
        if any(result.result[key] != shadow[key] for key in
            ("generationId", "requestDigest", "sourceSha256", "checkpointDigest", "jobIdentity")):
            raise RemoteContractError("shadow result identity mismatch")
    elif request.config.get("jobKind") == "segmentation_shadow":
        raise RemoteContractError("shadow job requires segmentation result schema")
    if output_root is not None:
        progress_path = PurePosixPath(result.result["progressPath"])
        for item in result.artifacts:
            try:
                with confined_path(output_root, item.relative_path).open("rb") as handle:
                    if item.relative_path == progress_path:
                        snapshot = _read_progress_snapshot(handle)
                        identity = StreamIdentity(len(snapshot), hashlib.sha256(snapshot).hexdigest())
                        if identity.size_bytes != item.size_bytes:
                            raise RemoteContractError("stream size mismatch")
                        if identity.sha256 != item.sha256:
                            raise RemoteContractError("stream digest mismatch")
                        events = validate_progress_jsonl(BytesIO(snapshot), expected_job_id=result.job_id)
                        if len(events) != result.result["progressEventCount"]:
                            raise RemoteContractError("progress event count mismatch")
                    else:
                        stream_identity(handle, expected_size=item.size_bytes, expected_sha256=item.sha256)
            except RemoteContractError:
                raise
            except (OSError, ValueError, TypeError):
                raise RemoteContractError("result artifact cannot be read") from None


def validate_completion(root: Path | str, request: JobRequest, receipt: JobReceipt, result: ResultBundle, completion: CompletionReceipt) -> None:
    if completion.job_id != request.job_id or completion.match_id != request.match_id or completion.source_commit != receipt.source_commit or completion.manifest_sha256 != receipt.manifest_sha256:
        raise RemoteContractError("completion identity mismatch")
    _, completion_namespace, completion_generation = _generation_path(
        completion.result_path,
        "resultPath",
        _RESULT_FILENAME,
    )
    primary_key = "maskResultPath" if result.schema_version == 3 else "processorResultPath"
    primary_filename = (_SEGMENTATION_RESULT_FILENAME if result.schema_version == 3 else
        _PROCESSOR_RESULT_V2_FILENAME if result.schema_version == 2 else _PROCESSOR_RESULT_FILENAME)
    _, processor_namespace, processor_generation = _generation_path(
        result.result[primary_key], primary_key, primary_filename,
    )
    _, progress_namespace, progress_generation = _generation_path(
        result.result["progressPath"],
        "progressPath",
        _PROGRESS_FILENAME,
    )
    if (
        (completion_namespace, completion_generation)
        != (processor_namespace, processor_generation)
        or (completion_namespace, completion_generation)
        != (progress_namespace, progress_generation)
    ):
        raise RemoteContractError("completion and result artifacts must share one generation")
    path = confined_path(root, completion.result_path)
    try:
        with path.open("rb") as handle:
            _, loaded_bytes = _load_canonical_json(handle)
    except RemoteContractError:
        raise
    except (OSError, ValueError, TypeError):
        raise RemoteContractError("completion result cannot be read") from None
    if len(loaded_bytes) != completion.result_size_bytes:
        raise RemoteContractError("stream size mismatch")
    if hashlib.sha256(loaded_bytes).hexdigest() != completion.result_sha256:
        raise RemoteContractError("stream digest mismatch")
    if loaded_bytes != canonical_json_bytes(result.to_mapping(), max_bytes=MAX_RESULT_BYTES):
        raise RemoteContractError("completion result payload mismatch")
    validate_result(request, receipt, result, output_root=root)


def _is_secret_key(key: str) -> bool:
    if _SECRET_KEY.search(key):
        return True
    camel_separated = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", key)
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", camel_separated)
    if _SECRET_KEY_SUFFIX.search(camel_separated):
        return True
    compact = re.sub(r"[^a-z0-9]", "", key.lower())
    return compact.endswith(_SECRET_COMPACT_KEY_SUFFIXES)


def remote_diagnostics_contain_credentials(value: object) -> bool:
    """Fail closed when bounded JSON-like diagnostics contain credential material."""

    counter = [0]

    def visit(item: object, depth: int) -> bool:
        counter[0] += 1
        if counter[0] > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            return True
        if isinstance(item, str):
            return _SECRET_TEXT.search(str.__str__(item)) is not None
        if item is None or isinstance(item, (bool, int, float)):
            return False
        if isinstance(item, Mapping):
            try:
                entries = islice(item.items(), MAX_JSON_NODES + 1)
                for index, (key, child) in enumerate(entries):
                    if index >= MAX_JSON_NODES or not isinstance(key, str):
                        return True
                    safe_key = str.__str__(key)
                    if _is_secret_key(safe_key) or _SECRET_TEXT.search(safe_key) or visit(child, depth + 1):
                        return True
                return False
            except Exception:
                return True
        if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray, memoryview)):
            try:
                for index, child in enumerate(islice(iter(item), MAX_JSON_NODES + 1)):
                    if index >= MAX_JSON_NODES or visit(child, depth + 1):
                        return True
                return False
            except Exception:
                return True
        return False

    return visit(value, 0)


def redact_remote_diagnostics(value: object, *, max_output_chars: int = 8192, max_depth: int = 8, max_items: int = 100) -> object:
    """Return bounded, JSON-safe diagnostics without invoking arbitrary __str__."""

    maximum = _integer(max_output_chars, "maximum diagnostic length", 32, 1_000_000)
    depth_limit = _integer(max_depth, "maximum diagnostic depth", 0, 64)
    item_limit = _integer(max_items, "maximum diagnostic items", 1, 10_000)
    budget = [maximum]
    def visit(item: object, depth: int, key: str = "") -> object:
        if _is_secret_key(key): return "[REDACTED]"
        if depth > depth_limit: return "[TRUNCATED]"
        if item is None or isinstance(item, bool):
            return item
        if isinstance(item, int):
            return item if int.bit_length(item) <= 53 else "[OVERSIZED_INTEGER]"
        if isinstance(item, float): return item if math.isfinite(item) else "[NONFINITE]"
        if isinstance(item, str):
            safe_item = str.__str__(item)
            if _SECRET_TEXT.search(safe_item):
                return "[REDACTED]"
            take = max(0, min(len(safe_item), budget[0], 512)); budget[0] -= take
            return safe_item[:take] + ("...[TRUNCATED]" if take < len(safe_item) else "")
        if isinstance(item, Mapping):
            result: dict[str, object] = {}
            try:
                iterator = islice(item.items(), item_limit)
                for raw_key, child in iterator:
                    safe_key = raw_key if isinstance(raw_key, str) else "[NONSTRING_KEY]"
                    if _is_secret_key(safe_key) or _SECRET_TEXT.search(safe_key):
                        result["[REDACTED_KEY]"] = "[REDACTED]"
                    else:
                        result[safe_key[:128]] = visit(child, depth + 1, safe_key)
            except Exception:
                result["__unavailable__"] = True
            return result
        if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray, memoryview)):
            result_items: list[object] = []
            try:
                for child in islice(iter(item), item_limit):
                    result_items.append(visit(child, depth + 1))
            except Exception:
                result_items.append("[UNAVAILABLE]")
            return result_items
        return "[UNSUPPORTED]"
    result = visit(value, 0)
    # Enforce the serialized boundary too, without ever serializing the original.
    try:
        rendered = json.dumps(result, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    except Exception:
        return "[REDACTED]"
    if not isinstance(rendered, str) or len(rendered) > maximum:
        return "[REDACTED]"
    return result
