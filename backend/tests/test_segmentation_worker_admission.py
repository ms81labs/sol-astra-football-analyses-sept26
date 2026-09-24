"""W03 CPU preflight for a future sealed SAM shadow job; no model runtime."""

import hashlib
import subprocess
import sys

import pytest

from backend.app.report_contracts import digest
from backend.app.segmentation import FramePoint, Prompt, SegmentationRequest, request_identity
from backend.app.storage import Storage
from backend.tests.test_audit_v3_final_journey import _install_video


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
        prompts=[Prompt(objectId="o1", trackId="7", frameId=0, box=(1, 1, 3, 3))],
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
             "prompts": [{"objectId": "o1", "trackId": "7", "frameId": 1, "box": [1, 1, 3, 3]}]}, **kwargs)
    for changed in (
        {"sourceSha256": "d" * 64}, {"checkpointDigest": "d" * 64},
        {"baseTrackingDigest": "d" * 64}, {"modelDigest": "d" * 64},
        {"workerDigest": "d" * 64}, {"cropDigest": "d" * 64},
        {"sourceUrl": "https://example.invalid/video"}, {"artifactPath": "../../weights"},
        {"frames": [{"frameId": 0, "ptsSeconds": .25}]},
        {"maxFrames": 121}, {"maxObjects": 33},
    ):
        with pytest.raises(ValueError):
            preflight_shadow_window(storage, match_id, generation_id,
                {**request.model_dump(mode="json"), **changed}, **kwargs)
    with pytest.raises(ValueError, match="cancel"):
        preflight_shadow_window(storage, match_id, generation_id,
            request.model_dump(mode="json"), cancelled=True, **kwargs)
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
