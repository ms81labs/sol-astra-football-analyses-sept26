from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any


FRAME_CSV_FIELDS = [
    "frameId",
    "timestamp",
    "ballX",
    "ballY",
    "ballConfidence",
    "possessionTeam",
    "possessionTrackId",
    "possessionDistance",
]

EVENT_CSV_FIELDS = [
    "type",
    "frameId",
    "timestamp",
    "team",
    "fromTrackId",
    "toTrackId",
    "description",
    "reviewStatus",
    "heuristicName",
]

METRIC_CSV_FIELDS = [
    "metric",
    "definitionVersion",
    "value",
    "availability",
    "reasonCodes",
    "publishedLabel",
    "teamScope",
    "deprecated",
    "unit",
    "eligibleSeconds",
    "requestedSeconds",
]


def _as_mapping(item: Any) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    raise TypeError(f"Unsupported export item: {type(item)!r}")


def flatten_frames_for_csv(frames: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in frames:
        payload = _as_mapping(frame)
        ball = payload.get("ball") or {}
        possession = payload.get("possession") or {}
        rows.append(
            {
                "frameId": payload.get("frameId"),
                "timestamp": payload.get("timestamp"),
                "ballX": ball.get("x"),
                "ballY": ball.get("y"),
                "ballConfidence": ball.get("confidence"),
                "possessionTeam": possession.get("team"),
                "possessionTrackId": possession.get("trackId"),
                "possessionDistance": possession.get("distance"),
            }
        )
    return rows


def flatten_events_for_csv(events: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        payload = _as_mapping(event)
        rows.append(
            {
                "type": payload.get("type"),
                "frameId": payload.get("frameId"),
                "timestamp": payload.get("timestamp"),
                "team": payload.get("team"),
                "fromTrackId": payload.get("fromTrackId"),
                "toTrackId": payload.get("toTrackId"),
                "description": payload.get("description"),
                "reviewStatus": payload.get("reviewStatus") or "unreviewed",
                "heuristicName": payload.get("heuristicName") or "provisional_event_suggestion",
            }
        )
    return rows


def flatten_metrics_for_csv(records: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        payload = _as_mapping(record)
        reason_codes = payload.get("reasonCodes") or []
        if isinstance(reason_codes, list):
            reason_codes = ",".join(str(code) for code in reason_codes)
        rows.append(
            {
                "metric": payload.get("metric"),
                "definitionVersion": payload.get("definitionVersion"),
                "value": payload.get("value"),
                "availability": payload.get("availability"),
                "reasonCodes": reason_codes,
                "publishedLabel": payload.get("publishedLabel"),
                "teamScope": payload.get("teamScope"),
                "deprecated": payload.get("deprecated") or False,
                "unit": payload.get("unit"),
                "eligibleSeconds": payload.get("eligibleSeconds"),
                "requestedSeconds": payload.get("requestedSeconds"),
            }
        )
    return rows


def render_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
