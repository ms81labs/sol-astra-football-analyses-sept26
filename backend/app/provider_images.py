"""Bounded source-frame image references for optional visual reports."""

from __future__ import annotations

import math
import re
from io import BytesIO
from typing import Literal

from pydantic import Field, model_validator

from .workbench.artifacts import ArtifactStore
from .workbench.contracts import StrictModel

MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 4_194_304


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
