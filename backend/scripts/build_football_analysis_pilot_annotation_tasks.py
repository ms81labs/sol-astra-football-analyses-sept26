from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2

from backend.scripts.validate_football_analysis_pilot_labels import SCHEMA_VERSION


LABEL_ROOT = Path(
    "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/"
    "football_analysis_pilot_corpus_v1/manual_labels"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_video(path: Path) -> dict[str, object]:
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if not path.is_file() or fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"video metadata is unavailable for {path}")
    return {
        "sha256": _sha256(path),
        "sizeBytes": path.stat().st_size,
        "fps": fps,
        "frameCount": frame_count,
        "width": width,
        "height": height,
    }


def build_annotation_tasks(
    inventory: dict[str, object],
    media: dict[str, dict[str, object]],
    *,
    inventory_sha256: str,
) -> dict[str, object]:
    protocol = inventory.get("labelingProtocol")
    if not isinstance(protocol, dict) or protocol.get("status") != "frozen":
        raise ValueError("labeling protocol must be frozen")
    scoring_protocol = protocol.get("scoringProtocol")
    if (
        not isinstance(scoring_protocol, dict)
        or type(scoring_protocol.get("version")) is not int
        or scoring_protocol["version"] <= 0
        or scoring_protocol.get("status") != "frozen"
    ):
        raise ValueError("scoring protocol must be versioned and frozen")
    scoring_sections = {
        "evaluationFrames",
        "ball",
        "players",
        "pitch",
        "possession",
        "events",
        "confidenceIntervals",
        "acceptance",
    }
    if (
        set(scoring_protocol) != {"version", "status", "frozenAt", *scoring_sections}
        or not isinstance(scoring_protocol.get("frozenAt"), str)
        or any(not isinstance(scoring_protocol.get(section), dict) for section in scoring_sections)
    ):
        raise ValueError("scoring protocol must contain the exact scoring sections")
    target_fps = scoring_protocol["evaluationFrames"].get("targetFps")
    if type(target_fps) is not int or target_fps <= 0:
        raise ValueError("scoring protocol targetFps must be a positive integer")
    intervals_by_source = protocol.get("selectedIntervalsBySource")
    candidates = inventory.get("candidates")
    target = inventory.get("target")
    if not isinstance(intervals_by_source, dict) or not isinstance(candidates, list) or not isinstance(target, dict):
        raise ValueError("inventory must contain selected intervals and candidates")
    expected_sources = target.get("disjointWholeMatches")
    expected_intervals = protocol.get("intervalsPerMatch")
    expected_seconds = protocol.get("secondsPerInterval")
    if isinstance(expected_sources, bool) or not isinstance(expected_sources, int) or expected_sources <= 0:
        raise ValueError("disjointWholeMatches must be a positive integer")
    if isinstance(expected_intervals, bool) or not isinstance(expected_intervals, int) or expected_intervals <= 0:
        raise ValueError("intervalsPerMatch must be a positive integer")
    if (
        isinstance(expected_seconds, bool)
        or not isinstance(expected_seconds, (int, float))
        or not math.isfinite(expected_seconds)
        or expected_seconds <= 0
    ):
        raise ValueError("secondsPerInterval must be a finite positive number")
    if len(intervals_by_source) != expected_sources:
        raise ValueError(f"protocol must select exactly {expected_sources} sources")
    candidates_by_id: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("sourceId"), str):
            raise ValueError("every candidate must have a string sourceId")
        source_id = candidate["sourceId"]
        if source_id in candidates_by_id:
            raise ValueError(f"duplicate candidate sourceId {source_id!r}")
        candidates_by_id[source_id] = candidate
    tasks: list[dict[str, object]] = []

    for source_id in sorted(intervals_by_source):
        candidate = candidates_by_id.get(source_id)
        if not candidate or candidate.get("pilotEligible") is not True or candidate.get("wholeMatch") is not True:
            raise ValueError(f"source {source_id!r} is not an eligible whole match")
        declared_duration = candidate.get("durationSeconds")
        if (
            isinstance(declared_duration, bool)
            or not isinstance(declared_duration, (int, float))
            or not math.isfinite(declared_duration)
            or declared_duration <= 0
        ):
            raise ValueError(f"source {source_id!r} requires finite positive durationSeconds")
        paths = candidate.get("paths") or [candidate.get("path")]
        if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
            raise ValueError(f"source {source_id!r} has invalid video paths")
        expected_hashes = candidate.get("sha256ByPath") or {paths[0]: candidate.get("sha256")}
        segments: list[tuple[str, dict[str, object], float, float]] = []
        offset = 0.0
        for path in paths:
            metadata = media.get(path)
            if not metadata or metadata.get("sha256") != expected_hashes.get(path):
                raise ValueError(f"source video hash mismatch for {path}")
            fps = float(metadata["fps"])
            duration = int(metadata["frameCount"]) / fps
            segments.append((path, metadata, offset, offset + duration))
            offset += duration
        if abs(offset - declared_duration) > max(0.001, 1 / float(segments[-1][1]["fps"])):
            raise ValueError(f"source duration mismatch for {source_id}")

        previous_end = -1.0
        intervals = intervals_by_source[source_id]
        if not isinstance(intervals, list) or len(intervals) != expected_intervals:
            raise ValueError(f"source {source_id!r} must have exactly {expected_intervals} intervals")
        for index, interval in enumerate(intervals, 1):
            if not isinstance(interval, list) or len(interval) != 2:
                raise ValueError(f"source {source_id!r} has an invalid interval")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in interval):
                raise ValueError(f"source {source_id!r} intervals require finite numeric bounds")
            start, end = map(float, interval)
            if not math.isfinite(start) or not math.isfinite(end) or start < previous_end or end <= start:
                raise ValueError(f"source {source_id!r} intervals must be finite, sorted, and non-overlapping")
            if not math.isclose(end - start, expected_seconds, abs_tol=1e-9):
                raise ValueError(f"source {source_id!r} interval {index} must be {expected_seconds:g} seconds")
            previous_end = end
            matching = [segment for segment in segments if segment[2] <= start and end <= segment[3] + 1e-9]
            if len(matching) != 1:
                raise ValueError(f"source {source_id!r} interval {index} crosses a video boundary")
            path, metadata, segment_start, _segment_end = matching[0]
            local_start = start - segment_start
            local_end = end - segment_start
            fps = float(metadata["fps"])
            start_frame = math.ceil(local_start * fps - 1e-9)
            end_frame = math.ceil(local_end * fps - 1e-9)
            evaluation_step = max(1, math.floor(fps / target_fps))
            evaluation_count = sum(frame_id % evaluation_step == 0 for frame_id in range(start_frame, end_frame))
            task_id = f"{source_id}-{index:02d}"
            tasks.append(
                {
                    "taskId": task_id,
                    "sourceId": source_id,
                    "evaluationRole": candidate.get("evaluationRole"),
                    "videoPath": path,
                    "videoSha256": metadata["sha256"],
                    "videoSizeBytes": int(metadata["sizeBytes"]),
                    "sourceWidth": int(metadata["width"]),
                    "sourceHeight": int(metadata["height"]),
                    "sourceFps": fps,
                    "globalStartSeconds": start,
                    "globalEndSeconds": end,
                    "localStartSeconds": local_start,
                    "localEndSeconds": local_end,
                    "sourceStartFrame": start_frame,
                    "sourceEndFrameExclusive": end_frame,
                    "frameCount": end_frame - start_frame,
                    "evaluationFrameStep": evaluation_step,
                    "evaluationFrameCount": evaluation_count,
                    "labelOutputPath": str(LABEL_ROOT / source_id / f"{task_id}.json"),
                    "status": "pending_human_annotation",
                }
            )

    selected_seconds = round(
        sum(float(task["globalEndSeconds"]) - float(task["globalStartSeconds"]) for task in tasks),
        9,
    )
    if not math.isclose(selected_seconds / 60, float(target["labeledMinutes"]), abs_tol=1e-9):
        raise ValueError("selected duration does not match the pilot target")
    return {
        "schemaVersion": "football_analysis_pilot_annotation_tasks_v2",
        "sourceInventorySha256": inventory_sha256,
        "selectionFrozenAt": protocol.get("frozenAt"),
        "annotationScope": protocol.get("annotationScope"),
        "coordinateSystem": "source-video pixels; xyxy boxes; zero-based source frames; end frame exclusive",
        "taskCount": len(tasks),
        "selectedDurationSeconds": selected_seconds,
        "selectedFrameCount": sum(int(task["frameCount"]) for task in tasks),
        "requiredLabelFrameCount": sum(int(task["evaluationFrameCount"]) for task in tasks),
        "heldOutReferenceLabelsAccessed": False,
        "pipelineOutputUsed": False,
        "labelSchemaVersion": SCHEMA_VERSION,
        "scoringProtocolVersion": scoring_protocol["version"],
        "tasks": tasks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frame-exact human annotation tasks for the frozen pilot.")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_corpus.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    inventory_bytes = args.inventory.read_bytes()
    inventory = json.loads(inventory_bytes)
    selected = set(inventory["labelingProtocol"]["selectedIntervalsBySource"])
    media: dict[str, dict[str, object]] = {}
    for candidate in inventory["candidates"]:
        if candidate.get("sourceId") not in selected:
            continue
        for relative in candidate.get("paths") or [candidate["path"]]:
            media[relative] = _probe_video(args.repo_root / relative)
    result = build_annotation_tasks(
        inventory,
        media,
        inventory_sha256=hashlib.sha256(inventory_bytes).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("taskCount", "selectedDurationSeconds", "selectedFrameCount", "requiredLabelFrameCount")}, indent=2))


if __name__ == "__main__":
    main()
