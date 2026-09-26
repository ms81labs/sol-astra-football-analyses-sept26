from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone, tzinfo
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import traceback
from types import SimpleNamespace

import pytest

from backend.app.remote_contracts import (
    MAX_FILES,
    MAX_PROGRESS_EVENTS,
    MAX_PROGRESS_TOTAL_BYTES,
    CompletionReceipt,
    FileEntry,
    JobReceipt,
    JobRequest,
    ProgressEvent,
    RemoteContractError,
    ResultBundle,
    StreamIdentity,
    atomic_write_json,
    canonical_json_bytes,
    confined_path,
    load_canonical_json,
    redact_remote_diagnostics,
    remote_diagnostics_contain_credentials,
    stream_identity,
    validate_completion,
    validate_progress_jsonl,
    validate_receipt_files,
    validate_result,
    validate_shadow_inputs,
)


SHA = "a" * 64
COMMIT = "b" * 40
NOW = datetime(2026, 8, 24, 12, 30, tzinfo=timezone.utc)
GENERATION = "0123456789abcdef0123456789abcdef"
RESULT_PATH = f"outputs/result.json.generations/{GENERATION}/result.json"
PROCESSOR_PATH = f"outputs/result.json.generations/{GENERATION}/result.processor-result.json"
PROCESSOR_V2_PATH = f"outputs/result.json.generations/{GENERATION}/result.processor-result.jsonl"
PROGRESS_PATH = f"outputs/result.json.generations/{GENERATION}/result.progress.jsonl"
MASK_PATH = f"outputs/result.json.generations/{GENERATION}/result.segmentation-result.json"


def entry(role="manifest", path="manifest.json", data=b"x"):
    return FileEntry.from_mapping({"role": role, "relativePath": path, "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})


def request_mapping():
    return {"schemaVersion": 1, "jobId": "job-1", "matchId": "match-1", "receiptPath": "sealed/receipt.json", "inputVideoPath": "inputs/match.mp4", "config": {"mode": "proof", "nested": [1, {"ok": True}]}}


def request():
    return JobRequest.from_mapping(request_mapping())


def receipt_for(req=None, video=b"video", manifest=b"manifest", evidence=b"evidence"):
    req = req or request()
    request_bytes = canonical_json_bytes(req.to_mapping())
    files = (
        entry("source_archive", "source/source.tar", b"source"),
        entry("manifest", "manifest.json", manifest),
        entry("evidence", "evidence.json", evidence),
        entry("input_video", req.input_video_path.as_posix(), video),
        entry("job_request", "job-request.json", request_bytes),
    )
    return JobReceipt.from_mapping({
        "schemaVersion": 1, "sourceCommit": COMMIT,
        "manifestSha256": hashlib.sha256(manifest).hexdigest(),
        "evidenceSha256": hashlib.sha256(evidence).hexdigest(),
        "jobRequestSha256": hashlib.sha256(request_bytes).hexdigest(),
        "requestedRuntimeOptions": req.config,
        "files": [item.to_mapping() for item in files],
    })


def result_for(req=None, receipt=None, artifact=b"output", progress=b"", progress_count=0, namespace="outputs/result.json.generations", generation=GENERATION):
    req = req or request(); receipt = receipt or receipt_for(req)
    processor = entry("result_artifact", f"{namespace}/{generation}/result.processor-result.json", artifact)
    progress_artifact = entry("result_artifact", f"{namespace}/{generation}/result.progress.jsonl", progress)
    return ResultBundle.from_mapping({
        "schemaVersion": 1, "jobId": req.job_id, "matchId": req.match_id,
        "sourceCommit": receipt.source_commit, "manifestSha256": receipt.manifest_sha256,
        "receiptSha256": hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest(),
        "requestedRuntimeOptions": receipt.requested_runtime_options,
        "result": {
            "processorResultPath": processor.relative_path.as_posix(),
            "progressPath": progress_artifact.relative_path.as_posix(),
            "progressEventCount": progress_count,
        },
        "artifacts": [processor.to_mapping(), progress_artifact.to_mapping()],
    })


def shadow_contracts(mask=b'{"schemaVersion":"segmentation_result_v1"}\n',
                     namespace="outputs/result.json.generations", job_identity=None,
                     source_generation=GENERATION):
    mask_path = f"{namespace}/{GENERATION}/result.segmentation-result.json"
    progress_path = f"{namespace}/{GENERATION}/result.progress.jsonl"
    request_bytes = b"sealed segmentation request"
    shadow = {"schemaVersion": 1, "matchId": "match-1", "generationId": source_generation,
              "requestDigest": hashlib.sha256(request_bytes).hexdigest(),
              "sourceSha256": hashlib.sha256(b"video").hexdigest(),
              "checkpointDigest": hashlib.sha256(b"checkpoint").hexdigest(),
              "deadlineSeconds": 30}
    shadow["jobIdentity"] = job_identity or hashlib.sha256(json.dumps({key: shadow[key] for key in
        ("matchId", "generationId", "requestDigest", "checkpointDigest")},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    req = JobRequest.from_mapping({**request_mapping(), "config":
        {"jobKind": "segmentation_shadow", "rights": {"cloudPermission": True,
            "processingScope": "local_plus_burst"}, "shadowSegmentation": shadow}})
    rec = receipt_for(req)
    rec = replace(rec, files=(*rec.files, entry("runtime_artifact", "inputs/checkpoint.bin", b"checkpoint"),
                              entry("runtime_artifact", "inputs/segmentation-request.json", request_bytes)))
    result = ResultBundle.from_mapping({
        "schemaVersion": 3, "jobId": req.job_id, "matchId": req.match_id,
        "sourceCommit": rec.source_commit, "manifestSha256": rec.manifest_sha256,
        "receiptSha256": hashlib.sha256(canonical_json_bytes(rec.to_mapping())).hexdigest(),
        "requestedRuntimeOptions": rec.requested_runtime_options,
        "result": {"maskResultPath": mask_path, "progressPath": progress_path, "progressEventCount": 0,
                   **{key: shadow[key] for key in ("generationId", "requestDigest", "sourceSha256",
                                                     "checkpointDigest", "jobIdentity")}},
        "artifacts": [entry("result_artifact", mask_path, mask).to_mapping(),
                      entry("result_artifact", progress_path, b"").to_mapping()],
    })
    return req, rec, result, mask


def test_shadow_result_accepts_live_source_generation():
    req, rec, result, _ = shadow_contracts(source_generation="gen_" + GENERATION)
    validate_result(req, rec, result)


def test_shadow_result_is_sealed_to_job_source_checkpoint_and_generation(tmp_path):
    req, rec, result, mask = shadow_contracts()
    result_bytes = canonical_json_bytes(result.to_mapping())
    for path, payload in ((MASK_PATH, mask), (PROGRESS_PATH, b""), (RESULT_PATH, result_bytes)):
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    validate_completion(tmp_path, req, rec, result, completion_for(req, rec, result_bytes))
    for changed in ({"jobIdentity": "d" * 64}, {"sourceSha256": "d" * 64},
                    {"checkpointDigest": "d" * 64}, {"generationId": "f" * 32}):
        bad = result.to_mapping()
        bad["result"].update(changed)
        with pytest.raises(RemoteContractError):
            validate_result(req, rec, ResultBundle.from_mapping(bad))
    bad = result.to_mapping()
    bad["result"]["maskResultPath"] = "../../arbitrary.json"
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(bad)
    bad = result.to_mapping()
    bad["artifacts"].append(bad["artifacts"][0])
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(bad)
    bad = result.to_mapping()
    bad["artifacts"][0]["sizeBytes"] = 128 * 1024 * 1024 + 1
    with pytest.raises(RemoteContractError, match="size"):
        ResultBundle.from_mapping(bad)
    other = JobRequest.from_mapping({**req.to_mapping(), "matchId": "another-match"})
    with pytest.raises(RemoteContractError):
        validate_result(other, rec, result)
    forged_req, forged_rec, forged_result, _ = shadow_contracts(job_identity="d" * 64)
    with pytest.raises(RemoteContractError):
        validate_result(forged_req, forged_rec, forged_result)
    injected = req.to_mapping()
    injected["config"]["shadowSegmentation"]["artifactUrl"] = "https://example.invalid/mask"
    with pytest.raises(RemoteContractError, match="unknown"):
        validate_shadow_inputs(JobRequest.from_mapping(injected), rec)
    unsealed = replace(rec, files=tuple(item for item in rec.files
        if item.relative_path != PurePosixPath("inputs/checkpoint.bin")))
    rebound = replace(result, receipt_sha256=hashlib.sha256(canonical_json_bytes(
        unsealed.to_mapping())).hexdigest())
    with pytest.raises(RemoteContractError, match="shadow input"):
        validate_result(req, unsealed, rebound)
    with pytest.raises(RemoteContractError, match="shadow job requires"):
        validate_result(req, rec, result_for(req, rec))


def test_daytona_collects_only_sealed_shadow_result_files(tmp_path):
    from backend.app.daytona import (_collect_result, DaytonaDiagnostics,
        DaytonaExecutionError, DaytonaExecutionResult)

    req, rec, result, mask = shadow_contracts(namespace="result-bundle.json.generations")
    result_bytes = canonical_json_bytes(result.to_mapping())
    result_path = f"result-bundle.json.generations/{GENERATION}/result.json"
    mask_path = result.result["maskResultPath"]
    progress_path = result.result["progressPath"]
    completion = completion_for(req, rec, result_bytes, result_path)
    remote = {
        "/home/daytona/job/completion-receipt.json": canonical_json_bytes(completion.to_mapping()),
        f"/home/daytona/job/{result_path}": result_bytes,
        f"/home/daytona/job/{mask_path}": mask,
        f"/home/daytona/job/{progress_path}": b"",
        "/home/daytona/job/unrequested-mask.json": b"do not fetch",
    }
    downloads = []
    class Files:
        def download_file_stream(self, path, timeout):
            downloads.append(path)
            return iter((remote[path],))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    owner, received_completion, received_result, primary, progress = _collect_result(
        SimpleNamespace(fs=Files()), workspace, req, rec, 10)
    try:
        assert received_completion == completion and received_result == result
        assert primary.read_bytes() == mask and progress.read_bytes() == b""
        assert primary.relative_to(owner.staging).as_posix() == mask_path
        accepted = DaytonaExecutionResult("sandbox-1", completion, result, owner.staging,
            primary, progress, DaytonaDiagnostics("[REDACTED]"))
        assert accepted.processor_path == primary
        with pytest.raises(DaytonaExecutionError, match="paths"):
            DaytonaExecutionResult("sandbox-1", completion, result, owner.staging,
                progress, progress, DaytonaDiagnostics("[REDACTED]"))
    finally:
        owner.cleanup()
    assert set(downloads) == set(remote) - {"/home/daytona/job/unrequested-mask.json"}
    remote[f"/home/daytona/job/{mask_path}"] = b"tampered mask"
    with pytest.raises(DaytonaExecutionError, match="download"):
        _collect_result(SimpleNamespace(fs=Files()), workspace, req, rec, 10)
    assert not list(workspace.iterdir()), "failed transfers must remove local staging"


def v2_result_mapping(req=None, receipt=None, processor=b"output", progress=b"", progress_count=0, row_count=2):
    req = req or request(); receipt = receipt or receipt_for(req)
    processor_artifact = entry("result_artifact", PROCESSOR_V2_PATH, processor)
    progress_artifact = entry("result_artifact", PROGRESS_PATH, progress)
    return {
        "schemaVersion": 2, "jobId": req.job_id, "matchId": req.match_id,
        "sourceCommit": receipt.source_commit, "manifestSha256": receipt.manifest_sha256,
        "receiptSha256": hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest(),
        "requestedRuntimeOptions": receipt.requested_runtime_options,
        "result": {
            "processorResultPath": processor_artifact.relative_path.as_posix(),
            "processorResultFormat": "jsonl-v1",
            "processorRowCount": row_count,
            "progressPath": progress_artifact.relative_path.as_posix(),
            "progressEventCount": progress_count,
        },
        "artifacts": [processor_artifact.to_mapping(), progress_artifact.to_mapping()],
    }


def write_result_artifacts(root: Path, result: ResultBundle, processor=b"output", progress=b""):
    payloads = {
        result.result["processorResultPath"]: processor,
        result.result["progressPath"]: progress,
    }
    for relative, payload in payloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def completion_for(req, receipt, result_bytes, result_path=RESULT_PATH):
    identity = stream_identity(io.BytesIO(result_bytes))
    return CompletionReceipt.from_mapping({
        "schemaVersion": 1,
        "jobId": req.job_id,
        "matchId": req.match_id,
        "resultPath": result_path,
        "resultSizeBytes": identity.size_bytes,
        "resultSha256": identity.sha256,
        "sourceCommit": receipt.source_commit,
        "manifestSha256": receipt.manifest_sha256,
        "completedAt": "2026-08-24T12:30:00Z",
    })


def progress_bytes(*events: Mapping[str, object]) -> bytes:
    return b"".join(canonical_json_bytes(event) for event in events)


SCHEMAS = [
    (FileEntry, lambda: entry().to_mapping()),
    (JobRequest, request_mapping),
    (JobReceipt, lambda: receipt_for().to_mapping()),
    (ProgressEvent, lambda: {"schemaVersion": 1, "jobId": "job-1", "sequence": 1, "progress": 1, "stage": "load", "message": "starting", "timestamp": "2026-08-24T12:30:00Z"}),
    (ResultBundle, lambda: result_for().to_mapping()),
    (CompletionReceipt, lambda: {"schemaVersion": 1, "jobId": "job-1", "matchId": "match-1", "resultPath": RESULT_PATH, "resultSizeBytes": 12, "resultSha256": SHA, "sourceCommit": COMMIT, "manifestSha256": SHA, "completedAt": "2026-08-24T12:30:00Z"}),
]


@pytest.mark.parametrize("cls,factory", SCHEMAS)
def test_every_schema_rejects_missing_and_extra_keys(cls, factory):
    for key in factory():
        value = factory(); value.pop(key)
        with pytest.raises(RemoteContractError, match="missing"):
            cls.from_mapping(value)
    value = factory(); value["secretExtra"] = "no"
    with pytest.raises(RemoteContractError, match="unknown"):
        cls.from_mapping(value)


def test_scalar_hash_git_and_timestamp_grammar_are_strict():
    for bad in (True, 0, 2, "1"):
        value = request_mapping(); value["schemaVersion"] = bad
        with pytest.raises(RemoteContractError): JobRequest.from_mapping(value)
    for bad in ("A" * 64, "a" * 63, True):
        value = entry().to_mapping(); value["sha256"] = bad
        with pytest.raises(RemoteContractError): FileEntry.from_mapping(value)
    value = receipt_for().to_mapping(); value["sourceCommit"] = "B" * 40
    with pytest.raises(RemoteContractError): JobReceipt.from_mapping(value)
    for bad in ("2026-08-24T12:30:00+01:00", "2026-08-24 12:30:00Z", "2026-08-24T12:30:00.000000Z", True):
        value = SCHEMAS[3][1](); value["timestamp"] = bad
        with pytest.raises(RemoteContractError): ProgressEvent.from_mapping(value)


def test_result_artifact_role_is_output_only_and_runtime_artifact_is_not_a_result():
    result_artifact = entry("result_artifact", PROCESSOR_PATH, b"{}\n")
    assert result_artifact.role == "result_artifact"
    receipt_value = receipt_for().to_mapping()
    receipt_value["files"].append(result_artifact.to_mapping())
    with pytest.raises(RemoteContractError, match="input|receipt|role"):
        JobReceipt.from_mapping(receipt_value)
    result_value = result_for().to_mapping()
    result_value["artifacts"][0]["role"] = "runtime_artifact"
    with pytest.raises(RemoteContractError, match="result_artifact"):
        ResultBundle.from_mapping(result_value)


def test_job_receipt_direct_constructor_rejects_result_artifact():
    receipt = receipt_for()
    artifact = entry("result_artifact", "outputs/result.json", b"{}\n")
    with pytest.raises(RemoteContractError, match="input|receipt|role"):
        replace(receipt, files=(*receipt.files, artifact))


def test_result_bundle_binds_exact_processor_and_progress_artifact_paths():
    req = request()
    rec = receipt_for(req)
    processor = entry("result_artifact", PROCESSOR_PATH, b"{}\n")
    progress = entry("result_artifact", PROGRESS_PATH, b"")
    value = {
        "schemaVersion": 1,
        "jobId": req.job_id,
        "matchId": req.match_id,
        "sourceCommit": rec.source_commit,
        "manifestSha256": rec.manifest_sha256,
        "receiptSha256": hashlib.sha256(canonical_json_bytes(rec.to_mapping())).hexdigest(),
        "requestedRuntimeOptions": rec.requested_runtime_options,
        "result": {
            "processorResultPath": processor.relative_path.as_posix(),
            "progressPath": progress.relative_path.as_posix(),
            "progressEventCount": 0,
        },
        "artifacts": [processor.to_mapping(), progress.to_mapping()],
    }
    result = ResultBundle.from_mapping(value)
    assert result.result["processorResultPath"] == processor.relative_path.as_posix()
    for mutation in ("missing", "swapped", "extra"):
        bad = result.to_mapping()
        if mutation == "missing":
            bad["artifacts"].pop()
        elif mutation == "swapped":
            bad["result"]["progressPath"] = processor.relative_path.as_posix()
        else:
            bad["artifacts"].append(entry("result_artifact", "outputs/extra.json", b"{}\n").to_mapping())
        with pytest.raises(RemoteContractError, match="artifact|[Pp]ath"):
            ResultBundle.from_mapping(bad)


def test_result_bundle_v2_binds_line_framed_processor_artifact():
    value = v2_result_mapping()
    result = ResultBundle(
        value["schemaVersion"], value["jobId"], value["matchId"], value["sourceCommit"],
        value["manifestSha256"], value["receiptSha256"], value["requestedRuntimeOptions"],
        value["result"], tuple(FileEntry.from_mapping(item) for item in value["artifacts"]),
    )
    assert result.processor_format == "jsonl-v1"
    assert result.processor_row_count == 2
    assert ResultBundle.from_mapping(result.to_mapping()) == result


def test_result_bundle_v2_rejects_unknown_format():
    value = v2_result_mapping()
    value["result"]["processorResultFormat"] = "unknown"
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(value)


def test_result_bundle_v1_rejects_v2_fields_and_uses_legacy_properties():
    value = result_for().to_mapping()
    value["result"]["processorRowCount"] = 2
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(value)
    legacy = result_for()
    assert legacy.processor_format == "json-v1"
    assert legacy.processor_row_count is None


@pytest.mark.parametrize("row_count", [-1, 20_000_001])
def test_result_bundle_v2_rejects_out_of_range_row_count(row_count):
    value = v2_result_mapping(row_count=row_count)
    with pytest.raises(RemoteContractError, match="processorRowCount"):
        ResultBundle.from_mapping(value)


def test_validate_completion_binds_v2_processor_filename(tmp_path):
    req = request(); rec = receipt_for(req)
    result = ResultBundle.from_mapping(v2_result_mapping(req, rec))
    write_result_artifacts(tmp_path, result)
    result_path = tmp_path / RESULT_PATH
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_bytes = canonical_json_bytes(result.to_mapping())
    result_path.write_bytes(result_bytes)
    validate_completion(tmp_path, req, rec, result, completion_for(req, rec, result_bytes))


def test_result_bundle_rejects_two_way_processor_progress_path_swap():
    value = result_for().to_mapping()
    processor_path = value["result"]["processorResultPath"]
    value["result"]["processorResultPath"] = value["result"]["progressPath"]
    value["result"]["progressPath"] = processor_path
    with pytest.raises(RemoteContractError, match="processorResultPath|progressPath"):
        ResultBundle.from_mapping(value)


@pytest.mark.parametrize("generation", ["abc", "0" * 31, "A" * 32, "g" * 32])
def test_generation_id_must_be_exact_lowercase_hex(generation):
    value = result_for().to_mapping()
    for key, filename in (("processorResultPath", "result.processor-result.json"), ("progressPath", "result.progress.jsonl")):
        value["result"][key] = f"outputs/result.json.generations/{generation}/{filename}"
    for artifact in value["artifacts"]:
        artifact["relativePath"] = f"outputs/result.json.generations/{generation}/{PurePosixPath(artifact['relativePath']).name}"
    with pytest.raises(RemoteContractError, match="generation"):
        ResultBundle.from_mapping(value)


@pytest.mark.parametrize("namespace", ["outputs/.json.generations", "outputs/result.generations", "outputs/result.json.generation", "outputs/result.json.generations.extra"])
def test_result_namespace_must_end_with_json_generations(namespace):
    with pytest.raises(RemoteContractError, match="namespace|generations"):
        result_for(namespace=namespace)


def test_result_sidecars_must_share_one_generation():
    value = result_for().to_mapping()
    other_generation = "f" * 32
    value["result"]["progressPath"] = f"outputs/result.json.generations/{other_generation}/result.progress.jsonl"
    value["artifacts"][1]["relativePath"] = value["result"]["progressPath"]
    with pytest.raises(RemoteContractError, match="generation"):
        ResultBundle.from_mapping(value)


def test_processor_and_progress_must_share_one_generation():
    value = result_for().to_mapping()
    other_generation = "f" * 32
    value["result"]["processorResultPath"] = f"outputs/result.json.generations/{other_generation}/result.processor-result.json"
    value["artifacts"][0]["relativePath"] = value["result"]["processorResultPath"]
    with pytest.raises(RemoteContractError, match="share one generation"):
        ResultBundle.from_mapping(value)


def test_generation_paths_accept_nested_and_distinct_logical_result_names():
    namespace = "outputs/nested/match-analysis.v2.json.generations"
    result = result_for(namespace=namespace)
    completion = completion_for(request(), receipt_for(), canonical_json_bytes(result.to_mapping()), f"{namespace}/{GENERATION}/result.json")
    assert completion.result_path.as_posix() == f"{namespace}/{GENERATION}/result.json"


@pytest.mark.parametrize("bad_path", [
    f"outputs/result.json.generations/{GENERATION}/bundle.json",
    f"outputs/result.generations/{GENERATION}/result.json",
    f"outputs/result.json.generations/{'A' * 32}/result.json",
    "outputs/result.json.generations/short/result.json",
])
def test_completion_rejects_wrong_fixed_name_namespace_or_generation(bad_path):
    value = SCHEMAS[5][1](); value["resultPath"] = bad_path
    with pytest.raises(RemoteContractError, match="resultPath|generation|namespace"):
        CompletionReceipt.from_mapping(value)


@pytest.mark.parametrize("factory", [
    lambda: CompletionReceipt(1, "job-1", "match-1", HostileStr(RESULT_PATH), 12, SHA, COMMIT, SHA, NOW),
    lambda: CompletionReceipt.from_mapping({**SCHEMAS[5][1](), "resultPath": HostileStr(RESULT_PATH)}),
])
def test_generation_paths_normalize_hostile_direct_and_mapping_values(factory):
    completion = factory()
    assert type(completion.result_path) is PurePosixPath
    assert completion.result_path.as_posix() == RESULT_PATH


@pytest.mark.parametrize(
    "field,bad_path",
    [
        ("processorResultPath", f"outputs/result.json.generations/{GENERATION}/result.json"),
        ("processorResultPath", f"outputs/result.json.generations/{GENERATION}/result.processor-result.json.backup"),
        ("processorResultPath", f"outputs/result.json.generations/{GENERATION}/result.PROCESSOR-RESULT.JSON"),
        ("progressPath", f"outputs/result.json.generations/{GENERATION}/progress.jsonl"),
        ("progressPath", f"outputs/result.json.generations/{GENERATION}/result.progress.jsonl.backup"),
        ("progressPath", f"outputs/result.json.generations/{GENERATION}/result.PROGRESS.JSONL"),
    ],
)
def test_result_bundle_rejects_misleading_or_case_variant_sidecar_names(field, bad_path):
    value = result_for().to_mapping()
    old_path = value["result"][field]
    value["result"][field] = bad_path
    for artifact in value["artifacts"]:
        if artifact["relativePath"] == old_path:
            artifact["relativePath"] = bad_path
    with pytest.raises(RemoteContractError, match=rf"{field} must use the fixed generation filename"):
        ResultBundle.from_mapping(value)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["artifacts"].pop(),
        lambda value: value["artifacts"].append(value["artifacts"][0].copy()),
        lambda value: value["artifacts"].append(
            entry("result_artifact", "outputs/extra.json", b"{}\n").to_mapping()
        ),
        lambda value: value["artifacts"].__setitem__(
            1, entry("result_artifact", "outputs/wrong.jsonl", b"").to_mapping()
        ),
    ],
    ids=["missing", "duplicate", "extra", "wrong-path"],
)
def test_result_bundle_rejects_nonexact_artifact_path_sets(mutation):
    value = result_for().to_mapping()
    mutation(value)
    with pytest.raises(RemoteContractError, match="artifact|duplicate|exactly two"):
        ResultBundle.from_mapping(value)


@pytest.mark.parametrize("bad", [True, 1.0, -1, MAX_PROGRESS_EVENTS + 1])
def test_result_bundle_rejects_invalid_progress_event_count(bad):
    value = result_for().to_mapping()
    value["result"]["progressEventCount"] = bad
    with pytest.raises(RemoteContractError, match="progressEventCount"):
        ResultBundle.from_mapping(value)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_result_bundle_result_mapping_has_exact_keys(mutation):
    value = result_for().to_mapping()
    if mutation == "missing":
        value["result"].pop("progressPath")
    else:
        value["result"]["score"] = 0.5
    with pytest.raises(RemoteContractError, match="result.*keys"):
        ResultBundle.from_mapping(value)


def test_result_bundle_normalizes_direct_result_scalars_and_preserves_artifact_order():
    result = result_for()
    reversed_artifacts = tuple(reversed(result.artifacts))
    rebuilt = replace(
        result,
        result={
            "processorResultPath": PurePosixPath(result.result["processorResultPath"]),
            "progressPath": PurePosixPath(result.result["progressPath"]),
            "progressEventCount": HostileInt(result.result["progressEventCount"]),
        },
        artifacts=reversed_artifacts,
    )
    assert type(rebuilt.result["processorResultPath"]) is str
    assert type(rebuilt.result["progressPath"]) is str
    assert type(rebuilt.result["progressEventCount"]) is int
    assert set(rebuilt.result) == {
        "processorResultPath",
        "progressPath",
        "progressEventCount",
    }
    assert rebuilt.artifacts == tuple(
        FileEntry(item.role, item.relative_path, item.size_bytes, item.sha256)
        for item in reversed_artifacts
    )
    assert ResultBundle.from_mapping(
        load_canonical_json(canonical_json_bytes(rebuilt.to_mapping()))
    ) == rebuilt


def test_result_bundle_accepts_two_empty_result_artifacts():
    value = result_for(artifact=b"").to_mapping()
    result = ResultBundle.from_mapping(value)
    assert [item.size_bytes for item in result.artifacts] == [0, 0]


@pytest.mark.parametrize("bad", ["/abs", ".", "..", "a/../b", "a//b", "a\\b", "a\0b", "C:/x", "a/./b", ""])
def test_posix_paths_reject_unsafe_or_noncanonical_forms(bad):
    value = entry().to_mapping(); value["relativePath"] = bad
    with pytest.raises(RemoteContractError): FileEntry.from_mapping(value)


def test_deep_immutability_and_canonical_round_trip():
    original = request_mapping(); req = JobRequest.from_mapping(original)
    original["config"]["nested"][1]["ok"] = False
    assert req.config["nested"][1]["ok"] is True
    with pytest.raises(TypeError): req.config["x"] = 1
    with pytest.raises(FrozenInstanceError): req.job_id = "other"
    raw = canonical_json_bytes(req.to_mapping())
    assert raw.endswith(b"\n") and load_canonical_json(raw) == req.to_mapping()
    assert set(req.to_mapping()) == {"schemaVersion", "jobId", "matchId", "receiptPath", "inputVideoPath", "config"}
    with pytest.raises(RemoteContractError, match="canonical"):
        load_canonical_json(json.dumps(req.to_mapping(), indent=2).encode())
    with pytest.raises(RemoteContractError): canonical_json_bytes({1: "bad"})
    with pytest.raises(RemoteContractError): canonical_json_bytes({"x": float("nan")})


def test_direct_dataclass_construction_also_freezes_nested_json():
    config = {"nested": [{"safe": True}]}
    req = JobRequest(1, "job-1", "match-1", PurePosixPath("receipt.json"), PurePosixPath("input.mp4"), config)
    config["nested"][0]["safe"] = False
    assert req.config["nested"][0]["safe"] is True
    with pytest.raises(TypeError):
        req.config["new"] = "unsafe"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: FileEntry("invalid", PurePosixPath("../escape"), -1, "X" * 64),
        lambda: JobReceipt(True, "X" * 40, "X" * 64, SHA, SHA, {}, ({"mutable": True},)),
        lambda: JobRequest(True, "bad id", "match", PurePosixPath("../receipt"), PurePosixPath("C:/video"), {}),
        lambda: ProgressEvent(True, "bad id", -1, float("nan"), "bad/stage", "ok", datetime.now()),
        lambda: ResultBundle(True, "bad id", "match", "X" * 40, SHA, SHA, {}, {}, ({"mutable": True},)),
        lambda: CompletionReceipt(True, "bad id", "match", PurePosixPath("../result"), -1, "X" * 64, "X" * 40, SHA, datetime.now()),
        lambda: StreamIdentity(True, "X" * 64),
    ],
)
def test_direct_constructors_reject_invalid_values(factory):
    with pytest.raises(RemoteContractError):
        factory()


def test_direct_collection_construction_copies_and_requires_contract_items():
    rec = receipt_for()
    mutable_files = list(rec.files)
    rebuilt = JobReceipt(rec.schema_version, rec.source_commit, rec.manifest_sha256, rec.evidence_sha256, rec.job_request_sha256, rec.requested_runtime_options, mutable_files)
    mutable_files.clear()
    assert len(rebuilt.files) == len(rec.files)
    assert all(type(item) is FileEntry for item in rebuilt.files)
    assert all(rebuilt_item is not original_item for rebuilt_item, original_item in zip(rebuilt.files, rec.files, strict=False))
    with pytest.raises(RemoteContractError, match="FileEntry"):
        JobReceipt(rec.schema_version, rec.source_commit, rec.manifest_sha256, rec.evidence_sha256, rec.job_request_sha256, {}, ({"role": "manifest"},))
    result = result_for(receipt=rec); mutable_artifacts = list(result.artifacts)
    rebuilt_result = replace(result, artifacts=mutable_artifacts)
    mutable_artifacts.clear()
    assert rebuilt_result.artifacts == result.artifacts
    assert all(type(item) is FileEntry for item in rebuilt_result.artifacts)
    assert all(rebuilt_item is not original_item for rebuilt_item, original_item in zip(rebuilt_result.artifacts, result.artifacts, strict=False))


def test_each_direct_constructor_field_is_independently_validated():
    file_value = entry(); req = request(); rec = receipt_for(req); progress = _event(1, 10); result = result_for(req, rec)
    completion = CompletionReceipt.from_mapping(SCHEMAS[5][1]())
    invalid_values = [
        (file_value, {"role": "invalid"}), (file_value, {"relative_path": PurePosixPath("../x")}),
        (file_value, {"size_bytes": -1}), (file_value, {"sha256": "X" * 64}),
        (rec, {"schema_version": True}), (rec, {"source_commit": "X" * 40}), (rec, {"evidence_sha256": "X" * 64}),
        (req, {"schema_version": True}), (req, {"job_id": "bad id"}), (req, {"receipt_path": PurePosixPath("~/.ssh")}),
        (progress, {"schema_version": True}), (progress, {"sequence": -1}), (progress, {"progress": float("nan")}),
        (progress, {"timestamp": datetime.now()}), (result, {"receipt_sha256": "X" * 64}),
        (result, {"artifacts": ({"mutable": True},)}), (completion, {"result_path": PurePosixPath("../x")}),
        (completion, {"result_size_bytes": 0}), (completion, {"completed_at": datetime.now()}),
    ]
    for contract, change in invalid_values:
        with pytest.raises(RemoteContractError):
            replace(contract, **change)


def test_all_serialized_schema_key_sets_are_exact():
    values = [entry(), request(), receipt_for(), _event(1, 10), result_for(), CompletionReceipt.from_mapping(SCHEMAS[5][1]())]
    expected = [
        {"role", "relativePath", "sizeBytes", "sha256"},
        {"schemaVersion", "jobId", "matchId", "receiptPath", "inputVideoPath", "config"},
        {"schemaVersion", "sourceCommit", "manifestSha256", "evidenceSha256", "jobRequestSha256", "requestedRuntimeOptions", "files"},
        {"schemaVersion", "jobId", "sequence", "progress", "stage", "message", "timestamp"},
        {"schemaVersion", "jobId", "matchId", "sourceCommit", "manifestSha256", "receiptSha256", "requestedRuntimeOptions", "result", "artifacts"},
        {"schemaVersion", "jobId", "matchId", "resultPath", "resultSizeBytes", "resultSha256", "sourceCommit", "manifestSha256", "completedAt"},
    ]
    assert [set(value.to_mapping()) for value in values] == expected


class GuardedReader(io.BytesIO):
    def read(self, size=-1):
        assert 0 <= size <= 1024 * 1024
        return super().read(size)


class SecretFailingReader:
    def __init__(self, exception_type=OSError):
        self.exception_type = exception_type

    def read(self, size=-1):
        raise self.exception_type("DAYTONA_API_KEY=ultra-secret")


class TextReader:
    def __init__(self, value="DAYTONA_API_KEY=ultra-secret\n"):
        self.value = value

    def read(self, size=-1):
        return self.value


class HostileMapping(Mapping):
    def __init__(self, value, failure):
        self.value = value
        self.failure = failure

    def __iter__(self):
        if self.failure == "iter":
            raise RuntimeError("DAYTONA_API_KEY=hostile-mapping-secret")
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __getitem__(self, key):
        if self.failure == "getitem":
            raise RuntimeError("DAYTONA_API_KEY=hostile-mapping-secret")
        return self.value[key]

    def items(self):
        if self.failure == "items":
            raise RuntimeError("DAYTONA_API_KEY=hostile-mapping-secret")
        return super().items()


class HostileReadAttribute:
    def __getattribute__(self, name):
        if name == "read":
            raise RuntimeError("DAYTONA_API_KEY=hostile-reader-secret")
        return super().__getattribute__(name)


class HostilePath(os.PathLike):
    def __fspath__(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-path-secret")


class HostilePurePath(PurePosixPath):
    def as_posix(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-relative-secret")


class HostileList(list):
    def __iter__(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-sequence-secret")


class HostileStr(str):
    def __len__(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-scalar-secret")


class HostileInt(int):
    def __abs__(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-scalar-secret")


class HostileBytes(bytes):
    def __len__(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-scalar-secret")


class HostileComparisonInt(int):
    def _fail(self, *_args):
        raise RuntimeError("DAYTONA_API_KEY=hostile-bound-secret")

    __add__ = __radd__ = __lt__ = __le__ = __gt__ = __ge__ = __eq__ = __ne__ = _fail


class HostileComparisonStr(str):
    def __eq__(self, _other):
        raise RuntimeError("DAYTONA_API_KEY=hostile-bound-secret")

    def __ne__(self, _other):
        raise RuntimeError("DAYTONA_API_KEY=hostile-bound-secret")


class HostileFloat(float):
    def _fail(self, *_args):
        raise RuntimeError("DAYTONA_API_KEY=hostile-bound-secret")

    __lt__ = __le__ = __gt__ = __ge__ = __eq__ = __ne__ = _fail


class HostileDateTime(datetime):
    def utcoffset(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-datetime-secret")

    def isoformat(self, *args, **kwargs):
        raise RuntimeError("DAYTONA_API_KEY=hostile-datetime-secret")


class HostileTimezone(tzinfo):
    def utcoffset(self, _value):
        raise RuntimeError("DAYTONA_API_KEY=hostile-timezone-secret")

    def dst(self, _value):
        return None

    def tzname(self, _value):
        return "HOSTILE"


def assert_safe_contract_failure(operation, sentinel):
    with pytest.raises(RemoteContractError) as captured:
        operation()
    assert captured.value.__suppress_context__
    assert sentinel not in "".join(traceback.format_exception(captured.value))


class HostileFileEntry(FileEntry):
    def to_mapping(self):
        raise RuntimeError("DAYTONA_API_KEY=hostile-file-entry-secret")


@pytest.mark.parametrize("parent", ["receipt", "result"])
def test_direct_parent_schemas_reject_file_entry_subclasses_without_leaking(parent):
    rec = receipt_for()
    result = result_for(receipt=rec)
    original = rec.files[0] if parent == "receipt" else result.artifacts[0]
    hostile = HostileFileEntry(original.role, original.relative_path, original.size_bytes, original.sha256)
    if parent == "receipt":
        operation = lambda: replace(rec, files=(hostile, *rec.files[1:]))
    else:
        operation = lambda: replace(result, artifacts=(hostile, result.artifacts[1]))
    assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-file-entry-secret")


@pytest.mark.parametrize("parent", ["receipt", "result"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("relative_path", PurePosixPath("../x")),
        ("size_bytes", -1),
        ("sha256", "bad"),
    ],
)
def test_direct_parent_schemas_revalidate_forged_base_file_entries(parent, field, value):
    rec = receipt_for()
    result = result_for(receipt=rec)
    original = rec.files[0] if parent == "receipt" else result.artifacts[0]
    forged = object.__new__(FileEntry)
    for name in ("role", "relative_path", "size_bytes", "sha256"):
        object.__setattr__(forged, name, value if name == field else getattr(original, name))
    with pytest.raises(RemoteContractError):
        if parent == "receipt":
            replace(rec, files=(forged, *rec.files[1:]))
        else:
            replace(result, artifacts=(forged, result.artifacts[1]))


def test_direct_parent_schemas_reject_forged_cross_boundary_roles():
    receipt = receipt_for()
    result = result_for(receipt=receipt)
    forged_receipt_entry = object.__new__(FileEntry)
    for name, value in (
        ("role", "result_artifact"),
        ("relative_path", receipt.files[0].relative_path),
        ("size_bytes", receipt.files[0].size_bytes),
        ("sha256", receipt.files[0].sha256),
    ):
        object.__setattr__(forged_receipt_entry, name, value)
    with pytest.raises(RemoteContractError, match="input|receipt|role"):
        replace(receipt, files=(forged_receipt_entry, *receipt.files[1:]))

    forged_result_entry = object.__new__(FileEntry)
    for name, value in (
        ("role", "runtime_artifact"),
        ("relative_path", result.artifacts[0].relative_path),
        ("size_bytes", result.artifacts[0].size_bytes),
        ("sha256", result.artifacts[0].sha256),
    ):
        object.__setattr__(forged_result_entry, name, value)
    with pytest.raises(RemoteContractError, match="result_artifact"):
        replace(result, artifacts=(forged_result_entry, result.artifacts[1]))


def test_stream_identity_is_bounded_and_detects_mismatch():
    data = os.urandom(3 * 1024 * 1024 + 17)
    ident = stream_identity(GuardedReader(data))
    assert ident.size_bytes == len(data) and ident.sha256 == hashlib.sha256(data).hexdigest()
    with pytest.raises(RemoteContractError, match="size"):
        stream_identity(GuardedReader(data), expected_size=len(data) - 1)
    with pytest.raises(RemoteContractError, match="digest"):
        stream_identity(GuardedReader(data), expected_sha256=SHA)
    with pytest.raises(RemoteContractError, match="maximum"):
        stream_identity(GuardedReader(data), max_bytes=len(data) - 1)
    with pytest.raises(RemoteContractError):
        stream_identity(io.BytesIO(), max_bytes=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_size": HostileComparisonInt(1)},
        {"expected_sha256": HostileComparisonStr(hashlib.sha256(b"x").hexdigest())},
        {"max_bytes": HostileComparisonInt(1)},
    ],
    ids=["expected-size", "expected-digest", "maximum-size"],
)
def test_stream_identity_uses_normalized_scalar_bounds(kwargs):
    identity = stream_identity(io.BytesIO(b"x"), **kwargs)
    assert identity.size_bytes == 1


def test_canonical_byte_input_is_rejected_before_oversized_parsing():
    import backend.app.remote_contracts as module
    with pytest.raises(RemoteContractError, match="size"):
        load_canonical_json(memoryview(bytearray(module.MAX_RESULT_BYTES + 1)))


def test_canonical_encoder_stops_at_byte_budget_with_shared_strings(monkeypatch):
    import backend.app.remote_contracts as module
    shared = "x" * module.MAX_JSON_STRING
    value = [shared] * 10_000
    observed = [0]
    real_iterencode = module.json.JSONEncoder.iterencode

    def counted_iterencode(self, item, _one_shot=False):
        for chunk in real_iterencode(self, item, _one_shot):
            observed[0] += len(chunk.encode("utf-8"))
            yield chunk

    monkeypatch.setattr(module.json.JSONEncoder, "iterencode", counted_iterencode)
    with pytest.raises(RemoteContractError, match="size|limit"):
        canonical_json_bytes(value, max_bytes=1024)
    assert observed[0] <= 1024 + 6 * module.MAX_JSON_STRING + 16


def test_canonical_encoder_counts_utf8_escaping_and_trailing_newline_exactly():
    value = {"é": "\n😀"}
    expected = '{"é":"\\n😀"}\n'.encode("utf-8")
    assert canonical_json_bytes(value, max_bytes=len(expected)) == expected
    with pytest.raises(RemoteContractError, match="size|limit"):
        canonical_json_bytes(value, max_bytes=len(expected) - 1)


def test_canonical_encoder_rejects_oversized_keys_before_encoding():
    import backend.app.remote_contracts as module
    with pytest.raises(RemoteContractError, match="key|oversized|unsafe"):
        canonical_json_bytes({"k" * (module.MAX_JSON_STRING + 1): True})


def test_contract_size_caps_do_not_use_full_json_dumps(monkeypatch):
    import backend.app.remote_contracts as module
    shared = "x" * module.MAX_JSON_STRING
    req_value = request_mapping()
    req_value["config"] = {"values": [shared] * 10}
    rec_value = receipt_for().to_mapping()
    rec_value["requestedRuntimeOptions"] = {"values": [shared] * 10}
    result_value = result_for().to_mapping()
    result_value["requestedRuntimeOptions"] = {"values": [shared] * 70}
    operations = [
        lambda: JobRequest.from_mapping(req_value),
        lambda: JobReceipt.from_mapping(rec_value),
        lambda: ResultBundle.from_mapping(result_value),
    ]
    monkeypatch.setattr(module.json, "dumps", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("full dump must not run")))
    for operation in operations:
        with pytest.raises(RemoteContractError, match="size|limit"):
            operation()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"integer":' + b"7" * 5000 + b"}\n",
        b"[" * 20_000 + b"]" * 20_000 + b"\n",
    ],
    ids=["oversized-integer", "excessive-parser-depth"],
)
def test_canonical_loader_suppresses_parser_limit_failures(raw):
    sentinel = raw.rstrip(b"\n").decode()
    with pytest.raises(RemoteContractError) as captured:
        load_canonical_json(raw)
    assert captured.value.__suppress_context__
    assert sentinel not in "".join(traceback.format_exception(captured.value))


def _receipt_with_hostile_options():
    value = receipt_for().to_mapping()
    value["requestedRuntimeOptions"] = HostileMapping({"gpu": "A10"}, "items")
    return value


def _result_with_hostile_result():
    value = result_for().to_mapping()
    value["result"] = HostileMapping({"score": 0.5}, "items")
    return value


@pytest.mark.parametrize(
    "operation",
    [
        lambda: JobRequest.from_mapping(HostileMapping(request_mapping(), "iter")),
        lambda: JobRequest.from_mapping(HostileMapping(request_mapping(), "getitem")),
        lambda: JobReceipt.from_mapping(HostileMapping(receipt_for().to_mapping(), "iter")),
        lambda: JobRequest.from_mapping({**request_mapping(), "config": HostileMapping({"mode": "proof"}, "items")}),
        lambda: JobReceipt.from_mapping(_receipt_with_hostile_options()),
        lambda: ResultBundle.from_mapping(_result_with_hostile_result()),
        lambda: canonical_json_bytes(HostileMapping({"safe": True}, "items")),
    ],
    ids=["exact-iteration", "field-lookup", "receipt-ingress", "config-freeze", "receipt-options", "result-freeze", "canonical-freeze"],
)
def test_mapping_protocol_failures_are_credential_safe(operation):
    assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-mapping-secret")


@pytest.mark.parametrize(
    "operation",
    [
        lambda: load_canonical_json(HostileReadAttribute()),
        lambda: stream_identity(HostileReadAttribute()),
        lambda: validate_progress_jsonl(HostileReadAttribute(), expected_job_id="job-1"),
    ],
)
def test_stream_attribute_probe_failures_are_credential_safe(operation):
    assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-reader-secret")


def test_path_protocol_failures_are_credential_safe(tmp_path):
    operations = [
        lambda: load_canonical_json(HostilePath()),
        lambda: confined_path(HostilePath(), "result.json"),
        lambda: atomic_write_json(HostilePath(), "result.json", {"safe": True}),
    ]
    for operation in operations:
        assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-path-secret")


def test_relative_path_protocol_failures_are_credential_safe(tmp_path):
    value = entry().to_mapping()
    value["relativePath"] = HostilePurePath("result.json")
    operations = [
        lambda: FileEntry.from_mapping(value),
        lambda: confined_path(tmp_path, HostilePurePath("result.json")),
        lambda: atomic_write_json(tmp_path, HostilePurePath("result.json"), {"safe": True}),
    ]
    for operation in operations:
        assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-relative-secret")


def _receipt_with_hostile_files():
    value = receipt_for().to_mapping()
    value["files"] = HostileList(value["files"])
    return value


def _result_with_hostile_artifacts():
    value = result_for().to_mapping()
    value["artifacts"] = HostileList(value["artifacts"])
    return value


@pytest.mark.parametrize(
    "operation",
    [
        lambda: canonical_json_bytes(HostileList([{"safe": True}])),
        lambda: JobReceipt.from_mapping(_receipt_with_hostile_files()),
        lambda: ResultBundle.from_mapping(_result_with_hostile_artifacts()),
    ],
    ids=["canonical-json", "receipt-files", "result-artifacts"],
)
def test_sequence_protocol_failures_are_credential_safe(operation):
    assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-sequence-secret")


@pytest.mark.parametrize(
    "operation",
    [
        lambda: JobRequest.from_mapping({**request_mapping(), "jobId": HostileStr("job-1")}),
        lambda: canonical_json_bytes({"value": HostileStr("safe")}),
        lambda: canonical_json_bytes({"value": HostileInt(1)}),
        lambda: load_canonical_json(HostileBytes(b"{}\n")),
        lambda: redact_remote_diagnostics(HostileStr("safe")),
    ],
    ids=["schema-text", "json-text", "json-integer", "json-bytes", "diagnostic-text"],
)
def test_scalar_subclass_protocols_cannot_leak_credentials(operation):
    try:
        operation()
    except Exception as exc:
        assert isinstance(exc, RemoteContractError)
        assert "DAYTONA_API_KEY=hostile-scalar-secret" not in "".join(traceback.format_exception(exc))


@pytest.mark.parametrize(
    "operation",
    [
        lambda reader: load_canonical_json(reader),
        lambda reader: stream_identity(reader),
        lambda reader: validate_progress_jsonl(reader, expected_job_id="job-1"),
    ],
)
@pytest.mark.parametrize("exception_type", [OSError, RuntimeError])
def test_stream_read_failures_are_credential_safe(operation, exception_type):
    with pytest.raises(RemoteContractError) as captured:
        operation(SecretFailingReader(exception_type))
    assert "secret" not in str(captured.value).lower()
    assert "ultra-secret" not in "".join(traceback.format_exception(captured.value))


def test_canonical_loader_rejects_text_chunks_without_typeerror_or_secret_leak():
    with pytest.raises(RemoteContractError, match="bytes") as captured:
        load_canonical_json(TextReader())
    assert "ultra-secret" not in "".join(traceback.format_exception(captured.value))


@pytest.mark.parametrize(
    "operation",
    [
        lambda reader: load_canonical_json(reader),
        lambda reader: stream_identity(reader),
        lambda reader: validate_progress_jsonl(reader, expected_job_id="job-1"),
    ],
)
def test_empty_text_chunks_are_not_mistaken_for_binary_eof(operation):
    with pytest.raises(RemoteContractError, match="bytes"):
        operation(TextReader(""))


def test_path_and_confinement_errors_suppress_secret_context(tmp_path):
    sentinel = "DAYTONA_API_KEY=ultra-secret"
    operations = [
        lambda: load_canonical_json(tmp_path / f"{sentinel}.json"),
        lambda: confined_path(f"{sentinel}\0root", "x"),
    ]
    for operation in operations:
        with pytest.raises(RemoteContractError) as captured:
            operation()
        assert sentinel not in "".join(traceback.format_exception(captured.value))


def test_receipt_entries_duplicates_bindings_and_real_files(tmp_path):
    req = request(); rec = receipt_for(req)
    for item, content in zip(rec.files, (b"source", b"manifest", b"evidence", b"video", canonical_json_bytes(req.to_mapping())), strict=False):
        target = tmp_path / item.relative_path.as_posix(); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    receipt_target = tmp_path / req.receipt_path.as_posix(); receipt_target.parent.mkdir(parents=True); receipt_target.write_bytes(canonical_json_bytes(rec.to_mapping()))
    validate_receipt_files(tmp_path, req, rec)
    bad = rec.to_mapping(); bad["files"].append(bad["files"][0])
    with pytest.raises(RemoteContractError, match="duplicate"):
        JobReceipt.from_mapping(bad)
    bad = rec.to_mapping(); bad["files"][3]["relativePath"] = "other.mp4"
    with pytest.raises(RemoteContractError, match="input video"): validate_receipt_files(tmp_path, req, JobReceipt.from_mapping(bad))
    (tmp_path / "manifest.json").write_bytes(b"truncated")
    with pytest.raises(RemoteContractError, match="size|digest"): validate_receipt_files(tmp_path, req, rec)


def test_receipt_path_rejects_receipt_substitution(tmp_path):
    req = request(); rec = receipt_for(req)
    for item, content in zip(rec.files, (b"source", b"manifest", b"evidence", b"video", canonical_json_bytes(req.to_mapping())), strict=False):
        target = tmp_path / item.relative_path.as_posix(); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    target = tmp_path / req.receipt_path.as_posix(); target.parent.mkdir(parents=True); target.write_bytes(canonical_json_bytes({"substitute": True}))
    with pytest.raises(RemoteContractError, match="receipt.*mismatch"):
        validate_receipt_files(tmp_path, req, rec)


@pytest.mark.parametrize("expected,substitute", [(True, 1), (1, 1.0), (1.0, True)])
def test_receipt_payload_binding_is_type_exact_for_nested_json(tmp_path, expected, substitute):
    req = request()
    rec_value = receipt_for(req).to_mapping()
    rec_value["requestedRuntimeOptions"] = {"nested": [{"value": expected}]}
    rec = JobReceipt.from_mapping(rec_value)
    contents = (b"source", b"manifest", b"evidence", b"video", canonical_json_bytes(req.to_mapping()))
    for item, content in zip(rec.files, contents, strict=False):
        target = tmp_path / item.relative_path.as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    actual = rec.to_mapping()
    actual["requestedRuntimeOptions"]["nested"][0]["value"] = substitute
    receipt_target = tmp_path / req.receipt_path.as_posix()
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    receipt_target.write_bytes(canonical_json_bytes(actual))
    with pytest.raises(RemoteContractError, match="receipt.*mismatch"):
        validate_receipt_files(tmp_path, req, rec)


def test_receipt_requires_all_sealed_upload_singletons_and_nonempty_payloads():
    rec = receipt_for().to_mapping()
    rec["files"] = [item for item in rec["files"] if item["role"] != "source_archive"]
    with pytest.raises(RemoteContractError, match="required.*role"):
        JobReceipt.from_mapping(rec)
    value = entry("input_video", "input.mp4", b"x").to_mapping(); value["sizeBytes"] = 0
    with pytest.raises(RemoteContractError, match="positive"):
        FileEntry.from_mapping(value)


def test_confined_path_rejects_symlink_escape_and_destination_symlink(tmp_path):
    root = tmp_path / "root"; outside = tmp_path / "outside"; root.mkdir(); outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RemoteContractError, match="symlink"): confined_path(root, "link/file")
    destination = root / "result.json"; destination.symlink_to(outside / "stolen")
    with pytest.raises(RemoteContractError, match="symlink"): atomic_write_json(root, "result.json", {"ok": True})


@pytest.mark.parametrize("value", [PurePosixPath("C:/escape"), PurePosixPath("~/.ssh"), PurePosixPath(r"a\b")])
def test_confined_path_revalidates_pure_posix_path_lexically(tmp_path, value):
    with pytest.raises(RemoteContractError):
        confined_path(tmp_path, value)


def test_atomic_write_success_and_failure_cleanup(tmp_path, monkeypatch):
    atomic_write_json(tmp_path, "nested/result.json", {"b": 2, "a": 1})
    assert (tmp_path / "nested/result.json").read_bytes() == b'{"a":1,"b":2}\n'
    import backend.app.remote_contracts as module
    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(RemoteContractError, match="write"):
        atomic_write_json(tmp_path, "nested/new.json", {"x": 1})
    assert not (tmp_path / "nested/new.json").exists()
    assert not list((tmp_path / "nested").glob(".remote-contract-*.tmp"))


def test_atomic_write_suppresses_secret_filesystem_exception_context(tmp_path, monkeypatch):
    import backend.app.remote_contracts as module
    sentinel = "DAYTONA_API_KEY=ultra-secret"
    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(OSError(sentinel)))
    with pytest.raises(RemoteContractError) as captured:
        atomic_write_json(tmp_path, "result.json", {"ok": True})
    assert sentinel not in "".join(traceback.format_exception(captured.value))
    assert not (tmp_path / "result.json").exists()
    assert not list(tmp_path.glob(".remote-contract-*.tmp"))


def test_atomic_write_rolls_back_published_destination_after_directory_fsync_failure(tmp_path, monkeypatch):
    import backend.app.remote_contracts as module
    real_open = module.os.open
    real_fsync = module.os.fsync
    directory_fds = []
    fsync_calls = [0]

    def capture_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        directory_fds.append(fd)
        return fd

    def fail_publish_fsync(fd):
        fsync_calls[0] += 1
        if fsync_calls[0] % 3 == 2:
            raise OSError("DAYTONA_API_KEY=directory-fsync-secret")
        return real_fsync(fd)

    monkeypatch.setattr(module.os, "open", capture_open)
    monkeypatch.setattr(module.os, "fsync", fail_publish_fsync)
    for index in range(3):
        destination = tmp_path / f"result-{index}.json"
        assert_safe_contract_failure(
            lambda destination=destination: atomic_write_json(tmp_path, destination.name, {"safe": True}),
            "DAYTONA_API_KEY=directory-fsync-secret",
        )
        assert not destination.exists()
        assert not list(tmp_path.glob(".remote-contract-*.tmp"))
    for fd in directory_fds:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_atomic_write_reports_indeterminate_failure_when_published_cleanup_cannot_be_confirmed(tmp_path, monkeypatch):
    import backend.app.remote_contracts as module
    sentinel = "DAYTONA_API_KEY=published-cleanup-secret"
    destination = tmp_path / "result.json"
    real_fsync = module.os.fsync
    real_unlink = module.Path.unlink
    fsync_calls = [0]

    def fail_directory_fsync(fd):
        fsync_calls[0] += 1
        if fsync_calls[0] == 2:
            raise OSError(sentinel)
        return real_fsync(fd)

    def fail_destination_unlink(path, *args, **kwargs):
        if path == destination:
            raise OSError(sentinel)
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "fsync", fail_directory_fsync)
    monkeypatch.setattr(module.Path, "unlink", fail_destination_unlink)
    with pytest.raises(RemoteContractError, match="indeterminate|published|cleanup") as captured:
        atomic_write_json(tmp_path, destination.name, {"safe": True})
    assert captured.value.__suppress_context__
    assert sentinel not in "".join(traceback.format_exception(captured.value))
    assert destination.exists()
    assert not list(tmp_path.glob(".remote-contract-*.tmp"))


@pytest.mark.parametrize("failure_type", [RuntimeError, MemoryError])
@pytest.mark.parametrize("stage", ["fchmod", "fdopen"])
def test_atomic_write_closes_unowned_descriptor_on_setup_failure(tmp_path, monkeypatch, stage, failure_type):
    import backend.app.remote_contracts as module
    sentinel = "DAYTONA_API_KEY=atomic-fd-secret"
    real_mkstemp = module.tempfile.mkstemp
    captured = []

    def capture_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        captured.append(fd)
        return fd, name

    monkeypatch.setattr(module.tempfile, "mkstemp", capture_mkstemp)
    monkeypatch.setattr(module.os, stage, lambda *_args, **_kwargs: (_ for _ in ()).throw(failure_type(sentinel)))

    for index in range(3):
        with pytest.raises(RemoteContractError) as failure:
            atomic_write_json(tmp_path, f"result-{index}.json", {"safe": True})
        assert sentinel not in "".join(traceback.format_exception(failure.value))
        with pytest.raises(OSError):
            os.fstat(captured[-1])
        assert not list(tmp_path.glob(".remote-contract-*.tmp"))


@pytest.mark.parametrize("stage", ["write", "fsync"])
def test_atomic_write_owned_descriptor_is_closed_on_io_failure(tmp_path, monkeypatch, stage):
    import backend.app.remote_contracts as module
    sentinel = "DAYTONA_API_KEY=atomic-io-secret"
    real_fdopen = module.os.fdopen
    captured = []

    class FailingWriter:
        def __init__(self, fd):
            self.handle = real_fdopen(fd, "wb")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.handle.close()

        def write(self, _payload):
            if stage == "write":
                raise RuntimeError(sentinel)
            return self.handle.write(_payload)

        def flush(self):
            return self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    def failing_fdopen(fd, _mode):
        captured.append(fd)
        return FailingWriter(fd)

    monkeypatch.setattr(module.os, "fdopen", failing_fdopen)
    if stage == "fsync":
        monkeypatch.setattr(module.os, "fsync", lambda *_args: (_ for _ in ()).throw(RuntimeError(sentinel)))

    with pytest.raises(RemoteContractError) as failure:
        atomic_write_json(tmp_path, "result.json", {"safe": True})
    assert sentinel not in "".join(traceback.format_exception(failure.value))
    with pytest.raises(OSError):
        os.fstat(captured[-1])
    assert not list(tmp_path.glob(".remote-contract-*.tmp"))


def _event(seq, progress, job="job-1"):
    return ProgressEvent.from_mapping({"schemaVersion": 1, "jobId": job, "sequence": seq, "progress": progress, "stage": "run", "message": "ok", "timestamp": f"2026-08-24T12:30:{seq:02d}Z"})


@pytest.mark.parametrize("progress", [HostileComparisonInt(10), HostileFloat(10.5)], ids=["integer", "float"])
def test_progress_normalizes_numeric_subclasses(progress):
    event = ProgressEvent(1, "job-1", 1, progress, "run", "ok", NOW)
    assert type(event.progress) is (int if isinstance(progress, int) else float)
    assert type(event.to_mapping()["progress"]) is type(event.progress)


def test_datetime_subclasses_are_normalized_without_protocol_calls():
    hostile = HostileDateTime(2026, 8, 24, 12, 30, tzinfo=timezone.utc)
    event = ProgressEvent(1, "job-1", 1, 10, "run", "ok", hostile)
    completion = CompletionReceipt(1, "job-1", "match-1", PurePosixPath(RESULT_PATH), 1, SHA, COMMIT, SHA, hostile)
    assert type(event.timestamp) is datetime
    assert type(completion.completed_at) is datetime
    assert event.to_mapping()["timestamp"] == "2026-08-24T12:30:00Z"
    assert completion.to_mapping()["completedAt"] == "2026-08-24T12:30:00Z"


def test_direct_utc_datetimes_normalize_fold_for_canonical_round_trip():
    folded = NOW.replace(fold=1)
    event = ProgressEvent(1, "job-1", 1, 10, "run", "ok", folded)
    completion = CompletionReceipt(1, "job-1", "match-1", PurePosixPath(RESULT_PATH), 1, SHA, COMMIT, SHA, folded)
    event_round_trip = ProgressEvent.from_mapping(load_canonical_json(canonical_json_bytes(event.to_mapping())))
    completion_round_trip = CompletionReceipt.from_mapping(load_canonical_json(canonical_json_bytes(completion.to_mapping())))
    assert event.timestamp.fold == event_round_trip.timestamp.fold == 0
    assert completion.completed_at.fold == completion_round_trip.completed_at.fold == 0
    assert event == event_round_trip
    assert completion == completion_round_trip


def test_datetime_timezone_protocol_failures_are_credential_safe():
    hostile = datetime(2026, 8, 24, 12, 30, tzinfo=HostileTimezone())
    operations = [
        lambda: ProgressEvent(1, "job-1", 1, 10, "run", "ok", hostile),
        lambda: CompletionReceipt(1, "job-1", "match-1", PurePosixPath(RESULT_PATH), 1, SHA, COMMIT, SHA, hostile),
    ]
    for operation in operations:
        assert_safe_contract_failure(operation, "DAYTONA_API_KEY=hostile-timezone-secret")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_job_id": HostileComparisonStr("job-1")},
        {"expected_job_id": "job-1", "max_total_bytes": HostileComparisonInt(200)},
        {"expected_job_id": "job-1", "max_line_bytes": HostileComparisonInt(200)},
        {"expected_job_id": "job-1", "max_events": HostileComparisonInt(1)},
    ],
    ids=["expected-job", "total-bytes", "line-bytes", "event-count"],
)
def test_progress_validator_uses_normalized_scalar_bounds(kwargs):
    raw = canonical_json_bytes(_event(1, 10).to_mapping())
    events = validate_progress_jsonl(io.BytesIO(raw), **kwargs)
    assert len(events) == 1


def test_progress_jsonl_streaming_validation_and_limits():
    raw = b"".join(canonical_json_bytes(_event(i, i * 10).to_mapping()) for i in range(1, 4))
    assert len(validate_progress_jsonl(GuardedReader(raw), expected_job_id="job-1")) == 3
    for events, match in [([_event(1, 20), _event(2, 10)], "progress"), ([_event(1, 10), _event(1, 20)], "sequence"), ([_event(1, 10), _event(2, 20, "other")], "job")]:
        with pytest.raises(RemoteContractError, match=match): validate_progress_jsonl(io.BytesIO(b"".join(canonical_json_bytes(x.to_mapping()) for x in events)), expected_job_id="job-1")
    with pytest.raises(RemoteContractError, match="newline"): validate_progress_jsonl(io.BytesIO(raw.rstrip(b"\n")), expected_job_id="job-1")
    with pytest.raises(RemoteContractError, match="event count"): validate_progress_jsonl(io.BytesIO(raw), expected_job_id="job-1", max_events=2)
    with pytest.raises(RemoteContractError, match="line"): validate_progress_jsonl(io.BytesIO(b"{" + b"x" * 100 + b"}\n"), expected_job_id="job-1", max_line_bytes=50)
    with pytest.raises(RemoteContractError, match="total"): validate_progress_jsonl(io.BytesIO(raw), expected_job_id="job-1", max_total_bytes=10)


def test_result_and_completion_cross_bind_every_identity(tmp_path):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    validate_result(req, rec, result)
    for field in ("jobId", "matchId", "sourceCommit", "manifestSha256", "receiptSha256"):
        value = result.to_mapping(); value[field] = ("c" * (40 if field == "sourceCommit" else 64)) if "Commit" in field or "Sha" in field else "substitute"
        with pytest.raises(RemoteContractError, match="mismatch"): validate_result(req, rec, ResultBundle.from_mapping(value))
    target = tmp_path / RESULT_PATH; target.parent.mkdir(parents=True); target.write_bytes(canonical_json_bytes(result.to_mapping()))
    write_result_artifacts(tmp_path, result)
    ident = stream_identity(target.open("rb"))
    completion = CompletionReceipt.from_mapping({"schemaVersion": 1, "jobId": req.job_id, "matchId": req.match_id, "resultPath": RESULT_PATH, "resultSizeBytes": ident.size_bytes, "resultSha256": ident.sha256, "sourceCommit": rec.source_commit, "manifestSha256": rec.manifest_sha256, "completedAt": "2026-08-24T12:30:00Z"})
    validate_completion(tmp_path, req, rec, result, completion)
    bad = completion.to_mapping(); bad["resultSha256"] = SHA
    with pytest.raises(RemoteContractError, match="digest|mismatch"): validate_completion(tmp_path, req, rec, result, CompletionReceipt.from_mapping(bad))


def test_completion_uses_one_bounded_snapshot_for_identity_and_payload(tmp_path, monkeypatch):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    write_result_artifacts(tmp_path, result)
    result_path = tmp_path / RESULT_PATH
    old_bytes = canonical_json_bytes({"old": True})
    expected_bytes = canonical_json_bytes(result.to_mapping())
    result_path.write_bytes(old_bytes)
    replacement = tmp_path / "outputs/replacement.json"
    replacement.write_bytes(expected_bytes)
    old_identity = stream_identity(io.BytesIO(old_bytes))
    completion = CompletionReceipt.from_mapping({
        "schemaVersion": 1, "jobId": req.job_id, "matchId": req.match_id,
        "resultPath": RESULT_PATH, "resultSizeBytes": old_identity.size_bytes,
        "resultSha256": old_identity.sha256, "sourceCommit": rec.source_commit,
        "manifestSha256": rec.manifest_sha256, "completedAt": "2026-08-24T12:30:00Z",
    })
    real_open = Path.open
    target_opens = [0]

    def swapping_open(path, *args, **kwargs):
        handle = real_open(path, *args, **kwargs)
        if path == result_path:
            target_opens[0] += 1
            if target_opens[0] == 1:
                os.replace(replacement, result_path)
        return handle

    monkeypatch.setattr(Path, "open", swapping_open)
    with pytest.raises(RemoteContractError, match="result payload mismatch"):
        validate_completion(tmp_path, req, rec, result, completion)
    assert target_opens[0] == 1


@pytest.mark.parametrize("result_path", [
    f"outputs/result.json.generations/{'f' * 32}/result.json",
    f"outputs/other-result.json.generations/{GENERATION}/result.json",
])
def test_completion_must_bind_to_both_result_artifact_generations(tmp_path, result_path):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    write_result_artifacts(tmp_path, result)
    result_bytes = canonical_json_bytes(result.to_mapping())
    target = tmp_path / result_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result_bytes)
    completion = completion_for(req, rec, result_bytes, result_path)
    with pytest.raises(RemoteContractError, match="generation"):
        validate_completion(tmp_path, req, rec, result, completion)


@pytest.mark.parametrize("validation", ["receipt", "result"])
def test_match_config_and_runtime_options_are_distinct_sealed_contracts(tmp_path, validation):
    req_value = request_mapping()
    req_value["config"] = {
        "attackDirection": "right_to_left",
        "manualHomographyPoints": [],
        "myTeamCluster": 2,
        "llmProvider": "local",
        "autoHomography": False,
    }
    req = JobRequest.from_mapping(req_value)
    rec_value = receipt_for(req).to_mapping()
    rec_value["requestedRuntimeOptions"] = {
        "primary_model": {"artifactId": "primary-model"},
        "auxiliary_ball_model": None,
        "auxiliary_ball_model_profile": None,
        "primary_acquisition_mode": "anchored_player_ranked_context_960",
        "edge_share_repair_profile": None,
        "baseline_guided_rescue_reference": None,
        "proposal_selection_truth_seed": None,
        "reviewed_positive_anchor_seed": None,
    }
    rec = JobReceipt.from_mapping(rec_value)
    if validation == "result":
        validate_result(req, rec, result_for(req, rec))
        return
    contents = (b"source", b"manifest", b"evidence", b"video", canonical_json_bytes(req.to_mapping()))
    for item, content in zip(rec.files, contents, strict=False):
        target = tmp_path / item.relative_path.as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    receipt_target = tmp_path / req.receipt_path.as_posix()
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    receipt_target.write_bytes(canonical_json_bytes(rec.to_mapping()))
    validate_receipt_files(tmp_path, req, rec)


def test_match_config_substitution_without_new_request_digest_is_rejected(tmp_path):
    req = request()
    rec = receipt_for(req)
    contents = (b"source", b"manifest", b"evidence", b"video", canonical_json_bytes(req.to_mapping()))
    for item, content in zip(rec.files, contents, strict=False):
        target = tmp_path / item.relative_path.as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    receipt_target = tmp_path / req.receipt_path.as_posix()
    receipt_target.parent.mkdir(parents=True, exist_ok=True)
    receipt_target.write_bytes(canonical_json_bytes(rec.to_mapping()))
    substituted = req.to_mapping()
    substituted["config"] = {"attackDirection": "right_to_left"}
    with pytest.raises(RemoteContractError, match="request.*identity|request.*mismatch"):
        validate_receipt_files(tmp_path, JobRequest.from_mapping(substituted), rec)


@pytest.mark.parametrize("expected,substitute", [(True, 1), (1, 1.0), (1.0, True)])
def test_result_runtime_options_binding_is_type_exact(expected, substitute):
    req = request()
    rec_value = receipt_for(req).to_mapping()
    rec_value["requestedRuntimeOptions"] = {"nested": [{"value": expected}]}
    rec = JobReceipt.from_mapping(rec_value)
    result_value = result_for(req, rec).to_mapping()
    result_value["requestedRuntimeOptions"]["nested"][0]["value"] = substitute
    with pytest.raises(RemoteContractError, match="options.*mismatch|identity.*mismatch"):
        validate_result(req, rec, ResultBundle.from_mapping(result_value))


def test_completion_result_payload_binding_is_exact(tmp_path):
    req = request()
    rec = receipt_for(req)
    result = result_for(req, rec)
    write_result_artifacts(tmp_path, result)
    actual = result.to_mapping()
    actual["result"]["processorResultPath"] = "outputs/substituted.json"
    result_path = tmp_path / RESULT_PATH
    result_path.write_bytes(canonical_json_bytes(actual))
    identity = stream_identity(result_path.open("rb"))
    completion = CompletionReceipt.from_mapping({
        "schemaVersion": 1,
        "jobId": req.job_id,
        "matchId": req.match_id,
        "resultPath": RESULT_PATH,
        "resultSizeBytes": identity.size_bytes,
        "resultSha256": identity.sha256,
        "sourceCommit": rec.source_commit,
        "manifestSha256": rec.manifest_sha256,
        "completedAt": "2026-08-24T12:30:00Z",
    })
    with pytest.raises(RemoteContractError, match="result payload mismatch"):
        validate_completion(tmp_path, req, rec, result, completion)


def test_result_rejects_any_receipt_substitution_and_completion_checks_artifacts(tmp_path):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    substituted_mapping = rec.to_mapping()
    substituted_mapping["evidenceSha256"] = "c" * 64
    for item in substituted_mapping["files"]:
        if item["role"] == "evidence": item["sha256"] = "c" * 64
    substituted = JobReceipt.from_mapping(substituted_mapping)
    with pytest.raises(RemoteContractError, match="receipt.*mismatch"):
        validate_result(req, substituted, result)
    result_path = tmp_path / RESULT_PATH; result_path.parent.mkdir(parents=True); result_path.write_bytes(canonical_json_bytes(result.to_mapping()))
    ident = stream_identity(result_path.open("rb"))
    completion = CompletionReceipt.from_mapping({"schemaVersion": 1, "jobId": req.job_id, "matchId": req.match_id, "resultPath": RESULT_PATH, "resultSizeBytes": ident.size_bytes, "resultSha256": ident.sha256, "sourceCommit": rec.source_commit, "manifestSha256": rec.manifest_sha256, "completedAt": "2026-08-24T12:30:00Z"})
    with pytest.raises(RemoteContractError, match="artifact"):
        validate_completion(tmp_path, req, rec, result, completion)


@pytest.mark.parametrize("result_key", ["processorResultPath", "progressPath"])
def test_result_artifact_identities_are_checked(tmp_path, result_key):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    write_result_artifacts(tmp_path, result)
    validate_result(req, rec, result, output_root=tmp_path)
    target = tmp_path / result.result[result_key]
    target.write_bytes(b"wrong")
    with pytest.raises(RemoteContractError, match="size|digest"): validate_result(req, rec, result, output_root=tmp_path)


@pytest.mark.parametrize("result_key", ["processorResultPath", "progressPath"])
def test_result_artifact_paths_must_exist_under_output_root(tmp_path, result_key):
    req = request(); rec = receipt_for(req); result = result_for(req, rec)
    write_result_artifacts(tmp_path, result)
    (tmp_path / result.result[result_key]).unlink()
    with pytest.raises(RemoteContractError, match="artifact"):
        validate_result(req, rec, result, output_root=tmp_path)


def test_validate_result_binds_progress_event_count_to_jsonl(tmp_path):
    req = request(); rec = receipt_for(req)
    payload = progress_bytes(_event(1, 10).to_mapping(), _event(2, 100).to_mapping())
    result = result_for(req, rec, progress=payload, progress_count=2)
    write_result_artifacts(tmp_path, result, progress=payload)
    validate_result(req, rec, result, output_root=tmp_path)

    mismatched = replace(result, result={**result.result, "progressEventCount": 1})
    with pytest.raises(RemoteContractError, match="progress.*count"):
        validate_result(req, rec, mismatched, output_root=tmp_path)


def test_validate_result_reads_progress_identity_and_content_from_one_snapshot(tmp_path, monkeypatch):
    req = request(); rec = receipt_for(req)
    payload = progress_bytes(_event(1, 100).to_mapping())
    result = result_for(req, rec, progress=payload, progress_count=1)
    write_result_artifacts(tmp_path, result, progress=payload)
    progress_path = tmp_path / result.result["progressPath"]
    real_open = Path.open
    progress_opens = 0

    def tracked_open(path, *args, **kwargs):
        nonlocal progress_opens
        if path == progress_path and (args[0] if args else kwargs.get("mode", "r")) == "rb":
            progress_opens += 1
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracked_open)
    validate_result(req, rec, result, output_root=tmp_path)
    assert progress_opens == 1


@pytest.mark.parametrize(
    "payload,count",
    [
        (b"not-json\n", 1),
        (
            json.dumps(_event(1, 10).to_mapping(), separators=(", ", ": ")).encode() + b"\n",
            1,
        ),
        (
            progress_bytes({**_event(1, 10).to_mapping(), "message": "API_KEY=secret"}),
            1,
        ),
        (
            progress_bytes({**_event(1, 10).to_mapping(), "jobId": "other-job"}),
            1,
        ),
        (
            progress_bytes(_event(2, 50).to_mapping(), _event(1, 100).to_mapping()),
            2,
        ),
    ],
    ids=["bad-json", "noncanonical", "credential", "wrong-job", "nonmonotonic"],
)
def test_validate_result_rejects_invalid_progress_jsonl(tmp_path, payload, count):
    req = request(); rec = receipt_for(req)
    result = result_for(req, rec, progress=payload, progress_count=count)
    write_result_artifacts(tmp_path, result, progress=payload)
    with pytest.raises(RemoteContractError):
        validate_result(req, rec, result, output_root=tmp_path)


def test_validate_result_bounds_progress_snapshot(tmp_path):
    req = request(); rec = receipt_for(req)
    payload = b"x" * (MAX_PROGRESS_TOTAL_BYTES + 1)
    result = result_for(req, rec, progress=payload, progress_count=1)
    write_result_artifacts(tmp_path, result, progress=payload)
    with pytest.raises(RemoteContractError, match="maximum|total|size"):
        validate_result(req, rec, result, output_root=tmp_path)


def test_completion_inherits_progress_event_count_validation(tmp_path):
    req = request(); rec = receipt_for(req)
    payload = progress_bytes(_event(1, 100).to_mapping())
    result = result_for(req, rec, progress=payload, progress_count=0)
    write_result_artifacts(tmp_path, result, progress=payload)
    result_path = tmp_path / RESULT_PATH
    result_path.write_bytes(canonical_json_bytes(result.to_mapping()))
    identity = stream_identity(result_path.open("rb"))
    completion = CompletionReceipt.from_mapping({
        "schemaVersion": 1,
        "jobId": req.job_id,
        "matchId": req.match_id,
        "resultPath": RESULT_PATH,
        "resultSizeBytes": identity.size_bytes,
        "resultSha256": identity.sha256,
        "sourceCommit": rec.source_commit,
        "manifestSha256": rec.manifest_sha256,
        "completedAt": "2026-08-24T12:30:00Z",
    })
    with pytest.raises(RemoteContractError, match="progress.*count"):
        validate_completion(tmp_path, req, rec, result, completion)


def test_credentials_are_recursively_redacted_without_unsafe_stringification():
    class Dangerous:
        def __str__(self): raise AssertionError("must not stringify")
    value = {"DAYTONA_API_KEY": "abc", "authorization": "Bearer xyz", "nested": [{"accessToken": "secret", "safe": "x" * 1000}], "object": Dangerous()}
    clean = redact_remote_diagnostics(value, max_output_chars=180)
    rendered = json.dumps(clean)
    assert "abc" not in rendered and "xyz" not in rendered and "secret" not in rendered
    assert "[REDACTED]" in rendered and len(rendered) <= 180


@pytest.mark.parametrize(
    "payload",
    [
        {"clientSecret": "value"},
        {"DBPassword": "value"},
        {"sessionCookie": "value"},
        {"nested": [{"accessToken": "value"}]},
        {"safe": "authorization: Bearer value"},
        {"safe": ["api_key=value"]},
    ],
)
def test_hardened_credential_detector_matches_redaction_families(payload):
    assert remote_diagnostics_contain_credentials(payload) is True


@pytest.mark.parametrize(
    "key",
    [
        "apiKey",
        "API_KEY",
        "awsSecretAccessKey",
        "AWS_SECRET_ACCESS_KEY",
        "secretAccessKey",
        "stripeSecretKey",
        "privateKey",
        "ACCESS_KEY_ID",
        "OAuthToken",
        "refresh_token",
        "authorizationHeader",
        "CLIENT_SECRET",
        "DBPassword",
        "sessionCookie",
        "serviceCredential",
    ],
)
def test_hardened_credential_detector_covers_key_case_and_separator_families(key):
    assert remote_diagnostics_contain_credentials({"nested": [{key: "value"}]}) is True


@pytest.mark.parametrize(
    "text",
    [
        "authorization: Bearer value",
        "api_key=value",
        "awsSecretAccessKey=value",
        "secretAccessKey: value",
        "stripeSecretKey=value",
        "privateKey: value",
        "accessKeyId=value",
        "Set-Cookie=session-value",
        "password: value",
    ],
)
def test_hardened_credential_detector_covers_secret_bearing_text(text):
    assert remote_diagnostics_contain_credentials({"safeKey": [text]}) is True


@pytest.mark.parametrize(
    "secret_value",
    [
        "awsSecretAccessKey=compound-secret-sentinel",
        "secretAccessKey: compound-secret-sentinel",
        "stripeSecretKey=compound-secret-sentinel",
        "privateKey: compound-secret-sentinel",
        "accessKeyId=compound-secret-sentinel",
    ],
)
def test_redaction_removes_compound_secret_key_assignments(secret_value):
    rendered = json.dumps(redact_remote_diagnostics({"message": secret_value}))
    assert "compound-secret-sentinel" not in rendered
    assert "[REDACTED]" in rendered


def test_hardened_credential_detector_accepts_safe_nested_json():
    assert remote_diagnostics_contain_credentials({
        "client": {
            "passwordPolicy": "strict",
            "tokenCount": 3,
            "cookiePreferences": "essential-only",
            "publicKey": "visible",
            "keyboard": "visible",
            "monkey": "visible",
        },
        "items": [1, True, "authorization policy enabled"],
    }) is False


def test_redaction_removes_secret_values_and_secret_bearing_keys_and_bounds_sequences():
    class HostileSequence(Sequence):
        def __len__(self): return 10**9
        def __getitem__(self, index):
            if index > 2: raise RuntimeError("token=iteration-secret")
            return ("safe", "Authorization: Bearer ultra-secret-token", "api_key=plain-secret")[index]
    clean = redact_remote_diagnostics({"token=leaked-key-material": "value", "mixed": HostileSequence()}, max_output_chars=120)
    rendered = json.dumps(clean)
    for leaked in ("leaked-key-material", "ultra-secret-token", "plain-secret", "iteration-secret"):
        assert leaked not in rendered
    assert len(rendered) <= 120 and "[REDACTED]" in rendered


@pytest.mark.parametrize(
    "secret_value",
    [
        "token=plain-secret",
        "refresh_token=plain-secret",
        "auth_token: plain-secret",
        "ToKeN : plain-secret",
        "REFRESH-TOKEN = plain-secret",
    ],
)
def test_redaction_removes_generic_token_assignments_in_harmless_fields(secret_value):
    rendered = json.dumps(redact_remote_diagnostics({"message": secret_value, "safe": "tokenizer ready", "tokenizer": "ready"}))
    assert "plain-secret" not in rendered
    assert "[REDACTED]" in rendered
    assert "tokenizer ready" in rendered
    assert '"tokenizer": "ready"' in rendered


@pytest.mark.parametrize(
    "secret_value",
    [
        "auth=plain-secret",
        "credential=plain-secret",
        "CREDENTIALS : plain-secret",
        "passwd=plain-secret",
        "PASS_WORD : plain-secret",
        "cookie=plain-secret",
        "Set-Cookie: plain-secret",
    ],
)
def test_redaction_removes_common_credential_assignments(secret_value):
    clean = redact_remote_diagnostics({"message": secret_value, "credentials": "also-secret"})
    rendered = json.dumps(clean)
    assert "plain-secret" not in rendered and "also-secret" not in rendered
    assert "credentials" not in rendered.lower()
    assert "[REDACTED]" in rendered


def test_redaction_preserves_credential_like_but_harmless_words():
    values = ["tokenizer", "secretary", "authentic", "mytokenvalue"]
    clean = redact_remote_diagnostics({value: value for value in values})
    rendered = json.dumps(clean)
    assert all(value in rendered for value in values)


@pytest.mark.parametrize("value", [10**5000, -(10**5000)], ids=["positive", "negative"])
def test_redaction_replaces_oversized_integers_with_json_safe_marker(value):
    clean = redact_remote_diagnostics({"message": "safe", "n": value})
    rendered = json.dumps(clean)
    assert "OVERSIZED_INTEGER" in rendered
    assert len(rendered) <= 8192


def test_redaction_suppresses_final_serialization_failures(monkeypatch):
    import backend.app.remote_contracts as module
    sentinel = "DAYTONA_API_KEY=ultra-secret"
    with monkeypatch.context() as patcher:
        patcher.setattr(module.json, "dumps", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError(sentinel)))
        clean = redact_remote_diagnostics({"message": "safe"})
    assert clean == "[REDACTED]"


@pytest.mark.parametrize(
    "credential_key",
    [
        "clientSecret",
        "clientAPIKey",
        "HTTPAuthorization",
        "JWTToken",
        "APIToken",
        "DBPassword",
        "XAPIKey",
        "authorizationHeader",
        "JWTTOKEN",
        "DBPASSWORD",
        "SESSIONCOOKIE",
        "USERCREDENTIALS",
        "CLIENTSECRET",
        "AUTHENTICATIONHEADER",
        "BEARERTOKEN",
        "client_secret",
        "client-secret",
        "clientPassword",
        "databasePassword",
        "sessionCookie",
        "userCredentials",
        "oauthToken",
        "githubToken",
        "bearerToken",
        "awsSecretAccessKey",
        "AWS_SECRET_ACCESS_KEY",
        "secretAccessKey",
        "stripeSecretKey",
        "privateKey",
        "ACCESS_KEY_ID",
    ],
)
def test_redaction_recognizes_prefixed_and_camelcase_credential_keys(credential_key):
    sentinel = "ultra-secret-key-material"
    clean = redact_remote_diagnostics({"nested": [{credential_key: sentinel}]})
    rendered = json.dumps(clean)
    assert sentinel not in rendered and credential_key not in rendered
    assert "[REDACTED_KEY]" in rendered and "[REDACTED]" in rendered


def test_redaction_suffix_key_detection_preserves_benign_boundaries():
    benign = [
        "tokenizer",
        "secretary",
        "authentic",
        "mytokenvalue",
        "cookieCutter",
        "passwordless",
        "TOKENIZER",
        "SECRETARY",
        "AUTHENTIC",
        "MYTOKENVALUE",
        "COOKIECUTTER",
        "PASSWORDLESS",
        "publicKey",
        "PUBLIC_KEY",
        "keyboard",
        "KEYBOARD",
        "monkey",
        "MONKEY",
    ]
    rendered = json.dumps(redact_remote_diagnostics({key: "visible" for key in benign}))
    assert all(key in rendered for key in benign)
    assert rendered.count("visible") == len(benign)


def test_redaction_never_reads_attacker_controlled_type_name():
    sentinel = "DAYTONA_API_KEY_ultra_secret"
    credential_named = type(sentinel, (), {})()

    class HostileMeta(type):
        def __getattribute__(cls, name):
            if name == "__name__":
                raise RuntimeError(sentinel)
            return super().__getattribute__(name)

    class Hostile(metaclass=HostileMeta):
        pass

    try:
        clean = redact_remote_diagnostics({"first": credential_named, "second": Hostile()})
    except Exception as exc:
        assert sentinel not in "".join(traceback.format_exception(exc))
        pytest.fail("redaction inspected attacker-controlled type metadata")
    rendered = json.dumps(clean)
    assert sentinel not in rendered
    assert rendered.count("[UNSUPPORTED]") == 2


def test_receipt_file_limit_and_exact_result_artifact_count():
    rec = receipt_for().to_mapping()
    rec["files"].extend(entry("runtime_artifact", f"runtime/{index}.bin", b"").to_mapping() for index in range(MAX_FILES - len(rec["files"])))
    accepted = JobReceipt.from_mapping(rec)
    assert JobReceipt.from_mapping(load_canonical_json(canonical_json_bytes(accepted.to_mapping()))) == accepted
    rec["files"].append(entry("runtime_artifact", "runtime/overflow.bin", b"").to_mapping())
    with pytest.raises(RemoteContractError, match="bounded"):
        JobReceipt.from_mapping(rec)
    result = result_for()
    assert ResultBundle.from_mapping(load_canonical_json(canonical_json_bytes(result.to_mapping()))) == result
    value = result.to_mapping()
    value["artifacts"].append(entry("result_artifact", "outputs/extra.bin", b"").to_mapping())
    with pytest.raises(RemoteContractError, match="exactly two"):
        ResultBundle.from_mapping(value)


def test_progress_bounds_and_text_limits():
    value = _event(1, 1).to_mapping()
    for bad in (-1, 101, True):
        value["progress"] = bad
        with pytest.raises(RemoteContractError): ProgressEvent.from_mapping(value)
    value = _event(1, 1).to_mapping(); value["message"] = "x" * 4097
    with pytest.raises(RemoteContractError): ProgressEvent.from_mapping(value)
    value = _event(1, 1).to_mapping(); value["message"] = "DAYTONA_API_KEY=do-not-ship"
    with pytest.raises(RemoteContractError, match="credential"): ProgressEvent.from_mapping(value)


def test_completion_requires_nonempty_canonical_result_file():
    value = SCHEMAS[5][1](); value["resultSizeBytes"] = 0
    with pytest.raises(RemoteContractError, match="positive"):
        CompletionReceipt.from_mapping(value)
