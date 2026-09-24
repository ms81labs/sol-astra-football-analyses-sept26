"""W03 CPU receipt assembly uses a SAM release identity, not processor artifacts."""

import hashlib
import json
from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from backend.app.report_contracts import digest
from backend.app.segmentation import FramePoint, Prompt, SegmentationRequest
from backend.app.storage import Storage
from backend.tests.test_audit_v3_final_journey import _install_video


@pytest.mark.integration
@pytest.mark.real_media
def test_staged_sam_window_seals_distinct_release_and_reopens_exact_inputs(tmp_path):
    from backend.app.segmentation_worker import stage_shadow_inputs, seal_shadow_job, load_sealed_shadow_bundle
    from backend.app.remote_contracts import FileEntry, canonical_json_bytes, validate_receipt_files

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    generation_id = storage.current_generation(match_id).generationId
    frames = storage.load_frames(match_id, generation_id=generation_id)
    release = tmp_path / "sam-release"
    release.mkdir()
    worker = release / "worker.bin"
    worker.write_bytes(b"CPU worker fixture, not a qualified SAM runtime")
    checkpoint = release / "checkpoint.bin"
    checkpoint.write_bytes(b"CPU checkpoint fixture, not SAM weights")
    source = release / "source.tar"
    source.write_bytes(b"CPU source archive fixture")
    model_digest = "a" * 64
    worker_digest = hashlib.sha256(worker.read_bytes()).hexdigest()
    request = SegmentationRequest(sourceSha256=storage.source_sha256(match_id),
        baseTrackingDigest=digest([frame.model_dump(mode="json") for frame in frames]),
        modelAlias="sam31-video", modelDigest=model_digest,
        checkpointDigest=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        workerDigest=worker_digest, executionMode="sam31_object_multiplex",
        cropDigest="b" * 64, precision="bf16", width=1000, height=600,
        intervalStart=0, intervalEnd=.5,
        frames=[FramePoint(frameId=0, ptsSeconds=frames[0].timestamp)],
        prompts=[Prompt(objectId="o1", trackId="7", frameId=0, point=(1, 1))],
        maxFrames=1, maxObjects=1)
    manifest = release / "sam-manifest.json"
    manifest.write_text(json.dumps({"schemaVersion": "sam_shadow_release_v1",
        "sourceCommit": "c" * 40, "upstreamCommit": "d" * 40,
        "imageDigest": "e" * 64, "modelDigest": model_digest,
        "workerDigest": worker_digest, "checkpointDigest": request.checkpointDigest,
        "sourceArchiveDigest": hashlib.sha256(source.read_bytes()).hexdigest()},
        sort_keys=True, separators=(",", ":")) + "\n")
    evidence = release / "sam-evidence.json"
    evidence.write_text('{"qualification":"cpu_contract_only","schemaVersion":"sam_shadow_evidence_v1"}\n')
    workspace = tmp_path / "shadow-inputs"
    workspace.mkdir()
    root, shadow = stage_shadow_inputs(storage, match_id, generation_id,
        request.model_dump(mode="json"), checkpoint_path=checkpoint,
        approved_model_digest=model_digest, approved_worker_digest=worker_digest,
        approved_crop_digest=request.cropDigest, deadline_seconds=300, workspace=workspace)
    approved_manifest = manifest.read_bytes()
    altered = json.loads(approved_manifest)
    altered["workerDigest"] = "f" * 64
    manifest.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="release does not match"):
        seal_shadow_job(storage, root, shadow, release_root=release)
    assert sorted(path.name for path in root.iterdir()) == ["inputs"]
    altered["workerDigest"] = worker_digest
    altered["sourceArchiveDigest"] = "f" * 64
    manifest.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="sealed shadow bundle"):
        seal_shadow_job(storage, root, shadow, release_root=release)
    assert sorted(path.name for path in root.iterdir()) == ["inputs"]
    manifest.write_bytes(approved_manifest)
    job, receipt = seal_shadow_job(storage, root, shadow, release_root=release)
    validate_receipt_files(root, job, receipt)
    assert load_sealed_shadow_bundle(root) == (job, receipt, request)
    assert job.config["samRelease"]["imageDigest"] == "e" * 64
    assert receipt.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert not any(entry.relative_path.as_posix().endswith(".mp4") for entry in receipt.files)
    extra = root / "inputs/undeclared.bin"
    extra.write_bytes(b"extra")
    forged = replace(receipt, files=(*receipt.files, FileEntry("runtime_artifact",
        PurePosixPath("inputs/undeclared.bin"), len(b"extra"), hashlib.sha256(b"extra").hexdigest())))
    (root / job.receipt_path).write_bytes(canonical_json_bytes(forged.to_mapping()))
    with pytest.raises(ValueError, match="sealed shadow bundle"):
        load_sealed_shadow_bundle(root)
    extra.unlink()
    (root / job.receipt_path).write_bytes(canonical_json_bytes(receipt.to_mapping()))
    (root / "inputs/window/0.png").write_bytes(b"tampered")
    with pytest.raises(Exception):
        load_sealed_shadow_bundle(root)
    second, second_shadow = stage_shadow_inputs(storage, match_id, generation_id,
        request.model_dump(mode="json"), checkpoint_path=checkpoint,
        approved_model_digest=model_digest, approved_worker_digest=worker_digest,
        approved_crop_digest=request.cropDigest, deadline_seconds=300, workspace=workspace)
    revoked = storage.get_match(match_id).config.model_copy(deep=True)
    revoked.rights.cloudPermission = False
    storage.update_match_config(match_id, revoked)
    with pytest.raises(ValueError, match="rights"):
        seal_shadow_job(storage, second, second_shadow, release_root=release)
    assert sorted(path.name for path in second.iterdir()) == ["inputs"]
