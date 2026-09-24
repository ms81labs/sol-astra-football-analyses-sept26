from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import fields, replace
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tracemalloc

import pytest
from pydantic import ValidationError

from backend.app.remote_contracts import (
    CompletionReceipt,
    FileEntry,
    JobReceipt,
    JobRequest,
    MAX_PROGRESS_TOTAL_BYTES,
    RemoteContractError,
    ResultBundle,
    canonical_json_bytes,
    load_canonical_json,
    validate_completion,
)


COMMIT = "b" * 40


class FlushSpy:
    def __init__(self):
        self.value = ""
        self.flush_count = 0

    @property
    def lines(self):
        return self.value.splitlines(keepends=True)

    def write(self, value):
        self.value += value
        return len(value)

    def flush(self):
        self.flush_count += 1


def _entry(role: str, relative_path: str, payload: bytes) -> dict[str, object]:
    return {
        "role": role,
        "relativePath": relative_path,
        "sizeBytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _runtime_options(reference: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "primary_model": reference or {"artifactId": "primary-model"},
        "auxiliary_ball_model": None,
        "auxiliary_ball_model_profile": None,
        "primary_acquisition_mode": "anchored_player_ranked_context_960",
        "edge_share_repair_profile": None,
        "baseline_guided_rescue_reference": None,
        "proposal_selection_truth_seed": None,
        "reviewed_positive_anchor_seed": None,
    }


def _bundle(
    tmp_path: Path,
    *,
    reference: dict[str, object] | None = None,
    all_runtime_artifacts: bool = False,
    identical_primary_auxiliary: bool = False,
) -> tuple[Path, Path, Path]:
    artifact_payloads = {"primary-model": b"sealed-model"}
    runtime_options = _runtime_options(reference)
    if all_runtime_artifacts:
        artifact_payloads.update({
            "auxiliary-model": b"auxiliary-model",
            "baseline-reference": b"baseline-reference",
            "truth-seed": b"truth-seed",
            "anchor-seed": b"anchor-seed",
        })
        runtime_options.update({
            "auxiliary_ball_model": {"artifactId": "auxiliary-model"},
            "auxiliary_ball_model_profile": "auxiliary-profile",
            "edge_share_repair_profile": "edge-profile",
            "baseline_guided_rescue_reference": {"artifactId": "baseline-reference"},
            "proposal_selection_truth_seed": {"artifactId": "truth-seed"},
            "reviewed_positive_anchor_seed": {"artifactId": "anchor-seed"},
        })
    if identical_primary_auxiliary:
        artifact_payloads["auxiliary-model"] = artifact_payloads["primary-model"]
        runtime_options["auxiliary_ball_model"] = {"artifactId": "auxiliary-model"}
    manifest_artifacts = [
        {
            "id": artifact_id,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "sizeBytes": len(payload),
            "localRelativePath": f"models/{artifact_id}.bin",
            "containerPath": f"/app/models/{artifact_id}.bin",
            "origin": "release",
            "retentionClass": "release",
        }
        for artifact_id, payload in artifact_payloads.items()
    ]
    manifest = {
        "schemaVersion": 1,
        "releaseVersion": "v7.3",
        "candidateVersion": "v7.3",
        "runtimeVersion": "v7.3",
        "sourceCommit": COMMIT,
        "createdAt": "2026-08-25T00:00:00Z",
        "runtimeOptions": runtime_options,
        "artifacts": manifest_artifacts,
        "requiredContracts": [
            "video_to_analysis_product_api_v1",
            "video_to_analysis_report_v1",
        ],
    }
    manifest_bytes = canonical_json_bytes(manifest)
    request = {
        "schemaVersion": 1,
        "jobId": "job-1",
        "matchId": "match-1",
        "receiptPath": "sealed/receipt.json",
        "inputVideoPath": "inputs/match.mp4",
        "config": {
            "attackDirection": "left_to_right",
            "manualHomographyPoints": [],
            "myTeamCluster": None,
            "llmProvider": "local",
            "autoHomography": True,
        },
    }
    request_bytes = canonical_json_bytes(request)
    payloads = {
        "source/source.tar": b"source",
        "manifest.json": manifest_bytes,
        "evidence.json": b"evidence",
        "inputs/match.mp4": b"video",
        "request.json": request_bytes,
        **{
            ("sealed/model.bin" if artifact_id == "primary-model" else f"sealed/{artifact_id}.bin"): payload
            for artifact_id, payload in artifact_payloads.items()
        },
    }
    receipt = {
        "schemaVersion": 1,
        "sourceCommit": COMMIT,
        "manifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "evidenceSha256": hashlib.sha256(payloads["evidence.json"]).hexdigest(),
        "jobRequestSha256": hashlib.sha256(request_bytes).hexdigest(),
        "requestedRuntimeOptions": runtime_options,
        "files": [
            _entry("source_archive", "source/source.tar", payloads["source/source.tar"]),
            _entry("manifest", "manifest.json", payloads["manifest.json"]),
            _entry("evidence", "evidence.json", payloads["evidence.json"]),
            _entry("input_video", "inputs/match.mp4", payloads["inputs/match.mp4"]),
            _entry("job_request", "request.json", payloads["request.json"]),
            *[
                _entry(
                    "runtime_artifact",
                    "sealed/model.bin" if artifact_id == "primary-model" else f"sealed/{artifact_id}.bin",
                    payload,
                )
                for artifact_id, payload in artifact_payloads.items()
            ],
        ],
    }
    for relative, payload in payloads.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    receipt_path = tmp_path / "sealed/receipt.json"
    receipt_path.write_bytes(canonical_json_bytes(receipt))
    return tmp_path / "request.json", tmp_path / "outputs/result.json", tmp_path / "outputs/completion.json"


def _publication_paths(result_path: Path, completion_path: Path) -> tuple[Path, ...]:
    return (
        result_path,
        completion_path,
        result_path.with_name(f"{result_path.stem}.processor-result.json"),
        result_path.with_name(f"{result_path.stem}.progress.jsonl"),
    )


def _set_bundle_job_id(root: Path, job_id: str) -> None:
    request_path = root / "request.json"
    request_mapping = load_canonical_json(request_path)
    request_mapping["jobId"] = job_id
    request_bytes = canonical_json_bytes(request_mapping)
    request_path.write_bytes(request_bytes)
    receipt_path = root / "sealed/receipt.json"
    receipt_mapping = load_canonical_json(receipt_path)
    receipt_mapping["jobRequestSha256"] = hashlib.sha256(request_bytes).hexdigest()
    request_entry = next(
        item for item in receipt_mapping["files"] if item["role"] == "job_request"
    )
    request_entry["sizeBytes"] = len(request_bytes)
    request_entry["sha256"] = hashlib.sha256(request_bytes).hexdigest()
    receipt_path.write_bytes(canonical_json_bytes(receipt_mapping))


def _generation_layout(worker, logical: str = "outputs/result.json", generation_id: str = "a" * 32):
    return worker._generation_layout(PurePosixPath(logical), generation_id)


def _load_committed_generation(tmp_path: Path, completion_path: Path):
    completion = CompletionReceipt.from_mapping(load_canonical_json(completion_path))
    result = ResultBundle.from_mapping(
        load_canonical_json(tmp_path.joinpath(*completion.result_path.parts))
    )
    request = JobRequest.from_mapping(load_canonical_json(tmp_path / "request.json"))
    receipt = JobReceipt.from_mapping(load_canonical_json(tmp_path / request.receipt_path))
    validate_completion(tmp_path, request, receipt, result, completion)
    return completion, result


def _load_public_generation_without_validation(
    tmp_path: Path, completion_path: Path,
) -> tuple[CompletionReceipt, ResultBundle, JobRequest, JobReceipt]:
    """Follow the public marker exactly as a fresh result consumer would."""
    completion = CompletionReceipt.from_mapping(load_canonical_json(completion_path))
    result = ResultBundle.from_mapping(
        load_canonical_json(tmp_path.joinpath(*completion.result_path.parts))
    )
    request = JobRequest.from_mapping(load_canonical_json(tmp_path / "request.json"))
    receipt = JobReceipt.from_mapping(load_canonical_json(tmp_path / request.receipt_path))
    return completion, result, request, receipt


def test_generation_layout_uses_fixed_generation_scoped_paths():
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "nested/output.json")

    assert tuple(field.name for field in fields(layout)) == (
        "namespace",
        "generation",
        "result",
        "processor",
        "progress",
        "completion",
    )
    assert layout.namespace == PurePosixPath("nested/output.json.generations")
    assert layout.generation == PurePosixPath("nested/output.json.generations") / ("a" * 32)
    assert layout.result == layout.generation / "result.json"
    assert layout.processor == layout.generation / "result.processor-result.jsonl"
    assert layout.progress == layout.generation / "result.progress.jsonl"
    assert layout.completion == layout.generation / "completion.json"
    first_generation_id = worker._new_generation_id()
    assert type(first_generation_id) is str
    assert first_generation_id != worker._new_generation_id()
    assert re.fullmatch(r"[0-9a-f]{32}", first_generation_id)


@pytest.mark.parametrize(
    ("logical", "generation_id"),
    [
        (PurePosixPath("."), "a" * 32),
        (PurePosixPath(".json"), "a" * 32),
        (PurePosixPath("result"), "a" * 32),
        (PurePosixPath("/result.json"), "a" * 32),
        (PurePosixPath("../result.json"), "a" * 32),
        (PurePosixPath("a/../result.json"), "a" * 32),
        ("result.json", "a" * 32),
        (PurePosixPath("result.json"), "a" * 31),
        (PurePosixPath("result.json"), "a" * 33),
        (PurePosixPath("result.json"), "A" * 32),
        (PurePosixPath("result.json"), "a" * 15 + "/" + "a" * 16),
        (PurePosixPath("result.json"), 1),
    ],
)
def test_generation_layout_rejects_unsafe_inputs(logical, generation_id):
    import backend.app.gpu_worker as worker

    with pytest.raises(worker.WorkerError):
        worker._generation_layout(logical, generation_id)


def test_generation_layout_rejects_builtin_subclasses():
    import backend.app.gpu_worker as worker

    class UnsafePath(PurePosixPath):
        pass

    class UnsafeId(str):
        pass

    with pytest.raises(worker.WorkerError):
        worker._generation_layout(UnsafePath("result.json"), "a" * 32)
    with pytest.raises(worker.WorkerError):
        worker._generation_layout(PurePosixPath("result.json"), UnsafeId("a" * 32))


@pytest.mark.parametrize(
    "raw",
    [
        "valid/result.json",
        "valid/result.txt",
        "café/比赛.json",
        "out/new\nline.json",
        "out/tab\tname.json",
        "out/control\x1fname.json",
        "C:/result.json",
        "out\\result.json",
        "out/null\0result.json",
        "/out/result.json",
        "../out/result.json",
        "~user/result.json",
        f"{'a' * 1020}.json",
    ],
)
def test_generation_path_validation_matches_remote_contract_relative_parity(raw):
    import backend.app.gpu_worker as worker
    import backend.app.remote_contracts as contracts

    value = PurePosixPath(raw)
    try:
        expected = contracts._relative(value, "probe")
    except contracts.RemoteContractError:
        with pytest.raises(worker.WorkerError):
            worker._generation_layout(value, "a" * 32)
    else:
        if not expected.name.endswith(".json"):
            with pytest.raises(worker.WorkerError, match="logical result path is unsafe"):
                worker._generation_layout(value, "a" * 32)
            return
        assert worker._generation_layout(value, "a" * 32).namespace == expected.with_name(
            f"{expected.name}.generations"
        )


@pytest.mark.parametrize(
    "raw",
    [
        "safe/completion.json",
        "safe/new\nline.json",
        "safe/tab\tname.json",
        "safe/control\x1fname.json",
        "C:/completion.json",
        "safe\\completion.json",
        "safe/null\0completion.json",
        "/safe/completion.json",
        "../safe/completion.json",
        "~user/completion.json",
        "a" * 1025,
    ],
)
def test_generation_reservation_path_validation_matches_remote_contract_parity(raw):
    import backend.app.gpu_worker as worker
    import backend.app.remote_contracts as contracts

    value = PurePosixPath(raw)
    layout = _generation_layout(worker)
    try:
        contracts._relative(value, "probe")
    except contracts.RemoteContractError:
        with pytest.raises(worker.WorkerError):
            worker._validate_generation_reservations(
                layout,
                value,
                PurePosixPath("request.json"),
                PurePosixPath("receipt.json"),
                (),
            )
    else:
        worker._validate_generation_reservations(
            layout,
            value,
            PurePosixPath("request.json"),
            PurePosixPath("receipt.json"),
            (),
        )


def test_generation_reservations_reject_path_subclasses_without_coercion():
    import backend.app.gpu_worker as worker

    class UnsafePath(PurePosixPath):
        pass

    with pytest.raises(worker.WorkerError):
        worker._validate_generation_reservations(
            _generation_layout(worker),
            UnsafePath("completion.json"),
            PurePosixPath("request.json"),
            PurePosixPath("receipt.json"),
            (),
        )


def test_generation_layout_rejects_when_derived_artifact_exceeds_contract_path_bound():
    import backend.app.gpu_worker as worker
    import backend.app.remote_contracts as contracts

    logical = PurePosixPath(f"{'a' * 970}.json")
    assert contracts._relative(logical, "logical") == logical
    derived_result = (
        logical.with_name(f"{logical.name}.generations")
        / ("a" * 32)
        / "result.json"
    )
    with pytest.raises(contracts.RemoteContractError):
        contracts._relative(derived_result, "derived")

    with pytest.raises(worker.WorkerError):
        worker._generation_layout(logical, "a" * 32)


def test_generation_reservations_use_path_parts_not_string_prefixes():
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "out/result.json")
    worker._validate_generation_reservations(
        layout,
        PurePosixPath("out/completion.json"),
        PurePosixPath("outside/request.json"),
        PurePosixPath("outside/receipt.json"),
        (PurePosixPath("outside/video.mp4"),),
    )


@pytest.mark.parametrize(
    ("logical", "completion", "sealed"),
    [
        ("out/result.json", "out/result.json", "sealed/input"),
        ("out/result.json", "out", "sealed/input"),
        ("out/result.json", "out/result.json/completion.json", "sealed/input"),
        ("out/result.json", "out/result.json.generations/complete.json", "sealed/input"),
        ("out/result.json", "complete.json", "out"),
        ("out/result.json", "complete.json", "out/result.json.generations"),
        ("out/result.json", "complete.json", "out/result.json.generations/foreign"),
    ],
)
def test_generation_reservations_reject_all_anchor_and_namespace_overlaps(
    logical, completion, sealed,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, logical)
    with pytest.raises(worker.WorkerError, match="overlap|distinct"):
        worker._validate_generation_reservations(
            layout,
            PurePosixPath(completion),
            PurePosixPath("request.json"),
            PurePosixPath("receipt.json"),
            (PurePosixPath(sealed),),
        )


def test_generation_creation_is_exclusive_descriptor_relative_and_preserves_stale_generation(
    tmp_path,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "nested/result.json")
    stale = tmp_path / layout.namespace / ("b" * 32)
    stale.mkdir(parents=True)
    (stale / "foreign").write_bytes(b"preserve")

    owned = worker._create_owned_generation(tmp_path, layout)

    assert (tmp_path / layout.generation).is_dir()
    assert (stale / "foreign").read_bytes() == b"preserve"
    assert owned.layout == layout
    assert (stale / "foreign").read_bytes() == b"preserve"


def test_generation_creation_rejects_existing_exact_generation_without_mutation(tmp_path):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker)
    generation = tmp_path / layout.generation
    generation.mkdir(parents=True)
    marker = generation / "foreign"
    marker.write_bytes(b"preserve")

    with pytest.raises(worker.WorkerError, match="collision"):
        worker._create_owned_generation(tmp_path, layout)

    assert marker.read_bytes() == b"preserve"


@pytest.mark.parametrize("symlink_part", ["outputs", "namespace"])
def test_generation_creation_rejects_symlink_components_without_touching_target(
    tmp_path, symlink_part,
):
    import backend.app.gpu_worker as worker

    outside = tmp_path / "outside"
    outside.mkdir()
    layout = _generation_layout(worker)
    if symlink_part == "outputs":
        (tmp_path / "outputs").symlink_to(outside, target_is_directory=True)
    else:
        (tmp_path / "outputs").mkdir()
        (tmp_path / layout.namespace).symlink_to(outside, target_is_directory=True)

    with pytest.raises((worker.WorkerError, worker.WorkerRollbackIndeterminate)):
        worker._create_owned_generation(tmp_path, layout)

    assert list(outside.iterdir()) == []


def test_generation_creation_fsyncs_each_new_parent_before_opening_child(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    events = []
    real_mkdir = worker.os.mkdir
    real_fsync = worker.os.fsync
    real_open = worker.os.open

    def record_mkdir(name, *args, **kwargs):
        result = real_mkdir(name, *args, **kwargs)
        events.append(("mkdir", str(name), kwargs.get("dir_fd")))
        return result

    def record_fsync(fd):
        events.append(("fsync", fd, None))
        return real_fsync(fd)

    def record_open(name, *args, **kwargs):
        events.append(("open", str(name), kwargs.get("dir_fd")))
        return real_open(name, *args, **kwargs)

    monkeypatch.setattr(worker.os, "mkdir", record_mkdir)
    monkeypatch.setattr(worker.os, "fsync", record_fsync)
    monkeypatch.setattr(worker.os, "open", record_open)
    layout = _generation_layout(worker, "one/two/result.json")
    owned = worker._create_owned_generation(tmp_path, layout)

    mkdir_indexes = [index for index, event in enumerate(events) if event[0] == "mkdir"]
    for index in mkdir_indexes:
        mkdir_event = events[index]
        fsync_index = next(
            candidate for candidate in range(index + 1, len(events))
            if events[candidate][0] == "fsync" and events[candidate][1] == mkdir_event[2]
        )
        child_open_index = next(
            candidate for candidate in range(index + 1, len(events))
            if events[candidate][0] == "open" and events[candidate][1] == mkdir_event[1]
        )
        assert fsync_index < child_open_index
    assert owned.layout == layout


def test_generation_creation_parent_swap_fails_closed_and_retains_owned_attempt(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker)
    real_mkdir = worker.os.mkdir
    swapped = False

    def swap_before_generation(name, *args, **kwargs):
        nonlocal swapped
        if name == layout.generation.name and not swapped:
            swapped = True
            (tmp_path / "outputs").rename(tmp_path / "displaced-outputs")
            (tmp_path / "outputs").mkdir()
            (tmp_path / layout.namespace).mkdir()
        return real_mkdir(name, *args, **kwargs)

    monkeypatch.setattr(worker.os, "mkdir", swap_before_generation)
    with pytest.raises(worker.WorkerRollbackIndeterminate):
        worker._create_owned_generation(tmp_path, layout)

    assert not (tmp_path / layout.generation).exists()
    assert (tmp_path / "displaced-outputs" / layout.namespace.name / layout.generation.name).is_dir()


def test_generation_creation_retains_owned_attempt_when_generation_parent_fsync_fails(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker)
    real_fsync = worker.os.fsync
    destructive_calls = []

    def record_unlink(*args, **kwargs):
        destructive_calls.append("unlink")

    def record_rmdir(*args, **kwargs):
        destructive_calls.append("rmdir")

    def record_chmod(*args, **kwargs):
        destructive_calls.append("chmod")

    def fail_generation_parent_fsync(fd):
        if (tmp_path / layout.generation).is_dir():
            raise OSError("injected generation parent fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(worker.os, "fsync", fail_generation_parent_fsync)
    monkeypatch.setattr(worker.os, "unlink", record_unlink)
    monkeypatch.setattr(worker.os, "rmdir", record_rmdir)
    monkeypatch.setattr(worker.os, "chmod", record_chmod)
    monkeypatch.setattr(worker.os, "fchmod", record_chmod)
    with pytest.raises(worker.WorkerRollbackIndeterminate):
        worker._create_owned_generation(tmp_path, layout)

    assert (tmp_path / layout.generation).is_dir()
    assert destructive_calls == []


def test_generation_reservation_failure_is_pure(tmp_path):
    import backend.app.gpu_worker as worker

    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"preserve")
    before = tuple(tmp_path.iterdir())
    layout = _generation_layout(worker)
    with pytest.raises(worker.WorkerError):
        worker._validate_generation_reservations(
            layout,
            PurePosixPath("outputs/result.json"),
            PurePosixPath("request.json"),
            PurePosixPath("receipt.json"),
            (),
        )
    assert tuple(tmp_path.iterdir()) == before
    assert sentinel.read_bytes() == b"preserve"


def test_generation_creation_fails_closed_when_descriptor_primitives_are_unsupported(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    monkeypatch.setattr(worker, "_GENERATION_DIR_FD_SUPPORTED", False)
    with pytest.raises(worker.WorkerRollbackIndeterminate):
        worker._create_owned_generation(tmp_path, _generation_layout(worker))
    assert tuple(tmp_path.iterdir()) == ()


def _install_generation_handoff_close_failure(worker, monkeypatch, child_name):
    real_open = worker.os.open
    real_close = worker.os.close
    tracked = {}

    def track_open(name, *args, **kwargs):
        descriptor = real_open(name, *args, **kwargs)
        if name == child_name and kwargs.get("dir_fd") is not None and not tracked:
            tracked.update(child=descriptor, prior=kwargs["dir_fd"], raised=False)
        return descriptor

    def close_then_raise(descriptor):
        real_close(descriptor)
        if descriptor == tracked.get("prior") and not tracked["raised"]:
            tracked["raised"] = True
            raise OSError("injected close failure after real close")

    monkeypatch.setattr(worker.os, "open", track_open)
    monkeypatch.setattr(worker.os, "close", close_then_raise)
    return tracked, real_close


def _assert_tracked_descriptor_closed(worker, tracked, real_close):
    assert tracked["raised"]
    try:
        worker.os.fstat(tracked["child"])
    except OSError as error:
        assert error.errno == errno.EBADF
        return
    real_close(tracked["child"])
    pytest.fail("newly opened child descriptor leaked during ownership handoff")


def _install_descriptor_tracker(worker, monkeypatch):
    real_open = worker.os.open
    real_dup = worker.os.dup
    # Reuse of a numeric fd requires its prior lifetime to have been closed. A
    # set therefore lets the final EBADF check cover every lifetime, including
    # descriptors transferred to fdopen and closed by the resulting stream.
    descriptors = set()

    def tracked_open(*args, **kwargs):
        descriptor = real_open(*args, **kwargs)
        descriptors.add(descriptor)
        return descriptor

    def tracked_dup(*args, **kwargs):
        descriptor = real_dup(*args, **kwargs)
        descriptors.add(descriptor)
        return descriptor

    monkeypatch.setattr(worker.os, "open", tracked_open)
    monkeypatch.setattr(worker.os, "dup", tracked_dup)
    return descriptors


def _assert_all_tracked_descriptors_closed(worker, descriptors):
    for descriptor in descriptors:
        try:
            worker.os.fstat(descriptor)
        except OSError as error:
            assert error.errno == errno.EBADF
        else:
            worker.os.close(descriptor)
            pytest.fail(f"tracked descriptor {descriptor} was leaked")


def test_open_generation_namespace_closes_new_child_when_prior_close_raises(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "one/result.json")
    (tmp_path / layout.namespace).mkdir(parents=True)
    root_fd = worker.os.open(tmp_path, worker._publication_open_flags())
    try:
        with monkeypatch.context() as scoped:
            tracked, real_close = _install_generation_handoff_close_failure(
                worker, scoped, layout.namespace.parts[0],
            )
            with pytest.raises(OSError):
                worker._open_generation_namespace(root_fd, layout.namespace)
        _assert_tracked_descriptor_closed(worker, tracked, real_close)
    finally:
        worker.os.close(root_fd)


def test_generation_creation_closes_new_child_when_prior_close_raises(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "one/result.json")
    with monkeypatch.context() as scoped:
        tracked, real_close = _install_generation_handoff_close_failure(
            worker, scoped, layout.namespace.parts[0],
        )
        with pytest.raises(worker.WorkerRollbackIndeterminate):
            worker._create_owned_generation(tmp_path, layout)
    _assert_tracked_descriptor_closed(worker, tracked, real_close)


@pytest.mark.parametrize(
    ("operation", "failure_call"),
    [
        *(("mkdir", index) for index in range(1, 5)),
        *(("fsync", index) for index in range(1, 5)),
        *(("open", index) for index in range(1, 15)),
    ],
)
def test_generation_creation_closes_descriptors_when_each_directory_stage_fails(
    tmp_path, monkeypatch, operation, failure_call,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, "one/two/result.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_bytes(b"preserve")
    calls = 0
    caught = None

    with monkeypatch.context() as scoped:
        descriptors = _install_descriptor_tracker(worker, scoped)
        real_operation = getattr(worker.os, operation)

        def fail_selected_call(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == failure_call:
                raise OSError(f"injected {operation} failure")
            return real_operation(*args, **kwargs)

        scoped.setattr(worker.os, operation, fail_selected_call)
        try:
            worker._create_owned_generation(tmp_path, layout)
        except worker.WorkerRollbackIndeterminate as error:
            caught = error

    assert caught is not None
    assert calls >= failure_call
    assert marker.read_bytes() == b"preserve"
    _assert_all_tracked_descriptors_closed(worker, descriptors)


def test_retained_generation_survives_downstream_failure_without_destructive_calls(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    stale_layout = _generation_layout(worker, generation_id="b" * 32)
    stale = tmp_path / stale_layout.generation
    stale.mkdir(parents=True)
    stale_payload = stale / "result.json"
    stale_payload.write_bytes(b"stale-generation")

    destructive_calls = []

    def forbidden(*args, **kwargs):
        destructive_calls.append(True)
        raise AssertionError("generation lifecycle must not mutate retained failures")

    monkeypatch.setattr(worker.os, "unlink", forbidden)
    monkeypatch.setattr(worker.os, "rmdir", forbidden)
    monkeypatch.setattr(worker.os, "chmod", forbidden)
    monkeypatch.setattr(worker.os, "fchmod", forbidden)

    layout = _generation_layout(worker)
    owned = worker._create_owned_generation(tmp_path, layout)
    partial = tmp_path / layout.result
    partial.write_bytes(b"partial-result")
    try:
        raise worker.WorkerError("simulated downstream failure")
    except worker.WorkerError:
        pass

    assert owned.layout == layout
    assert partial.read_bytes() == b"partial-result"
    assert stale_payload.read_bytes() == b"stale-generation"
    assert destructive_calls == []


def test_owned_generation_validation_preserves_creation_identity_records(tmp_path):
    import backend.app.gpu_worker as worker

    owned = worker._create_owned_generation(tmp_path, _generation_layout(worker))

    assert worker._validate_owned_generation(owned) is owned
    with pytest.raises(worker.WorkerRollbackIndeterminate, match="ownership"):
        worker._validate_owned_generation(replace(owned, generation_identity=(True, 1)))


def test_generation_lifecycle_exposes_no_hot_path_cleanup_api():
    import backend.app.gpu_worker as worker

    assert not hasattr(worker, "_cleanup_owned_generation")
    assert not hasattr(worker, "_rollback_generation_attempt")


def test_worker_commits_only_a_generation_scoped_completion_marker(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    generation_id = "1" * 32
    request_path, logical_result, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    worker.run_worker(request_path, logical_result, completion_path)

    completion, result = _load_committed_generation(tmp_path, completion_path)
    layout = worker._generation_layout(
        PurePosixPath("outputs/result.json"), generation_id,
    )
    generation = tmp_path / layout.generation
    assert not logical_result.exists()
    assert set(path.name for path in generation.iterdir()) == {
        "result.json",
        "result.processor-result.jsonl",
        "result.progress.jsonl",
        "completion.json",
    }
    assert completion.result_path == layout.result
    assert {
        PurePosixPath(result.result["processorResultPath"]),
        PurePosixPath(result.result["progressPath"]),
    } == {layout.processor, layout.progress}
    assert (generation / "completion.json").stat().st_ino == completion_path.stat().st_ino
    assert all(
        not path.exists()
        for path in (
            logical_result.with_name("result.processor-result.jsonl"),
            logical_result.with_name("result.progress.jsonl"),
        )
    )
    assert stat.S_IMODE(generation.stat().st_mode) == 0o500
    assert {
        stat.S_IMODE(path.stat().st_mode) for path in generation.iterdir()
    } == {0o400}


@pytest.mark.parametrize(
    "stage",
    ["processor", "progress", "result", "result-validation", "completion", "seal", "link"],
)
def test_worker_retains_failed_generation_without_public_marker_or_destructive_cleanup(
    tmp_path, monkeypatch, stage,
):
    import backend.app.gpu_worker as worker

    generation_id = "2" * 32
    request_path, logical_result, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    target = {
        "processor": "_write_generation_processor",
        "progress": "_write_generation_progress",
        "result": "_write_generation_json",
        "result-validation": "validate_result",
        "completion": "_write_generation_completion",
        "seal": "_seal_generation_read_only",
        "link": "_commit_completion_link",
    }[stage]
    original = getattr(worker, target)
    calls = []

    def fail_selected(*args, **kwargs):
        calls.append(True)
        if target != "_write_generation_json" or len(calls) == 1:
            raise OSError(stage)
        return original(*args, **kwargs)

    monkeypatch.setattr(worker, target, fail_selected)
    destructive = []
    real_unlink = worker.os.unlink
    real_rmdir = worker.os.rmdir

    def record_unlink(*args, **kwargs):
        destructive.append(("unlink", args, kwargs))
        return real_unlink(*args, **kwargs)

    def record_rmdir(*args, **kwargs):
        destructive.append(("rmdir", args, kwargs))
        return real_rmdir(*args, **kwargs)

    monkeypatch.setattr(worker.os, "unlink", record_unlink)
    monkeypatch.setattr(worker.os, "rmdir", record_rmdir)

    with pytest.raises(OSError):
        worker.run_worker(request_path, logical_result, completion_path)

    generation = tmp_path / worker._generation_layout(
        PurePosixPath("outputs/result.json"), generation_id,
    ).generation
    assert generation.is_dir()
    assert not completion_path.exists()
    assert not logical_result.exists()
    generation_deletes = [
        call for call in destructive
        if "result.json.generations" in repr(call)
        or generation_id in repr(call)
        or any(name in repr(call) for name in (
            "result.processor-result.jsonl", "result.progress.jsonl", "completion.json",
        ))
    ]
    assert generation_deletes == []


def test_worker_retry_leaves_failed_generation_and_commits_only_fresh_generation(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    identifiers = iter(("0" * 32, "1" * 32))
    monkeypatch.setattr(worker, "_new_generation_id", lambda: next(identifiers))
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_progress = worker._write_generation_progress
    attempts = []

    def fail_first(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise OSError("first attempt")
        return real_progress(*args, **kwargs)

    monkeypatch.setattr(worker, "_write_generation_progress", fail_first)
    with pytest.raises(OSError, match="first attempt"):
        worker.run_worker(request_path, logical_result, completion_path)
    worker.run_worker(request_path, logical_result, completion_path)

    completion, _ = _load_committed_generation(tmp_path, completion_path)
    assert "0" * 32 in {
        path.name for path in (tmp_path / "outputs/result.json.generations").iterdir()
    }
    assert completion.result_path.parts[-2] == "1" * 32
    assert not (tmp_path / "outputs/result.json.generations" / ("0" * 32) / "completion.json").exists()


@pytest.mark.parametrize("artifact", ["processor", "progress", "result", "completion"])
@pytest.mark.parametrize("failure", ["write", "flush", "file-fsync", "directory-fsync"])
def test_direct_generation_writer_retains_partial_fixed_file_on_failure(
    tmp_path, monkeypatch, artifact, failure,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="8" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    real_write = worker._write_stream
    real_fsync = worker.os.fsync
    fsync_calls = []
    destructive = []

    if failure == "write":
        def partial_then_fail(handle, payload):
            real_write(handle, payload[:1])
            raise OSError("write")

        monkeypatch.setattr(worker, "_write_stream", partial_then_fail)
    elif failure == "flush":
        monkeypatch.setattr(
            worker,
            "_flush_stream",
            lambda *args: (_ for _ in ()).throw(OSError("flush")),
        )
    else:
        target_call = 1 if failure == "file-fsync" else 2

        def fail_selected_fsync(fd):
            fsync_calls.append(fd)
            if len(fsync_calls) == target_call:
                raise OSError(failure)
            return real_fsync(fd)

        monkeypatch.setattr(worker.os, "fsync", fail_selected_fsync)

    monkeypatch.setattr(worker.os, "unlink", lambda *a, **k: destructive.append("unlink"))
    monkeypatch.setattr(worker.os, "rmdir", lambda *a, **k: destructive.append("rmdir"))
    monkeypatch.setattr(worker.os, "chmod", lambda *a, **k: destructive.append("chmod"))
    monkeypatch.setattr(worker.os, "fchmod", lambda *a, **k: destructive.append("fchmod"))
    event = worker.ProgressEvent(
        1, "job-1", 1, 1, "run", "ok", datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    completion = CompletionReceipt(
        1,
        "job-1",
        "match-1",
        layout.result,
        1,
        "0" * 64,
        COMMIT,
        "1" * 64,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    call = {
        "processor": lambda: worker._write_generation_processor(
            tmp_path, owned, {"rows": [1]},
        ),
        "progress": lambda: worker._write_generation_progress(
            tmp_path, owned, (event,), "job-1",
        ),
        "result": lambda: worker._write_generation_json(
            tmp_path, owned, layout.result, {"value": 1},
        ),
        "completion": lambda: worker._write_generation_completion(
            tmp_path, owned, completion,
        ),
    }[artifact]

    with pytest.raises(worker.WorkerError):
        call()

    target = tmp_path / getattr(layout, artifact)
    assert target.exists()
    assert destructive == []
    assert not tuple((tmp_path / layout.generation).glob("*.tmp"))
    if failure == "write":
        assert target.read_bytes()


def test_generation_validation_rejects_unexpected_entry_and_retains_it(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "9" * 32
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_seal = worker._seal_generation_read_only

    def add_unexpected(root, owned, expected):
        (tmp_path / owned.layout.generation / "unexpected").write_bytes(b"retained")
        return real_seal(root, owned, expected)

    monkeypatch.setattr(worker, "_seal_generation_read_only", add_unexpected)
    with pytest.raises(worker.WorkerRollbackIndeterminate, match="contents"):
        worker.run_worker(request_path, logical_result, completion_path)

    unexpected = (
        tmp_path / "outputs/result.json.generations" / generation_id / "unexpected"
    )
    assert unexpected.read_bytes() == b"retained"
    assert not completion_path.exists()


def test_worker_durably_seals_each_generation_file_before_directories_and_link(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "7" * 32
    fixed_names = {
        "result.processor-result.jsonl",
        "result.progress.jsonl",
        "result.json",
        "completion.json",
    }
    events = []
    names_by_identity = {}
    sealed_file_identities = set()
    generation_identity = {"value": None}
    real_open = worker.os.open
    real_fchmod = worker.os.fchmod
    real_fsync = worker.os.fsync
    real_close = worker.os.close
    real_link = worker.os.link
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def identity(descriptor):
        metadata = worker.os.fstat(descriptor)
        return (metadata.st_dev, metadata.st_ino), metadata.st_mode

    def record_open(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        name = Path(path).name
        file_identity, mode = identity(descriptor)
        if name in fixed_names and stat.S_ISREG(mode):
            names_by_identity[file_identity] = name
            events.append(("file-open", name, file_identity))
        return descriptor

    def record_fchmod(descriptor, mode):
        descriptor_identity, descriptor_mode = identity(descriptor)
        result = real_fchmod(descriptor, mode)
        if stat.S_ISREG(descriptor_mode):
            sealed_file_identities.add(descriptor_identity)
            events.append(("file-fchmod", names_by_identity[descriptor_identity], descriptor_identity))
        elif stat.S_ISDIR(descriptor_mode):
            generation_identity["value"] = descriptor_identity
            events.append(("generation-fchmod", None, descriptor_identity))
        return result

    def record_fsync(descriptor):
        descriptor_identity, descriptor_mode = identity(descriptor)
        if descriptor_identity in sealed_file_identities:
            events.append(("file-fsync", names_by_identity[descriptor_identity], descriptor_identity))
        elif descriptor_identity == generation_identity["value"]:
            events.append(("generation-fsync", None, descriptor_identity))
        elif generation_identity["value"] is not None and stat.S_ISDIR(descriptor_mode):
            events.append(("namespace-fsync", None, descriptor_identity))
        return real_fsync(descriptor)

    def record_close(descriptor):
        try:
            descriptor_identity, _ = identity(descriptor)
        except OSError:
            descriptor_identity = None
        if descriptor_identity in sealed_file_identities:
            events.append(("file-close", names_by_identity[descriptor_identity], descriptor_identity))
        return real_close(descriptor)

    def record_link(*args, **kwargs):
        events.append(("completion-link", None, None))
        return real_link(*args, **kwargs)

    monkeypatch.setattr(worker.os, "open", record_open)
    monkeypatch.setattr(worker.os, "fchmod", record_fchmod)
    monkeypatch.setattr(worker.os, "fsync", record_fsync)
    monkeypatch.setattr(worker.os, "close", record_close)
    monkeypatch.setattr(worker.os, "link", record_link)

    worker.run_worker(request_path, logical_result, completion_path)

    file_fchmods = [event for event in events if event[0] == "file-fchmod"]
    assert {event[1] for event in file_fchmods} == fixed_names
    assert len(file_fchmods) == 4
    for _, name, file_identity in file_fchmods:
        chmod_index = events.index(("file-fchmod", name, file_identity))
        fsync_index = events.index(("file-fsync", name, file_identity))
        close_index = events.index(("file-close", name, file_identity))
        assert any(
            event[0] == "file-open" and event[1] == name and event[2] == file_identity
            for event in events[:chmod_index]
        )
        assert chmod_index < fsync_index < close_index

    final_file_fsync = max(
        index for index, event in enumerate(events) if event[0] == "file-fsync"
    )
    generation_fchmod = next(
        index for index, event in enumerate(events) if event[0] == "generation-fchmod"
    )
    generation_fsync = next(
        index for index, event in enumerate(events) if event[0] == "generation-fsync"
    )
    namespace_fsync = next(
        index for index, event in enumerate(events) if event[0] == "namespace-fsync"
    )
    completion_link = next(
        index for index, event in enumerate(events) if event[0] == "completion-link"
    )
    assert final_file_fsync < generation_fchmod < generation_fsync < namespace_fsync
    assert namespace_fsync < completion_link


@pytest.mark.parametrize("failure_position", [1, 2, 3, 4])
def test_post_fchmod_file_fsync_failure_retains_generation_without_restoration(
    tmp_path, monkeypatch, failure_position,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = f"{failure_position:032x}"
    fixed_names = (
        "result.processor-result.jsonl",
        "result.progress.jsonl",
        "result.json",
        "completion.json",
    )
    fsync_error = OSError("sealed file metadata fsync")
    sealed_file_identities = set()
    all_fchmods = []
    regular_fchmods = []
    regular_fsyncs = []
    destructive = []
    metadata_failure = {"raised": False}
    process_calls = []
    real_fchmod = worker.os.fchmod
    real_fsync = worker.os.fsync
    real_unlink = worker.os.unlink
    real_rmdir = worker.os.rmdir
    real_chmod = worker.os.chmod
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(
        worker,
        "process_video_input",
        lambda *args, **kwargs: process_calls.append(True) or {"rows": [{"Frame_ID": 0}]},
    )

    def descriptor_identity(descriptor):
        metadata = worker.os.fstat(descriptor)
        return (metadata.st_dev, metadata.st_ino), metadata.st_mode

    def track_fchmod(descriptor, mode):
        identity, descriptor_mode = descriptor_identity(descriptor)
        result = real_fchmod(descriptor, mode)
        all_fchmods.append(("file" if stat.S_ISREG(descriptor_mode) else "directory", mode))
        if stat.S_ISREG(descriptor_mode):
            sealed_file_identities.add(identity)
            regular_fchmods.append((identity, mode))
        return result

    def fail_selected_regular_fsync(descriptor):
        identity, _ = descriptor_identity(descriptor)
        if identity in sealed_file_identities:
            regular_fsyncs.append(identity)
            if len(regular_fsyncs) == failure_position:
                metadata_failure["raised"] = True
                raise fsync_error
        return real_fsync(descriptor)

    def record_after_failure(name, operation):
        def record(*args, **kwargs):
            if metadata_failure["raised"]:
                destructive.append(name)
            return operation(*args, **kwargs)

        return record

    monkeypatch.setattr(worker.os, "fchmod", track_fchmod)
    monkeypatch.setattr(worker.os, "fsync", fail_selected_regular_fsync)
    monkeypatch.setattr(worker.os, "unlink", record_after_failure("unlink", real_unlink))
    monkeypatch.setattr(worker.os, "rmdir", record_after_failure("rmdir", real_rmdir))
    monkeypatch.setattr(worker.os, "chmod", record_after_failure("chmod", real_chmod))

    with pytest.raises(worker.WorkerError, match="^generation sealing failed$") as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    generation = tmp_path / "outputs/result.json.generations" / generation_id
    files = [generation / name for name in fixed_names]
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is fsync_error
    assert caught.value.__suppress_context__ is True
    assert process_calls == [True]
    assert len(regular_fsyncs) == failure_position
    assert [mode for _, mode in regular_fchmods] == [0o400] * failure_position
    assert all_fchmods == [("file", 0o400)] * failure_position
    assert [stat.S_IMODE(path.stat().st_mode) for path in files] == (
        [0o400] * failure_position + [0o600] * (4 - failure_position)
    )
    assert files[0].read_bytes() == (
        b'{"metadata":{},"rowCount":1,"schemaVersion":1}\n{"Frame_ID":0}\n'
    )
    assert files[1].read_bytes() == b""
    assert files[2].read_bytes()
    assert files[3].read_bytes()
    assert stat.S_IMODE(generation.stat().st_mode) == 0o700
    assert not completion_path.exists()
    assert not logical_result.exists()
    assert destructive == []


@pytest.mark.parametrize("failure", ["file-mode", "generation-fsync", "namespace-fsync"])
def test_sealing_failure_never_restores_generation_permissions(
    tmp_path, monkeypatch, failure,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="a" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    identities = {
        relative: worker._write_generation_json(tmp_path, owned, relative, {"name": relative.name})
        for relative in (layout.processor, layout.progress, layout.result, layout.completion)
    }
    real_fchmod = worker.os.fchmod
    real_fsync = worker.os.fsync
    modes = []
    fsync_calls = []

    def fail_third(descriptor, mode):
        modes.append(mode)
        if failure == "file-mode" and len(modes) == 3:
            raise OSError("seal")
        return real_fchmod(descriptor, mode)

    def fail_selected_fsync(descriptor):
        metadata = worker.os.fstat(descriptor)
        descriptor_type = (
            "file"
            if stat.S_ISREG(metadata.st_mode)
            else "generation"
            if stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o500
            else "namespace"
        )
        fsync_calls.append(descriptor_type)
        if failure == f"{descriptor_type}-fsync":
            raise OSError("seal")
        return real_fsync(descriptor)

    monkeypatch.setattr(worker.os, "fchmod", fail_third)
    monkeypatch.setattr(worker.os, "fsync", fail_selected_fsync)
    with pytest.raises(worker.WorkerError, match="sealing"):
        worker._seal_generation_read_only(tmp_path, owned, identities)

    if failure == "file-mode":
        assert modes == [0o400, 0o400, 0o400]
    else:
        assert modes == [0o400, 0o400, 0o400, 0o400, 0o500]
        expected_fsyncs = ["file"] * 4 + ["generation"]
        if failure == "namespace-fsync":
            expected_fsyncs.append("namespace")
        assert fsync_calls == expected_fsyncs
    assert (tmp_path / layout.generation).is_dir()


def test_public_hard_link_failure_retains_sealed_generation_without_marker(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "b" * 32
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    link_error = OSError("link")
    monkeypatch.setattr(
        worker.os,
        "link",
        lambda *args, **kwargs: (_ for _ in ()).throw(link_error),
    )
    with pytest.raises(worker.WorkerError, match="publication failed") as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    assert caught.value.__cause__ is link_error
    generation = tmp_path / "outputs/result.json.generations" / generation_id
    assert generation.is_dir()
    assert set(path.name for path in generation.iterdir()) == {
        "result.json", "result.processor-result.jsonl", "result.progress.jsonl", "completion.json",
    }
    assert not completion_path.exists()


def test_link_then_raise_is_indeterminate_and_retains_same_inode_marker(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "e" * 32
    link_error = OSError("link outcome unavailable")
    linked = {"value": False}
    destructive = []
    real_link = worker.os.link
    real_unlink = worker.os.unlink
    real_rmdir = worker.os.rmdir
    real_chmod = worker.os.chmod
    real_fchmod = worker.os.fchmod
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def link_then_raise(*args, **kwargs):
        real_link(*args, **kwargs)
        linked["value"] = True
        raise link_error

    def record_after_link(name, operation):
        def wrapped(*args, **kwargs):
            if linked["value"]:
                destructive.append(name)
            return operation(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(worker.os, "link", link_then_raise)
    monkeypatch.setattr(worker.os, "unlink", record_after_link("unlink", real_unlink))
    monkeypatch.setattr(worker.os, "rmdir", record_after_link("rmdir", real_rmdir))
    monkeypatch.setattr(worker.os, "chmod", record_after_link("chmod", real_chmod))
    monkeypatch.setattr(worker.os, "fchmod", record_after_link("fchmod", real_fchmod))

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    generation = tmp_path / "outputs/result.json.generations" / generation_id
    private_completion = generation / "completion.json"
    assert caught.value.__cause__ is link_error
    assert completion_path.exists()
    assert private_completion.stat().st_ino == completion_path.stat().st_ino
    assert generation.is_dir()
    assert destructive == []


def test_private_completion_source_swap_then_replacement_link_is_indeterminate(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "f" * 32
    link_error = OSError("link outcome unavailable")
    renamed_name = "completion.original.json"
    replacement_bytes = b"replacement-completion\n"
    mutated = {"value": False}
    destructive = []
    real_link = worker.os.link
    real_unlink = worker.os.unlink
    real_rmdir = worker.os.rmdir
    real_chmod = worker.os.chmod
    real_fchmod = worker.os.fchmod
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def replace_source_link_replacement_then_raise(source, target, *args, **kwargs):
        source_dir_fd = kwargs["src_dir_fd"]
        worker.os.fchmod(source_dir_fd, 0o700)
        worker.os.rename(
            source,
            renamed_name,
            src_dir_fd=source_dir_fd,
            dst_dir_fd=source_dir_fd,
        )
        replacement_fd = worker.os.open(
            source,
            worker.os.O_WRONLY
            | worker.os.O_CREAT
            | worker.os.O_EXCL
            | worker.os.O_NOFOLLOW,
            0o400,
            dir_fd=source_dir_fd,
        )
        try:
            assert worker.os.write(replacement_fd, replacement_bytes) == len(replacement_bytes)
            worker.os.fsync(replacement_fd)
        finally:
            worker.os.close(replacement_fd)
        real_link(source, target, *args, **kwargs)
        mutated["value"] = True
        raise link_error

    def record_after_mutation(name, operation):
        def wrapped(*args, **kwargs):
            if mutated["value"]:
                destructive.append(name)
            return operation(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(worker.os, "link", replace_source_link_replacement_then_raise)
    monkeypatch.setattr(worker.os, "unlink", record_after_mutation("unlink", real_unlink))
    monkeypatch.setattr(worker.os, "rmdir", record_after_mutation("rmdir", real_rmdir))
    monkeypatch.setattr(worker.os, "chmod", record_after_mutation("chmod", real_chmod))
    monkeypatch.setattr(worker.os, "fchmod", record_after_mutation("fchmod", real_fchmod))

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    generation = tmp_path / "outputs/result.json.generations" / generation_id
    replacement = generation / "completion.json"
    renamed_original = generation / renamed_name
    assert caught.value.__cause__ is link_error
    assert replacement.read_bytes() == replacement_bytes
    assert completion_path.read_bytes() == replacement_bytes
    assert replacement.stat().st_ino == completion_path.stat().st_ino
    assert renamed_original.exists()
    assert renamed_original.stat().st_ino != replacement.stat().st_ino
    assert generation.is_dir()
    assert destructive == []


def test_link_failure_after_private_completion_source_disappears_is_indeterminate(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "0" * 32
    link_error = OSError("link outcome unavailable")
    renamed_name = "completion.retained.json"
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def rename_source_then_raise(source, _target, *args, **kwargs):
        source_dir_fd = kwargs["src_dir_fd"]
        worker.os.fchmod(source_dir_fd, 0o700)
        worker.os.rename(
            source,
            renamed_name,
            src_dir_fd=source_dir_fd,
            dst_dir_fd=source_dir_fd,
        )
        raise link_error

    monkeypatch.setattr(worker.os, "link", rename_source_then_raise)

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    generation = tmp_path / "outputs/result.json.generations" / generation_id
    assert caught.value.__cause__ is link_error
    assert not (generation / "completion.json").exists()
    assert (generation / renamed_name).exists()
    assert not completion_path.exists()


@pytest.mark.parametrize("source_inspection", ["error", "malformed"])
def test_link_failure_with_uncertain_private_source_stat_is_indeterminate(
    tmp_path, monkeypatch, source_inspection,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    link_error = OSError("link outcome unavailable")
    real_stat = worker.os.stat
    source_dir_fd = {"value": None}
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def fail_link(*args, **kwargs):
        source_dir_fd["value"] = kwargs["src_dir_fd"]
        raise link_error

    def uncertain_source_stat(path, *args, **kwargs):
        if (
            source_dir_fd["value"] is not None
            and kwargs.get("dir_fd") == source_dir_fd["value"]
            and Path(path).name == "completion.json"
            and kwargs.get("follow_symlinks") is False
        ):
            if source_inspection == "error":
                raise OSError("source stat unavailable")
            return type(
                "MalformedSourceStat",
                (),
                {"st_dev": "device", "st_ino": "inode", "st_mode": "mode"},
            )()
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(worker.os, "link", fail_link)
    monkeypatch.setattr(worker.os, "stat", uncertain_source_stat)

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    assert caught.value.__cause__ is link_error
    assert not completion_path.exists()


@pytest.mark.parametrize(
    "unusable_stat",
    [
        object(),
        type("MalformedStat", (), {"st_dev": "device", "st_ino": "inode"})(),
    ],
    ids=["missing-identity", "malformed-identity"],
)
def test_link_failure_with_unusable_destination_stat_is_indeterminate_from_link_error(
    tmp_path, monkeypatch, unusable_stat,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    link_error = OSError("link outcome unavailable")
    real_stat = worker.os.stat
    link_failed = {"value": False}
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    def fail_link(*args, **kwargs):
        link_failed["value"] = True
        raise link_error

    def unusable_destination_stat(path, *args, **kwargs):
        if (
            link_failed["value"]
            and Path(path).name == completion_path.name
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
        ):
            return unusable_stat
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(worker.os, "link", fail_link)
    monkeypatch.setattr(worker.os, "stat", unusable_destination_stat)

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    assert caught.value.__cause__ is link_error
    assert not completion_path.exists()


def test_missing_generation_link_capability_fails_before_processing_or_mutation(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    process_calls = []
    monkeypatch.setattr(worker, "_GENERATION_DIR_FD_SUPPORTED", False)
    monkeypatch.setattr(
        worker,
        "process_video_input",
        lambda *args, **kwargs: process_calls.append(True) or {"rows": [{"Frame_ID": 0}]},
    )

    with pytest.raises(worker.WorkerRollbackIndeterminate, match="generation lifecycle"):
        worker.run_worker(request_path, logical_result, completion_path)

    assert process_calls == []
    assert not (tmp_path / "outputs/result.json.generations").exists()
    assert not completion_path.exists()


def test_generation_creation_does_not_leak_descriptors(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    created = []
    with monkeypatch.context() as scoped:
        descriptors = _install_descriptor_tracker(worker, scoped)
        for index in range(40):
            layout = _generation_layout(worker, generation_id=f"{index:032x}")
            created.append(worker._create_owned_generation(tmp_path, layout))

    assert [owned.layout.generation.name for owned in created] == [
        f"{index:032x}" for index in range(40)
    ]
    assert descriptors
    _assert_all_tracked_descriptors_closed(worker, descriptors)


def _install_tempdir_exit_failure(worker, monkeypatch, error: Exception) -> None:
    real_temporary_directory = worker.TemporaryDirectory

    class ExitFailureTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            self.inner = real_temporary_directory(*args, **kwargs)

        def __enter__(self):
            return self.inner.__enter__()

        def __exit__(self, exc_type, exc_value, traceback):
            self.inner.__exit__(exc_type, exc_value, traceback)
            raise error

    monkeypatch.setattr(worker, "TemporaryDirectory", ExitFailureTemporaryDirectory)


def _relocate_sealed_input(
    root: Path,
    request_path: Path,
    role: str,
    artifact_index: int,
    destination: Path,
) -> tuple[Path, tuple[Path, ...]]:
    request = load_canonical_json(request_path)
    receipt_path = root / request["receiptPath"]
    receipt = load_canonical_json(receipt_path)

    if role == "receipt":
        destination.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.replace(destination)
        receipt_path = destination
        request["receiptPath"] = destination.relative_to(root).as_posix()
    else:
        matching = [item for item in receipt["files"] if item["role"] == role]
        entry = matching[artifact_index]
        source = root / entry["relativePath"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        entry["relativePath"] = destination.relative_to(root).as_posix()
        if role == "job_request":
            request_path = destination
        elif role == "input_video":
            request["inputVideoPath"] = entry["relativePath"]

    request_bytes = canonical_json_bytes(request)
    request_path.write_bytes(request_bytes)
    request_entry = next(item for item in receipt["files"] if item["role"] == "job_request")
    request_entry.update(_entry("job_request", request_path.relative_to(root).as_posix(), request_bytes))
    receipt["jobRequestSha256"] = request_entry["sha256"]
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    sealed_paths = (receipt_path, *(root / item["relativePath"] for item in receipt["files"]))
    return request_path, sealed_paths


@pytest.mark.parametrize(
    ("role", "artifact_index"),
    [
        ("job_request", 0),
        ("receipt", 0),
        ("manifest", 0),
        ("evidence", 0),
        ("input_video", 0),
        ("source_archive", 0),
        ("runtime_artifact", 0),
        ("runtime_artifact", 1),
        ("runtime_artifact", 2),
        ("runtime_artifact", 3),
        ("runtime_artifact", 4),
    ],
    ids=[
        "request", "receipt", "manifest", "evidence", "video", "source-archive",
        "primary-model", "auxiliary-model", "baseline-reference", "truth-seed", "anchor-seed",
    ],
)
@pytest.mark.parametrize(
    "output_index",
    [0, 1],
    ids=["logical-result", "completion"],
)
def test_worker_output_overlap_preserves_every_sealed_input(
    tmp_path,
    monkeypatch,
    role,
    artifact_index,
    output_index,
):
    import backend.app.gpu_worker as worker

    request_path, _, _ = _bundle(tmp_path, all_runtime_artifacts=True)
    result_path = tmp_path / "result.json"
    completion_path = tmp_path / "completion.json"
    destination = _publication_paths(result_path, completion_path)[output_index]
    request_path, sealed_paths = _relocate_sealed_input(
        tmp_path, request_path, role, artifact_index, destination,
    )
    before = {path: path.read_bytes() for path in sealed_paths}
    process_calls = []
    monkeypatch.setattr(
        worker,
        "process_video_input",
        lambda *args, **kwargs: process_calls.append(1) or {"rows": [{"Frame_ID": 0}]},
    )

    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)

    assert process_calls == []
    assert {path: path.read_bytes() for path in sealed_paths} == before


@pytest.mark.parametrize(
    "completion_alias",
    [
        "outputs/result.json",
        "outputs/result.json.generations",
        "outputs/result.json.generations/child",
    ],
    ids=["logical-result", "generation-namespace", "generation-child"],
)
def test_worker_output_overlap_rejects_collisions_among_publications_before_cleanup(
    tmp_path,
    monkeypatch,
    completion_alias,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, _ = _bundle(tmp_path)
    completion_path = tmp_path / completion_alias
    publication_paths = set(_publication_paths(result_path, completion_path.resolve(strict=False)))
    for index, path in enumerate(publication_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"publication-{index}".encode())
    before = {path: path.read_bytes() for path in publication_paths}
    process_calls = []
    monkeypatch.setattr(
        worker,
        "process_video_input",
        lambda *args, **kwargs: process_calls.append(1) or {"rows": [{"Frame_ID": 0}]},
    )

    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)

    assert process_calls == []
    assert {path: path.read_bytes() for path in publication_paths} == before


def test_worker_malformed_preserves_all_preexisting_publications(tmp_path):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    request_path.write_bytes(b"malformed-request")
    publication_paths = _publication_paths(result_path, completion_path)
    for index, path in enumerate(publication_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original-{index}".encode())
    before = {path: path.read_bytes() for path in publication_paths}

    with pytest.raises(RemoteContractError):
        worker.run_worker(request_path, result_path, completion_path)

    assert {path: path.read_bytes() for path in publication_paths} == before


def test_worker_malformed_preserves_publications_when_receipt_schema_is_invalid(tmp_path):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    receipt_path = tmp_path / "sealed/receipt.json"
    receipt = load_canonical_json(receipt_path)
    receipt["schemaVersion"] = 2
    receipt_path.write_bytes(canonical_json_bytes(receipt))
    publication_paths = _publication_paths(result_path, completion_path)
    for index, path in enumerate(publication_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original-{index}".encode())
    before = {path: path.read_bytes() for path in publication_paths}

    with pytest.raises(Exception, match="schemaVersion"):
        worker.run_worker(request_path, result_path, completion_path)

    assert {path: path.read_bytes() for path in publication_paths} == before


def test_worker_malformed_preserves_publications_when_receipt_file_validation_fails(tmp_path):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    (tmp_path / "inputs/match.mp4").write_bytes(b"tampered-after-sealing")
    publication_paths = _publication_paths(result_path, completion_path)
    for index, path in enumerate(publication_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original-{index}".encode())
    before = {path: path.read_bytes() for path in publication_paths}

    with pytest.raises(Exception, match="stream (size|digest) mismatch"):
        worker.run_worker(request_path, result_path, completion_path)

    assert {path: path.read_bytes() for path in publication_paths} == before


def test_gpu_worker_module_imports():
    from backend.app.gpu_worker import run_worker

    assert callable(run_worker)


@pytest.mark.parametrize(
    "payload",
    [
        {"autoHomography": True},
        {
            "attackDirection": "right_to_left",
            "manualHomographyPoints": [{"x": "1.5", "y": 2}],
            "myTeamCluster": "3",
            "llmProvider": "cloud",
            "autoHomography": False,
        },
    ],
)
def test_worker_match_config_validation_matches_authoritative_schema(payload):
    import backend.app.gpu_worker as worker
    from backend.app.schemas import MatchConfig

    assert worker._match_config(payload) == MatchConfig.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"attackDirection": "sideways"},
        {"manualHomographyPoints": [{"x": "not-a-number", "y": 2}]},
    ],
)
def test_worker_match_config_rejects_every_authoritative_schema_failure(payload):
    import backend.app.gpu_worker as worker
    from backend.app.schemas import MatchConfig

    with pytest.raises(ValidationError):
        MatchConfig.model_validate(payload)
    with pytest.raises(worker.WorkerError, match="match config"):
        worker._match_config(payload)


def test_worker_match_config_preserves_worker_unknown_field_rejection():
    import backend.app.gpu_worker as worker

    with pytest.raises(worker.WorkerError, match="unknown fields"):
        worker._match_config({"unknown": True})


def test_worker_validates_then_processes_once_with_exact_local_inputs(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    calls = []

    def process(video_path, config, **kwargs):
        calls.append((video_path, config, kwargs, Path(kwargs["model_path"]).read_bytes()))
        kwargs["progress_callback"]({"progress": 10, "stage": "load", "message": "starting"})
        kwargs["progress_callback"]({"progress": 100, "stage": "finish", "message": "complete"})
        return {"rows": [{"Frame_ID": 1}], "score": 0.5}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)

    assert len(calls) == 1
    video_path, config, kwargs, model_bytes = calls[0]
    assert video_path != tmp_path / "inputs/match.mp4"
    assert not video_path.exists()
    assert config.autoHomography is True
    assert kwargs["match_id"] == "match-1" and kwargs["job_id"] == "job-1"
    assert model_bytes == b"sealed-model"
    assert kwargs["primary_model_path"] == kwargs["model_path"]
    assert not Path(kwargs["model_path"]).exists()
    assert not result_path.exists()
    request = JobRequest.from_mapping(load_canonical_json(request_path))
    receipt = JobReceipt.from_mapping(load_canonical_json(tmp_path / request.receipt_path))
    completion = CompletionReceipt.from_mapping(load_canonical_json(completion_path))
    result = ResultBundle.from_mapping(
        load_canonical_json(tmp_path / completion.result_path)
    )
    generation = completion.result_path.parent.as_posix()
    assert result.result == {
        "processorResultPath": f"{generation}/result.processor-result.jsonl",
        "processorResultFormat": "jsonl-v1",
        "processorRowCount": 1,
        "progressPath": f"{generation}/result.progress.jsonl",
        "progressEventCount": 2,
    }
    processor_lines = (tmp_path / result.result["processorResultPath"]).read_bytes().splitlines()
    assert json.loads(processor_lines[0])["metadata"]["score"] == 0.5
    progress_lines = (tmp_path / result.result["progressPath"]).read_bytes().splitlines()
    assert [json.loads(line)["sequence"] for line in progress_lines] == [1, 2]
    assert len(result.artifacts) == 2
    validate_completion(tmp_path, request, receipt, result, completion)


def test_worker_isolates_video_without_allocating_a_second_copy(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    original_video_path = tmp_path / "inputs/match.mp4"
    original_identity = original_video_path.stat().st_ino
    captured = {}

    def process(video_path, config, **kwargs):
        captured["identity"] = Path(video_path).stat().st_ino
        captured["original_exists"] = original_video_path.exists()
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)

    assert captured == {
        "identity": original_identity,
        "original_exists": False,
    }
    assert original_video_path.read_bytes() == b"video"


def test_worker_processes_verified_video_snapshot_when_bundle_video_changes(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    original_video_path = tmp_path / "inputs/match.mp4"
    real_prepare = worker._prepare_runtime

    def prepare(*args, **kwargs):
        result = real_prepare(*args, **kwargs)
        original_video_path.write_bytes(b"replacement-after-validation")
        return result

    captured = {}

    def process(video_path, config, **kwargs):
        captured["path"] = video_path
        captured["bytes"] = video_path.read_bytes()
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "_prepare_runtime", prepare)
    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)
    assert captured["bytes"] == b"video"
    assert captured["path"] != original_video_path
    assert not captured["path"].exists()


def _production_processor_result(row_count: int = 10_000) -> dict[str, object]:
    return {
        "matchId": "match-1",
        "fps": 25.0,
        "frameCount": row_count,
        "durationSeconds": row_count / 25.0,
        "trackColors": {"home": "#0b4dbb", "away": "#df2020", "ball": "#ffffff"},
        "rows": [
            {
                "Frame_ID": index,
                "Track_ID": index % 23,
                "Class_ID": 0 if index % 23 else 32,
                "Confidence": 0.875,
                "X": float(index % 1920),
                "Y": float(index % 1080),
                "Team": "home" if index % 2 else "away",
                "Observed": index % 7 != 0,
            }
            for index in range(row_count)
        ],
    }


def _canonical_processor_bytes(value: object) -> bytes:
    metadata = dict(value)
    rows = metadata.pop("rows")
    return canonical_json_bytes(
        {"schemaVersion": 1, "rowCount": len(rows), "metadata": metadata},
    ) + b"".join(canonical_json_bytes(row) for row in rows)


def test_processor_v2_writes_metadata_then_exact_canonical_rows():
    import backend.app.gpu_worker as worker

    row_1 = {"Frame_ID": 1, "label": "mål"}
    row_2 = {"Frame_ID": 2, "label": "pass"}
    chunks, row_count = worker._processor_result_v2_chunks(
        {"rows": [row_1, row_2], "trackColors": {}},
    )

    assert row_count == 2
    assert b"".join(chunks) == (
        canonical_json_bytes(
            {"schemaVersion": 1, "rowCount": 2, "metadata": {"trackColors": {}}},
        )
        + canonical_json_bytes(row_1)
        + canonical_json_bytes(row_2)
    )


@pytest.mark.parametrize(
    ("limit_name", "line_value", "expected_line"),
    [
        pytest.param(
            "MAX_PROCESSOR_METADATA_LINE_BYTES",
            {"schemaVersion": 1, "rowCount": 1, "metadata": {"label": "mål"}},
            '{"metadata":{"label":"mål"},"rowCount":1,"schemaVersion":1}\n'.encode("utf-8"),
            id="metadata",
        ),
        pytest.param(
            "MAX_PROCESSOR_ROW_LINE_BYTES",
            {"Frame_ID": 1, "label": "mål"},
            '{"Frame_ID":1,"label":"mål"}\n'.encode("utf-8"),
            id="row",
        ),
    ],
)
def test_processor_v2_lines_accept_exact_utf8_limit_and_reject_one_more(
    monkeypatch,
    limit_name,
    line_value,
    expected_line,
):
    import backend.app.gpu_worker as worker

    row = {"Frame_ID": 1, "label": "mål"}
    payload = (
        '{"metadata":{"label":"mål"},"rowCount":1,"schemaVersion":1}\n'.encode("utf-8")
        + '{"Frame_ID":1,"label":"mål"}\n'.encode("utf-8")
    )
    assert expected_line.endswith(b"\n")
    assert len(expected_line) > len(expected_line.decode("utf-8"))
    assert worker._processor_json_line(line_value, maximum=len(expected_line)) == expected_line

    monkeypatch.setattr(worker, limit_name, len(expected_line))
    chunks, row_count = worker._processor_result_v2_chunks({"rows": [row], "label": "mål"})
    assert row_count == 1
    assert b"".join(chunks) == payload

    monkeypatch.setattr(worker, limit_name, len(expected_line) - 1)
    with pytest.raises(worker.WorkerError, match="size limit"):
        b"".join(worker._processor_result_v2_chunks({"rows": [row], "label": "mål"})[0])


def test_worker_v2_failure_never_publishes_completion(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="f" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_BYTES", 128)

    with pytest.raises(worker.WorkerError, match="size limit"):
        worker._write_generation_processor(
            tmp_path,
            owned,
            {"rows": [{"Frame_ID": 0, "payload": "x" * 256}]},
        )

    assert not (tmp_path / "completion.json").exists()


def test_generation_processor_is_canonical_bounded_and_completes(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    processor_result = _production_processor_result()
    expected = _canonical_processor_bytes(processor_result)
    measured_layout = _generation_layout(worker, generation_id="1" * 32)
    measured_generation = worker._create_owned_generation(tmp_path, measured_layout)
    tracemalloc.start()
    measured_entry = worker._write_generation_processor(
        tmp_path, measured_generation, processor_result,
    )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert measured_entry.size_bytes == len(expected)
    assert measured_entry.sha256 == hashlib.sha256(expected).hexdigest()
    assert (tmp_path / measured_entry.relative_path).read_bytes() == expected

    def return_processor_result(*args, **kwargs):
        tracemalloc.start()
        return processor_result

    monkeypatch.setattr(worker, "process_video_input", return_processor_result)
    worker.run_worker(request_path, result_path, completion_path)
    _, publication_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    completion = CompletionReceipt.from_mapping(load_canonical_json(completion_path))
    result = ResultBundle.from_mapping(load_canonical_json(tmp_path / completion.result_path))
    processor_path = tmp_path / result.result["processorResultPath"]
    assert processor_path.read_bytes() == expected
    assert hashlib.sha256(processor_path.read_bytes()).hexdigest() == hashlib.sha256(expected).hexdigest()
    # Streaming should need only encoder/write buffers, not a second artifact-sized byte snapshot.
    assert peak < int(len(expected) * 0.90)
    assert publication_peak < int(len(expected) * 0.90)
    request = JobRequest.from_mapping(load_canonical_json(request_path))
    receipt = JobReceipt.from_mapping(load_canonical_json(tmp_path / request.receipt_path))
    validate_completion(tmp_path, request, receipt, result, completion)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_streamed_processor_graph_rejects_nonfinite_numbers(number):
    import backend.app.gpu_worker as worker

    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result({"value": number})


def test_streamed_processor_graph_rejects_cycles():
    import backend.app.gpu_worker as worker

    value: dict[str, object] = {}
    value["cycle"] = value
    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(type("HostileDict", (dict,), {})(rows=[]), id="dict-subclass"),
        pytest.param({"rows": type("HostileList", (list,), {})([])}, id="list-subclass"),
        pytest.param(type("ProtocolMapping", (Mapping,), {
            "__getitem__": lambda self, key: (_ for _ in ()).throw(AssertionError("touched")),
            "__iter__": lambda self: (_ for _ in ()).throw(AssertionError("touched")),
            "__len__": lambda self: 1,
        })(), id="mapping-protocol"),
    ],
)
def test_streamed_processor_graph_accepts_only_exact_builtin_containers(value):
    import backend.app.gpu_worker as worker

    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result(value)


def test_streamed_processor_graph_enforces_depth_nodes_and_text_ceilings(monkeypatch):
    import backend.app.gpu_worker as worker

    nested: object = None
    for _ in range(worker.MAX_PROCESSOR_RESULT_DEPTH + 1):
        nested = [nested]
    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result({"nested": nested})
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_NODES", 5)
    worker._validate_processor_result({"rows": [1, 2, 3]})
    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result({"rows": [1, 2, 3, 4]})
    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result({"k" * (worker.MAX_PROCESSOR_RESULT_KEY_CHARS + 1): 1})
    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result({"value": "x" * (worker.MAX_PROCESSOR_RESULT_STRING_CHARS + 1)})


def test_streamed_processor_node_capacity_covers_full_match_with_headroom(monkeypatch):
    import backend.app.gpu_worker as worker

    full_match_rows = 5 * (90 * 60) * 23
    basic_row_nodes = 1 + 11
    plausible_base_nodes = 2 + full_match_rows * basic_row_nodes
    assert full_match_rows == 621_000
    assert plausible_base_nodes == 7_452_002
    assert worker.MAX_PROCESSOR_RESULT_NODES == 20_000_000
    assert worker.MAX_PROCESSOR_RESULT_NODES >= plausible_base_nodes * 2 + 1_000_000

    representative_rows = 50_000
    row = {f"field{index}": index for index in range(11)}
    value = {"rows": [dict(row) for _ in range(representative_rows)]}
    exact_nodes = 2 + representative_rows * basic_row_nodes
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_NODES", exact_nodes)
    worker._validate_processor_result(value)
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_NODES", exact_nodes - 1)
    with pytest.raises(worker.WorkerError, match="complexity"):
        worker._validate_processor_result(value)


@pytest.mark.parametrize(
    "value",
    [
        {"apiKey": "secret"},
        {"nested": [{"authorizationHeader": "Bearer secret"}]},
        {"message": "password=secret"},
    ],
)
def test_streamed_processor_graph_rejects_credentials(value):
    import backend.app.gpu_worker as worker

    with pytest.raises(worker.WorkerError, match="processor result"):
        worker._validate_processor_result(value)


def test_generation_processor_enforces_exact_byte_boundary(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    value = {"rows": [{"Frame_ID": 1}, {"Frame_ID": 2}, {"Frame_ID": 3}]}
    expected = _canonical_processor_bytes(value)
    layout = _generation_layout(worker, generation_id="2" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_BYTES", len(expected))
    entry = worker._write_generation_processor(tmp_path, owned, value)
    assert entry.size_bytes == len(expected)
    assert entry.sha256 == hashlib.sha256(expected).hexdigest()
    assert (tmp_path / entry.relative_path).read_bytes() == expected
    limited_layout = _generation_layout(worker, generation_id="3" * 32)
    limited_owned = worker._create_owned_generation(tmp_path, limited_layout)
    monkeypatch.setattr(worker, "MAX_PROCESSOR_RESULT_BYTES", len(expected) - 1)
    with pytest.raises(worker.WorkerError, match="size"):
        worker._write_generation_processor(tmp_path, limited_owned, value)
    assert (tmp_path / limited_layout.processor).exists()
    assert not tuple((tmp_path / limited_layout.generation).glob("*.tmp"))


def test_generation_processor_uses_canonical_rows_and_handles_partial_writes(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    calls = []
    real_dumps = worker.json.dumps

    def record_dumps(value, **kwargs):
        calls.append(value)
        return real_dumps(value, **kwargs)

    monkeypatch.setattr(worker.json, "dumps", record_dumps)
    real_write = worker._write_stream
    write_calls = []

    def short_write(handle, payload):
        write_calls.append(len(payload))
        partial = payload[:max(1, len(payload) // 2)]
        return real_write(handle, partial)

    monkeypatch.setattr(worker, "_write_stream", short_write)
    value = {"rows": [{"id": 1, "label": "mål"}]}
    layout = _generation_layout(worker, generation_id="4" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    entry = worker._write_generation_processor(tmp_path, owned, value)
    assert calls == [
        {"schemaVersion": 1, "rowCount": 1, "metadata": {}},
        {"id": 1, "label": "mål"},
    ]
    assert len(write_calls) > 1
    assert (tmp_path / entry.relative_path).read_bytes() == _canonical_processor_bytes(value)


def test_generation_json_writer_rejects_overreported_writes_and_retains_file(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    monkeypatch.setattr(worker, "_write_stream", lambda _handle, payload: len(payload) + 1)
    layout = _generation_layout(worker, generation_id="5" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    with pytest.raises(worker.WorkerError, match="write failed"):
        worker._write_generation_json(tmp_path, owned, layout.result, {"rows": [{"Frame_ID": 0}]})
    assert (tmp_path / layout.result).exists()
    assert not tuple((tmp_path / layout.generation).glob("*.tmp"))


def test_generation_writer_namespace_swap_is_confined_and_fails_closed(
    tmp_path,
    monkeypatch,
):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="6" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    namespace = tmp_path / layout.namespace
    detached_namespace = tmp_path / "detached-generations"
    replacement_generation = namespace / layout.generation.name
    outside_payload = replacement_generation / layout.processor.name
    real_fsync = worker.os.fsync
    fsync_calls = []

    def swap_namespace_after_artifact_durability(descriptor):
        fsync_calls.append(descriptor)
        result = real_fsync(descriptor)
        if len(fsync_calls) == 2:
            namespace.rename(detached_namespace)
            replacement_generation.mkdir(parents=True)
            outside_payload.write_bytes(b"outside")
        return result

    monkeypatch.setattr(worker.os, "fsync", swap_namespace_after_artifact_durability)
    with pytest.raises(worker.WorkerRollbackIndeterminate, match="indeterminate"):
        worker._write_generation_processor(tmp_path, owned, {"rows": [{"Frame_ID": 1}]})

    expected = _canonical_processor_bytes({"rows": [{"Frame_ID": 1}]})
    assert len(fsync_calls) == 2
    assert outside_payload.read_bytes() == b"outside"
    assert (
        detached_namespace / layout.generation.name / layout.processor.name
    ).read_bytes() == expected


@pytest.mark.parametrize("binding_is_current", [True, False], ids=["success", "binding-failure"])
def test_generation_writer_closes_descriptors_and_retains_bytes(
    tmp_path, monkeypatch, binding_is_current,
):
    import backend.app.gpu_worker as worker

    owned_generations = [
        worker._create_owned_generation(
            tmp_path,
            _generation_layout(worker, generation_id=f"{index:032x}"),
        )
        for index in range(40)
    ]
    expected = _canonical_processor_bytes({"rows": [{"Frame_ID": 0}]})
    entries = []
    errors = []
    with monkeypatch.context() as scoped:
        descriptors = _install_descriptor_tracker(worker, scoped)
        if not binding_is_current:
            scoped.setattr(
                worker,
                "_generation_binding_is_current",
                lambda *args: False,
            )
        for owned in owned_generations:
            try:
                entries.append(
                    worker._write_generation_processor(tmp_path, owned, {"rows": [{"Frame_ID": 0}]})
                )
            except worker.WorkerRollbackIndeterminate as error:
                errors.append(error)

    if binding_is_current:
        assert len(entries) == 40
        assert errors == []
    else:
        assert entries == []
        assert len(errors) == 40
        assert all("binding" in str(error) for error in errors)
    assert all(
        (tmp_path / owned.layout.processor).read_bytes() == expected
        for owned in owned_generations
    )
    assert descriptors
    _assert_all_tracked_descriptors_closed(worker, descriptors)


def test_generation_fixed_name_symlink_collision_never_touches_target(tmp_path):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="7" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    outside = tmp_path / "outside-bytes"
    outside.write_bytes(b"outside")
    collision = tmp_path / layout.processor
    collision.symlink_to(outside)

    with pytest.raises(worker.WorkerError, match="write failed"):
        worker._write_generation_processor(tmp_path, owned, {"rows": [{"Frame_ID": 0}]})

    assert outside.read_bytes() == b"outside"
    assert collision.is_symlink()


def test_generation_fixed_name_foreign_file_collision_never_clobbers_bytes(tmp_path):
    import backend.app.gpu_worker as worker

    layout = _generation_layout(worker, generation_id="b" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    collision = tmp_path / layout.processor
    collision.write_bytes(b"foreign")

    with pytest.raises(worker.WorkerError, match="write failed"):
        worker._write_generation_processor(tmp_path, owned, {"rows": [{"Frame_ID": 0}]})

    assert collision.read_bytes() == b"foreign"


def test_committed_generation_mutation_is_detected_by_later_consumer_validation(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    worker.run_worker(request_path, result_path, completion_path)
    completion, result = _load_committed_generation(tmp_path, completion_path)
    processor = tmp_path / result.result["processorResultPath"]
    processor.chmod(0o600)
    with processor.open("r+b") as handle:
        original = handle.read(1)
        handle.seek(0)
        handle.write(bytes([original[0] ^ 1]))
    request = JobRequest.from_mapping(load_canonical_json(request_path))
    receipt = JobReceipt.from_mapping(load_canonical_json(tmp_path / request.receipt_path))
    with pytest.raises(RemoteContractError, match="digest mismatch"):
        validate_completion(tmp_path, request, receipt, result, completion)


@pytest.mark.parametrize("file_kind", ["result", "processor", "progress"])
@pytest.mark.parametrize(
    ("mutation", "replacement", "expected_error"),
    [
        ("same-size replacement", b"same", "digest mismatch"),
        ("truncation", b"short", "size mismatch"),
        ("growth", b"long", "size mismatch"),
    ],
)
def test_fresh_consumer_rejects_each_committed_file_mutation(
    tmp_path, monkeypatch, file_kind, mutation, replacement, expected_error,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)

    def process(*args, **kwargs):
        kwargs["progress_callback"](
            {"progress": 100, "stage": "finish", "message": "complete"}
        )
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)
    completion, result, _, _ = _load_public_generation_without_validation(
        tmp_path, completion_path,
    )
    targets = {
        "result": tmp_path.joinpath(*completion.result_path.parts),
        "processor": tmp_path / result.result["processorResultPath"],
        "progress": tmp_path / result.result["progressPath"],
    }
    substitutions = {
        "result": {
            b"same": (b'"jobId":"job-1"', b'"jobId":"job-2"'),
            b"short": (b'"jobId":"job-1"', b'"jobId":"j"'),
            b"long": (b'"jobId":"job-1"', b'"jobId":"job-100"'),
        },
        "processor": {
            b"same": (b'"rowCount"', b'"rowXount"'),
            b"short": (b'"Frame_ID"', b'"F"'),
            b"long": (b'"Frame_ID"', b'"Frame_Identifier"'),
        },
        "progress": {
            b"same": (b'"message":"complete"', b'"message":"changed!"'),
            b"short": (b'"message":"complete"', b'"message":"done"'),
            b"long": (b'"message":"complete"', b'"message":"completed-later"'),
        },
    }
    target = targets[file_kind]
    original = target.read_bytes()
    old, new = substitutions[file_kind][replacement]
    mutated = original.replace(old, new, 1)
    assert mutated != original
    if mutation == "same-size replacement":
        assert len(mutated) == len(original)
    elif mutation == "truncation":
        assert len(mutated) < len(original)
    else:
        assert len(mutated) > len(original)
    target.chmod(0o600)
    target.write_bytes(mutated)

    fresh_completion, fresh_result, request, receipt = (
        _load_public_generation_without_validation(tmp_path, completion_path)
    )
    with pytest.raises(RemoteContractError, match=expected_error):
        validate_completion(
            tmp_path, request, receipt, fresh_result, fresh_completion,
        )


@pytest.mark.parametrize(
    ("namespace", "generation"),
    [
        ("outputs/other.json.generations", "1" * 32),
        ("outputs/result.json.generations", "2" * 32),
    ],
    ids=["artifact-path-binding", "generation-identifier"],
)
def test_fresh_consumer_rejects_changed_committed_result_binding(
    tmp_path, monkeypatch, namespace, generation,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    worker.run_worker(request_path, result_path, completion_path)
    completion, result, _, _ = _load_public_generation_without_validation(
        tmp_path, completion_path,
    )
    result_mapping = result.to_mapping()
    processor_path = f"{namespace}/{generation}/result.processor-result.jsonl"
    progress_path = f"{namespace}/{generation}/result.progress.jsonl"
    result_mapping["result"]["processorResultPath"] = processor_path
    result_mapping["result"]["progressPath"] = progress_path
    result_mapping["artifacts"][0]["relativePath"] = processor_path
    result_mapping["artifacts"][1]["relativePath"] = progress_path
    committed_result = tmp_path.joinpath(*completion.result_path.parts)
    committed_result.chmod(0o600)
    committed_result.write_bytes(canonical_json_bytes(result_mapping))

    fresh_completion, fresh_result, request, receipt = (
        _load_public_generation_without_validation(tmp_path, completion_path)
    )
    with pytest.raises(RemoteContractError, match="share one generation"):
        validate_completion(
            tmp_path, request, receipt, fresh_result, fresh_completion,
        )


def test_fresh_consumer_rejects_completion_copied_from_another_job(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    other_root = tmp_path / "other-job"
    other_root.mkdir()
    other_request, other_result, other_completion = _bundle(other_root)
    _set_bundle_job_id(other_root, "job-2")
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    generation_ids = iter(["3" * 32, "3" * 32])
    monkeypatch.setattr(worker, "_new_generation_id", lambda: next(generation_ids))
    worker.run_worker(request_path, result_path, completion_path)
    worker.run_worker(other_request, other_result, other_completion)
    completion_path.chmod(0o600)
    completion_path.write_bytes(other_completion.read_bytes())

    completion, result, request, receipt = _load_public_generation_without_validation(
        tmp_path, completion_path,
    )
    with pytest.raises(RemoteContractError, match="completion identity mismatch"):
        validate_completion(tmp_path, request, receipt, result, completion)


def test_concurrent_progress_replacement_uses_one_open_descriptor_snapshot(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)

    def process(*args, **kwargs):
        for index in range(1_000):
            kwargs["progress_callback"](
                {"progress": index / 10, "stage": "run", "message": "frame"}
            )
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)
    completion, result, request, receipt = _load_public_generation_without_validation(
        tmp_path, completion_path,
    )
    progress_path = tmp_path / result.result["progressPath"]
    replacement_path = progress_path.with_name("concurrent-replacement.jsonl")
    original_bytes = progress_path.read_bytes()
    assert len(original_bytes) > 64 * 1024
    replacement_bytes = original_bytes.replace(
        b'"message":"frame"', b'"message":"other"', 1,
    )
    assert replacement_bytes != original_bytes
    generation_dir = progress_path.parent
    generation_dir.chmod(0o700)
    replacement_path.write_bytes(replacement_bytes)
    generation_dir.chmod(0o500)
    real_open = Path.open
    target_opens = 0
    replacement_count = 0

    class ReplaceAfterFirstRead:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self, size=-1):
            nonlocal replacement_count
            chunk = self.handle.read(size)
            if chunk and replacement_count == 0:
                replacement_count += 1
                generation_dir.chmod(0o700)
                try:
                    os.replace(replacement_path, progress_path)
                finally:
                    generation_dir.chmod(0o500)
            return chunk

    def replacing_open(path, *args, **kwargs):
        nonlocal target_opens
        handle = real_open(path, *args, **kwargs)
        if path == progress_path and (args[0] if args else kwargs.get("mode", "r")) == "rb":
            target_opens += 1
            return ReplaceAfterFirstRead(handle)
        return handle

    monkeypatch.setattr(Path, "open", replacing_open)
    validate_completion(tmp_path, request, receipt, result, completion)

    assert target_opens == 1
    assert replacement_count == 1
    assert progress_path.read_bytes() == replacement_bytes


def test_generation_progress_empty_and_multiple_events_are_exact(tmp_path):
    import backend.app.gpu_worker as worker

    empty_layout = _generation_layout(worker, generation_id="8" * 32)
    empty_owned = worker._create_owned_generation(tmp_path, empty_layout)
    empty_entry, empty_count = worker._write_generation_progress(
        tmp_path, empty_owned, (), "job-1",
    )
    assert empty_count == 0 and (tmp_path / empty_entry.relative_path).read_bytes() == b""
    events = (
        worker.ProgressEvent(1, "job-1", 1, 10, "load", "starting", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        worker.ProgressEvent(1, "job-1", 2, 100, "finish", "done", datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)),
    )
    layout = _generation_layout(worker, generation_id="9" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    entry, count = worker._write_generation_progress(tmp_path, owned, events, "job-1")
    expected = b"".join(canonical_json_bytes(event.to_mapping()) for event in events)
    assert count == 2
    assert (tmp_path / entry.relative_path).read_bytes() == expected
    assert entry == FileEntry(
        "result_artifact", layout.progress, len(expected), hashlib.sha256(expected).hexdigest(),
    )


@pytest.mark.parametrize("mutation", ["job", "order", "credentials", "line", "total", "events"])
def test_generation_progress_enforces_validation_and_limits(tmp_path, monkeypatch, mutation):
    import backend.app.gpu_worker as worker

    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if mutation == "job":
        events = (worker.ProgressEvent(1, "other", 1, 1, "run", "ok", stamp),)
    elif mutation == "order":
        events = (
            worker.ProgressEvent(1, "job-1", 2, 1, "run", "ok", stamp),
            worker.ProgressEvent(1, "job-1", 1, 2, "run", "ok", stamp),
        )
    elif mutation == "credentials":
        with pytest.raises(RemoteContractError):
            worker.ProgressEvent(1, "job-1", 1, 1, "run", "api_key=secret", stamp)
        return
    elif mutation == "line":
        monkeypatch.setattr(worker, "MAX_PROGRESS_LINE_BYTES", 100)
        events = (worker.ProgressEvent(1, "job-1", 1, 1, "run", "x" * 80, stamp),)
    elif mutation == "total":
        event = worker.ProgressEvent(1, "job-1", 1, 1, "run", "ok", stamp)
        monkeypatch.setattr(worker, "MAX_PROGRESS_TOTAL_BYTES", len(canonical_json_bytes(event.to_mapping())) - 1)
        events = (event,)
    else:
        monkeypatch.setattr(worker, "MAX_PROGRESS_EVENTS", 1)
        events = (
            worker.ProgressEvent(1, "job-1", 1, 1, "run", "ok", stamp),
            worker.ProgressEvent(1, "job-1", 2, 2, "run", "ok", stamp),
        )
    layout = _generation_layout(worker, generation_id="a" * 32)
    owned = worker._create_owned_generation(tmp_path, layout)
    with pytest.raises(worker.WorkerError):
        worker._write_generation_progress(tmp_path, owned, events, "job-1")
    assert (tmp_path / layout.progress).exists()


def test_generation_transaction_writes_four_private_files_then_links_completion(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "_new_generation_id", lambda: "3" * 32)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    calls = []
    for name in (
        "_write_generation_processor",
        "_write_generation_progress",
        "_write_generation_json",
        "validate_result",
        "validate_completion",
        "_write_generation_completion",
        "_seal_generation_read_only",
        "_commit_completion_link",
    ):
        original = getattr(worker, name)

        def record(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(worker, name, record)

    worker.run_worker(request_path, logical_result, completion_path)

    assert calls == [
        "_write_generation_processor",
        "_write_generation_progress",
        "_write_generation_json",
        "validate_result",
        "validate_completion",
        "_write_generation_completion",
        "_seal_generation_read_only",
        "_commit_completion_link",
    ]


def test_existing_completion_is_never_overwritten_or_mutated(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    identifiers = iter(("4" * 32, "5" * 32))
    monkeypatch.setattr(worker, "_new_generation_id", lambda: next(identifiers))
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    worker.run_worker(request_path, logical_result, completion_path)
    before_marker = completion_path.read_bytes()
    first_generation = tmp_path / CompletionReceipt.from_mapping(
        load_canonical_json(completion_path)
    ).result_path.parent
    before_generation = {
        path.name: path.read_bytes() for path in first_generation.iterdir()
    }

    with pytest.raises(worker.WorkerError, match="already exists") as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    assert isinstance(caught.value.__cause__, FileExistsError)
    assert completion_path.read_bytes() == before_marker
    assert {path.name: path.read_bytes() for path in first_generation.iterdir()} == before_generation
    assert (tmp_path / "outputs/result.json.generations" / ("5" * 32)).is_dir()


@pytest.mark.parametrize("failure", ["parent-fsync", "identity-confirmation"])
def test_post_link_uncertainty_retains_marker_and_generation(tmp_path, monkeypatch, failure):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "6" * 32
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_fsync = worker.os.fsync
    real_stat = worker.os.stat
    linked = {"value": False}
    real_link = worker.os.link

    def record_link(*args, **kwargs):
        result = real_link(*args, **kwargs)
        linked["value"] = True
        return result

    def maybe_fail_fsync(fd):
        if failure == "parent-fsync" and linked["value"]:
            raise OSError("public parent fsync")
        return real_fsync(fd)

    def maybe_fail_stat(path, *args, **kwargs):
        if (
            failure == "identity-confirmation"
            and linked["value"]
            and Path(path).name == completion_path.name
            and kwargs.get("dir_fd") is not None
        ):
            raise OSError("public identity confirmation")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(worker.os, "link", record_link)
    monkeypatch.setattr(worker.os, "fsync", maybe_fail_fsync)
    monkeypatch.setattr(worker.os, "stat", maybe_fail_stat)
    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, logical_result, completion_path)

    assert isinstance(caught.value.__cause__, OSError)
    assert completion_path.exists()
    assert (tmp_path / "outputs/result.json.generations" / generation_id).is_dir()


def test_post_link_public_parent_swap_is_indeterminate_and_retains_detached_marker(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "c" * 32
    outputs = tmp_path / "outputs"
    detached_outputs = tmp_path / "detached-outputs"
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_link = worker.os.link

    def swap_public_parent_then_link(*args, **kwargs):
        outputs.rename(detached_outputs)
        outputs.mkdir()
        return real_link(*args, **kwargs)

    monkeypatch.setattr(worker.os, "link", swap_public_parent_then_link)

    with pytest.raises(worker.WorkerRollbackIndeterminate, match="indeterminate"):
        worker.run_worker(request_path, logical_result, completion_path)

    assert not completion_path.exists()
    assert (detached_outputs / "completion.json").exists()
    assert (
        detached_outputs / "result.json.generations" / generation_id
    ).is_dir()


def test_post_link_generation_namespace_swap_is_indeterminate_and_retains_marker(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    generation_id = "d" * 32
    namespace = tmp_path / "outputs/result.json.generations"
    detached_namespace = tmp_path / "detached-generations"
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_link = worker.os.link

    def swap_generation_namespace_then_link(*args, **kwargs):
        namespace.rename(detached_namespace)
        namespace.mkdir()
        return real_link(*args, **kwargs)

    monkeypatch.setattr(worker.os, "link", swap_generation_namespace_then_link)

    with pytest.raises(worker.WorkerRollbackIndeterminate, match="indeterminate"):
        worker.run_worker(request_path, logical_result, completion_path)

    assert completion_path.exists()
    assert not (namespace / generation_id).exists()
    private_completion = detached_namespace / generation_id / "completion.json"
    assert private_completion.exists()
    assert private_completion.stat().st_ino == completion_path.stat().st_ino


def test_successful_completion_link_is_the_last_fallible_worker_operation(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, logical_result, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    real_commit = worker._commit_completion_link
    returned = {"value": False}

    def commit(*args, **kwargs):
        real_commit(*args, **kwargs)
        returned["value"] = True

    monkeypatch.setattr(worker, "_commit_completion_link", commit)
    worker.run_worker(request_path, logical_result, completion_path)
    assert returned["value"] is True

    tree = ast.parse(
        (Path(worker.__file__)).read_text(encoding="utf-8")
    )
    run_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_worker"
    )
    assert isinstance(run_function.body[-1], ast.Return)
    assert isinstance(run_function.body[-2], ast.Expr)
    assert isinstance(run_function.body[-2].value, ast.Call)
    assert getattr(run_function.body[-2].value.func, "id", None) == "_commit_completion_link"


@pytest.mark.parametrize("mutation", ["request", "receipt", "artifact"])
def test_validation_failure_precedes_materialization_and_processing(tmp_path, monkeypatch, mutation):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    target = {
        "request": request_path,
        "receipt": tmp_path / "sealed/receipt.json",
        "artifact": tmp_path / "sealed/model.bin",
    }[mutation]
    target.write_bytes(target.read_bytes() + b"tampered")
    process_calls = []
    materialize_calls = []
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: process_calls.append(1))
    monkeypatch.setattr(worker, "_materialize_local_options", lambda *args, **kwargs: materialize_calls.append(1))
    with pytest.raises(RemoteContractError):
        worker.run_worker(request_path, result_path, completion_path)
    assert process_calls == [] and materialize_calls == []
    assert not result_path.exists() and not completion_path.exists()


def test_nonlocal_reference_is_rejected_without_processing(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    reference = {"inline": {
        "name": "model.bin",
        "contentBase64": "eA==",
        "sha256": hashlib.sha256(b"x").hexdigest(),
        "sizeBytes": 1,
    }}
    request_path, result_path, completion_path = _bundle(tmp_path, reference=reference)
    calls = []
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: calls.append(1))
    with pytest.raises(Exception, match="local|sealed|artifact"):
        worker.run_worker(request_path, result_path, completion_path)
    assert calls == []


@pytest.mark.parametrize("change", ["missing", "extra", "options"])
def test_manifest_and_sealed_artifact_sets_must_match_before_materialization(tmp_path, monkeypatch, change):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    receipt_path = tmp_path / "sealed/receipt.json"
    receipt = load_canonical_json(receipt_path)
    if change == "missing":
        receipt["files"] = [item for item in receipt["files"] if item["role"] != "runtime_artifact"]
    elif change == "extra":
        extra = b"extra-model"
        (tmp_path / "sealed/extra.bin").write_bytes(extra)
        receipt["files"].append(_entry("runtime_artifact", "sealed/extra.bin", extra))
    else:
        receipt["requestedRuntimeOptions"]["primary_acquisition_mode"] = "substituted"
    receipt_path.write_bytes(canonical_json_bytes(receipt))
    process_calls = []
    materialize_calls = []
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: process_calls.append(1))
    monkeypatch.setattr(worker, "_materialize_local_options", lambda *args, **kwargs: materialize_calls.append(1))
    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)
    assert process_calls == [] and materialize_calls == []


def test_materializer_uses_only_verified_local_paths_without_network_imports(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker
    import builtins

    request_path, result_path, completion_path = _bundle(tmp_path)
    real_materialize = worker._materialize_local_options
    captured = {}
    network_calls = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"daytona", "runpod", "boto3", "botocore", "requests", "socket", "urllib"}:
            network_calls.append(name)
            raise AssertionError("network/provider import attempted")
        return real_import(name, *args, **kwargs)

    def materialize(options, paths_by_id):
        captured.update(paths_by_id)
        assert all(path.is_file() for path in paths_by_id.values())
        return real_materialize(options, paths_by_id)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(worker, "_materialize_local_options", materialize)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    worker.run_worker(request_path, result_path, completion_path)
    assert set(captured) == {"primary-model"}
    assert all(path.is_absolute() and not path.exists() for path in captured.values())
    assert network_calls == []


def test_materializer_passes_exact_local_kwargs_for_every_runtime_option(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path, all_runtime_artifacts=True)
    captured = {}

    def process(_video_path, _config, **kwargs):
        captured.update(kwargs)
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)

    path_kwargs = {
        key: value for key, value in captured.items()
        if key.endswith("_path") or key == "model_path"
    }
    assert set(path_kwargs) == {
        "model_path",
        "primary_model_path",
        "auxiliary_ball_model_path",
        "baseline_guided_rescue_reference_path",
        "proposal_selection_truth_seed_path",
        "reviewed_positive_anchor_seed_path",
    }
    assert all(Path(value).is_absolute() and not Path(value).exists() for value in path_kwargs.values())
    assert captured["model_path"] == captured["primary_model_path"]
    assert captured["auxiliary_ball_model_profile"] == "auxiliary-profile"
    assert captured["edge_share_repair_profile"] == "edge-profile"


def test_distinct_artifacts_with_identical_bytes_materialize_once_each(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(
        tmp_path,
        identical_primary_auxiliary=True,
    )
    captured = {}

    def process(_video_path, _config, **kwargs):
        captured.update(kwargs)
        assert Path(kwargs["primary_model_path"]).read_bytes() == b"sealed-model"
        assert Path(kwargs["auxiliary_ball_model_path"]).read_bytes() == b"sealed-model"
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    worker.run_worker(request_path, result_path, completion_path)
    assert captured["primary_model_path"] != captured["auxiliary_ball_model_path"]


def test_explicit_manifest_relative_path_binding_rejects_swapped_artifact_identity(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path, all_runtime_artifacts=True)
    receipt_path = tmp_path / "sealed/receipt.json"
    receipt = load_canonical_json(receipt_path)
    runtime_entries = [item for item in receipt["files"] if item["role"] == "runtime_artifact"]
    primary_entry, auxiliary_entry = runtime_entries[:2]
    primary_payload = (tmp_path / primary_entry["relativePath"]).read_bytes()
    auxiliary_payload = (tmp_path / auxiliary_entry["relativePath"]).read_bytes()
    primary_entry.update(_entry("runtime_artifact", "models/primary-model.bin", auxiliary_payload))
    auxiliary_path = tmp_path / auxiliary_entry["relativePath"]
    auxiliary_path.write_bytes(primary_payload)
    auxiliary_entry.update(_entry("runtime_artifact", auxiliary_entry["relativePath"], primary_payload))
    explicit_path = tmp_path / primary_entry["relativePath"]
    explicit_path.parent.mkdir(parents=True, exist_ok=True)
    explicit_path.write_bytes(auxiliary_payload)
    receipt_path.write_bytes(canonical_json_bytes(receipt))
    process_calls = []
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: process_calls.append(1))
    with pytest.raises(worker.WorkerError, match="artifact identity"):
        worker.run_worker(request_path, result_path, completion_path)
    assert process_calls == []


@pytest.mark.parametrize(
    "bad_result",
    [
        None,
        [1],
        {"value": float("nan")},
        {"api_key": "super-secret"},
        {"nested": {"clientSecret": "value"}},
        {"nested": [{"DBPassword": "value"}]},
        {"sessionCookie": "value"},
        {"nested": {"awsSecretAccessKey": "worker-result-sentinel"}},
        {"secretAccessKey": "worker-result-sentinel"},
        {"nested": [{"stripeSecretKey": "worker-result-sentinel"}]},
        {"privateKey": "worker-result-sentinel"},
        {"accessKeyId": "worker-result-sentinel"},
        {"large": "x" * 70_000},
    ],
)
def test_unsafe_processor_results_roll_back_publication(tmp_path, monkeypatch, bad_result):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: bad_result)
    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)
    assert not result_path.exists() and not completion_path.exists()


def test_malicious_progress_fails_and_removes_outputs(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)

    def process(*args, **kwargs):
        kwargs["progress_callback"]({"progress": 40, "stage": "run", "message": "ok"})
        kwargs["progress_callback"]({"progress": 30, "stage": "run", "message": "api_key=secret"})
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)
    assert not result_path.exists() and not completion_path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"progress": 1, "stage": "run", "message": "x" * 70_000},
        {"progress": 1, "stage": "run", "message": "ok", "jobId": "other-job"},
        {"progress": 1, "stage": "run", "message": "ok", "accessToken": "value"},
        {"progress": 1, "stage": "run", "message": "ok", "awsSecretAccessKey": "progress-sentinel"},
        {"progress": 1, "stage": "run", "message": "ok", "secretAccessKey": "progress-sentinel"},
        {"progress": 1, "stage": "run", "message": "ok", "stripeSecretKey": "progress-sentinel"},
        {"progress": 1, "stage": "run", "message": "ok", "privateKey": "progress-sentinel"},
        {"progress": 1, "stage": "run", "message": "ok", "accessKeyId": "progress-sentinel"},
    ],
)
def test_oversized_wrong_job_or_sensitive_progress_fails_safely(tmp_path, monkeypatch, payload):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)

    def process(*args, **kwargs):
        kwargs["progress_callback"](payload)
        return {"rows": [{"Frame_ID": 0}]}

    monkeypatch.setattr(worker, "process_video_input", process)
    with pytest.raises(worker.WorkerError):
        worker.run_worker(request_path, result_path, completion_path)
    assert not result_path.exists() and not completion_path.exists()


def test_progress_collector_flushes_a_valid_event_immediately():
    import backend.app.gpu_worker as worker

    output = FlushSpy()
    events, _, callback = worker._progress_collector("job-1", output=output)
    callback({"workerStage": "trackingPass", "stageStatus": "running"})
    assert output.lines == [
        worker.LIVE_PROGRESS_PREFIX
        + canonical_json_bytes(events[0].to_mapping()).decode()
    ]
    assert output.flush_count == 1


def test_progress_collector_never_emits_an_unsafe_event():
    import backend.app.gpu_worker as worker

    output = FlushSpy()
    _, state, callback = worker._progress_collector("job-1", output=output)
    callback({"message": "api_key=secret"})
    assert state["error"] is True
    assert output.lines == []


@pytest.mark.parametrize("operation", ["write", "flush"])
def test_progress_collector_keeps_validated_event_when_output_fails(monkeypatch, operation):
    import backend.app.gpu_worker as worker

    output = FlushSpy()
    monkeypatch.setattr(output, operation, lambda *args: (_ for _ in ()).throw(OSError()))
    events, state, callback = worker._progress_collector("job-1", output=output)
    callback({"progress": 10, "stage": "load", "message": "starting"})
    assert worker._validated_progress(events, state, "job-1") == tuple(events)


def test_progress_collector_rejects_exact_event_limit_plus_one_without_retaining_extra(monkeypatch):
    import backend.app.gpu_worker as worker

    test_limit = 5
    monkeypatch.setattr(worker, "MAX_PROGRESS_EVENTS", test_limit)
    events, state, callback = worker._progress_collector("job-1")
    payload = {"progress": 1, "stage": "run", "message": "ok"}
    for _ in range(test_limit + 1):
        callback(payload)
    assert state["error"] is True
    assert len(events) == test_limit


def test_progress_collector_checks_event_limit_before_serializing_excess(monkeypatch):
    import backend.app.gpu_worker as worker

    test_limit = 5
    monkeypatch.setattr(worker, "MAX_PROGRESS_EVENTS", test_limit)
    events, state, callback = worker._progress_collector("job-1")
    payload = {"progress": 1, "stage": "run", "message": "ok"}
    for _ in range(test_limit):
        callback(payload)
    serialization_calls = []

    def reject_serialization(*args, **kwargs):
        serialization_calls.append(1)
        raise AssertionError("serialized excess event")

    monkeypatch.setattr(
        worker,
        "canonical_json_bytes",
        reject_serialization,
    )
    callback(payload)
    assert state["error"] is True
    assert len(events) == test_limit
    assert serialization_calls == []


def test_progress_collector_rejects_cumulative_total_before_retaining_oversize():
    import backend.app.gpu_worker as worker

    events, state, callback = worker._progress_collector("job-1")
    payload = {"progress": 1, "stage": "run", "message": "x" * 4_000}
    attempts = MAX_PROGRESS_TOTAL_BYTES // 4_000 + 3
    for _ in range(attempts):
        callback(payload)
    retained_bytes = sum(len(canonical_json_bytes(event.to_mapping())) for event in events)
    assert state["error"] is True
    assert retained_bytes <= MAX_PROGRESS_TOTAL_BYTES


def test_private_completion_failure_retains_generation_without_public_outputs(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    generation_id = "7" * 32
    monkeypatch.setattr(worker, "_new_generation_id", lambda: generation_id)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    monkeypatch.setattr(
        worker,
        "_write_generation_completion",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("publication failed")),
    )
    with pytest.raises(OSError):
        worker.run_worker(request_path, result_path, completion_path)
    assert not result_path.exists() and not completion_path.exists()
    assert (tmp_path / "outputs/result.json.generations" / generation_id).is_dir()


def test_postpublication_validation_failure_rolls_back_both_outputs(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})
    monkeypatch.setattr(worker, "validate_completion", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("invalid")))
    with pytest.raises(ValueError):
        worker.run_worker(request_path, result_path, completion_path)
    assert not result_path.exists() and not completion_path.exists()


def test_process_failure_cleans_temporary_materialization(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    real_materialize = worker._materialize_local_options
    materialized_paths = []

    def materialize(options, paths_by_id):
        materialized_paths.extend(paths_by_id.values())
        return real_materialize(options, paths_by_id)

    monkeypatch.setattr(worker, "_materialize_local_options", materialize)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failed")))
    with pytest.raises(RuntimeError):
        worker.run_worker(request_path, result_path, completion_path)
    assert len(materialized_paths) == 1 and not materialized_paths[0].exists()


def test_generation_creation_rejects_parent_symlink_swap_without_touching_outside_bytes(
    tmp_path,
    monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    publication_paths = _publication_paths(result_path, completion_path)
    output_directory = result_path.parent
    output_directory.mkdir()
    detached_directory = tmp_path / "detached-outputs"
    outside_directory = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_directory.mkdir()
    outside_paths = tuple(outside_directory / path.name for path in publication_paths)
    for index, path in enumerate(outside_paths):
        path.write_bytes(f"outside-{index}".encode())
    before = {path: path.read_bytes() for path in outside_paths}
    real_prepare = worker._prepare_runtime

    def swap_output_directory(*args, **kwargs):
        runtime = real_prepare(*args, **kwargs)
        output_directory.rename(detached_directory)
        output_directory.symlink_to(outside_directory, target_is_directory=True)
        return runtime

    monkeypatch.setattr(worker, "_prepare_runtime", swap_output_directory)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    with pytest.raises(Exception) as caught:
        worker.run_worker(request_path, result_path, completion_path)

    assert {path: path.read_bytes() for path in outside_paths} == before
    assert isinstance(caught.value, worker.WorkerRollbackIndeterminate)
    assert "indeterminate" in str(caught.value)


def test_tempdir_exit_failure_occurs_before_any_publication(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    publication_paths = _publication_paths(result_path, completion_path)
    _install_tempdir_exit_failure(
        worker, monkeypatch, OSError("temporary directory cleanup failed"),
    )
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    with pytest.raises(OSError, match="temporary directory cleanup failed"):
        worker.run_worker(request_path, result_path, completion_path)

    assert all(not path.exists() for path in publication_paths)


def test_temporary_directory_exit_failure_occurs_before_generation_creation(tmp_path, monkeypatch):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    exit_error = worker.WorkerRollbackIndeterminate("temporary directory exit indeterminate")
    _install_tempdir_exit_failure(worker, monkeypatch, exit_error)
    monkeypatch.setattr(worker, "process_video_input", lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]})

    with pytest.raises(worker.WorkerRollbackIndeterminate) as caught:
        worker.run_worker(request_path, result_path, completion_path)

    assert caught.value is exit_error
    assert not (tmp_path / "outputs/result.json.generations").exists()


def test_processing_and_temporary_exit_failures_preserve_primary_and_chain_secondary(
    tmp_path, monkeypatch,
):
    import backend.app.gpu_worker as worker

    request_path, result_path, completion_path = _bundle(tmp_path)
    primary = RuntimeError("processor failed")
    secondary = OSError("temporary directory cleanup failed")
    _install_tempdir_exit_failure(worker, monkeypatch, secondary)
    monkeypatch.setattr(
        worker,
        "process_video_input",
        lambda *args, **kwargs: (_ for _ in ()).throw(primary),
    )

    with pytest.raises(RuntimeError) as caught:
        worker.run_worker(request_path, result_path, completion_path)

    assert caught.value is primary
    assert caught.value.__cause__ is secondary
    assert not (tmp_path / "outputs/result.json.generations").exists()
    assert not completion_path.exists()


def test_gpu_worker_has_no_forbidden_provider_or_network_imports():
    source = (Path(__file__).parents[1] / "app/gpu_worker.py").read_text(encoding="utf-8")
    roots = {node.names[0].name.split(".")[0] for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import)}
    roots |= {node.module.split(".")[0] for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    assert roots.isdisjoint({"daytona", "runpod", "boto3", "requests", "urllib", "socket"})


def test_cli_help_has_exact_required_arguments():
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.gpu_worker", "--help"],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "--request" in completed.stdout
    assert "--result" in completed.stdout
    assert "--completion-receipt" in completed.stdout
    assert set(re.findall(r"--[a-z-]+", completed.stdout)) == {
        "--help", "--request", "--result", "--completion-receipt",
    }


def test_cli_failure_is_nonzero_bounded_and_redacted(tmp_path):
    request_path = tmp_path / "api_key=super-secret.json"
    request_path.write_bytes(b"not canonical")
    completed = subprocess.run(
        [
            sys.executable, "-m", "backend.app.gpu_worker",
            "--request", str(request_path),
            "--result", str(tmp_path / "result.json"),
            "--completion-receipt", str(tmp_path / "completion.json"),
        ],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "super-secret" not in completed.stderr
    assert len(completed.stderr) < 200


@pytest.mark.parametrize(
    "arguments",
    [
        ["--api_key=super-secret"],
        ["--request", "--result=super-secret"],
        ["super-secret"],
    ],
)
def test_cli_parser_errors_never_echo_secret_arguments(arguments):
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.gpu_worker", *arguments],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "super-secret" not in completed.stderr
    assert len(completed.stderr) < 200


def test_cli_duplicate_secret_argument_is_rejected_without_echo(tmp_path):
    request_path, result_path, completion_path = _bundle(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.gpu_worker",
            "--request=super-secret",
            f"--request={request_path}",
            f"--result={result_path}",
            f"--completion-receipt={completion_path}",
        ],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "super-secret" not in completed.stderr
    assert len(completed.stderr) < 200
    assert not result_path.exists() and not completion_path.exists()


@pytest.mark.parametrize(
    ("abbreviation", "exact"),
    [
        ("--requ", "--request"),
        ("--res", "--result"),
        ("--completion-r", "--completion-receipt"),
    ],
)
def test_cli_rejects_abbreviated_secret_arguments(abbreviation, exact, tmp_path):
    secret_root = tmp_path / "super-secret"
    request_path, result_path, completion_path = _bundle(secret_root)
    arguments = {
        "--request": str(request_path),
        "--result": str(result_path),
        "--completion-receipt": str(completion_path),
    }
    command = [sys.executable, "-m", "backend.app.gpu_worker"]
    for flag, value in arguments.items():
        command.append(f"{abbreviation if flag == exact else flag}={value}")
    completed = subprocess.run(
        command,
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "super-secret" not in completed.stderr
    assert len(completed.stderr) < 200
    assert not result_path.exists() and not completion_path.exists()


@pytest.mark.parametrize("abbreviation_first", [True, False])
def test_cli_rejects_mixed_abbreviated_and_exact_duplicate_without_echo(tmp_path, abbreviation_first):
    secret_root = tmp_path / "super-secret"
    request_path, result_path, completion_path = _bundle(secret_root)
    request_arguments = [f"--requ={request_path}", f"--request={request_path}"]
    if not abbreviation_first:
        request_arguments.reverse()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.gpu_worker",
            *request_arguments,
            f"--result={result_path}",
            f"--completion-receipt={completion_path}",
        ],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "super-secret" not in completed.stderr
    assert len(completed.stderr) < 200
    assert not result_path.exists() and not completion_path.exists()


def test_fresh_worker_import_loads_no_forbidden_provider_or_network_modules():
    script = r'''
import argparse
import pathlib
import sys
blocked = {"daytona", "runpod", "boto3", "botocore", "requests", "socket", "urllib"}
for module_name in list(sys.modules):
    if module_name.split(".")[0] in blocked:
        del sys.modules[module_name]
class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise ImportError("blocked forbidden module")
        return None
sys.meta_path.insert(0, Blocker())
import backend.app.gpu_worker
loaded = sorted(name for name in sys.modules if name.split(".")[0] in blocked)
if loaded:
    raise SystemExit("forbidden modules loaded")
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_valid_artifact_worker_run_loads_no_forbidden_provider_or_network_modules(tmp_path):
    request_path, result_path, completion_path = _bundle(tmp_path)
    script = r'''
import pathlib
import socket
import sys
import urllib.request
import backend.app.schemas
blocked = {"daytona", "runpod", "boto3", "botocore", "requests"}
for module_name in list(sys.modules):
    if module_name.split(".")[0] in blocked:
        del sys.modules[module_name]
class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise ImportError("blocked forbidden module")
        return None
sys.meta_path.insert(0, Blocker())
import backend.app.gpu_worker as worker
network_calls = []
socket.socket = lambda *args, **kwargs: network_calls.append("socket")
socket.create_connection = lambda *args, **kwargs: network_calls.append("create_connection")
urllib.request.urlopen = lambda *args, **kwargs: network_calls.append("urlopen")
worker.process_video_input = lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}]}
worker.run_worker(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
loaded = sorted(name for name in sys.modules if name.split(".")[0] in blocked)
if loaded:
    raise SystemExit("forbidden provider modules loaded")
if network_calls:
    raise SystemExit("network call attempted")
'''
    completed = subprocess.run(
        [sys.executable, "-c", script, str(request_path), str(result_path), str(completion_path)],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
