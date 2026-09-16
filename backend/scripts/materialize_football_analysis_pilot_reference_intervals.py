from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


PLAYING_PERIODS = {"FIRST_HALF", "SECOND_HALF"}


def reference_clock_offsets(
    tasks: list[dict[str, object]], video_paths: list[str], metadata_xml: Path
) -> dict[str, float]:
    """Map frozen concatenated-video task times onto official tracker match time."""
    if len(video_paths) != 2 or video_paths[0] == video_paths[1]:
        raise ValueError("exactly two ordered half videos are required")
    periods = ET.parse(metadata_xml).getroot().findall(".//period")
    anchors = [float(period.get("matchTimeStart", "nan")) / 1000 for period in periods
               if period.get("period") == "SECOND_HALF"]
    if len(anchors) != 1 or not math.isfinite(anchors[0]):
        raise ValueError("one finite SECOND_HALF matchTimeStart is required")
    offsets: dict[str, float] = {}
    for task in tasks:
        video_path = str(task["videoPath"])
        if video_path not in video_paths:
            raise ValueError(f"unknown task video path: {video_path}")
        segment_start = float(task["globalStartSeconds"]) - float(task["localStartSeconds"])
        if not math.isfinite(segment_start):
            raise ValueError("task video segment start must be finite")
        task_id = str(task["taskId"])
        if task_id in offsets:
            raise ValueError(f"duplicate task ID: {task_id}")
        offsets[task_id] = 0.0 if video_path == video_paths[0] else anchors[0] - segment_start
    return offsets


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_intervals(intervals: list[list[float]]) -> list[tuple[float, float]]:
    if not intervals:
        raise ValueError("interval list must not be empty")
    result: list[tuple[float, float]] = []
    for interval in intervals:
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("each interval must contain start and end seconds")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in interval):
            raise ValueError("interval values must be finite numbers")
        start, end = map(float, interval)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise ValueError("interval bounds must be finite, non-negative, and increasing")
        if result and start < result[-1][1]:
            raise ValueError("intervals must be sorted and non-overlapping")
        result.append((start, end))
    return result


def _player_metadata(path: Path) -> dict[str, dict[str, object]]:
    players: dict[str, dict[str, object]] = {}
    for player in ET.parse(path).getroot().findall(".//player"):
        player_id = player.get("id")
        if not player_id:
            continue
        jersey = player.get("shirtNumber")
        players[player_id] = {
            "teamId": player.get("teamId"),
            "jerseyNumber": int(jersey) if jersey and jersey.isdigit() else None,
            "role": player.get("position"),
            "name": player.get("nameEn") or player.get("name"),
        }
    return players


def _location(value: str | None) -> dict[str, float] | None:
    try:
        parts = [] if value is None else value.strip("[]").split(",")
        if len(parts) != 2:
            return None
        x, y = map(float, parts)
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return {"x": x, "y": y}
    except ValueError:
        return None


def materialize_reference_intervals(
    source_id: str,
    tracker_xml: Path,
    metadata_xml: Path,
    intervals: list[list[float]],
    output_path: Path,
    *,
    reference_clock_offsets_seconds: list[float] | None = None,
) -> dict[str, object]:
    selected = _validated_intervals(intervals)
    offsets = [0.0] * len(selected) if reference_clock_offsets_seconds is None else reference_clock_offsets_seconds
    if len(offsets) != len(selected) or any(not math.isfinite(float(offset)) for offset in offsets):
        raise ValueError("one finite reference clock offset is required per interval")
    reference_intervals = [(round(start + float(offset), 3), round(end + float(offset), 3))
                           for (start, end), offset in zip(selected, offsets)]
    if any(start < 0 for start, _end in reference_intervals) or any(
        reference_intervals[index][0] < reference_intervals[index - 1][1]
        for index in range(1, len(reference_intervals))
    ):
        raise ValueError("corrected reference intervals must be non-negative and non-overlapping")
    if not source_id or not tracker_xml.is_file() or not metadata_xml.is_file():
        raise ValueError("source_id, tracker XML, and metadata XML are required")
    players = _player_metadata(metadata_xml)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = player_count = ball_count = malformed_count = excluded_period_count = 0

    with output_path.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as output:
            for _event, frame in ET.iterparse(tracker_xml, events=("end",)):
                if frame.tag != "frame":
                    continue
                try:
                    match_time = float(frame.get("matchTime", "")) / 1000.0
                except ValueError as exc:
                    raise ValueError("frame matchTime must be numeric") from exc
                window_index = next(
                    (index for index, (start, end) in enumerate(reference_intervals)
                     if start <= match_time < end), None
                )
                if window_index is None:
                    frame.clear()
                    continue
                period = frame.get("eventPeriod")
                if period not in PLAYING_PERIODS:
                    excluded_period_count += 1
                    frame.clear()
                    continue
                entities: list[dict[str, object]] = []
                for element in frame:
                    if element.tag not in {"player", "ball"}:
                        continue
                    position = _location(element.get("loc"))
                    if position is None:
                        malformed_count += 1
                        continue
                    entity_id = element.get("playerId") or element.tag
                    entity: dict[str, object] = {
                        "entityType": element.tag,
                        "id": entity_id,
                        "pitchPositionNormalized": position,
                    }
                    if element.tag == "player":
                        entity.update(players.get(entity_id, {}))
                        player_count += 1
                    else:
                        ball_count += 1
                    entities.append(entity)
                row = {
                    "sourceId": source_id,
                    "sourceFrameNumber": int(frame.get("frameNumber", "0")),
                    "matchTimeSeconds": match_time,
                    "videoTimelineSeconds": round(match_time - float(offsets[window_index]), 3),
                    "eventPeriod": period,
                    "ballStatus": frame.get("ballStatus"),
                    "entities": entities,
                }
                output.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
                frame_count += 1
                frame.clear()

    return {
        "schemaVersion": "football_analysis_pilot_pitch_reference_intervals_v2",
        "sourceId": source_id,
        "sourceTrackerXmlPath": str(tracker_xml),
        "sourceTrackerXmlSha256": _sha256(tracker_xml),
        "sourceMetadataXmlPath": str(metadata_xml),
        "sourceMetadataXmlSha256": _sha256(metadata_xml),
        "selectedIntervals": [[start, end] for start, end in selected],
        "referenceIntervals": [[start, end] for start, end in reference_intervals],
        "referenceClockOffsetsSeconds": [float(offset) for offset in offsets],
        "selectedDurationSeconds": sum(end - start for start, end in selected),
        "frameCount": frame_count,
        "playerEntityCount": player_count,
        "ballEntityCount": ball_count,
        "malformedLocationCount": malformed_count,
        "excludedPeriodFrameCount": excluded_period_count,
        "outputPath": str(output_path),
        "outputSizeBytes": output_path.stat().st_size,
        "outputSha256": _sha256(output_path),
        "coordinateSystem": "source-normalized pitch coordinates",
        "imageBoundingBoxesPresent": False,
        "manualLabelMinutesCompleted": 0,
        "heldOutLabelsAccessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize bounded SoccerTrack pitch references.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--tracker-xml", type=Path, required=True)
    parser.add_argument("--metadata-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_corpus.json"),
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        intervals = manifest["labelingProtocol"]["selectedIntervalsBySource"][args.source_id]
    except (KeyError, TypeError) as exc:
        parser.error(f"source {args.source_id!r} has no frozen intervals")
    candidates = [candidate for candidate in manifest["candidates"]
                  if candidate.get("sourceId") == args.source_id]
    if len(candidates) != 1:
        parser.error(f"source {args.source_id!r} must have one candidate")
    tasks = [task for task in json.loads(args.tasks.read_text(encoding="utf-8"))["tasks"]
             if task["sourceId"] == args.source_id]
    tasks.sort(key=lambda task: float(task["globalStartSeconds"]))
    if len(tasks) != len(intervals) or any(
        [float(task["globalStartSeconds"]), float(task["globalEndSeconds"])] != interval
        for task, interval in zip(tasks, intervals)
    ):
        parser.error("frozen task intervals differ from selected source intervals")
    clock_offsets = reference_clock_offsets(tasks, candidates[0]["paths"], args.metadata_xml)
    summary = materialize_reference_intervals(
        args.source_id,
        args.tracker_xml,
        args.metadata_xml,
        intervals,
        args.output,
        reference_clock_offsets_seconds=[clock_offsets[str(task["taskId"])] for task in tasks],
    )
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
