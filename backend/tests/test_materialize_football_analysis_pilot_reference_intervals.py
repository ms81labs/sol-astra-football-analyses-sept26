from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys

import pytest
from backend.scripts import materialize_football_analysis_pilot_reference_intervals as reference_module

from backend.scripts.materialize_football_analysis_pilot_reference_intervals import (
    materialize_reference_intervals,
)


def test_second_half_reference_clock_uses_metadata_anchor_not_video_concat_start(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.xml"
    metadata.write_text(
        '<metadata><period period="SECOND_HALF" matchTimeStart="8000"/></metadata>',
        encoding="utf-8",
    )
    tasks = [
        {"taskId": "first", "videoPath": "first.mp4", "globalStartSeconds": 3.0, "localStartSeconds": 3.0},
        {"taskId": "second", "videoPath": "second.mp4", "globalStartSeconds": 10.5, "localStartSeconds": 0.5},
    ]

    assert reference_module.reference_clock_offsets(tasks, ["first.mp4", "second.mp4"], metadata) == {
        "first": 0.0,
        "second": -2.0,
    }


def test_materializer_selects_tracker_window_and_writes_video_time(tmp_path: Path) -> None:
    tracker = tmp_path / "tracking.xml"
    tracker.write_text(
        '<data><frame matchTime="8200" frameNumber="1" eventPeriod="SECOND_HALF"/>'
        '<frame matchTime="10200" frameNumber="2" eventPeriod="SECOND_HALF"/></data>',
        encoding="utf-8",
    )
    metadata = tmp_path / "metadata.xml"
    metadata.write_text("<metadata/>", encoding="utf-8")
    output = tmp_path / "out.gz"

    summary = materialize_reference_intervals(
        "match", tracker, metadata, [[10.0, 11.0]], output,
        reference_clock_offsets_seconds=[-2.0],
    )

    rows = [json.loads(line) for line in gzip.decompress(output.read_bytes()).decode().splitlines()]
    assert [row["sourceFrameNumber"] for row in rows] == [1]
    assert rows[0]["matchTimeSeconds"] == 8.2
    assert rows[0]["videoTimelineSeconds"] == 10.2
    assert summary["referenceClockOffsetsSeconds"] == [-2.0]


def test_exact_millisecond_end_frame_is_excluded_after_clock_shift(tmp_path: Path) -> None:
    tracker = tmp_path / "tracking.xml"
    tracker.write_text(
        '<data><frame matchTime="4187927" frameNumber="1" eventPeriod="SECOND_HALF"/>'
        '<frame matchTime="4187967" frameNumber="2" eventPeriod="SECOND_HALF"/></data>',
        encoding="utf-8",
    )
    metadata = tmp_path / "metadata.xml"
    metadata.write_text("<metadata/>", encoding="utf-8")
    output = tmp_path / "out.gz"

    summary = materialize_reference_intervals(
        "match", tracker, metadata, [[4093.0, 4193.0]], output,
        reference_clock_offsets_seconds=[2699.967 - 2705.0],
    )

    assert summary["frameCount"] == 1
    assert [json.loads(line)["sourceFrameNumber"] for line in gzip.decompress(output.read_bytes()).decode().splitlines()] == [1]


def test_cli_uses_frozen_task_video_clock_offset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = tmp_path / "tracking.xml"
    tracker.write_text(
        '<data><frame matchTime="8200" frameNumber="1" eventPeriod="SECOND_HALF"/></data>',
        encoding="utf-8",
    )
    metadata = tmp_path / "metadata.xml"
    metadata.write_text(
        '<metadata><period period="SECOND_HALF" matchTimeStart="8000"/></metadata>',
        encoding="utf-8",
    )
    manifest = tmp_path / "corpus.json"
    manifest.write_text(json.dumps({
        "labelingProtocol": {"selectedIntervalsBySource": {"match": [[10.0, 11.0]]}},
        "candidates": [{"sourceId": "match", "paths": ["first.mp4", "second.mp4"]}],
    }), encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": [{
        "sourceId": "match", "taskId": "second", "videoPath": "second.mp4",
        "globalStartSeconds": 10.0, "globalEndSeconds": 11.0,
        "localStartSeconds": 0.0,
    }]}), encoding="utf-8")
    output = tmp_path / "out.gz"
    monkeypatch.setattr(sys, "argv", [
        "materialize", "--source-id", "match", "--tracker-xml", str(tracker),
        "--metadata-xml", str(metadata), "--manifest", str(manifest),
        "--tasks", str(tasks), "--output", str(output),
    ])

    reference_module.main()

    rows = [json.loads(line) for line in gzip.decompress(output.read_bytes()).decode().splitlines()]
    assert [row["videoTimelineSeconds"] for row in rows] == [10.2]


def test_materializes_only_bounded_playing_period_pitch_references(tmp_path: Path) -> None:
    tracker = tmp_path / "tracking.xml"
    tracker.write_text(
        """<data>
<frame matchTime="999" frameNumber="1" eventPeriod="FIRST_HALF" ballStatus="OUT"><player playerId="p1" loc="[0.1, 0.2]"/></frame>
<frame matchTime="1000" frameNumber="2" eventPeriod="FIRST_HALF" ballStatus="ALIVE"><player playerId="p1" loc="[0.2, 0.3]"/><player playerId="bad" loc="missing"/><ball playerId="ball" loc="[0.4, 0.5]"/></frame>
<frame matchTime="1999" frameNumber="3" eventPeriod="SECOND_HALF" ballStatus="ALIVE"><player playerId="p1" loc="[0.3, 0.4]"/></frame>
<frame matchTime="2000" frameNumber="4" eventPeriod="SECOND_HALF" ballStatus="ALIVE"><player playerId="p1" loc="[0.4, 0.5]"/></frame>
<frame matchTime="1500" frameNumber="5" eventPeriod="EXTRA_FIRST_HALF" ballStatus="ALIVE"><player playerId="p1" loc="[0.5, 0.6]"/></frame>
</data>""",
        encoding="utf-8",
    )
    metadata = tmp_path / "metadata.xml"
    metadata.write_text(
        """<metadata><players><player id="p1" teamId="t1" shirtNumber="9" position="CF" nameEn="Player One"/></players></metadata>""",
        encoding="utf-8",
    )
    output = tmp_path / "references.jsonl.gz"

    summary = materialize_reference_intervals("match", tracker, metadata, [[1.0, 2.0]], output)

    rows = [json.loads(line) for line in gzip.decompress(output.read_bytes()).decode().splitlines()]
    assert [row["sourceFrameNumber"] for row in rows] == [2, 3]
    assert rows[0]["entities"] == [
        {
            "entityType": "player",
            "id": "p1",
            "jerseyNumber": 9,
            "name": "Player One",
            "pitchPositionNormalized": {"x": 0.2, "y": 0.3},
            "role": "CF",
            "teamId": "t1",
        },
        {
            "entityType": "ball",
            "id": "ball",
            "pitchPositionNormalized": {"x": 0.4, "y": 0.5},
        },
    ]
    assert summary["frameCount"] == 2
    assert summary["playerEntityCount"] == 2
    assert summary["ballEntityCount"] == 1
    assert summary["malformedLocationCount"] == 1
    assert summary["excludedPeriodFrameCount"] == 1
    assert summary["selectedDurationSeconds"] == 1.0
    assert summary["imageBoundingBoxesPresent"] is False
    assert summary["manualLabelMinutesCompleted"] == 0
    assert summary["heldOutLabelsAccessed"] is False
    assert len(summary["outputSha256"]) == 64


@pytest.mark.parametrize(
    "intervals",
    [[], [[2, 1]], [[1, 2], [1.5, 3]], [[1, float("inf")]], [[True, 2]]],
)
def test_rejects_invalid_intervals(tmp_path: Path, intervals: list[list[float]]) -> None:
    tracker = tmp_path / "tracking.xml"
    tracker.write_text("<data/>", encoding="utf-8")
    metadata = tmp_path / "metadata.xml"
    metadata.write_text("<metadata/>", encoding="utf-8")

    with pytest.raises(ValueError, match="interval"):
        materialize_reference_intervals("match", tracker, metadata, intervals, tmp_path / "out.gz")
