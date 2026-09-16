"""The CVAT video export uses sampled clip-frame numbers, not UI indexes."""

from __future__ import annotations

import importlib
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest

from backend.scripts.validate_football_analysis_pilot_labels import validate_label_payload


TASK = {
    "taskId": "pilot-probe-01",
    "videoSha256": "a" * 64,
    "sourceWidth": 854,
    "sourceHeight": 480,
    "sourceFps": 30.0,
    "sourceStartFrame": 39478,
    "sourceEndFrameExclusive": 39490,
    "evaluationFrameStep": 6,
    "evaluationFrameCount": 2,
}
CLIP = {
    "taskId": "pilot-probe-01",
    "sourceStartFrame": 39478,
    "sourceEndFrameExclusive": 39490,
    "frameCount": 12,
    "width": 854,
    "height": 480,
    "path": "clips/pilot-probe-01.mp4",
    "sha256": "c" * 64,
    "sourceVideoSha256": "a" * 64,
}
XML = b"""<?xml version="1.0" encoding="utf-8"?>
<annotations>
  <version>1.1</version>
  <meta><task>
    <name>pilot-probe-01</name><size>2</size><mode>interpolation</mode>
    <start_frame>2</start_frame><stop_frame>8</stop_frame>
    <frame_filter>step=6</frame_filter>
    <original_size><width>854</width><height>480</height></original_size>
    <source>pilot-probe-01.mp4</source>
  </task></meta>
  <track id="0" label="player" source="manual">
    <box frame="2" outside="0" occluded="0" xtl="10" ytl="10" xbr="30" ybr="40">
      <attribute name="team">home</attribute>
    </box>
    <box frame="8" outside="0" occluded="0" xtl="11" ytl="10" xbr="31" ybr="40">
      <attribute name="team">home</attribute>
    </box>
  </track>
  <track id="1" label="ball" source="manual">
    <box frame="2" outside="0" occluded="0" xtl="100" ytl="100" xbr="104" ybr="104" />
    <box frame="8" outside="1" occluded="0" xtl="100" ytl="100" xbr="104" ybr="104" />
  </track>
</annotations>
"""
REVIEW = {
    "taskId": "pilot-probe-01",
    "annotatorId": "reviewer-1",
    "independentAnnotation": True,
    "pipelineOutputUsed": False,
    "lockedAt": "2026-09-15T07:00:00Z",
    "pitchReference": {
        "sourceId": "independent-pitch-reference",
        "sha256": "b" * 64,
        "associationMethod": "predeclared_identity",
    },
    "eventsReviewed": True,
    "events": [{"eventId": "pass-1", "type": "pass", "startFrame": 39480, "endFrameExclusive": 39486, "team": "home"}],
    "frames": [
        {
            "frameId": 39480,
            "reviewed": True,
            "ballVisibility": "visible",
            "ballPitchPositionMeters": [50.0, 20.0],
            "entityPitchPositionsMeters": {"cvat-0": [30.0, 20.0]},
            "possession": {"state": "observed", "team": "home", "trackId": "cvat-0"},
        },
        {
            "frameId": 39486,
            "reviewed": True,
            "ballVisibility": "not_visible",
            "ballPitchPositionMeters": None,
            "entityPitchPositionsMeters": {},
            "possession": {"state": "unknown", "team": "unknown", "trackId": None},
        },
    ],
}


def test_converts_real_cvat_video_frame_convention_into_locked_v3_labels() -> None:
    converter = importlib.import_module("backend.scripts.convert_football_analysis_pilot_cvat_labels")

    payload = converter.convert_cvat_export(TASK, CLIP, XML, REVIEW)

    assert [frame["frameId"] for frame in payload["frames"]] == [39480, 39486]
    assert payload["frames"][0]["entities"] == [{
        "trackId": "cvat-0", "kind": "player", "team": "home",
        "bbox": [10.0, 10.0, 30.0, 40.0], "pitchPositionMeters": [30.0, 20.0],
    }]
    assert payload["frames"][0]["ball"] == {
        "visibility": "visible", "bbox": [100.0, 100.0, 104.0, 104.0],
        "pitchPositionMeters": [50.0, 20.0],
    }
    assert payload["frames"][1]["ball"]["visibility"] == "not_visible"
    assert payload["frames"][1]["ball"]["bbox"] is None
    assert validate_label_payload(TASK, payload)["pitchPositionCount"] == 2


def test_rejects_clip_from_another_source_even_when_task_name_matches() -> None:
    converter = importlib.import_module("backend.scripts.convert_football_analysis_pilot_cvat_labels")
    clip = deepcopy(CLIP)
    clip["sourceVideoSha256"] = "d" * 64

    with pytest.raises(ValueError, match="clip does not match frozen task"):
        converter.convert_cvat_export(TASK, clip, XML, REVIEW)


def test_cli_hash_checks_clip_and_writes_only_frozen_label_path(tmp_path) -> None:
    clip_path = tmp_path / "clips" / "pilot-probe-01.mp4"
    clip_path.parent.mkdir()
    clip_path.write_bytes(b"synthetic clip for hash-bound CLI test")
    source_path = tmp_path / "sources" / "parent.mp4"
    source_path.parent.mkdir()
    source_path.write_bytes(b"synthetic parent source for hash-bound CLI test")
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    task = {
        **TASK, "videoSha256": source_sha, "videoPath": "sources/parent.mp4",
        "videoSizeBytes": source_path.stat().st_size,
        "labelOutputPath": "manual_labels/pilot-probe-01.json",
    }
    clip = {
        **CLIP, "sha256": hashlib.sha256(clip_path.read_bytes()).hexdigest(),
        "sourceVideoSha256": source_sha,
    }
    tasks_path = tmp_path / "tasks.json"
    clips_path = tmp_path / "clips.json"
    review_path = tmp_path / "review.json"
    zip_path = tmp_path / "export.zip"
    tasks_path.write_text(json.dumps({"tasks": [task]}))
    clips_path.write_text(json.dumps({"entries": [clip]}))
    review_json = json.dumps(REVIEW)
    review_path.write_text(review_json.replace('"pipelineOutputUsed": false', '"pipelineOutputUsed": true, "pipelineOutputUsed": false'))
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("annotations.xml", XML)

    command = [
        sys.executable, "-m", "backend.scripts.convert_football_analysis_pilot_cvat_labels",
        "--task-id", "pilot-probe-01", "--export-zip", str(zip_path),
        "--review", str(review_path), "--tasks", str(tasks_path),
        "--clips", str(clips_path), "--repo-root", str(tmp_path),
    ]
    duplicate = subprocess.run(
        command, cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True, text=True, check=False,
    )
    assert duplicate.returncode == 2
    assert "duplicate" in duplicate.stderr
    assert not (tmp_path / "manual_labels" / "pilot-probe-01.json").exists()

    review_path.write_text(review_json)
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = tmp_path / "manual_labels" / "pilot-probe-01.json"
    assert validate_label_payload(task, json.loads(output.read_text()))["frameCount"] == 2
    assert output.stat().st_mode & 0o777 == 0o600


def test_review_template_names_every_source_frame_but_cannot_lock_itself() -> None:
    converter = importlib.import_module("backend.scripts.convert_football_analysis_pilot_cvat_labels")

    template = converter.make_review_template(TASK)

    assert [frame["frameId"] for frame in template["frames"]] == [39480, 39486]
    assert template["events"] is None
    assert template["eventsReviewed"] is False
    assert all(frame["reviewed"] is False and frame["ballVisibility"] is None for frame in template["frames"])
    with pytest.raises(ValueError, match="human event review"):
        converter.convert_cvat_export(TASK, CLIP, XML, template)


def test_cli_creates_unreviewed_template_without_export_or_label_file(tmp_path) -> None:
    tasks_path = tmp_path / "tasks.json"
    clips_path = tmp_path / "clips.json"
    tasks_path.write_text(json.dumps({"tasks": [{**TASK, "labelOutputPath": "manual_labels/pilot-probe-01.json"}]}))
    clips_path.write_text(json.dumps({"entries": [CLIP]}))
    template_path = tmp_path / "review-template.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "backend.scripts.convert_football_analysis_pilot_cvat_labels",
            "--task-id", "pilot-probe-01", "--template-out", str(template_path),
            "--tasks", str(tasks_path), "--clips", str(clips_path), "--repo-root", str(tmp_path),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    template = json.loads(template_path.read_text())
    assert [frame["frameId"] for frame in template["frames"]] == [39480, 39486]
    assert template["independentAnnotation"] is False
    assert template_path.stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "manual_labels" / "pilot-probe-01.json").exists()


def test_rejects_conflicting_unmodeled_provenance_in_review_sidecar() -> None:
    converter = importlib.import_module("backend.scripts.convert_football_analysis_pilot_cvat_labels")
    review = deepcopy(REVIEW)
    review["modelAssisted"] = True

    with pytest.raises(ValueError, match="review sidecar fields"):
        converter.convert_cvat_export(TASK, CLIP, XML, review)


def test_cli_rejects_tampered_clip_hash_before_reading_annotation_export(tmp_path) -> None:
    clip_path = tmp_path / "clips" / "pilot-probe-01.mp4"
    clip_path.parent.mkdir()
    clip_path.write_bytes(b"the real clip bytes")
    tasks_path = tmp_path / "tasks.json"
    clips_path = tmp_path / "clips.json"
    tasks_path.write_text(json.dumps({"tasks": [{**TASK, "labelOutputPath": "manual_labels/pilot-probe-01.json"}]}))
    clips_path.write_text(json.dumps({"entries": [CLIP]}))

    result = subprocess.run(
        [
            sys.executable, "-m", "backend.scripts.convert_football_analysis_pilot_cvat_labels",
            "--task-id", "pilot-probe-01", "--export-zip", str(tmp_path / "missing.zip"),
            "--review", str(tmp_path / "missing.json"), "--tasks", str(tasks_path),
            "--clips", str(clips_path), "--repo-root", str(tmp_path),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "clip SHA-256 does not match frozen manifest" in result.stderr
    assert not (tmp_path / "manual_labels" / "pilot-probe-01.json").exists()


def test_cli_rejects_tampered_parent_source_before_reading_export(tmp_path) -> None:
    clip_path = tmp_path / "clips" / "pilot-probe-01.mp4"
    clip_path.parent.mkdir()
    clip_path.write_bytes(b"frozen synthetic clip")
    source_path = tmp_path / "sources" / "parent.mp4"
    source_path.parent.mkdir()
    source_path.write_bytes(b"unexpected parent source bytes")
    task = {
        **TASK,
        "videoPath": "sources/parent.mp4",
        "videoSizeBytes": source_path.stat().st_size,
        "labelOutputPath": "manual_labels/pilot-probe-01.json",
    }
    clip = {**CLIP, "sha256": hashlib.sha256(clip_path.read_bytes()).hexdigest()}
    tasks_path = tmp_path / "tasks.json"
    clips_path = tmp_path / "clips.json"
    tasks_path.write_text(json.dumps({"tasks": [task]}))
    clips_path.write_text(json.dumps({"entries": [clip]}))

    result = subprocess.run(
        [
            sys.executable, "-m", "backend.scripts.convert_football_analysis_pilot_cvat_labels",
            "--task-id", "pilot-probe-01", "--export-zip", str(tmp_path / "missing.zip"),
            "--review", str(tmp_path / "missing.json"), "--tasks", str(tasks_path),
            "--clips", str(clips_path), "--repo-root", str(tmp_path),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "parent source SHA-256 does not match frozen task" in result.stderr
    assert not (tmp_path / "manual_labels" / "pilot-probe-01.json").exists()


def test_live_repository_rejects_test_manifest_override(tmp_path) -> None:
    tasks_path = tmp_path / "forged-tasks.json"
    tasks_path.write_text(json.dumps({"tasks": [TASK]}))
    repository = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="cvat-manifest-test-", dir=repository / "backend/storage") as scratch:
        template_path = Path(scratch) / "review.json"
        result = subprocess.run(
            [
                sys.executable, "-m", "backend.scripts.convert_football_analysis_pilot_cvat_labels",
                "--task-id", "pilot-probe-01", "--template-out", str(template_path),
                "--tasks", str(tasks_path), "--repo-root", str(repository),
            ],
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 2
        assert "manifest overrides are only allowed in isolated test roots" in result.stderr
        assert not template_path.exists()
