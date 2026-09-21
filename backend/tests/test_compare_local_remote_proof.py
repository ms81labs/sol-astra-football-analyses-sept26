from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.compare_local_remote_proof as compare_local_remote_proof


def test_compare_local_remote_proof_sets_expected_diagnosis(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    local_result = {
        "recommendedProfile": "baseline_player_window",
        "profiles": [
            {
                "name": "baseline_player_window",
                "selectedSummary": {"frames": 18, "edgeFrameShare": 0.0, "pathLength": 251.55},
                "selectedScore": 153.0,
                "viable": True,
            }
        ],
    }

    def fake_run_local_ball_recovery_matrix(**kwargs):  # noqa: ANN003
        assert kwargs["video_path"] == clip_path
        return local_result

    class FakeSummary:
        def __init__(self, payload: dict[str, object]):
            self._payload = payload

        def model_dump(self, mode="json"):  # noqa: ANN001, ARG002
            return self._payload

    remote_payload = {
        "matchId": "match-123",
        "jobId": "job-123",
        "rawRowCount": 12577,
        "frameCount": 1516,
        "playerFrames": 1516,
        "withBallFrames": 0,
        "trackedPossessionFrames": 0,
        "controlledPossessionFrames": 0,
        "eventCount": 0,
        "eventTypes": {},
        "shotCount": 0,
        "ballSignalStatus": "trusted",
        "ballTrackViable": False,
        "recoveryProfileName": "baseline_player_window",
        "recoveryApplied": False,
        "recoveredSelectedFrames": 18,
        "dominantAnchorCoord": [12.5, 19.5],
        "dominantAnchorCount": 3,
        "dominantAnchorShare": 0.75,
        "meanSourceCenterY": 173.33,
        "meanSourceBoxArea": 800.0,
        "candidateEdgeShare": 0.35,
        "selectedEdgeFrameShare": 0.15,
        "fiveMinuteTruthReady": False,
        "truthGateReasons": ["Need at least 3 event families"],
    }

    def fake_summarize_match_benchmark(storage, match_id):  # noqa: ANN001
        assert match_id == "match-123"
        assert isinstance(storage.storage_root, Path)
        return FakeSummary(remote_payload)

    monkeypatch.setattr(
        compare_local_remote_proof,
        "run_local_ball_recovery_matrix",
        fake_run_local_ball_recovery_matrix,
    )
    monkeypatch.setattr(
        compare_local_remote_proof,
        "summarize_match_benchmark",
        fake_summarize_match_benchmark,
    )

    payload = compare_local_remote_proof.compare_local_remote_proof(
        video_path=clip_path,
        match_id="match-123",
        storage_root=tmp_path,
    )

    assert payload["videoPath"] == str(clip_path)
    assert payload["matchId"] == "match-123"
    assert payload["localRecommendedProfile"] == "baseline_player_window"
    assert payload["localBestSelectedSummary"] == {"frames": 18, "edgeFrameShare": 0.0, "pathLength": 251.55}
    assert payload["remoteImportedBenchmark"]["ballFrames"] == 0
    assert payload["remoteImportedBenchmark"]["truthGateReasons"] == ["Need at least 3 event families"]
    assert payload["diagnosis"] == "local_viable_but_remote_ball_missing"


def test_compare_local_remote_proof_sets_all_supported_diagnoses(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    class FakeSummary:
        def __init__(self, payload: dict[str, object]):
            self._payload = payload

        def model_dump(self, mode="json"):  # noqa: ANN001, ARG002
            return self._payload

    cases = [
        (
            {
                "recommendedProfile": "no_viable_profile",
                "profiles": [],
            },
            {
                "ballFrames": 0,
                "fiveMinuteTruthReady": False,
                "truthGateReasons": [],
            },
            "local_not_viable",
        ),
        (
            {
                "recommendedProfile": "baseline_player_window",
                "profiles": [{"name": "baseline_player_window", "selectedSummary": {"frames": 18}, "selectedScore": 1.0, "viable": True}],
            },
            {
                "ballFrames": 12,
                "fiveMinuteTruthReady": False,
                "truthGateReasons": ["Need at least 3 event families"],
            },
            "remote_ball_present_but_truth_gates_failed",
        ),
        (
            {
                "recommendedProfile": "baseline_player_window",
                "profiles": [{"name": "baseline_player_window", "selectedSummary": {"frames": 18}, "selectedScore": 1.0, "viable": True}],
            },
            {
                "ballFrames": 12,
                "fiveMinuteTruthReady": True,
                "truthGateReasons": [],
            },
            "remote_truth_ready",
        ),
    ]

    for local_result, remote_payload, expected in cases:
        monkeypatch.setattr(
            compare_local_remote_proof,
            "run_local_ball_recovery_matrix",
            lambda local_result=local_result, **kwargs: local_result,
        )
        monkeypatch.setattr(
            compare_local_remote_proof,
            "summarize_match_benchmark",
            lambda storage, match_id, remote_payload=remote_payload: FakeSummary(
                {
                    "matchId": match_id,
                    "jobId": "job-123",
                    "rawRowCount": 1,
                    "frameCount": 1,
                    "playerFrames": 1,
                    "withBallFrames": remote_payload["ballFrames"],
                    "trackedPossessionFrames": 1,
                    "controlledPossessionFrames": 1,
                    "eventCount": 1,
                    "eventTypes": {"recovery": 1},
                    "shotCount": 0,
                    "ballSignalStatus": "trusted",
                    "ballTrackViable": bool(remote_payload["ballFrames"]),
                    "recoveryProfileName": "baseline_player_window",
                    "recoveryApplied": False,
                    "recoveredSelectedFrames": 18,
                    "dominantAnchorCoord": [12.5, 19.5],
                    "dominantAnchorCount": 3,
                    "dominantAnchorShare": 0.75,
                    "meanSourceCenterY": 173.33,
                    "meanSourceBoxArea": 800.0,
                    "candidateEdgeShare": 0.35,
                    "selectedEdgeFrameShare": 0.15,
                    "fiveMinuteTruthReady": remote_payload["fiveMinuteTruthReady"],
                    "truthGateReasons": remote_payload["truthGateReasons"],
                }
            ),
        )

        payload = compare_local_remote_proof.compare_local_remote_proof(
            video_path=clip_path,
            match_id="match-123",
            storage_root=tmp_path,
        )
        assert payload["diagnosis"] == expected


def test_compare_local_remote_proof_main_serializes_compact_json(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    monkeypatch.setattr(
        compare_local_remote_proof,
        "compare_local_remote_proof",
        lambda **kwargs: {
            "videoPath": str(kwargs["video_path"]),
            "matchId": kwargs["match_id"],
            "localRecommendedProfile": "baseline_player_window",
            "localBestSelectedSummary": {"frames": 18},
            "remoteImportedBenchmark": {"ballFrames": 12, "truthGateReasons": []},
            "diagnosis": "remote_truth_ready",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "compare_local_remote_proof.py",
            "--video-path",
            str(clip_path),
            "--match-id",
            "match-123",
            "--storage-root",
            str(tmp_path),
        ],
    )

    compare_local_remote_proof.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["matchId"] == "match-123"
    assert payload["diagnosis"] == "remote_truth_ready"
    assert payload["remoteImportedBenchmark"]["ballFrames"] == 12
