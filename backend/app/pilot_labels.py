"""Shared runtime pilot evaluation; research command entry points remain separate."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
import re
from typing import Mapping

SCHEMA_VERSION = "football_analysis_pilot_labels_v3"


TEAMS = {"home", "away", "unknown"}


_RFC3339_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")


def parse_unique_json(raw: bytes | str) -> object:
    """Reject ambiguous keys in human-truth JSON before validation."""

    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique_keys)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")


def _bbox(value: object, *, width: int, height: int, name: str) -> None:
    if not isinstance(value, list) or len(value) != 4 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
        for item in value
    ):
        raise ValueError(f"{name} bbox must contain four finite numbers")
    x1, y1, x2, y2 = value
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"{name} bbox must be inside {width}x{height}")


def _pitch_position(value: object, name: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, list) or len(value) != 2 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
        for item in value
    ):
        raise ValueError(f"{name} pitchPositionMeters must contain two finite numbers or null")
    return True


def parse_utc_timestamp(value: object, field: str) -> datetime:
    if type(value) is not str or _RFC3339_UTC.fullmatch(value) is None:
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp")
    try:
        timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp") from exc
    if timestamp > datetime.now(timezone.utc):
        raise ValueError(f"{field} cannot be in the future")
    return timestamp


def validate_label_payload(task: Mapping[str, object], payload: Mapping[str, object]) -> dict[str, int | float]:
    """Return acceptance denominators only when one task is complete and safe."""

    _exact_keys(
        payload,
        {
            "schemaVersion",
            "taskId",
            "sourceVideoSha256",
            "independentAnnotation",
            "pipelineOutputUsed",
            "annotatorId",
            "lockedAt",
            "pitchReference",
            "frames",
            "events",
        },
        "label payload",
    )
    if payload["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {SCHEMA_VERSION}")
    for field, task_field in (("taskId", "taskId"), ("sourceVideoSha256", "videoSha256")):
        if payload[field] != task[task_field]:
            raise ValueError(f"{field} does not match the frozen task")
    if payload["independentAnnotation"] is not True:
        raise ValueError("independentAnnotation must be true")
    if payload["pipelineOutputUsed"] is not False:
        raise ValueError("pipelineOutputUsed must be false")
    if not isinstance(payload["annotatorId"], str) or not payload["annotatorId"].strip():
        raise ValueError("annotatorId must be a non-empty string")
    parse_utc_timestamp(payload["lockedAt"], "lockedAt")
    pitch_reference = payload["pitchReference"]
    if pitch_reference is not None:
        pitch_reference = _mapping(pitch_reference, "pitchReference")
        _exact_keys(pitch_reference, {"sourceId", "sha256", "associationMethod"}, "pitchReference")
        if not isinstance(pitch_reference["sourceId"], str) or not pitch_reference["sourceId"].strip():
            raise ValueError("pitchReference sourceId must be a non-empty string")
        digest = pitch_reference["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("pitchReference sha256 must be lower-case hexadecimal")
        if pitch_reference["associationMethod"] not in {"predeclared_identity", "withheld_control_keypoint"}:
            raise ValueError("pitchReference associationMethod is invalid")

    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    step = task.get("evaluationFrameStep")
    declared_frame_count = task.get("evaluationFrameCount")
    if type(step) is not int or step <= 0 or type(declared_frame_count) is not int or declared_frame_count <= 0:
        raise ValueError("task must declare a positive evaluation frame step and count")
    expected_frame_ids = [frame_id for frame_id in range(start, end) if frame_id % step == 0]
    if len(expected_frame_ids) != declared_frame_count:
        raise ValueError("task evaluation frame count does not match its interval and step")
    width = int(task["sourceWidth"])
    height = int(task["sourceHeight"])
    frames = payload["frames"]
    if not isinstance(frames, list) or [frame.get("frameId") if isinstance(frame, Mapping) else None for frame in frames] != expected_frame_ids:
        raise ValueError("frames must contain exactly the declared evaluation frames in order")

    pitch_position_count = 0
    for frame in frames:
        frame = _mapping(frame, "frame")
        _exact_keys(frame, {"frameId", "ball", "entities", "possession"}, "frame")
        ball = _mapping(frame["ball"], "ball")
        _exact_keys(ball, {"visibility", "bbox", "pitchPositionMeters"}, "ball")
        pitch_position_count += _pitch_position(ball["pitchPositionMeters"], "ball")
        visibility = ball["visibility"]
        if visibility not in {"visible", "occluded", "not_visible", "unknown"}:
            raise ValueError("ball visibility is invalid")
        if visibility == "visible":
            if ball["bbox"] is None:
                raise ValueError("visible ball requires bbox")
            _bbox(ball["bbox"], width=width, height=height, name="ball")
        elif ball["bbox"] is not None:
            raise ValueError("non-visible ball must not have bbox")

        entities = frame["entities"]
        if not isinstance(entities, list):
            raise ValueError("entities must be an array")
        track_ids: set[str] = set()
        for raw_entity in entities:
            entity = _mapping(raw_entity, "entity")
            _exact_keys(entity, {"trackId", "kind", "team", "bbox", "pitchPositionMeters"}, "entity")
            pitch_position_count += _pitch_position(entity["pitchPositionMeters"], "entity")
            track_id = entity["trackId"]
            if not isinstance(track_id, str) or not track_id or track_id in track_ids:
                raise ValueError("entity trackId must be a unique non-empty string per frame")
            track_ids.add(track_id)
            if entity["kind"] not in {"player", "referee"} or entity["team"] not in TEAMS:
                raise ValueError("entity kind or team is invalid")
            _bbox(entity["bbox"], width=width, height=height, name="entity")

        possession = _mapping(frame["possession"], "possession")
        _exact_keys(possession, {"state", "team", "trackId"}, "possession")
        if possession["state"] not in {"observed", "inferred", "unknown"} or possession["team"] not in TEAMS:
            raise ValueError("possession state or team is invalid")
        possession_track = possession["trackId"]
        if possession["state"] == "unknown":
            if possession_track is not None or possession["team"] != "unknown":
                raise ValueError("unknown possession must have unknown team and null trackId")
        elif possession_track is not None and possession_track not in track_ids:
            raise ValueError("possession trackId must identify an entity in the same frame")

    if pitch_position_count and pitch_reference is None:
        raise ValueError("pitchReference is required when pitch positions are present")

    events = payload["events"]
    if not isinstance(events, list):
        raise ValueError("events must be an array")
    event_ids: set[str] = set()
    for raw_event in events:
        event = _mapping(raw_event, "event")
        _exact_keys(event, {"eventId", "type", "startFrame", "endFrameExclusive", "team"}, "event")
        event_id = event["eventId"]
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            raise ValueError("eventId must be a unique non-empty string")
        event_ids.add(event_id)
        if event["type"] not in {"pass", "shot"} or event["team"] not in TEAMS:
            raise ValueError("event type or team is invalid")
        event_start, event_end = event["startFrame"], event["endFrameExclusive"]
        if type(event_start) is not int or type(event_end) is not int or not (start <= event_start < event_end <= end):
            raise ValueError("event frame range must be inside the frozen task")

    return {
        "frameCount": len(frames),
        "eventCount": len(events),
        "pitchPositionCount": pitch_position_count,
        "durationSeconds": (end - start) / float(task["sourceFps"]),
    }
