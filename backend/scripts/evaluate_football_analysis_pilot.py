"""Protocol-v3 metrics for the frozen football-analysis pilot."""

from __future__ import annotations

import hashlib
import importlib
import io
import argparse
import csv
import json
import math
from pathlib import Path
import re
from statistics import NormalDist, median
import subprocess
import sys
from contextlib import redirect_stdout
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.scripts.validate_football_analysis_pilot_labels import parse_unique_json, parse_utc_timestamp


TRACKEVAL_COMMIT = "12c8791b303e0a0b50f753af204249e622d0281a"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_PILOT_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1"


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_declaration(path: Path, source_id: str) -> tuple[str, str]:
    raw = path.read_bytes()
    value = parse_unique_json(raw)
    keys = {
        "schemaVersion", "sourceId", "myTeamSide", "reviewerId", "declaredAt",
        "footageBasis", "independentDeclaration", "pipelineOutputUsed",
    }
    if (
        type(value) is not dict or set(value) != keys
        or value["schemaVersion"] != "football_analysis_pilot_source_declaration_v1"
        or value["sourceId"] != source_id
        or type(value["myTeamSide"]) is not str or value["myTeamSide"] not in {"home", "away"}
        or any(type(value[key]) is not str or not value[key].strip()
               for key in ("reviewerId", "footageBasis"))
        or value["independentDeclaration"] is not True
        or value["pipelineOutputUsed"] is not False
    ):
        raise ValueError("source declaration is incomplete or does not match the source")
    parse_utc_timestamp(value["declaredAt"], "source declaration declaredAt")
    return value["myTeamSide"], hashlib.sha256(raw).hexdigest()


def load_prediction_artifacts(
    artifact_dir: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[int, str]]:
    """Load the native files persisted for one application match."""

    rows = _read_json(artifact_dir / "raw_rows.json")
    analytics = _read_json(artifact_dir / "analytics.json")
    events = _read_json(artifact_dir / "events.json")
    layers = _read_json(artifact_dir / "ball_truth_layers.json")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("raw_rows.json must contain an array of objects")
    if not isinstance(analytics, dict) or not isinstance(analytics.get("ballAssignments"), list):
        raise ValueError("analytics.json must contain ballAssignments")
    assignments = analytics["ballAssignments"]
    if not all(isinstance(item, dict) for item in assignments):
        raise ValueError("analytics ballAssignments must contain objects")
    if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
        raise ValueError("events.json must contain an array of objects")
    if not isinstance(layers, dict):
        raise ValueError("ball_truth_layers.json must contain an object")
    sources: dict[int, str] = {}
    for layer_name, source in (("inferredBall", "inferred"), ("observedBall", "observed")):
        layer = layers.get(layer_name)
        if not isinstance(layer, dict) or not isinstance(layer.get("rows"), list):
            raise ValueError(f"ball_truth_layers.json must contain {layer_name}.rows")
        for row in layer["rows"]:
            if not isinstance(row, dict) or "Frame_ID" not in row:
                raise ValueError(f"{layer_name}.rows must contain objects with Frame_ID")
            sources[int(row["Frame_ID"])] = source
    return rows, assignments, events, sources


def _validated_input_video_identity(artifact_dir: Path, expected_sha256: str) -> str:
    if type(expected_sha256) is not str or _SHA256.fullmatch(expected_sha256) is None:
        raise ValueError("expected input-video SHA-256 must be a lower-case digest")
    try:
        identity = _read_json(artifact_dir / "input_video_identity.json")
    except (OSError, ValueError) as exc:
        raise ValueError("input_video_identity.json is missing or invalid") from exc
    keys = {
        "schemaVersion", "jobId", "matchId", "sourceCommit", "manifestSha256",
        "receiptSha256", "inputVideoSha256", "inputVideoSizeBytes",
    }
    if (
        type(identity) is not dict
        or set(identity) != keys
        or type(identity["schemaVersion"]) is not int
        or identity["schemaVersion"] != 1
        or type(identity["jobId"]) is not str
        or not identity["jobId"]
        or identity["matchId"] != artifact_dir.name
        or type(identity["sourceCommit"]) is not str
        or _COMMIT.fullmatch(identity["sourceCommit"]) is None
        or any(type(identity[key]) is not str or _SHA256.fullmatch(identity[key]) is None
               for key in ("manifestSha256", "receiptSha256", "inputVideoSha256"))
        or type(identity["inputVideoSizeBytes"]) is not int
        or identity["inputVideoSizeBytes"] <= 0
        or identity["inputVideoSha256"] != expected_sha256
    ):
        raise ValueError("native artifact input-video identity does not match the declared clip")
    return expected_sha256


def _declared_input_video_sha256(task: Mapping[str, object], task_manifest: Path, media_root: Path) -> str:
    """Bind one held-out worker input to the frozen task and local clip bytes."""

    task_id = task.get("taskId")
    start = task.get("sourceStartFrame")
    end = task.get("sourceEndFrameExclusive")
    step = task.get("evaluationFrameStep")
    if (
        type(task_id) is not str or not task_id or Path(task_id).name != task_id
        or any(type(value) is not int for value in (start, end, step))
        or start < 0 or end <= start or step <= 0
    ):
        raise ValueError("frozen task input-video identity is invalid")

    def digest(path: Path) -> str:
        with path.open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()

    clips = _read_json(media_root / "annotation_clips" / "annotation_clips_manifest_v1.json")
    if (
        type(clips) is not dict or type(clips.get("entries")) is not list
        or clips.get("taskManifestSha256") != digest(task_manifest)
    ):
        raise ValueError("annotation clips do not match the frozen task manifest")
    entries = [entry for entry in clips["entries"] if type(entry) is dict and entry.get("taskId") == task_id]
    if len(entries) != 1:
        raise ValueError("frozen task must identify exactly one annotation clip")
    clip = entries[0]
    annotation_path = media_root / "annotation_clips" / f"{task_id}.mp4"
    declared_path = Path(clip["path"]) if type(clip.get("path")) is str else None
    if declared_path is not None and not declared_path.is_absolute():
        declared_path = Path(__file__).resolve().parents[2] / declared_path
    if (
        declared_path is None or declared_path.resolve() != annotation_path.resolve()
        or clip.get("sourceStartFrame") != start or clip.get("sourceEndFrameExclusive") != end
        or clip.get("frameCount") != end - start
        or clip.get("width") != task.get("sourceWidth") or clip.get("height") != task.get("sourceHeight")
        or clip.get("sourceVideoSha256") != task.get("videoSha256")
        or type(clip.get("sha256")) is not str or _SHA256.fullmatch(clip["sha256"]) is None
    ):
        raise ValueError("annotation clip does not match the frozen task")
    if digest(annotation_path) != clip["sha256"]:
        raise ValueError("annotation clip SHA-256 does not match its manifest")
    if start % step == 0:
        return clip["sha256"]

    aligned_manifest = media_root / "inference_clips" / "aligned_media_manifest_v1.tsv"
    with aligned_manifest.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream, delimiter="\t") if row.get("taskId") == task_id]
    if len(rows) != 1:
        raise ValueError("frozen task must identify exactly one aligned clip")
    row = rows[0]
    aligned_start = start - start % step
    prefix = start - aligned_start
    if (
        row.get("alignedStartFrame") != str(aligned_start)
        or row.get("prefixFrames") != str(prefix)
        or row.get("frameCount") != str(end - aligned_start)
        or row.get("sourceVideoSha256") != task.get("videoSha256")
        or row.get("annotationSha256") != clip["sha256"]
        or type(row.get("alignedSha256")) is not str or _SHA256.fullmatch(row["alignedSha256"]) is None
    ):
        raise ValueError("aligned clip does not match the frozen task")
    aligned_path = media_root / "inference_clips" / f"{task_id}-aligned.mp4"
    if digest(aligned_path) != row["alignedSha256"]:
        raise ValueError("aligned clip SHA-256 does not match its manifest")
    return row["alignedSha256"]


def evaluate_task_artifacts(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    protocol: Mapping[str, object],
    *,
    artifact_dir: Path,
    prediction_scope: str,
    prediction_source_start_frame: int | None = None,
    expected_input_video_sha256: str | None = None,
    trackeval_root: Path,
    team_mapping: Mapping[str, str] | None = None,
) -> dict[str, object]:
    if task.get("evaluationRole") == "held_out_test" and expected_input_video_sha256 is None:
        raise ValueError("held-out scoring requires the declared input-video SHA-256")
    input_sha256 = (
        _validated_input_video_identity(artifact_dir, expected_input_video_sha256)
        if expected_input_video_sha256 is not None else None
    )
    rows, assignments, events, sources = load_prediction_artifacts(artifact_dir)
    rows, assignments, events, sources = normalize_prediction_artifacts(
        task,
        rows,
        assignments,
        events,
        sources,
        prediction_scope=prediction_scope,
        prediction_source_start_frame=prediction_source_start_frame,
    )
    players = evaluate_players(task, labels, rows, protocol, team_mapping=team_mapping)
    associations = players.pop("trackAssociations")
    return {
        "schemaVersion": "football_analysis_pilot_task_result_v1",
        "taskId": task["taskId"],
        "sourceId": task["sourceId"],
        "predictionScope": prediction_scope,
        "predictionInputVideoSha256": input_sha256,
        "predictionSourceStartFrame": (
            prediction_source_start_frame
            if prediction_source_start_frame is not None
            else int(task["sourceStartFrame"]) if prediction_scope == "task-interval" else None
        ),
        "teamMapping": dict(team_mapping or {}),
        "ball": evaluate_ball(task, labels, rows, protocol, prediction_sources=sources),
        "players": players,
        "tracking": evaluate_tracking(
            build_trackeval_sequence_data(task, labels, rows, protocol),
            trackeval_root=trackeval_root,
        ),
        "possession": evaluate_possession(
            task,
            labels,
            assignments,
            protocol,
            track_associations=associations,
            team_mapping=team_mapping,
        ),
        "pitch": evaluate_pitch(task, labels, rows, protocol, track_associations=associations),
        "events": evaluate_events(task, labels, events, protocol),
    }


def normalize_prediction_artifacts(
    task: Mapping[str, object],
    raw_rows: Sequence[Mapping[str, object]],
    assignments: Sequence[Mapping[str, object]],
    events: Sequence[Mapping[str, object]],
    ball_sources: Mapping[int, str],
    *,
    prediction_scope: str,
    prediction_source_start_frame: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[int, str]]:
    if prediction_scope not in {"whole-source", "task-interval"}:
        raise ValueError("prediction_scope must be whole-source or task-interval")
    if prediction_scope == "whole-source":
        if prediction_source_start_frame is not None:
            raise ValueError("whole-source predictions cannot have a clip start frame")
        frame_offset = 0
    else:
        start = int(task["sourceStartFrame"])
        step = int(task["evaluationFrameStep"])
        if step <= 0:
            raise ValueError("evaluation frame step must be positive")
        aligned_start = start - start % step
        if prediction_source_start_frame is None:
            if aligned_start != start:
                raise ValueError("off-grid task-interval predictions cannot match frozen source frames; use whole-source artifacts or a globally aligned inference clip")
            frame_offset = start
        elif type(prediction_source_start_frame) is not int or prediction_source_start_frame != aligned_start:
            raise ValueError("prediction clip start frame must equal the globally aligned source frame")
        else:
            frame_offset = prediction_source_start_frame
    time_offset = frame_offset / float(task["sourceFps"])
    normalized_rows = [
        {
            **row,
            "Frame_ID": int(row["Frame_ID"]) + frame_offset,
            "Timestamp": float(row["Timestamp"]) + time_offset,
        }
        for row in raw_rows
    ]
    normalized_assignments = [
        {
            **assignment,
            "frameId": int(assignment["frameId"]) + frame_offset,
            "timestamp": float(assignment["timestamp"]) + time_offset,
        }
        for assignment in assignments
    ]
    normalized_events = [
        {
            **event,
            "frameId": int(event["frameId"]) + frame_offset,
            "timestamp": float(event["timestamp"]) + time_offset,
        }
        for event in events
    ]
    return normalized_rows, normalized_assignments, normalized_events, {
        int(frame_id) + frame_offset: source for frame_id, source in ball_sources.items()
    }


def evaluation_frame_ids(task: Mapping[str, object], protocol: Mapping[str, object]) -> list[int]:
    frame_rule = protocol["evaluationFrames"]
    if not isinstance(frame_rule, Mapping):
        raise ValueError("evaluationFrames must be an object")
    fps = float(task["sourceFps"])
    target_fps = int(frame_rule["targetFps"])
    if not math.isfinite(fps) or fps <= 0 or target_fps <= 0:
        raise ValueError("sourceFps and targetFps must be positive")
    step = max(1, math.floor(fps / target_fps))
    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    selected = [frame_id for frame_id in range(start, end) if frame_id % step == 0]
    if task.get("evaluationFrameStep") != step or task.get("evaluationFrameCount") != len(selected):
        raise ValueError("task evaluation frame cadence does not match the frozen protocol")
    return selected


def wilson_interval(successes: int, total: int, *, level: float) -> tuple[float, float] | None:
    if successes < 0 or total < 0 or successes > total:
        raise ValueError("Wilson counts are invalid")
    if total == 0:
        return None
    if not 0 < level < 1:
        raise ValueError("confidence level must be between zero and one")
    z = NormalDist().inv_cdf(0.5 + level / 2)
    estimate = successes / total
    denominator = 1 + z * z / total
    center = (estimate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(estimate * (1 - estimate) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def _iou(left: Sequence[float], right: Sequence[float]) -> float:
    intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _prediction_bbox(row: Mapping[str, object]) -> tuple[float, float, float, float]:
    values = tuple(float(row[key]) for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2"))
    if any(not math.isfinite(value) for value in values) or values[0] >= values[2] or values[1] >= values[3]:
        raise ValueError("prediction bbox is invalid")
    return values


def evaluate_ball(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
    *,
    prediction_sources: Mapping[int, str] | None = None,
) -> dict[str, object]:
    frames = labels.get("frames")
    if not isinstance(frames, list):
        raise ValueError("labels must contain frames")
    labels_by_frame = {int(frame["frameId"]): frame for frame in frames if isinstance(frame, Mapping)}
    selected = evaluation_frame_ids(task, protocol)
    predictions_by_frame: dict[int, list[tuple[float, float, float, float]]] = {}
    for row in prediction_rows:
        if row.get("Entity_Type") != "ball":
            continue
        frame_id = int(row["Frame_ID"])
        if frame_id in selected:
            predictions_by_frame.setdefault(frame_id, []).append(_prediction_bbox(row))

    ball_protocol = protocol["ball"]
    confidence_protocol = protocol["confidenceIntervals"]
    if not isinstance(ball_protocol, Mapping) or not isinstance(confidence_protocol, Mapping):
        raise ValueError("ball and confidenceIntervals must be objects")
    threshold = float(ball_protocol["iouThreshold"])
    level = float(confidence_protocol["level"])
    counts = {
        "evaluationFrames": len(selected),
        "ignoredFrames": 0,
        "visibleTruth": 0,
        "notVisibleTruth": 0,
        "predictions": 0,
        "truePositives": 0,
        "falsePositives": 0,
        "falseNegatives": 0,
    }
    source_counts = {"observed": 0, "inferred": 0, "unknown": 0}
    matched_ious: list[float] = []
    center_errors: list[float] = []
    for frame_id in selected:
        frame = labels_by_frame.get(frame_id)
        if not isinstance(frame, Mapping) or not isinstance(frame.get("ball"), Mapping):
            raise ValueError(f"label frame {frame_id} is missing ball truth")
        ball = frame["ball"]
        visibility = ball["visibility"]
        predictions = predictions_by_frame.get(frame_id, [])
        if visibility in {"occluded", "unknown"}:
            counts["ignoredFrames"] += 1
            continue
        counts["predictions"] += len(predictions)
        source = (prediction_sources or {}).get(frame_id, "unknown")
        source_counts[source if source in source_counts else "unknown"] += len(predictions)
        if visibility == "not_visible":
            counts["notVisibleTruth"] += 1
            counts["falsePositives"] += len(predictions)
            continue
        if visibility != "visible" or not isinstance(ball.get("bbox"), list):
            raise ValueError(f"label frame {frame_id} has invalid ball visibility")
        counts["visibleTruth"] += 1
        truth = tuple(float(value) for value in ball["bbox"])
        if not predictions:
            counts["falseNegatives"] += 1
            continue
        best = max(predictions, key=lambda prediction: _iou(prediction, truth))
        best_iou = _iou(best, truth)
        if best_iou < threshold:
            counts["falseNegatives"] += 1
            counts["falsePositives"] += len(predictions)
            continue
        counts["truePositives"] += 1
        counts["falsePositives"] += len(predictions) - 1
        matched_ious.append(best_iou)
        center_errors.append(math.hypot((best[0] + best[2] - truth[0] - truth[2]) / 2, (best[1] + best[3] - truth[1] - truth[3]) / 2))

    precision_denominator = counts["truePositives"] + counts["falsePositives"]
    recall_denominator = counts["truePositives"] + counts["falseNegatives"]
    scored_frames = counts["evaluationFrames"] - counts["ignoredFrames"]
    scored_minutes = scored_frames / int(protocol["evaluationFrames"]["targetFps"]) / 60  # type: ignore[index]
    return {
        "counts": counts,
        "precision": counts["truePositives"] / precision_denominator if precision_denominator else None,
        "precision95": wilson_interval(counts["truePositives"], precision_denominator, level=level),
        "recall": counts["truePositives"] / recall_denominator if recall_denominator else None,
        "recall95": wilson_interval(counts["truePositives"], recall_denominator, level=level),
        "falsePositivesPerMinute": counts["falsePositives"] / scored_minutes if scored_minutes else None,
        "meanMatchedIoU": sum(matched_ious) / len(matched_ious) if matched_ious else None,
        "medianCenterErrorPixels": median(center_errors) if center_errors else None,
        "predictionSourceBreakdown": source_counts,
    }


def _prediction_kind(row: Mapping[str, object]) -> str | None:
    entity_type = row.get("Entity_Type")
    if entity_type == "referee":
        return "referee"
    if entity_type in {"player", "my_team", "enemy", "home", "away"}:
        return "player"
    return None


def _prediction_team(row: Mapping[str, object], team_mapping: Mapping[str, str]) -> str:
    team = str(row.get("team", row.get("Entity_Type", "unknown")))
    if team in {"home", "away"}:
        return team
    return team_mapping.get(team, "unknown")


def _associate_entities(
    truth: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    threshold: float,
) -> list[tuple[Mapping[str, object], Mapping[str, object]]]:
    if not truth or not predictions:
        return []
    ordered_truth = sorted(truth, key=lambda entity: str(entity["trackId"]))
    ordered_predictions = sorted(predictions, key=lambda row: int(row["Track_ID"]))
    costs = np.full((len(ordered_truth), len(ordered_predictions) + len(ordered_truth)), 2.0, dtype=float)
    costs[:, len(ordered_predictions) :] = 1.0
    for truth_index, truth_entity in enumerate(ordered_truth):
        for prediction_index, prediction in enumerate(ordered_predictions):
            overlap = _iou(truth_entity["bbox"], _prediction_bbox(prediction))  # type: ignore[arg-type]
            if overlap >= threshold:
                costs[truth_index, prediction_index] = 1.0 - overlap
    truth_indices, prediction_indices = linear_sum_assignment(costs)
    return [
        (ordered_truth[truth_index], ordered_predictions[prediction_index])
        for truth_index, prediction_index in zip(truth_indices, prediction_indices)
        if prediction_index < len(ordered_predictions) and costs[truth_index, prediction_index] < 1.0
    ]


def build_trackeval_sequence_data(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
) -> dict[str, object]:
    frames = labels.get("frames")
    if not isinstance(frames, list):
        raise ValueError("labels must contain frames")
    selected = evaluation_frame_ids(task, protocol)
    labels_by_frame = {int(frame["frameId"]): frame for frame in frames if isinstance(frame, Mapping)}
    predictions_by_frame: dict[int, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if _prediction_kind(row) is not None and int(row["Frame_ID"]) in selected:
            predictions_by_frame.setdefault(int(row["Frame_ID"]), []).append(row)
    truth_keys = sorted(
        {
            (str(entity["kind"]), str(entity["trackId"]))
            for frame in frames
            if isinstance(frame, Mapping) and int(frame["frameId"]) in selected
            for entity in frame.get("entities", [])
        }
    )
    prediction_keys = sorted(
        {
            (_prediction_kind(row), str(row["Track_ID"]) if int(row["Track_ID"]) >= 0 else f"untracked-{frame_id}-{index}")
            for frame_id, rows in predictions_by_frame.items()
            for index, row in enumerate(rows)
        }
    )
    truth_ids = {key: index for index, key in enumerate(truth_keys)}
    prediction_ids = {key: index for index, key in enumerate(prediction_keys)}
    gt_ids: list[np.ndarray] = []
    tracker_ids: list[np.ndarray] = []
    similarities: list[np.ndarray] = []
    for frame_id in selected:
        frame = labels_by_frame.get(frame_id)
        if not isinstance(frame, Mapping) or not isinstance(frame.get("entities"), list):
            raise ValueError(f"label frame {frame_id} is missing entity truth")
        truth = frame["entities"]
        predictions = predictions_by_frame.get(frame_id, [])
        gt_ids.append(np.asarray([truth_ids[(str(entity["kind"]), str(entity["trackId"]))] for entity in truth], dtype=int))
        tracker_ids.append(
            np.asarray(
                [
                    prediction_ids[
                        (
                            _prediction_kind(row),
                            str(row["Track_ID"]) if int(row["Track_ID"]) >= 0 else f"untracked-{frame_id}-{index}",
                        )
                    ]
                    for index, row in enumerate(predictions)
                ],
                dtype=int,
            )
        )
        similarities.append(
            np.asarray(
                [
                    [
                        _iou(entity["bbox"], _prediction_bbox(row))  # type: ignore[arg-type]
                        if entity["kind"] == _prediction_kind(row)
                        else 0.0
                        for row in predictions
                    ]
                    for entity in truth
                ],
                dtype=float,
            ).reshape((len(truth), len(predictions)))
        )
    return {
        "num_timesteps": len(selected),
        "num_gt_dets": sum(len(ids) for ids in gt_ids),
        "num_tracker_dets": sum(len(ids) for ids in tracker_ids),
        "num_gt_ids": len(truth_ids),
        "num_tracker_ids": len(prediction_ids),
        "gt_ids": gt_ids,
        "tracker_ids": tracker_ids,
        "similarity_scores": similarities,
    }


def _longest_tracking_gap(data: Mapping[str, object], threshold: float = 0.5) -> int:
    current = np.zeros(int(data["num_gt_ids"]), dtype=int)
    longest = 0
    for gt_ids, tracker_ids, similarity in zip(data["gt_ids"], data["tracker_ids"], data["similarity_scores"]):  # type: ignore[arg-type]
        present = set(gt_ids.tolist())
        matched: set[int] = set()
        if len(gt_ids) and len(tracker_ids):
            truth_indices, prediction_indices = linear_sum_assignment(-similarity)
            matched = {
                int(gt_ids[truth_index])
                for truth_index, prediction_index in zip(truth_indices, prediction_indices)
                if similarity[truth_index, prediction_index] >= threshold
            }
        for truth_id in range(len(current)):
            current[truth_id] = current[truth_id] + 1 if truth_id in present and truth_id not in matched else 0
        longest = max(longest, int(current.max(initial=0)))
    return longest


def evaluate_tracking(data: Mapping[str, object], *, trackeval_root: Path) -> dict[str, object]:
    result = subprocess.run(
        ["git", "-C", str(trackeval_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode or result.stdout.strip() != TRACKEVAL_COMMIT:
        raise ValueError(f"trackeval_root must be the pinned TrackEval commit {TRACKEVAL_COMMIT}")
    try:
        with redirect_stdout(io.StringIO()):
            trackeval = importlib.import_module("trackeval")
    finally:
        sys.path.pop(0)
    if not Path(trackeval.__file__).resolve().is_relative_to(trackeval_root.resolve()):
        raise ValueError("a different TrackEval package is already imported")
    # TrackEval's pinned revision predates NumPy 1.24 alias removals.
    if not hasattr(np, "float"):
        np.float = float  # type: ignore[attr-defined]
    if not hasattr(np, "int"):
        np.int = int  # type: ignore[attr-defined]
    hota = trackeval.metrics.HOTA().eval_sequence(data)
    identity = trackeval.metrics.Identity({"THRESHOLD": 0.5, "PRINT_CONFIG": False}).eval_sequence(data)
    clear = trackeval.metrics.CLEAR({"THRESHOLD": 0.5, "PRINT_CONFIG": False}).eval_sequence(data)
    return {
        "trackEvalCommit": TRACKEVAL_COMMIT,
        "HOTA": float(np.mean(hota["HOTA"])),
        "DetA": float(np.mean(hota["DetA"])),
        "AssA": float(np.mean(hota["AssA"])),
        "IDF1": float(identity["IDF1"]),
        "identitySwitches": int(clear["IDSW"]),
        "longestTrackGapFrames": _longest_tracking_gap(data),
    }


def evaluate_players(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
    *,
    team_mapping: Mapping[str, str] | None = None,
) -> dict[str, object]:
    frames = labels.get("frames")
    player_protocol = protocol.get("players")
    confidence_protocol = protocol.get("confidenceIntervals")
    if not isinstance(frames, list) or not isinstance(player_protocol, Mapping) or not isinstance(confidence_protocol, Mapping):
        raise ValueError("labels frames and player protocol must be present")
    selected = evaluation_frame_ids(task, protocol)
    labels_by_frame = {int(frame["frameId"]): frame for frame in frames if isinstance(frame, Mapping)}
    predictions_by_frame: dict[int, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if _prediction_kind(row) is not None and int(row["Frame_ID"]) in selected:
            predictions_by_frame.setdefault(int(row["Frame_ID"]), []).append(row)
    threshold = float(player_protocol["detectionIouThreshold"])
    level = float(confidence_protocol["level"])
    mapping = team_mapping or {}
    truth_count = prediction_count = 0
    matches: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    track_associations: dict[int, dict[str, int]] = {}
    for frame_id in selected:
        frame = labels_by_frame.get(frame_id)
        if not isinstance(frame, Mapping) or not isinstance(frame.get("entities"), list):
            raise ValueError(f"label frame {frame_id} is missing entity truth")
        frame_truth = frame["entities"]
        frame_predictions = predictions_by_frame.get(frame_id, [])
        truth_count += len(frame_truth)
        prediction_count += len(frame_predictions)
        for kind in ("player", "referee"):
            kind_matches = _associate_entities(
                [entity for entity in frame_truth if entity.get("kind") == kind],
                [row for row in frame_predictions if _prediction_kind(row) == kind],
                threshold,
            )
            matches.extend(kind_matches)
            for truth_entity, prediction in kind_matches:
                track_associations.setdefault(frame_id, {})[str(truth_entity["trackId"])] = int(prediction["Track_ID"])
    true_positives = len(matches)
    known_team_matches = [(truth, prediction) for truth, prediction in matches if truth.get("team") != "unknown"]
    team_correct = sum(_prediction_team(prediction, mapping) == truth["team"] for truth, prediction in known_team_matches)
    role_correct = sum(_prediction_kind(prediction) == truth["kind"] for truth, prediction in matches)
    return {
        "counts": {
            "truth": truth_count,
            "predictions": prediction_count,
            "truePositives": true_positives,
            "falsePositives": prediction_count - true_positives,
            "falseNegatives": truth_count - true_positives,
        },
        "precision": true_positives / prediction_count if prediction_count else None,
        "precision95": wilson_interval(true_positives, prediction_count, level=level),
        "recall": true_positives / truth_count if truth_count else None,
        "recall95": wilson_interval(true_positives, truth_count, level=level),
        "teamAgreement": {
            "correct": team_correct,
            "total": len(known_team_matches),
            "value": team_correct / len(known_team_matches) if known_team_matches else None,
            "unknownTruthMatches": true_positives - len(known_team_matches),
            "unknownPredictionMatches": sum(_prediction_team(prediction, mapping) == "unknown" for _, prediction in matches),
        },
        "roleAgreement": {
            "correct": role_correct,
            "total": true_positives,
            "value": role_correct / true_positives if true_positives else None,
        },
        "trackAssociations": track_associations,
    }


def _possession_transitions(
    frames: Sequence[Mapping[str, object]], fps: float, team_mapping: Mapping[str, str]
) -> list[tuple[str, str, float]]:
    previous: str | None = None
    transitions: list[tuple[str, str, float]] = []
    for frame in sorted(frames, key=lambda item: int(item["frameId"])):
        possession = frame.get("possession")
        if not isinstance(possession, Mapping):
            continue
        team = _prediction_team(possession, team_mapping)
        if team not in {"home", "away"}:
            continue
        if previous is not None and team != previous:
            transitions.append((previous, team, int(frame["frameId"]) / fps))
        previous = team
    return transitions


def _transition_errors(
    truth: Sequence[tuple[str, str, float]], predictions: Sequence[tuple[str, str, float]]
) -> list[float]:
    errors: list[tuple[float, float]] = []
    for direction in (("home", "away"), ("away", "home")):
        truth_times = [timestamp for source, target, timestamp in truth if (source, target) == direction]
        prediction_times = [timestamp for source, target, timestamp in predictions if (source, target) == direction]
        if not truth_times or not prediction_times:
            continue
        costs = np.abs(np.subtract.outer(truth_times, prediction_times))
        truth_indices, prediction_indices = linear_sum_assignment(costs)
        errors.extend((truth_times[truth_index], prediction_times[prediction_index] - truth_times[truth_index]) for truth_index, prediction_index in zip(truth_indices, prediction_indices))
    return [error for _, error in sorted(errors)]


def evaluate_possession(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_frames: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
    *,
    track_associations: Mapping[int, Mapping[str, int]],
    team_mapping: Mapping[str, str] | None = None,
) -> dict[str, object]:
    frames = labels.get("frames")
    confidence_protocol = protocol.get("confidenceIntervals")
    if not isinstance(frames, list) or not isinstance(confidence_protocol, Mapping):
        raise ValueError("labels frames and confidence protocol must be present")
    selected = evaluation_frame_ids(task, protocol)
    labels_by_frame = {int(frame["frameId"]): frame for frame in frames if isinstance(frame, Mapping)}
    predictions_by_frame = {int(frame["frameId"]): frame for frame in prediction_frames}
    mapping = team_mapping or {}
    counts = {
        "evaluationFrames": len(selected),
        "scoredTeamFrames": 0,
        "unknownTruthFrames": 0,
        "correctTeamFrames": 0,
        "scoredEntityFrames": 0,
        "correctEntityFrames": 0,
    }
    for frame_id in selected:
        truth_frame = labels_by_frame.get(frame_id)
        if not isinstance(truth_frame, Mapping) or not isinstance(truth_frame.get("possession"), Mapping):
            raise ValueError(f"label frame {frame_id} is missing possession truth")
        truth = truth_frame["possession"]
        if truth.get("team") == "unknown":
            counts["unknownTruthFrames"] += 1
            continue
        counts["scoredTeamFrames"] += 1
        prediction_frame = predictions_by_frame.get(frame_id, {})
        prediction = prediction_frame.get("possession", {}) if isinstance(prediction_frame, Mapping) else {}
        if not isinstance(prediction, Mapping):
            prediction = {}
        counts["correctTeamFrames"] += _prediction_team(prediction, mapping) == truth["team"]
        truth_track = truth.get("trackId")
        if truth_track is not None:
            counts["scoredEntityFrames"] += 1
            expected_track = track_associations.get(frame_id, {}).get(str(truth_track))
            counts["correctEntityFrames"] += expected_track is not None and prediction.get("trackId") == expected_track
    level = float(confidence_protocol["level"])
    fps = float(task["sourceFps"])
    truth_transitions = _possession_transitions(
        [frame for frame in frames if isinstance(frame, Mapping)], fps, {}
    )
    prediction_transitions = _possession_transitions(
        [
            frame
            for frame in prediction_frames
            if int(task["sourceStartFrame"]) <= int(frame["frameId"]) < int(task["sourceEndFrameExclusive"])
        ],
        fps,
        mapping,
    )
    transition_errors = _transition_errors(truth_transitions, prediction_transitions)
    absolute_errors = [abs(error) for error in transition_errors]
    samples = int(confidence_protocol["bootstrapSamples"])
    method = str(confidence_protocol["percentileMethod"])
    version = int(protocol["version"])
    source_id = str(task.get("sourceId", task.get("taskId", "unknown")))
    transition_bootstrap = lambda values, statistic, name: _bootstrap_interval(
        values,
        statistic,
        protocol_version=version,
        source_id=source_id,
        metric_name=name,
        samples=samples,
        level=level,
        percentile_method=method,
    )
    return {
        "counts": counts,
        "teamAgreement": counts["correctTeamFrames"] / counts["scoredTeamFrames"] if counts["scoredTeamFrames"] else None,
        "teamAgreement95": wilson_interval(counts["correctTeamFrames"], counts["scoredTeamFrames"], level=level),
        "entityAgreement": counts["correctEntityFrames"] / counts["scoredEntityFrames"] if counts["scoredEntityFrames"] else None,
        "entityAgreement95": wilson_interval(counts["correctEntityFrames"], counts["scoredEntityFrames"], level=level),
        "transitions": {
            "counts": {
                "truth": len(truth_transitions),
                "predictions": len(prediction_transitions),
                "matched": len(transition_errors),
            },
            "signedErrorsSeconds": transition_errors,
            "meanSignedErrorSeconds": float(np.mean(transition_errors)) if transition_errors else None,
            "meanSignedErrorSeconds95": transition_bootstrap(transition_errors, np.mean, "possessionTransitionMeanSignedSeconds"),
            "medianAbsoluteErrorSeconds": float(np.median(absolute_errors)) if absolute_errors else None,
            "medianAbsoluteErrorSeconds95": transition_bootstrap(absolute_errors, np.median, "possessionTransitionMedianAbsoluteSeconds"),
            "p95AbsoluteErrorSeconds": float(np.quantile(absolute_errors, 0.95, method=method)) if absolute_errors else None,
            "p95AbsoluteErrorSeconds95": transition_bootstrap(
                absolute_errors,
                lambda sample: np.quantile(sample, 0.95, method=method),
                "possessionTransitionP95AbsoluteSeconds",
            ),
        },
    }


def _bootstrap_interval(
    values: Sequence[float],
    statistic,
    *,
    protocol_version: int,
    source_id: str,
    metric_name: str,
    samples: int,
    level: float,
    percentile_method: str,
) -> tuple[float, float] | None:
    if not values:
        return None
    seed_material = f"{protocol_version}\n{source_id}\n{metric_name}".encode()
    seed = int(hashlib.sha256(seed_material).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    source = np.asarray(values, dtype=float)
    estimates = np.asarray([statistic(rng.choice(source, len(source), replace=True)) for _ in range(samples)])
    tail = (1.0 - level) / 2.0
    low, high = np.quantile(estimates, [tail, 1.0 - tail], method=percentile_method)
    return float(low), float(high)


def evaluate_pitch(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
    *,
    track_associations: Mapping[int, Mapping[str, int]],
) -> dict[str, object]:
    frames = labels.get("frames")
    confidence_protocol = protocol.get("confidenceIntervals")
    if not isinstance(frames, list) or not isinstance(confidence_protocol, Mapping):
        raise ValueError("labels frames and confidence protocol must be present")
    selected = set(evaluation_frame_ids(task, protocol))
    predictions: dict[tuple[int, int], Mapping[str, object]] = {}
    for row in prediction_rows:
        if _prediction_kind(row) is None or int(row["Frame_ID"]) not in selected:
            continue
        key = int(row["Frame_ID"]), int(row["Track_ID"])
        if key in predictions:
            raise ValueError(f"duplicate predicted track {key[1]} on frame {key[0]}")
        predictions[key] = row
    reference_positions = 0
    errors: list[float] = []
    for frame in frames:
        if not isinstance(frame, Mapping) or int(frame["frameId"]) not in selected:
            continue
        frame_id = int(frame["frameId"])
        entities = frame.get("entities")
        if not isinstance(entities, list):
            raise ValueError(f"label frame {frame_id} is missing entity truth")
        for entity in entities:
            position = entity.get("pitchPositionMeters")
            if position is None:
                continue
            reference_positions += 1
            predicted_track = track_associations.get(frame_id, {}).get(str(entity["trackId"]))
            prediction = predictions.get((frame_id, predicted_track)) if predicted_track is not None else None
            if prediction is None:
                continue
            predicted_x, predicted_y = float(prediction["X"]), float(prediction["Y"])
            if not math.isfinite(predicted_x) or not math.isfinite(predicted_y):
                raise ValueError("predicted pitch position must be finite")
            errors.append(math.hypot(predicted_x - float(position[0]), predicted_y - float(position[1])))
    level = float(confidence_protocol["level"])
    samples = int(confidence_protocol["bootstrapSamples"])
    method = str(confidence_protocol["percentileMethod"])
    source_id = str(task["sourceId"])
    version = int(protocol["version"])
    median_error = float(np.median(errors)) if errors else None
    p95_error = float(np.quantile(errors, 0.95, method=method)) if errors else None
    maximum_error = max(errors) if errors else None
    bootstrap = lambda statistic, name: _bootstrap_interval(
        errors,
        statistic,
        protocol_version=version,
        source_id=source_id,
        metric_name=name,
        samples=samples,
        level=level,
        percentile_method=method,
    )
    return {
        "eligibleForAcceptance": labels.get("pitchReference") is not None and bool(errors),
        "errorsMeters": errors,
        "referencePositionCount": reference_positions,
        "matchedPositionCount": len(errors),
        "referenceCoverage": len(errors) / reference_positions if reference_positions else None,
        "medianErrorMeters": median_error,
        "medianErrorMeters95": bootstrap(np.median, "pitchMedianErrorMeters"),
        "p95ErrorMeters": p95_error,
        "p95ErrorMeters95": bootstrap(lambda sample: np.quantile(sample, 0.95, method=method), "pitchP95ErrorMeters"),
        "maximumErrorMeters": maximum_error,
        "maximumErrorMeters95": bootstrap(np.max, "pitchMaximumErrorMeters"),
    }


def _distance_to_truth_window(truth: Mapping[str, object], timestamp: float, fps: float) -> float:
    start = int(truth["startFrame"]) / fps
    end = int(truth["endFrameExclusive"]) / fps
    return max(start - timestamp, timestamp - end, 0.0)


def _event_matches(truth: Mapping[str, object], prediction: Mapping[str, object], fps: float, tolerance: float) -> bool:
    truth_team = truth.get("team")
    return (
        truth_team in {"unknown", prediction.get("team")}
        and _distance_to_truth_window(truth, float(prediction["timestamp"]), fps) <= tolerance
    )


def _match_events(
    truth: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    *,
    fps: float,
    tolerance: float,
) -> int:
    if not truth or not predictions:
        return 0
    maximum_distance = tolerance + 1.0
    unmatched_cost = maximum_distance * (min(len(truth), len(predictions)) + 1)
    costs = np.full((len(truth), len(predictions) + len(truth)), unmatched_cost, dtype=float)
    for truth_index, truth_event in enumerate(truth):
        for prediction_index, prediction in enumerate(predictions):
            if _event_matches(truth_event, prediction, fps, tolerance):
                costs[truth_index, prediction_index] = _distance_to_truth_window(
                    truth_event, float(prediction["timestamp"]), fps
                )
    truth_indices, prediction_indices = linear_sum_assignment(costs)
    return sum(prediction_index < len(predictions) and costs[truth_index, prediction_index] < unmatched_cost for truth_index, prediction_index in zip(truth_indices, prediction_indices))


def evaluate_events(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    predictions: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
) -> dict[str, object]:
    truth_events = labels.get("events")
    event_protocol = protocol.get("events")
    confidence_protocol = protocol.get("confidenceIntervals")
    if not isinstance(truth_events, list) or not isinstance(event_protocol, Mapping) or not isinstance(confidence_protocol, Mapping):
        raise ValueError("labels events and event protocol must be present")
    fps = float(task["sourceFps"])
    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    tolerance = float(event_protocol["toleranceSeconds"])
    level = float(confidence_protocol["level"])
    in_task_predictions = [prediction for prediction in predictions if start <= int(prediction["frameId"]) < end]
    classes: dict[str, object] = {}
    for event_class in event_protocol["classes"]:
        class_truth = sorted(
            (event for event in truth_events if event.get("type") == event_class),
            key=lambda event: (int(event["startFrame"]), str(event["eventId"])),
        )
        class_predictions = sorted(
            (event for event in in_task_predictions if event.get("type") == event_class),
            key=lambda event: float(event["timestamp"]),
        )
        true_positives = _match_events(class_truth, class_predictions, fps=fps, tolerance=tolerance)
        prediction_count = len(class_predictions)
        truth_count = len(class_truth)
        counts = {
            "truth": truth_count,
            "predictions": prediction_count,
            "truePositives": true_positives,
            "falsePositives": prediction_count - true_positives,
            "falseNegatives": truth_count - true_positives,
        }
        classes[str(event_class)] = {
            "counts": counts,
            "precision": true_positives / prediction_count if prediction_count else None,
            "precision95": wilson_interval(true_positives, prediction_count, level=level),
            "recall": true_positives / truth_count if truth_count else None,
            "recall95": wilson_interval(true_positives, truth_count, level=level),
            "applicable": bool(truth_count or prediction_count),
        }
    return {"classes": classes}


def evaluate_source_acceptance(
    source_id: str,
    task_results: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
    *,
    expected_task_ids: Sequence[str],
    team_mapping: Mapping[str, str],
) -> dict[str, object]:
    """Pool frozen acceptance metrics while keeping task frame identities separate."""

    task_results = sorted(task_results, key=lambda result: str(result.get("taskId", "")))
    if not task_results or any(result.get("sourceId") != source_id for result in task_results):
        raise ValueError("task results must be non-empty and belong to one source")
    task_ids = [str(result.get("taskId", "")) for result in task_results]
    if sorted(task_ids) != sorted(expected_task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("task results must contain exactly the frozen tasks for the source")
    expected_mapping = dict(team_mapping)
    if (
        set(expected_mapping) != {"my_team", "enemy"}
        or set(expected_mapping.values()) != {"home", "away"}
        or any(result.get("teamMapping") != expected_mapping for result in task_results)
    ):
        raise ValueError("task results must use the declared source team mapping")
    confidence = protocol.get("confidenceIntervals")
    bars = protocol.get("acceptance")
    event_protocol = protocol.get("events")
    if not isinstance(confidence, Mapping) or not isinstance(bars, Mapping) or not isinstance(event_protocol, Mapping):
        raise ValueError("protocol confidence, acceptance and events must be objects")
    level = float(confidence["level"])

    def count(values: Mapping[str, object], key: str, label: str) -> int:
        value = values.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"missing or invalid {label} counts")
        return value

    ball_counts = {key: 0 for key in ("evaluationFrames", "ignoredFrames", "visibleTruth", "notVisibleTruth", "predictions", "truePositives", "falsePositives", "falseNegatives")}
    source_counts = {key: 0 for key in ("observed", "inferred", "unknown")}
    pitch_errors: list[float] = []
    pitch_eligible = False
    pitch_reference_positions = pitch_matched_positions = 0
    task_metrics: list[dict[str, object]] = []
    event_counts = {
        str(event_type): {"truth": 0, "predictions": 0, "truePositives": 0}
        for event_type in event_protocol["classes"]
    }
    for result in task_results:
        metrics = {name: result.get(name) for name in ("players", "tracking", "possession")}
        if not all(isinstance(value, Mapping) for value in metrics.values()):
            raise ValueError("each task result must contain player, tracking and possession metrics")
        task_metrics.append({
            "taskId": result["taskId"],
            "predictionScope": result.get("predictionScope"),
            "predictionSourceStartFrame": result.get("predictionSourceStartFrame"),
            "predictionInputVideoSha256": result.get("predictionInputVideoSha256"),
            **metrics,
        })
        ball = result.get("ball")
        pitch = result.get("pitch")
        events = result.get("events")
        if not isinstance(ball, Mapping) or not isinstance(ball.get("counts"), Mapping):
            raise ValueError("each task result must contain ball counts")
        task_ball_counts = ball["counts"]
        ball_tp = count(task_ball_counts, "truePositives", "ball")
        ball_fp = count(task_ball_counts, "falsePositives", "ball")
        ball_fn = count(task_ball_counts, "falseNegatives", "ball")
        if count(task_ball_counts, "predictions", "ball") != ball_tp + ball_fp:
            raise ValueError("invalid ball counts")
        if count(task_ball_counts, "visibleTruth", "ball") != ball_tp + ball_fn:
            raise ValueError("invalid ball counts")
        if count(task_ball_counts, "evaluationFrames", "ball") != sum(
            count(task_ball_counts, key, "ball")
            for key in ("ignoredFrames", "visibleTruth", "notVisibleTruth")
        ):
            raise ValueError("invalid ball counts")
        for key in ball_counts:
            ball_counts[key] += count(task_ball_counts, key, "ball")
        breakdown = ball.get("predictionSourceBreakdown")
        if not isinstance(breakdown, Mapping) or set(breakdown) != set(source_counts):
            raise ValueError("missing or invalid ball prediction source counts")
        if sum(count(breakdown, key, "ball prediction source") for key in source_counts) != count(task_ball_counts, "predictions", "ball"):
            raise ValueError("invalid ball prediction source counts")
        for key in source_counts:
            source_counts[key] += count(breakdown, key, "ball prediction source")
        if not isinstance(pitch, Mapping) or not isinstance(pitch.get("errorsMeters"), list):
            raise ValueError("each task result must contain pitch errorsMeters")
        errors = [float(error) for error in pitch["errorsMeters"]]
        if any(not math.isfinite(error) or error < 0 for error in errors):
            raise ValueError("pitch errorsMeters must contain finite non-negative numbers")
        if type(pitch.get("eligibleForAcceptance")) is not bool:
            raise ValueError("pitch eligibility must be declared for every task")
        task_pitch_eligible = pitch["eligibleForAcceptance"]
        if task_pitch_eligible != bool(errors):
            raise ValueError("pitch eligibility must match the presence of independently referenced errors")
        task_reference_positions = count(pitch, "referencePositionCount", "pitch")
        task_matched_positions = count(pitch, "matchedPositionCount", "pitch")
        if task_matched_positions != len(errors) or task_matched_positions > task_reference_positions:
            raise ValueError("invalid pitch counts")
        pitch_errors.extend(errors)
        pitch_eligible |= task_pitch_eligible
        pitch_reference_positions += task_reference_positions
        pitch_matched_positions += task_matched_positions
        if not isinstance(events, Mapping) or not isinstance(events.get("classes"), Mapping):
            raise ValueError("each task result must contain event classes")
        for event_type, counts in event_counts.items():
            event = events["classes"].get(event_type)
            if not isinstance(event, Mapping) or not isinstance(event.get("counts"), Mapping):
                raise ValueError(f"each task result must contain {event_type} event counts")
            task_event_counts = event["counts"]
            truth = count(task_event_counts, "truth", f"{event_type} event")
            predictions = count(task_event_counts, "predictions", f"{event_type} event")
            true_positives = count(task_event_counts, "truePositives", f"{event_type} event")
            if true_positives > min(truth, predictions):
                raise ValueError(f"invalid {event_type} event counts")
            if (
                count(task_event_counts, "falsePositives", f"{event_type} event") != predictions - true_positives
                or count(task_event_counts, "falseNegatives", f"{event_type} event") != truth - true_positives
            ):
                raise ValueError(f"invalid {event_type} event counts")
            for key in counts:
                counts[key] += count(task_event_counts, key, f"{event_type} event")

    true_positives = ball_counts["truePositives"]
    precision_denominator = true_positives + ball_counts["falsePositives"]
    recall_denominator = true_positives + ball_counts["falseNegatives"]
    ball_precision = true_positives / precision_denominator if precision_denominator else None
    ball_recall = true_positives / recall_denominator if recall_denominator else None
    scored_frames = ball_counts["evaluationFrames"] - ball_counts["ignoredFrames"]
    target_fps = int(protocol["evaluationFrames"]["targetFps"])  # type: ignore[index]
    ball_result = {
        "counts": ball_counts,
        "precision": ball_precision,
        "precision95": wilson_interval(true_positives, precision_denominator, level=level),
        "recall": ball_recall,
        "recall95": wilson_interval(true_positives, recall_denominator, level=level),
        "falsePositivesPerMinute": ball_counts["falsePositives"] / (scored_frames / target_fps / 60) if scored_frames else None,
        "predictionSourceBreakdown": source_counts,
    }

    samples = int(confidence["bootstrapSamples"])
    method = str(confidence["percentileMethod"])
    pitch_median = float(np.median(pitch_errors)) if pitch_errors else None
    pitch_p95 = float(np.quantile(pitch_errors, 0.95, method=method)) if pitch_errors else None
    pitch_result = {
        "eligibleForAcceptance": pitch_eligible,
        "referencePositionCount": pitch_reference_positions,
        "matchedPositionCount": pitch_matched_positions,
        "referenceCoverage": pitch_matched_positions / pitch_reference_positions if pitch_reference_positions else None,
        "errorCount": len(pitch_errors),
        "medianErrorMeters": pitch_median,
        "medianErrorMeters95": _bootstrap_interval(pitch_errors, np.median, protocol_version=int(protocol["version"]), source_id=source_id, metric_name="pitchMedianErrorMeters", samples=samples, level=level, percentile_method=method),
        "p95ErrorMeters": pitch_p95,
        "p95ErrorMeters95": _bootstrap_interval(pitch_errors, lambda values: np.quantile(values, 0.95, method=method), protocol_version=int(protocol["version"]), source_id=source_id, metric_name="pitchP95ErrorMeters", samples=samples, level=level, percentile_method=method),
    }

    event_results: dict[str, object] = {}
    checks: dict[str, dict[str, object]] = {
        "ballPrecision": {"value": ball_precision, "threshold": bars["ballPrecisionMinimum"], "passed": ball_precision is not None and ball_precision >= float(bars["ballPrecisionMinimum"])},
        "visibleBallRecall": {"value": ball_recall, "threshold": bars["visibleBallRecallMinimum"], "passed": ball_recall is not None and ball_recall >= float(bars["visibleBallRecallMinimum"])},
        "pitchEligible": {"value": pitch_eligible, "threshold": True, "passed": pitch_eligible},
        "pitchMedianErrorMeters": {"value": pitch_median, "threshold": bars["pitchMedianErrorMetersMaximum"], "passed": pitch_median is not None and pitch_median <= float(bars["pitchMedianErrorMetersMaximum"])},
        "pitchP95ErrorMeters": {"value": pitch_p95, "threshold": bars["pitchP95ErrorMetersMaximum"], "passed": pitch_p95 is not None and pitch_p95 <= float(bars["pitchP95ErrorMetersMaximum"])},
    }
    for event_type, counts in event_counts.items():
        precision = counts["truePositives"] / counts["predictions"] if counts["predictions"] else None
        recall = counts["truePositives"] / counts["truth"] if counts["truth"] else None
        applicable = bool(counts["truth"] or counts["predictions"])
        event_results[event_type] = {
            "counts": {**counts, "falsePositives": counts["predictions"] - counts["truePositives"], "falseNegatives": counts["truth"] - counts["truePositives"]},
            "precision": precision,
            "precision95": wilson_interval(counts["truePositives"], counts["predictions"], level=level),
            "recall": recall,
            "recall95": wilson_interval(counts["truePositives"], counts["truth"], level=level),
            "applicable": applicable,
        }
        checks[f"{event_type}Precision"] = {"value": precision, "threshold": bars["supportedEventPrecisionMinimum"], "passed": not applicable or precision is not None and precision >= float(bars["supportedEventPrecisionMinimum"])}
        checks[f"{event_type}Recall"] = {"value": recall, "threshold": bars["supportedEventRecallMinimum"], "passed": not applicable or recall is not None and recall >= float(bars["supportedEventRecallMinimum"])}
    return {
        "schemaVersion": "football_analysis_pilot_source_acceptance_v1",
        "sourceId": source_id,
        "taskIds": task_ids,
        "teamMapping": expected_mapping,
        "taskMetrics": task_metrics,
        "ball": ball_result,
        "pitch": pitch_result,
        "events": {"classes": event_results},
        "acceptance": {"checks": checks, "passed": all(bool(check["passed"]) for check in checks.values())},
    }


def _scoring_protocol(corpus_path: Path) -> Mapping[str, object]:
    corpus = _read_json(corpus_path)
    if not isinstance(corpus, dict):
        raise ValueError("corpus must contain an object")
    labeling_protocol = corpus.get("labelingProtocol")
    if not isinstance(labeling_protocol, dict) or not isinstance(labeling_protocol.get("scoringProtocol"), dict):
        raise ValueError("corpus must contain labelingProtocol.scoringProtocol")
    protocol = dict(labeling_protocol["scoringProtocol"])
    acceptance = protocol.get("acceptance")
    bars = labeling_protocol.get("acceptanceBars")
    if not isinstance(acceptance, dict) or bars is not None and not isinstance(bars, dict):
        raise ValueError("corpus must contain valid acceptance configuration")
    protocol["acceptance"] = {**acceptance, **(bars or {})}
    return protocol


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score frozen football-analysis pilot artifacts")
    commands = parser.add_subparsers(dest="command", required=True)
    task_parser = commands.add_parser("task", help="score one task from native match artifacts")
    task_parser.add_argument("--task-id", required=True)
    task_parser.add_argument("--artifact-dir", required=True, type=Path)
    task_parser.add_argument("--prediction-scope", required=True, choices=("whole-source", "task-interval"))
    task_parser.add_argument("--prediction-source-start-frame", type=int)
    task_parser.add_argument("--expected-input-video-sha256")
    task_parser.add_argument("--trackeval-root", required=True, type=Path)
    task_parser.add_argument("--source-declaration", required=True, type=Path)
    task_parser.add_argument(
        "--task-manifest",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"),
    )
    for command_parser in (task_parser, commands.add_parser("source", help="pool saved task results by source")):
        command_parser.add_argument(
            "--corpus",
            type=Path,
            default=Path("backend/benchmark_suites/football_analysis_pilot_corpus.json"),
        )
    source_parser = commands.choices["source"]
    source_parser.add_argument("--source-id", required=True)
    source_parser.add_argument("--task-result", required=True, action="append", type=Path)
    source_parser.add_argument("--source-declaration", required=True, type=Path)
    source_parser.add_argument(
        "--task-manifest",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"),
    )
    args = parser.parse_args(argv)
    protocol = _scoring_protocol(args.corpus)

    if args.command == "source":
        my_team, declaration_sha256 = _source_declaration(args.source_declaration, args.source_id)
        task_results = [parse_unique_json(path.read_bytes()) for path in args.task_result]
        if not all(isinstance(result, dict) for result in task_results):
            raise ValueError("every task result must contain an object")
        if any(result.get("teamDeclarationSha256") != declaration_sha256 for result in task_results):
            raise ValueError("task results must match the source declaration SHA-256")
        task_manifest = _read_json(args.task_manifest)
        if not isinstance(task_manifest, dict) or not isinstance(task_manifest.get("tasks"), list):
            raise ValueError("task manifest must contain tasks")
        expected_tasks = [
            task for task in task_manifest["tasks"]
            if isinstance(task, dict) and task.get("sourceId") == args.source_id
        ]
        expected_task_ids = [str(task["taskId"]) for task in expected_tasks]
        for task in expected_tasks:
            if task.get("evaluationRole") != "held_out_test":
                continue
            expected_sha256 = _declared_input_video_sha256(task, args.task_manifest, _PILOT_MEDIA_ROOT)
            matches = [result for result in task_results if result.get("taskId") == task["taskId"]]
            if len(matches) != 1 or matches[0].get("predictionInputVideoSha256") != expected_sha256:
                raise ValueError("held-out input-video hash must match the frozen clip")
            start = int(task["sourceStartFrame"])
            step = int(task["evaluationFrameStep"])
            if (
                matches[0].get("predictionScope") != "task-interval"
                or matches[0].get("predictionSourceStartFrame") != start - start % step
            ):
                raise ValueError("held-out task result must retain the aligned prediction scope")
        opponent = "away" if my_team == "home" else "home"
        result = evaluate_source_acceptance(
            args.source_id,
            task_results,
            protocol,
            expected_task_ids=expected_task_ids,
            team_mapping={"my_team": my_team, "enemy": opponent},
        )
        result["teamDeclarationSha256"] = declaration_sha256
        print(
            json.dumps(
                result,
                indent=2,
                sort_keys=True,
            )
        )
        return

    task_manifest = _read_json(args.task_manifest)
    if not isinstance(task_manifest, dict) or not isinstance(task_manifest.get("tasks"), list):
        raise ValueError("task manifest must contain tasks")
    matches = [task for task in task_manifest["tasks"] if isinstance(task, dict) and task.get("taskId") == args.task_id]
    if len(matches) != 1:
        raise ValueError(f"task-id must identify exactly one frozen task: {args.task_id}")
    task = matches[0]
    my_team, declaration_sha256 = _source_declaration(args.source_declaration, str(task["sourceId"]))
    if task.get("evaluationRole") == "held_out_test":
        declared_sha256 = _declared_input_video_sha256(task, args.task_manifest, _PILOT_MEDIA_ROOT)
        if args.expected_input_video_sha256 != declared_sha256:
            raise ValueError("expected input-video hash must match the declared clip SHA-256")
    labels = parse_unique_json(Path(str(task["labelOutputPath"])).read_bytes())
    if not isinstance(labels, dict):
        raise ValueError("label file must contain an object")
    from backend.scripts.validate_football_analysis_pilot_labels import validate_label_payload

    validate_label_payload(task, labels)
    opponent = "away" if my_team == "home" else "home"
    result = evaluate_task_artifacts(
        task,
        labels,
        protocol,
        artifact_dir=args.artifact_dir,
        prediction_scope=args.prediction_scope,
        prediction_source_start_frame=args.prediction_source_start_frame,
        expected_input_video_sha256=args.expected_input_video_sha256,
        trackeval_root=args.trackeval_root,
        team_mapping={"my_team": my_team, "enemy": opponent},
    )
    result["teamDeclarationSha256"] = declaration_sha256
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
