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
    from backend.app.daytona import DaytonaDiagnostics, DaytonaExecutionResult
    from backend.app.remote_contracts import CompletionReceipt, ResultBundle
    from backend.app.segmentation import load_result, run_rectangle_stub
    from backend.app.segmentation_worker import retain_shadow_mask_result
    from backend.app.workbench.artifacts import ArtifactStore

    def downloaded(mask):
        output = tmp_path / "download"
        namespace = "result-bundle.json.generations/" + "1" * 32
        mask_path = f"{namespace}/result.segmentation-result.json"
        progress_path = f"{namespace}/result.progress.jsonl"
        mask_bytes = json.dumps(mask.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":")).encode()
        paths = ((mask_path, mask_bytes), (progress_path, b""))
        for relative, content in paths:
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        result = ResultBundle.from_mapping({"schemaVersion": 3, "jobId": job.job_id,
            "matchId": match_id, "sourceCommit": receipt.source_commit,
            "manifestSha256": receipt.manifest_sha256,
            "receiptSha256": hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest(),
            "requestedRuntimeOptions": receipt.requested_runtime_options,
            "result": {"maskResultPath": mask_path, "progressPath": progress_path,
                "progressEventCount": 0, **{key: shadow[key] for key in
                    ("generationId", "requestDigest", "sourceSha256", "checkpointDigest", "jobIdentity")}},
            "artifacts": [FileEntry("result_artifact", PurePosixPath(relative),
                len(content), hashlib.sha256(content).hexdigest()).to_mapping()
                for relative, content in paths]})
        result_bytes = canonical_json_bytes(result.to_mapping())
        result_path = f"{namespace}/result.json"
        (output / result_path).write_bytes(result_bytes)
        completion = CompletionReceipt.from_mapping({"schemaVersion": 1,
            "jobId": job.job_id, "matchId": match_id, "resultPath": result_path,
            "resultSizeBytes": len(result_bytes), "resultSha256": hashlib.sha256(result_bytes).hexdigest(),
            "sourceCommit": receipt.source_commit, "manifestSha256": receipt.manifest_sha256,
            "completedAt": "2026-09-25T00:00:00Z"})
        return DaytonaExecutionResult("sandbox-1", completion, result, output,
            output / mask_path, output / progress_path, DaytonaDiagnostics("[REDACTED]"))

    mask = run_rectangle_stub(request)
    imported = retain_shadow_mask_result(storage, root, downloaded(mask))
    assert imported["qualityAccepted"] is False
    assert imported["generationId"] == generation_id
    assert load_result(ArtifactStore(storage.storage_root / "artifacts"),
                       imported["maskArtifactDigest"]) == mask
    assert storage.load_analysis_artifact(match_id, "sam_shadow_mask") == imported
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        overlay = client.get(f"/api/matches/{match_id}/mask-overlay",
            params={"generationId": generation_id, "frameId": 0})
        assert overlay.status_code == 200
        assert overlay.json() == {"schemaVersion": "mask_overlay_v1", "matchId": match_id,
            "generationId": generation_id, "sourceSha256": request.sourceSha256,
            "sourceFrameId": 0, "ptsSeconds": frames[0].timestamp,
            "width": request.width, "height": request.height,
            "qualification": "review_only", "executionClass": "stub",
            "masks": [{"objectId": "o1", "trackId": "7", "rle": mask.masks[0].rle}]}
    altered = mask.model_dump(mode="json")
    altered["baseTrackingDigest"] = "f" * 64
    altered["outputDigest"] = hashlib.sha256(json.dumps({key: value for key, value in altered.items()
        if key != "outputDigest"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    from backend.app.segmentation import MaskResult
    with pytest.raises(ValueError, match="mask result"):
        retain_shadow_mask_result(storage, root,
            downloaded(MaskResult.model_validate_json(json.dumps(altered))))
    assert storage.load_analysis_artifact(match_id, "sam_shadow_mask") == imported
    revoked = storage.get_match(match_id).config.model_copy(deep=True)
    revoked.rights.cloudPermission = False
    storage.update_match_config(match_id, revoked)
    with pytest.raises(ValueError, match="rights"):
        retain_shadow_mask_result(storage, root, downloaded(mask))
    assert storage.load_analysis_artifact(match_id, "sam_shadow_mask") == imported
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        assert client.get(f"/api/matches/{match_id}/mask-overlay",
            params={"generationId": generation_id, "frameId": 0}).status_code == 404
    storage.update_match_config(match_id, config)
    source_path = storage.get_match_input_path(match_id)
    source_bytes = source_path.read_bytes()
    source_path.write_bytes(source_bytes + b"changed")
    with pytest.raises(ValueError, match="source"):
        retain_shadow_mask_result(storage, root, downloaded(mask))
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        assert client.get(f"/api/matches/{match_id}/mask-overlay",
            params={"generationId": generation_id, "frameId": 0}).status_code == 404
    source_path.write_bytes(source_bytes)
    assert storage.load_analysis_artifact(match_id, "sam_shadow_mask") == imported
    extra = root / "inputs/undeclared.bin"
    extra.write_bytes(b"extra")
    forged = replace(receipt, files=(*receipt.files, FileEntry("runtime_artifact",
        PurePosixPath("inputs/undeclared.bin"), len(b"extra"), hashlib.sha256(b"extra").hexdigest())))
    (root / job.receipt_path).write_bytes(canonical_json_bytes(forged.to_mapping()))
    with pytest.raises(ValueError, match="sealed shadow bundle"):
        load_sealed_shadow_bundle(root)
    extra.unlink()
    (root / job.receipt_path).write_bytes(canonical_json_bytes(receipt.to_mapping()))
    frame_path = root / "inputs/window/0.png"
    frame_bytes = frame_path.read_bytes()
    frame_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sealed shadow bundle"):
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
    storage.update_match_config(match_id, config)
    frame_path.write_bytes(frame_bytes)
    storage.save_frames(match_id, frames)
    assert storage.current_generation(match_id).generationId != generation_id
    with pytest.raises(ValueError, match="generation"):
        retain_shadow_mask_result(storage, root, downloaded(mask))
    assert storage.load_analysis_artifact(match_id, "sam_shadow_mask") == imported
