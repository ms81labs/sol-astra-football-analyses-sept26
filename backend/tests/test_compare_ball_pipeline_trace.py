from __future__ import annotations

import json

import backend.scripts.compare_ball_pipeline_trace as compare_ball_pipeline_trace
from backend.app.storage import Storage


def _write_trace(storage: Storage, match_id: str, stages: list[dict[str, object]]) -> None:
    storage.save_analysis_artifact(
        match_id,
        "ball_pipeline_trace",
        {
            "traceVersion": 1,
            "matchId": match_id,
            "jobId": f"job-{match_id}",
            "processingBackend": "local",
            "inputMode": "video",
            "videoPath": f"/tmp/{match_id}.mp4",
            "workerPath": "local",
            "stages": stages,
        },
    )


def _stage(stage: str, *, ball_rows: int = 0, ball_frames: int = 0, tracked: int = 0, controlled: int = 0, event_count: int = 0, event_types: dict[str, int] | None = None) -> dict[str, object]:
    return {
        "stage": stage,
        "ballRowCount": ball_rows,
        "ballFrameCount": ball_frames,
        "playerRowCount": 10,
        "frameCount": 10,
        "trackedPossessionFrames": tracked,
        "controlledPossessionFrames": controlled,
        "eventCount": event_count,
        "eventTypes": event_types or {},
        "firstBallFrame": 0 if ball_frames else None,
        "lastBallFrame": 9 if ball_frames else None,
    }


def test_compare_ball_pipeline_trace_detects_divergence_before_returned_rows(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    local_stages = [
        _stage("processVideoPrimary", ball_rows=5, ball_frames=5),
        _stage("processVideoRecovery", ball_rows=2, ball_frames=2),
        _stage("processVideoReturnedRows", ball_rows=7, ball_frames=7),
        _stage("persistRawRows", ball_rows=7, ball_frames=7),
        _stage("normalizedFrames", ball_rows=7, ball_frames=7),
        _stage("possessionOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5),
        _stage("eventOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5, event_count=3, event_types={"pass": 1}),
    ]
    remote_stages = [
        _stage("processVideoPrimary", ball_rows=0, ball_frames=0),
        _stage("processVideoRecovery", ball_rows=0, ball_frames=0),
        _stage("processVideoReturnedRows", ball_rows=0, ball_frames=0),
        _stage("persistRawRows", ball_rows=0, ball_frames=0),
        _stage("normalizedFrames", ball_rows=0, ball_frames=0),
        _stage("possessionOutputs", tracked=0, controlled=0),
        _stage("eventOutputs", tracked=0, controlled=0),
    ]
    _write_trace(storage, "local-match", local_stages)
    _write_trace(storage, "remote-match", remote_stages)
    monkeypatch.setattr(
        compare_ball_pipeline_trace,
        "summarize_match_benchmark",
        lambda storage, match_id: type("FakeSummary", (), {"fiveMinuteTruthReady": False})(),
    )

    payload = compare_ball_pipeline_trace.compare_ball_pipeline_trace(
        local_match_id="local-match",
        remote_match_id="remote-match",
        storage_root=tmp_path,
    )

    assert payload["firstDivergingStage"] == "processVideoPrimary"
    assert payload["diagnosis"] == "diverges_before_returned_rows"


def test_compare_ball_pipeline_trace_detects_divergence_during_import_normalization(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    common_prefix = [
        _stage("processVideoPrimary", ball_rows=5, ball_frames=5),
        _stage("processVideoRecovery", ball_rows=2, ball_frames=2),
        _stage("processVideoReturnedRows", ball_rows=7, ball_frames=7),
    ]
    _write_trace(storage, "local-match", common_prefix + [
        _stage("persistRawRows", ball_rows=7, ball_frames=7),
        _stage("normalizedFrames", ball_rows=7, ball_frames=7),
        _stage("possessionOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5),
        _stage("eventOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5, event_count=3, event_types={"pass": 1}),
    ])
    _write_trace(storage, "remote-match", common_prefix + [
        _stage("persistRawRows", ball_rows=0, ball_frames=0),
        _stage("normalizedFrames", ball_rows=0, ball_frames=0),
        _stage("possessionOutputs", tracked=0, controlled=0),
        _stage("eventOutputs", tracked=0, controlled=0),
    ])
    monkeypatch.setattr(
        compare_ball_pipeline_trace,
        "summarize_match_benchmark",
        lambda storage, match_id: type("FakeSummary", (), {"fiveMinuteTruthReady": False})(),
    )

    payload = compare_ball_pipeline_trace.compare_ball_pipeline_trace(
        local_match_id="local-match",
        remote_match_id="remote-match",
        storage_root=tmp_path,
    )

    assert payload["firstDivergingStage"] == "persistRawRows"
    assert payload["diagnosis"] == "diverges_during_import_normalization"


def test_compare_ball_pipeline_trace_detects_divergence_during_possession_assignment(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    common_prefix = [
        _stage("processVideoPrimary", ball_rows=5, ball_frames=5),
        _stage("processVideoRecovery", ball_rows=2, ball_frames=2),
        _stage("processVideoReturnedRows", ball_rows=7, ball_frames=7),
        _stage("persistRawRows", ball_rows=7, ball_frames=7),
        _stage("normalizedFrames", ball_rows=7, ball_frames=7),
    ]
    _write_trace(storage, "local-match", common_prefix + [
        _stage("possessionOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5),
        _stage("eventOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5, event_count=3, event_types={"pass": 1}),
    ])
    _write_trace(storage, "remote-match", common_prefix + [
        _stage("possessionOutputs", ball_rows=7, ball_frames=7, tracked=0, controlled=0),
        _stage("eventOutputs", ball_rows=7, ball_frames=7, tracked=0, controlled=0, event_count=3, event_types={"pass": 1}),
    ])
    monkeypatch.setattr(
        compare_ball_pipeline_trace,
        "summarize_match_benchmark",
        lambda storage, match_id: type("FakeSummary", (), {"fiveMinuteTruthReady": False})(),
    )

    payload = compare_ball_pipeline_trace.compare_ball_pipeline_trace(
        local_match_id="local-match",
        remote_match_id="remote-match",
        storage_root=tmp_path,
    )

    assert payload["firstDivergingStage"] == "possessionOutputs"
    assert payload["diagnosis"] == "diverges_during_possession_assignment"


def test_compare_ball_pipeline_trace_reports_no_divergence_but_truth_gate_failure(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    stages = [
        _stage("processVideoPrimary", ball_rows=5, ball_frames=5),
        _stage("processVideoRecovery", ball_rows=2, ball_frames=2),
        _stage("processVideoReturnedRows", ball_rows=7, ball_frames=7),
        _stage("persistRawRows", ball_rows=7, ball_frames=7),
        _stage("normalizedFrames", ball_rows=7, ball_frames=7),
        _stage("possessionOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5),
        _stage("eventOutputs", ball_rows=7, ball_frames=7, tracked=6, controlled=5, event_count=3, event_types={"pass": 1}),
    ]
    _write_trace(storage, "local-match", stages)
    _write_trace(storage, "remote-match", stages)
    monkeypatch.setattr(
        compare_ball_pipeline_trace,
        "summarize_match_benchmark",
        lambda storage, match_id: type("FakeSummary", (), {"fiveMinuteTruthReady": False})(),
    )

    payload = compare_ball_pipeline_trace.compare_ball_pipeline_trace(
        local_match_id="local-match",
        remote_match_id="remote-match",
        storage_root=tmp_path,
    )

    assert payload["firstDivergingStage"] is None
    assert payload["diagnosis"] == "no_divergence_but_truth_gates_fail"


def test_compare_ball_pipeline_trace_main_serializes_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        compare_ball_pipeline_trace,
        "compare_ball_pipeline_trace",
        lambda **kwargs: {
            "localMatchId": kwargs["local_match_id"],
            "remoteMatchId": kwargs["remote_match_id"],
            "firstDivergingStage": "persistRawRows",
            "stageComparisons": {"persistRawRows": {"diverged": True}},
            "diagnosis": "diverges_during_import_normalization",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "compare_ball_pipeline_trace.py",
            "--local-match-id",
            "local-match",
            "--remote-match-id",
            "remote-match",
            "--storage-root",
            str(tmp_path),
        ],
    )

    compare_ball_pipeline_trace.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["firstDivergingStage"] == "persistRawRows"
    assert payload["diagnosis"] == "diverges_during_import_normalization"
