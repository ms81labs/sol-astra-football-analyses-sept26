from __future__ import annotations

import backend.app.proof_summary as proof_summary


def test_build_canonical_proof_summary_from_live_summary_payload_includes_required_judge_fields() -> None:
    payload = proof_summary.build_canonical_proof_summary(
        {
            "matchId": "match-123",
            "jobId": "job-123",
            "detectorModelPath": "/workspace/weights/yolov10n.pt",
            "detectorModelName": "yolov10n.pt",
            "rawRowCount": 8,
            "withBallFrames": 5,
            "acceptedBallFrames": 4,
            "supportedAcceptedBallRatio": 0.75,
            "controlledPossessionFrames": 3,
            "eventTypes": {"pass": 2, "recovery": 1, "shot": 0},
            "truthGateReasons": ["Need more samples"],
            "recoveryProfileName": "proposal_windows_075",
            "ballTrackViable": True,
        }
    )

    assert payload["savedMatchId"] == "match-123"
    assert payload["jobId"] == "job-123"
    assert payload["rawRows"] == 8
    assert payload["ballFrames"] == 5
    assert payload["acceptedBallFrames"] == 4
    assert payload["supportedAcceptedBallRatio"] == 0.75
    assert payload["controlledPossessionFrames"] == 3
    assert payload["eventTypes"] == {"pass": 2, "recovery": 1, "shot": 0}
    assert payload["eventFamilyCount"] == 2
    assert payload["truthGateReasons"] == ["Need more samples"]
    assert payload["recoveryProfile"] == "proposal_windows_075"
    assert payload["ballTrackViable"] is True


def test_build_canonical_proof_summary_backfills_missing_judge_fields_from_saved_bundle_sources() -> None:
    payload = proof_summary.build_canonical_proof_summary(
        {
            "savedMatchId": "match-123",
            "jobId": "job-123",
            "acceptedBallFrames": 0,
            "supportedAcceptedBallRatio": 0.0,
            "controlledPossessionFrames": 0,
            "eventTypes": {},
            "truthGateReasons": ["Need controlled possession"],
        },
        {
            "matchId": "match-123",
            "jobId": "job-123",
            "rawRowCount": 15187,
            "acceptedBallFrames": 0,
            "supportedAcceptedBallRatio": 0.0,
            "controlledPossessionFrames": 0,
            "eventFamilyCount": 0,
            "truthGateReasons": ["Need controlled possession"],
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.0,
        },
    )

    assert payload["savedMatchId"] == "match-123"
    assert payload["jobId"] == "job-123"
    assert payload["rawRows"] == 15187
    assert payload["acceptedBallFrames"] == 0
    assert payload["supportedAcceptedBallRatio"] == 0.0
    assert payload["controlledPossessionFrames"] == 0
    assert payload["eventFamilyCount"] == 0
    assert payload["truthGateReasons"] == ["Need controlled possession"]
    assert payload["ballTrackViable"] is False
    assert payload["ballTrackEdgeFrameShare"] == 0.0
