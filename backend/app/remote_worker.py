"""Application worker for validated Daytona football jobs."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import time
from typing import BinaryIO, Callable, Iterator

from .daytona import (
    ClientFactory as DaytonaClientFactory,
    DaytonaExecutionRequest,
    DaytonaExecutionResult,
    _StagingOwner,
    _open_preflight_regular_file,
    execute_daytona_job,
)
from .gpu_worker import _processor_json_line, _validate_processor_result
from .processor import persist_remote_video_result, persist_remote_video_result_stream
from .release_manifest import load_release_manifest
from .remote_contracts import (
    FileEntry,
    JobReceipt,
    JobRequest,
    MAX_FILE_BYTES,
    MAX_PROCESSOR_METADATA_LINE_BYTES,
    MAX_PROCESSOR_RESULT_BYTES,
    MAX_PROCESSOR_ROW_LINE_BYTES,
    MAX_PROGRESS_TOTAL_BYTES,
    READ_CHUNK_BYTES,
    ProgressEvent,
    StreamIdentity,
    canonical_json_bytes,
    load_canonical_json,
    validate_progress_jsonl,
)
from .settings import ProcessingSettings
from .storage import Storage
from .workbench.jobs import maintain_job_lease
from backend.release.preflight import build_validated_tar_context, validate_release_preflight


ExecutionRequestBuilder = Callable[[Storage, str, ProcessingSettings], DaytonaExecutionRequest]
REPO_ROOT = Path(__file__).resolve().parents[2]
# Legacy v1 imports materialize the complete JSON object.
MAX_PROCESSOR_IMPORT_BYTES = 64 * 1024 * 1024


def _copy_regular_file(
    source: Path,
    destination: Path | None = None,
    *,
    maximum_bytes: int = MAX_FILE_BYTES,
) -> StreamIdentity:
    source_fd = destination_fd = -1
    destination_created = False
    try:
        source_fd = _open_preflight_regular_file(source)
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum_bytes:
            raise ValueError
        if destination is not None:
            destination_fd = os.open(
                destination,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            destination_created = True
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(source_fd, READ_CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > maximum_bytes:
                raise ValueError
            digest.update(chunk)
            if destination_fd >= 0:
                view = memoryview(chunk)
                while view:
                    view = view[os.write(destination_fd, view):]
        after = os.fstat(source_fd)
        named = os.stat(source, follow_symlinks=False)
        if (
            not stat.S_ISREG(named.st_mode)
            or (after.st_dev, after.st_ino, after.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
            or (named.st_dev, named.st_ino, named.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
            or size != before.st_size
        ):
            raise ValueError
        if destination_fd >= 0:
            os.fsync(destination_fd)
        return StreamIdentity(size, digest.hexdigest())
    except Exception:
        if destination is not None and destination_created:
            destination.unlink(missing_ok=True)
        raise RuntimeError("Daytona bundle file is invalid") from None
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if source_fd >= 0:
            os.close(source_fd)


def _entry(role: str, bundle_root: Path, relative: PurePosixPath) -> FileEntry:
    identity = _copy_regular_file(bundle_root / relative)
    return FileEntry(role, relative, identity.size_bytes, identity.sha256)


def _build_execution_request(
    storage: Storage,
    job_id: str,
    settings: ProcessingSettings,
) -> DaytonaExecutionRequest:
    if (
        settings.processing_backend != "daytona"
        or settings.daytona_api_key is None
        or settings.daytona_policy is None
    ):
        raise RuntimeError("Daytona settings are unavailable")
    workspace = storage.storage_root / ".daytona"
    workspace.mkdir(parents=True, exist_ok=True)
    bundle_root = Path(tempfile.mkdtemp(prefix="daytona-bundle-", dir=workspace))
    try:
        manifest_path = REPO_ROOT / "backend/release/v7.3.json"
        evidence_path = REPO_ROOT / "backend/release/verification/v7.3-pre-cloud.json"
        candidate_manifest = load_release_manifest(manifest_path)
        candidate_manifest_sha256 = _copy_regular_file(manifest_path).sha256
        image_tag = (
            f"v7.3-{candidate_manifest.source_commit}-"
            f"{candidate_manifest_sha256[:12]}"
        )
        preflight = validate_release_preflight(
            repo_root=REPO_ROOT,
            manifest_path=manifest_path,
            evidence_path=evidence_path,
            mode="build-only",
            image_tag=image_tag,
        )
        job = storage.get_job(job_id)
        match = storage.get_match(job.matchId)
        if match.inputMode != "video":
            raise RuntimeError("Daytona requires a video input")
        input_source = storage.get_match_input_path(match.id)

        source_relative = PurePosixPath("source/source.tar")
        source_path = bundle_root / source_relative
        source_path.parent.mkdir(parents=True)
        build_validated_tar_context(
            repo_root=REPO_ROOT,
            receipt=preflight.to_mapping(),
            output_path=source_path,
        )
        manifest_relative = PurePosixPath("release/manifest.json")
        evidence_relative = PurePosixPath("release/evidence.json")
        (bundle_root / manifest_relative).parent.mkdir(parents=True, exist_ok=True)
        manifest_identity = _copy_regular_file(
            preflight.manifest_path, bundle_root / manifest_relative
        )
        evidence_identity = _copy_regular_file(
            preflight.evidence_path, bundle_root / evidence_relative
        )

        runtime_entries: list[FileEntry] = []
        for _artifact_id, local_path, container_path in preflight.artifacts:
            relative = PurePosixPath(container_path.removeprefix("/app/"))
            destination = bundle_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            identity = _copy_regular_file(local_path, destination)
            runtime_entries.append(
                FileEntry(
                    "runtime_artifact", relative, identity.size_bytes, identity.sha256
                )
            )

        input_suffix = input_source.suffix if input_source.suffix.isascii() else ""
        input_relative = PurePosixPath(f"inputs/video{input_suffix}")
        (bundle_root / input_relative).parent.mkdir(parents=True, exist_ok=True)
        input_identity = _copy_regular_file(input_source, bundle_root / input_relative)
        receipt_relative = PurePosixPath("sealed/job-receipt.json")
        manifest = load_release_manifest(
            preflight.manifest_path,
            expected_source_commit=preflight.source_commit,
        )
        request = JobRequest(
            1,
            job.id,
            match.id,
            receipt_relative,
            input_relative,
            match.config.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        request_path = bundle_root / "job-request.json"
        request_path.write_bytes(canonical_json_bytes(request.to_mapping()))
        entries = (
            _entry("source_archive", bundle_root, source_relative),
            FileEntry(
                "manifest",
                manifest_relative,
                manifest_identity.size_bytes,
                manifest_identity.sha256,
            ),
            FileEntry(
                "evidence",
                evidence_relative,
                evidence_identity.size_bytes,
                evidence_identity.sha256,
            ),
            *runtime_entries,
            FileEntry(
                "input_video",
                input_relative,
                input_identity.size_bytes,
                input_identity.sha256,
            ),
            _entry("job_request", bundle_root, PurePosixPath("job-request.json")),
        )
        receipt = JobReceipt(
            1,
            preflight.source_commit,
            preflight.manifest_sha256,
            preflight.evidence_sha256,
            entries[-1].sha256,
            manifest.runtime_options,
            entries,
        )
        receipt_path = bundle_root / receipt_relative
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(canonical_json_bytes(receipt.to_mapping()))
        return DaytonaExecutionRequest(
            api_key=settings.daytona_api_key,
            policy=settings.daytona_policy,
            bundle_root=bundle_root,
            workspace=workspace,
            preflight=preflight,
        )
    except Exception:
        try:
            _cleanup_owned_directory(bundle_root, workspace, "daytona-bundle-")
        except Exception:
            raise RuntimeError(
                "Daytona staging cleanup could not be confirmed"
            ) from None
        raise RuntimeError("Daytona release bundle is unavailable") from None


def _read_result_artifact(
    result: DaytonaExecutionResult,
    path: Path,
    *,
    job_id: str,
    match_id: str,
    maximum_bytes: int,
    declared_path_key: str,
) -> bytes:
    descriptor = -1
    try:
        if (
            type(result) is not DaytonaExecutionResult
            or result.result.job_id != job_id
            or result.result.match_id != match_id
            or result.completion.job_id != job_id
            or result.completion.match_id != match_id
        ):
            raise ValueError
        relative = PurePosixPath(path.relative_to(result.staging_root).as_posix())
        if relative != PurePosixPath(result.result.result[declared_path_key]):
            raise ValueError
        entry = next(
            item for item in result.result.artifacts if item.relative_path == relative
        )
        if entry.size_bytes > maximum_bytes:
            raise ValueError
        descriptor = _open_preflight_regular_file(path)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size != entry.size_bytes:
            raise ValueError
        digest = hashlib.sha256()
        payload = bytearray()
        while True:
            chunk = os.read(
                descriptor,
                min(READ_CHUNK_BYTES, maximum_bytes + 1 - len(payload)),
            )
            if not chunk:
                break
            payload.extend(chunk)
            digest.update(chunk)
            if len(payload) > maximum_bytes:
                raise ValueError
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino, after.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
            or len(payload) != entry.size_bytes
            or digest.hexdigest() != entry.sha256
        ):
            raise ValueError
        return bytes(payload)
    except Exception:
        raise RuntimeError("Daytona result artifact is invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _load_processor_result(
    result: DaytonaExecutionResult,
    *,
    job_id: str,
    match_id: str,
) -> object:
    try:
        encoded = _read_result_artifact(
            result,
            result.processor_path,
            job_id=job_id,
            match_id=match_id,
            maximum_bytes=MAX_PROCESSOR_IMPORT_BYTES,
            declared_path_key="processorResultPath",
        )

        payload = json.loads(encoded, object_pairs_hook=_reject_duplicate_keys)
        _validate_processor_result(payload)
        return payload
    except Exception:
        raise RuntimeError("Daytona processor result is invalid") from None


def _input_video_identity(execution: DaytonaExecutionRequest, result: DaytonaExecutionResult) -> dict[str, object]:
    try:
        receipt = JobReceipt.from_mapping(
            load_canonical_json(execution.bundle_root / "sealed" / "job-receipt.json")
        )
        digest = hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest()
        if (
            digest != result.result.receipt_sha256
            or receipt.source_commit != result.result.source_commit
            or receipt.manifest_sha256 != result.result.manifest_sha256
        ):
            raise ValueError
        video = next(item for item in receipt.files if item.role == "input_video")
        if video.size_bytes <= 0:
            raise ValueError
        return {
            "schemaVersion": 1,
            "jobId": result.result.job_id,
            "matchId": result.result.match_id,
            "sourceCommit": receipt.source_commit,
            "manifestSha256": receipt.manifest_sha256,
            "receiptSha256": digest,
            "inputVideoSha256": video.sha256,
            "inputVideoSizeBytes": video.size_bytes,
        }
    except Exception:
        raise RuntimeError("Daytona input video identity is invalid") from None


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


class _OneShotRows(Iterator[dict[str, object]]):
    def __init__(self, rows: Iterator[dict[str, object]]) -> None:
        self.rows = rows
        self.exhausted = False
        self.closed = False

    def __iter__(self) -> Iterator[dict[str, object]]:
        if self.exhausted or self.closed:
            raise RuntimeError("Daytona processor result rows already consumed")
        return self

    def __next__(self) -> dict[str, object]:
        if self.closed:
            raise RuntimeError("Daytona processor result rows already consumed")
        try:
            return next(self.rows)
        except StopIteration:
            self.exhausted = True
            raise
        except Exception:
            self.closed = True
            raise RuntimeError("Daytona processor result is invalid") from None

    def close(self) -> None:
        self.closed = True
        close = getattr(self.rows, "close", None)
        if close is not None:
            close()


@dataclass(slots=True)
class ProcessorResultStream:
    """One-shot rows; successful context exit requires validated EOF."""

    metadata: dict[str, object]
    row_count: int
    rows: Iterator[dict[str, object]]
    _handle: BinaryIO | None = field(default=None, repr=False)
    _rows: _OneShotRows = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rows = _OneShotRows(self.rows)
        self.rows = self._rows

    def __enter__(self) -> "ProcessorResultStream":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            try:
                self._rows.close()
            finally:
                if self._handle is not None:
                    self._handle.close()
            if exc_type is None and not self._rows.exhausted:
                raise ValueError
        except Exception:
            raise RuntimeError("Daytona processor result is invalid") from None


def _canonical_processor_line(handle: BinaryIO, maximum: int) -> tuple[bytes, dict[str, object]]:
    raw = handle.readline(maximum + 1)
    if not raw.endswith(b"\n") or len(raw) > maximum:
        raise ValueError
    value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    if type(value) is not dict or _processor_json_line(value, maximum=maximum) != raw:
        raise ValueError
    return raw, value


def _load_processor_result_source(
    result: DaytonaExecutionResult,
    *,
    job_id: str,
    match_id: str,
) -> object:
    descriptor = -1
    handle = None
    try:
        if type(result) is not DaytonaExecutionResult:
            raise ValueError
        if result.result.schema_version == 1:
            return _load_processor_result(result, job_id=job_id, match_id=match_id)
        if (
            result.result.job_id != job_id
            or result.result.match_id != match_id
            or result.completion.job_id != job_id
            or result.completion.match_id != match_id
        ):
            raise ValueError
        path = result.processor_path
        relative = PurePosixPath(path.relative_to(result.staging_root).as_posix())
        if (
            relative != PurePosixPath(result.result.result["processorResultPath"])
            or relative.parent != result.completion.result_path.parent
        ):
            raise ValueError
        entry = next(item for item in result.result.artifacts if item.relative_path == relative)
        if entry.size_bytes > MAX_PROCESSOR_RESULT_BYTES:
            raise ValueError
        descriptor = _open_preflight_regular_file(path)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size != entry.size_bytes:
            raise ValueError
        handle = os.fdopen(descriptor, "rb")
        descriptor = -1  # The handle now owns this descriptor.
        raw, header = _canonical_processor_line(handle, MAX_PROCESSOR_METADATA_LINE_BYTES)
        row_count = result.result.processor_row_count
        if (
            set(header) != {"schemaVersion", "rowCount", "metadata"}
            or type(header["schemaVersion"]) is not int
            or header["schemaVersion"] != 1
            or type(header["rowCount"]) is not int
            or type(row_count) is not int
            or header["rowCount"] != row_count
            or type(header["metadata"]) is not dict
            or "rows" in header["metadata"]
        ):
            raise ValueError
        _validate_processor_result(header["metadata"])
        digest = hashlib.sha256(raw)
        size = len(raw)

        def rows() -> Iterator[dict[str, object]]:
            nonlocal size
            previous_frame = -1
            for _ in range(row_count):
                raw, row = _canonical_processor_line(handle, MAX_PROCESSOR_ROW_LINE_BYTES)
                _validate_processor_result(row)
                size += len(raw)
                digest.update(raw)
                frame = row.get("Frame_ID")
                if (
                    size > entry.size_bytes
                    or type(frame) is not int
                    or frame < previous_frame
                    or frame < 0
                ):
                    raise ValueError
                previous_frame = frame
                yield row
            if handle.read(1):
                raise ValueError
            after = os.fstat(handle.fileno())
            named = os.stat(path, follow_symlinks=False)
            verify_fd = _open_preflight_regular_file(path)
            try:
                on_disk = hashlib.sha256()
                while True:
                    chunk = os.read(verify_fd, READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    on_disk.update(chunk)
                on_disk_stat = os.fstat(verify_fd)
            finally:
                os.close(verify_fd)
            if (
                not stat.S_ISREG(named.st_mode)
                or (after.st_dev, after.st_ino, after.st_size)
                != (before.st_dev, before.st_ino, before.st_size)
                or (named.st_dev, named.st_ino, named.st_size)
                != (before.st_dev, before.st_ino, before.st_size)
                or (on_disk_stat.st_dev, on_disk_stat.st_ino, on_disk_stat.st_size)
                != (before.st_dev, before.st_ino, before.st_size)
                or (after.st_mtime_ns, after.st_ctime_ns)
                != (before.st_mtime_ns, before.st_ctime_ns)
                or size != entry.size_bytes
                or digest.hexdigest() != entry.sha256
                or on_disk.hexdigest() != entry.sha256
            ):
                raise ValueError

        return ProcessorResultStream(header["metadata"], row_count, rows(), handle)
    except Exception:
        try:
            if handle is not None:
                handle.close()
        finally:
            raise RuntimeError("Daytona processor result is invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _load_progress(
    result: DaytonaExecutionResult,
    *,
    job_id: str,
    match_id: str,
) -> dict[str, object]:
    try:
        encoded = _read_result_artifact(
            result,
            result.progress_path,
            job_id=job_id,
            match_id=match_id,
            maximum_bytes=MAX_PROGRESS_TOTAL_BYTES,
            declared_path_key="progressPath",
        )
        events = validate_progress_jsonl(BytesIO(encoded), expected_job_id=job_id)
    except Exception:
        raise RuntimeError("Daytona progress result is invalid") from None
    return events[-1].to_mapping() if events else {}


def _owned_directory_owner(
    root_path: Path,
    workspace: Path,
    prefix: str,
) -> _StagingOwner:
    try:
        before = root_path.lstat()
        owner = workspace.resolve(strict=True)
        if (
            not stat.S_ISDIR(before.st_mode)
            or root_path.is_symlink()
            or root_path.parent.resolve(strict=True) != owner
            or not root_path.name.startswith(prefix)
        ):
            raise RuntimeError
        owner_handle = _StagingOwner(owner, root_path)
        if owner_handle.identity != (before.st_dev, before.st_ino):
            owner_handle.release()
            raise RuntimeError
        return owner_handle
    except Exception:
        raise RuntimeError("Daytona staging cleanup could not be confirmed") from None


def _confirm_owned_directory(owner: _StagingOwner) -> None:
    try:
        opened = os.stat(
            owner.staging.name,
            dir_fd=owner.workspace_fd,
            follow_symlinks=False,
        )
        if (opened.st_dev, opened.st_ino) != owner.identity:
            raise RuntimeError
    except Exception:
        raise RuntimeError("Daytona staging cleanup could not be confirmed") from None


def _cleanup_owned_directory(root_path: Path, workspace: Path, prefix: str) -> None:
    owner = _owned_directory_owner(root_path, workspace, prefix)
    try:
        owner.cleanup()
    except Exception:
        raise RuntimeError("Daytona staging cleanup could not be confirmed") from None


def _failure_message(_: BaseException) -> str:
    return "Daytona processing failed"


def _persist_remote_progress(
    storage: Storage,
    job_id: str,
    match_id: str,
) -> Callable[[ProgressEvent], None]:
    last = {"sequence": -1, "progress": 0.0}

    def callback(event: ProgressEvent) -> None:
        mapped = min(0.85, 0.10 + 0.75 * float(event.progress) / 100.0)
        if event.sequence <= last["sequence"] or mapped < last["progress"]:
            return
        storage.save_analysis_artifact(match_id, "remote_worker_progress", event.to_mapping())
        storage.update_job(
            job_id,
            status="processing",
            progress=mapped,
            message=event.message,
        )
        last.update(sequence=event.sequence, progress=mapped)

    return callback


def _run_remote_job(
    storage: Storage,
    job_id: str,
    settings: ProcessingSettings | None = None,
    *,
    client_factory: DaytonaClientFactory | None = None,
) -> None:
    result = None
    execution = None
    staging_owner = None
    bundle_owner = None
    staging_cleaned = False
    bundle_cleaned = False
    cancelled = False
    match_id = storage.get_job(job_id).matchId
    try:
        storage.save_analysis_artifact(match_id, "remote_worker_progress", {})
        storage.save_analysis_artifact(
            match_id,
            "remote_transport_debug",
            {
                "requestedTransport": "daytona",
                "resolvedTransport": "daytona",
                "initialRunId": None,
                "runtimeOutcome": "preparing",
                "workerProgress": {},
            },
        )
        resolved_settings = settings or ProcessingSettings.from_env()
        if resolved_settings.processing_backend != "daytona":
            raise RuntimeError("Daytona processing is not selected")
        storage.update_job(
            job_id,
            status="processing",
            progress=0.05,
            message="Preparing Daytona job",
        )
        execution = _build_execution_request(storage, job_id, resolved_settings)
        if type(execution) is not DaytonaExecutionRequest:
            raise RuntimeError("Daytona execution ownership is invalid")
        bundle_owner = _owned_directory_owner(
            execution.bundle_root,
            execution.workspace,
            "daytona-bundle-",
        )
        kwargs = {"progress_callback": _persist_remote_progress(storage, job_id, match_id)}

        def poll_wait() -> None:
            if storage.job_ledger.cancel_requested(job_id):
                raise RuntimeError("job cancellation requested")
            time.sleep(2)

        kwargs["poll_wait"] = poll_wait
        if client_factory is not None:
            kwargs["client_factory"] = client_factory
        result = execute_daytona_job(execution, **kwargs)
        if type(result) is not DaytonaExecutionResult:
            raise RuntimeError("Daytona result ownership is invalid")
        staging_owner = _owned_directory_owner(
            result.staging_root,
            execution.workspace,
            "daytona-result-",
        )
        _confirm_owned_directory(bundle_owner)
        _confirm_owned_directory(staging_owner)
        if (
            result.result.job_id != job_id
            or result.result.match_id != match_id
            or result.completion.job_id != job_id
            or result.completion.match_id != match_id
        ):
            raise RuntimeError("Daytona result ownership is invalid")
        input_identity = _input_video_identity(execution, result)
        storage.update_job(
            job_id,
            status="processing",
            progress=0.9,
            message="Importing validated remote result",
            remote_run_id=result.sandbox_id,
        )
        progress = _load_progress(result, job_id=job_id, match_id=match_id)
        storage.save_analysis_artifact(match_id, "remote_worker_progress", progress)
        with storage.remote_cost_unsettled(), storage.remote_result_import(match_id):
            payload = _load_processor_result_source(result, job_id=job_id, match_id=match_id)
            if isinstance(payload, ProcessorResultStream):
                with payload:
                    persist_remote_video_result_stream(storage, job_id, payload)
            else:
                persist_remote_video_result(storage, job_id, payload)
            storage.save_analysis_artifact(match_id, "input_video_identity", input_identity)
            staging_owner.cleanup()
            staging_cleaned = True
            bundle_owner.cleanup()
            bundle_cleaned = True
            storage.update_job(
                job_id,
                status="completed",
                progress=1.0,
                message="Processing complete",
                remote_run_id=result.sandbox_id,
                ledger_outcome_unknown=True,
            )
        try:
            storage.save_analysis_artifact(
                match_id,
                "remote_transport_debug",
                {
                    "requestedTransport": "daytona",
                    "resolvedTransport": "daytona",
                    "initialRunId": result.sandbox_id,
                    "runtimeOutcome": "completed",
                    "workerProgress": progress,
                },
            )
        except Exception:
            pass
    except Exception as exc:
        if storage.job_ledger.cancel_requested(job_id):
            cancelled = True
        else:
            message = _failure_message(exc)
            run_id = getattr(result, "sandbox_id", None)
            storage.update_job(
                job_id,
                status="failed",
                progress=1.0,
                message=message,
                error=message,
                remote_run_id=run_id if isinstance(run_id, str) else None,
                ledger_outcome_unknown=True,
            )
            storage.update_match_status(match_id, status="failed")
            try:
                storage.save_analysis_artifact(
                    match_id,
                    "remote_transport_debug",
                    {
                        "requestedTransport": "daytona",
                        "resolvedTransport": "daytona",
                        "initialRunId": run_id if isinstance(run_id, str) else None,
                        "runtimeOutcome": "failed",
                        "workerProgress": {},
                        "finalErrorMessage": message,
                    },
                )
            except Exception:
                pass
    finally:
        cleanup_failed = False
        if staging_owner is not None and not staging_cleaned:
            try:
                staging_owner.cleanup()
            except Exception:
                cleanup_failed = True
        if bundle_owner is not None and not bundle_cleaned:
            try:
                bundle_owner.cleanup()
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            message = "Daytona staging cleanup could not be confirmed"
            if not cancelled:
                storage.update_job(
                    job_id,
                    status="failed",
                    progress=1.0,
                    message=message,
                    error=message,
                    remote_run_id=getattr(result, "sandbox_id", None),
                    ledger_outcome_unknown=True,
                )
                storage.update_match_status(match_id, status="failed")
        if cancelled:
            storage.update_job(
                job_id,
                status="cancelled",
                progress=1.0,
                message="Cancelled",
                ledger_outcome_unknown=True,
            )
            storage.job_ledger.confirm_termination(
                job_id,
                owner_id=f"job:{job_id}",
                cost_known=False,
            )
            storage.job_ledger.confirm_cleanup(
                job_id,
                owner_id=f"job:{job_id}",
                ok=not cleanup_failed,
            )


def run_remote_job(
    storage_root: Path,
    job_id: str,
    settings: ProcessingSettings | None = None,
    *,
    client_factory: DaytonaClientFactory | None = None,
) -> None:
    storage = Storage(storage_root)
    try:
        with maintain_job_lease(
            storage.job_ledger,
            job_id,
            owner_id=f"job:{job_id}",
        ):
            _run_remote_job(
                storage,
                job_id,
                settings=settings,
                client_factory=client_factory,
            )
    finally:
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one validated Daytona job.")
    parser.add_argument("--storage-root", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    run_remote_job(Path(args.storage_root), args.job_id)


if __name__ == "__main__":
    main()
