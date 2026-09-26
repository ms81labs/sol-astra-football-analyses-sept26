"""Bounded source-frame image references for optional visual reports."""

from __future__ import annotations

import math
import json
import re
from io import BytesIO
from fractions import Fraction
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .workbench.artifacts import ArtifactStore
from .workbench.contracts import StrictModel

MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 4_194_304
MAX_SOURCE_PIXELS = 16_777_216
MAX_MANIFEST_IMAGES = 4


class ProviderImage(StrictModel):
    matchId: str = Field(min_length=1)
    generationId: str = Field(min_length=1)
    sourceSha256: str
    sourceFrameId: int = Field(ge=0)
    ptsSeconds: float = Field(ge=0)
    sourceWidth: int = Field(gt=0)
    sourceHeight: int = Field(gt=0)
    crop: tuple[int, int, int, int]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    imageSha256: str
    imageBytes: int = Field(gt=0, le=MAX_IMAGE_BYTES)
    mimeType: Literal["image/png"] = "image/png"

    @model_validator(mode="after")
    def valid_source_crop(self) -> "ProviderImage":
        if not math.isfinite(self.ptsSeconds) or not all(
            re.fullmatch(r"[a-f0-9]{64}", value) and value != "0" * 64
            for value in (self.sourceSha256, self.imageSha256)
        ):
            raise ValueError("invalid source or image identity")
        x1, y1, x2, y2 = self.crop
        if not (0 <= x1 < x2 <= self.sourceWidth and 0 <= y1 < y2 <= self.sourceHeight):
            raise ValueError("crop outside source frame")
        if (self.width, self.height) != (x2 - x1, y2 - y1) or self.width * self.height > MAX_IMAGE_PIXELS:
            raise ValueError("image dimensions do not match bounded source crop")
        return self


def resolve_provider_image(
    store: ArtifactStore, reference: ProviderImage, *, match_id: str,
    generation_id: str, source_sha256: str, source_frames: dict[int, float],
    approved_images: dict[str, ProviderImage],
) -> bytes:
    """Resolve only a server-approved source frame; never accept a path or FrameData as pixels."""
    if not isinstance(reference, ProviderImage):
        raise TypeError("approved image reference required")
    ref = ProviderImage.model_validate(reference.model_dump())
    # The stored evidence clock and the decoder PTS clock can differ by float
    # rounding; admission already bound them with the same 1e-6 tolerance.
    frame_time = source_frames.get(ref.sourceFrameId)
    if (ref.matchId, ref.generationId, ref.sourceSha256) != (match_id, generation_id, source_sha256) \
            or frame_time is None or not math.isclose(frame_time, ref.ptsSeconds, rel_tol=0, abs_tol=1e-6):
        raise ValueError("image source scope or frame time mismatch")
    if approved_images.get(ref.imageSha256) != ref:
        raise ValueError("image artifact is not approved")
    payload = store.get(ref.imageSha256, namespace="provider_images", max_bytes=MAX_IMAGE_BYTES)
    if len(payload) != ref.imageBytes:
        raise ValueError("image byte size mismatch")
    # Pillow is only needed when an approved image is actually resolved; API-only
    # startup remains usable without the optional image decoder.
    from PIL import Image
    with Image.open(BytesIO(payload)) as image:
        if image.format != "PNG" or image.size != (ref.width, ref.height):
            raise ValueError("image format or dimensions mismatch")
        image.load()
    return payload


def admit_decoded_image(
    store: ArtifactStore, source_path: Path, frame, *, match_id: str,
    generation_id: str, crop: tuple[int, int, int, int] | None = None,
) -> ProviderImage:
    """Retain pixels supplied by the server's source decoder with their exact clock."""
    from .workbench.hashing import stream_sha256
    from PIL import Image

    if (frame.presentation_clock != "decoder_pts" or frame.pts is None
            or frame.presentation_time_seconds is None
            or not math.isfinite(frame.presentation_time_seconds)
            or frame.presentation_time_seconds < 0
            or frame.source_frame_index < 0
            or frame.rotation != 0
            or frame.colour_order not in {"rgb", "bgr"}
            or frame.width <= 0 or frame.height <= 0
            or frame.width * frame.height > MAX_SOURCE_PIXELS
            or len(frame.payload) != frame.width * frame.height * 3):
        raise ValueError("decoded frame has no exact bounded source clock or pixels")
    if frame.presentation_time is None or not math.isclose(
        float(frame.presentation_time), frame.presentation_time_seconds, rel_tol=0, abs_tol=1e-6
    ):
        raise ValueError("decoded frame source clock mismatch")
    x1, y1, x2, y2 = crop or (0, 0, frame.width, frame.height)
    if not (0 <= x1 < x2 <= frame.width and 0 <= y1 < y2 <= frame.height) \
            or (x2 - x1) * (y2 - y1) > MAX_IMAGE_PIXELS:
        raise ValueError("invalid bounded image crop")
    source_sha256 = stream_sha256(Path(source_path)).sha256
    image = Image.frombytes("RGB", (frame.width, frame.height), frame.payload,
                            "raw", "BGR" if frame.colour_order == "bgr" else "RGB")
    output = BytesIO()
    image.crop((x1, y1, x2, y2)).save(output, format="PNG")
    payload = output.getvalue()
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("encoded image exceeds byte limit")
    digest = store.put(payload, namespace="provider_images")
    return ProviderImage(matchId=match_id, generationId=generation_id,
        sourceSha256=source_sha256, sourceFrameId=frame.source_frame_index,
        ptsSeconds=frame.presentation_time_seconds, sourceWidth=frame.width,
        sourceHeight=frame.height, crop=(x1, y1, x2, y2), width=x2 - x1,
        height=y2 - y1, imageSha256=digest, imageBytes=len(payload))


def save_image_manifest(store: ArtifactStore, images: list[ProviderImage]) -> str:
    if not 1 <= len(images) <= MAX_MANIFEST_IMAGES:
        raise ValueError("image manifest exceeds fixed limit")
    validated = [ProviderImage.model_validate(item.model_dump()) for item in images]
    if len({item.imageSha256 for item in validated}) != len(validated) or len({
        (item.matchId, item.generationId, item.sourceSha256) for item in validated
    }) != 1:
        raise ValueError("image manifest has duplicate or mixed source identity")
    payload = json.dumps({"schemaVersion": "provider_image_manifest_v1",
                          "images": [item.model_dump(mode="json") for item in validated]},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return store.put(payload, namespace="provider_image_manifests")


def load_image_manifest(
    store: ArtifactStore, digest: str, *, match_id: str, generation_id: str,
    source_sha256: str, source_frames: dict[int, float],
) -> tuple[tuple[ProviderImage, bytes], ...]:
    document = json.loads(store.get(digest, namespace="provider_image_manifests", max_bytes=16_384))
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "images"} \
            or document["schemaVersion"] != "provider_image_manifest_v1" \
            or not isinstance(document["images"], list) \
            or not 1 <= len(document["images"]) <= MAX_MANIFEST_IMAGES:
        raise ValueError("invalid provider image manifest")
    images = tuple(ProviderImage.model_validate_json(json.dumps(item)) for item in document["images"])
    approved = {item.imageSha256: item for item in images}
    if len(approved) != len(images):
        raise ValueError("duplicate image artifact in manifest")
    return tuple((item, resolve_provider_image(store, item, match_id=match_id,
        generation_id=generation_id, source_sha256=source_sha256,
        source_frames=source_frames, approved_images=approved)) for item in images)


def select_source_image_manifest(storage, match_id: str, generation_id: str,
                                 source_frame_ids: list[int]) -> str:
    """Seek retained video by source PTS and admit only exact current-frame hits."""
    from .workbench.hashing import stream_sha256
    from .workbench.media import (
        DecodedFrame, FfmpegProbe, _ShowinfoParser, _assert_safe_ffmpeg_argv,
        _run_bounded_media_process, verified_source_pts_index,
    )
    from .workbench.media_execution import MediaExecutionPolicy

    if not 1 <= len(source_frame_ids) <= MAX_MANIFEST_IMAGES or any(
        type(frame_id) is not int or frame_id < 0 for frame_id in source_frame_ids
    ) or len(set(source_frame_ids)) != len(source_frame_ids):
        raise ValueError("invalid source frame selection")
    with storage.generation_snapshot(match_id, generation_id=generation_id):
        with storage.generations.guard(match_id, "publication"):
            if storage.generations.resolve(match_id).generationId != generation_id:
                raise ValueError("stale source generation")
        if storage.get_match(match_id).inputMode != "video":
            raise ValueError("source frame selection requires retained video")
        frames = storage.load_frames(match_id, generation_id=generation_id)
        selected = {item.frameId: item for item in frames if item.frameId in source_frame_ids}
        if len(selected) != len(source_frame_ids) or any(
            sum(item.timestamp == selected[frame_id].timestamp for item in frames) != 1
            for frame_id in source_frame_ids
        ):
            raise ValueError("source frame selection is missing or has ambiguous time")
        source = storage.get_match_input_path(match_id)
        # ponytail: four independent seeks, capped at 30 seconds each; batch seek only
        # when measured late-match selection latency warrants it.
        policy = MediaExecutionPolicy(max_duration_seconds=10_800, max_frames=500_000,
            job_timeout_seconds=30, cpu_soft_seconds=30, cpu_hard_seconds=31,
            captured_output_bytes=8 * 1024**2)
        probe = FfmpegProbe(policy=policy)
        identity = probe.probe_identity(source)
        if identity.sourceSha256 != storage.source_sha256(match_id) or not identity.width or not identity.height:
            raise ValueError("retained source identity mismatch")
        time_base = (identity.timeBaseNum, identity.timeBaseDen)
        if not all(isinstance(value, int) and value > 0 for value in time_base):
            raise ValueError("retained source has no exact time base")
        pts_by_frame = verified_source_pts_index(probe, source, policy,
            time_base=Fraction(*time_base), timeout=policy.job_timeout_seconds,
            expected={frame_id: selected[frame_id].timestamp for frame_id in source_frame_ids},
            mismatch_message="selected source frame identity does not match current evidence")
        store = ArtifactStore(storage.storage_root / "artifacts")
        references = []
        for frame_id in source_frame_ids:
            expected = selected[frame_id].timestamp
            command = [probe.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
                "-protocol_whitelist", "file,pipe", "-threads", str(policy.threads),
                "-noautorotate", "-ss", str(expected), "-copyts", "-i", str(source),
                "-map", "0:v:0", "-an", "-vf", "showinfo", "-frames:v", "1",
                "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
            _assert_safe_ffmpeg_argv(command)
            completed = _run_bounded_media_process(command, timeout=policy.job_timeout_seconds,
                output_cap=policy.captured_output_bytes, file_cap=policy.max_file_bytes,
                policy=policy)
            parser = _ShowinfoParser()
            times = parser.feed(completed.stderr) + parser.finish()
            size = identity.width * identity.height * 3
            if completed.returncode != 0 or len(completed.stdout) != size or not times:
                raise ValueError("selected source frame was not decoded")
            pts = times[0][1]
            seconds = float(Fraction(pts * time_base[0], time_base[1]))
            if pts != pts_by_frame[frame_id] or not math.isclose(seconds, expected, rel_tol=0, abs_tol=1e-6):
                raise ValueError("selected source frame time does not match current evidence")
            decoded = DecodedFrame(frame_id, pts, seconds, identity.width, identity.height,
                "bgr", identity.rotation or 0, completed.stdout, "ffmpeg_seek",
                time_base=time_base)
            references.append(admit_decoded_image(store, source, decoded,
                match_id=match_id, generation_id=generation_id))
        if stream_sha256(source).sha256 != identity.sourceSha256:
            raise ValueError("retained source changed during image selection")
        with storage.generations.guard(match_id, "publication"):
            if storage.generations.resolve(match_id).generationId != generation_id:
                raise ValueError("stale source generation")
        return save_image_manifest(store, references)
