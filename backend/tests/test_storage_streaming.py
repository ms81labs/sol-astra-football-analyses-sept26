import json
import os
import stat

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from backend.app.run_benchmarks import summarize_match_benchmark
from backend.app.schemas import FrameData, MatchConfig, MatchSummary, PlayerData
from backend.app.storage import Storage


def test_player_data_uses_slots_and_preserves_validated_constructor_values():
    player = PlayerData(id="7", x="48.5", y=34)
    assert (player.id, player.x, player.y, player.confidence) == (7, 48.5, 34.0, 0.0)
    assert not hasattr(player, "__dict__")


@pytest.mark.parametrize("field,value", [("id", "invalid"), ("x", None), ("y", "invalid"), ("confidence", [])])
def test_player_data_rejects_invalid_constructor_and_nested_frame_values(field, value):
    payload = {"id": 7, "x": 48.0, "y": 34.0, "confidence": 0.9, field: value}
    with pytest.raises(ValidationError):
        PlayerData(**payload)
    for team in ("myTeam", "enemies", "unassignedPlayers"):
        with pytest.raises(ValidationError):
            FrameData.model_validate({"frameId": 0, "timestamp": 0.0, team: [payload]})


def test_frame_data_preserves_nested_player_json_round_trip():
    payload = {
        "frameId": 0, "timestamp": 0.0, "ball": None, "possession": None,
        "coordinateSpace": "pitch_normalized_0_100", "geometryAvailable": False, "coordinateProvenance": {},
        "myTeam": [{"id": 7, "x": 48.0, "y": 34.0, "confidence": 0.9}],
        "enemies": [{"id": 8, "x": 90.0, "y": 34.0, "confidence": 0.8}],
        "unassignedPlayers": [{"id": 9, "x": 50.0, "y": 34.0, "confidence": 0.0}],
    }
    frame = FrameData.model_validate(payload)
    assert isinstance(frame.myTeam[0], PlayerData)
    assert frame.model_dump(mode="json") == payload
    assert FrameData.model_validate_json(frame.model_dump_json()).model_dump(mode="json") == payload


def test_video_ball_signal_is_not_trusted_on_new_or_saved_artifacts(tmp_path):
    storage = Storage(tmp_path)
    summary = MatchSummary(
        possession=50,
        myTeamDistance=0,
        enemyDistance=0,
        myTeamAvgPos={"x": 50, "y": 50},
        enemyAvgPos={"x": 50, "y": 50},
        myTeamTopSpeed=0,
        enemyTopSpeed=0,
        myTeamSprints=0,
        enemySprints=0,
        formation="-",
        ballSignalStatus="trusted",
    )

    new_video = storage.create_match("new video", "video", "clip.mp4", tmp_path / "clip.mp4", MatchConfig())
    storage.save_analytics(new_video.id, summary, [], [], [])
    saved = json.loads((storage._match_dir(new_video.id) / "analytics.json").read_text())
    assert saved["summary"]["ballSignalStatus"] == "untrusted"
    assert "independently verified" in saved["summary"]["ballSignalMessage"]

    old_video = storage.create_match("saved video", "video", "old.mp4", tmp_path / "old.mp4", MatchConfig())
    old_path = storage._match_dir(old_video.id) / "analytics.json"
    storage._write_json(old_path, {
        "summary": summary.model_dump(mode="json"),
        "ballAssignments": [],
        "formationTimeline": [],
        "shots": [],
    })
    original = old_path.read_bytes()
    loaded, _, _, _ = storage.load_analytics(old_video.id)
    assert loaded.ballSignalStatus == "untrusted"
    assert "independently verified" in loaded.ballSignalMessage
    assert old_path.read_bytes() == original
    assert summarize_match_benchmark(storage, old_video.id).ballSignalStatus == "untrusted"

    tracking = storage.create_match("tracking data", "tracking_json", "tracks.json", tmp_path / "tracks.json", MatchConfig())
    storage.save_analytics(tracking.id, summary, [], [], [])
    loaded_tracking, _, _, _ = storage.load_analytics(tracking.id)
    assert loaded_tracking.ballSignalStatus == "trusted"


def test_save_frames_streams_one_pass_without_eager_json_writer(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    match_dir = storage._match_dir("match-1")

    class OneShotFrames:
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            assert self.iterations == 1, "frames iterated twice"
            yield FrameData(frameId=0, timestamp=0.0, myTeam=[PlayerData(id=7, x=48, y=34)])
            assert list(match_dir.glob(".frames.json.*.tmp")), "frames consumed before atomic write"
            yield FrameData(frameId=1, timestamp=0.2)

    monkeypatch.setattr(storage, "_write_json", lambda *args: pytest.fail("eager JSON writer"))
    frames = OneShotFrames()
    storage.save_frames("match-1", frames)
    saved = storage.load_frames("match-1")
    assert [frame.frameId for frame in saved] == [0, 1]
    assert (saved[0].myTeam[0].id, saved[0].myTeam[0].x, saved[0].myTeam[0].confidence) == (7, 48.0, 0.0)
    assert frames.iterations == 1
    assert sorted(path.name for path in match_dir.iterdir()) == [".generation.lifetime.lock", ".generation.lock", ".review.lock", "frames.json"]


@pytest.mark.parametrize("failure", ["iteration", "serialization"])
def test_save_frames_streaming_failure_preserves_existing_file(tmp_path, failure):
    storage = Storage(tmp_path)
    storage.save_frames("match-1", [FrameData(frameId=99, timestamp=19.8)])
    match_dir = storage._match_dir("match-1")
    before = (match_dir / "frames.json").read_bytes()

    def frames():
        yield FrameData(frameId=0, timestamp=0.0)
        assert list(match_dir.glob(".frames.json.*.tmp")), "frames consumed before atomic write"
        if failure == "iteration":
            raise RuntimeError("frame stream failed")
        yield FrameData.model_construct(frameId=1, timestamp=0.2, ball=object())

    error = RuntimeError if failure == "iteration" else PydanticSerializationError
    with pytest.raises(error):
        storage.save_frames("match-1", frames())
    assert (match_dir / "frames.json").read_bytes() == before
    assert sorted(path.name for path in match_dir.iterdir()) == [".generation.lifetime.lock", ".generation.lock", ".review.lock", "frames.json"]


def test_save_raw_rows_streams_a_one_shot_iterable(tmp_path):
    storage = Storage(tmp_path)

    class OneShotRows:
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            assert self.iterations == 1, "rows iterated twice"
            yield {"Frame_ID": 0, "label": "café"}
            yield {"Frame_ID": 1, "nested": [1, None, True]}

    rows = OneShotRows()
    storage.save_raw_rows("match-1", rows)
    assert storage.load_raw_rows("match-1") == [
        {"Frame_ID": 0, "label": "café"},
        {"Frame_ID": 1, "nested": [1, None, True]},
    ]
    assert rows.iterations == 1


@pytest.mark.parametrize("failure", ["iteration", "serialization"])
def test_save_raw_rows_one_shot_failure_preserves_previous_array(tmp_path, failure):
    storage = Storage(tmp_path)
    storage.save_raw_rows("match-1", [{"existing": True}])
    path = storage._match_dir("match-1") / "raw_rows.json"
    before = path.read_bytes()
    observed = []

    def rows():
        observed.append(0)
        yield {"Frame_ID": 0}
        observed.append(1)
        if failure == "iteration":
            raise RuntimeError("stream failed")
        yield {"invalid": object()}

    error = RuntimeError if failure == "iteration" else TypeError
    with pytest.raises(error):
        storage.save_raw_rows("match-1", rows())
    assert observed == [0, 1]
    assert path.read_bytes() == before
    assert sorted(item.name for item in path.parent.iterdir()) == ["raw_rows.json"]


def test_save_raw_rows_one_shot_empty_array_fsyncs_before_and_after_replace(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    operations = []
    original_fsync, original_replace = os.fsync, os.replace

    def fsync(descriptor):
        operations.append("directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file")
        original_fsync(descriptor)

    def replace(source, destination):
        operations.append("replace")
        original_replace(source, destination)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)
    storage.save_raw_rows("match-1", iter(()))
    assert storage.load_raw_rows("match-1") == []
    assert operations == ["file", "replace", "directory"]
