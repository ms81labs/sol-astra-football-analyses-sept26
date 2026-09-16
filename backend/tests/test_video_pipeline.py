import pytest
from unittest.mock import patch
from pathlib import Path

from backend.app.video_pipeline import process_video_input
from backend.app.schemas import MatchConfig, HomographyPoint


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
        mock_process.return_value = {"rows": [], "trackColors": {}}

        result = process_video_input(Path("/fake/video.mp4"), config)

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[0][0] == str(Path("/fake/video.mp4"))
        assert call_args[1]["homography_points"] == [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert result == {"rows": [], "trackColors": {}}


def test_process_video_input_forwards_progress_callback_to_process_video():
    """Passes the callback through unchanged so the worker can emit live heartbeats."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])
    progress_events = []

    def progress_callback(payload):  # noqa: ANN001
        progress_events.append(payload)

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}}

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
        assert result == {"rows": [], "trackColors": {}}
        assert progress_events == []


def test_process_video_input_forwards_model_path_to_process_video():
    """Passes an explicit detector override through without touching MatchConfig."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            model_path="/workspace/weights/yolo11s.pt",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["model_path"] == "/workspace/weights/yolo11s.pt"
        assert result == {"rows": [], "trackColors": {}}


def test_process_video_input_forwards_edge_share_repair_profile_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            edge_share_repair_profile="source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["edge_share_repair_profile"] == "source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2"
        assert result == {"rows": [], "trackColors": {}}


def test_process_video_input_forwards_baseline_guided_rescue_reference_path_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}}

        result = process_video_input(
            Path("/fake/video.mp4"),
            config,
            baseline_guided_rescue_reference_path="/tmp/baseline-guided-reference.json",
        )

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["baseline_guided_rescue_reference_path"] == "/tmp/baseline-guided-reference.json"
        assert result == {"rows": [], "trackColors": {}}


def test_process_video_input_forwards_primary_and_auxiliary_detector_fields_to_process_video():
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = {"rows": [], "trackColors": {}}

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
        assert result == {"rows": [], "trackColors": {}}


def test_process_video_input_raises_when_process_video_returns_nothing():
    """Raises RuntimeError when process_video returns an empty/falsy result."""
    config = _cfg([[0, 0], [100, 0], [100, 100], [0, 100]])

    with patch("backend.app.video_pipeline._process_video_impl") as mock_process:
        mock_process.return_value = []

        with pytest.raises(RuntimeError, match="tracking rows"):
            process_video_input(Path("/fake/video.mp4"), config)
