"""Bounded source-frame image references for optional visual reports."""

from __future__ import annotations

import math
import json
import re
from io import BytesIO
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
    if (ref.matchId, ref.generationId, ref.sourceSha256) != (match_id, generation_id, source_sha256) \
            or source_frames.get(ref.sourceFrameId) != ref.ptsSeconds:
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
