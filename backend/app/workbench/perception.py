"""GA-06/07 perception benchmarks and GA-08 tracker/team adapters."""

from __future__ import annotations

from typing import Any, Literal

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
    latencyMs: float | None
    peakMemoryMb: float | None
    falsePositives: int
    falseNegatives: int
    failureExamples: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    labelsIndependent: bool


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
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
) -> BenchmarkReceipt:
    used_labels: set[int] = set()
    true_positive = 0
    localisation: list[float] = []
    failures: list[str] = []
    if task == "player_coverage":
        eligible = [label for label in labels if label.kind == "player"]
        negatives = [label for label in labels if label.kind == "negative"]
    else:
        eligible = [label for label in labels if label.kind == "ball" and label.visible]
        negatives = [label for label in labels if label.kind == "negative" or (label.kind == "ball" and not label.visible)]
    for detection in detections:
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
            localisation.append(1.0 - best)
        else:
            failures.append(f"fp:{detection.frameId}:{detection.kind}:{detection.stratum}")
    false_negative = len(eligible) - len(used_labels)
    false_positive = len(detections) - true_positive
    for label in negatives:
        for detection in detections:
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
        localisationErrorPx=(sum(localisation) / len(localisation)) if localisation else None,
        latencyMs=None,
        peakMemoryMb=None,
        falsePositives=false_positive,
        falseNegatives=false_negative,
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
        if any(_iou(bbox, tuple(float(value) for value in item["bbox"])) >= iou_threshold for item in kept):
            continue
        kept.append({**detection, "bbox": bbox, "sourceCoordinates": True, "deterministic": True})
    return kept


class PreprocessorAdapter:
    """Colour/crop/resize adapter. Football coordinates stay in source space."""

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


class DetectorAdapter:
    """Detector runtime adapter. CUDA visibility is not video-engine capability."""

    name = "ultralytics_fail_closed"

    def detect(
        self,
        frame: dict[str, Any],
        *,
        requested_backend: str = "cpu",
        video_engine_capability: bool = False,
    ) -> dict[str, Any]:
        selected = requested_backend
        fallback = None
        if requested_backend == "cuda" and not video_engine_capability:
            selected = "cpu"
            fallback = "cpu"
        return {
            "requestedBackend": requested_backend,
            "selectedBackend": selected,
            "fallback": fallback,
            "silentlyChangedColour": False,
            "exportFpsEqualsInferenceFps": False,
            "colourOrder": frame.get("colourOrder", "bgr"),
            "counts": {"primary": 0, "recovery": 0},
            "detections": [],
        }


class TrackerAdapter:
    name = "botsort_baseline"

    def associate(
        self,
        detections: list[Detection],
        *,
        cut_detected: bool = False,
        broadcast_replay: bool = False,
        previous_tracks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        del previous_tracks
        chunk = tracker_chunk(scene_discontinuity=cut_detected, broadcast_replay=broadcast_replay)
        policy = reconnect_across_cut(cut_detected=cut_detected or broadcast_replay)
        tracks = []
        for detection in detections:
            prefix = f"{self.name}:reset" if chunk["reset"] else self.name
            tracks.append(
                {
                    "frameId": detection.frameId,
                    "trackId": f"{prefix}:{detection.frameId}:{detection.bbox}",
                    "bbox": detection.bbox,
                    "kind": detection.kind,
                    "observationSource": detection.observationSource,
                    "reset": chunk["reset"] or policy["reset"],
                    "silentlyReconnected": False,
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
