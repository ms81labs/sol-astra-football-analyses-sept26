from __future__ import annotations

from copy import deepcopy

import pytest

from backend.scripts.build_football_analysis_pilot_annotation_tasks import (
    build_annotation_tasks,
)


def _scoring_protocol() -> dict[str, object]:
    return {
        "version": 3,
        "status": "frozen",
        "frozenAt": "2026-09-14",
        "evaluationFrames": {"targetFps": 5},
        "ball": {},
        "players": {},
        "pitch": {},
        "possession": {},
        "events": {},
        "confidenceIntervals": {},
        "acceptance": {},
    }


def test_maps_global_intervals_to_source_frames_without_opening_reference_labels() -> None:
    inventory = {
        "schemaVersion": 1,
        "suiteName": "pilot",
        "target": {"disjointWholeMatches": 2, "labeledMinutes": 0.10333333333333333},
        "labelingProtocol": {
            "status": "frozen",
            "frozenAt": "2026-09-14",
            "intervalsPerMatch": 1,
            "secondsPerInterval": 3.1,
            "annotationScope": ["visible ball bounding box"],
            "scoringProtocol": _scoring_protocol(),
            "selectedIntervalsBySource": {
                "two-halves": [[12.0, 15.1]],
                "single": [[2.1, 5.2]],
            },
        },
        "candidates": [
            {
                "sourceId": "two-halves",
                "paths": ["a.mp4", "b.mp4"],
                "sha256ByPath": {"a.mp4": "a" * 64, "b.mp4": "b" * 64},
                "durationSeconds": 20.0,
                "wholeMatch": True,
                "pilotEligible": True,
                "evaluationRole": "validation",
            },
            {
                "sourceId": "single",
                "path": "single.mp4",
                "sha256": "c" * 64,
                "durationSeconds": 10.0,
                "wholeMatch": True,
                "pilotEligible": True,
                "evaluationRole": "held_out_test",
                "referenceLabelPaths": ["must-not-be-copied.json"],
            },
        ],
    }
    media = {
        "a.mp4": {"sha256": "a" * 64, "sizeBytes": 1, "fps": 25.0, "frameCount": 250, "width": 100, "height": 50},
        "b.mp4": {"sha256": "b" * 64, "sizeBytes": 2, "fps": 25.0, "frameCount": 250, "width": 100, "height": 50},
        "single.mp4": {"sha256": "c" * 64, "sizeBytes": 3, "fps": 30.0, "frameCount": 300, "width": 80, "height": 40},
    }

    result = build_annotation_tasks(inventory, media, inventory_sha256="d" * 64)

    assert result["taskCount"] == 2
    assert result["selectedDurationSeconds"] == 6.2
    assert result["selectedFrameCount"] == 171
    assert result["requiredLabelFrameCount"] == 31
    assert result["heldOutReferenceLabelsAccessed"] is False
    assert result["pipelineOutputUsed"] is False
    assert result["labelSchemaVersion"] == "football_analysis_pilot_labels_v3"
    assert result["scoringProtocolVersion"] == 3
    assert result["tasks"] == [
        {
            "taskId": "single-01",
            "sourceId": "single",
            "evaluationRole": "held_out_test",
            "videoPath": "single.mp4",
            "videoSha256": "c" * 64,
            "videoSizeBytes": 3,
            "sourceWidth": 80,
            "sourceHeight": 40,
            "sourceFps": 30.0,
            "globalStartSeconds": 2.1,
            "globalEndSeconds": 5.2,
            "localStartSeconds": 2.1,
            "localEndSeconds": 5.2,
            "sourceStartFrame": 63,
            "sourceEndFrameExclusive": 156,
            "frameCount": 93,
            "evaluationFrameStep": 6,
            "evaluationFrameCount": 15,
            "labelOutputPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/manual_labels/single/single-01.json",
            "status": "pending_human_annotation",
        },
        {
            "taskId": "two-halves-01",
            "sourceId": "two-halves",
            "evaluationRole": "validation",
            "videoPath": "b.mp4",
            "videoSha256": "b" * 64,
            "videoSizeBytes": 2,
            "sourceWidth": 100,
            "sourceHeight": 50,
            "sourceFps": 25.0,
            "globalStartSeconds": 12.0,
            "globalEndSeconds": 15.1,
            "localStartSeconds": 2.0,
            "localEndSeconds": 5.1,
            "sourceStartFrame": 50,
            "sourceEndFrameExclusive": 128,
            "frameCount": 78,
            "evaluationFrameStep": 5,
            "evaluationFrameCount": 16,
            "labelOutputPath": "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/manual_labels/two-halves/two-halves-01.json",
            "status": "pending_human_annotation",
        },
    ]


def _valid_protocol_inventory() -> dict[str, object]:
    return {
        "target": {"disjointWholeMatches": 1, "labeledMinutes": 5},
        "labelingProtocol": {
            "status": "frozen",
            "intervalsPerMatch": 3,
            "secondsPerInterval": 100,
            "scoringProtocol": _scoring_protocol(),
            "selectedIntervalsBySource": {"match": [[0, 100], [100, 200], [200, 300]]},
        },
        "candidates": [
            {
                "sourceId": "match",
                "path": "match.mp4",
                "sha256": "a" * 64,
                "durationSeconds": 300,
                "wholeMatch": True,
                "pilotEligible": True,
                "evaluationRole": "validation",
            }
        ],
    }


MEDIA = {
    "match.mp4": {
        "sha256": "a" * 64,
        "sizeBytes": 1,
        "fps": 1.0,
        "frameCount": 300,
        "width": 1,
        "height": 1,
    }
}


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("target", "disjointWholeMatches", 1.9, "positive integer"),
        ("labelingProtocol", "intervalsPerMatch", 3.9, "positive integer"),
        ("labelingProtocol", "secondsPerInterval", True, "finite positive number"),
        ("target", "disjointWholeMatches", 2, "exactly 2 sources"),
        ("labelingProtocol", "intervalsPerMatch", 2, "exactly 2 intervals"),
        ("labelingProtocol", "secondsPerInterval", 99, "must be 99 seconds"),
    ],
)
def test_rejects_protocol_cardinality_drift(
    section: str,
    field: str,
    value: object,
    message: str,
) -> None:
    inventory = deepcopy(_valid_protocol_inventory())
    inventory[section][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match=message):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)


@pytest.mark.parametrize("interval", [[False, 100], ["0", "100"]])
def test_rejects_coerced_interval_endpoints(interval: list[object]) -> None:
    inventory = _valid_protocol_inventory()
    inventory["labelingProtocol"]["selectedIntervalsBySource"]["match"][0] = interval  # type: ignore[index]

    with pytest.raises(ValueError, match="finite numeric bounds"):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)


def test_rejects_duplicate_candidate_source_ids() -> None:
    inventory = _valid_protocol_inventory()
    inventory["candidates"].append(deepcopy(inventory["candidates"][0]))  # type: ignore[union-attr,index]

    with pytest.raises(ValueError, match="duplicate candidate sourceId"):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)


@pytest.mark.parametrize("scoring_protocol", [None, {"version": True, "status": "frozen"}, {"version": 1, "status": "draft"}])
def test_requires_versioned_frozen_scoring_protocol(scoring_protocol: object) -> None:
    inventory = _valid_protocol_inventory()
    inventory["labelingProtocol"]["scoringProtocol"] = scoring_protocol  # type: ignore[index]

    with pytest.raises(ValueError, match="scoring protocol must be versioned and frozen"):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)


def test_rejects_incomplete_scoring_protocol() -> None:
    inventory = _valid_protocol_inventory()
    del inventory["labelingProtocol"]["scoringProtocol"]["ball"]  # type: ignore[index]

    with pytest.raises(ValueError, match="exact scoring sections"):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)


@pytest.mark.parametrize("duration", [float("nan"), True, "300"])
def test_rejects_coerced_candidate_duration(duration: object) -> None:
    inventory = _valid_protocol_inventory()
    inventory["candidates"][0]["durationSeconds"] = duration  # type: ignore[index]

    with pytest.raises(ValueError, match="finite positive durationSeconds"):
        build_annotation_tasks(inventory, MEDIA, inventory_sha256="b" * 64)
