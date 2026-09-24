"""W03 CPU preflight for a future sealed SAM shadow job; no model runtime."""

import hashlib
import subprocess
import sys

import pytest

from backend.app.report_contracts import digest
from backend.app.segmentation import FramePoint, Prompt, SegmentationRequest, request_identity
from backend.app.storage import Storage
from backend.tests.test_audit_v3_final_journey import _install_video


def test_sam3_prompt_mapping_uses_local_frame_indices_and_normalised_points():
    from backend.app.segmentation_worker import sam3_prompt_requests

    request = SegmentationRequest(sourceSha256="a" * 64, baseTrackingDigest="b" * 64,
        modelAlias="sam31-video", modelDigest="c" * 64, checkpointDigest="d" * 64,
        workerDigest="e" * 64, executionMode="sam31_object_multiplex", cropDigest="f" * 64,
        precision="bf16", width=200, height=100, intervalStart=1, intervalEnd=3,
        frames=[FramePoint(frameId=10, ptsSeconds=1), FramePoint(frameId=15, ptsSeconds=2)],
        prompts=[Prompt(objectId="b", trackId="t2", frameId=15, point=(20, 10)),
                 Prompt(objectId="a", trackId="t1", frameId=10, point=(50, 25))],
        maxFrames=2, maxObjects=2)
    objects, prompts = sam3_prompt_requests(request)
    assert objects == {"a": 1, "b": 2}
    assert prompts == [
        {"type": "add_prompt", "frame_index": 1, "obj_id": 2,
         "points": [[.1, .1]], "point_labels": [1],
         "rel_coordinates": True},
        {"type": "add_prompt", "frame_index": 0, "obj_id": 1,
         "points": [[.25, .25]], "point_labels": [1], "rel_coordinates": True},
    ]
    with pytest.raises(ValueError, match="frame geometry"):
        sam3_prompt_requests(request.model_copy(update={"prompts": [
            Prompt(objectId="b", trackId="t2", frameId=15, point=(201, 60))]}))
    with pytest.raises(ValueError, match="box prompts"):
        sam3_prompt_requests(request.model_copy(update={"prompts": [
            Prompt(objectId="b", trackId="t2", frameId=15, box=(20, 10, 120, 60))]}))


def test_sam3_prompt_mapping_keeps_multiple_points_for_one_object_and_frame():
    from backend.app.segmentation_worker import sam3_prompt_requests

    request = SegmentationRequest(sourceSha256="a" * 64, baseTrackingDigest="b" * 64,
        modelAlias="sam31-video", modelDigest="c" * 64, checkpointDigest="d" * 64,
        workerDigest="e" * 64, executionMode="sam31_object_multiplex", cropDigest="f" * 64,
        precision="bf16", width=200, height=100, intervalStart=1, intervalEnd=2,
        frames=[FramePoint(frameId=10, ptsSeconds=1)],
        prompts=[Prompt(objectId="a", trackId="t1", frameId=10, point=(20, 10)),
                 Prompt(objectId="a", trackId="t1", frameId=10, point=(50, 25))],
        maxFrames=1, maxObjects=1)
    _, commands = sam3_prompt_requests(request)
    assert commands == [{"type": "add_prompt", "frame_index": 0, "obj_id": 1,
        "points": [[.1, .1], [.25, .25]], "point_labels": [1, 1],
        "rel_coordinates": True}]


@pytest.mark.integration
@pytest.mark.real_media
def test_sam3_window_stages_sparse_exact_source_frames_and_cleans_failure(tmp_path, monkeypatch):
    from PIL import Image
    from backend.app import segmentation_worker
    from backend.app.segmentation_worker import stage_sam_source_window, validate_sam_source_window
    from backend.app.workbench.media import FfmpegFrameSource
    from backend.app.workbench.media import resolve_trusted_executable

    source = tmp_path / "source.mp4"
    subprocess.run([str(resolve_trusted_executable("ffmpeg")), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=4:duration=1", "-threads", "1",
        "-pix_fmt", "yuv420p", str(source)], check=True, timeout=40)
    request = SegmentationRequest(sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        baseTrackingDigest="b" * 64, modelAlias="sam31-video", modelDigest="c" * 64,
        checkpointDigest="d" * 64, workerDigest="e" * 64,
        executionMode="sam31_object_multiplex", cropDigest="f" * 64, precision="bf16",
        width=160, height=90, intervalStart=0, intervalEnd=.75,
        frames=[FramePoint(frameId=0, ptsSeconds=0), FramePoint(frameId=2, ptsSeconds=.5)],
        prompts=[Prompt(objectId="a", trackId="t1", frameId=2, point=(10, 10))],
        maxFrames=2, maxObjects=1)
    workspace = tmp_path / "windows"
    workspace.mkdir()
    root, manifest = stage_sam_source_window(source, request, workspace)
    assert validate_sam_source_window(root, request) == manifest
    assert [(item["sourceFrameId"], item["localIndex"], item["ptsSeconds"])
        for item in manifest["frames"]] == [(0, 0, 0), (2, 1, .5)]
    assert sorted(path.name for path in root.iterdir()) == ["0.png", "1.png", "window.json"]
    decoded = list(FfmpegFrameSource().iter_frames(source))
    for local_index, source_index in enumerate((0, 2)):
        with Image.open(root / f"{local_index}.png") as image:
            assert image.size == (160, 90)
            expected = Image.frombytes("RGB", image.size, decoded[source_index].payload, "raw", "BGR")
            assert image.tobytes() == expected.tobytes()
    first = root / "0.png"
    original = first.read_bytes()
    first.write_bytes(b"changed")
    with pytest.raises(ValueError, match="window"):
        validate_sam_source_window(root, request)
    first.write_bytes(original)
    first.unlink()
    first.symlink_to(source)
    with pytest.raises(ValueError, match="window"):
        validate_sam_source_window(root, request)
    first.unlink()
    first.write_bytes(original)
    manifest_path = root / "window.json"
    original_manifest = manifest_path.read_bytes()
    malformed = {**manifest, "frames": [{**manifest["frames"][0], "sourceFrameId": 2},
        manifest["frames"][1]]}
    from backend.app.remote_contracts import canonical_json_bytes
    manifest_path.write_bytes(canonical_json_bytes(malformed))
    with pytest.raises(ValueError, match="window"):
        validate_sam_source_window(root, request)
    manifest_path.write_bytes(original_manifest)
    (root / "extra.png").write_bytes(original)
    with pytest.raises(ValueError, match="window"):
        validate_sam_source_window(root, request)
    (root / "extra.png").unlink()
    with pytest.raises(ValueError, match="source frame PTS"):
        stage_sam_source_window(source, request.model_copy(update={"frames": [
            FramePoint(frameId=0, ptsSeconds=0), FramePoint(frameId=2, ptsSeconds=.4)]}), workspace)
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]
    clock = iter((0.0, 0.0, 301.0))
    with monkeypatch.context() as patch:
        patch.setattr(segmentation_worker, "monotonic", lambda: next(clock))
        with pytest.raises(ValueError, match="deadline"):
            stage_sam_source_window(source, request, workspace)
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source identity"):
        stage_sam_source_window(source, request, workspace)
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]


def test_shadow_preflight_import_does_not_load_sam_or_torch():
    completed = subprocess.run([sys.executable, "-c",
        "import sys; import backend.app.segmentation_worker; "
        "assert 'torch' not in sys.modules and 'sam3' not in sys.modules"],
        capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.integration
@pytest.mark.real_media
def test_shadow_preflight_binds_current_source_rights_and_approved_runtime(tmp_path, monkeypatch):
    from backend.app import segmentation_worker
    from backend.app.segmentation_worker import preflight_shadow_window
    from backend.app.workbench.media import FfmpegProbe

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    frames = storage.load_frames(match_id, generation_id=generation_id)
    source_sha = storage.source_sha256(match_id)
    checkpoint = tmp_path / "approved-checkpoint.bin"
    checkpoint.write_bytes(b"CPU preflight fixture, not SAM weights")
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    model_sha, worker_sha, crop_sha = (letter * 64 for letter in "abc")
    request = SegmentationRequest(sourceSha256=source_sha,
        baseTrackingDigest=digest([frame.model_dump(mode="json") for frame in frames]),
        modelAlias="sam31-video", modelDigest=model_sha, checkpointDigest=checkpoint_sha,
        workerDigest=worker_sha, executionMode="sam31_object_multiplex", cropDigest=crop_sha,
        precision="bf16", width=1000, height=600, intervalStart=0, intervalEnd=.5,
        frames=[FramePoint(frameId=0, ptsSeconds=frames[0].timestamp)],
        prompts=[Prompt(objectId="o1", trackId="7", frameId=0, point=(1, 1))],
        maxFrames=1, maxObjects=1)
    kwargs = dict(checkpoint_path=checkpoint, approved_model_digest=model_sha,
        approved_worker_digest=worker_sha, approved_crop_digest=crop_sha,
        deadline_seconds=300)
    with pytest.raises(ValueError, match="rights"):
        preflight_shadow_window(storage, match_id, generation_id, request.model_dump(mode="json"), **kwargs)
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    admission = preflight_shadow_window(storage, match_id, generation_id,
        request.model_dump(mode="json"), **kwargs)
    assert admission["matchId"] == match_id and admission["generationId"] == generation_id
    assert admission["requestDigest"] == request_identity(request)
    assert admission["checkpointDigest"] == checkpoint_sha
    assert admission["jobIdentity"] == preflight_shadow_window(storage, match_id, generation_id,
        request.model_dump(mode="json"), **kwargs)["jobIdentity"]
    clock = iter((0.0, 301.0))
    with monkeypatch.context() as patch:
        patch.setattr(segmentation_worker, "monotonic", lambda: next(clock))
        with pytest.raises(ValueError, match="deadline"):
            preflight_shadow_window(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)
    original_probe = FfmpegProbe.probe_identity
    def change_checkpoint_during_probe(probe, path):
        identity = original_probe(probe, path)
        checkpoint.write_bytes(b"changed during probe")
        return identity
    with monkeypatch.context() as patch:
        patch.setattr(FfmpegProbe, "probe_identity", change_checkpoint_during_probe)
        with pytest.raises(ValueError, match="checkpoint"):
            preflight_shadow_window(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)
    checkpoint.write_bytes(b"CPU preflight fixture, not SAM weights")
    def revoke_rights_during_probe(probe, path):
        identity = original_probe(probe, path)
        revoked = storage.get_match(match_id).config.model_copy(deep=True)
        revoked.rights.cloudPermission = False
        storage.update_match_config(match_id, revoked)
        return identity
    with monkeypatch.context() as patch:
        patch.setattr(FfmpegProbe, "probe_identity", revoke_rights_during_probe)
        with pytest.raises(ValueError, match="rights"):
            preflight_shadow_window(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)
    storage.update_match_config(match_id, config)
    with pytest.raises(ValueError, match="source dimensions"):
        preflight_shadow_window(storage, match_id, generation_id,
            {**request.model_dump(mode="json"), "width": 999}, **kwargs)
    # The stored 0.2s observation for frame 1 differs from this video's 0.25s PTS.
    with pytest.raises(ValueError, match="source frame"):
        preflight_shadow_window(storage, match_id, generation_id,
            {**request.model_dump(mode="json"), "frames": [{"frameId": 1, "ptsSeconds": frames[1].timestamp}],
             "prompts": [{"objectId": "o1", "trackId": "7", "frameId": 1, "point": [1, 1]}]}, **kwargs)
    for changed in (
        {"sourceSha256": "d" * 64}, {"checkpointDigest": "d" * 64},
        {"baseTrackingDigest": "d" * 64}, {"modelDigest": "d" * 64},
        {"workerDigest": "d" * 64}, {"cropDigest": "d" * 64},
        {"sourceUrl": "https://example.invalid/video"}, {"artifactPath": "../../weights"},
        {"frames": [{"frameId": 0, "ptsSeconds": .25}]},
        {"prompts": [{"objectId": "o1", "trackId": "7", "frameId": 0,
                      "box": [1, 1, 1001, 3]}]},
        {"maxFrames": 121}, {"maxObjects": 33},
    ):
        with pytest.raises(ValueError):
            preflight_shadow_window(storage, match_id, generation_id,
                {**request.model_dump(mode="json"), **changed}, **kwargs)
    with pytest.raises(ValueError, match="cancel"):
        preflight_shadow_window(storage, match_id, generation_id,
            request.model_dump(mode="json"), cancelled=True, **kwargs)
    cancellation = {"requested": False}
    def cancel_during_probe(probe, path):
        identity = original_probe(probe, path)
        cancellation["requested"] = True
        return identity
    with monkeypatch.context() as patch:
        patch.setattr(FfmpegProbe, "probe_identity", cancel_during_probe)
        with pytest.raises(ValueError, match="cancel"):
            preflight_shadow_window(storage, match_id, generation_id,
                request.model_dump(mode="json"), cancelled=lambda: cancellation["requested"], **kwargs)
    assert cancellation["requested"], "cancellation must be observed after the probe starts"
    with pytest.raises(ValueError, match="deadline"):
        preflight_shadow_window(storage, match_id, generation_id,
            request.model_dump(mode="json"), **{**kwargs, "deadline_seconds": 0})
    with pytest.raises(ValueError, match="generation"):
        preflight_shadow_window(storage, match_id, "stale",
            request.model_dump(mode="json"), **kwargs)
    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="digest"):
        preflight_shadow_window(storage, match_id, generation_id,
            request.model_dump(mode="json"), **kwargs)
    checkpoint.write_bytes(b"CPU preflight fixture, not SAM weights")
    other_match_id = _install_video(storage, tmp_path)
    other_config = storage.get_match(other_match_id).config.model_copy(deep=True)
    other_config.rights.cloudPermission = True
    other_config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(other_match_id, other_config)
    other_generation = storage.current_generation(other_match_id).generationId
    other = preflight_shadow_window(storage, other_match_id, other_generation,
        request.model_dump(mode="json"), **kwargs)
    assert other["requestDigest"] == admission["requestDigest"]
    assert other["jobIdentity"] != admission["jobIdentity"]
    def replace_generation_during_probe(probe, path):
        identity = original_probe(probe, path)
        storage.save_frames(match_id, frames)
        return identity
    with monkeypatch.context() as patch:
        patch.setattr(FfmpegProbe, "probe_identity", replace_generation_during_probe)
        with pytest.raises(ValueError, match="generation"):
            preflight_shadow_window(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)


@pytest.mark.integration
@pytest.mark.real_media
def test_shadow_input_staging_seals_current_window_and_cleans_revoked_rights(tmp_path, monkeypatch):
    from backend.app import segmentation_worker
    from backend.app.segmentation_worker import stage_shadow_inputs, validate_sam_source_window
    from backend.app.remote_contracts import load_canonical_json

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    generation_id = storage.current_generation(match_id).generationId
    frames = storage.load_frames(match_id, generation_id=generation_id)
    checkpoint = tmp_path / "approved-checkpoint.bin"
    checkpoint.write_bytes(b"CPU staging fixture, not SAM weights")
    model_sha, worker_sha, crop_sha = (letter * 64 for letter in "abc")
    request = SegmentationRequest(sourceSha256=storage.source_sha256(match_id),
        baseTrackingDigest=digest([frame.model_dump(mode="json") for frame in frames]),
        modelAlias="sam31-video", modelDigest=model_sha,
        checkpointDigest=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        workerDigest=worker_sha, executionMode="sam31_object_multiplex", cropDigest=crop_sha,
        precision="bf16", width=1000, height=600, intervalStart=0, intervalEnd=.5,
        frames=[FramePoint(frameId=0, ptsSeconds=frames[0].timestamp)],
        prompts=[Prompt(objectId="o1", trackId="7", frameId=0, point=(1, 1))],
        maxFrames=1, maxObjects=1)
    workspace = tmp_path / "shadow-inputs"
    workspace.mkdir()
    kwargs = dict(checkpoint_path=checkpoint, approved_model_digest=model_sha,
        approved_worker_digest=worker_sha, approved_crop_digest=crop_sha,
        deadline_seconds=300, workspace=workspace)
    root, shadow = stage_shadow_inputs(storage, match_id, generation_id,
        request.model_dump(mode="json"), **kwargs)
    assert shadow["schemaVersion"] == 2
    assert shadow["requestDigest"] == request_identity(request)
    assert shadow["windowDigest"] == hashlib.sha256(
        (root / "inputs/window/window.json").read_bytes()).hexdigest()
    assert validate_sam_source_window(root / "inputs/window", request)["requestDigest"] == shadow["requestDigest"]
    assert load_canonical_json(root / "inputs/segmentation-request.json") == request.model_dump(mode="json")
    assert (root / "inputs/checkpoint.bin").read_bytes() == checkpoint.read_bytes()
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]

    original_stage = segmentation_worker.stage_sam_source_window
    def revoke_after_staging(*args, **kw):
        result = original_stage(*args, **kw)
        revoked = storage.get_match(match_id).config.model_copy(deep=True)
        revoked.rights.cloudPermission = False
        storage.update_match_config(match_id, revoked)
        return result
    with monkeypatch.context() as patch:
        patch.setattr(segmentation_worker, "stage_sam_source_window", revoke_after_staging)
        with pytest.raises(ValueError, match="rights"):
            stage_shadow_inputs(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]
    storage.update_match_config(match_id, config)

    def change_checkpoint_after_staging(*args, **kw):
        result = original_stage(*args, **kw)
        checkpoint.write_bytes(b"changed after admission")
        return result
    with monkeypatch.context() as patch:
        patch.setattr(segmentation_worker, "stage_sam_source_window", change_checkpoint_after_staging)
        with pytest.raises(ValueError, match="checkpoint"):
            stage_shadow_inputs(storage, match_id, generation_id,
                request.model_dump(mode="json"), **kwargs)
    assert sorted(path.name for path in workspace.iterdir()) == [root.name]
