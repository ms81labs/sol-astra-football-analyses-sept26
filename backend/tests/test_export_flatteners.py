from backend.app.export_flatteners import (
    flatten_events_for_csv,
    flatten_frames_for_csv,
    flatten_metrics_for_csv,
)
from backend.app.schemas import DetectedEvent, MetricAvailabilityRecord


def test_flatten_frames_for_csv_export():
    frames = [
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 40.0, "y": 50.0, "confidence": 0.9},
            "possession": {"team": "unassigned", "trackId": 11, "distance": 3.1},
        }
    ]

    rows = flatten_frames_for_csv(frames)

    assert rows == [
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ballX": 40.0,
            "ballY": 50.0,
            "ballConfidence": 0.9,
            "possessionTeam": "unassigned",
            "possessionTrackId": 11,
            "possessionDistance": 3.1,
        }
    ]


def test_flatten_events_for_csv_export():
    events = [
        DetectedEvent(
            type="pass",
            frameId=10,
            timestamp=2.0,
            team="unassigned",
            fromTrackId=7,
            toTrackId=11,
            description="Pass from #7 to #11",
        )
    ]

    rows = flatten_events_for_csv(events)

    assert rows == [
        {
            "type": "pass",
            "frameId": 10,
            "timestamp": 2.0,
            "team": "unassigned",
            "fromTrackId": 7,
            "toTrackId": 11,
            "description": "Pass from #7 to #11",
            "reviewStatus": "unreviewed",
            "heuristicName": "provisional_event_suggestion",
        }
    ]


def test_flatten_metrics_for_csv_preserves_unknown_availability():
    records = [
        MetricAvailabilityRecord(
            metric="my_team_ppda",
            availability="unknown",
            value=None,
            reasonCodes=["ZERO_DENOMINATOR"],
        ),
        MetricAvailabilityRecord(
            metric="experimental_shot_quality",
            availability="experimental",
            value=0.42,
            publishedLabel="experimental_shot_quality",
        ),
    ]

    rows = flatten_metrics_for_csv(records)

    assert rows[0]["metric"] == "my_team_ppda"
    assert rows[0]["availability"] == "unknown"
    assert rows[0]["value"] is None
    assert rows[0]["reasonCodes"] == "ZERO_DENOMINATOR"
    assert rows[1]["publishedLabel"] == "experimental_shot_quality"
