import hashlib
import json
from pathlib import Path

from backend.scripts.evaluate_football_analysis_pilot_soccertrack_events import (
    build_event_truth,
    summarize_tracking_continuity,
)
from backend.scripts import evaluate_football_analysis_pilot_soccertrack_events as events


def test_build_event_truth_maps_supported_classes_and_global_time_to_source_frames() -> None:
    task = {
        "globalStartSeconds": 60.0,
        "globalEndSeconds": 70.0,
        "localStartSeconds": 10.0,
        "sourceFps": 25.0,
    }
    actions = [
        {"gameTime": "1 - 1:01", "position": "61000", "label": "PASS"},
        {"gameTime": "1 - 1:02", "position": "62000", "label": "HIGH PASS"},
        {"gameTime": "1 - 1:03", "position": "63000", "label": "CROSS"},
        {"gameTime": "1 - 1:04", "position": "64000", "label": "SHOT"},
        {"gameTime": "1 - 1:05", "position": "65000", "label": "DRIVE"},
        {"gameTime": "1 - 1:11", "position": "71000", "label": "PASS"},
    ]

    truth = build_event_truth(task, actions)

    assert [event["type"] for event in truth] == ["pass", "pass", "pass", "shot"]
    assert [event["startFrame"] for event in truth] == [275, 300, 325, 350]
    assert all(event["team"] == "unknown" for event in truth)


def test_second_half_bas_truth_uses_tracker_anchor_for_video_source_frame() -> None:
    task = {
        "globalStartSeconds": 10.0, "globalEndSeconds": 12.0,
        "localStartSeconds": 0.0, "sourceFps": 25.0,
    }
    actions = [{"position": "9000", "label": "PASS"}]

    truth = build_event_truth(task, actions, reference_clock_offset_seconds=-2.0)

    assert [event["startFrame"] for event in truth] == [25]


def test_event_diagnostic_binds_corrected_validation_clock_metadata() -> None:
    artifact = json.loads(events.OUTPUT_PATH.read_text(encoding="utf-8"))
    corpus = json.loads(events.CORPUS_PATH.read_text(encoding="utf-8"))
    source = corpus["validationPitchReferenceMaterialization"]["resultsBySource"]["soccertrack-v2-117092"]

    assert artifact["sourceMetadataXmlSha256"] == source["metadataXmlSha256"]
    assert artifact["truthReferenceClockOffsetsSecondsByTask"] == {
        "soccertrack-v2-117092-01": 0.0,
        "soccertrack-v2-117092-02": 0.0,
        "soccertrack-v2-117092-03": 5.0,
    }


def test_summarize_tracking_continuity_counts_sampled_track_lifetimes() -> None:
    frames = [
        {"myTeam": [{"id": 1}], "enemies": [{"id": 2}, {"id": -1}], "unassignedPlayers": []},
        {"myTeam": [{"id": 1}], "enemies": [], "unassignedPlayers": [{"id": 3}]},
        {"myTeam": [{"id": 1}], "enemies": [], "unassignedPlayers": [{"id": 3}]},
    ]

    assert summarize_tracking_continuity(frames) == {
        "sampledFrames": 3,
        "playerRows": 7,
        "playerRowsPerSampledFrame": 7 / 3,
        "untrackedPlayerRows": 1,
        "uniqueTrackIds": 3,
        "sampledFramesPerTrack": {
            "median": 2,
            "p90NearestRank": 3,
            "maximum": 3,
            "singleFrameTracks": 1,
            "atMostFiveFrameTracks": 3,
            "atMostFiveFrameTrackShare": 1.0,
        },
    }
