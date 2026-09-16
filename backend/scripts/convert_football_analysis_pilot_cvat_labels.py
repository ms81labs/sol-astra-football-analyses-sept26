"""Convert a reviewed CVAT-for-video export to the frozen pilot label contract."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from backend.scripts.validate_football_analysis_pilot_labels import (
    SCHEMA_VERSION,
    TEAMS,
    parse_unique_json,
    validate_label_payload,
)


def convert_cvat_export(
    task: Mapping[str, object],
    clip: Mapping[str, object],
    xml_bytes: bytes,
    review: Mapping[str, object],
) -> dict[str, object]:
    """Require exact CVAT task metadata and explicit per-frame human review."""

    if not isinstance(xml_bytes, bytes) or len(xml_bytes) > 32_000_000 or b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        raise ValueError("CVAT XML is unsafe or too large")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("CVAT XML is malformed") from exc
    if root.tag != "annotations" or root.findtext("version") != "1.1" or any(child.tag not in {"version", "meta", "track"} for child in root):
        raise ValueError("expected CVAT for video 1.1 annotations and tracks")
    meta = root.find("meta/task")
    if meta is None:
        raise ValueError("CVAT task metadata is missing")

    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    step = int(task["evaluationFrameStep"])
    count = int(task["evaluationFrameCount"])
    first = (-start) % step
    last = first + step * (count - 1)
    if (
        clip.get("taskId") != task["taskId"]
        or clip.get("sourceStartFrame") != start
        or clip.get("sourceEndFrameExclusive") != end
        or clip.get("frameCount") != end - start
        or clip.get("width") != task["sourceWidth"]
        or clip.get("height") != task["sourceHeight"]
        or clip.get("sourceVideoSha256") != task["videoSha256"]
    ):
        raise ValueError("clip does not match frozen task")
    expected_meta = {
        "name": str(task["taskId"]),
        "size": str(count),
        "mode": "interpolation",
        "start_frame": str(first),
        "stop_frame": str(last),
        "frame_filter": f"step={step}",
        "original_size/width": str(task["sourceWidth"]),
        "original_size/height": str(task["sourceHeight"]),
        "source": Path(str(clip["path"])).name,
    }
    for field, expected in expected_meta.items():
        if meta.findtext(field) != expected:
            raise ValueError(f"CVAT {field} does not match frozen task")

    expected_ids = [frame_id for frame_id in range(start, end) if frame_id % step == 0]
    if len(expected_ids) != count:
        raise ValueError("frozen evaluation frame count is inconsistent")
    if not isinstance(review, Mapping) or set(review) != {
        "taskId", "annotatorId", "independentAnnotation", "pipelineOutputUsed", "lockedAt",
        "pitchReference", "eventsReviewed", "events", "frames",
    }:
        raise ValueError("review sidecar fields must match the declared contract exactly")
    if review.get("taskId") != task["taskId"] or review.get("eventsReviewed") is not True:
        raise ValueError("human event review and task identity are required")
    review_frames = review.get("frames")
    if not isinstance(review_frames, list) or [frame.get("frameId") if isinstance(frame, Mapping) else None for frame in review_frames] != expected_ids:
        raise ValueError("human review must cover every declared source frame in order")

    entities_by_frame: dict[int, list[dict[str, object]]] = {frame_id: [] for frame_id in expected_ids}
    ball_by_frame: dict[int, list[float]] = {}
    track_ids: set[str] = set()
    for track in root.findall("track"):
        if track.get("source") != "manual" or track.get("label") not in {"player", "referee", "ball"}:
            raise ValueError("CVAT track must have a manually labeled supported kind")
        raw_track_id = track.get("id", "")
        if not raw_track_id.isdecimal() or raw_track_id in track_ids:
            raise ValueError("CVAT track ID must be a unique nonnegative integer")
        track_ids.add(raw_track_id)
        stable_id = f"cvat-{raw_track_id}"
        if any(child.tag not in {"box", "attribute"} for child in track):
            raise ValueError("CVAT track contains unsupported annotations")
        seen_frames: set[int] = set()
        for box in track.findall("box"):
            raw_frame = box.get("frame", "")
            if not raw_frame.isdecimal():
                raise ValueError("CVAT box frame is invalid")
            clip_frame = int(raw_frame)
            frame_id = start + clip_frame
            if frame_id not in entities_by_frame or clip_frame in seen_frames:
                raise ValueError("CVAT box is off cadence or duplicated")
            seen_frames.add(clip_frame)
            outside = box.get("outside")
            occluded = box.get("occluded")
            if outside not in {"0", "1"} or occluded not in {"0", "1"}:
                raise ValueError("CVAT box visibility flags are invalid")
            if outside == "1":
                continue
            try:
                bbox = [float(box.attrib[key]) for key in ("xtl", "ytl", "xbr", "ybr")]
            except (KeyError, ValueError) as exc:
                raise ValueError("CVAT box coordinates are invalid") from exc
            if track.get("label") == "ball":
                if occluded == "1" or frame_id in ball_by_frame:
                    raise ValueError("CVAT ball box is occluded or duplicated")
                ball_by_frame[frame_id] = bbox
                continue
            if track.get("label") == "player":
                team_nodes = box.findall("attribute[@name='team']")
                if len(team_nodes) != 1 or team_nodes[0].text not in TEAMS:
                    raise ValueError("CVAT player team is missing or unresolved")
                team = team_nodes[0].text
            else:
                team = "unknown"
            entities_by_frame[frame_id].append({
                "trackId": stable_id,
                "kind": track.get("label"),
                "team": team,
                "bbox": bbox,
            })

    frames: list[dict[str, object]] = []
    for expected_id, reviewed in zip(expected_ids, review_frames, strict=True):
        if not isinstance(reviewed, Mapping) or reviewed.get("reviewed") is not True:
            raise ValueError(f"source frame {expected_id} is not independently reviewed")
        if set(reviewed) != {"frameId", "reviewed", "ballVisibility", "ballPitchPositionMeters", "entityPitchPositionsMeters", "possession"}:
            raise ValueError(f"source frame {expected_id} review fields are incomplete")
        pitch = reviewed["entityPitchPositionsMeters"]
        if not isinstance(pitch, Mapping):
            raise ValueError("entity pitch positions must be keyed by CVAT track ID")
        entities = sorted(entities_by_frame[expected_id], key=lambda entity: str(entity["trackId"]))
        entity_ids = {str(entity["trackId"]) for entity in entities}
        if set(pitch) - entity_ids:
            raise ValueError("entity pitch position refers to a missing CVAT track")
        for entity in entities:
            entity["pitchPositionMeters"] = pitch.get(entity["trackId"])
        frames.append({
            "frameId": expected_id,
            "ball": {
                "visibility": reviewed["ballVisibility"],
                "bbox": ball_by_frame.get(expected_id),
                "pitchPositionMeters": reviewed["ballPitchPositionMeters"],
            },
            "entities": entities,
            "possession": reviewed["possession"],
        })

    payload: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "taskId": task["taskId"],
        "sourceVideoSha256": task["videoSha256"],
        "independentAnnotation": review.get("independentAnnotation"),
        "pipelineOutputUsed": review.get("pipelineOutputUsed"),
        "annotatorId": review.get("annotatorId"),
        "lockedAt": review.get("lockedAt"),
        "pitchReference": review.get("pitchReference"),
        "frames": frames,
        "events": review.get("events"),
    }
    validate_label_payload(task, payload)
    return payload


def make_review_template(task: Mapping[str, object]) -> dict[str, object]:
    """List every frozen frame with blanks that cannot pass the lock gate."""

    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    step = int(task["evaluationFrameStep"])
    frame_ids = [frame_id for frame_id in range(start, end) if frame_id % step == 0]
    if len(frame_ids) != task["evaluationFrameCount"]:
        raise ValueError("frozen evaluation frame count is inconsistent")
    return {
        "taskId": task["taskId"],
        "annotatorId": None,
        "independentAnnotation": False,
        "pipelineOutputUsed": None,
        "lockedAt": None,
        "pitchReference": None,
        "eventsReviewed": False,
        "events": None,
        "frames": [
            {
                "frameId": frame_id,
                "reviewed": False,
                "ballVisibility": None,
                "ballPitchPositionMeters": None,
                "entityPitchPositionsMeters": {},
                "possession": None,
            }
            for frame_id in frame_ids
        ],
    }


def _write_new_json(path: Path, payload: Mapping[str, object]) -> None:
    """Create a private file, never replacing a reviewer-owned file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, indent=2, sort_keys=True)
            output_file.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--export-zip", type=Path, help="CVAT for video 1.1 export without images")
    parser.add_argument("--review", type=Path, help="independently completed review sidecar")
    parser.add_argument("--template-out", type=Path, help="create an incomplete reviewer template only")
    parser.add_argument("--tasks", type=Path, default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"))
    parser.add_argument("--clips", type=Path, default=Path("backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/annotation_clips/annotation_clips_manifest_v1.json"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if (args.template_out is None) == (args.export_zip is None):
        parser.error("choose exactly one of --template-out or --export-zip")
    if args.export_zip is not None and args.review is None or args.template_out is not None and args.review is not None:
        parser.error("--review is required with --export-zip and forbidden with --template-out")
    try:
        root = args.repo_root.resolve()
        repository = Path(__file__).resolve().parents[2]
        if root.is_relative_to(repository) and (
            args.tasks.resolve() != repository / "backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"
            or args.clips.resolve() != repository / "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/annotation_clips/annotation_clips_manifest_v1.json"
        ):
            raise ValueError("manifest overrides are only allowed in isolated test roots")
        tasks = json.loads(args.tasks.read_text(encoding="utf-8"))["tasks"]
        task_matches = [task for task in tasks if task.get("taskId") == args.task_id]
        if len(task_matches) != 1:
            raise ValueError("task ID must identify one frozen task")
        task = task_matches[0]
        if args.template_out is not None:
            template_path = (root / args.template_out).resolve()
            if not template_path.is_relative_to(root):
                raise ValueError("review template path must stay inside the repository")
            _write_new_json(template_path, make_review_template(task))
            print(template_path)
            return
        clips = json.loads(args.clips.read_text(encoding="utf-8"))["entries"]
        clip_matches = [clip for clip in clips if clip.get("taskId") == args.task_id]
        if len(clip_matches) != 1:
            raise ValueError("task ID must identify one frozen clip")
        clip = clip_matches[0]
        clip_path = (root / str(clip["path"])).resolve()
        output = (root / str(task["labelOutputPath"])).resolve()
        if not clip_path.is_relative_to(root) or not output.is_relative_to(root):
            raise ValueError("clip and label paths must stay inside the repository")
        if output.exists():
            raise ValueError("locked label file already exists; it will not be overwritten")
        with clip_path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != clip["sha256"]:
                raise ValueError("clip SHA-256 does not match frozen manifest")
        source_path = (root / str(task["videoPath"])).resolve()
        if not source_path.is_relative_to(root):
            raise ValueError("parent source path must stay inside the repository")
        if source_path.stat().st_size != task["videoSizeBytes"]:
            raise ValueError("parent source size does not match frozen task")
        with source_path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != task["videoSha256"]:
                raise ValueError("parent source SHA-256 does not match frozen task")
        with ZipFile(args.export_zip) as archive:
            members = archive.namelist()
            if members != ["annotations.xml"] or archive.getinfo("annotations.xml").file_size > 32_000_000:
                raise ValueError("CVAT export must contain only a bounded annotations.xml")
            xml_bytes = archive.read("annotations.xml")
        review = parse_unique_json(args.review.read_bytes())
        payload = convert_cvat_export(task, clip, xml_bytes, review)
        _write_new_json(output, payload)
        print(output)
    except (BadZipFile, FileNotFoundError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
