"""GA-06/07 perception benchmarks and GA-08 tracker/team adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast
from collections.abc import Iterable, Sequence

import numpy as np
from pydantic import Field

from .contracts import ObservationSource, StrictModel
from .identity import reconnect_across_cut, tracker_chunk

Stratum = Literal["near", "middle", "far", "small", "negative"]


class Detection(StrictModel):
    frameId: int
    bbox: tuple[float, float, float, float]
    score: float
    kind: Literal["player", "ball", "official", "other"]
    stratum: Stratum
    observationSource: ObservationSource = "observed"


class Label(StrictModel):
    frameId: int
    bbox: tuple[float, float, float, float]
    kind: Literal["player", "ball", "official", "other", "negative"]
    stratum: Stratum
    visible: bool = True


class BenchmarkReceipt(StrictModel):
    task: Literal["player_coverage", "ball_detection", "identity"]
    configuration: str
    precision: float | None
    recall: float | None
    localisationErrorPx: float | None
    centreOffsetPx: float | None = None
    meanOneMinusIou: float | None = None
    latencyMs: float | None
    peakMemoryMb: float | None
    falsePositives: int
    falseNegatives: int
    ignoredOtherClass: int = 0
    failureExamples: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    labelsIndependent: bool


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom else 0.0


def score_detections(
    detections: list[Detection],
    labels: list[Label],
    *,
    task: Literal["player_coverage", "ball_detection"],
    configuration: str,
    iou_threshold: float = 0.5,
    labels_independent: bool,
    count_other_class_as_fp: bool = False,
) -> BenchmarkReceipt:
    used_labels: set[int] = set()
    true_positive = 0
    centre_offsets: list[float] = []
    one_minus_iou: list[float] = []
    failures: list[str] = []
    task_kind = "player" if task == "player_coverage" else "ball"
    in_task = [detection for detection in detections if detection.kind == task_kind]
    other = [detection for detection in detections if detection.kind != task_kind]
    if task == "player_coverage":
        eligible = [label for label in labels if label.kind == "player"]
        negatives = [label for label in labels if label.kind == "negative"]
    else:
        eligible = [label for label in labels if label.kind == "ball" and label.visible]
        negatives = [label for label in labels if label.kind == "negative" or (label.kind == "ball" and not label.visible)]
    for detection in in_task:
        match_index = None
        best = 0.0
        for index, label in enumerate(eligible):
            if index in used_labels or label.frameId != detection.frameId:
                continue
            overlap = _iou(detection.bbox, label.bbox)
            if overlap > best:
                best = overlap
                match_index = index
        if match_index is not None and best >= iou_threshold:
            used_labels.add(match_index)
            true_positive += 1
            label = eligible[match_index]
            detection_centre = ((detection.bbox[0] + detection.bbox[2]) / 2, (detection.bbox[1] + detection.bbox[3]) / 2)
            label_centre = ((label.bbox[0] + label.bbox[2]) / 2, (label.bbox[1] + label.bbox[3]) / 2)
            centre_offsets.append(
                ((detection_centre[0] - label_centre[0]) ** 2 + (detection_centre[1] - label_centre[1]) ** 2) ** 0.5
            )
            one_minus_iou.append(1.0 - best)
        else:
            failures.append(f"fp:{detection.frameId}:{detection.kind}:{detection.stratum}")
    false_negative = len(eligible) - len(used_labels)
    false_positive = len(in_task) - true_positive + (len(other) if count_other_class_as_fp else 0)
    for label in negatives:
        for detection in in_task:
            if detection.frameId == label.frameId and _iou(detection.bbox, label.bbox) >= iou_threshold:
                failures.append(f"negative_hit:{label.frameId}:{label.stratum}")
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else None
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else None
    notes = []
    if not labels_independent:
        notes.append("LABELS_INCOMPLETE")
    return BenchmarkReceipt(
        task=task,
        configuration=configuration,
        precision=precision,
        recall=recall,
        localisationErrorPx=(sum(centre_offsets) / len(centre_offsets)) if centre_offsets else None,
        centreOffsetPx=(sum(centre_offsets) / len(centre_offsets)) if centre_offsets else None,
        meanOneMinusIou=(sum(one_minus_iou) / len(one_minus_iou)) if one_minus_iou else None,
        latencyMs=None,
        peakMemoryMb=None,
        falsePositives=false_positive,
        falseNegatives=false_negative,
        ignoredOtherClass=len(other),
        failureExamples=failures[:12],
        notes=notes,
        labelsIndependent=labels_independent,
    )


class StratumBenchmark(StrictModel):
    byStratum: dict[str, BenchmarkReceipt]
    labelsIndependent: bool


def score_detections_by_stratum(
    detections: list[Detection],
    labels: list[Label],
    *,
    task: Literal["player_coverage", "ball_detection"],
    configuration: str,
    iou_threshold: float = 0.5,
    labels_independent: bool,
) -> StratumBenchmark:
    strata = sorted({item.stratum for item in detections} | {item.stratum for item in labels})
    by_stratum: dict[str, BenchmarkReceipt] = {}
    for stratum in strata:
        by_stratum[stratum] = score_detections(
            [item for item in detections if item.stratum == stratum],
            [item for item in labels if item.stratum == stratum],
            task=task,
            configuration=f"{configuration}:{stratum}",
            iou_threshold=iou_threshold,
            labels_independent=labels_independent,
        )
    return StratumBenchmark(byStratum=by_stratum, labelsIndependent=labels_independent)


def tile_to_source(
    bbox: tuple[float, float, float, float],
    *,
    origin: tuple[float, float],
    scale: float = 1.0,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    ox, oy = origin
    return (ox + x1 * scale, oy + y1 * scale, ox + x2 * scale, oy + y2 * scale)


def unwrap_ultralytics_track_result(tracked: object) -> object:
    """Ultralytics track() may return a Result, a list, or an iterator of Results."""

    if hasattr(tracked, "boxes"):
        return tracked
    if isinstance(tracked, (list, tuple)):
        if not tracked:
            raise RuntimeError("ultralytics track returned no results")
        return tracked[0]
    try:
        return next(iter(cast(Iterable[object], tracked)))
    except StopIteration as exc:
        raise RuntimeError("ultralytics track returned no results") from exc


def _ultralytics_scalar(value: Any) -> float:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return _ultralytics_scalar(value[0] if value else 0)
    return float(value or 0)


def _ultralytics_xyxy(value: Any) -> tuple[float, float, float, float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)) and value and hasattr(value[0], "tolist"):
        value = value[0].tolist()
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = value[0]
    coords = [float(item) for item in list(value)[:4]]
    while len(coords) < 4:
        coords.append(0.0)
    return (coords[0], coords[1], coords[2], coords[3])


def _ultralytics_observed_device(result: object) -> str | None:
    boxes = getattr(result, "boxes", None)
    tensor = getattr(boxes, "data", None)
    device = getattr(tensor, "device", None)
    return str(device) if device is not None else None


def merge_tiled_detections(
    detections: list[dict[str, Any]],
    *,
    iou_threshold: float,
) -> list[dict[str, Any]]:
    ordered = sorted(
        detections,
        key=lambda item: (-float(item.get("score") or 0.0), str(item.get("tileId") or "")),
    )
    kept: list[dict[str, Any]] = []
    for detection in ordered:
        bbox = tuple(float(value) for value in detection["bbox"])
        if any(
            item.get("frameId") == detection.get("frameId")
            and item.get("kind") == detection.get("kind")
            and _iou(bbox, tuple(float(value) for value in item["bbox"])) >= iou_threshold
            for item in kept
        ):
            continue
        kept.append({**detection, "bbox": bbox, "sourceCoordinates": True, "deterministic": True})
    return kept


class PreprocessPlan:
    """Metadata-only preview for the development contract endpoint."""

    name = "bgr_compatible_preprocess"

    def transform(
        self,
        *,
        pixels: bytes,
        width: int,
        height: int,
        colour_order: str,
        crop: tuple[int, int, int, int] | None = None,
        resize: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        del width, height
        order = colour_order.lower()
        converted = bytearray(pixels)
        if order == "rgb":
            for index in range(0, len(converted) - 2, 3):
                converted[index], converted[index + 2] = converted[index + 2], converted[index]
            order = "bgr"
        return {
            "pixels": bytes(converted),
            "colourOrder": order,
            "crop": list(crop) if crop else None,
            "resize": list(resize) if resize else None,
            "sourceCoordinatesUnchanged": True,
            "silentlyChangedColour": False,
            "footballRulesApplied": False,
            "requestedColourOrder": colour_order.lower(),
        }


@dataclass(frozen=True)
class InverseTransform:
    crop: tuple[int, int, int, int]
    output_size: tuple[int, int]

    def map_box(self, bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = bbox
        crop_x1, crop_y1, crop_x2, crop_y2 = self.crop
        output_width, output_height = self.output_size
        scale_x = (crop_x2 - crop_x1) / output_width
        scale_y = (crop_y2 - crop_y1) / output_height
        return (
            crop_x1 + x1 * scale_x,
            crop_y1 + y1 * scale_y,
            crop_x1 + x2 * scale_x,
            crop_y1 + y2 * scale_y,
        )


class Preprocessor:
    """Apply colour, crop, and resize operations while retaining source mapping."""

    def transform(
        self,
        frame: dict[str, Any],
        *,
        crop: tuple[int, int, int, int] | None = None,
        resize: tuple[int, int] | None = None,
    ) -> tuple[np.ndarray, InverseTransform]:
        width = int(frame["width"])
        height = int(frame["height"])
        pixels = np.frombuffer(frame["pixels"], dtype=np.uint8)
        if width <= 0 or height <= 0 or pixels.size != width * height * 3:
            raise ValueError("frame pixels must match positive width and height")
        image = pixels.reshape(height, width, 3)
        colour_order = str(frame.get("colourOrder", frame.get("colour_order", "bgr"))).lower()
        if colour_order == "rgb":
            image = image[..., ::-1]
        elif colour_order != "bgr":
            raise ValueError("colour order must be rgb or bgr")

        region = crop or (0, 0, width, height)
        x1, y1, x2, y2 = region
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("crop must be within the source frame")
        image = np.ascontiguousarray(image[y1:y2, x1:x2])

        output_size = resize or (x2 - x1, y2 - y1)
        output_width, output_height = output_size
        if output_width <= 0 or output_height <= 0:
            raise ValueError("resize dimensions must be positive")
        if image.shape[:2] != (output_height, output_width):
            try:
                import cv2

                image = cv2.resize(image, output_size, interpolation=cv2.INTER_NEAREST)
            except ImportError:
                rows = np.arange(output_height) * image.shape[0] // output_height
                columns = np.arange(output_width) * image.shape[1] // output_width
                image = image[rows[:, None], columns]
        return image, InverseTransform(crop=region, output_size=output_size)


@dataclass(frozen=True)
class Capabilities:
    hw_decode: bool | None
    cuda_inference: bool | None
    hw_encode: bool | None
    notes: tuple[str, ...] = ()


def probe_capabilities() -> Capabilities:
    try:
        import torch
    except ImportError:
        return Capabilities(None, None, None, ("TORCH_UNAVAILABLE",))
    return Capabilities(None, bool(torch.cuda.is_available()), None)


def select_inference_device(requested: str, caps: Capabilities) -> dict[str, Any]:
    if requested == "cpu":
        return {"device": "cpu", "reasonCodes": []}
    if requested != "cuda":
        raise ValueError("inference device must be cpu or cuda")
    if caps.cuda_inference is True:
        return {"device": "cuda", "reasonCodes": []}
    reason = "CUDA_UNPROBED" if caps.cuda_inference is None else "CUDA_UNAVAILABLE"
    return {"device": "cpu", "reasonCodes": [reason]}


class DetectorAdapter:
    """Detector runtime adapter. CUDA visibility is not video-engine capability."""

    name = "ultralytics_fail_closed"

    def detect(
        self,
        frame: dict[str, Any],
        *,
        requested_backend: str = "cpu",
        video_engine_capability: bool = False,
        capabilities: Capabilities | None = None,
        runtime: Any | None = None,
    ) -> dict[str, Any]:
        del video_engine_capability
        selection = select_inference_device(requested_backend, capabilities or probe_capabilities())
        selected = selection["device"]
        fallback = "cpu" if selected != requested_backend else None
        detections: list[dict[str, Any]] = []
        production_path = None
        if callable(runtime):
            wrapped = self.from_ultralytics(runtime(frame), frame_id=int(frame.get("frameId") or 0))
            detections = list(wrapped.get("detections") or [])
            production_path = wrapped.get("productionPath")
            observed_device = wrapped.get("observedDevice")
        else:
            observed_device = None
        return {
            "requestedBackend": requested_backend,
            "selectedBackend": selected,
            "observedDevice": observed_device,
            "fallback": fallback,
            "reasonCodes": selection["reasonCodes"],
            "silentlyChangedColour": False,
            "exportFpsEqualsInferenceFps": False,
            "colourOrder": frame.get("colourOrder", "bgr"),
            "counts": {"primary": len(detections), "recovery": 0},
            "detections": detections,
            "productionPath": production_path,
        }

    def ingest_recovery_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        detections: list[dict[str, Any]] = []
        for row in rows:
            source = str(row.get("observationSource") or row.get("source") or row.get("Ball_Source") or "")
            if source in {"observed", "visible", "observed_ball"}:
                observation = "observed_ball"
            elif source in {"inferred", "inferred_ball", "temporally_predicted"}:
                observation = "inferred_ball"
            else:
                observation = "inferred_ball"
            detections.append(
                {
                    "frameId": int(row.get("Frame_ID") or row.get("frameId") or 0),
                    "bbox": (
                        float(row.get("Source_X1") or 0.0),
                        float(row.get("Source_Y1") or 0.0),
                        float(row.get("Source_X2") or 0.0),
                        float(row.get("Source_Y2") or 0.0),
                    ),
                    "score": float(row.get("Conf") or row.get("score") or 0.0),
                    "kind": "ball",
                    "observationSource": observation,
                    "stratum": "near",
                }
            )
        states = separate_ball_states(detections)
        return {
            "requestedBackend": "cpu",
            "selectedBackend": "cpu",
            "observedDevice": None,
            "fallback": None,
            "silentlyChangedColour": False,
            "exportFpsEqualsInferenceFps": False,
            "counts": {"primary": states["visible"], "recovery": states["inferred"] + states["unknown"]},
            "detections": detections,
            "states": states,
            "productionPath": "recover_ball_rows",
            "labelsIndependent": False,
        }

    def from_ultralytics(self, result: object, *, frame_id: int = 0) -> dict[str, Any]:
        detections: list[dict[str, Any]] = []
        boxes = getattr(result, "boxes", None) or []
        for box in boxes:
            cls_id = int(_ultralytics_scalar(getattr(box, "cls", 0)))
            score = float(_ultralytics_scalar(getattr(box, "conf", 0.0)))
            xyxy = _ultralytics_xyxy(getattr(box, "xyxy", (0, 0, 0, 0)))
            kind = "ball" if cls_id in {32, 37} else "player" if cls_id == 0 else "other"
            detections.append(
                {
                    "frameId": frame_id,
                    "bbox": xyxy,
                    "score": score,
                    "kind": kind,
                    "observationSource": "observed",
                    "stratum": "near",
                }
            )
        return {
            "requestedBackend": "cpu",
            "selectedBackend": "cpu",
            "observedDevice": _ultralytics_observed_device(result),
            "fallback": None,
            "silentlyChangedColour": False,
            "exportFpsEqualsInferenceFps": False,
            "counts": {"primary": len(detections), "recovery": 0},
            "detections": detections,
            "productionPath": "ultralytics",
        }


class IouAssociationFallback:
    name = "iou_fallback"

    def associate(
        self,
        detections: list[Detection],
        *,
        cut_detected: bool = False,
        broadcast_replay: bool = False,
        previous_tracks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        chunk = tracker_chunk(scene_discontinuity=cut_detected, broadcast_replay=broadcast_replay)
        policy = reconnect_across_cut(cut_detected=cut_detected or broadcast_replay)
        reset = bool(chunk["reset"] or policy["reset"])
        used_previous: set[int] = set()
        tracks = []
        for detection in detections:
            prefix = f"{self.name}:reset" if reset else self.name
            track_id = f"{prefix}:{detection.frameId}:{detection.bbox}"
            if not reset and previous_tracks:
                best_index = None
                best_iou = 0.5
                for index, previous in enumerate(previous_tracks):
                    if index in used_previous:
                        continue
                    previous_bbox = previous.get("bbox")
                    if not previous_bbox:
                        continue
                    score = _iou(detection.bbox, tuple(previous_bbox))
                    if score >= best_iou:
                        best_iou = score
                        best_index = index
                if best_index is not None:
                    used_previous.add(best_index)
                    track_id = str(previous_tracks[best_index]["trackId"])
            tracks.append(
                {
                    "frameId": detection.frameId,
                    "trackId": track_id,
                    "bbox": detection.bbox,
                    "kind": detection.kind,
                    "observationSource": detection.observationSource,
                    "reset": reset,
                    "silentlyReconnected": False,
                    "productionPath": "iou_fallback",
                    "productionEligible": False,
                }
            )
        return tracks


class TrackerAdapter:
    """Read identities assigned by the core Ultralytics/BoTSORT tracker."""

    name = "ultralytics_botsort"

    def from_ultralytics(self, result: object, *, detections: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        boxes = getattr(result, "boxes", None) or []
        tracks: list[dict[str, Any]] = []
        for index, box in enumerate(boxes):
            track_id = getattr(box, "id", None)
            identity = "unassigned" if track_id is None else str(int(_ultralytics_scalar(track_id)))
            detection = (detections or [{}])[index] if detections and index < len(detections) else {}
            tracks.append(
                {
                    "frameId": detection.get("frameId", 0),
                    "trackId": identity,
                    "bbox": detection.get("bbox") or _ultralytics_xyxy(getattr(box, "xyxy", (0, 0, 0, 0))),
                    "kind": detection.get("kind", "player"),
                    "observationSource": detection.get("observationSource", "observed"),
                    "reset": False,
                    "silentlyReconnected": False,
                    "productionPath": "botsort",
                }
            )
        return tracks


class IdentityRepair:
    def __init__(self) -> None:
        self.edits: list[dict[str, Any]] = []

    def split(self, track_id: str, at_frame: int, *, author: str) -> dict[str, Any]:
        edit = {"kind": "track_split", "trackId": track_id, "atFrame": at_frame, "author": author}
        self.edits.append(edit)
        return edit

    def join(self, left_track_id: str, right_track_id: str, *, author: str) -> dict[str, Any]:
        edit = {
            "kind": "track_join",
            "leftTrackId": left_track_id,
            "rightTrackId": right_track_id,
            "author": author,
        }
        self.edits.append(edit)
        return edit


def separate_ball_states(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"visible": 0, "inferred": 0, "unknown": 0}
    for row in rows:
        source = row.get("observationSource") or row.get("source") or "unknown"
        if source in {"observed", "visible", "observed_ball"}:
            counts["visible"] += 1
        elif source in {"inferred", "inferred_ball", "temporally_predicted"}:
            counts["inferred"] += 1
        else:
            counts["unknown"] += 1
    return counts


def preview_identity_change(
    *,
    kind: str,
    track_id: str | None = None,
    at_frame: int | None = None,
    interval_start: float | None = None,
    interval_end: float | None = None,
) -> dict[str, Any]:
    start = float(at_frame if at_frame is not None else interval_start or 0.0)
    end = float(interval_end if interval_end is not None else start)
    invalidates = ["ownership", "player_events", "metrics", "report"]
    if kind == "team_mapping":
        invalidates = ["team_state", "events", "metrics", "report"]
    return {
        "preview": True,
        "committed": False,
        "kind": kind,
        "trackId": track_id,
        "newMappingShown": kind == "team_mapping",
        "affectedIntervals": [{"start": start, "end": end}],
        "invalidates": invalidates,
        "visionRerun": False,
    }
