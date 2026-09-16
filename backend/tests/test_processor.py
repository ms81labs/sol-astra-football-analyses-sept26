import hashlib
import json
from pathlib import Path

import pytest
import backend.app.processor as processor
from backend.app.analytics import normalize_tracking_rows
from backend.app.processor import (
    _normalize_track_colors,
    _persist_video_outputs,
    _resolve_selected_cluster,
    _prepare_video_outputs,
    persist_remote_video_result,
    process_match,
    reprocess_video_match,
)
from backend.app.schemas import BallOwnership, ColorClusterSummary, DetectedEvent, FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage
from backend.app.runtime_options import ProofRuntimeOptions


@pytest.mark.parametrize("rows", [
    [],
    [{"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "player", "Track_ID": 7, "X": 48, "Y": 34},
     {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "X": 50, "Y": 34}],
    [{"frameId": 2, "timestamp": 0.4}, {"frameId": 0, "timestamp": 0.0}],
])
def test_normalize_tracking_rows_consumes_one_shot_rows(rows):
    class OneShotRows:
        def __iter__(self):
            assert not getattr(self, "consumed", False), "rows iterated twice"
            self.consumed = True
            yield from rows

    frames = normalize_tracking_rows(OneShotRows())
    assert [frame.frameId for frame in frames] == (
        [] if not rows else [2, 0] if "frameId" in rows[0] else [0, 2]
    )
    if rows and "Frame_ID" in rows[0]:
        assert frames[0].ball.x == 50
        assert frames[1].unassignedPlayers[0].id == 7


def test_normalize_tracking_rows_rejects_null_one_shot_row():
    with pytest.raises(TypeError):
        normalize_tracking_rows(iter([None]))


def test_legacy_metadata_failure_preserves_existing_raw_rows(tmp_path):
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="legacy validation", input_mode="video", original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4", config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    storage.save_raw_rows(match.id, [{"existing": True}])
    row = {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "X": 50.0, "Y": 34.0}
    with pytest.raises(ValueError):
        persist_remote_video_result(storage, job.id, {
            "rows": [row],
            "ballPipelineTrace": {"stages": [{"stage": "persistRawRows", "frameCount": "invalid"}]},
        })
    assert storage.load_raw_rows(match.id) == [{"existing": True}]


@pytest.mark.parametrize("selected_cluster", [None, 0, 99])
def test_remote_stream_persists_the_same_rows_and_frames(tmp_path, selected_cluster):
    from backend.app.remote_worker import ProcessorResultStream

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="stream parity", input_mode="video", original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4", config=MatchConfig(myTeamCluster=selected_cluster),
    )
    job = storage.create_job(match.id)
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.95},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 51.0, "Y": 34.0, "Conf": 0.5},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 7, "X": 48.0, "Y": 34.0, "Conf": 0.8},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 8, "X": 90.0, "Y": 34.0, "Conf": 0.8},
        {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "player", "Track_ID": 7, "X": 49.0, "Y": 34.0, "Conf": 0.8},
        {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 34.0, "Conf": 0.9},
    ]
    metadata = {
        "trackColors": {"7": [[220, 20, 20]], "8": [[20, 20, 220]]},
        "runtimeFingerprint": {"gitSha": "abc123"},
        "recoveryDebug": {"profiles": []},
        "recoveryProfileMatrix": {"profileCount": 0},
        "ballTruthLayers": {
            "sampleInterval": 1,
            "observedBall": {"rows": [rows[0]]},
            "inferredBall": {"rows": [rows[-1]]},
        },
    }
    persist_remote_video_result(storage, job.id, {**metadata, "rows": rows})
    match_dir = storage._match_dir(match.id)
    before = {path.name: json.loads(path.read_text()) for path in match_dir.glob("*.json")}

    with storage.remote_result_import(match.id), ProcessorResultStream(metadata, len(rows), iter(rows)) as source:
        processor.persist_remote_video_result_stream(storage, job.id, source)

    assert {path.name: json.loads(path.read_text()) for path in match_dir.glob("*.json")} == before
    assert storage.load_raw_rows(match.id) == rows
    frames = storage.load_frames(match.id)
    assert [frame.frameId for frame in frames] == [0, 1, 2]
    assert frames[0].ball.x == 51.0  # Normalization keeps the final observation.
    players = frames[0].myTeam if selected_cluster == 0 else frames[0].unassignedPlayers
    assert players[0].id == 7
    assert storage.get_match(match.id).requiresTeamSelection == (selected_cluster != 0)
    truth = storage.load_analysis_artifact(match.id, "ball_truth_layers")
    assert truth["acceptedBall"]["rows"][0]["X"] == 50.0  # Truth uses highest confidence.
    stage = next(item for item in before["ball_pipeline_trace.json"]["stages"] if item["stage"] == "persistRawRows")
    assert (stage["ballRowCount"], stage["ballFrameCount"], stage["playerRowCount"], stage["frameCount"]) == (3, 2, 3, 3)


@pytest.mark.parametrize("failure", ["rows", "analytics", "persistence", "empty"])
def test_remote_stream_failure_restores_existing_outputs(tmp_path, monkeypatch, failure):
    from backend.app.remote_worker import ProcessorResultStream

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="stream rollback", input_mode="video", original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4", config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    row = {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.9}
    persist_remote_video_result(storage, job.id, {"rows": [row], "trackColors": {}})
    match_dir = storage._match_dir(match.id)
    before = {path.name: path.read_bytes() for path in match_dir.glob("*.json")}
    before_match = storage.get_match(match.id)

    def fail(*args, **kwargs):
        raise RuntimeError("stream failed")

    def rows():
        if failure == "empty":
            return
        yield {**row, "X": 99.0}
        if failure == "rows":
            fail()

    if failure == "analytics":
        monkeypatch.setattr(processor, "_compute_outputs_and_match_state", fail)
    elif failure == "persistence":
        monkeypatch.setattr(storage, "save_events", fail)
    source = ProcessorResultStream({"trackColors": {}, "recoveryDebug": {"new": True}}, 0 if failure == "empty" else 1, rows())
    with pytest.raises(RuntimeError), storage.remote_result_import(match.id), source:
        processor.persist_remote_video_result_stream(storage, job.id, source)

    assert {path.name: path.read_bytes() for path in match_dir.glob("*.json")} == before
    assert storage.get_match(match.id) == before_match


def test_neutral_remote_persistence_uses_provider_neutral_metadata(monkeypatch, tmp_path):
    class Record:
        pass

    job = Record()
    job.matchId = "match-1"
    match = Record()
    match.id = "match-1"
    match.config = MatchConfig(autoHomography=True)
    video_path = tmp_path / "input.mp4"

    class FakeStorage:
        def get_job(self, job_id):
            assert job_id == "job-1"
            return job

        def get_match(self, match_id):
            assert match_id == "match-1"
            return match

        def get_match_input_path(self, match_id):
            assert match_id == "match-1"
            return video_path

    calls = []
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: calls.append((args, kwargs)))
    payload = {"rows": []}

    persist_remote_video_result(FakeStorage(), "job-1", payload)
    assert len(calls) == 1
    assert calls[0][1] == {
        "processing_backend": "remote",
        "video_path": video_path,
        "worker_path": "gpu_worker",
    }


# === normalize_tracking_rows tests ===

def test_normalize_tracking_rows_empty():
    result = normalize_tracking_rows([])
    assert result == []


def test_normalize_tracking_rows_already_normalized():
    rows = [
        {"frameId": 0, "timestamp": 0.0, "ball": {"x": 50.0, "y": 50.0, "confidence": 0.95}, "myTeam": [], "enemies": []},
        {"frameId": 1, "timestamp": 0.2, "ball": None, "myTeam": [{"id": 7, "x": 30.0, "y": 50.0, "confidence": 0.92}], "enemies": []},
    ]
    result = normalize_tracking_rows(rows)
    assert len(result) == 2
    assert result[0].frameId == 0
    assert result[0].ball is not None and result[0].ball.x == 50.0
    assert result[1].ball is None
    assert result[1].myTeam[0].id == 7


def test_normalize_tracking_rows_groups_by_frame_id():
    rows = [
        {"Frame_ID": 5, "Timestamp": 1.0, "Entity_Type": "ball", "X": 50.0, "Y": 50.0, "Conf": 0.95},
        {"Frame_ID": 5, "Timestamp": 1.0, "Entity_Type": "my_team", "Track_ID": 7, "X": 30.0, "Y": 50.0, "Conf": 0.92},
        {"Frame_ID": 5, "Timestamp": 1.0, "Entity_Type": "enemy", "Track_ID": 11, "X": 70.0, "Y": 50.0, "Conf": 0.90},
        {"Frame_ID": 6, "Timestamp": 1.2, "Entity_Type": "my_team", "Track_ID": 7, "X": 31.0, "Y": 51.0, "Conf": 0.88},
    ]
    result = normalize_tracking_rows(rows)
    assert len(result) == 2
    frame_5 = result[0]
    assert frame_5.frameId == 5
    assert frame_5.timestamp == 1.0
    assert frame_5.ball is not None and frame_5.ball.x == 50.0
    assert len(frame_5.myTeam) == 1 and frame_5.myTeam[0].id == 7
    assert len(frame_5.enemies) == 1 and frame_5.enemies[0].id == 11
    frame_6 = result[1]
    assert frame_6.frameId == 6
    assert frame_6.timestamp == 1.2
    assert frame_6.ball is None
    assert len(frame_6.myTeam) == 1


def test_normalize_tracking_rows_missing_conf_defaults_to_zero():
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 1, "X": 10.0, "Y": 20.0},
    ]
    result = normalize_tracking_rows(rows)
    assert result[0].myTeam[0].confidence == 0.0


def test_normalize_tracking_rows_non_numeric_x_raises():
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 1, "X": "not_a_number", "Y": 20.0},
    ]
    with pytest.raises(ValueError):
        normalize_tracking_rows(rows)


def test_normalize_tracking_rows_multiple_players_per_frame():
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 1, "X": 10.0, "Y": 20.0},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 2, "X": 15.0, "Y": 25.0},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "enemy", "Track_ID": 3, "X": 80.0, "Y": 30.0},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "X": 50.0, "Y": 50.0},
    ]
    result = normalize_tracking_rows(rows)
    assert len(result[0].myTeam) == 2
    assert len(result[0].enemies) == 1
    assert result[0].ball is not None


def test_normalize_tracking_rows_keeps_unresolved_players_visible():
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 40.0, "Y": 50.0, "Conf": 0.81},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0, "Conf": 0.77},
    ]
    result = normalize_tracking_rows(rows)
    assert len(result) == 1
    assert [player.id for player in result[0].unassignedPlayers] == [4, 12]


# === _normalize_track_colors tests ===

def test_normalize_track_colors_valid():
    colors = {
        1: [[34, 86, 220], [38, 90, 225]],
        2: [[215, 42, 54], [208, 38, 44]],
    }
    result = _normalize_track_colors(colors)
    assert 1 in result and len(result[1]) == 2
    assert 2 in result and len(result[2]) == 2
    assert result[1][0] == (34.0, 86.0, 220.0)


def test_normalize_track_colors_empty_dict():
    result = _normalize_track_colors({})
    assert result == {}


def test_normalize_track_colors_non_dict_returns_empty():
    result = _normalize_track_colors("not a dict")
    assert result == {}


def test_normalize_track_colors_skips_non_list_samples():
    colors = {
        1: "not a list",
        2: [[34, 86, 220]],
        3: [1, 2],  # wrong length, skipped
    }
    result = _normalize_track_colors(colors)
    assert 1 not in result
    assert 2 in result
    assert 3 not in result


# === _resolve_selected_cluster tests ===

def test_resolve_selected_cluster_empty():
    cluster, requires = _resolve_selected_cluster(MatchConfig(), [])
    assert cluster is None
    assert requires is False


def test_resolve_selected_cluster_no_my_team_cluster():
    cluster, requires = _resolve_selected_cluster(
        MatchConfig(),
        [ColorClusterSummary(clusterId=3, rgbCentroid=[100.0, 100.0, 100.0], trackIds=[1, 2])],
    )
    assert cluster is None
    assert requires is True


def test_resolve_selected_cluster_with_my_team_cluster():
    cluster, requires = _resolve_selected_cluster(
        MatchConfig(myTeamCluster=5),
        [ColorClusterSummary(clusterId=3, rgbCentroid=[100.0, 100.0, 100.0], trackIds=[1, 2])],
    )
    assert cluster is None
    assert requires is True


def test_resolve_selected_cluster_with_valid_my_team_cluster():
    cluster, requires = _resolve_selected_cluster(
        MatchConfig(myTeamCluster=5),
        [ColorClusterSummary(clusterId=5, rgbCentroid=[100.0, 100.0, 100.0], trackIds=[1, 2])],
    )
    assert cluster == 5
    assert requires is False


# === _prepare_video_outputs tests ===

def test_prepare_video_outputs_already_normalized_frames():
    frames = [
        {"frameId": 0, "timestamp": 0.0, "ball": {"x": 50.0, "y": 50.0, "confidence": 0.95}, "myTeam": [], "enemies": []},
    ]
    result_frames, result_clusters, result_requires, result_raw = _prepare_video_outputs(frames, MatchConfig())
    assert len(result_frames) == 1
    assert result_frames[0].frameId == 0
    assert result_clusters == []
    assert result_requires is False
    assert result_raw is None


def test_prepare_video_outputs_raw_rows_normalized():
    raw_rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 7, "X": 30.0, "Y": 50.0},
        {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "my_team", "Track_ID": 7, "X": 31.0, "Y": 50.0},
    ]
    result_frames, result_clusters, result_requires, result_raw = _prepare_video_outputs(raw_rows, MatchConfig())
    assert len(result_frames) == 2
    assert result_clusters == []
    assert result_requires is False
    assert result_raw is not None and len(result_raw) == 2


def test_prepare_video_outputs_keeps_players_unassigned_until_team_selected():
    config = MatchConfig()
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 40.0, "Y": 50.0},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0},
        ],
        "trackColors": {
            "4": [[20, 90, 220]],
            "12": [[220, 50, 60]],
        },
    }

    frames, clusters, requires_team_selection, _raw = _prepare_video_outputs(video_result, config)

    assert requires_team_selection is True
    assert len(clusters) == 2
    assert frames[0].myTeam == []
    assert frames[0].enemies == []
    assert [player.id for player in frames[0].unassignedPlayers] == [4, 12]


def test_prepare_video_outputs_with_invalid_team_cluster_stays_unresolved():
    config = MatchConfig(myTeamCluster=99)
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 40.0, "Y": 50.0},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0},
        ],
        "trackColors": {
            "4": [[20, 90, 220]],
            "12": [[220, 50, 60]],
        },
    }

    frames, clusters, requires_team_selection, _raw = _prepare_video_outputs(video_result, config)

    assert requires_team_selection is True
    assert len(clusters) == 2
    assert frames[0].myTeam == []
    assert frames[0].enemies == []
    assert [player.id for player in frames[0].unassignedPlayers] == [4, 12]


def test_prepare_video_outputs_empty_list_raises():
    with pytest.raises(RuntimeError, match="did not return any tracking rows"):
        _prepare_video_outputs([], MatchConfig())


def test_prepare_video_outputs_dict_without_rows_raises():
    with pytest.raises(RuntimeError, match="unsupported payload"):
        _prepare_video_outputs({"status": "ok"}, MatchConfig())


def test_prepare_video_outputs_dict_with_empty_rows_raises():
    with pytest.raises(RuntimeError, match="did not return any tracking rows"):
        _prepare_video_outputs({"rows": []}, MatchConfig())


def test_persist_video_outputs_saves_ball_pipeline_trace(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="trace match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
        ],
        "trackColors": {},
        "sourceClock": {"sourceSha256": "a" * 64, "byteSize": 5, "codec": "h264"},
        "runtimeFingerprint": {
            "configuredImageName": "ghcr.io/example/fotball-analyst-runpod-handler:abc123",
            "imageTag": "abc123",
            "gitSha": "deadbeef",
            "buildLabel": "deadbeef",
            "handlerDependencyVersions": {
                "python": "3.12.2",
                "opencv": "4.13.0-test",
                "ultralytics": "8.4.14-test",
            },
        },
        "ballPipelineTrace": {
            "traceVersion": 1,
            "primaryModelPath": "/workspace/weights/yolov10n.pt",
            "primaryModelName": "yolov10n.pt",
            "auxiliaryBallModelPath": "/workspace/weights/touchline-best.pt",
            "auxiliaryBallModelName": "touchline-best.pt",
            "auxiliaryBallModelProfile": "ball_probe_only_v1",
            "trackingModelPath": "/workspace/weights/yolov10n.pt",
            "trackingDetectorProfile": "coco_tracking_full",
            "probeModelPath": "/workspace/weights/touchline-best.pt",
            "probeDetectorProfile": "ball_probe_only_v1",
            "recoveryModelPath": "/workspace/weights/touchline-best.pt",
            "recoveryDetectorProfile": "ball_probe_only_v1",
            "stages": [
                {
                    "stage": "processVideoPrimary",
                    "ballRowCount": 1,
                    "ballFrameCount": 1,
                    "playerRowCount": 1,
                    "frameCount": 1,
                    "trackedPossessionFrames": 0,
                    "controlledPossessionFrames": 0,
                    "eventCount": 0,
                    "eventTypes": {},
                    "firstBallFrame": 0,
                    "lastBallFrame": 0,
                },
                {
                    "stage": "processVideoRecovery",
                    "ballRowCount": 0,
                    "ballFrameCount": 0,
                    "playerRowCount": 0,
                    "frameCount": 0,
                    "trackedPossessionFrames": 0,
                    "controlledPossessionFrames": 0,
                    "eventCount": 0,
                    "eventTypes": {},
                    "firstBallFrame": None,
                    "lastBallFrame": None,
                },
                {
                    "stage": "processVideoReturnedRows",
                    "ballRowCount": 1,
                    "ballFrameCount": 1,
                    "playerRowCount": 1,
                    "frameCount": 1,
                    "trackedPossessionFrames": 0,
                    "controlledPossessionFrames": 0,
                    "eventCount": 0,
                    "eventTypes": {},
                    "firstBallFrame": 0,
                    "lastBallFrame": 0,
                },
            ],
        },
    }
    normalized_frames = [
        FrameData(
            frameId=0,
            timestamp=0.0,
            ball={"x": 52.0, "y": 50.0, "confidence": 0.95},
            myTeam=[{"id": 4, "x": 51.0, "y": 50.0, "confidence": 0.9}],
        )
    ]
    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda frames, **_kwargs: (
            normalized_frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")],
            [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=4, distance=1.0)],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        video_result,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    trace = storage.load_analysis_artifact(match.id, "ball_pipeline_trace")
    assert trace["matchId"] == match.id
    assert trace["jobId"] == job.id
    assert trace["processingBackend"] == "local"
    assert trace["workerPath"] == "local"
    assert trace["runtimeFingerprint"] == {
        "configuredImageName": "ghcr.io/example/fotball-analyst-runpod-handler:abc123",
        "imageTag": "abc123",
        "gitSha": "deadbeef",
        "buildLabel": "deadbeef",
        "handlerDependencyVersions": {
            "python": "3.12.2",
            "opencv": "4.13.0-test",
            "ultralytics": "8.4.14-test",
        },
    }
    assert trace["primaryModelPath"] == "/workspace/weights/yolov10n.pt"
    assert trace["primaryModelName"] == "yolov10n.pt"
    assert trace["auxiliaryBallModelPath"] == "/workspace/weights/touchline-best.pt"
    assert trace["auxiliaryBallModelName"] == "touchline-best.pt"
    assert trace["auxiliaryBallModelProfile"] == "ball_probe_only_v1"
    assert trace["trackingModelPath"] == "/workspace/weights/yolov10n.pt"
    assert trace["trackingDetectorProfile"] == "coco_tracking_full"
    assert trace["probeModelPath"] == "/workspace/weights/touchline-best.pt"
    assert trace["probeDetectorProfile"] == "ball_probe_only_v1"
    assert trace["recoveryModelPath"] == "/workspace/weights/touchline-best.pt"
    assert trace["recoveryDetectorProfile"] == "ball_probe_only_v1"
    assert [stage["stage"] for stage in trace["stages"]] == [
        "processVideoPrimary",
        "processVideoRecovery",
        "processVideoReturnedRows",
        "persistRawRows",
        "normalizedFrames",
        "possessionOutputs",
        "eventOutputs",
    ]
    persist_stage = next(stage for stage in trace["stages"] if stage["stage"] == "persistRawRows")
    normalized_stage = next(stage for stage in trace["stages"] if stage["stage"] == "normalizedFrames")
    possession_stage = next(stage for stage in trace["stages"] if stage["stage"] == "possessionOutputs")
    event_stage = next(stage for stage in trace["stages"] if stage["stage"] == "eventOutputs")
    assert persist_stage["ballRowCount"] == 1
    assert normalized_stage["ballFrameCount"] == 1
    assert possession_stage["trackedPossessionFrames"] == 1
    assert possession_stage["controlledPossessionFrames"] == 1
    assert event_stage["eventCount"] == 1
    assert event_stage["eventTypes"] == {"recovery": 1}
    assert storage.load_analysis_artifact(match.id, "source_clock")["codec"] == "h264"


def test_persist_video_outputs_saves_phase_timings_and_recovery_debug(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="phase timing match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
        ],
        "trackColors": {},
        "recoveryDebug": {
            "phaseTimings": {
                "trackingPassSeconds": 12.5,
                "recoverySelectionSeconds": 48.25,
                "totalProcessVideoSeconds": 77.0,
            },
            "profileTimings": [
                {
                    "name": "proposal_windows_075",
                    "elapsedSeconds": 48.25,
                    "candidateRows": 14,
                    "selectedFrames": 5,
                    "directSeedRetryPolicy": "bounded_multiscale_fallback",
                    "directSeedRetryScales": [1600, 960, 1920],
                }
            ],
        },
        "ballPipelineTrace": {
            "traceVersion": 1,
            "phaseTimings": {
                "trackingPassSeconds": 12.5,
                "recoverySelectionSeconds": 48.25,
                "totalProcessVideoSeconds": 77.0,
            },
            "stages": [],
        },
    }
    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda frames, **_kwargs: (
            frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        video_result,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    trace = storage.load_analysis_artifact(match.id, "ball_pipeline_trace")
    recovery_debug = storage.load_analysis_artifact(match.id, "recovery_debug")
    assert trace["phaseTimings"]["trackingPassSeconds"] == 12.5
    assert trace["phaseTimings"]["recoverySelectionSeconds"] == 48.25
    assert trace["phaseTimings"]["totalProcessVideoSeconds"] == 77.0
    assert recovery_debug["phaseTimings"]["trackingPassSeconds"] == 12.5
    assert recovery_debug["phaseTimings"]["recoverySelectionSeconds"] == 48.25
    assert recovery_debug["profileTimings"][0]["name"] == "proposal_windows_075"
    assert recovery_debug["profileTimings"][0]["elapsedSeconds"] == 48.25


def test_process_match_video_job_persists_worker_progress_and_updates_job_message(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"video")
    match = storage.create_match(
        name="worker progress match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=clip_path,
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)

    def fake_process_video_input(
        video_path,
        config,
        *,
        model_path=None,
        primary_model_path=None,
        auxiliary_ball_model_path=None,
        auxiliary_ball_model_profile=None,
        edge_share_repair_profile=None,
        progress_callback=None,
        match_id=None,
        job_id=None,
    ):
        assert isinstance(model_path, str)
        assert primary_model_path in {None, model_path}
        assert auxiliary_ball_model_path is None
        assert auxiliary_ball_model_profile is None
        assert edge_share_repair_profile is None
        assert progress_callback is not None
        assert match_id == match.id
        assert job_id == job.id
        progress_callback(
            {
                "matchId": match.id,
                "jobId": job.id,
                "workerStage": "trackingPass",
                "stageStatus": "started",
                "heartbeatAt": "2026-04-14T22:20:00+00:00",
                "trackingFramesSeen": 250,
            }
        )
        progress_callback(
            {
                "matchId": match.id,
                "jobId": job.id,
                "workerStage": "recoverySelection",
                "stageStatus": "started",
                "heartbeatAt": "2026-04-14T22:20:35+00:00",
                "trackingFramesSeen": 7580,
            }
        )
        return {"rows": [{"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 1, "X": 1.0, "Y": 1.0, "Conf": 0.8}]}

    monkeypatch.setattr(processor, "process_video_input", fake_process_video_input)
    monkeypatch.setattr(
        processor,
        "materialize_proof_runtime_options",
        lambda options, **kwargs: {
            "model_path": "verified-primary.pt",
            "primary_model_path": "verified-primary.pt",
            "auxiliary_ball_model_profile": None,
            "edge_share_repair_profile": None,
        },
    )
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: None)

    process_match(storage, job.id)

    updated_job = storage.get_job(job.id)
    worker_progress = storage.load_analysis_artifact(match.id, "worker_progress")
    assert updated_job.status == "processing"
    assert updated_job.message == "Running recovery profiles"
    assert updated_job.progress == pytest.approx(0.75)
    assert worker_progress["workerStage"] == "recoverySelection"
    assert worker_progress["stageStatus"] == "started"
    assert worker_progress["trackingFramesSeen"] == 7580


def test_process_match_materializes_typed_runtime_options_only_at_pipeline_boundary(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"video")
    match = storage.create_match(
        name="portable local runtime",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=clip_path,
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    options = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {"artifactId": "primary-model"},
            "auxiliary_ball_model": {"artifactId": "auxiliary-model"},
            "auxiliary_ball_model_profile": "aux-profile",
            "primary_acquisition_mode": "acquisition-v2",
            "edge_share_repair_profile": "repair-v2",
            "baseline_guided_rescue_reference": {"artifactId": "baseline-reference"},
            "proposal_selection_truth_seed": {"artifactId": "proposal-seed"},
            "reviewed_positive_anchor_seed": {"artifactId": "anchor-seed"},
        }
    )
    materialized = {
        "model_path": str(tmp_path / "resolved/primary.pt"),
        "primary_model_path": str(tmp_path / "resolved/primary.pt"),
        "auxiliary_ball_model_path": str(tmp_path / "resolved/auxiliary.pt"),
        "auxiliary_ball_model_profile": "aux-profile",
        "edge_share_repair_profile": "repair-v2",
        "baseline_guided_rescue_reference_path": str(tmp_path / "resolved/baseline.json"),
        "proposal_selection_truth_seed_path": str(tmp_path / "resolved/proposal.json"),
        "reviewed_positive_anchor_seed_path": str(tmp_path / "resolved/anchor.json"),
    }
    materialize_calls = []
    captured = {}
    monkeypatch.setattr(processor, "load_proof_runtime_options", lambda *_args, **_kwargs: options)

    def fake_materialize(value, **kwargs):  # noqa: ANN001
        materialize_calls.append((value, kwargs))
        return materialized

    monkeypatch.setattr(processor, "materialize_proof_runtime_options", fake_materialize)

    def fake_process_video_input(video_path, config, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        return {"rows": [{"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 1, "X": 1.0, "Y": 1.0, "Conf": 0.8}]}

    monkeypatch.setattr(processor, "process_video_input", fake_process_video_input)
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: None)

    process_match(storage, job.id)

    assert materialize_calls == [
        (
            options,
            {
                "storage_root": tmp_path,
                "environment": "local",
                "manifest_path": processor.RUNTIME_MANIFEST_PATH,
                "resolver_root": processor.RUNTIME_ARTIFACT_ROOT,
                "object_loader": processor.local_boto3_object_loader,
            },
        )
    ]
    assert {key: captured[key] for key in materialized} == materialized


def test_process_match_streams_allowed_object_store_reference_through_local_boto3_boundary(
    tmp_path,
    monkeypatch,
):
    storage = Storage(tmp_path / "storage")
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"video")
    match = storage.create_match(
        name="portable local object runtime",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=clip_path,
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    primary_content = b"primary-model"
    baseline_content = b"baseline-reference"
    baseline_digest = hashlib.sha256(baseline_content).hexdigest()
    options = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {"artifactId": "primary-model"},
            "auxiliary_ball_model": None,
            "auxiliary_ball_model_profile": None,
            "primary_acquisition_mode": "anchored_player_ranked_context_960",
            "edge_share_repair_profile": "repair-v2",
            "baseline_guided_rescue_reference": {
                "objectStore": {
                    "bucket": "release-inputs",
                    "key": "v7.3/baseline.json",
                    "endpointUrl": "https://objects.example.test",
                    "region": "eu-test-1",
                    "sha256": baseline_digest,
                    "sizeBytes": len(baseline_content),
                }
            },
            "proposal_selection_truth_seed": None,
            "reviewed_positive_anchor_seed": None,
        }
    )
    storage.save_analysis_artifact(match.id, "proof_runtime_options", options.to_mapping())
    artifact_root = tmp_path / "artifact-root"
    primary_path = artifact_root / "release-assets/models/primary.pt"
    primary_path.parent.mkdir(parents=True)
    primary_path.write_bytes(primary_content)
    manifest_path = tmp_path / "v7.3.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "releaseVersion": "v7.3",
                "candidateVersion": "v7.3",
                "runtimeVersion": "v7.3",
                "sourceCommit": "a" * 40,
                "createdAt": "2026-08-22T12:34:56Z",
                "runtimeOptions": options.to_mapping(),
                "artifacts": [
                    {
                        "id": "primary-model",
                        "sha256": hashlib.sha256(primary_content).hexdigest(),
                        "sizeBytes": len(primary_content),
                        "localRelativePath": "release-assets/models/primary.pt",
                        "containerPath": "/app/models/primary.pt",
                        "origin": "test-fixture",
                        "retentionClass": "release-essential",
                    }
                ],
                "requiredContracts": [
                    "video_to_analysis_product_api_v1",
                    "video_to_analysis_report_v1",
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(processor, "RUNTIME_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(processor, "RUNTIME_ARTIFACT_ROOT", artifact_root.resolve())
    monkeypatch.setenv("PROOF_RUNTIME_OBJECT_STORE_ALLOWED_ORIGINS", "https://objects.example.test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    read_sizes: list[int] = []

    class FakeBody:
        def __init__(self):
            self.chunks = [b"baseline-", b"reference", b""]

        def read(self, size):  # noqa: ANN001, ANN201
            read_sizes.append(size)
            return self.chunks.pop(0)

        def close(self):
            return None

    class FakeClient:
        def get_object(self, *, Bucket, Key):  # noqa: N803, ANN001, ANN201
            assert Bucket == "release-inputs"
            assert Key == "v7.3/baseline.json"
            return {"Body": FakeBody()}

    def fake_boto3_client(service_name, **kwargs):  # noqa: ANN001
        assert service_name == "s3"
        assert kwargs["endpoint_url"] == "https://objects.example.test"
        assert kwargs["region_name"] == "eu-test-1"
        assert kwargs["aws_access_key_id"] == "test-access"
        assert kwargs["aws_secret_access_key"] == "test-secret"
        return FakeClient()

    monkeypatch.setattr("backend.app.proof_runtime.boto3.client", fake_boto3_client)
    captured = {}

    def fake_process_video_input(video_path, config, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        assert Path(kwargs["model_path"]).read_bytes() == primary_content
        assert Path(kwargs["baseline_guided_rescue_reference_path"]).read_bytes() == baseline_content
        return {
            "rows": [
                {
                    "Frame_ID": 0,
                    "Timestamp": 0.0,
                    "Entity_Type": "player",
                    "Track_ID": 1,
                    "X": 1.0,
                    "Y": 1.0,
                    "Conf": 0.8,
                }
            ]
        }

    monkeypatch.setattr(processor, "process_video_input", fake_process_video_input)
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: None)

    process_match(storage, job.id)

    assert read_sizes == [1024 * 1024, 1024 * 1024, 1024 * 1024]
    assert captured["edge_share_repair_profile"] == "repair-v2"


def test_process_match_video_job_ignores_historical_runtime_registry_when_match_has_no_override(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    weights_path = tmp_path / "weights" / "v7_2_best.pt"
    weights_path.parent.mkdir(parents=True)
    weights_path.write_bytes(b"weights")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "promoted_touchline_detector_candidate.json").write_text(
        """
        {
          "runtimeDefaultMutationExecuted": true,
          "runtimeDefaultProfileName": "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1",
          "runtimeContract": {
            "primaryDetectorModelPath": "yolov10n.pt",
            "auxiliaryBallModelPath": "auxiliary-model",
            "auxiliaryBallModelProfile": "ball_probe_only_v7_2_crop_256"
          }
        }
        """,
        encoding="utf-8",
    )
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"video")
    match = storage.create_match(
        name="registry default match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=clip_path,
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)

    captured = {}

    def fake_materialize(options, **kwargs):  # noqa: ANN001
        assert options == ProofRuntimeOptions.defaults()
        return {
            "model_path": "verified-primary.pt",
            "primary_model_path": "verified-primary.pt",
            "auxiliary_ball_model_profile": options.auxiliary_ball_model_profile,
            "edge_share_repair_profile": options.edge_share_repair_profile,
        }

    def fake_process_video_input(
        video_path,
        config,
        *,
        model_path=None,
        primary_model_path=None,
        auxiliary_ball_model_path=None,
        auxiliary_ball_model_profile=None,
        edge_share_repair_profile=None,
        progress_callback=None,
        match_id=None,
        job_id=None,
    ):
        captured.update(
            {
                "model_path": model_path,
                "primary_model_path": primary_model_path,
                "auxiliary_ball_model_path": auxiliary_ball_model_path,
                "auxiliary_ball_model_profile": auxiliary_ball_model_profile,
                "edge_share_repair_profile": edge_share_repair_profile,
                "match_id": match_id,
                "job_id": job_id,
            }
        )
        return {"rows": [{"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 1, "X": 1.0, "Y": 1.0, "Conf": 0.8}]}

    monkeypatch.setattr(processor, "process_video_input", fake_process_video_input)
    monkeypatch.setattr(processor, "materialize_proof_runtime_options", fake_materialize)
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: None)

    process_match(storage, job.id)

    assert captured["model_path"] == "verified-primary.pt"
    assert captured["primary_model_path"] == "verified-primary.pt"
    assert captured["auxiliary_ball_model_path"] is None
    assert captured["auxiliary_ball_model_profile"] is None
    assert captured["edge_share_repair_profile"] is None
    assert captured["match_id"] == match.id
    assert captured["job_id"] == job.id


def test_process_match_persists_worker_progress_history(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="video history heartbeat",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")

    def fake_process_video_input(
        input_path,
        config,
        *,
        model_path=None,
        primary_model_path=None,
        auxiliary_ball_model_path=None,
        auxiliary_ball_model_profile=None,
        edge_share_repair_profile=None,
        progress_callback=None,
        match_id=None,
        job_id=None,
    ):
        assert isinstance(model_path, str)
        assert primary_model_path in {None, model_path}
        assert auxiliary_ball_model_path is None
        assert auxiliary_ball_model_profile is None
        assert edge_share_repair_profile is None
        assert progress_callback is not None
        assert match_id == match.id
        assert job_id == job.id
        progress_callback(
            {
                "matchId": match.id,
                "jobId": job.id,
                "workerStage": "trackingPass",
                "stageStatus": "started",
                "heartbeatAt": "2026-04-15T07:00:00+00:00",
                "trackingFramesSeen": 250,
            }
        )
        progress_callback(
            {
                "matchId": match.id,
                "jobId": job.id,
                "workerStage": "recoverySelection",
                "stageStatus": "profile_started",
                "heartbeatAt": "2026-04-15T07:00:30+00:00",
                "recoveryProfileName": "proposal_windows_075",
                "recoveryProfileIndex": 8,
                "recoveryProfileCount": 9,
            }
        )
        progress_callback(
            {
                "matchId": match.id,
                "jobId": job.id,
                "workerStage": "recoverySelection",
                "stageStatus": "profile_completed",
                "heartbeatAt": "2026-04-15T07:00:42+00:00",
                "recoveryProfileName": "proposal_windows_075",
                "recoveryProfileIndex": 8,
                "recoveryProfileCount": 9,
                "recoveryProfileElapsedSeconds": 12.5,
                "recoveryProfileSelectedFrames": 10,
                "recoveryProfileAnchoredFrameCount": 10,
                "recoveryProfileSupportedFrameShare": 0.5,
                "recoveryProfileAnchoredFrameShare": 0.25,
                "recoveryProfileAnchoredPathLength": 8.0,
                "recoveryProfileUnsupportedEdgeFrameShare": 0.1,
                "recoveryProfileBridgeFrameCount": 2,
                "recoveryProfileSelectedScore": 123.4,
            }
        )
        return {
            "rows": [
                {
                    "Frame_ID": 0,
                    "Timestamp": 0.0,
                    "Entity_Type": "player",
                    "Track_ID": 1,
                    "X": 1.0,
                    "Y": 1.0,
                    "Conf": 0.8,
                }
            ]
        }

    monkeypatch.setattr(processor, "process_video_input", fake_process_video_input)
    monkeypatch.setattr(
        processor,
        "materialize_proof_runtime_options",
        lambda options, **kwargs: {
            "model_path": "verified-primary.pt",
            "primary_model_path": "verified-primary.pt",
            "auxiliary_ball_model_profile": None,
            "edge_share_repair_profile": None,
        },
    )
    monkeypatch.setattr(processor, "_persist_video_outputs", lambda *args, **kwargs: None)

    process_match(storage, job.id)

    worker_progress = storage.load_analysis_artifact(match.id, "worker_progress")
    history_path = storage._match_dir(match.id) / "worker_progress_history.jsonl"
    assert worker_progress["workerStage"] == "recoverySelection"
    assert worker_progress["stageStatus"] == "profile_completed"
    history_lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 3
    tracking_payload, started_payload, completed_payload = [processor.json.loads(line) for line in history_lines]
    assert tracking_payload["workerStage"] == "trackingPass"
    assert started_payload["stageStatus"] == "profile_started"
    assert completed_payload["stageStatus"] == "profile_completed"
    assert completed_payload["recoveryProfileName"] == "proposal_windows_075"
    assert completed_payload["recoveryProfileSelectedScore"] == pytest.approx(123.4)
    assert completed_payload["jobMessage"] == "Running recovery profiles"


def test_persist_video_outputs_saves_ball_truth_layers(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="truth layers match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
        ],
        "trackColors": {},
        "recoveryProfileMatrix": {
            "selectedProfileName": "proposal_windows_075",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "cropMode": "proposal_windows",
                    "viable": True,
                    "candidateFrames": 11,
                    "selectedFrames": 4,
                    "candidateSegmentCount": 2,
                    "selectedSegmentCount": 1,
                    "corridorCandidateFrames": 0,
                    "corridorFramesWithTwoAnchors": 0,
                    "corridorFramesWithSingleAnchor": 0,
                    "corridorMeanWidth": 0.0,
                    "proposalCandidateFrames": 11,
                    "proposalWindowCount": 4,
                    "proposalFramesWithAnchorSeed": 7,
                    "proposalFramesWithoutAnchorSeed": 4,
                    "proposalExactSeedFrames": 2,
                    "proposalInterpolatedSeedFrames": 3,
                    "proposalSingleSeedFrames": 2,
                    "proposalUnseededFrames": 4,
                    "proposalMeanWindowWidth": 13.5,
                }
            ],
        },
        "ballTruthLayers": {
            "observedBall": {
                "rows": [{"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95}],
                "summary": {
                    "rowCount": 1,
                    "frameCount": 1,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 0,
                },
            },
            "inferredBall": {
                "rows": [],
                "summary": {
                    "rowCount": 0,
                    "frameCount": 0,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 0,
                    "firstFrame": None,
                    "lastFrame": None,
                },
            },
            "acceptedBall": {
                "rows": [{"Frame_ID": 99, "Entity_Type": "ball", "Track_ID": -1, "X": 1.0, "Y": 1.0, "Conf": 0.01}],
                "summary": {
                    "rowCount": 1,
                    "frameCount": 1,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 99,
                    "lastFrame": 99,
                },
            },
            "acceptedSegments": [
                {"startFrame": 99, "endFrame": 99, "frameCount": 1, "source": "inferred"},
            ],
            "unknownGaps": [
                {"startFrame": 1, "endFrame": 98, "frameCount": 98},
            ],
            "acceptedSourceBreakdown": {"observed": 1, "inferred": 0},
        },
        "runtimeFingerprint": {
            "configuredImageName": "ghcr.io/example/fotball-analyst-runpod-handler:abc123",
            "imageTag": "abc123",
            "gitSha": "deadbeef",
            "buildLabel": "deadbeef",
            "handlerDependencyVersions": {
                "python": "3.12.2",
                "opencv": "4.13.0-test",
                "ultralytics": "8.4.14-test",
            },
        },
        "ballPipelineTrace": {
            "traceVersion": 1,
            "stages": [],
        },
    }
    normalized_frames = [
        FrameData(
            frameId=0,
            timestamp=0.0,
            ball={"x": 52.0, "y": 50.0, "confidence": 0.95},
            myTeam=[{"id": 4, "x": 51.0, "y": 50.0, "confidence": 0.9}],
        )
    ]
    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda frames, **_kwargs: (
            normalized_frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")],
            [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=4, distance=1.0)],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        video_result,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    truth_layers = storage.load_analysis_artifact(match.id, "ball_truth_layers")
    assert truth_layers != video_result["ballTruthLayers"]
    assert truth_layers["acceptedBall"]["rows"] == [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95}
    ]
    assert truth_layers["acceptedBall"]["summary"]["frameCount"] == 1
    assert truth_layers["acceptedSegments"] == [
        {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
    ]
    assert truth_layers["unknownGaps"] == []
    assert truth_layers["acceptedSourceBreakdown"] == {"observed": 1, "inferred": 0}
    assert truth_layers["directObservationBreakdown"] == {
        "trackingObservedBallFrames": 1,
        "probeObservedBallFrames": 0,
        "probeOnlyObservedBallFrames": 0,
        "acceptedFromObservedFrames": 1,
        "acceptedFromObservedRatio": 1.0,
    }
    profile_matrix = storage.load_analysis_artifact(match.id, "recovery_profile_matrix")
    assert profile_matrix["selectedProfileName"] == "proposal_windows_075"
    assert profile_matrix["profiles"][0]["proposalInterpolatedSeedFrames"] == 3
    assert profile_matrix["profiles"][0]["proposalUnseededFrames"] == 4


def test_persist_video_outputs_saves_accepted_match_state_and_applies_hidden_continuity(tmp_path):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="accepted match state match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")

    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 7, "X": 19.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95},
            {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "my_team", "Track_ID": 7, "X": 21.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "my_team", "Track_ID": 7, "X": 21.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80},
        ],
        "trackColors": {},
        "ballTruthLayers": {
            "sampleInterval": 1,
            "observedBall": {
                "rows": [{"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95}],
                "summary": {"rowCount": 1, "frameCount": 1, "pathLength": 0.0, "edgeFrameShare": 0.0, "segmentCount": 1, "firstFrame": 0, "lastFrame": 0},
            },
            "inferredBall": {
                "rows": [{"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80}],
                "summary": {"rowCount": 1, "frameCount": 1, "pathLength": 0.0, "edgeFrameShare": 0.0, "segmentCount": 1, "firstFrame": 2, "lastFrame": 2},
            },
            "acceptedBall": {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95},
                    {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80},
                ],
                "summary": {"rowCount": 2, "frameCount": 2, "pathLength": 2.0, "edgeFrameShare": 0.0, "segmentCount": 2, "firstFrame": 0, "lastFrame": 2},
            },
            "acceptedSegments": [
                {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
                {"startFrame": 2, "endFrame": 2, "frameCount": 1, "source": "inferred"},
            ],
            "unknownGaps": [{"startFrame": 1, "endFrame": 1, "frameCount": 1}],
            "acceptedSourceBreakdown": {"observed": 1, "inferred": 1},
            "supportDiagnostics": {
                "supportedObservedBallFrames": 1,
                "supportedAcceptedBallFrames": 2,
                "supportedAcceptedBallRatio": 1.0,
                "unsupportedAcceptedEdgeFrames": 0,
            },
        },
        "matchStateEvidence": {
            "frames": [
                {"frameId": 0, "hasAcceptedBall": True, "acceptedSource": "observed", "playerSupported": True, "edgeHeavy": False, "reasonCodes": ["accepted_ball", "observed_ball"]},
                {"frameId": 1, "hasAcceptedBall": False, "acceptedSource": "none", "playerSupported": False, "edgeHeavy": False, "reasonCodes": ["no_accepted_ball"]},
                {"frameId": 2, "hasAcceptedBall": True, "acceptedSource": "inferred", "playerSupported": True, "edgeHeavy": False, "reasonCodes": ["accepted_ball", "inferred_ball"]},
            ],
        },
    }

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        video_result,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    accepted_match_state = storage.load_analysis_artifact(match.id, "accepted_match_state")
    assert accepted_match_state["stateContinuityAppliedFrames"] == 1
    assert [frame["mode"] for frame in accepted_match_state["frames"]] == [
        "controlled_possession",
        "controlled_possession",
        "controlled_possession",
    ]
    assert accepted_match_state["frames"][0]["source"] == "observed_ball"
    assert accepted_match_state["frames"][1]["source"] == "player_conditioned"
    assert accepted_match_state["frames"][1]["ballVisibility"] == "hidden"
    assert accepted_match_state["frames"][2]["source"] == "inferred_ball"
    _, assignments, _, _ = storage.load_analytics(match.id)
    assert [assignment.team for assignment in assignments] == ["my_team", "my_team", "my_team"]
    assert [assignment.trackId for assignment in assignments] == [7, 7, 7]


def test_reprocess_video_match_rebuilds_accepted_match_state_from_saved_truth_layers(tmp_path):
    storage = Storage(tmp_path)
    config = MatchConfig()
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"video")
    match = storage.create_match(
        name="reprocess accepted match state",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=input_path,
        config=config,
    )
    storage.save_raw_rows(
        match.id,
        [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 7, "X": 19.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95},
            {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "my_team", "Track_ID": 7, "X": 21.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "my_team", "Track_ID": 7, "X": 21.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80},
        ],
    )
    storage.save_analysis_artifact(
        match.id,
        "ball_truth_layers",
        {
            "sampleInterval": 1,
            "observedBall": {
                "rows": [{"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95}],
                "summary": {"rowCount": 1, "frameCount": 1, "pathLength": 0.0, "edgeFrameShare": 0.0, "segmentCount": 1, "firstFrame": 0, "lastFrame": 0},
            },
            "inferredBall": {
                "rows": [{"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80}],
                "summary": {"rowCount": 1, "frameCount": 1, "pathLength": 0.0, "edgeFrameShare": 0.0, "segmentCount": 1, "firstFrame": 2, "lastFrame": 2},
            },
            "acceptedBall": {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95},
                    {"Frame_ID": 2, "Timestamp": 0.4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.0, "Conf": 0.80},
                ],
                "summary": {"rowCount": 2, "frameCount": 2, "pathLength": 2.0, "edgeFrameShare": 0.0, "segmentCount": 2, "firstFrame": 0, "lastFrame": 2},
            },
            "acceptedSegments": [
                {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
                {"startFrame": 2, "endFrame": 2, "frameCount": 1, "source": "inferred"},
            ],
            "unknownGaps": [{"startFrame": 1, "endFrame": 1, "frameCount": 1}],
            "acceptedSourceBreakdown": {"observed": 1, "inferred": 1},
        },
    )
    storage.save_frames(
        match.id,
        [
            FrameData(frameId=0, timestamp=0.0, ball={"x": 20.0, "y": 30.0, "confidence": 0.95}, myTeam=[{"id": 7, "x": 19.0, "y": 30.0, "confidence": 0.9}]),
            FrameData(frameId=1, timestamp=0.2, ball=None, myTeam=[{"id": 7, "x": 21.0, "y": 30.0, "confidence": 0.9}]),
            FrameData(frameId=2, timestamp=0.4, ball={"x": 22.0, "y": 30.0, "confidence": 0.80}, myTeam=[{"id": 7, "x": 21.0, "y": 30.0, "confidence": 0.9}]),
        ],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])

    reprocess_video_match(storage, match.id)

    accepted_match_state = storage.load_analysis_artifact(match.id, "accepted_match_state")
    assert accepted_match_state["stateContinuityAppliedFrames"] == 1
    assert accepted_match_state["frames"][1]["source"] == "player_conditioned"


def test_persist_video_outputs_keeps_normalized_frames_reprocessable(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="normalized frames match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    frames = [
        FrameData(
            frameId=0,
            timestamp=0.0,
            ball={"x": 52.0, "y": 50.0, "confidence": 0.95},
            myTeam=[{"id": 4, "x": 51.0, "y": 50.0, "confidence": 0.9}],
        )
    ]
    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda persisted_frames, **_kwargs: (
            persisted_frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        frames,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    raw_rows_path = storage._match_dir(match.id) / "raw_rows.json"
    assert raw_rows_path.exists()
    raw_rows_path.unlink()

    seen_frames = {}

    def fake_compute_outputs(persisted_frames, **_kwargs):
        seen_frames["frame_ids"] = [frame.frameId for frame in persisted_frames]
        return (
            persisted_frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        )

    monkeypatch.setattr(processor, "_compute_outputs_and_match_state", fake_compute_outputs)

    reprocess_video_match(storage, match.id)

    assert seen_frames["frame_ids"] == [0]


def test_reprocess_video_match_reuses_image_space_detections_for_team_mapping(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig(myTeamCluster=0)
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"video")
    match = storage.create_match(
        name="team mapping reprocess",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=input_path,
        config=config,
    )
    storage.save_raw_rows(
        match.id,
        [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "my_team", "Track_ID": 7, "X": 19.0, "Y": 30.0, "Conf": 0.9},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.95},
        ],
    )
    storage.update_match_status(
        match.id,
        status="ready",
        requires_team_selection=False,
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[1.0, 0.0, 0.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[0.0, 0.0, 1.0], trackIds=[]),
        ],
    )

    def fail_vision(*_args, **_kwargs):
        raise AssertionError("team mapping reprocess must not invoke vision")

    monkeypatch.setattr(processor, "process_video_input", fail_vision)

    reprocess_video_match(storage, match.id, config=MatchConfig(myTeamCluster=1))
    plan = storage.load_analysis_artifact(match.id, "reprocess_plan")
    assert plan["visionInvoked"] is False
    assert plan["imageSpaceDetectionsReused"] is True
    assert plan["reused"] is True


def test_persist_video_outputs_preserves_producer_sample_interval_for_sparse_ball_rows(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="sample interval match",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
            {"Frame_ID": 10, "Timestamp": 2.0, "Entity_Type": "ball", "Track_ID": -1, "X": 58.0, "Y": 48.0, "Conf": 0.91},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
            {"Frame_ID": 10, "Timestamp": 2.0, "Entity_Type": "player", "Track_ID": 4, "X": 57.0, "Y": 50.0, "Conf": 0.9},
        ],
        "trackColors": {},
        "ballTruthLayers": {
            "sampleInterval": 5,
            "observedBall": {
                "rows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                ],
                "summary": {
                    "rowCount": 1,
                    "frameCount": 1,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 0,
                },
            },
            "inferredBall": {
                "rows": [
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 58.0, "Y": 48.0, "Conf": 0.91},
                ],
                "summary": {
                    "rowCount": 1,
                    "frameCount": 1,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 10,
                    "lastFrame": 10,
                },
            },
            "acceptedBall": {
                "rows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 58.0, "Y": 48.0, "Conf": 0.91},
                ],
                "summary": {
                    "rowCount": 2,
                    "frameCount": 2,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 2,
                    "firstFrame": 0,
                    "lastFrame": 10,
                },
            },
            "acceptedSegments": [
                {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
                {"startFrame": 10, "endFrame": 10, "frameCount": 1, "source": "inferred"},
            ],
            "unknownGaps": [
                {"startFrame": 5, "endFrame": 5, "frameCount": 1},
            ],
            "acceptedSourceBreakdown": {"observed": 1, "inferred": 1},
        },
        "ballPipelineTrace": {
            "traceVersion": 1,
            "stages": [],
        },
    }

    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda frames, **_kwargs: (
            frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )

    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        video_result,
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )

    truth_layers = storage.load_analysis_artifact(match.id, "ball_truth_layers")
    assert truth_layers["sampleInterval"] == 5
    assert truth_layers["acceptedSegments"] == [
        {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
        {"startFrame": 10, "endFrame": 10, "frameCount": 1, "source": "inferred"},
    ]
    assert truth_layers["unknownGaps"] == [
        {"startFrame": 5, "endFrame": 5, "frameCount": 1},
    ]


def test_persist_video_outputs_saves_four_rates_projection_and_cache_identity(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    config = MatchConfig()
    match = storage.create_match(
        name="four rates persist",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=config,
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")
    monkeypatch.setattr(
        processor,
        "_compute_outputs_and_match_state",
        lambda frames, **_kwargs: (
            frames,
            MatchSummary(
                possession=55,
                myTeamDistance=1000,
                enemyDistance=950,
                myTeamAvgPos={"x": 52.0, "y": 48.0},
                enemyAvgPos={"x": 48.0, "y": 52.0},
                myTeamTopSpeed=30.1,
                enemyTopSpeed=29.0,
                myTeamSprints=10,
                enemySprints=9,
                formation="4-3-3",
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        ),
    )
    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        config,
        {
            "rows": [
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
            ],
            "trackColors": {},
            "fourRates": {"exportFpsEqualsInferenceFps": False, "decodeCount": 25, "inferenceCount": 25, "exportCount": 5},
            "projectionPolicy": {
                "playerAnchor": "ground_contact",
                "boxCentreIsFoot": False,
                "aerialBallMeasuredGroundLocation": False,
            },
            "cacheIdentity": "cache-abc",
            "sampling": {"selectedBackend": "opencv+ultralytics_track", "exportFpsEqualsInferenceFps": False},
            "vidStridePolicy": {"addsVidStrideAlone": False, "targetFpsEqualsInferenceFps": False},
            "decodeMemoryPolicy": {"retainAllDecodedFrames": False, "gpuResident": False},
        },
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )
    rates = storage.load_analysis_artifact(match.id, "four_rates")
    assert rates["exportFpsEqualsInferenceFps"] is False
    policy = storage.load_analysis_artifact(match.id, "projection_policy")
    assert policy["boxCentreIsFoot"] is False
    assert policy["playerAnchor"] == "ground_contact"
    cache = storage.load_analysis_artifact(match.id, "cache_identity")
    assert cache["cacheIdentity"] == "cache-abc"
    sampling = storage.load_analysis_artifact(match.id, "sampling")
    assert sampling["selectedBackend"] == "opencv+ultralytics_track"
    stride = storage.load_analysis_artifact(match.id, "vid_stride_policy")
    assert stride["addsVidStrideAlone"] is False


def test_save_analysis_artifact_writes_alongside_previous_digest(tmp_path):
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="alongside",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=MatchConfig(),
    )
    storage.save_analysis_artifact(match.id, "projection_policy", {"playerAnchor": "box_centre"})
    first = storage.load_analysis_artifact(match.id, "projection_policy")
    storage.save_analysis_artifact(match.id, "projection_policy", {"playerAnchor": "ground_contact"})
    live = storage.load_analysis_artifact(match.id, "projection_policy")
    receipt = json.loads((storage._match_dir(match.id) / "receipts" / "projection_policy.json").read_text(encoding="utf-8"))
    assert live["playerAnchor"] == "ground_contact"
    assert receipt["mutatedHistorical"] is False
    assert receipt["previousDigest"]
    assert receipt["digest"] != receipt["previousDigest"]
    assert first["playerAnchor"] == "box_centre" or receipt["previousDigest"]
