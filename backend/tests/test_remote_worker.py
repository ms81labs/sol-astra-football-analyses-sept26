from __future__ import annotations

import json
import hashlib
import os
import tracemalloc
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import daytona as daytona_adapter
from backend.app import gpu_worker
from backend.app import remote_worker
from backend.app import storage as storage_module
from backend.app.remote_contracts import (
    CompletionReceipt,
    FileEntry,
    JobReceipt,
    ProgressEvent,
    ResultBundle,
    canonical_json_bytes,
)
from backend.app.schemas import MatchConfig
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage
from backend.release.daytona_policy import load_daytona_policy
from backend.release.preflight import PreflightResult


def _job(storage: Storage):
    input_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="remote match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=input_path,
        config=MatchConfig(autoHomography=True),
    )
    return match, storage.create_job(match.id)


def _settings() -> ProcessingSettings:
    return ProcessingSettings(
        processing_backend="daytona",
        daytona_api_key="test-only-key",
        daytona_policy=load_daytona_policy(),
    )


def _execution(workspace: Path) -> daytona_adapter.DaytonaExecutionRequest:
    bundle = workspace / "daytona-bundle-owned"
    bundle.mkdir(parents=True)
    receipt_path = bundle / "sealed" / "job-receipt.json"
    receipt_path.parent.mkdir()
    receipt_path.write_bytes(canonical_json_bytes(_fixture_receipt().to_mapping()))
    digest = "b" * 64
    preflight = PreflightResult(
        source_commit="b" * 40,
        manifest_sha256=digest,
        manifest_path=workspace / "manifest.json",
        evidence_path=workspace / "evidence.json",
        evidence_phase="pre_cloud",
        evidence_sha256=digest,
        artifacts=(),
        artifact_metadata=(),
    )
    return daytona_adapter.DaytonaExecutionRequest(
        api_key="test-only-key",
        policy=load_daytona_policy(),
        bundle_root=bundle,
        workspace=workspace,
        preflight=preflight,
    )


def _fixture_receipt() -> JobReceipt:
    digest = "b" * 64
    files = (
        FileEntry("source_archive", "release/source.tar", 1, "a" * 64),
        FileEntry("manifest", "release/manifest.json", 1, digest),
        FileEntry("evidence", "release/evidence.json", 1, digest),
        FileEntry("input_video", "inputs/video.mp4", 5, "0cab1c9617404faf2b24e221e189ca5945813e14d3f766345b09ca13bbe28ffc"),
        FileEntry("job_request", "job-request.json", 1, digest),
    )
    return JobReceipt(1, "b" * 40, digest, digest, digest, {}, files)


def _execution_result(
    staging: Path,
    *,
    job_id: str,
    match_id: str,
    sandbox_id: str,
    processor_payload: bytes = b'{"rows":[]}\n',
    progress_payload: bytes = b"",
    processor_row_count: int | None = None,
) -> daytona_adapter.DaytonaExecutionResult:
    generation = "0123456789abcdef0123456789abcdef"
    generation_root = staging / "result-bundle.json.generations" / generation
    generation_root.mkdir(parents=True)
    processor_path = generation_root / (
        "result.processor-result.json" if processor_row_count is None
        else "result.processor-result.jsonl"
    )
    progress_path = generation_root / "result.progress.jsonl"
    processor_path.write_bytes(processor_payload)
    progress_path.write_bytes(progress_payload)
    processor_relative = processor_path.relative_to(staging).as_posix()
    progress_relative = progress_path.relative_to(staging).as_posix()
    result = ResultBundle(
        1 if processor_row_count is None else 2,
        job_id,
        match_id,
        "b" * 40,
        "b" * 64,
        hashlib.sha256(canonical_json_bytes(_fixture_receipt().to_mapping())).hexdigest(),
        {},
        {
            "processorResultPath": processor_relative,
            "progressPath": progress_relative,
            "progressEventCount": 0 if not progress_payload else 1,
            **({} if processor_row_count is None else {
                "processorResultFormat": "jsonl-v1",
                "processorRowCount": processor_row_count,
            }),
        },
        (
            FileEntry(
                "result_artifact",
                processor_relative,
                len(processor_payload),
                hashlib.sha256(processor_payload).hexdigest(),
            ),
            FileEntry(
                "result_artifact",
                progress_relative,
                len(progress_payload),
                hashlib.sha256(progress_payload).hexdigest(),
            ),
        ),
    )
    result_bytes = canonical_json_bytes(result.to_mapping())
    completion = CompletionReceipt(
        1,
        job_id,
        match_id,
        f"result-bundle.json.generations/{generation}/result.json",
        len(result_bytes),
        hashlib.sha256(result_bytes).hexdigest(),
        "b" * 40,
        "b" * 64,
        datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    return daytona_adapter.DaytonaExecutionResult(
        sandbox_id,
        completion,
        result,
        staging,
        processor_path,
        progress_path,
        daytona_adapter.DaytonaDiagnostics("[REDACTED]"),
    )


def test_remote_progress_is_persisted_before_adapter_returns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    event = ProgressEvent(
        1,
        job.id,
        1,
        50,
        "tracking",
        "running",
        datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-progress",
        progress_payload=canonical_json_bytes(event.to_mapping()),
    )
    observed = []

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: _execution(workspace))

    def execute(_request, *, progress_callback, **_kwargs):
        progress_callback(event)
        observed.append(storage.get_job(job.id))
        return result

    monkeypatch.setattr(remote_worker, "execute_daytona_job", execute)
    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert observed[0].status == "processing"
    assert observed[0].progress == pytest.approx(0.475)
    assert storage.load_analysis_artifact(match.id, "remote_worker_progress")["sequence"] == event.sequence


def test_run_remote_job_persists_sandbox_imports_processor_and_writes_neutral_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    execution = _execution(workspace)
    progress_payload = canonical_json_bytes(
        ProgressEvent(
            1,
            job.id,
            1,
            98,
            "resultSerialize",
            "completed",
            datetime(2026, 9, 2, tzinfo=timezone.utc),
        ).to_mapping()
    )
    result = _execution_result(
        staging,
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-123",
        processor_payload=json.dumps({"rows": [{"Frame_ID": 1}]}).encode(),
        progress_payload=progress_payload,
    )
    imported: list[object] = []
    completed_diagnostics: list[dict[str, object]] = []
    client_factory = object()

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(
        remote_worker,
        "execute_daytona_job",
        lambda request, *, client_factory, progress_callback, poll_wait: result,
    )
    monkeypatch.setattr(
        remote_worker,
        "persist_remote_video_result",
        lambda actual_storage, actual_job_id, payload: imported.append(payload),
    )
    original_save = Storage.save_analysis_artifact

    def save_artifact(self, match_id, analysis_type, payload):
        if analysis_type == "remote_transport_debug" and payload.get("runtimeOutcome") == "completed":
            assert not staging.exists()
            assert not execution.bundle_root.exists()
            completed_diagnostics.append(payload)
        return original_save(self, match_id, analysis_type, payload)

    monkeypatch.setattr(Storage, "save_analysis_artifact", save_artifact)

    remote_worker.run_remote_job(
        tmp_path,
        job.id,
        settings=_settings(),
        client_factory=client_factory,
    )

    persisted = storage.get_job(job.id)
    assert persisted.remoteRunId == "sandbox-123"
    assert persisted.status == "completed"
    assert imported == [{"rows": [{"Frame_ID": 1}]}]
    assert storage.load_analysis_artifact(match.id, "remote_transport_debug")["initialRunId"] == "sandbox-123"
    assert storage.load_analysis_artifact(match.id, "remote_worker_progress")["stage"] == "resultSerialize"
    identity = storage.load_analysis_artifact(match.id, "input_video_identity")
    assert identity["schemaVersion"] == 1
    assert identity["jobId"] == job.id
    assert identity["matchId"] == match.id
    assert identity["inputVideoSha256"] == "0cab1c9617404faf2b24e221e189ca5945813e14d3f766345b09ca13bbe28ffc"
    assert identity["inputVideoSizeBytes"] == 5
    assert identity["receiptSha256"] == result.result.receipt_sha256
    assert not staging.exists()
    assert not execution.bundle_root.exists()
    assert len(completed_diagnostics) == 1


def test_run_remote_job_rejects_input_receipt_replaced_after_result_validation(tmp_path: Path, monkeypatch) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-receipt-mismatch",
    )
    altered = _fixture_receipt().to_mapping()
    altered["files"][3]["sha256"] = "d" * 64
    (execution.bundle_root / "sealed" / "job-receipt.json").write_bytes(canonical_json_bytes(altered))
    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: result)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == "failed"
    assert not (tmp_path / "matches" / match.id / "input_video_identity.json").exists()
    assert not execution.bundle_root.exists()
    assert not result.staging_root.exists()


def test_run_remote_job_rolls_back_partial_football_outputs_when_import_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    storage.save_raw_rows(match.id, [{"existing": True}])
    storage.save_analysis_artifact(match.id, "ball_truth_layers", {"existing": True})
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    execution = _execution(workspace)
    result = _execution_result(
        staging,
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-rollback",
        processor_payload=b'{"rows":[{"Frame_ID":1}]}',
    )

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: result)

    def partial_import(actual_storage: Storage, actual_job_id: str, payload: object) -> None:
        actual_storage.save_raw_rows(match.id, [{"partial": True}])
        actual_storage.save_analysis_artifact(match.id, "ball_truth_layers", {"partial": True})
        raise RuntimeError("secret import detail")

    monkeypatch.setattr(remote_worker, "persist_remote_video_result", partial_import)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    persisted = storage.get_job(job.id)
    assert persisted.status == "failed"
    assert persisted.remoteRunId == "sandbox-rollback"
    assert storage.load_raw_rows(match.id) == [{"existing": True}]
    assert storage.load_analysis_artifact(match.id, "ball_truth_layers") == {"existing": True}
    assert storage.load_analysis_artifact(match.id, "remote_transport_debug")["initialRunId"] == "sandbox-rollback"


def test_remote_import_restores_input_video_identity_after_failure(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    storage.save_analysis_artifact(match.id, "input_video_identity", {"inputVideoSha256": "previous"})

    with pytest.raises(RuntimeError, match="failed import"):
        with storage.remote_result_import(match.id):
            storage.save_analysis_artifact(match.id, "input_video_identity", {"inputVideoSha256": "partial"})
            raise RuntimeError("failed import")

    assert storage.load_analysis_artifact(match.id, "input_video_identity") == {"inputVideoSha256": "previous"}


def test_run_remote_job_rejects_replaced_processor_after_adapter_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-replaced-processor",
    )
    replacement = workspace / "replacement.json"
    replacement.write_bytes(b'{"rows":[{"attacker":true}]}\n')
    imported: list[object] = []

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)

    def execute(*args, **kwargs):
        remote_worker.os.replace(replacement, result.processor_path)
        return result

    monkeypatch.setattr(remote_worker, "execute_daytona_job", execute)
    monkeypatch.setattr(
        remote_worker,
        "persist_remote_video_result",
        lambda *args: imported.append(args[-1]),
    )

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == "failed"
    assert imported == []


def test_run_remote_job_rejects_symlinked_progress_after_adapter_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    progress = canonical_json_bytes(
        ProgressEvent(
            1,
            job.id,
            1,
            98,
            "resultSerialize",
            "completed",
            datetime(2026, 9, 2, tzinfo=timezone.utc),
        ).to_mapping()
    )
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-symlink-progress",
        progress_payload=progress,
    )
    outside = tmp_path / "outside-progress.jsonl"
    outside.write_bytes(progress)
    imported: list[object] = []

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)

    def execute(*args, **kwargs):
        result.progress_path.unlink()
        result.progress_path.symlink_to(outside)
        return result

    monkeypatch.setattr(remote_worker, "execute_daytona_job", execute)
    monkeypatch.setattr(
        remote_worker,
        "persist_remote_video_result",
        lambda *args: imported.append(args[-1]),
    )

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == "failed"
    assert imported == []


def test_remote_import_restores_snapshot_when_atomic_restore_rename_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    storage.save_raw_rows(match.id, [{"original": True}])
    match_dir = storage._match_dir(match.id)
    original_replace = remote_worker.os.replace
    restore_attempted = False

    def fail_snapshot_restore(source, destination):
        nonlocal restore_attempted
        if Path(source).parent.name == "snapshot" and Path(destination).parent == match_dir:
            restore_attempted = True
            raise OSError("simulated atomic restore failure")
        return original_replace(source, destination)

    monkeypatch.setattr("backend.app.storage.os.replace", fail_snapshot_restore)

    with pytest.raises(RuntimeError, match="import failed"):
        with storage.remote_result_import(match.id):
            storage.save_raw_rows(match.id, [{"partial": True}])
            raise RuntimeError("import failed")

    assert storage.load_raw_rows(match.id) == [{"original": True}]
    assert restore_attempted is True
    assert list(tmp_path.glob(".remote-import-*")) == []


def test_remote_import_rollback_preserves_concurrent_unrelated_match_file(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    storage.save_raw_rows(match.id, [{"original": True}])
    annotation = storage._match_dir(match.id) / "coach-annotation.json"

    with pytest.raises(RuntimeError, match="import failed"):
        with storage.remote_result_import(match.id):
            storage.save_raw_rows(match.id, [{"partial": True}])
            annotation.write_text('{"note":"keep"}\n', encoding="utf-8")
            raise RuntimeError("import failed")

    assert storage.load_raw_rows(match.id) == [{"original": True}]
    assert annotation.read_text(encoding="utf-8") == '{"note":"keep"}\n'


def test_remote_import_rolls_back_every_owned_video_output(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    expected = {
        "accepted_match_state.json",
        "analytics.json",
        "ball_pipeline_trace.json",
        "ball_truth_layers.json",
        "decode_anchors.json",
        "events.json",
        "four_rates.json",
        "tactical_report.json",
        "drills.json",
            "frames.json",
            "current_generation.json",
            "input_video_identity.json",
        "ownership_publication.json",
        "raw_rows.json",
        "recovery_debug.json",
        "recovery_profile_matrix.json",
    }
    assert set(storage_module._REMOTE_RESULT_FILENAMES) == expected
    match_dir = storage._match_dir(match.id)
    for filename in expected:
        (match_dir / filename).write_text('{"state":"before"}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="import failed"):
        with storage.remote_result_import(match.id):
            for filename in expected:
                (match_dir / filename).write_text('{"state":"partial"}\n', encoding="utf-8")
            raise RuntimeError("import failed")

    for filename in expected:
        assert (match_dir / filename).read_text(encoding="utf-8") == '{"state":"before"}\n'


def test_remote_import_rejects_snapshot_source_swap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    storage.save_raw_rows(match.id, [{"original": True}])
    source = storage._match_dir(match.id) / "raw_rows.json"
    outside = tmp_path / "outside.json"
    outside.write_text('{"outside":true}\n', encoding="utf-8")
    source_identity = (source.stat().st_dev, source.stat().st_ino)
    original_read = storage_module.os.read
    swapped = False

    def swap_after_read(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        chunk = original_read(descriptor, size)
        opened = os.fstat(descriptor)
        if chunk and not swapped and (opened.st_dev, opened.st_ino) == source_identity:
            swapped = True
            source.unlink()
            source.symlink_to(outside)
        return chunk

    monkeypatch.setattr(storage_module.os, "read", swap_after_read)
    yielded = False

    with pytest.raises(RuntimeError, match="snapshot could not be confirmed"):
        with storage.remote_result_import(match.id):
            yielded = True

    assert swapped is True
    assert yielded is False
    assert source.is_symlink()
    assert outside.read_text(encoding="utf-8") == '{"outside":true}\n'
    assert list(tmp_path.glob(".remote-import-*")) == []


def test_remote_import_cleans_partial_snapshot_when_copy_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, _job_record = _job(storage)
    storage.save_raw_rows(match.id, [{"original": True}])
    original_write = storage_module.os.write
    failed = False

    def fail_snapshot_write(descriptor: int, payload: bytes) -> int:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated snapshot write failure")
        return original_write(descriptor, payload)

    monkeypatch.setattr(storage_module.os, "write", fail_snapshot_write)

    with pytest.raises(RuntimeError, match="snapshot could not be confirmed"):
        with storage.remote_result_import(match.id):
            raise AssertionError("snapshot failure must prevent import")

    assert failed is True
    assert list(tmp_path.glob(".remote-import-*")) == []


def test_run_remote_job_rolls_back_import_when_snapshot_cleanup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    storage.save_raw_rows(match.id, [{"original": True}])
    workspace = tmp_path / "workspace"
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-snapshot-cleanup",
    )
    original_rmtree = storage_module.shutil.rmtree
    cleanup_failed = False

    def fail_snapshot_cleanup_once(path, *args, **kwargs):
        nonlocal cleanup_failed
        if Path(path).name.startswith(".remote-import-") and not cleanup_failed:
            cleanup_failed = True
            (Path(path) / "snapshot" / "raw_rows.json").unlink()
            raise OSError("simulated snapshot cleanup failure")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: result)
    monkeypatch.setattr(storage_module.shutil, "rmtree", fail_snapshot_cleanup_once)

    def import_new_output(actual_storage: Storage, actual_job_id: str, payload: object) -> None:
        actual_storage.save_raw_rows(match.id, [{"new": True}])
        actual_storage.update_match_status(match.id, status="completed")

    monkeypatch.setattr(remote_worker, "persist_remote_video_result", import_new_output)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert cleanup_failed is True
    assert storage.get_job(job.id).status == "failed"
    assert storage.get_match(match.id).status == "failed"
    assert storage.load_raw_rows(match.id) == [{"original": True}]
    assert len(list(tmp_path.glob(".remote-import-*"))) == 1


def test_build_execution_request_seals_job_match_input_and_pre_cloud_release_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path / "storage")
    match, job = _job(storage)
    repo_root = tmp_path / "repo"
    manifest = repo_root / "backend/release/v7.3.json"
    evidence = repo_root / "backend/release/verification/v7.3-pre-cloud.json"
    model = tmp_path / "model.bin"
    manifest.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"runtimeOptions": {"primaryModel": {"artifactId": "primary-model"}}}),
        encoding="utf-8",
    )
    evidence.write_bytes(b"evidence")
    model.write_bytes(b"model")
    preflight = PreflightResult(
        source_commit="b" * 40,
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        manifest_path=manifest,
        evidence_path=evidence,
        evidence_phase="pre_cloud",
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        artifacts=(("primary-model", model, "/app/models/model.bin"),),
        artifact_metadata=(("primary-model", hashlib.sha256(b"model").hexdigest(), 5),),
    )
    monkeypatch.setattr(remote_worker, "REPO_ROOT", repo_root)
    preflight_calls: list[dict[str, object]] = []

    def fake_preflight(**kwargs):
        preflight_calls.append(kwargs)
        return preflight

    monkeypatch.setattr(remote_worker, "validate_release_preflight", fake_preflight)
    monkeypatch.setattr(
        remote_worker,
        "load_release_manifest",
        lambda *args, **kwargs: SimpleNamespace(
            source_commit="b" * 40,
            runtime_options={"primaryModel": {"artifactId": "primary-model"}},
        ),
    )

    def fake_build(*, output_path, **kwargs):
        Path(output_path).write_bytes(b"source archive")
        return Path(output_path)

    monkeypatch.setattr(remote_worker, "build_validated_tar_context", fake_build)

    execution = remote_worker._build_execution_request(storage, job.id, _settings())

    request = json.loads((execution.bundle_root / "job-request.json").read_text(encoding="utf-8"))
    receipt = json.loads((execution.bundle_root / request["receiptPath"]).read_text(encoding="utf-8"))
    assert request["jobId"] == job.id
    assert request["matchId"] == match.id
    assert (execution.bundle_root / request["inputVideoPath"]).read_bytes() == b"video"
    assert receipt["sourceCommit"] == "b" * 40
    assert preflight_calls[0]["mode"] == "build-only"
    assert preflight_calls[0]["evidence_path"] == evidence
    assert preflight_calls[0]["image_tag"] == (
        f"v7.3-{'b' * 40}-{hashlib.sha256(manifest.read_bytes()).hexdigest()[:12]}"
    )
    assert receipt["requestedRuntimeOptions"] == {
        "primaryModel": {"artifactId": "primary-model"}
    }
    assert {entry["role"] for entry in receipt["files"]} == {
        "source_archive",
        "manifest",
        "evidence",
        "runtime_artifact",
        "input_video",
        "job_request",
    }
    _root, _workspace, adapter_request, _receipt, _paths, _identities = (
        daytona_adapter._preflight(execution)
    )
    assert adapter_request.job_id == job.id


def test_bundle_file_copy_streams_and_rejects_nonregular_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    payload = b"x" * (128 * 1024 + 1)
    source.write_bytes(payload)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _self: (_ for _ in ()).throw(AssertionError("whole-file read")),
    )

    identity = remote_worker._copy_regular_file(source, destination)

    assert identity.size_bytes == len(payload)
    assert identity.sha256 == hashlib.sha256(payload).hexdigest()
    assert destination.stat().st_size == len(payload)
    with pytest.raises(RuntimeError, match="bundle file is invalid"):
        remote_worker._copy_regular_file(source, destination)
    assert destination.stat().st_size == len(payload)

    symlink = tmp_path / "source-link.bin"
    symlink.symlink_to(source)
    with pytest.raises(RuntimeError, match="bundle file is invalid"):
        remote_worker._copy_regular_file(symlink, tmp_path / "symlink-copy.bin")

    fifo = tmp_path / "source.fifo"
    os.mkfifo(fifo)
    with pytest.raises(RuntimeError, match="bundle file is invalid"):
        remote_worker._copy_regular_file(fifo, tmp_path / "fifo-copy.bin")


def test_bundle_file_copy_rejects_source_path_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.bin"
    replacement = tmp_path / "replacement.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"original")
    replacement.write_bytes(b"replacement")
    original_read = remote_worker.os.read
    swapped = False

    def swap_after_read(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        chunk = original_read(descriptor, size)
        if chunk and not swapped:
            swapped = True
            os.replace(replacement, source)
        return chunk

    monkeypatch.setattr(remote_worker.os, "read", swap_after_read)

    with pytest.raises(RuntimeError, match="bundle file is invalid"):
        remote_worker._copy_regular_file(source, destination)

    assert swapped is True
    assert not destination.exists()


def test_build_execution_request_reports_unconfirmed_bundle_cleanup_without_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path / "storage")
    _match_record, job = _job(storage)
    repo_root = tmp_path / "repo"
    manifest = repo_root / "backend/release/v7.3.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(remote_worker, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        remote_worker,
        "load_release_manifest",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("credential-secret")),
    )
    cleanup_calls: list[tuple[Path, Path, str]] = []

    def fail_cleanup(root: Path, workspace: Path, prefix: str) -> None:
        cleanup_calls.append((root, workspace, prefix))
        raise RuntimeError("credential-secret")

    monkeypatch.setattr(remote_worker, "_cleanup_owned_directory", fail_cleanup)

    with pytest.raises(RuntimeError, match="cleanup could not be confirmed") as caught:
        remote_worker._build_execution_request(storage, job.id, _settings())

    assert cleanup_calls and cleanup_calls[0][2] == "daytona-bundle-"
    assert "credential-secret" not in str(caught.value)


def test_missing_daytona_credentials_fail_job_without_local_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    executed: list[object] = []
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: executed.append(args))

    remote_worker.run_remote_job(tmp_path, job.id)

    persisted = storage.get_job(job.id)
    assert persisted.status == "failed"
    assert persisted.error == "Daytona processing failed"
    assert executed == []
    assert storage.get_match(match.id).status == "failed"
    assert storage.load_analysis_artifact(match.id, "remote_transport_debug")["runtimeOutcome"] == "failed"
    assert storage.load_analysis_artifact(match.id, "remote_worker_progress") == {}


def test_initial_diagnostic_write_failure_still_terminalizes_job_before_retrying_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    original_save = Storage.save_analysis_artifact
    original_update = Storage.update_job
    events: list[str] = []
    failed_once = False

    def fail_initial_save(self, match_id, analysis_type, payload):
        nonlocal failed_once
        events.append(f"artifact:{analysis_type}")
        if analysis_type == "remote_worker_progress" and not failed_once:
            failed_once = True
            raise OSError("simulated diagnostic disk failure")
        return original_save(self, match_id, analysis_type, payload)

    def record_update(self, actual_job_id, **kwargs):
        events.append(f"job:{kwargs['status']}")
        return original_update(self, actual_job_id, **kwargs)

    monkeypatch.setattr(Storage, "save_analysis_artifact", fail_initial_save)
    monkeypatch.setattr(Storage, "update_job", record_update)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == "failed"
    assert storage.get_match(match.id).status == "failed"
    assert events.index("job:failed") < events.index("artifact:remote_transport_debug")


def test_staging_cleanup_does_not_follow_symlinks_outside_owned_directory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    outside = tmp_path / "outside"
    staging.mkdir(parents=True)
    outside.mkdir()
    protected = outside / "protected.txt"
    protected.write_text("keep", encoding="utf-8")
    (staging / "outside-link").symlink_to(outside, target_is_directory=True)

    remote_worker._cleanup_owned_directory(staging, workspace, "daytona-result-")

    assert not staging.exists()
    assert protected.read_text(encoding="utf-8") == "keep"

    staging.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="cleanup could not be confirmed"):
        remote_worker._cleanup_owned_directory(staging, workspace, "daytona-result-")
    assert protected.read_text(encoding="utf-8") == "keep"


def test_staging_cleanup_does_not_delete_rename_swapped_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    replacement = workspace / "replacement"
    moved_owned = workspace / "moved-owned"
    staging.mkdir(parents=True)
    replacement.mkdir()
    (staging / "owned.txt").write_text("owned", encoding="utf-8")
    protected = replacement / "protected.txt"
    protected.write_text("keep", encoding="utf-8")
    original_move = daytona_adapter._rename_noreplace
    swapped = False

    def swap_then_move(source_parent_fd, source, destination_parent_fd, destination):
        nonlocal swapped
        if not swapped and source == staging.name:
            swapped = True
            remote_worker.os.rename(staging, moved_owned)
            remote_worker.os.rename(replacement, staging)
        return original_move(source_parent_fd, source, destination_parent_fd, destination)

    monkeypatch.setattr(daytona_adapter, "_rename_noreplace", swap_then_move)

    with pytest.raises(RuntimeError, match="cleanup could not be confirmed"):
        remote_worker._cleanup_owned_directory(staging, workspace, "daytona-result-")

    assert swapped is True
    assert (staging / "protected.txt").read_text(encoding="utf-8") == "keep"
    assert (moved_owned / "owned.txt").read_text(encoding="utf-8") == "owned"


def test_progress_loader_uses_the_bounded_job_bound_contract(tmp_path: Path) -> None:
    event = ProgressEvent(
        1,
        "job-progress-1",
        1,
        98,
        "resultSerialize",
        "completed",
        datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    result = _execution_result(
        tmp_path / "daytona-result-progress",
        job_id="job-progress-1",
        match_id="match-progress-1",
        sandbox_id="sandbox-progress",
        progress_payload=canonical_json_bytes(event.to_mapping()),
    )

    assert remote_worker._load_progress(
        result, job_id="job-progress-1", match_id="match-progress-1"
    ) == event.to_mapping()
    with pytest.raises(RuntimeError, match="progress result is invalid"):
        remote_worker._load_progress(
            result, job_id="different-job", match_id="match-progress-1"
        )


def test_processor_loader_binds_the_processor_path_and_completion_identity(
    tmp_path: Path,
) -> None:
    result = _execution_result(
        tmp_path / "daytona-result-bindings",
        job_id="job-bindings-1",
        match_id="match-bindings-1",
        sandbox_id="sandbox-bindings",
        progress_payload=b'{"rows":[]}\n',
    )
    swapped_path = replace(result, processor_path=result.progress_path)
    wrong_completion = replace(
        result,
        completion=replace(result.completion, match_id="different-match"),
    )

    for invalid in (swapped_path, wrong_completion):
        with pytest.raises(RuntimeError, match="processor result is invalid"):
            remote_worker._load_processor_result(
                invalid,
                job_id="job-bindings-1",
                match_id="match-bindings-1",
            )


@pytest.mark.parametrize("field", ["size", "digest"])
def test_processor_loader_requires_exact_declared_artifact_identity(
    tmp_path: Path,
    field: str,
) -> None:
    result = _execution_result(
        tmp_path / f"daytona-result-{field}",
        job_id="job-artifact-1",
        match_id="match-artifact-1",
        sandbox_id=f"sandbox-{field}",
    )
    processor_entry, progress_entry = result.result.artifacts
    invalid_entry = FileEntry(
        "result_artifact",
        processor_entry.relative_path,
        processor_entry.size_bytes + (1 if field == "size" else 0),
        "f" * 64 if field == "digest" else processor_entry.sha256,
    )
    invalid = replace(
        result,
        result=replace(result.result, artifacts=(invalid_entry, progress_entry)),
    )

    with pytest.raises(RuntimeError, match="processor result is invalid"):
        remote_worker._load_processor_result(
            invalid,
            job_id="job-artifact-1",
            match_id="match-artifact-1",
        )


def test_processor_loader_rejects_payload_above_worker_artifact_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result = _execution_result(
        tmp_path / "daytona-result-processor",
        job_id="job-processor-1",
        match_id="match-processor-1",
        sandbox_id="sandbox-processor",
    )
    monkeypatch.setattr(remote_worker, "MAX_PROCESSOR_IMPORT_BYTES", 4)

    with pytest.raises(RuntimeError, match="processor result is invalid"):
        remote_worker._load_processor_result(
            result, job_id="job-processor-1", match_id="match-processor-1"
        )


V2_HEADER = b'{"metadata":{"trackColors":{}},"rowCount":2,"schemaVersion":1}\n'
V2_ROWS = b'{"Frame_ID":1}\n{"Frame_ID":2}\n'


def _v2_result(tmp_path, payload=V2_HEADER + V2_ROWS, *, row_count=2):
    return _execution_result(
        tmp_path / "daytona-result-v2",
        job_id="job-v2", match_id="match-v2", sandbox_id="sandbox-v2",
        processor_payload=payload, processor_row_count=row_count,
    )


def _v2_source(result):
    return remote_worker._load_processor_result_source(
        result, job_id="job-v2", match_id="match-v2"
    )


def _production_shaped_result(tmp_path: Path, *, job_id: str, match_id: str, row_count: int):
    result = _execution_result(
        tmp_path / "daytona-result-capacity",
        job_id=job_id,
        match_id=match_id,
        sandbox_id="sandbox-capacity",
        processor_payload=b"",
        processor_row_count=row_count,
    )
    digest = hashlib.sha256()
    size = 0

    def write(value: object, handle) -> None:
        nonlocal size
        payload = gpu_worker._processor_json_line(
            value,
            maximum=gpu_worker.MAX_PROCESSOR_ROW_LINE_BYTES,
        )
        handle.write(payload)
        digest.update(payload)
        size += len(payload)

    with result.processor_path.open("wb") as handle:
        write(
            {"schemaVersion": 1, "rowCount": row_count, "metadata": {"trackColors": {}}},
            handle,
        )
        for index in range(row_count):
            frame_id, slot = divmod(index, 23)
            write(
                {
                    "Frame_ID": frame_id,
                    "Timestamp": frame_id / 5,
                    "Entity_Type": "ball" if slot == 0 else "player",
                    "Track_ID": -1 if slot == 0 else slot,
                    "X": float((frame_id + slot) % 100),
                    "Y": float((frame_id * 2 + slot) % 68),
                    "Conf": 0.9,
                },
                handle,
            )
    processor, progress = result.result.artifacts
    return replace(
        result,
        result=replace(
            result.result,
            artifacts=(replace(processor, size_bytes=size, sha256=digest.hexdigest()), progress),
        ),
    )


def measured_import_peak(tmp_path: Path, row_count: int) -> int:
    storage = Storage(tmp_path / f"storage-{row_count}")
    match, job = _job(storage)
    result = _production_shaped_result(
        tmp_path / f"capacity-{row_count}",
        job_id=job.id,
        match_id=match.id,
        row_count=row_count,
    )

    tracemalloc.start()
    try:
        with storage.remote_result_import(match.id):
            with remote_worker._load_processor_result_source(
                result,
                job_id=job.id,
                match_id=match.id,
            ) as source:
                assert source.row_count == row_count
                remote_worker.persist_remote_video_result_stream(storage, job.id, source)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert storage._match_dir(match.id).joinpath("raw_rows.json").read_bytes().count(
        b'"Frame_ID"'
    ) == row_count
    frames = storage.load_frames(match.id)
    expected_frame_count = (row_count + 22) // 23
    assert len(frames) == expected_frame_count
    assert sum(frame.ball is not None for frame in frames) == expected_frame_count
    assert sum(
        len(frame.myTeam) + len(frame.enemies) + len(frame.unassignedPlayers)
        for frame in frames
    ) == row_count - expected_frame_count
    first = frames[0]
    last = frames[-1]
    last_slot = (row_count - 1) % 23
    assert (first.frameId, first.timestamp, first.ball.x, first.ball.y) == (0, 0.0, 0.0, 0.0)
    assert (first.unassignedPlayers[0].id, first.unassignedPlayers[0].x, first.unassignedPlayers[0].y) == (1, 1.0, 1.0)
    assert (last.frameId, last.timestamp, last.ball.x, last.ball.y) == (
        expected_frame_count - 1,
        (expected_frame_count - 1) / 5,
        float((expected_frame_count - 1) % 100),
        float(((expected_frame_count - 1) * 2) % 68),
    )
    assert (
        last.unassignedPlayers[-1].id,
        last.unassignedPlayers[-1].x,
        last.unassignedPlayers[-1].y,
    ) == (
        last_slot,
        float(((expected_frame_count - 1) + last_slot) % 100),
        float((((expected_frame_count - 1) * 2) + last_slot) % 68),
    )
    return peak


def import_production_shaped_rows(tmp_path: Path, *, row_count: int) -> int:
    return measured_import_peak(tmp_path, row_count)


@pytest.mark.parametrize("failure", [None, "digest", "row", "analytics", "persistence", "early_exit"])
def test_run_remote_stream_import_consumes_validated_eof_inside_rollback(tmp_path, monkeypatch, failure):
    from backend.app import processor

    storage = Storage(tmp_path)
    match, job = _job(storage)
    row = {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.9}
    processor.persist_remote_video_result(storage, job.id, {"rows": [row], "trackColors": {}})
    match_dir = storage._match_dir(match.id)
    before = {path.name: path.read_bytes() for path in match_dir.glob("*.json")}
    rows = [{**row, "X": 75.0}, {**row, "Frame_ID": 1, "Timestamp": 0.2}]
    if failure == "row":
        del rows[-1]["X"]
    chunks, row_count = gpu_worker._processor_result_v2_chunks({"rows": rows, "trackColors": {}})
    workspace = tmp_path / "workspace"
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned", job_id=job.id, match_id=match.id,
        sandbox_id="sandbox-stream", processor_payload=b"".join(chunks), processor_row_count=row_count,
    )
    if failure == "digest":
        entry, progress = result.result.artifacts
        result = replace(result, result=replace(result.result, artifacts=(replace(entry, sha256="0" * 64), progress)))
    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: result)
    monkeypatch.setattr(remote_worker, "_load_processor_result", lambda *args, **kwargs: pytest.fail("legacy whole read"))
    monkeypatch.setattr(remote_worker, "persist_remote_video_result", lambda *args: pytest.fail("legacy persistence"))

    def fail(*args, **kwargs):
        raise RuntimeError("injected import failure")

    if failure == "analytics":
        monkeypatch.setattr(processor, "_compute_outputs_and_match_state", fail)
    elif failure == "persistence":
        monkeypatch.setattr(Storage, "publish_generation", fail)
    elif failure == "early_exit":
        def early_exit(actual_storage, actual_job, source):
            actual_storage.save_raw_rows(match.id, [next(source.rows)])
        monkeypatch.setattr(remote_worker, "persist_remote_video_result_stream", early_exit, raising=False)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == ("failed" if failure else "completed")
    if failure:
        assert {name: (match_dir / name).read_bytes() for name in before} == before
        assert storage.get_job(job.id).error == "Daytona processing failed"
    else:
        assert storage.load_raw_rows(match.id) == rows
        assert [frame.ball.x for frame in storage.load_frames(match.id)] == [75.0, 50.0]
        assert storage.get_match(match.id).status == "ready"
    assert not result.staging_root.exists()
    assert not execution.bundle_root.exists()


def test_v2_loader_yields_rows_once_without_legacy_whole_read(tmp_path, monkeypatch):
    result = _v2_result(tmp_path)
    monkeypatch.setattr(remote_worker, "_read_result_artifact", lambda *a, **k: pytest.fail("whole read"))
    with _v2_source(result) as source:
        assert source.metadata == {"trackColors": {}}
        assert source.row_count == 2
        assert list(source.rows) == [{"Frame_ID": 1}, {"Frame_ID": 2}]
        with pytest.raises(RuntimeError, match="already consumed"):
            list(source.rows)


def test_v2_loader_accepts_writer_metadata_at_depth_limit(tmp_path):
    metadata = "leaf"
    for _ in range(gpu_worker.MAX_PROCESSOR_RESULT_DEPTH):
        metadata = {"nested": metadata}
    chunks, row_count = gpu_worker._processor_result_v2_chunks(
        {**metadata, "rows": [{"Frame_ID": 1}]}
    )
    result = _v2_result(tmp_path, b"".join(chunks), row_count=row_count)
    with _v2_source(result) as source:
        assert source.metadata == metadata
        assert list(source.rows) == [{"Frame_ID": 1}]


def test_v2_loader_requires_bounded_reads(tmp_path, monkeypatch):
    result = _v2_result(tmp_path)
    original_fdopen = remote_worker.os.fdopen
    requests = []
    line_limits = iter([
        remote_worker.MAX_PROCESSOR_METADATA_LINE_BYTES + 1,
        remote_worker.MAX_PROCESSOR_ROW_LINE_BYTES + 1,
        remote_worker.MAX_PROCESSOR_ROW_LINE_BYTES + 1,
    ])

    class GuardedHandle:
        def __init__(self, descriptor, mode):
            self.handle = original_fdopen(descriptor, mode)

        def readline(self, size=-1):
            assert size == next(line_limits), "unexpected or unbounded line read"
            requests.append("line")
            return self.handle.readline(size)

        def read(self, size=-1):
            assert size == 1, "only the one-byte EOF read is allowed"
            requests.append("eof")
            return self.handle.read(size)

        def fileno(self):
            return self.handle.fileno()

        def close(self):
            self.handle.close()

    monkeypatch.setattr(remote_worker.os, "fdopen", GuardedHandle)
    with _v2_source(result) as source:
        assert source.metadata == {"trackColors": {}}
        assert list(source.rows) == [{"Frame_ID": 1}, {"Frame_ID": 2}]
    assert requests == ["line", "line", "line", "eof"]


@pytest.mark.parametrize("payload,row_count", [
    (V2_HEADER + V2_ROWS, 3),
    (V2_HEADER + b'{"Frame_ID":1}\n', 2),
    (V2_HEADER + V2_ROWS + b'{"Frame_ID":3}\n', 2),
    (V2_HEADER + V2_ROWS + b'\n', 2),
    (V2_HEADER + V2_ROWS.rstrip(b'\n'), 2),
    (V2_HEADER + b'{"Frame_ID":2}\n{"Frame_ID":1}\n', 2),
    (V2_HEADER + b'{"Frame_ID":true}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID":1.5}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID":-1}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'[]\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID": 1}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID":1,"Frame_ID":1}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID":1,"value":NaN}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER + b'{"Frame_ID":1,"apiKey":"secret-value"}\n{"Frame_ID":2}\n', 2),
    (V2_HEADER.replace(b'"schemaVersion":1', b'"schemaVersion":2') + V2_ROWS, 2),
    (V2_HEADER.replace(b'"rowCount":2', b'"rowCount":true') + V2_ROWS, 2),
    (V2_HEADER.replace(b'"trackColors":{}', b'"rows":[]') + V2_ROWS, 2),
    (V2_HEADER.replace(b'"trackColors":{}', b'"apiKey":"secret-value"') + V2_ROWS, 2),
    (V2_HEADER.replace(b'"metadata":', b'"extra":0,"metadata":') + V2_ROWS, 2),
])
def test_v2_loader_rejects_invalid_framing_values_and_counts(tmp_path, payload, row_count):
    result = _v2_result(tmp_path, payload, row_count=row_count)
    with pytest.raises(RuntimeError, match="^Daytona processor result is invalid$") as error:
        with _v2_source(result) as source:
            list(source.rows)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("limit", [
    "MAX_PROCESSOR_METADATA_LINE_BYTES", "MAX_PROCESSOR_ROW_LINE_BYTES",
    "MAX_PROCESSOR_RESULT_BYTES",
])
def test_v2_loader_enforces_bounds(tmp_path, monkeypatch, limit):
    result = _v2_result(tmp_path)
    monkeypatch.setattr(remote_worker, limit, 4, raising=False)
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            list(source.rows)


@pytest.mark.parametrize("field", ["size", "digest", "path", "job", "match"])
def test_v2_loader_binds_artifact_and_completion_identity(tmp_path, field):
    result = _v2_result(tmp_path)
    processor, progress = result.result.artifacts
    if field in {"size", "digest"}:
        entry = replace(processor, size_bytes=processor.size_bytes + (field == "size"),
                        sha256="f" * 64 if field == "digest" else processor.sha256)
        result = replace(result, result=replace(result.result, artifacts=(entry, progress)))
    elif field == "path":
        result = replace(result, processor_path=result.progress_path)
    elif field == "job":
        result = replace(result, completion=replace(result.completion, job_id="wrong-job"))
    else:
        result = replace(result, completion=replace(result.completion, match_id="wrong-match"))
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            list(source.rows)


@pytest.mark.parametrize("mutation", ["replace", "symlink", "append", "truncate", "overwrite"])
def test_v2_loader_rejects_file_mutation_before_eof(tmp_path, mutation):
    result = _v2_result(tmp_path)
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            rows = iter(source.rows)
            assert next(rows) == {"Frame_ID": 1}
            path = result.processor_path
            if mutation in {"replace", "symlink"}:
                original = path.with_suffix(".original")
                path.rename(original)
                if mutation == "replace":
                    path.write_bytes(V2_HEADER + V2_ROWS)
                else:
                    path.symlink_to(original)
            elif mutation == "append":
                with path.open("ab") as handle:
                    handle.write(b'\n')
            elif mutation == "truncate":
                path.write_bytes(V2_HEADER)
            else:
                # Same-size in-place overwrite can keep inode/size and, on coarse
                # timestamps, mtime. Preserve mtime so the loader cannot hide behind st_mtime_ns.
                before = path.stat()
                path.write_bytes(V2_HEADER + V2_ROWS.replace(b'2', b'3'))
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            list(rows)



def test_v2_loader_rejects_overwrite_when_open_fd_metadata_does_not_change(tmp_path, monkeypatch):
    """Buffered readers plus unchanged fstat metadata must not accept a same-size overwrite."""
    result = _v2_result(tmp_path)
    original_fstat = os.fstat
    original_stat = os.stat
    snapshots: dict[tuple[int, int], os.stat_result] = {}

    def _freeze(st: os.stat_result) -> os.stat_result:
        key = (st.st_dev, st.st_ino)
        return snapshots.setdefault(key, st)

    monkeypatch.setattr(os, "fstat", lambda fd: _freeze(original_fstat(fd)))
    monkeypatch.setattr(
        os,
        "stat",
        lambda path, *args, **kwargs: _freeze(original_stat(path, *args, **kwargs)),
    )

    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            rows = iter(source.rows)
            assert next(rows) == {"Frame_ID": 1}
            result.processor_path.write_bytes(V2_HEADER + V2_ROWS.replace(b"2", b"3"))
            list(rows)


def test_v2_loader_rejects_initial_symlink(tmp_path):
    result = _v2_result(tmp_path)
    original = result.processor_path.with_suffix(".original")
    result.processor_path.rename(original)
    result.processor_path.symlink_to(original)
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            list(source.rows)


def test_v2_loader_closes_descriptor_on_partial_consumption(tmp_path, monkeypatch):
    result = _v2_result(tmp_path)
    opened = []
    original_open = remote_worker._open_preflight_regular_file

    def record_open(path):
        descriptor = original_open(path)
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(remote_worker, "_open_preflight_regular_file", record_open)
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        with _v2_source(result) as source:
            assert next(source.rows) == {"Frame_ID": 1}
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])


def test_v2_loader_allows_equal_frames_and_empty_stream(tmp_path):
    result = _v2_result(tmp_path, V2_HEADER + b'{"Frame_ID":1}\n{"Frame_ID":1}\n')
    with _v2_source(result) as source:
        assert list(source.rows) == [{"Frame_ID": 1}, {"Frame_ID": 1}]
    empty = _v2_result(tmp_path / "empty", V2_HEADER.replace(b'"rowCount":2', b'"rowCount":0'), row_count=0)
    with _v2_source(empty) as source:
        assert list(source.rows) == []


def test_v2_loader_source_dispatch_keeps_v1_limit(tmp_path, monkeypatch):
    result = _execution_result(tmp_path / "v1", job_id="job-v2", match_id="match-v2", sandbox_id="sandbox-v1")
    assert _v2_source(result) == {"rows": []}
    monkeypatch.setattr(remote_worker, "MAX_PROCESSOR_IMPORT_BYTES", 4)
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        _v2_source(result)


def test_v2_loader_does_not_mask_consumer_failure_and_closes_source(tmp_path):
    result = _v2_result(tmp_path)
    with pytest.raises(LookupError, match="consumer failed"):
        with _v2_source(result) as source:
            assert next(source.rows) == {"Frame_ID": 1}
            raise LookupError("consumer failed")
    with pytest.raises(RuntimeError, match="already consumed"):
        next(source.rows)


def test_v2_loader_accepts_v2_above_legacy_limit(tmp_path, monkeypatch):
    result = _v2_result(tmp_path)
    monkeypatch.setattr(remote_worker, "MAX_PROCESSOR_IMPORT_BYTES", 4)
    with _v2_source(result) as source:
        assert list(source.rows) == [{"Frame_ID": 1}, {"Frame_ID": 2}]


def test_v2_loader_binds_completion_generation(tmp_path):
    result = _v2_result(tmp_path)
    completion = replace(result.completion, result_path="result-bundle.json.generations/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/result.json")
    with pytest.raises(RuntimeError, match="processor result is invalid"):
        _v2_source(replace(result, completion=completion))


@pytest.mark.skipif(os.getenv("RUN_FULL_MATCH_CAPACITY") != "1", reason="opt-in capacity test")
def test_621000_rows_round_trip_with_bounded_host_memory(tmp_path):
    peak = import_production_shaped_rows(tmp_path, row_count=621_000)

    print(f"621000-row host import peak: {peak} bytes")
    assert peak < 256 * 1024 * 1024


def test_streaming_import_peak_does_not_scale_with_encoded_copies(tmp_path):
    small = measured_import_peak(tmp_path, 10_000)
    large = measured_import_peak(tmp_path, 100_000)

    assert large - small < 96 * 1024 * 1024


def test_post_execution_failure_explicitly_persists_sandbox_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    _match_record, job = _job(storage)
    match_id = storage.get_job(job.id).matchId
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    execution = _execution(workspace)
    result = _execution_result(
        staging,
        job_id=job.id,
        match_id=match_id,
        sandbox_id="sandbox-after-execute",
        progress_payload=b"invalid\n",
    )
    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", lambda *args, **kwargs: result)

    original_update_job = Storage.update_job
    failed_once = False

    def fail_first_remote_id_update(self, actual_job_id, **kwargs):
        nonlocal failed_once
        if kwargs.get("remote_run_id") == result.sandbox_id and not failed_once:
            failed_once = True
            raise OSError("simulated database interruption")
        return original_update_job(self, actual_job_id, **kwargs)

    monkeypatch.setattr(Storage, "update_job", fail_first_remote_id_update)

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).remoteRunId == result.sandbox_id


def test_missing_owned_bundle_is_an_unconfirmed_cleanup_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    _match_record, job = _job(storage)
    match_id = storage.get_job(job.id).matchId
    workspace = tmp_path / "workspace"
    staging = workspace / "daytona-result-owned"
    execution = _execution(workspace)
    bundle = execution.bundle_root
    result = _execution_result(
        staging,
        job_id=job.id,
        match_id=match_id,
        sandbox_id="sandbox-missing-bundle",
    )
    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    imported: list[object] = []

    def execute(*args, **kwargs):
        bundle.rename(workspace / "missing-owned-bundle")
        return result

    monkeypatch.setattr(remote_worker, "execute_daytona_job", execute)
    monkeypatch.setattr(
        remote_worker,
        "persist_remote_video_result",
        lambda *args: imported.append(args[-1]),
    )

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    persisted = storage.get_job(job.id)
    assert persisted.status == "failed"
    assert persisted.error == "Daytona staging cleanup could not be confirmed"
    assert imported == []


def test_wrong_bound_exact_result_still_cleans_returned_staging(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = Storage(tmp_path)
    match, job = _job(storage)
    workspace = tmp_path / "workspace"
    execution = _execution(workspace)
    result = _execution_result(
        workspace / "daytona-result-owned",
        job_id=job.id,
        match_id=match.id,
        sandbox_id="sandbox-wrong-binding",
    )
    wrong_result = replace(
        result,
        result=replace(result.result, job_id="different-job"),
    )
    monkeypatch.setattr(remote_worker, "_build_execution_request", lambda *args: execution)
    monkeypatch.setattr(
        remote_worker,
        "execute_daytona_job",
        lambda *args, **kwargs: wrong_result,
    )

    remote_worker.run_remote_job(tmp_path, job.id, settings=_settings())

    assert storage.get_job(job.id).status == "failed"
    assert not result.staging_root.exists()
