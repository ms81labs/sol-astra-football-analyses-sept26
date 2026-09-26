"""Fail-closed Daytona transport for sealed GPU jobs.

The SDK is deliberately imported only by the production factory after local
preflight has succeeded.
"""
from __future__ import annotations

import logging

from collections.abc import Callable, Iterator
from contextlib import ExitStack, nullcontext
import ctypes
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
from typing import Any, Protocol

from backend.app.gpu_worker import LIVE_PROGRESS_PREFIX
from backend.app.remote_contracts import (
    MAX_PROCESSOR_RESULT_BYTES, MAX_SEGMENTATION_RESULT_BYTES, MAX_PROGRESS_EVENTS, MAX_PROGRESS_LINE_BYTES,
    MAX_PROGRESS_TOTAL_BYTES, MAX_RESULT_BYTES,
    CompletionReceipt, JobReceipt,
    JobRequest, ProgressEvent, ResultBundle, canonical_json_bytes, confined_path,
    load_canonical_json, validate_completion,
    validate_result,
)
from backend.release.daytona_policy import DaytonaPolicy, load_daytona_policy
from backend.release.preflight import PreflightResult


LOGGER = logging.getLogger(__name__)

INPUT_ROOT = "/home/daytona/job"
OUTPUT_ROOT = INPUT_ROOT
EXECUTION_COMMAND = (
    "python -m backend.app.gpu_worker "
    "--request /home/daytona/job/job-request.json "
    "--result /home/daytona/job/result-bundle.json "
    "--completion-receipt /home/daytona/job/completion-receipt.json"
)
_SANDBOX_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")
_PATH_TYPE = type(Path())
_SDK_NAME_PREFIX = "fa-"
_SDK_OWNER_LABEL = "football-analyst-owner"
_LIVE_PROGRESS_PREFIX_BYTES = LIVE_PROGRESS_PREFIX.encode("ascii")


class DaytonaExecutionError(RuntimeError):
    """Stable, secret-safe lifecycle failure."""


class _LocalStagingCleanupError(DaytonaExecutionError):
    """Internal typed signal that local staging cleanup was not confirmed."""


class _UnreturnedSandboxCleanupError(DaytonaExecutionError):
    """Carry an unreturned sandbox into the caller's cleanup path."""

    def __init__(self, sandbox: Any):
        super().__init__("create: sandbox cleanup was not confirmed")
        self.sandbox = sandbox


class DaytonaConfirmedAbsent(Exception):
    """The provider explicitly confirmed a cleanup target is absent."""


@dataclass(frozen=True, slots=True)
class DaytonaExecutionRequest:
    api_key: str
    policy: DaytonaPolicy
    bundle_root: Path
    workspace: Path
    preflight: PreflightResult

    def __repr__(self) -> str:
        return (
            "DaytonaExecutionRequest(api_key='[REDACTED]', "
            f"policy={self.policy!r}, bundle_root={self.bundle_root!r}, "
            f"workspace={self.workspace!r}, preflight={self.preflight!r})"
        )


@dataclass(frozen=True, slots=True)
class DaytonaSandboxSpec:
    image: str
    public: bool
    ephemeral: bool
    spot: bool
    ttl_minutes: int
    network_block_all: bool
    env_vars: tuple[()]
    cpu: int
    memory_gib: int
    disk_gib: int
    gpu: int
    gpu_types: tuple[str, str]


@dataclass(frozen=True, slots=True)
class SessionCommand:
    command: str
    run_async: bool


@dataclass(frozen=True, slots=True)
class DaytonaDiagnostics:
    stdout: str

    def __post_init__(self) -> None:
        if type(self.stdout) is not str or self.stdout != "[REDACTED]":
            raise DaytonaExecutionError("execute: diagnostics are invalid")


@dataclass(frozen=True, slots=True)
class DaytonaExecutionResult:
    sandbox_id: str
    completion: CompletionReceipt
    result: ResultBundle
    staging_root: Path
    processor_path: Path
    progress_path: Path
    diagnostics: DaytonaDiagnostics

    def __post_init__(self) -> None:
        if (
            type(self.sandbox_id) is not str
            or _SANDBOX_ID.fullmatch(self.sandbox_id) is None
            or type(self.completion) is not CompletionReceipt
            or type(self.result) is not ResultBundle
            or type(self.staging_root) is not _PATH_TYPE
            or type(self.processor_path) is not _PATH_TYPE
            or type(self.progress_path) is not _PATH_TYPE
            or type(self.diagnostics) is not DaytonaDiagnostics
        ):
            raise DaytonaExecutionError("execute: result interface is invalid")
        try:
            processor_relative = self.processor_path.relative_to(self.staging_root)
            progress_relative = self.progress_path.relative_to(self.staging_root)
            if (
                confined_path(self.staging_root, PurePosixPath(processor_relative.as_posix()))
                != self.processor_path
                or confined_path(self.staging_root, PurePosixPath(progress_relative.as_posix()))
                != self.progress_path
                or PurePosixPath(processor_relative.as_posix()) != self.result.primary_artifact_path
                or PurePosixPath(progress_relative.as_posix()) != PurePosixPath(self.result.result["progressPath"])
            ):
                raise ValueError
        except Exception:
            raise DaytonaExecutionError("execute: result interface paths are invalid") from None


class _Filesystem(Protocol):
    def upload_file_stream(self, source: Any, remote_path: str, timeout: int) -> None: ...
    def download_file_stream(self, remote_path: str, timeout: int) -> Iterator[bytes]: ...


class _Process(Protocol):
    def create_session(self, session_id: str, request_timeout: float | None = None) -> None: ...
    def execute_session_command(self, session_id: str, req: Any, timeout: int | None = None) -> Any: ...
    def get_session_command(self, session_id: str, command_id: str, request_timeout: float | None = None) -> Any: ...
    def get_session_command_logs(self, session_id: str, command_id: str, request_timeout: float | None = None) -> Any: ...
    def delete_session(self, session_id: str, request_timeout: float | None = None) -> None: ...


class _Sandbox(Protocol):
    id: str
    fs: _Filesystem
    process: _Process


class _Client(Protocol):
    def create(self, spec: DaytonaSandboxSpec, timeout: int) -> _Sandbox: ...
    def delete(self, sandbox: _Sandbox, timeout: int, wait: bool) -> None: ...
    def get(self, sandbox_id: str, timeout: int) -> _Sandbox: ...


ClientFactory = Callable[[str, str], _Client]


class _SdkProcess:
    def __init__(self, process: Any, sdk: Any):
        self._process = process
        self._sdk = sdk

    def create_session(self, session_id: str, request_timeout: float | None = None) -> None:
        self._process.create_session(session_id, request_timeout=request_timeout)

    def execute_session_command(self, session_id: str, req: SessionCommand,
                                timeout: int | None = None) -> Any:
        return self._process.execute_session_command(
            session_id,
            self._sdk.SessionExecuteRequest(
                command=req.command, run_async=req.run_async
            ),
            timeout=timeout,
        )

    def get_session_command(self, session_id: str, command_id: str,
                            request_timeout: float | None = None) -> Any:
        return self._process.get_session_command(
            session_id, command_id, request_timeout=request_timeout
        )

    def get_session_command_logs(self, session_id: str, command_id: str,
                                 request_timeout: float | None = None) -> Any:
        return self._process.get_session_command_logs(
            session_id, command_id, request_timeout=request_timeout
        )

    def delete_session(self, session_id: str, request_timeout: float | None = None) -> None:
        self._process.delete_session(session_id, request_timeout=request_timeout)


class _SdkSandbox:
    def __init__(self, sandbox: Any, sdk: Any):
        self._sandbox = sandbox
        self._sdk = sdk

    @property
    def id(self) -> str:
        return self._sandbox.id

    @property
    def fs(self) -> _Filesystem:
        return self._sandbox.fs

    @property
    def process(self) -> _Process:
        return _SdkProcess(self._sandbox.process, self._sdk)


class _SdkClient:
    _CREATE_CLEANUP_ATTEMPTS = 3

    def __init__(self, client: Any, sdk: Any, *, image: Any = None,
                 image_factory: Callable[[], Any] | None = None):
        self._client = client
        self._sdk = sdk
        self._image = image
        self._image_factory = image_factory

    def create(self, spec: DaytonaSandboxSpec, timeout: int) -> _Sandbox:
        owner_token = os.urandom(16).hex()
        sandbox_name = f"{_SDK_NAME_PREFIX}{owner_token}"
        types = {"RTX-PRO-6000": self._sdk.GpuType.RTX_PRO_6000, "H100": self._sdk.GpuType.H100}
        context = self._image_factory() if self._image_factory is not None else nullcontext(
            self._image if self._image is not None else spec.image
        )
        sandbox = None
        try:
            with context as image:
                params = self._sdk.CreateSandboxFromImageParams(
                    name=sandbox_name, labels={_SDK_OWNER_LABEL: owner_token},
                    image=image, public=spec.public, ephemeral=spec.ephemeral,
                    spot=spec.spot, ttl_minutes=spec.ttl_minutes,
                    network_block_all=spec.network_block_all, env_vars={},
                    resources=self._sdk.Resources(
                        cpu=spec.cpu, memory=spec.memory_gib, disk=spec.disk_gib,
                        gpu=spec.gpu, gpu_type=[types[item] for item in spec.gpu_types],
                    ),
                )
                sandbox = self._client.create(params, timeout=timeout)
        except BaseException as create_failure:
            if sandbox is None:
                try:
                    candidate = self.get(sandbox_name, timeout=timeout)
                except DaytonaConfirmedAbsent:
                    raise create_failure from None
                except BaseException:
                    raise DaytonaExecutionError(
                        "create: sandbox cleanup was not confirmed"
                    ) from None
                try:
                    owned = (
                        candidate.name == sandbox_name
                        and type(candidate.labels) is dict
                        and candidate.labels[_SDK_OWNER_LABEL] == owner_token
                    )
                except BaseException:
                    owned = False
                if not owned:
                    raise DaytonaExecutionError(
                        "create: sandbox cleanup was not confirmed"
                    ) from None
                sandbox = candidate
            if not self._cleanup_unreturned_sandbox(sandbox, timeout):
                raise _UnreturnedSandboxCleanupError(sandbox) from None
            raise create_failure
        return _SdkSandbox(sandbox, self._sdk)

    def _cleanup_unreturned_sandbox(self, sandbox: _Sandbox, timeout: int) -> bool:
        for _ in range(self._CREATE_CLEANUP_ATTEMPTS):
            try:
                self.delete(sandbox, timeout=timeout, wait=True)
            except DaytonaConfirmedAbsent:
                return True
            except BaseException:
                LOGGER.warning("unreturned sandbox cleanup delete failed")
            try:
                self.get(sandbox.id, timeout=timeout)
            except DaytonaConfirmedAbsent:
                return True
            except BaseException:
                LOGGER.warning("unreturned sandbox cleanup confirmation failed")
        return False

    def delete(self, sandbox: _Sandbox, timeout: int, wait: bool) -> None:
        try:
            target = sandbox._sandbox if isinstance(sandbox, _SdkSandbox) else sandbox
            self._client.delete(target, timeout=timeout, wait=wait)
        except self._sdk.DaytonaNotFoundError:
            raise DaytonaConfirmedAbsent() from None

    def get(self, sandbox_id: str, timeout: int) -> _Sandbox:
        try:
            return self._client.get(sandbox_id, request_timeout=timeout)
        except self._sdk.DaytonaNotFoundError:
            raise DaytonaConfirmedAbsent() from None


def _production_client_factory(api_key: str, target: str, *, image: Any = None,
                               image_factory: Callable[[], Any] | None = None,
                               repo_root: Path | None = None) -> _Client:
    import daytona as sdk  # type: ignore[import-not-found]
    if image is None and image_factory is None:
        from backend.app.daytona_worker_image import worker_image_factory
        image_factory = worker_image_factory(sdk, repo_root or Path(__file__).resolve().parents[2])
    return _SdkClient(sdk.Daytona(sdk.DaytonaConfig(api_key=api_key, target=target)), sdk,
                      image=image, image_factory=image_factory)


def _safe_root(value: object, label: str) -> Path:
    if type(value) is not _PATH_TYPE or not value.is_absolute():
        raise DaytonaExecutionError(f"preflight: {label} is invalid")
    try:
        before = value.lstat()
        resolved = value.resolve(strict=True)
        after = resolved.stat()
    except OSError:
        raise DaytonaExecutionError(f"preflight: {label} is unavailable") from None
    if value.is_symlink() or not resolved.is_dir() or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise DaytonaExecutionError(f"preflight: {label} is unsafe")
    return resolved


def _open_preflight_regular_file(path: object) -> int:
    """Open one exact absolute regular file through a no-follow descriptor chain."""
    if type(path) is not _PATH_TYPE or not path.is_absolute():
        raise DaytonaExecutionError("preflight: release file path is invalid")
    if any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise DaytonaExecutionError("preflight: release file path is not normalized")
    current = os.open(
        "/",
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
    )
    descriptor = -1
    try:
        for part in path.parts[1:-1]:
            next_descriptor = os.open(
                part,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current,
            )
            os.close(current)
            current = next_descriptor
        descriptor = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=current,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            os.close(descriptor)
            descriptor = -1
            raise DaytonaExecutionError("preflight: release file is not regular")
        return descriptor
    except DaytonaExecutionError:
        raise
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        raise DaytonaExecutionError("preflight: release file cannot be opened safely") from None
    finally:
        os.close(current)


def _preflight_file_identity(path: object) -> tuple[str, int]:
    descriptor = _open_preflight_regular_file(path)
    try:
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                return digest.hexdigest(), size
            digest.update(chunk)
            size += len(chunk)
    except OSError:
        raise DaytonaExecutionError("preflight: release file cannot be read safely") from None
    finally:
        os.close(descriptor)


def _read_preflight_contract(path: object, expected: type[Any]) -> tuple[Any, tuple[str, int]]:
    descriptor = _open_preflight_regular_file(path)
    try:
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            value = expected.from_mapping(load_canonical_json(handle))
        payload = canonical_json_bytes(value.to_mapping(), max_bytes=MAX_RESULT_BYTES)
        return value, (hashlib.sha256(payload).hexdigest(), len(payload))
    except Exception:
        raise DaytonaExecutionError("preflight: sealed contract is invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _preflight(execution: DaytonaExecutionRequest) -> tuple[Path, Path, JobRequest, JobReceipt, tuple[PurePosixPath, ...], dict[PurePosixPath, tuple[str, int]]]:
    if type(execution) is not DaytonaExecutionRequest:
        raise DaytonaExecutionError("preflight: execution request type is invalid")
    key = execution.api_key
    if type(key) is not str or not key.strip() or len(key) > 4096 or "\0" in key:
        raise DaytonaExecutionError("preflight: API key is invalid")
    if type(execution.policy) is not DaytonaPolicy or execution.policy != load_daytona_policy():
        raise DaytonaExecutionError("preflight: policy identity mismatch")
    if type(execution.preflight) is not PreflightResult:
        raise DaytonaExecutionError("preflight: release evidence type is invalid")
    root = _safe_root(execution.bundle_root, "bundle root")
    workspace = _safe_root(execution.workspace, "workspace")
    request_path = confined_path(root, "job-request.json")
    request, request_identity = _read_preflight_contract(request_path, JobRequest)
    if request.config.get("jobKind") == "segmentation_shadow":
        raise DaytonaExecutionError("preflight: SAM release preflight is unavailable")
    receipt_path = confined_path(root, request.receipt_path)
    receipt, receipt_identity = _read_preflight_contract(receipt_path, JobReceipt)
    try:
        by_role = {entry.role: entry for entry in receipt.files}
        if by_role["input_video"].relative_path != request.input_video_path:
            raise ValueError
        if request_identity != (
            by_role["job_request"].sha256,
            by_role["job_request"].size_bytes,
        ):
            raise ValueError
        receipt_bytes = canonical_json_bytes(receipt.to_mapping(), max_bytes=MAX_RESULT_BYTES)
        if receipt_identity != (hashlib.sha256(receipt_bytes).hexdigest(), len(receipt_bytes)):
            raise ValueError
        for entry in receipt.files:
            if _preflight_file_identity(confined_path(root, entry.relative_path)) != (
                entry.sha256,
                entry.size_bytes,
            ):
                raise ValueError
    except Exception:
        raise DaytonaExecutionError("preflight: sealed file identity mismatch") from None
    proof = execution.preflight
    if (proof.source_commit != receipt.source_commit or
        proof.manifest_sha256 != receipt.manifest_sha256 or
        proof.evidence_sha256 != receipt.evidence_sha256 or proof.evidence_phase != "pre_cloud"):
        raise DaytonaExecutionError("preflight: release identity mismatch")
    roles = {entry.role: entry for entry in receipt.files if entry.role in {"manifest", "evidence"}}
    for role, live in (("manifest", proof.manifest_path), ("evidence", proof.evidence_path)):
        try:
            entry = roles[role]
            if _preflight_file_identity(live) != (entry.sha256, entry.size_bytes):
                raise ValueError
        except Exception:
            raise DaytonaExecutionError("preflight: release file binding mismatch") from None
    try:
        if type(proof.artifacts) is not tuple or type(proof.artifact_metadata) is not tuple:
            raise ValueError
        artifact_ids: list[str] = []
        for item in proof.artifacts:
            if (
                type(item) is not tuple
                or len(item) != 3
                or type(item[0]) is not str
                or not item[0]
                or len(item[0]) > 256
                or "\0" in item[0]
            ):
                raise ValueError
            artifact_ids.append(item[0])
        metadata_ids: list[str] = []
        for item in proof.artifact_metadata:
            if (
                type(item) is not tuple
                or len(item) != 3
                or type(item[0]) is not str
                or not item[0]
                or len(item[0]) > 256
                or "\0" in item[0]
                or type(item[1]) is not str
                or type(item[2]) is not int
            ):
                raise ValueError
            metadata_ids.append(item[0])
        if (
            len(artifact_ids) != len(set(artifact_ids))
            or len(metadata_ids) != len(set(metadata_ids))
            or set(artifact_ids) != set(metadata_ids)
        ):
            raise ValueError
        metadata = {item[0]: (item[1], item[2]) for item in proof.artifact_metadata}
        proof_ids = []
        for artifact_id, local_path, container_path in proof.artifacts:
            if type(artifact_id) is not str or type(local_path) is not _PATH_TYPE or type(container_path) is not str: raise ValueError
            if not container_path.startswith(("/app/models/", "/app/release-inputs/")): raise ValueError
            relative = PurePosixPath(container_path.removeprefix("/app/"))
            if ".." in relative.parts or relative.as_posix() != container_path.removeprefix("/app/"): raise ValueError
            identity = _preflight_file_identity(local_path)
            if metadata.get(artifact_id) != identity: raise ValueError
            proof_ids.append((relative, *identity))
        sealed = [(e.relative_path, e.sha256, e.size_bytes) for e in receipt.files
                  if e.role == "runtime_artifact"]
        if sorted(proof_ids) != sorted(sealed): raise ValueError
    except Exception:
        raise DaytonaExecutionError("preflight: release artifact binding mismatch") from None
    paths = {entry.relative_path for entry in receipt.files}; paths.add(request.receipt_path)
    if PurePosixPath("job-request.json") not in paths:
        raise DaytonaExecutionError("preflight: request upload binding mismatch")
    for relative in paths: confined_path(root, relative)
    identities = {entry.relative_path: (entry.sha256, entry.size_bytes) for entry in receipt.files}
    identities[request.receipt_path] = receipt_identity
    return root, workspace, request, receipt, tuple(sorted(paths, key=PurePosixPath.as_posix)), identities


def _sandbox_spec(policy: DaytonaPolicy) -> DaytonaSandboxSpec:
    return DaytonaSandboxSpec(policy.image, policy.public, policy.ephemeral, policy.spot,
        policy.ttl_minutes, policy.network_block_all, (), policy.cpu,
        policy.memory_gib, policy.disk_gib, policy.gpu, policy.gpu_types)


def _sandbox_identifier(sandbox: _Sandbox) -> str:
    value = sandbox.id
    if type(value) is not str or _SANDBOX_ID.fullmatch(value) is None:
        raise DaytonaExecutionError("create: sandbox identity is invalid")
    return value


def _sandbox_error_reference(sandbox_id: str) -> str:
    """Return a bounded correlation value without copying provider text."""
    if type(sandbox_id) is not str:
        return "unavailable"
    return hashlib.sha256(str.__str__(sandbox_id).encode("utf-8")).hexdigest()[:16]


def _download(fs: _Filesystem, remote: str, local: Path, *, timeout: int,
              maximum: int, expected_size: int | None = None,
              expected_sha256: str | None = None) -> None:
    if local.exists() or local.is_symlink():
        raise DaytonaExecutionError("download: local destination already exists")
    local.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if local.parent.is_symlink():
        raise DaytonaExecutionError("download: local destination is unsafe")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1; size = 0; digest = hashlib.sha256()
    stream: object | None = None
    iterator: object | None = None
    try:
        descriptor = os.open(local, flags, 0o600)
        stream = fs.download_file_stream(remote, timeout=timeout)
        iterator = iter(stream)
        for chunk in iterator:
            if type(chunk) is not bytes:
                raise DaytonaExecutionError("download: provider stream is invalid")
            size += len(chunk)
            if size > maximum:
                raise DaytonaExecutionError("download: stream exceeds size limit")
            digest.update(chunk); view = memoryview(chunk)
            while view:
                view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
    except DaytonaExecutionError:
        raise
    except Exception:
        raise DaytonaExecutionError("download: provider transfer failed") from None
    finally:
        closed: set[int] = set()
        for candidate in (iterator, stream):
            if candidate is None or id(candidate) in closed:
                continue
            closed.add(id(candidate))
            try:
                close = getattr(candidate, "close", None)
                if callable(close):
                    close()
            except Exception:
                LOGGER.warning("download stream close failed")
        if descriptor >= 0: os.close(descriptor)
    if expected_size is not None and size != expected_size:
        raise DaytonaExecutionError("download: stream size mismatch")
    if expected_sha256 is not None and digest.hexdigest() != expected_sha256:
        raise DaytonaExecutionError("download: stream digest mismatch")


def _remote_output(relative: PurePosixPath) -> str:
    return f"{OUTPUT_ROOT}/{relative.as_posix()}"


def _validate_completion_envelope(
    request: JobRequest,
    receipt: JobReceipt,
    completion: CompletionReceipt,
) -> None:
    """Authorize the fixed result namespace before requesting the result file."""
    path = completion.result_path
    if (
        completion.job_id != request.job_id
        or completion.match_id != request.match_id
        or completion.source_commit != receipt.source_commit
        or completion.manifest_sha256 != receipt.manifest_sha256
        or len(path.parts) != 3
        or path.parts[0] != "result-bundle.json.generations"
        or _GENERATION_ID.fullmatch(path.parts[1]) is None
        or path.parts[2] != "result.json"
    ):
        raise DaytonaExecutionError("download: completion envelope binding failed")


def _validate_result_envelopes(
    request: JobRequest,
    receipt: JobReceipt,
    completion: CompletionReceipt,
    result: ResultBundle,
) -> None:
    """Reject identity or generation mismatches before artifact transport."""
    try:
        validate_result(request, receipt, result)
        if (
            completion.job_id != request.job_id
            or completion.match_id != request.match_id
            or completion.source_commit != receipt.source_commit
            or completion.manifest_sha256 != receipt.manifest_sha256
        ):
            raise ValueError
        result_path = completion.result_path
        processor_path = result.primary_artifact_path
        progress_path = PurePosixPath(result.result["progressPath"])
        if (
            len(result_path.parts) != 3
            or result_path.parts[0] != "result-bundle.json.generations"
            or result_path.parent != processor_path.parent
            or result_path.parent != progress_path.parent
        ):
            raise ValueError
    except Exception:
        raise DaytonaExecutionError("download: result envelope binding failed") from None


def _bounded_rmtree(parent_fd: int, name: str, depth: int = 0) -> None:
    if depth > 64:
        raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
    )
    try:
        entries = os.listdir(descriptor)
        if len(entries) > 100_000:
            raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
        for entry in entries:
            opened = os.stat(entry, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(opened.st_mode) and not stat.S_ISLNK(opened.st_mode):
                _bounded_rmtree(descriptor, entry, depth + 1)
            else:
                os.unlink(entry, dir_fd=descriptor)
    finally:
        os.close(descriptor)
    os.rmdir(name, dir_fd=parent_fd)


def _rename_noreplace(
    source_parent_fd: int,
    source: str,
    destination_parent_fd: int,
    destination: str,
) -> None:
    """Atomically move one name without replacing any destination entry.

    The adapter requires Linux renameat2; unavailable platforms fail closed.
    """
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError):
        raise OSError(errno.ENOSYS, "renameat2 is unavailable") from None
    result = renameat2(
        source_parent_fd,
        ctypes.c_char_p(os.fsencode(source)),
        destination_parent_fd,
        ctypes.c_char_p(os.fsencode(destination)),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _close_descriptors(*descriptors: int) -> None:
    failed = False
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except Exception:
            failed = True
    if failed:
        raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")


def _create_private_directory(
    parent_fd: int,
    prefix: str,
    close_descriptor: Callable[[int], None] = _close_descriptors,
) -> tuple[str, int]:
    """Create and retain a fresh 0700 directory relative to an open parent."""
    for _ in range(128):
        name = f"{prefix}{os.urandom(16).hex()}"
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        descriptor = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
        )
        try:
            opened = os.fstat(descriptor)
            if stat.S_ISDIR(opened.st_mode) and stat.S_IMODE(opened.st_mode) == 0o700:
                return name, descriptor
        except Exception:
            close_descriptor(descriptor)
            raise DaytonaExecutionError(
                "cleanup: local staging cleanup was not confirmed"
            ) from None
        close_descriptor(descriptor)
        raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
    raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")


class _StagingOwner:
    """Retain staging identity until deletion or caller transfer.

    Cleanup resists untrusted directory entries and workspace-name substitution.
    It assumes a privileged or same-UID process does not modify the private 0700
    quarantine; such a process is outside this adapter's local threat model.
    A non-EBADF close failure makes that numeric descriptor irrecoverably
    uncertain: it is retained, never retried, and may remain open until process
    teardown rather than risking closure of a caller-reused descriptor number.
    """

    def __init__(self, workspace: Path, staging: Path):
        self.workspace = workspace
        self.staging = staging
        self.workspace_fd = -1
        self.staging_fd = -1
        self.cleanup_workspace_fd = -1
        self.cleanup_staging_fd = -1
        self._uncertain_descriptors: set[str] = set()
        self._poisoned_descriptors: set[int] = set()
        self._local_descriptor_uncertainty = False
        self.descriptors: tuple[int, ...] = ()
        self.closed = True
        try:
            self.workspace_fd = os.open(
                workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            self.staging_fd = os.open(
                staging.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=self.workspace_fd,
            )
            workspace_opened = os.fstat(self.workspace_fd)
            staging_opened = os.fstat(self.staging_fd)
            self.cleanup_workspace_fd = os.dup(self.workspace_fd)
            self.cleanup_staging_fd = os.dup(self.staging_fd)
        except Exception:
            descriptors = tuple(
                descriptor
                for descriptor in (
                    self.cleanup_staging_fd,
                    self.cleanup_workspace_fd,
                    self.staging_fd,
                    self.workspace_fd,
                )
                if descriptor >= 0
            )
            _close_descriptors(*descriptors)
            raise DaytonaExecutionError(
                "cleanup: local staging cleanup was not confirmed"
            ) from None
        self.workspace_identity = (workspace_opened.st_dev, workspace_opened.st_ino)
        self.identity = (staging_opened.st_dev, staging_opened.st_ino)
        self.descriptors = (
            self.staging_fd,
            self.workspace_fd,
            self.cleanup_staging_fd,
            self.cleanup_workspace_fd,
        )
        self.closed = False

    def _attempt_close(self, attribute: str) -> bool:
        descriptor = getattr(self, attribute)
        if descriptor < 0:
            return True
        try:
            os.close(descriptor)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                setattr(self, attribute, -1)
                self._uncertain_descriptors.discard(attribute)
                return True
            self._poisoned_descriptors.add(descriptor)
            self._uncertain_descriptors.add(attribute)
            self._local_descriptor_uncertainty = True
            return False
        except Exception:
            self._poisoned_descriptors.add(descriptor)
            self._uncertain_descriptors.add(attribute)
            self._local_descriptor_uncertainty = True
            return False
        setattr(self, attribute, -1)
        self._uncertain_descriptors.discard(attribute)
        return True

    def _close_all(self) -> None:
        failed = False
        for attribute in (
            "staging_fd",
            "workspace_fd",
            "cleanup_staging_fd",
            "cleanup_workspace_fd",
        ):
            if attribute in self._uncertain_descriptors:
                closed = False
            else:
                closed = self._attempt_close(attribute)
            if not closed:
                failed = True
        self.closed = all(getattr(self, attribute) < 0 for attribute in (
            "staging_fd", "workspace_fd", "cleanup_staging_fd", "cleanup_workspace_fd"
        ))
        if failed:
            raise _LocalStagingCleanupError(
                "cleanup: local staging cleanup was not confirmed"
            )

    def _close_temporary_descriptor(self, descriptor: int) -> None:
        try:
            os.close(descriptor)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                return
            self._poisoned_descriptors.add(descriptor)
            self._local_descriptor_uncertainty = True
            raise _LocalStagingCleanupError(
                "cleanup: local staging cleanup was not confirmed"
            ) from None
        except Exception:
            self._poisoned_descriptors.add(descriptor)
            self._local_descriptor_uncertainty = True
            raise _LocalStagingCleanupError(
                "cleanup: local staging cleanup was not confirmed"
            ) from None

    def _halt_poisoned_cleanup(self) -> None:
        for attribute in (
            "staging_fd",
            "workspace_fd",
            "cleanup_staging_fd",
            "cleanup_workspace_fd",
        ):
            descriptor = getattr(self, attribute)
            if (
                descriptor < 0
                or descriptor in self._poisoned_descriptors
                or attribute in self._uncertain_descriptors
            ):
                continue
            self._attempt_close(attribute)
        self.closed = all(getattr(self, attribute) < 0 for attribute in (
            "staging_fd", "workspace_fd", "cleanup_staging_fd", "cleanup_workspace_fd"
        ))
        raise _LocalStagingCleanupError(
            "cleanup: local staging cleanup was not confirmed"
        )

    def _halt_after_external_poison(self, descriptors: set[int]) -> None:
        self._poisoned_descriptors.update(descriptors)
        self._halt_poisoned_cleanup()

    def _validated_descriptor(
        self, attributes: tuple[str, ...], identity: tuple[int, int]
    ) -> int | None:
        for attribute in attributes:
            descriptor = getattr(self, attribute)
            if descriptor < 0:
                continue
            if attribute in self._uncertain_descriptors:
                self._local_descriptor_uncertainty = True
                continue
            try:
                opened = os.fstat(descriptor)
            except OSError:
                raise _LocalStagingCleanupError(
                    "cleanup: local staging cleanup was not confirmed"
                ) from None
            except Exception:
                raise _LocalStagingCleanupError(
                    "cleanup: local staging cleanup was not confirmed"
                ) from None
            if (opened.st_dev, opened.st_ino) == identity:
                return descriptor
            raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
        return None

    def _cleanup_descriptors(self) -> tuple[int, int | None]:
        workspace_fd = self._validated_descriptor(
            ("cleanup_workspace_fd", "workspace_fd"), self.workspace_identity
        )
        staging_fd = self._validated_descriptor(
            ("cleanup_staging_fd", "staging_fd"), self.identity
        )
        if workspace_fd is None and staging_fd is not None:
            derived = -1
            try:
                derived = os.open(
                    "..",
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=staging_fd,
                )
                opened = os.fstat(derived)
            except Exception:
                if derived >= 0:
                    _close_descriptors(derived)
                raise DaytonaExecutionError(
                    "cleanup: local staging cleanup was not confirmed"
                ) from None
            if (opened.st_dev, opened.st_ino) != self.workspace_identity:
                _close_descriptors(derived)
                raise DaytonaExecutionError(
                    "cleanup: local staging cleanup was not confirmed"
                )
            if self.workspace_fd >= 0:
                _close_descriptors(derived)
                raise DaytonaExecutionError(
                    "cleanup: local staging cleanup was not confirmed"
                )
            self.workspace_fd = derived
            workspace_fd = derived
        if workspace_fd is None:
            raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
        return workspace_fd, staging_fd

    def release(self) -> None:
        transfer_failed = False
        for attribute in ("staging_fd", "workspace_fd"):
            if not self._attempt_close(attribute):
                transfer_failed = True
        if transfer_failed:
            try:
                self.cleanup()
            except DaytonaExecutionError:
                raise DaytonaExecutionError(
                    "cleanup: local staging cleanup was not confirmed"
                ) from None
            raise DaytonaExecutionError(
                "cleanup: staging ownership transfer was not confirmed"
            )
        for attribute in ("cleanup_workspace_fd", "cleanup_staging_fd"):
            if not self._attempt_close(attribute):
                try:
                    self.cleanup()
                except DaytonaExecutionError:
                    raise DaytonaExecutionError(
                        "cleanup: local staging cleanup was not confirmed"
                    ) from None
                raise DaytonaExecutionError(
                    "cleanup: staging ownership transfer was not confirmed"
                )
        self.closed = True

    def cleanup(self) -> None:
        if self._poisoned_descriptors:
            self._halt_poisoned_cleanup()
        quarantine_name: str | None = None
        quarantine_fd: int | None = None
        descriptors_closed = False
        entry = f"staging-{os.urandom(16).hex()}"
        try:
            workspace_fd, _ = self._cleanup_descriptors()
            quarantine_name, quarantine_fd = _create_private_directory(
                workspace_fd,
                ".daytona-quarantine-",
                self._close_temporary_descriptor,
            )
            _rename_noreplace(
                workspace_fd,
                self.staging.name,
                quarantine_fd,
                entry,
            )
            moved = os.stat(entry, dir_fd=quarantine_fd, follow_symlinks=False)
            moved_identity = (moved.st_dev, moved.st_ino)
            if moved_identity != self.identity:
                _rename_noreplace(
                    quarantine_fd,
                    entry,
                    workspace_fd,
                    self.staging.name,
                )
                try:
                    os.stat(entry, dir_fd=quarantine_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise DaytonaExecutionError(
                        "cleanup: local staging cleanup was not confirmed"
                    )
                restored = os.stat(
                    self.staging.name,
                    dir_fd=workspace_fd,
                    follow_symlinks=False,
                )
                if (restored.st_dev, restored.st_ino) != moved_identity:
                    raise DaytonaExecutionError(
                        "cleanup: local staging cleanup was not confirmed"
                    )
                closing_fd = quarantine_fd
                quarantine_fd = None
                self._close_temporary_descriptor(closing_fd)
                os.rmdir(quarantine_name, dir_fd=workspace_fd)
                try:
                    os.stat(
                        quarantine_name,
                        dir_fd=workspace_fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    raise DaytonaExecutionError(
                        "cleanup: local staging cleanup was not confirmed"
                    )
                raise DaytonaExecutionError(
                    "cleanup: local staging cleanup was not confirmed"
                )
            moved_fd = os.open(
                entry,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=quarantine_fd,
            )
            try:
                retained = os.fstat(moved_fd)
                retained_identity = (retained.st_dev, retained.st_ino)
            finally:
                self._close_temporary_descriptor(moved_fd)
            if retained_identity != self.identity:
                raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
            if shutil.rmtree.avoids_symlink_attacks:
                shutil.rmtree(entry, dir_fd=quarantine_fd)
            else:
                _bounded_rmtree(quarantine_fd, entry)
            try:
                os.stat(entry, dir_fd=quarantine_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
            closing_fd = quarantine_fd
            quarantine_fd = None
            self._close_temporary_descriptor(closing_fd)
            os.rmdir(quarantine_name, dir_fd=workspace_fd)
            try:
                os.stat(quarantine_name, dir_fd=workspace_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed")
            descriptors_closed = True
            self._close_all()
            if self._local_descriptor_uncertainty:
                raise _LocalStagingCleanupError(
                    "cleanup: local staging cleanup was not confirmed"
                )
        except DaytonaExecutionError:
            if not descriptors_closed:
                descriptors_closed = True
                self._close_all()
            raise
        except Exception:
            if not descriptors_closed:
                descriptors_closed = True
                self._close_all()
            raise DaytonaExecutionError("cleanup: local staging cleanup was not confirmed") from None
        finally:
            if quarantine_fd is not None:
                try:
                    self._close_temporary_descriptor(quarantine_fd)
                except DaytonaExecutionError:
                    pass


def _collect_result(sandbox: _Sandbox, workspace: Path, request: JobRequest,
                    receipt: JobReceipt, timeout: int) -> tuple[_StagingOwner, CompletionReceipt, ResultBundle, Path, Path]:
    staging: Path | None = None
    staging_owner: _StagingOwner | None = None
    successful = False
    try:
        workspace = _safe_root(workspace, "workspace")
        staging = Path(tempfile.mkdtemp(prefix="daytona-result-", dir=workspace))
        created = staging.lstat()
        if (
            staging.parent != workspace
            or not staging.name.startswith("daytona-result-")
            or not stat.S_ISDIR(created.st_mode)
            or stat.S_ISLNK(created.st_mode)
        ):
            raise DaytonaExecutionError("download: staging directory is invalid")
        os.chmod(staging, 0o700)
        staging_owner = _StagingOwner(workspace, staging)
        completion_file = staging / "completion-receipt.json"
        _download(sandbox.fs, f"{OUTPUT_ROOT}/completion-receipt.json", completion_file,
                  timeout=timeout, maximum=MAX_RESULT_BYTES)
        completion = CompletionReceipt.from_mapping(load_canonical_json(completion_file))
        _validate_completion_envelope(request, receipt, completion)
        result_file = confined_path(staging, completion.result_path)
        _download(sandbox.fs, _remote_output(completion.result_path), result_file,
                  timeout=timeout, maximum=MAX_RESULT_BYTES,
                  expected_size=completion.result_size_bytes,
                  expected_sha256=completion.result_sha256)
        result = ResultBundle.from_mapping(load_canonical_json(result_file))
        _validate_result_envelopes(request, receipt, completion, result)
        files: dict[PurePosixPath, Path] = {}
        progress_rel = PurePosixPath(result.result["progressPath"])
        for entry in result.artifacts:
            maximum = (MAX_PROGRESS_TOTAL_BYTES if entry.relative_path == progress_rel else
                       MAX_SEGMENTATION_RESULT_BYTES if result.schema_version == 3 else MAX_PROCESSOR_RESULT_BYTES)
            destination = confined_path(staging, entry.relative_path)
            _download(sandbox.fs, _remote_output(entry.relative_path), destination,
                      timeout=timeout, maximum=maximum,
                      expected_size=entry.size_bytes, expected_sha256=entry.sha256)
            files[entry.relative_path] = destination
        validate_completion(staging, request, receipt, result, completion)
        successful = True
        return (staging_owner, completion, result,
                files[result.primary_artifact_path],
                files[progress_rel])
    except DaytonaExecutionError:
        raise
    except Exception:
        raise DaytonaExecutionError("download: result validation failed") from None
    finally:
        if not successful and staging_owner is not None:
            try:
                staging_owner.cleanup()
            except DaytonaExecutionError:
                raise _LocalStagingCleanupError(
                    "cleanup: lifecycle failed and local staging cleanup was not confirmed"
                ) from None


def _cleanup(client: _Client, sandbox: _Sandbox, policy: DaytonaPolicy,
             retry_wait: Callable[[], None]) -> bool:
    for attempt in range(policy.cleanup_attempts):
        try:
            client.delete(sandbox, timeout=policy.delete_timeout_seconds, wait=True)
            return True
        except DaytonaConfirmedAbsent:
            return True
        except Exception:
            if attempt + 1 < policy.cleanup_attempts:
                try:
                    retry_wait()
                except Exception:
                    LOGGER.warning("cleanup retry wait failed")
    return False


def _safe_diagnostics(value: object) -> DaytonaDiagnostics:
    """Represent untrusted provider output with one fixed allowlisted value."""
    del value
    return DaytonaDiagnostics("[REDACTED]")


def _session_id(job_id: str) -> str:
    return f"fa-{job_id}"


def _forward_progress_snapshot(
    process: _Process,
    session_id: str,
    command_id: str,
    job_id: str,
    last_sequence: int,
    last_progress: int | float,
    progress_callback: Callable[[ProgressEvent], None] | None,
    request_timeout: float,
) -> tuple[int, int | float]:
    if progress_callback is None:
        return last_sequence, last_progress
    try:
        stdout = process.get_session_command_logs(
            session_id, command_id, request_timeout=request_timeout
        ).stdout
        if type(stdout) is not str or len(stdout) > MAX_PROGRESS_TOTAL_BYTES:
            return last_sequence, last_progress
        snapshot = stdout.encode("utf-8")
        if len(snapshot) > MAX_PROGRESS_TOTAL_BYTES:
            return last_sequence, last_progress
    except Exception:
        return last_sequence, last_progress
    marked_lines = 0
    for line in snapshot.splitlines(keepends=True):
        if not line.endswith(b"\n") or not line.startswith(_LIVE_PROGRESS_PREFIX_BYTES):
            continue
        marked_lines += 1
        if marked_lines > MAX_PROGRESS_EVENTS:
            break
        payload = line[len(_LIVE_PROGRESS_PREFIX_BYTES):]
        if not payload or len(payload) > MAX_PROGRESS_LINE_BYTES:
            continue
        try:
            event = ProgressEvent.from_mapping(load_canonical_json(payload))
        except Exception:
            continue
        if (
            event.job_id != job_id
            or event.sequence <= last_sequence
            or event.progress < last_progress
        ):
            continue
        last_sequence, last_progress = event.sequence, event.progress
        try:
            progress_callback(event)
        except Exception:
            LOGGER.warning("progress callback failed")
    return last_sequence, last_progress


def _execute_session(
    process: _Process,
    request: JobRequest,
    policy: DaytonaPolicy,
    progress_callback: Callable[[ProgressEvent], None] | None,
    poll_wait: Callable[[], None],
    monotonic: Callable[[], float],
) -> None:
    session_id = _session_id(request.job_id)
    process.create_session(session_id, request_timeout=policy.create_timeout_seconds)
    try:
        deadline = monotonic() + policy.execution_timeout_seconds

        def remaining() -> float:
            budget = deadline - monotonic()
            if budget <= 0:
                raise DaytonaExecutionError("execute: worker timed out")
            return budget

        command = process.execute_session_command(
            session_id, SessionCommand(EXECUTION_COMMAND, True),
            timeout=policy.execution_timeout_seconds,
        )
        last_sequence = -1
        last_progress: int | float = -1
        while True:
            status = process.get_session_command(
                session_id, command.cmd_id, request_timeout=remaining()
            )
            budget = remaining()
            last_sequence, last_progress = _forward_progress_snapshot(
                process,
                session_id,
                command.cmd_id,
                request.job_id,
                last_sequence,
                last_progress,
                progress_callback,
                2 if status.exit_code is not None else min(2, budget),
            )
            if status.exit_code is not None:
                if type(status.exit_code) is not int or status.exit_code != 0:
                    raise DaytonaExecutionError("execute: worker returned nonzero")
                return
            remaining()
            poll_wait()
    finally:
        process.delete_session(session_id, request_timeout=policy.delete_timeout_seconds)


class _VerifiedUpload:
    """A bounded-read upload stream whose consumed bytes are identity checked."""
    def __init__(self, handle: Any):
        self._handle = handle; self._digest = hashlib.sha256(); self.size = 0

    def read(self, size: int = -1) -> bytes:
        requested = 64 * 1024 if size is None or size < 0 else min(size, 64 * 1024)
        chunk = self._handle.read(requested)
        if type(chunk) is not bytes:
            raise DaytonaExecutionError("upload: local stream is invalid")
        self._digest.update(chunk); self.size += len(chunk)
        return chunk

    @property
    def sha256(self) -> str:
        return self._digest.hexdigest()


@dataclass(frozen=True, slots=True)
class _PreparedUpload:
    relative_path: PurePosixPath
    expected_sha256: str
    expected_size: int
    handle: Any


@dataclass(slots=True)
class _RetainedUpload:
    descriptor: int
    handle: Any


_UNCERTAIN_UPLOAD_HANDLES: list[Any] = []


class _UploadOwner:
    """Close retained uploads once, before result ownership can transfer."""

    def __init__(self) -> None:
        self._retained: list[_RetainedUpload] = []
        self.poisoned_descriptors: set[int] = set()
        self.closed = False

    def retain(self, handle: Any) -> None:
        self._retained.append(_RetainedUpload(handle.fileno(), handle))

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        failed = False
        for retained in self._retained:
            try:
                retained.handle.close()
            except OSError as exc:
                # Keep an object whose close raised alive until process teardown;
                # its finalizer must not later touch a reused descriptor number.
                _UNCERTAIN_UPLOAD_HANDLES.append(retained.handle)
                if exc.errno != errno.EBADF:
                    self.poisoned_descriptors.add(retained.descriptor)
                    failed = True
            except Exception:
                _UNCERTAIN_UPLOAD_HANDLES.append(retained.handle)
                self.poisoned_descriptors.add(retained.descriptor)
                failed = True
        if failed:
            raise _LocalStagingCleanupError(
                "cleanup: local staging cleanup was not confirmed"
            )


def _prepare_uploads(
    root: Path,
    upload_paths: tuple[PurePosixPath, ...],
    identities: dict[PurePosixPath, tuple[str, int]],
    owner: _UploadOwner,
) -> tuple[_PreparedUpload, ...]:
    """Pin validated regular-file descriptions before any provider mutation.

    Path replacement is excluded by retaining the descriptions. A same-owner
    in-place writer is outside the sealed-file trust model; consumed-byte
    identity verification still detects such changes and fails closed.
    """
    prepared: list[_PreparedUpload] = []
    try:
        for relative in upload_paths:
            descriptor = _open_preflight_regular_file(confined_path(root, relative))
            try:
                handle = os.fdopen(descriptor, "rb")
            except Exception:
                os.close(descriptor)
                raise
            owner.retain(handle)
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise DaytonaExecutionError("preflight: upload source is not regular")
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = handle.read(64 * 1024)
                if type(chunk) is not bytes:
                    raise DaytonaExecutionError("preflight: upload source stream is invalid")
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            expected_sha256, expected_size = identities[relative]
            if (digest.hexdigest(), size) != (expected_sha256, expected_size):
                raise DaytonaExecutionError("preflight: upload source identity mismatch")
            handle.seek(0)
            prepared.append(
                _PreparedUpload(relative, expected_sha256, expected_size, handle)
            )
        return tuple(prepared)
    except DaytonaExecutionError:
        raise
    except Exception:
        raise DaytonaExecutionError("preflight: upload sources cannot be retained safely") from None


def execute_daytona_job(execution: DaytonaExecutionRequest, *,
                        client_factory: ClientFactory = _production_client_factory,
                        retry_wait: Callable[[], None] = lambda: None,
                        progress_callback: Callable[[ProgressEvent], None] | None = None,
                        poll_wait: Callable[[], None] = lambda: time.sleep(2)) -> DaytonaExecutionResult:
    """Validate, execute once, collect one generation, then confirm deletion."""
    try:
        root, workspace, request, receipt, upload_paths, upload_identities = _preflight(execution)
    except DaytonaExecutionError:
        raise
    except Exception:
        raise DaytonaExecutionError("preflight: local validation failed") from None
    with ExitStack() as upload_cleanup:
        upload_owner = _UploadOwner()
        upload_cleanup.callback(upload_owner.close)
        prepared_uploads = _prepare_uploads(
            root, upload_paths, upload_identities, upload_owner
        )
        try:
            client = client_factory(execution.api_key, execution.policy.target)
        except Exception:
            raise DaytonaExecutionError("client: construction failed") from None
        sandbox: _Sandbox | None = None; sandbox_id = "unavailable"
        pending: DaytonaExecutionError | None = None
        outcome: DaytonaExecutionResult | None = None
        unreturned_staging: _StagingOwner | None = None
        upload_cleanup_failed = False
        stage = "create"
        try:
            sandbox = client.create(_sandbox_spec(execution.policy), timeout=execution.policy.create_timeout_seconds)
            sandbox_id = _sandbox_identifier(sandbox); stage = "upload"
            for prepared in prepared_uploads:
                if not stat.S_ISREG(os.fstat(prepared.handle.fileno()).st_mode):
                    raise DaytonaExecutionError("upload: retained source is unsafe")
                verified = _VerifiedUpload(prepared.handle)
                sandbox.fs.upload_file_stream(
                    verified,
                    f"{INPUT_ROOT}/{prepared.relative_path.as_posix()}",
                    timeout=execution.policy.transfer_timeout_seconds,
                )
                if (verified.sha256, verified.size) != (
                    prepared.expected_sha256,
                    prepared.expected_size,
                ):
                    raise DaytonaExecutionError("upload: retained source identity changed")
            stage = "execute"
            _execute_session(
                sandbox.process,
                request,
                execution.policy,
                progress_callback,
                poll_wait,
                time.monotonic,
            )
            diagnostics = _safe_diagnostics(None)
            stage = "download"
            unreturned_staging, completion, result, processor, progress = _collect_result(
                sandbox, workspace, request, receipt, execution.policy.transfer_timeout_seconds)
            outcome = DaytonaExecutionResult(sandbox_id, completion, result, unreturned_staging.staging,
                                             processor, progress, diagnostics)
        except _UnreturnedSandboxCleanupError as exc:
            sandbox = exc.sandbox
            try:
                sandbox_id = _sandbox_identifier(sandbox)
            except DaytonaExecutionError:
                sandbox_id = "unavailable"
            pending = DaytonaExecutionError(
                "create: sandbox cleanup was not confirmed"
            )
        except DaytonaExecutionError as exc:
            pending = exc
        except Exception:
            pending = DaytonaExecutionError(f"{stage}: provider operation failed")
        finally:
            try:
                upload_owner.close()
            except _LocalStagingCleanupError:
                upload_cleanup_failed = True
                if unreturned_staging is not None:
                    try:
                        unreturned_staging._halt_after_external_poison(
                            upload_owner.poisoned_descriptors
                        )
                    except _LocalStagingCleanupError:
                        pass
            if sandbox is not None and not _cleanup(client, sandbox, execution.policy, retry_wait):
                local_cleanup_failed = upload_cleanup_failed or isinstance(
                    pending, _LocalStagingCleanupError
                )
                if unreturned_staging is not None and not upload_cleanup_failed:
                    try:
                        unreturned_staging.cleanup()
                    except DaytonaExecutionError:
                        local_cleanup_failed = True
                if local_cleanup_failed:
                    raise DaytonaExecutionError(
                        "cleanup: sandbox and local staging cleanup were not confirmed"
                    ) from None
                reference = _sandbox_error_reference(sandbox_id)
                raise DaytonaExecutionError(
                    f"cleanup: sandbox reference {reference} destruction was not confirmed"
                ) from None
        if pending is not None:
            if upload_cleanup_failed:
                raise DaytonaExecutionError(
                    "cleanup: lifecycle failed and local staging cleanup was not confirmed"
                ) from None
            if unreturned_staging is not None:
                try:
                    unreturned_staging.cleanup()
                except DaytonaExecutionError:
                    raise DaytonaExecutionError(
                        "cleanup: lifecycle failed and local staging cleanup was not confirmed"
                    ) from None
            raise pending
        if upload_cleanup_failed:
            raise _LocalStagingCleanupError(
                "cleanup: local staging cleanup was not confirmed"
            )
        if outcome is None:
            if unreturned_staging is not None:
                try:
                    unreturned_staging.cleanup()
                except DaytonaExecutionError:
                    raise DaytonaExecutionError(
                        "cleanup: lifecycle failed and local staging cleanup was not confirmed"
                    ) from None
            raise DaytonaExecutionError("execute: no validated result")
        unreturned_staging.release()
        return outcome
