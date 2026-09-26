"""CPU-only, model-neutral segmentation artifact contract."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.segmentation import (
    FrameMask, FramePoint, MaskObject, MaskResult, Prompt, SegmentationRequest,
    decode_rle, rectangle_rle, request_identity, run_rectangle_stub,
    load_result, save_result, require_real_model,
)
from backend.app.workbench.artifacts import ArtifactStore


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def request(**changes) -> SegmentationRequest:
    payload = dict(
        sourceSha256=SHA_A, baseTrackingDigest=SHA_B, modelAlias="sam31-video",
        modelDigest=SHA_C, checkpointDigest=SHA_B, workerDigest=SHA_A,
        executionMode="rectangle_stub", cropDigest=SHA_A, precision="bf16", width=3, height=2,
        frames=[FramePoint(frameId=4, ptsSeconds=0.32), FramePoint(frameId=5, ptsSeconds=0.80)],
        prompts=[Prompt(objectId="o1", trackId="t7", frameId=4, box=(1, 0, 3, 2))],
        intervalStart=0.32, intervalEnd=1.0, maxFrames=2, maxObjects=1,
    )
    payload.update(changes)
    return SegmentationRequest(**payload)


def test_rectangle_codec_round_trip_empty_clip_and_invalid_counts() -> None:
    encoded = rectangle_rle(3, 2, (1, 0, 3, 2))
    assert encoded == {"size": [2, 3], "counts": [2, 4]}
    assert decode_rle(encoded) == [[0, 1, 1], [0, 1, 1]]
    assert rectangle_rle(2, 2, (0, 0, 2, 2))["counts"] == [0, 4]
    assert decode_rle(rectangle_rle(3, 2, (-2, -1, 1, 2))) == [[1, 0, 0], [1, 0, 0]]
    assert decode_rle(rectangle_rle(3, 2, (4, 0, 5, 2))) == [[0, 0, 0], [0, 0, 0]]
    for bad in ({"size": [2, 3], "counts": [2, 3]}, {"size": [2, 3], "counts": [-1, 7]},
                {"size": [2, 3], "counts": [1.5, 4.5]}):
        with pytest.raises(ValueError):
            decode_rle(bad)
    with pytest.raises(ValueError):
        rectangle_rle(0, 2, (0, 0, 1, 1))
    with pytest.raises(ValueError):
        rectangle_rle(3, 2, (float("nan"), 0, 1, 1))


def test_request_rejects_invalid_mapping_scope_and_limits() -> None:
    with pytest.raises(ValidationError):
        request(prompts=[Prompt(objectId="o1", trackId="t7", frameId=9, box=(0, 0, 1, 1))])
    with pytest.raises(ValidationError):
        request(prompts=[Prompt(objectId="o1", trackId="t7", frameId=4, box=(0, 0, 1, 1)),
                         Prompt(objectId="o1", trackId="t8", frameId=4, box=(0, 0, 1, 1))])
    with pytest.raises(ValidationError):
        request(width=0)
    with pytest.raises(ValidationError):
        request(maxFrames=1)
    with pytest.raises(ValidationError):
        request(maxFrames=121)
    with pytest.raises(ValidationError):
        request(sourceSha256="unknown")


def test_request_identity_changes_with_every_determining_input() -> None:
    baseline = request()
    identity = request_identity(baseline)
    assert identity == request_identity(request())
    assert identity is not None
    for change in (
        {"sourceSha256": SHA_B}, {"baseTrackingDigest": SHA_A}, {"modelDigest": SHA_A},
        {"checkpointDigest": SHA_A}, {"workerDigest": SHA_B}, {"executionMode": "different_mode"},
        {"cropDigest": SHA_B}, {"precision": "fp32"},
        {"modelAlias": "other-model"},
        {"frames": [FramePoint(frameId=4, ptsSeconds=0.33), FramePoint(frameId=5, ptsSeconds=0.80)]},
        {"prompts": [Prompt(objectId="o1", trackId="t7", frameId=4, box=(0, 0, 2, 2))]},
    ):
        assert request_identity(request(**change)) != identity
    assert request_identity(request(modelDigest=None)) is None
    assert request_identity(request(workerDigest=None)) is None


def test_stub_artifact_is_decodable_immutable_and_cannot_pass_real_receipt(tmp_path: Path) -> None:
    result = run_rectangle_stub(request())
    assert result.executionClass == "stub"
    assert result.status == "stub_complete"
    assert result.reasonCodes == ["DETERMINISTIC_RECTANGLE_STUB"]
    assert decode_rle(result.masks[0].rle) == [[0, 1, 1], [0, 1, 1]]
    assert result.masks[0].sourceFrameId == 4
    assert result.masks[0].ptsSeconds == 0.32
    with pytest.raises(ValueError, match="real model"):
        require_real_model(result)
    store = ArtifactStore(tmp_path / "artifacts")
    digest = save_result(store, result)
    assert load_result(ArtifactStore(tmp_path / "artifacts"), digest) == result
    with pytest.raises(ValidationError, match="duplicate object mapping"):
        MaskResult.model_validate_json(json.dumps({**result.model_dump(mode="json"), "objects": [
            MaskObject(objectId="o1", trackId="t7").model_dump(),
            MaskObject(objectId="o2", trackId="t7").model_dump(),
        ]}))
    with pytest.raises(ValidationError, match="output digest mismatch"):
        MaskResult.model_validate_json(json.dumps({**result.model_dump(mode="json"), "reasonCodes": []}))


def test_point_prompt_is_decodable_and_api_import_does_not_load_torch() -> None:
    result = run_rectangle_stub(request(prompts=[Prompt(objectId="o1", trackId="t7", frameId=4, point=(1, 0))]))
    assert decode_rle(result.masks[0].rle) == [[0, 1, 0], [0, 0, 0]]
    completed = subprocess.run([sys.executable, "-c",
        "import sys; import backend.app.segmentation; assert 'torch' not in sys.modules"],
        capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr


def test_remote_mask_result_shape_is_bounded_without_expanding_pixels(monkeypatch) -> None:
    import backend.app.segmentation as segmentation

    sample = run_rectangle_stub(request()).model_dump(mode="json")
    payload = {key: value for key, value in sample.items() if key != "outputDigest"}

    def reseal(changes):
        changed = {**payload, **changes}
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return {**changed, "outputDigest": hashlib.sha256(encoded).hexdigest()}

    with pytest.raises(ValidationError, match="objects"):
        MaskResult.model_validate_json(json.dumps(reseal({"objects": [
            {"objectId": f"o{i}", "trackId": f"t{i}"} for i in range(33)]})))
    with pytest.raises(ValidationError, match="frames"):
        MaskResult.model_validate_json(json.dumps(reseal({"frames": [
            {"frameId": i, "ptsSeconds": float(i)} for i in range(121)],
            "intervalEnd": 122.0})))

    monkeypatch.setattr(segmentation, "decode_rle", lambda _rle: (_ for _ in ()).throw(
        AssertionError("remote result validation must not expand pixels")))
    assert FrameMask.model_validate(sample["masks"][0]).rle == sample["masks"][0]["rle"]
    with pytest.raises(ValidationError, match="RLE"):
        FrameMask.model_validate({**sample["masks"][0], "rle": {"size": [2, 3], "counts": [2, 3]}})
