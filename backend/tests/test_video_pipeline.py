import pytest
from unittest.mock import patch
from pathlib import Path

from backend.app.video_pipeline import process_video_input
from backend.app.schemas import MatchConfig, HomographyPoint


PRODUCER_RECEIPT = {
    "fourRates": {
        "decodeCount": 1,
        "detectorPrimaryCount": 1,
        "detectorRecoveryCount": 0,
        "trackerUpdateCount": 1,
        "exportCount": 1,
    },
    "samplingReceipt": {},
    "decodeAnchors": {"beginning": 0.0, "middle": None, "end": None},
}


def _cfg(points):
    return MatchConfig(
        inputMode="video",
        attackDirection="left_to_right",
        manualHomographyPoints=[HomographyPoint(x=p[0], y=p[1]) for p in points],
    )


def test_process_video_input_requires_exactly_four_homography_points():
    """Raises RuntimeError when manualHomographyPoints has fewer than 4 entries."""
    config = _cfg([])
    with pytest.raises(RuntimeError, match="exactly 4 points"):
        process_video_input(Path("/fake/video.mp4"), config)


def test_process_video_input_requires_not_more_than_four_points():
    """Raises RuntimeError when manualHomographyPoints has more than 4 entries."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100], [50, 50]])
    with pytest.raises(RuntimeError, match="exactly 4 points"):
        process_video_input(Path("/fake/video.mp4"), config)


def test_process_video_input_passes_parsed_points_to_process_video():
    """Correctly extracts (x, y) from schema points and passes them to process_video."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(Path("/fake/video.mp4"), config)

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[0][0] == str(Path("/fake/video.mp4"))
        assert call_args[1]["homography_points"] == [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result


def test_process_video_input_forwards_progress_callback_to_process_video():
    """Passes the callback through unchanged so the worker can emit live heartbeats."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])
    progress_events = []

    def progress_callback(payload):  # noqa: ANN001
        progress_events.append(payload)

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            progress_callback=progress_callback,
            match_id="match-123",
            job_id="job-123",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["progress_callback"] is progress_callback
        assert call_args[1]["match_id"] == "match-123"
        assert call_args[1]["job_id"] == "job-123"
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result
        assert progress_events == []


def test_process_video_input_forwards_model_path_to_process_video():
    """Passes an explicit detector override through without touching MatchConfig."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            model_path="/workspace/weights/yolo11s.pt",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model_path"] == "/workspace/weights/yolo11s.pt"
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result


def test_process_video_input_forwards_edge_share_repair_profile_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            edge_share_repair_profile="source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["edge_share_repair_profile"] == "source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2"
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result


def test_process_video_input_forwards_baseline_guided_rescue_reference_path_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            baseline_guided_rescue_reference_path="/tmp/baseline-guided-reference.json",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["baseline_guided_rescue_reference_path"] == "/tmp/baseline-guided-reference.json"
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result


def test_process_video_input_forwards_primary_and_auxiliary_detector_fields_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}, **PRODUCER_RECEIPT}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            model_path="/workspace/weights/yolov10n.pt",
            primary_model_path="/workspace/weights/yolov10n.pt",
            auxiliary_ball_model_path="/workspace/weights/touchline-best.pt",
            auxiliary_ball_model_profile="ball_probe_only_v1",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model_path"] == "/workspace/weights/yolov10n.pt"
        assert call_args[1]["primary_model_path"] == "/workspace/weights/yolov10n.pt"
        assert call_args[1]["auxiliary_ball_model_path"] == "/workspace/weights/touchline-best.pt"
        assert call_args[1]["auxiliary_ball_model_profile"] == "ball_probe_only_v1"
        assert result["rows"] == []
        assert result["trackColors"] == {}
        assert "sourceClock" in result
        assert result["sourceClock"]["decodeErrors"]


def test_process_video_input_attaches_source_clock_from_frame_source(tmp_path, monkeypatch):
    video = tmp_path / "clip.bin"
    video.write_bytes(b"fixture-bytes")
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    class FakeSource:
        name = "fixture"

        def probe(self, path):
            from backend.app.workbench.contracts import SourceClockIdentity

            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size, codec="h264")

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [{"Frame_ID": 0}], "trackColors": {}, **PRODUCER_RECEIPT}
        result = process_video_input(video, config, frame_source=FakeSource())

    assert result["rows"] == [{"Frame_ID": 0}]
    assert result["sourceClock"]["sourceSha256"] == "a" * 64
    assert result["sourceClock"]["byteSize"] == 13
    assert result["sourceClock"]["codec"] == "h264"


def test_process_video_input_forwards_frame_source_to_process_video(tmp_path):
    video = tmp_path / "clip.bin"
    video.write_bytes(b"fixture-bytes")
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    class FakeSource:
        name = "fixture"

        def probe(self, path):
            from backend.app.workbench.contracts import SourceClockIdentity

            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size)

    source = FakeSource()
    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [{"Frame_ID": 0}], "trackColors": {}, **PRODUCER_RECEIPT}
        process_video_input(video, config, frame_source=source)

    assert mock_process.call_args.kwargs["frame_source"] is source


def test_process_video_input_defaults_to_opencv_frame_source(tmp_path):
    video = tmp_path / "clip.bin"
    video.write_bytes(b"fixture-bytes")
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [{"Frame_ID": 0}], "trackColors": {}, **PRODUCER_RECEIPT}
        process_video_input(video, config)

    frame_source = mock_process.call_args.kwargs["frame_source"]
    assert frame_source is not None
    assert getattr(frame_source, "name", None) == "opencv"


def test_process_video_input_raises_when_process_video_returns_nothing():
    """Raises RuntimeError when process_video returns an empty/falsy result."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = []

        with pytest.raises(RuntimeError, match="tracking rows"):
            process_video_input(Path("/fake/video.mp4"), config)


def test_process_video_input_preserves_four_rates_and_separates_policy(tmp_path):
    video = tmp_path / "clip.bin"
    video.write_bytes(b"fixture-bytes")
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    class FakeSource:
        name = "fixture"

        def probe(self, path):
            from backend.app.workbench.contracts import SourceClockIdentity

            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size, codec="h264")

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [{"Frame_ID": 0}], "trackColors": {}, **PRODUCER_RECEIPT}
        result = process_video_input(video, config, frame_source=FakeSource())

    assert result["exportFpsEqualsInferenceFps"] is False
    assert result["fourRates"] == PRODUCER_RECEIPT["fourRates"]
    assert "cacheIdentity" not in result
    assert result["policy"]["requestedBackend"] == "fixture+ultralytics_track"
    assert result["vidStridePolicy"]["addsVidStrideAlone"] is False
    assert result["vidStridePolicy"]["targetFpsEqualsInferenceFps"] is False
    assert result["projectionPolicy"]["boxCentreIsFoot"] is False
    assert result["projectionPolicy"]["aerialBallMeasuredGroundLocation"] is False
    assert result["decodeMemoryPolicy"]["retainAllDecodedFrames"] is False
    assert result["decodeMemoryPolicy"]["gpuResident"] is False
    assert result["decodeMemoryPolicy"]["canPromoteDefault"] is False
    assert "CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY" in result["decodeMemoryPolicy"]["reasonCodes"] or result["decodeMemoryPolicy"]["videoEngineCapability"] is False


def test_report_only_reprocess_does_not_invoke_vision():
    from backend.app.video_pipeline import reprocess_for_change

    calls = []

    def vision():
        calls.append("vision")
        return {"rows": [{"Frame_ID": 1}]}

    reused = reprocess_for_change(
        change="report",
        previous_identity="abc",
        current_identity="abc",
        vision=vision,
    )
    assert reused["visionInvoked"] is False
    assert calls == []
    rebuilt = reprocess_for_change(
        change="perception",
        previous_identity=None,
        current_identity="def",
        vision=vision,
    )
    assert rebuilt["visionInvoked"] is True
    assert "observations" in rebuilt["rebuild"]
    assert calls == ["vision"]


def test_processor_report_change_does_not_invoke_vision() -> None:
    from backend.app.processor import reprocess_match_for_change

    calls: list[str] = []

    reused = reprocess_match_for_change(
        change="report",
        previous_identity="abc",
        current_identity="abc",
        vision=lambda: calls.append("vision") or {"rows": [{"Frame_ID": 1}]},
    )
    assert reused["visionInvoked"] is False
    assert calls == []
    rebuilt = reprocess_match_for_change(
        change="perception",
        previous_identity=None,
        current_identity="def",
        vision=lambda: calls.append("vision") or {"rows": [{"Frame_ID": 1}]},
    )
    assert rebuilt["visionInvoked"] is True
    assert "observations" in rebuilt["rebuild"]
    assert calls == ["vision"]


def test_detected_rows_project_players_from_ground_contact_not_box_centre() -> None:
    from backend.app.video_pipeline import project_detected_rows

    player = project_detected_rows([{"kind": "player", "bbox": (10.0, 20.0, 30.0, 80.0)}])[0]
    assert player["imageX"] == 20.0
    assert player["imageY"] == 80.0
    assert player["boxCentreIsFoot"] is False
    aerial = project_detected_rows([{"kind": "ball", "airborne": True, "bbox": (10.0, 20.0, 30.0, 80.0)}])[0]
    assert aerial["measuredGroundLocation"] is False
    assert "AERIAL_NOT_GROUND_PLANE" in aerial["reasonCodes"]


def test_tracking_rows_project_players_from_source_box_ground_contact() -> None:
    from backend.app.video_pipeline import project_detected_rows

    player = project_detected_rows(
        [
            {
                "Entity_Type": "player",
                "Source_X1": 10.0,
                "Source_Y1": 20.0,
                "Source_X2": 30.0,
                "Source_Y2": 80.0,
            }
        ]
    )[0]
    assert player["imageX"] == 20.0
    assert player["imageY"] == 80.0
    assert player["boxCentreIsFoot"] is False
    aerial = project_detected_rows(
        [
            {
                "Entity_Type": "ball",
                "airborne": True,
                "Source_X1": 10.0,
                "Source_Y1": 20.0,
                "Source_X2": 30.0,
                "Source_Y2": 80.0,
            }
        ]
    )[0]
    assert aerial["measuredGroundLocation"] is False
    assert "AERIAL_NOT_GROUND_PLANE" in aerial["reasonCodes"]


def test_projected_rows_reset_tracker_identity_across_cuts() -> None:
    from backend.app.video_pipeline import associate_projected_rows

    rows = [
        {
            "Entity_Type": "player",
            "Source_X1": 10.0,
            "Source_Y1": 20.0,
            "Source_X2": 30.0,
            "Source_Y2": 80.0,
            "Frame_ID": 4,
            "Track_ID": 12,
        }
    ]
    tracks = associate_projected_rows(rows, cut_detected=True)
    assert tracks
    assert all(track["reset"] is True for track in tracks)
    assert all(track["silentlyReconnected"] is False for track in tracks)
    assert tracks[0]["trackId"] == "12"
    assert tracks[0]["productionPath"] == "botsort"
