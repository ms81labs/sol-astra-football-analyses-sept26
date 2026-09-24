"""Model-neutral, source-bound mask artifacts; no GPU runtime in the API."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Literal

from pydantic import Field, model_validator

from .workbench.artifacts import ArtifactStore
from .workbench.contracts import StrictModel

MAX_MASK_PIXELS = 16_777_216
MAX_FRAMES = 120
MAX_OBJECTS = 32


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _valid_sha(value: str | None) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value)) and value != "0" * 64


class FramePoint(StrictModel):
    frameId: int = Field(ge=0)
    ptsSeconds: float = Field(ge=0)

    @model_validator(mode="after")
    def finite(self) -> "FramePoint":
        if not math.isfinite(self.ptsSeconds):
            raise ValueError("nonfinite source PTS")
        return self


class Prompt(StrictModel):
    schemaVersion: Literal["mask_prompt_v1"] = "mask_prompt_v1"
    objectId: str = Field(min_length=1)
    trackId: str = Field(min_length=1)
    frameId: int = Field(ge=0)
    box: tuple[float, float, float, float] | None = None
    point: tuple[float, float] | None = None

    @model_validator(mode="after")
    def valid_shape(self) -> "Prompt":
        if (self.box is None) == (self.point is None):
            raise ValueError("exactly one box or point prompt is required")
        coordinates = self.box if self.box is not None else self.point
        if not all(math.isfinite(value) for value in coordinates):
            raise ValueError("nonfinite prompt coordinate")
        if self.box is not None and (self.box[2] <= self.box[0] or self.box[3] <= self.box[1]):
            raise ValueError("empty prompt box")
        return self


class SegmentationRequest(StrictModel):
    schemaVersion: Literal["segmentation_request_v1"] = "segmentation_request_v1"
    sourceSha256: str | None
    baseTrackingDigest: str | None
    modelAlias: str = Field(min_length=1)
    modelDigest: str | None
    checkpointDigest: str | None
    workerDigest: str | None
    executionMode: str = Field(min_length=1)
    cropDigest: str | None
    precision: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    intervalStart: float = Field(ge=0)
    intervalEnd: float
    frames: list[FramePoint] = Field(min_length=1)
    prompts: list[Prompt] = Field(min_length=1)
    maxFrames: int = Field(gt=0)
    maxObjects: int = Field(gt=0)

    @model_validator(mode="after")
    def bounded(self) -> "SegmentationRequest":
        if not all(math.isfinite(value) for value in (self.intervalStart, self.intervalEnd)) \
                or self.intervalEnd <= self.intervalStart:
            raise ValueError("invalid source interval")
        if self.width * self.height > MAX_MASK_PIXELS or self.maxFrames > MAX_FRAMES or self.maxObjects > MAX_OBJECTS:
            raise ValueError("segmentation request exceeds fixed limits")
        if len(self.frames) > self.maxFrames or len({prompt.objectId for prompt in self.prompts}) > self.maxObjects:
            raise ValueError("segmentation request exceeds declared limits")
        if len(self.prompts) > MAX_FRAMES * MAX_OBJECTS:
            raise ValueError("too many prompts")
        for value in (self.sourceSha256, self.baseTrackingDigest, self.modelDigest,
                      self.checkpointDigest, self.workerDigest, self.cropDigest):
            if value is not None and not _valid_sha(value):
                raise ValueError("invalid determining input digest")
        frame_ids = [frame.frameId for frame in self.frames]
        pts = [frame.ptsSeconds for frame in self.frames]
        if frame_ids != sorted(set(frame_ids)) or pts != sorted(set(pts)):
            raise ValueError("source frame and PTS mapping must increase exactly")
        if pts[0] < self.intervalStart or pts[-1] >= self.intervalEnd:
            raise ValueError("frame outside source interval")
        mapping: dict[str, str] = {}
        for prompt in self.prompts:
            if prompt.frameId not in frame_ids:
                raise ValueError("prompt outside requested frame interval")
            if prompt.objectId in mapping and mapping[prompt.objectId] != prompt.trackId:
                raise ValueError("duplicate object mapping")
            mapping[prompt.objectId] = prompt.trackId
        return self


def request_identity(request: SegmentationRequest) -> str | None:
    if not all(_valid_sha(value) for value in (request.sourceSha256, request.baseTrackingDigest,
                                               request.modelDigest, request.checkpointDigest,
                                               request.workerDigest, request.cropDigest)):
        return None
    return _digest(request.model_dump(mode="json"))


def rectangle_rle(width: int, height: int, xyxy: tuple[float, float, float, float]) -> dict:
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0 \
            or width * height > MAX_MASK_PIXELS:
        raise ValueError("invalid mask dimensions")
    if len(xyxy) != 4 or not all(math.isfinite(value) for value in xyxy):
        raise ValueError("invalid rectangle coordinates")
    x1, y1, x2, y2 = xyxy
    if x2 <= x1 or y2 <= y1:
        raise ValueError("empty rectangle")
    counts: list[int] = [0]
    foreground = False
    for x in range(width):
        for y in range(height):
            value = x1 <= x + 0.5 < x2 and y1 <= y + 0.5 < y2
            if value != foreground:
                counts.append(0)
                foreground = value
            counts[-1] += 1
    return {"size": [height, width], "counts": counts}


def _validate_rle(rle: dict) -> tuple[int, int, list[int]]:
    size, counts = rle.get("size"), rle.get("counts")
    if not isinstance(size, list) or len(size) != 2 or any(type(value) is not int or value <= 0 for value in size):
        raise ValueError("invalid RLE size")
    if not isinstance(counts, list) or not counts or any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("invalid RLE counts")
    height, width = size
    if height * width > MAX_MASK_PIXELS:
        raise ValueError("RLE image exceeds fixed limit")
    if len(counts) > width * height + 1 or any(count == 0 for count in counts[1:]) \
            or sum(counts) != width * height:
        raise ValueError("RLE counts do not cover the image")
    return height, width, counts


def decode_rle(rle: dict) -> list[list[int]]:
    height, width, counts = _validate_rle(rle)
    pixels = [value for index, count in enumerate(counts) for value in [index % 2] * count]
    return [[pixels[x * height + y] for x in range(width)] for y in range(height)]


class MaskObject(StrictModel):
    objectId: str = Field(min_length=1)
    trackId: str = Field(min_length=1)


class FrameMask(StrictModel):
    objectId: str
    sourceFrameId: int = Field(ge=0)
    ptsSeconds: float = Field(ge=0)
    rle: dict

    @model_validator(mode="after")
    def valid_mask(self) -> "FrameMask":
        if not math.isfinite(self.ptsSeconds):
            raise ValueError("nonfinite mask PTS")
        _validate_rle(self.rle)
        return self


class MaskResult(StrictModel):
    schemaVersion: Literal["segmentation_result_v1"] = "segmentation_result_v1"
    sourceSha256: str | None
    baseTrackingDigest: str | None
    requestDigest: str | None
    modelAlias: str
    modelDigest: str | None
    checkpointDigest: str | None
    workerDigest: str | None
    executionMode: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    intervalStart: float = Field(ge=0)
    intervalEnd: float
    frames: list[FramePoint] = Field(max_length=MAX_FRAMES)
    prompts: list[Prompt] = Field(max_length=MAX_FRAMES * MAX_OBJECTS)
    codec: Literal["rle_uncompressed_column_major_v1"] = "rle_uncompressed_column_major_v1"
    executionClass: Literal["stub", "real_model"]
    status: Literal["stub_complete", "complete", "failed"]
    reasonCodes: list[str]
    usage: dict[str, int | float | None]
    objects: list[MaskObject] = Field(max_length=MAX_OBJECTS)
    masks: list[FrameMask] = Field(max_length=MAX_FRAMES * MAX_OBJECTS)
    outputDigest: str

    @model_validator(mode="after")
    def valid_result(self) -> "MaskResult":
        if self.width * self.height > MAX_MASK_PIXELS or self.intervalEnd <= self.intervalStart \
                or not all(math.isfinite(value) for value in (self.intervalStart, self.intervalEnd)):
            raise ValueError("invalid result bounds")
        if len({item.objectId for item in self.objects}) != len(self.objects) \
                or len({item.trackId for item in self.objects}) != len(self.objects):
            raise ValueError("duplicate object mapping")
        if len({(mask.objectId, mask.sourceFrameId) for mask in self.masks}) != len(self.masks):
            raise ValueError("duplicate mask output")
        object_ids = {item.objectId for item in self.objects}
        source_pts = {frame.frameId: frame.ptsSeconds for frame in self.frames}
        if any(mask.objectId not in object_ids or mask.rle["size"] != [self.height, self.width]
               or source_pts.get(mask.sourceFrameId) != mask.ptsSeconds
               for mask in self.masks):
            raise ValueError("mask/object/dimension mismatch")
        payload = self.model_dump(mode="json", exclude={"outputDigest"})
        if self.outputDigest != _digest(payload):
            raise ValueError("segmentation output digest mismatch")
        return self


def run_rectangle_stub(request: SegmentationRequest) -> MaskResult:
    points = {frame.frameId: frame.ptsSeconds for frame in request.frames}
    objects = [MaskObject(objectId=object_id, trackId=track_id) for object_id, track_id in
               sorted({prompt.objectId: prompt.trackId for prompt in request.prompts}.items())]
    masks = []
    for prompt in request.prompts:
        box = prompt.box if prompt.box is not None else (
            prompt.point[0], prompt.point[1], prompt.point[0] + 1, prompt.point[1] + 1)
        masks.append(FrameMask(objectId=prompt.objectId, sourceFrameId=prompt.frameId,
                               ptsSeconds=points[prompt.frameId], rle=rectangle_rle(request.width, request.height, box)))
    payload = dict(sourceSha256=request.sourceSha256, baseTrackingDigest=request.baseTrackingDigest,
                   requestDigest=request_identity(request), modelAlias=request.modelAlias,
                   modelDigest=request.modelDigest, checkpointDigest=request.checkpointDigest,
                   workerDigest=request.workerDigest, executionMode=request.executionMode,
                   width=request.width, height=request.height,
                   intervalStart=request.intervalStart, intervalEnd=request.intervalEnd,
                   frames=[item.model_dump(mode="json") for item in request.frames],
                   prompts=[item.model_dump(mode="json") for item in request.prompts],
                   executionClass="stub", status="stub_complete", reasonCodes=["DETERMINISTIC_RECTANGLE_STUB"],
                   usage={"frames": len(masks), "objects": len(objects), "gpuSeconds": 0},
                   objects=[item.model_dump(mode="json") for item in objects],
                   masks=[item.model_dump(mode="json") for item in masks],
                   schemaVersion="segmentation_result_v1", codec="rle_uncompressed_column_major_v1")
    return MaskResult.model_validate_json(json.dumps({**payload, "outputDigest": _digest(payload)}))


def save_result(store: ArtifactStore, result: MaskResult) -> str:
    payload = json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return store.put(payload, namespace="segmentation")


def load_result(store: ArtifactStore, digest: str) -> MaskResult:
    return MaskResult.model_validate_json(store.get(digest, namespace="segmentation"))


def require_real_model(result: MaskResult) -> None:
    if result.executionClass != "real_model" or result.status != "complete" or not _valid_sha(result.modelDigest):
        raise ValueError("real model acceptance requires a complete non-stub artifact")
