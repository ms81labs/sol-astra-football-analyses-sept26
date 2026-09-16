"""GA-06/07 perception benchmarks and GA-08 tracker/team adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import ObservationSource, StrictModel

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


class TrackerAdapter:
    name = "botsort_baseline"

    def associate(self, detections: list[Detection]) -> list[dict[str, Any]]:
        tracks = []
        for detection in detections:
            tracks.append(
                {
                    "frameId": detection.frameId,
                    "trackId": f"{self.name}:{detection.frameId}:{detection.bbox}",
                    "bbox": detection.bbox,
                    "kind": detection.kind,
                    "observationSource": detection.observationSource,
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
