import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from backend.app.edge_share_repair_profiles import (
    ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES,
    get_source_edge_share_repair_config,
)
from backend.app.homography_utils import build_homography_from_points
import backend.run_guerilla as run_guerilla
from backend.run_guerilla import (
    _build_ball_truth_layers,
    _build_ball_support_diagnostics,
    build_anchor_corridor_crop_window,
    _filter_probe_observed_ball_rows,
    _coherent_ball_subchains,
    _summarize_recovered_ball_anchor_diagnostics,
    ball_recovery_crop_window,
    ball_track_summary_is_viable,
    ball_rows_need_recovery,
    ball_rows_need_supplemental_recovery,
    ball_rows_show_meaningful_motion,
    build_ball_recovery_experiment_profiles,
    build_ball_recovery_quality_matrix_profiles,
    build_tracking_row,
    collect_player_windows_from_rows,
    collect_primary_player_windows,
    collect_observed_source_anchors,
    merge_missing_ball_rows,
    run_ball_recovery_experiment,
    score_ball_track_summary,
    select_meaningful_recovered_ball_rows,
    split_ball_rows_into_segments,
    suppress_repeated_false_ball_clusters,
    summarize_ball_recovery_crop_windows,
    summarize_recovered_ball_candidates,
    summarize_ball_track_rows,
    process_video,
    projection_anchor_for_detection,
    select_best_ball_recovery_profile,
    should_keep_detection_for_pitch,
    update_player_window,
)


def test_import_does_not_probe_gui_apis():
    script = """
import cv2
import sys
import types

ultralytics = types.ModuleType("ultralytics")
ultralytics.YOLO = object
sys.modules["ultralytics"] = ultralytics

calls = []
cv2.imshow = lambda *_args, **_kwargs: calls.append("imshow")
cv2.destroyAllWindows = lambda: calls.append("destroyAllWindows")

import backend.run_guerilla as run_guerilla

assert calls == [], calls
assert run_guerilla.HEADLESS is False
"""
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = ":99"

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_build_homography_from_points_raises_on_fewer_than_four_points():
    """Raises ValueError when fewer than 4 points are supplied."""
    with pytest.raises(ValueError, match="exactly 4 points"):
        build_homography_from_points([[100, 100], [200, 100]])


def test_build_homography_from_points_raises_on_collinear_points():
    """Raises ValueError when all 4 points are collinear (no valid homography)."""
    # All 4 points lie on the same line — findHomography returns None
    collinear = [[0, 0], [100, 0], [200, 0], [300, 0]]
    with pytest.raises(ValueError, match="degenerate"):
        build_homography_from_points(collinear)


def test_build_homography_from_points_raises_when_points_are_too_close():
    """Raises ValueError when points are nearly coincident (degenerate)."""
    # All points lie on y=x line — zero area → degenerate
    near_degenerate = [[0, 0], [1, 1], [2, 2], [3, 3]]
    with pytest.raises(ValueError, match="degenerate"):
        build_homography_from_points(near_degenerate)


def test_build_homography_from_points_returns_valid_matrix_for_rectangle():
    """Returns a 3x3 homography matrix for a valid rectangle."""
    points = [[100, 50], [500, 50], [500, 350], [100, 350]]
    H = build_homography_from_points(points)

    assert H.shape == (3, 3)
    # Homography must be invertible (determinant != 0)
    assert abs(np.linalg.det(H)) > 1e-6

    # The TL corner (100, 50) should map close to (0, 0)
    pt = np.array([100, 50, 1.0])
    projected = H.dot(pt)
    projected /= projected[2]
    assert abs(projected[0]) < 1.0
    assert abs(projected[1]) < 1.0


def test_resolve_homography_manual_fallback_scales_clicked_points(monkeypatch):
    first_frame = np.zeros((1440, 2560, 3), dtype=np.uint8)
    low_res_points = [[10, 20], [110, 20], [110, 220], [10, 220]]

    monkeypatch.setattr(run_guerilla, "HEADLESS", False)
    monkeypatch.setattr(
        run_guerilla,
        "select_homography_points",
        lambda _frame, return_points=False: (np.eye(3), low_res_points),
    )

    homography, pitch_points = run_guerilla.resolve_homography(
        first_frame,
        homography_points=None,
        use_auto=False,
    )

    assert homography.tolist() == [
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert pitch_points == [[20.0, 40.0], [220.0, 40.0], [220.0, 440.0], [20.0, 440.0]]


def test_build_homography_from_points_reverse_order_still_valid():
    """Any valid quadrilateral produces a valid homography regardless of ordering."""
    # BL, TL, TR, BR order
    points = [[100, 350], [100, 50], [500, 50], [500, 350]]
    H = build_homography_from_points(points)

    assert H.shape == (3, 3)
    assert abs(np.linalg.det(H)) > 1e-6


def test_projection_anchor_for_ball_uses_box_center():
    cx, cy = projection_anchor_for_detection(32, 10, 20, 30, 60)

    assert cx == 20
    assert cy == 40


def test_projection_anchor_for_player_uses_box_feet():
    cx, cy = projection_anchor_for_detection(0, 10, 20, 30, 60)

    assert cx == 20
    assert cy == 60


def test_projection_anchor_for_ball_probe_only_profile_treats_class_zero_as_ball():
    cx, cy = projection_anchor_for_detection(0, 10, 20, 30, 60, detector_profile="ball_probe_only_v1")

    assert cx == 20
    assert cy == 40


def test_should_keep_detection_for_pitch_filters_ball_outside_polygon():
    pitch_points = [[0, 0], [100, 0], [100, 100], [0, 100]]

    assert should_keep_detection_for_pitch(32, 50, 50, pitch_points) is True
    assert should_keep_detection_for_pitch(32, 150, 50, pitch_points) is False


def test_should_keep_detection_for_pitch_does_not_filter_players():
    pitch_points = [[0, 0], [100, 0], [100, 100], [0, 100]]

    assert should_keep_detection_for_pitch(0, 150, 50, pitch_points) is True


def test_should_keep_detection_for_pitch_ball_probe_only_profile_filters_ball_outside_polygon():
    pitch_points = [[0, 0], [100, 0], [100, 100], [0, 100]]

    assert should_keep_detection_for_pitch(0, 50, 50, pitch_points, detector_profile="ball_probe_only_v1") is True
    assert should_keep_detection_for_pitch(0, 150, 50, pitch_points, detector_profile="ball_probe_only_v1") is False


def test_build_tracking_row_persists_source_box_coordinates():
    row = build_tracking_row(
        frame_id=25,
        timestamp=5.0,
        entity_type="ball",
        track_id=-1,
        pitch_x=12.34,
        pitch_y=56.78,
        detection_conf=0.91,
        source_box=(10.123, 20.456, 30.789, 40.012),
    )

    assert row["Frame_ID"] == 25
    assert row["Entity_Type"] == "ball"
    assert row["Source_X1"] == 10.12
    assert row["Source_Y1"] == 20.46
    assert row["Source_X2"] == 30.79
    assert row["Source_Y2"] == 40.01


def test_ball_rows_need_recovery_when_no_ball_rows_exist():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "X": 30.0, "Y": 40.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "player", "X": 32.0, "Y": 42.0, "Conf": 0.9},
    ]

    assert ball_rows_need_recovery(rows) is True


def test_ball_rows_show_meaningful_motion_rejects_static_cluster():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.83, "Y": 95.28, "Conf": 0.29},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.81, "Y": 95.31, "Conf": 0.28},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.84, "Y": 95.27, "Conf": 0.27},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.82, "Y": 95.29, "Conf": 0.26},
    ]

    assert ball_rows_show_meaningful_motion(rows) is False


def test_ball_rows_show_meaningful_motion_accepts_moving_signal():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 41.0, "Y": 54.0, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.5, "Y": 53.0, "Conf": 0.28},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.5, "Conf": 0.26},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 53.5, "Y": 47.0, "Conf": 0.25},
    ]

    assert ball_rows_show_meaningful_motion(rows) is True


def test_split_ball_rows_into_segments_breaks_on_large_frame_gap():
    rows = [
        {"Frame_ID": 100, "Entity_Type": "ball", "Track_ID": -1, "X": 30.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 105, "Entity_Type": "ball", "Track_ID": -1, "X": 32.0, "Y": 41.0, "Conf": 0.22},
        {"Frame_ID": 110, "Entity_Type": "ball", "Track_ID": -1, "X": 35.0, "Y": 42.0, "Conf": 0.24},
        {"Frame_ID": 220, "Entity_Type": "ball", "Track_ID": -1, "X": 80.0, "Y": 90.0, "Conf": 0.21},
        {"Frame_ID": 225, "Entity_Type": "ball", "Track_ID": -1, "X": 82.0, "Y": 91.0, "Conf": 0.23},
    ]

    segments = split_ball_rows_into_segments(rows, max_frame_gap=20)

    assert len(segments) == 2
    assert [row["Frame_ID"] for row in segments[0]] == [100, 105, 110]
    assert [row["Frame_ID"] for row in segments[1]] == [220, 225]


def test_select_meaningful_recovered_ball_rows_suppresses_static_best_cluster():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.83, "Y": 95.28, "Conf": 0.31},
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 43.0, "Y": 54.0, "Conf": 0.22},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.81, "Y": 95.31, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 46.5, "Y": 53.0, "Conf": 0.23},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.84, "Y": 95.27, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 51.0, "Y": 49.5, "Conf": 0.24},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.82, "Y": 95.29, "Conf": 0.28},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 56.5, "Y": 47.0, "Conf": 0.25},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert len(selected_rows) == 4
    assert max(row["X"] for row in selected_rows) < 60.0
    assert ball_rows_show_meaningful_motion(selected_rows) is True


def test_select_meaningful_recovered_ball_rows_keeps_multiple_viable_non_overlapping_segments():
    rows = [
        {"Frame_ID": 100, "Entity_Type": "ball", "X": 30.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 105, "Entity_Type": "ball", "X": 34.0, "Y": 43.0, "Conf": 0.21},
        {"Frame_ID": 110, "Entity_Type": "ball", "X": 38.0, "Y": 46.0, "Conf": 0.22},
        {"Frame_ID": 220, "Entity_Type": "ball", "X": 68.0, "Y": 50.0, "Conf": 0.24},
        {"Frame_ID": 225, "Entity_Type": "ball", "X": 75.0, "Y": 55.0, "Conf": 0.25},
        {"Frame_ID": 230, "Entity_Type": "ball", "X": 83.0, "Y": 61.0, "Conf": 0.26},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [100, 105, 110, 220, 225, 230]


def test_select_meaningful_recovered_ball_rows_prefers_higher_scoring_segment_when_frames_overlap():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 12.0, "Y": 96.6, "Conf": 0.28},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 18.0, "Y": 96.8, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 24.0, "Y": 97.0, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 40.0, "Y": 42.0, "Conf": 0.40},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 44.0, "Y": 45.0, "Conf": 0.41},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 48.0, "Y": 48.0, "Conf": 0.42},
        {"Frame_ID": 100, "Entity_Type": "ball", "X": 68.0, "Y": 50.0, "Conf": 0.24},
        {"Frame_ID": 105, "Entity_Type": "ball", "X": 75.0, "Y": 55.0, "Conf": 0.25},
        {"Frame_ID": 110, "Entity_Type": "ball", "X": 83.0, "Y": 61.0, "Conf": 0.26},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [5, 10, 15, 100, 105, 110]


def test_select_meaningful_recovered_ball_rows_prefers_anchor_strong_segment_over_frame_heavier_edge_heavy_alternative():
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "X": 41.0, "Y": 40.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "player", "X": 45.0, "Y": 43.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "player", "X": 49.0, "Y": 46.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 40.0, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 43.0, "Conf": 0.30},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 46.0, "Conf": 0.29},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 92.0, "Y": 95.0, "Conf": 0.42},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 94.0, "Y": 94.0, "Conf": 0.41},
        {"Frame_ID": 25, "Entity_Type": "ball", "X": 96.0, "Y": 93.0, "Conf": 0.40},
        {"Frame_ID": 35, "Entity_Type": "ball", "X": 95.0, "Y": 92.0, "Conf": 0.39},
        {"Frame_ID": 45, "Entity_Type": "ball", "X": 93.0, "Y": 91.0, "Conf": 0.38},
        {"Frame_ID": 55, "Entity_Type": "ball", "X": 91.0, "Y": 90.0, "Conf": 0.37},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows, player_rows=player_rows)

    assert [row["Frame_ID"] for row in selected_rows] == [0, 5, 10]


def test_select_meaningful_recovered_ball_rows_rejects_lower_scoring_segment_when_ranges_overlap_without_shared_frames():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 30.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 68.0, "Y": 50.0, "Conf": 0.30},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 34.0, "Y": 43.0, "Conf": 0.21},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 76.0, "Y": 56.0, "Conf": 0.31},
        {"Frame_ID": 20, "Entity_Type": "ball", "X": 38.0, "Y": 46.0, "Conf": 0.22},
        {"Frame_ID": 25, "Entity_Type": "ball", "X": 84.0, "Y": 62.0, "Conf": 0.32},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [5, 15, 25]


def test_select_meaningful_recovered_ball_rows_prefers_coherent_in_field_segment_over_isolated_edge_maxima():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "X": 42.0,
            "Y": 54.0,
            "Conf": 0.24,
            "Source_X1": 120.0,
            "Source_Y1": 120.0,
            "Source_X2": 140.0,
            "Source_Y2": 140.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "X": 46.0,
            "Y": 51.0,
            "Conf": 0.25,
            "Source_X1": 125.0,
            "Source_Y1": 123.0,
            "Source_X2": 145.0,
            "Source_Y2": 143.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "X": 97.0,
            "Y": 96.0,
            "Conf": 0.95,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "X": 50.0,
            "Y": 48.0,
            "Conf": 0.26,
            "Source_X1": 130.0,
            "Source_Y1": 126.0,
            "Source_X2": 150.0,
            "Source_Y2": 146.0,
        },
        {
            "Frame_ID": 35,
            "Entity_Type": "ball",
            "X": 96.0,
            "Y": 95.0,
            "Conf": 0.91,
            "Source_X1": 132.0,
            "Source_Y1": 128.0,
            "Source_X2": 152.0,
            "Source_Y2": 148.0,
        },
        {
            "Frame_ID": 70,
            "Entity_Type": "ball",
            "X": 95.0,
            "Y": 96.0,
            "Conf": 0.92,
        },
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [0, 5, 10]
    assert max(row["X"] for row in selected_rows) < 60.0
    assert ball_rows_show_meaningful_motion(selected_rows) is True


def test_build_ball_truth_layers_unions_tracking_and_probe_observed_rows_by_frame():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.51},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 25.0, "Y": 35.0, "Conf": 0.62},
    ]
    probe_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 21.0, "Y": 31.0, "Conf": 0.73},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 30.0, "Y": 40.0, "Conf": 0.48},
    ]
    inferred_rows = [
        {"Frame_ID": 15, "Entity_Type": "ball", "Track_ID": -1, "X": 33.0, "Y": 42.0, "Conf": 0.40},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        inferred_rows,
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
    )

    observed_rows = layers["observedBall"]["rows"]
    accepted_rows = layers["acceptedBall"]["rows"]

    assert [row["Frame_ID"] for row in observed_rows] == [0, 5, 10]
    assert observed_rows[0]["X"] == 21.0
    assert [row["Frame_ID"] for row in accepted_rows] == [0, 5, 10, 15]
    assert layers["acceptedSourceBreakdown"] == {"observed": 3, "inferred": 1}
    assert layers["directObservationBreakdown"] == {
        "trackingObservedBallFrames": 2,
        "rawProbeObservedBallFrames": 2,
        "filteredProbeObservedBallFrames": 2,
        "suppressedProbeObservedBallFrames": 0,
        "anchoredProbeObservedBallFrames": 2,
        "bridgeProbeObservedBallFrames": 0,
        "probeObservedBallFrames": 2,
        "probeOnlyObservedBallFrames": 1,
        "acceptedFromObservedFrames": 3,
        "acceptedFromObservedRatio": 0.75,
    }


def test_build_ball_truth_layers_prefers_tracking_row_on_confidence_tie():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.60},
    ]
    probe_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 90.0, "Y": 10.0, "Conf": 0.60},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
    )

    observed_rows = layers["observedBall"]["rows"]

    assert len(observed_rows) == 1
    assert observed_rows[0]["X"] == 20.0
    assert layers["directObservationBreakdown"]["probeOnlyObservedBallFrames"] == 0


def test_filter_probe_observed_ball_rows_suppresses_unsupported_edge_rows_without_anchors():
    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 98.0, "Y": 4.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 98.0, "Y": 5.0, "Conf": 0.85},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 97.0, "Y": 4.5, "Conf": 0.8},
    ]

    filtered = _filter_probe_observed_ball_rows(probe_rows, player_rows=[], sample_interval=5)

    assert filtered["rawFrameCount"] == 3
    assert filtered["filteredFrameCount"] == 0
    assert filtered["suppressedFrameCount"] == 3
    assert filtered["anchoredFrameCount"] == 0
    assert filtered["bridgeFrameCount"] == 0
    assert filtered["filteredRows"] == []


def test_filter_probe_observed_ball_rows_keeps_supported_probe_row_even_when_edge_heavy():
    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 96.0, "Y": 4.0, "Conf": 0.25},
    ]
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "Track_ID": 7, "X": 95.0, "Y": 5.0, "Conf": 0.9},
    ]

    filtered = _filter_probe_observed_ball_rows(probe_rows, player_rows=player_rows, sample_interval=5)

    assert [row["Frame_ID"] for row in filtered["filteredRows"]] == [0]
    assert filtered["anchoredFrameCount"] == 1
    assert filtered["bridgeFrameCount"] == 0


def test_filter_probe_observed_ball_rows_keeps_non_edge_probe_row_when_unsupported():
    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 55.0, "Y": 52.0, "Conf": 0.2},
    ]

    filtered = _filter_probe_observed_ball_rows(probe_rows, player_rows=[], sample_interval=5)

    assert [row["Frame_ID"] for row in filtered["filteredRows"]] == [0]
    assert filtered["anchoredFrameCount"] == 1
    assert filtered["bridgeFrameCount"] == 0


def test_filter_probe_observed_ball_rows_keeps_single_unsupported_edge_bridge_between_anchors():
    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 7.0, "Y": 40.0, "Conf": 0.6},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 3.0, "Y": 41.0, "Conf": 0.95},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 8.5, "Y": 42.0, "Conf": 0.62},
    ]

    filtered = _filter_probe_observed_ball_rows(probe_rows, player_rows=[], sample_interval=5)

    assert [row["Frame_ID"] for row in filtered["filteredRows"]] == [0, 5, 10]
    assert filtered["anchoredFrameCount"] == 2
    assert filtered["bridgeFrameCount"] == 1


def test_filter_probe_observed_ball_rows_drops_long_all_edge_probe_segment():
    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 97.0, "Y": 4.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 98.0, "Y": 4.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 99.0, "Y": 4.0, "Conf": 0.9},
        {"Frame_ID": 15, "Entity_Type": "ball", "Track_ID": -1, "X": 98.0, "Y": 5.0, "Conf": 0.9},
    ]

    filtered = _filter_probe_observed_ball_rows(probe_rows, player_rows=[], sample_interval=5)

    assert filtered["filteredRows"] == []
    assert filtered["suppressedFrameCount"] == 4


def test_build_ball_truth_layers_prefers_supported_observed_row_over_higher_confidence_unsupported_row():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 20.0, "Conf": 0.55},
    ]
    probe_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 96.0, "Y": 6.0, "Conf": 0.95},
    ]
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "Track_ID": 7, "X": 22.0, "Y": 20.0, "Conf": 0.9},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
        player_rows=player_rows,
    )

    observed_rows = layers["observedBall"]["rows"]

    assert len(observed_rows) == 1
    assert observed_rows[0]["X"] == 20.0


def test_build_ball_truth_layers_prefers_non_edge_observed_row_when_support_ties():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 45.0, "Y": 45.0, "Conf": 0.40},
    ]
    probe_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 98.0, "Y": 45.0, "Conf": 0.95},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
        player_rows=[],
    )

    observed_rows = layers["observedBall"]["rows"]

    assert len(observed_rows) == 1
    assert observed_rows[0]["X"] == 45.0


def test_build_ball_truth_layers_prefers_tracking_row_on_final_support_aware_tie():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.60},
    ]
    probe_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 24.0, "Y": 34.0, "Conf": 0.60},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
        player_rows=[],
    )

    observed_rows = layers["observedBall"]["rows"]

    assert len(observed_rows) == 1
    assert observed_rows[0]["X"] == 20.0


def test_build_ball_truth_layers_prefers_supported_same_source_candidate_before_confidence():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 96.0, "Y": 6.0, "Conf": 0.95},
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 20.0, "Conf": 0.55},
    ]
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "Track_ID": 7, "X": 22.0, "Y": 20.0, "Conf": 0.9},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=[],
        sample_interval=5,
        player_rows=player_rows,
    )

    observed_rows = layers["observedBall"]["rows"]

    assert len(observed_rows) == 1
    assert observed_rows[0]["X"] == 20.0


def test_build_ball_support_diagnostics_counts_supported_and_unsupported_edge_frames():
    observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 10.0, "Y": 10.0, "Conf": 0.7},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 2.0, "Y": 14.0, "Conf": 0.6},
    ]
    accepted_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 10.0, "Y": 10.0, "Conf": 0.7},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 2.0, "Y": 14.0, "Conf": 0.6},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 50.0, "Conf": 0.5},
    ]
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "X": 18.0, "Y": 10.0},
        {"Frame_ID": 5, "Entity_Type": "player", "X": 30.0, "Y": 30.0},
        {"Frame_ID": 10, "Entity_Type": "player", "X": 55.0, "Y": 50.0},
    ]

    diagnostics = _build_ball_support_diagnostics(observed_rows, accepted_rows, player_rows)

    assert diagnostics == {
        "supportedObservedBallFrames": 1,
        "supportedAcceptedBallFrames": 2,
        "supportedAcceptedBallRatio": 0.667,
        "unsupportedAcceptedEdgeFrames": 1,
    }


def test_build_ball_truth_layers_reports_player_support_diagnostics():
    tracking_observed_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 20.0, "Conf": 0.60},
    ]
    probe_observed_rows = [
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 96.0, "Y": 50.0, "Conf": 0.70},
    ]
    inferred_rows = [
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 30.0, "Y": 30.0, "Conf": 0.40},
    ]
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "Track_ID": 1, "X": 22.0, "Y": 22.0, "Conf": 0.90},
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 2, "X": 31.0, "Y": 31.0, "Conf": 0.90},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        inferred_rows,
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
        player_rows=player_rows,
    )

    assert layers["supportDiagnostics"] == {
        "supportedObservedBallFrames": 1,
        "supportedAcceptedBallFrames": 2,
        "supportedAcceptedBallRatio": 1.0,
        "unsupportedAcceptedEdgeFrames": 0,
    }
    assert layers["directObservationBreakdown"] == {
        "trackingObservedBallFrames": 1,
        "rawProbeObservedBallFrames": 1,
        "filteredProbeObservedBallFrames": 0,
        "suppressedProbeObservedBallFrames": 1,
        "anchoredProbeObservedBallFrames": 0,
        "bridgeProbeObservedBallFrames": 0,
        "probeObservedBallFrames": 0,
        "probeOnlyObservedBallFrames": 0,
        "acceptedFromObservedFrames": 1,
        "acceptedFromObservedRatio": 0.5,
    }


def test_build_ball_truth_layers_applies_edge_share_repair_only_for_target_source():
    tracking_observed_rows = [
        {"Frame_ID": frame_id, "Entity_Type": "ball", "Track_ID": -1, "X": 2.0, "Y": 96.0, "Conf": 0.8}
        for frame_id in range(0, 12)
    ] + [
        {"Frame_ID": frame_id, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 45.0, "Conf": 0.8}
        for frame_id in range(12, 16)
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=[],
        sample_interval=1,
        player_rows=[],
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_edge_run_keep_every_2_min10",
    )

    accepted_rows = layers["acceptedBall"]["rows"]
    frame_ids = [row["Frame_ID"] for row in accepted_rows]

    assert frame_ids == [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15]
    assert layers["edgeShareRepairDiagnostics"] == {
        "applied": True,
        "profileName": "source_robustness_shadow_edge_run_keep_every_2_min10",
        "mode": "uniform_edge_run_thin",
        "keepEvery": 2,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "thinnedEdgeRuns": 1,
        "droppedAcceptedEdgeFrames": 5,
        "retainedAcceptedEdgeFrames": 7,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 5,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 7,
        "sourceClipId": "trimed-5min.mp4",
    }

    control_layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=[],
        sample_interval=1,
        player_rows=[],
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_edge_run_keep_every_2_min10",
    )

    assert [row["Frame_ID"] for row in control_layers["acceptedBall"]["rows"]] == list(range(16))
    assert control_layers["edgeShareRepairDiagnostics"] == {
        "applied": False,
        "profileName": "source_robustness_shadow_edge_run_keep_every_2_min10",
        "mode": "uniform_edge_run_thin",
        "keepEvery": 2,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "thinnedEdgeRuns": 0,
        "droppedAcceptedEdgeFrames": 0,
        "retainedAcceptedEdgeFrames": 0,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 0,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 12,
        "sourceClipId": "trimed-football-2-1minute.mp4",
    }


def test_build_ball_truth_layers_support_guarded_repair_preserves_boundary_supported_and_bridge_frames():
    tracking_observed_rows = [
        {"Frame_ID": frame_id, "Entity_Type": "ball", "Track_ID": -1, "X": 2.0, "Y": 96.0, "Conf": 0.8}
        for frame_id in range(0, 12)
    ]
    player_rows = [
        {"Frame_ID": 4, "Entity_Type": "player", "Track_ID": 7, "X": 2.5, "Y": 95.5, "Conf": 0.9},
        {"Frame_ID": 6, "Entity_Type": "player", "Track_ID": 7, "X": 2.5, "Y": 95.5, "Conf": 0.9},
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=[],
        sample_interval=1,
        player_rows=player_rows,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_supported_edge_run_keep_every_2_min10_guard2",
    )

    accepted_rows = layers["acceptedBall"]["rows"]

    assert [row["Frame_ID"] for row in accepted_rows] == [0, 1, 2, 4, 5, 6, 7, 9, 10, 11]
    assert layers["edgeShareRepairDiagnostics"] == {
        "applied": True,
        "profileName": "source_robustness_shadow_supported_edge_run_keep_every_2_min10_guard2",
        "mode": "support_guarded_thin",
        "keepEvery": 2,
        "minRunLength": 10,
        "guardFrameCount": 2,
        "thinnedEdgeRuns": 1,
        "droppedAcceptedEdgeFrames": 2,
        "retainedAcceptedEdgeFrames": 10,
        "preservedBoundaryFrames": 4,
        "preservedSupportedFrames": 2,
        "preservedBridgeFrames": 1,
        "droppedInteriorUnsupportedFrames": 2,
        "supportedAcceptedBallRatio": 0.2,
        "unsupportedAcceptedEdgeFrames": 8,
        "sourceClipId": "trimed-5min.mp4",
    }


def test_build_ball_truth_layers_touchline_probe_replacement_replaces_supported_edge_run_and_reports_diagnostics():
    frame_ids = list(range(340, 390, 5))
    tracking_observed_rows = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 36.8,
            "Y": 96.9,
            "Conf": 0.9,
        }
        for frame_id in frame_ids
    ]
    probe_observed_rows = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 44.0 + (index * 1.5),
            "Y": 62.0 - (index * 1.2),
            "Conf": 0.2,
        }
        for index, frame_id in enumerate(frame_ids)
    ]
    player_rows = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "player",
            "Track_ID": 7,
            "X": 37.0,
            "Y": 96.2,
            "Conf": 0.95,
        }
        for frame_id in frame_ids
    ]

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=probe_observed_rows,
        sample_interval=5,
        player_rows=player_rows,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_probe_replace_v1",
    )

    accepted_rows = layers["acceptedBall"]["rows"]
    assert [row["Frame_ID"] for row in accepted_rows] == frame_ids
    assert max(float(row["Y"]) for row in accepted_rows) < 70.0
    assert layers["edgeShareRepairDiagnostics"] == {
        "applied": True,
        "profileName": "source_robustness_shadow_touchline_probe_replace_v1",
        "mode": "touchline_probe_replace",
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "thinnedEdgeRuns": 0,
        "droppedAcceptedEdgeFrames": 0,
        "retainedAcceptedEdgeFrames": 10,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 0,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 0,
        "sourceClipId": "trimed-5min.mp4",
    }
    assert layers["sourceConditionedRunReplacementDiagnostics"] == {
        "applied": True,
        "profileName": "source_robustness_shadow_touchline_probe_replace_v1",
        "mode": "touchline_probe_replace",
        "sourceClipId": "trimed-5min.mp4",
        "runsConsidered": 1,
        "runsAccepted": 1,
        "runsRejected": 0,
        "medianReplacementCoverageRatio": 1.0,
        "acceptedCandidateSourceCounts": {"probeObservedBall.filteredRows": 1},
        "replacementRejectionReasonCounts": {},
        "runDiagnostics": [
            {
                "startFrame": 340,
                "endFrame": 385,
                "runLength": 10,
                "edgeHeavyShare": 1.0,
                "playerSupportedShare": 1.0,
                "candidateSourceUsed": "probeObservedBall.filteredRows",
                "candidateFrameCount": 10,
                "replacementCoverageRatio": 1.0,
                "replacementEdgeShareDelta": 1.0,
                "candidateViable": True,
                "candidateNearViable": True,
                "reconnectBeforeOk": True,
                "reconnectAfterOk": True,
                "reconnectOk": True,
                "accepted": True,
                "rejectionReason": None,
            }
        ],
    }


def test_build_ball_truth_layers_carries_source_conditioned_acquisition_diagnostics():
    tracking_observed_rows = [
        {"Frame_ID": frame_id, "Entity_Type": "ball", "Track_ID": -1, "X": 10.0, "Y": 96.0, "Conf": 0.8}
        for frame_id in range(0, 10)
    ]
    acquisition_diagnostics = {
        "applied": True,
        "profileName": "source_robustness_shadow_touchline_acquisition_upgrade_v1",
        "mode": "touchline_acquisition_upgrade",
        "sourceClipId": "trimed-5min.mp4",
        "selectedAcquisitionProfileName": "source_robustness_shadow_touchline_acquisition_upgrade_v1",
        "proposalWindowKindCandidateCounts": {
            "direct_seed_tight": 5,
            "touchline_escape": 5,
        },
        "proposalWindowKindSelectedCounts": {
            "touchline_escape": 4,
        },
        "touchlineEscapeCandidateFrames": 5,
        "touchlineEscapeSelectedFrames": 4,
        "edgeStuckCandidateRejectionCounts": {
            "edge_share_not_improved": 1,
        },
        "repeatedAnchorSuppressionCount": 0,
        "candidateSourceEdgeShareBeforeSelection": 1.0,
        "candidateSourceEdgeShareAfterSelection": 0.4,
    }

    layers = _build_ball_truth_layers(
        tracking_observed_rows,
        [],
        probe_observed_rows=[],
        sample_interval=1,
        player_rows=[],
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_upgrade_v1",
        acquisition_diagnostics=acquisition_diagnostics,
    )

    assert layers["sourceConditionedAcquisitionDiagnostics"] == acquisition_diagnostics
    assert layers["edgeShareRepairDiagnostics"]["applied"] is False
    assert layers["sourceConditionedRunReplacementDiagnostics"]["applied"] is False


@pytest.mark.parametrize(
    "profile_name",
    list(ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES)
    + [
        "source_robustness_shadow_edge_run_keep_every_3_min8",
        "source_robustness_shadow_edge_run_keep_every_4_min6",
        "source_robustness_shadow_supported_edge_run_keep_every_2_min10_guard2",
        "source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2",
        "source_robustness_shadow_supported_edge_run_keep_every_2_min14_guard2",
        "source_robustness_shadow_supported_edge_run_keep_every_3_min14_guard2",
        "source_robustness_shadow_touchline_probe_replace_v1",
        "source_robustness_shadow_touchline_acquisition_upgrade_v1",
        "source_robustness_shadow_touchline_acquisition_reopen_v2",
        "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    ],
)
def test_source_edge_share_repair_catalog_recognizes_active_and_legacy_profiles(profile_name):
    assert run_guerilla._source_edge_share_repair_config(profile_name) == get_source_edge_share_repair_config(profile_name)


def test_select_meaningful_recovered_ball_rows_falls_back_to_non_empty_sparse_rows_when_no_short_segment_is_coherent():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 28.0, "Y": 38.0, "Conf": 0.20},
        {"Frame_ID": 30, "Entity_Type": "ball", "X": 44.0, "Y": 49.0, "Conf": 0.21},
        {"Frame_ID": 60, "Entity_Type": "ball", "X": 61.0, "Y": 58.0, "Conf": 0.22},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [0, 30, 60]
    assert ball_rows_show_meaningful_motion(selected_rows) is True


def test_select_meaningful_recovered_ball_rows_rejects_non_viable_junk_fallback_after_coherent_search():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 12.0, "Y": 96.6, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 18.0, "Y": 96.8, "Conf": 0.21},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 24.0, "Y": 97.0, "Conf": 0.22},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert selected_rows == []


def test_coherent_ball_subchains_stays_bounded_with_noisy_multi_candidate_frames():
    rows = []
    for frame_id in [0, 5, 10, 15, 20]:
        for offset_index, offset in enumerate([0.0, 0.5, 1.0, 1.5]):
            rows.append(
                {
                    "Frame_ID": frame_id,
                    "Entity_Type": "ball",
                    "X": 45.0 + offset,
                    "Y": 50.0 + offset,
                    "Conf": 0.30 - (offset_index * 0.01),
                }
            )

    subchains = _coherent_ball_subchains(rows)

    assert len(subchains) <= len(rows)
    assert all(len(chain) >= 3 for chain in subchains)


def test_build_ball_recovery_experiment_profiles_includes_baseline_and_highres_probe():
    profiles = build_ball_recovery_experiment_profiles(configured_imgsz=1280, configured_conf=0.12)

    assert [profile["name"] for profile in profiles] == [
        "baseline",
        "highres_same_conf",
        "highres_low_conf",
    ]
    assert profiles[0]["settings"] == {"imgsz": 1600, "conf": 0.08}
    assert profiles[1]["settings"] == {"imgsz": 1920, "conf": 0.08}
    assert profiles[2]["settings"] == {"imgsz": 1920, "conf": 0.05}


def test_build_ball_recovery_quality_matrix_profiles_includes_candidate_generation_probes():
    profiles = build_ball_recovery_quality_matrix_profiles()

    assert [profile["name"] for profile in profiles] == [
        "baseline_player_window",
        "width_cap_075",
        "width_cap_06",
        "crop_edge_margin_40",
        "upper_crop_band_075",
        "edge_margin_40_upper_075",
        "edge_margin_40_upper_078",
        "proposal_windows_075",
        "anchor_corridor_width_cap_075",
    ]
    assert profiles[3]["cropEdgeMargin"] == 40
    assert profiles[4]["maxCropCenterYRatio"] == 0.75
    assert profiles[5]["cropEdgeMargin"] == 40
    assert profiles[5]["maxCropCenterYRatio"] == 0.75
    assert profiles[6]["cropEdgeMargin"] == 40
    assert profiles[6]["maxCropCenterYRatio"] == 0.78
    assert profiles[7]["cropMode"] == "proposal_windows"
    assert profiles[7]["proposalMaxWindowsPerFrame"] == 3
    assert profiles[8]["cropMode"] == "anchor_corridor"
    assert profiles[8]["corridorHalfWidthPx"] == 20
    assert all(profile["usePlayerWindows"] is True for profile in profiles)


def test_build_ball_recovery_quality_matrix_profiles_includes_anchor_corridor_profile():
    profiles = build_ball_recovery_quality_matrix_profiles()

    corridor_profiles = [profile for profile in profiles if profile.get("cropMode") == "anchor_corridor"]

    assert len(corridor_profiles) == 1
    assert corridor_profiles[0]["usePlayerWindows"] is True
    assert corridor_profiles[0]["maxCropWidthRatio"] == 0.75


def test_collect_observed_source_anchors_uses_best_ball_row_source_box_centers_per_frame():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Conf": 0.20,
            "Source_X1": 10.0,
            "Source_Y1": 20.0,
            "Source_X2": 30.0,
            "Source_Y2": 40.0,
        },
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Conf": 0.30,
            "Source_X1": 50.0,
            "Source_Y1": 60.0,
            "Source_X2": 70.0,
            "Source_Y2": 80.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "Conf": 0.25,
            "Source_X1": 100.0,
            "Source_Y1": 110.0,
            "Source_X2": 140.0,
            "Source_Y2": 150.0,
        },
    ]

    anchors = collect_observed_source_anchors(rows)

    assert anchors == {
        0: (60.0, 70.0),
        5: (120.0, 130.0),
    }


def test_build_anchor_corridor_crop_window_interpolates_between_neighboring_anchors():
    frame_shape = (200, 200, 3)
    anchors = {
        0: (20.0, 20.0),
        10: (60.0, 60.0),
    }

    crop_window = build_anchor_corridor_crop_window(
        frame_shape,
        frame_id=5,
        observed_source_anchors=anchors,
        player_window=None,
        corridor_half_width_px=10,
        corridor_padding_px=5,
    )

    assert crop_window is not None
    left, top, right, bottom = crop_window
    assert (left + right) / 2.0 == pytest.approx(40.0, abs=1e-6)
    assert (top + bottom) / 2.0 == pytest.approx(40.0, abs=1e-6)
    assert right - left == 30
    assert bottom - top == 30


def test_build_anchor_corridor_crop_window_falls_back_when_anchors_are_missing():
    frame_shape = (200, 200, 3)
    player_window = [40.0, 50.0, 100.0, 140.0]

    no_anchor_window = build_anchor_corridor_crop_window(
        frame_shape,
        frame_id=5,
        observed_source_anchors={},
        player_window=player_window,
        corridor_half_width_px=10,
        corridor_padding_px=5,
    )
    one_anchor_window = build_anchor_corridor_crop_window(
        frame_shape,
        frame_id=5,
        observed_source_anchors={5: (80.0, 90.0)},
        player_window=player_window,
        corridor_half_width_px=10,
        corridor_padding_px=5,
    )

    assert no_anchor_window == ball_recovery_crop_window(frame_shape, player_window)
    assert one_anchor_window is not None
    left, top, right, bottom = one_anchor_window
    assert (left + right) / 2.0 == pytest.approx(80.0, abs=1e-6)
    assert (top + bottom) / 2.0 == pytest.approx(90.0, abs=1e-6)


def test_build_anchor_corridor_crop_windows_by_frame_uses_full_clip_span_and_classifies_anchor_support():
    crop_windows, summary = run_guerilla._build_anchor_corridor_crop_windows_by_frame(
        (200, 200, 3),
        frame_interval=5,
        observed_source_anchors={0: (20.0, 20.0), 5: (40.0, 40.0)},
        player_windows=None,
        frame_count=20,
        corridor_half_width_px=10,
        corridor_padding_px=5,
    )

    assert sorted(crop_windows) == [0, 5, 10, 15]
    assert summary["corridorCandidateFrames"] == 4
    assert summary["corridorFramesWithTwoAnchors"] == 0
    assert summary["corridorFramesWithSingleAnchor"] == 4


def test_profile_recovery_cache_key_distinguishes_generation_time_hygiene():
    shared_settings = {"imgsz": 1600, "conf": 0.08}
    baseline_profile = {
        "name": "baseline_player_window",
        "settings": dict(shared_settings),
        "usePlayerWindows": True,
        "maxCropWidthRatio": 0.75,
    }
    edge_hygiene_profile = {
        "name": "edge_margin_40_upper_078",
        "settings": dict(shared_settings),
        "usePlayerWindows": True,
        "maxCropWidthRatio": 0.75,
        "cropEdgeMargin": 40,
        "maxCropCenterYRatio": 0.78,
    }

    assert run_guerilla._profile_recovery_cache_key(baseline_profile) != run_guerilla._profile_recovery_cache_key(
        edge_hygiene_profile
    )


def test_profile_recovery_cache_key_distinguishes_direct_seed_retry_policy():
    shared_settings = {"imgsz": 1600, "conf": 0.08}
    baseline_profile = {
        "name": "proposal_windows_075",
        "settings": dict(shared_settings),
        "usePlayerWindows": True,
        "cropMode": "proposal_windows",
        "maxCropWidthRatio": 0.35,
        "proposalMaxWindowsPerFrame": 3,
        "proposalCropWidthRatio": 0.35,
        "proposalCropPaddingPx": run_guerilla.PLAYER_PROPOSAL_CROP_PADDING_PX,
        "directSeedRetryPolicy": "single_retry_960",
        "directSeedRetryScales": [1600, 960],
    }
    fallback_profile = {
        **baseline_profile,
        "directSeedRetryPolicy": "bounded_multiscale_fallback",
        "directSeedRetryScales": [1600, 960, 1920],
    }

    assert run_guerilla._profile_recovery_cache_key(baseline_profile) != run_guerilla._profile_recovery_cache_key(
        fallback_profile
    )


def test_build_player_proposal_crop_windows_uses_truth_seed_rows_as_anchor_windows(tmp_path):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "acceptedBallSeedRows": [
                    {
                        "candidateFrameId": "seed-10",
                        "windowId": "window-a",
                        "frameId": 10,
                        "row": {
                            "Frame_ID": 10,
                            "X": 44.0,
                            "Y": 44.0,
                            "Source_X1": 40.0,
                            "Source_Y1": 50.0,
                            "Source_X2": 50.0,
                            "Source_Y2": 60.0,
                        },
                    },
                    {
                        "candidateFrameId": "seed-15",
                        "windowId": "window-a",
                        "frameId": 15,
                        "row": {
                            "Frame_ID": 15,
                            "X": 45.0,
                            "Y": 45.0,
                            "Source_X1": 80.0,
                            "Source_Y1": 90.0,
                            "Source_X2": 90.0,
                            "Source_Y2": 100.0,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (200, 200, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=20,
        max_proposals_per_frame=4,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1",
        proposal_selection_truth_seed_path=str(seed_path),
    )

    assert sorted(crop_windows) == [10, 15]
    assert all(spec["proposalWindowKind"] == "direct_seed_tight" for specs in crop_windows.values() for spec in specs)
    assert all(spec["proposalSeedMode"] == "truth_seed" for specs in crop_windows.values() for spec in specs)
    assert summary["proposalCropGeometryFixTruthSeedFrames"] == 2
    assert summary["proposalCropGeometryFixUsedFrames"] == 2
    assert summary["proposalDirectSeedTightWindowFrames"] == 2


def test_build_player_proposal_crop_windows_uses_reviewed_positive_anchor_seed(tmp_path):
    seed_path = tmp_path / "reviewed_positive_anchor_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-240",
                        "frameIndex": 240,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 360.0,
                            "y1": 660.0,
                            "x2": 420.0,
                            "y2": 700.0,
                        },
                        "sourceCenter": {"x": 390.0, "y": 680.0},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (720, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=330,
        max_proposals_per_frame=3,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1"
        ),
        reviewed_positive_anchor_seed_path=str(seed_path),
    )

    assert sorted(crop_windows) == [240]
    assert crop_windows[240][0]["proposalWindowKind"] == "reviewed_positive_anchor"
    assert crop_windows[240][0]["proposalSeedMode"] == "reviewed_positive_anchor"
    assert crop_windows[240][0]["reviewedPositiveAnchorFrame"] is True
    assert summary["reviewedPositiveAnchorSeedFrames"] == 1
    assert summary["reviewedPositiveAnchorWindowFrames"] == 1
    assert summary["reviewedPositiveAnchorSkippedNonTargetFrames"] == 0


def test_build_player_proposal_crop_windows_uses_audit_context_windows_for_scale_fix(tmp_path):
    seed_path = tmp_path / "reviewed_positive_anchor_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-240",
                        "frameIndex": 240,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 360.0,
                            "y1": 660.0,
                            "x2": 420.0,
                            "y2": 700.0,
                        },
                        "sourceCenter": {"x": 390.0, "y": 680.0},
                    }
                ],
                "refutedSeeds": [
                    {"frameIndex": 245, "reviewDecision": "reject_seed"},
                ],
            }
        ),
        encoding="utf-8",
    )

    config = get_source_edge_share_repair_config(
        "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1"
    )
    assert config["reviewedPositiveProposalGenerationFixEnabled"] is True
    assert config["reviewedPositiveProposalGenerationFixContextRatios"] == [1.0, 4.0, 8.0]
    assert config["reviewedPositiveProposalGenerationFixRetryScales"] == [640, 960, 1600]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (720, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=330,
        max_proposals_per_frame=3,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1"
        ),
        reviewed_positive_anchor_seed_path=str(seed_path),
    )

    assert sorted(crop_windows) == [240]
    kinds = [spec["proposalWindowKind"] for spec in crop_windows[240]]
    assert kinds == [
        "reviewed_positive_audit_context_1",
        "reviewed_positive_audit_context_4",
        "reviewed_positive_audit_context_8",
    ]
    assert all(spec["proposalSeedMode"] == "reviewed_positive_anchor" for spec in crop_windows[240])
    assert all(spec["reviewedPositiveAnchorFrame"] is True for spec in crop_windows[240])
    assert all(spec["reviewedPositiveAuditContextWindow"] is True for spec in crop_windows[240])
    assert all(spec["reviewedPositiveSourceBBox"] for spec in crop_windows[240])
    assert summary["reviewedPositiveAnchorSeedFrames"] == 1
    assert summary["reviewedPositiveAnchorWindowFrames"] == 3
    assert summary["reviewedPositiveAuditContextWindowFrames"] == 3
    assert summary["reviewedPositiveAnchorSkippedNonTargetFrames"] == 0


def test_build_player_proposal_crop_windows_prioritizes_audit_best_crop_for_scale_fix_v2(tmp_path, monkeypatch):
    seed_path = tmp_path / "reviewed_positive_anchor_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-255",
                        "frameIndex": 255,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 414.0,
                            "y1": 668.0,
                            "x2": 432.0,
                            "y2": 685.0,
                        },
                        "sourceCenter": {"x": 423.0, "y": 676.5},
                    }
                ],
                "refutedSeeds": [],
            }
        ),
        encoding="utf-8",
    )
    audit_path = tmp_path / "reviewed_positive_crop_reinference_matrix.json"
    audit_path.write_text(
        json.dumps(
            {
                "reviewedPositiveCropRows": [
                    {
                        "frameIndex": 255,
                        "diagnosticClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                        "bestAttempt": {
                            "contextRatio": 8.0,
                            "imgsz": 960,
                            "cropWindow": [351, 608, 495, 744],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    config = get_source_edge_share_repair_config(
        "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v2"
    )
    assert config["reviewedPositiveProposalGenerationFixRetryScales"] == [1600, 640, 960]
    assert config["reviewedPositiveProposalGenerationFixUseAuditBestAttempts"] is True
    config["reviewedPositiveProposalGenerationFixAuditMatrixPath"] = str(audit_path)
    monkeypatch.setattr(run_guerilla, "_source_edge_share_repair_config", lambda _: config)

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (720, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=330,
        max_proposals_per_frame=3,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v2"
        ),
        reviewed_positive_anchor_seed_path=str(seed_path),
    )

    kinds = [spec["proposalWindowKind"] for spec in crop_windows[255]]
    assert kinds[0] == "reviewed_positive_audit_best_context_8_scale_960"
    assert crop_windows[255][0]["window"] == (351, 608, 495, 720)
    assert crop_windows[255][0]["reviewedPositiveAuditBestAttemptWindow"] is True
    assert crop_windows[255][0]["reviewedPositiveAuditBestAttemptImgSz"] == 960
    assert summary["reviewedPositiveAuditBestAttemptWindowFrames"] == 1


def test_residual_reviewed_positive_profile_excludes_already_accepted_frames(tmp_path, monkeypatch):
    seed_path = tmp_path / "reviewed_positive_anchor_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-250",
                        "frameIndex": 250,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 406.0,
                            "y1": 678.0,
                            "x2": 423.0,
                            "y2": 693.0,
                        },
                    },
                    {
                        "reviewItemId": "positive-275",
                        "frameIndex": 275,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 467.0,
                            "y1": 643.0,
                            "x2": 486.0,
                            "y2": 661.0,
                        },
                    },
                ],
                "refutedSeeds": [{"frameIndex": 260, "reviewDecision": "reject_seed"}],
            }
        ),
        encoding="utf-8",
    )
    audit_path = tmp_path / "reviewed_positive_crop_reinference_matrix.json"
    audit_path.write_text(
        json.dumps(
            {
                "reviewedPositiveCropRows": [
                    {
                        "frameIndex": 275,
                        "diagnosticClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                        "bestAttempt": {
                            "contextRatio": 8.0,
                            "imgsz": 640,
                            "cropWindow": [400, 580, 552, 724],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1"
    config = get_source_edge_share_repair_config(profile_name)
    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    assert config["reviewedPositiveProposalGenerationFixEnabled"] is True
    assert config["reviewedPositiveProposalGenerationFixRetryScales"] == [
        640,
        960,
        1280,
        1600,
        1920,
    ]
    assert config["reviewedPositiveProposalGenerationFixExcludeFrameIds"] == [
        250,
        255,
        260,
        265,
        270,
    ]
    config["reviewedPositiveProposalGenerationFixAuditMatrixPath"] = str(audit_path)
    monkeypatch.setattr(run_guerilla, "_source_edge_share_repair_config", lambda _: config)

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (720, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=330,
        max_proposals_per_frame=3,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
        reviewed_positive_anchor_seed_path=str(seed_path),
    )

    assert sorted(crop_windows) == [275]
    assert crop_windows[275][0]["proposalWindowKind"] == "reviewed_positive_audit_best_context_8_scale_640"
    assert summary["reviewedPositiveAnchorSkippedExcludedFrames"] == 1
    assert summary["reviewedPositiveAnchorUsedFrames"] == 1


def test_build_player_proposal_crop_windows_ignores_reviewed_positive_anchor_seed_for_non_target_clip(tmp_path):
    seed_path = tmp_path / "reviewed_positive_anchor_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-240",
                        "frameIndex": 240,
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {
                            "x1": 381.0,
                            "y1": 688.0,
                            "x2": 397.0,
                            "y2": 704.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (720, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=330,
        max_proposals_per_frame=3,
        source_clip_id="comparison.mp4",
        edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1"
        ),
        reviewed_positive_anchor_seed_path=str(seed_path),
    )

    assert crop_windows == {}
    assert summary["reviewedPositiveAnchorSeedFrames"] == 0


def test_build_player_proposal_crop_windows_ignores_truth_seed_rows_for_non_target_clip(tmp_path):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "acceptedBallSeedRows": [
                    {
                        "candidateFrameId": "seed-10",
                        "windowId": "window-a",
                        "frameId": 10,
                        "row": {
                            "Frame_ID": 10,
                            "X": 44.0,
                            "Y": 44.0,
                            "Source_X1": 40.0,
                            "Source_Y1": 50.0,
                            "Source_X2": 50.0,
                            "Source_Y2": 60.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (200, 200, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=20,
        max_proposals_per_frame=4,
        source_clip_id="comparison.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1",
        proposal_selection_truth_seed_path=str(seed_path),
    )

    assert crop_windows == {}
    assert summary["proposalCropGeometryFixTruthSeedFrames"] == 0


def test_build_player_proposal_crop_windows_expands_truth_seed_windows_for_attempt_two(tmp_path):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "acceptedBallSeedRows": [
                    {
                        "candidateFrameId": "seed-10",
                        "windowId": "window-a",
                        "frameId": 10,
                        "row": {
                            "Frame_ID": 10,
                            "X": 44.0,
                            "Y": 44.0,
                            "Source_X1": 40.0,
                            "Source_Y1": 50.0,
                            "Source_X2": 50.0,
                            "Source_Y2": 60.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    baseline_windows, baseline_summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (352, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=20,
        max_proposals_per_frame=4,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1",
        proposal_selection_truth_seed_path=str(seed_path),
    )
    expanded_windows, expanded_summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (352, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=20,
        max_proposals_per_frame=4,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2",
        proposal_selection_truth_seed_path=str(seed_path),
    )

    assert sorted(baseline_windows) == [10]
    assert sorted(expanded_windows) == [10]
    assert expanded_summary["proposalCropGeometryFixCropWidthRatio"] > baseline_summary[
        "proposalCropGeometryFixCropWidthRatio"
    ]
    assert expanded_summary["proposalMeanWindowWidth"] > baseline_summary["proposalMeanWindowWidth"]
    assert expanded_summary["proposalCropGeometryFixUsedFrames"] == 1


def test_proposal_crop_geometry_attempt_three_combines_expanded_windows_with_seed_viability_admission(tmp_path):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "acceptedBallSeedRows": [
                    {
                        "candidateFrameId": "seed-10",
                        "windowId": "window-a",
                        "frameId": 10,
                        "row": {
                            "Frame_ID": 10,
                            "X": 44.0,
                            "Y": 44.0,
                            "Source_X1": 40.0,
                            "Source_Y1": 50.0,
                            "Source_X2": 50.0,
                            "Source_Y2": 60.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        (352, 1280, 3),
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={},
        frame_count=20,
        max_proposals_per_frame=4,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3",
        proposal_selection_truth_seed_path=str(seed_path),
    )
    admission_config = run_guerilla._touchline_support_viability_admission_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3",
    )

    assert sorted(crop_windows) == [10]
    assert summary["proposalCropGeometryFixCropWidthRatio"] == 0.5
    assert summary["proposalMeanWindowWidth"] > 140
    assert admission_config["approachFamily"] == "viability_neutral_seed_window"
    assert admission_config["truthSeedPath"]


def test_selection_segment_viability_profile_selects_real_seed_proposal_rows():
    rows = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "X": 45.0 + index,
            "Y": 34.0,
            "Conf": 0.41,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "truth_seed",
        }
        for index, frame_id in enumerate([10, 15, 20])
    ]

    assert run_guerilla.select_meaningful_recovered_ball_rows(rows) == []

    selected = run_guerilla.select_meaningful_recovered_ball_rows(
        rows,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1",
    )

    assert [row["Frame_ID"] for row in selected] == [10, 15, 20]


def test_selection_segment_viability_profile_rejects_edge_heavy_rows():
    rows = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "X": 1.0,
            "Y": 34.0,
            "Conf": 0.41,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "truth_seed",
        }
        for frame_id in [10, 15, 20]
    ]

    selected = run_guerilla.select_meaningful_recovered_ball_rows(
        rows,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1",
    )

    assert selected == []


def _reviewed_positive_segment_rows(**overrides):
    rows = []
    for index, frame_id in enumerate([250, 255, 260, 265, 270]):
        row = {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "X": 42.0,
            "Y": 34.0,
            "Conf": 0.41,
            "ProposalWindowKind": "reviewed_positive_audit_context_8",
            "ProposalSeedMode": "reviewed_positive_anchor",
            "Source_X1": 100.0 + index,
            "Source_Y1": 110.0,
            "Source_X2": 106.0 + index,
            "Source_Y2": 116.0,
            "ProposalSeedCenterX": 103.0 + index,
            "ProposalSeedCenterY": 113.0,
        }
        row.update(overrides)
        rows.append(row)
    return rows


def test_reviewed_positive_selected_segment_profile_selects_only_reviewed_positive_rows():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    rows = _reviewed_positive_segment_rows()

    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    config = get_source_edge_share_repair_config(profile_name)
    assert config is not None
    assert config["reviewedPositiveSelectedSegmentFixEnabled"] is True
    assert run_guerilla.select_meaningful_recovered_ball_rows(rows) == []

    config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=config,
    )

    assert [row["Frame_ID"] for row in selected] == [250, 255, 260, 265, 270]


def test_reviewed_positive_selected_segment_profile_rejects_non_reviewed_and_non_target_rows():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    non_reviewed_rows = _reviewed_positive_segment_rows(
        ProposalWindowKind="direct_seed_tight",
        ProposalSeedMode="truth_seed",
    )

    assert (
        run_guerilla.select_meaningful_recovered_ball_rows(
            non_reviewed_rows,
            source_clip_id="trimed-5min.mp4",
            edge_share_repair_profile=profile_name,
        )
        == []
    )
    assert (
        run_guerilla.select_meaningful_recovered_ball_rows(
            _reviewed_positive_segment_rows(),
            source_clip_id="other.mp4",
            edge_share_repair_profile=profile_name,
        )
        == []
    )


def test_reviewed_positive_selected_segment_profile_preserves_safety_guards():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    synthetic_rows = _reviewed_positive_segment_rows(SyntheticBallRow=True)
    edge_rows = _reviewed_positive_segment_rows(X=1.0, Y=34.0)
    repeated_anchor_rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        Source_X1=100.0,
        Source_Y1=110.0,
        Source_X2=106.0,
        Source_Y2=116.0,
        ProposalSeedCenterX=103.0,
        ProposalSeedCenterY=113.0,
    )

    for rows in (synthetic_rows, edge_rows, repeated_anchor_rows):
        assert (
            run_guerilla.select_meaningful_recovered_ball_rows(
                rows,
                source_clip_id="trimed-5min.mp4",
                edge_share_repair_profile=profile_name,
            )
            == []
        )


def test_reviewed_positive_selected_segment_profile_records_edge_share_gate_trace():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    rows = _reviewed_positive_segment_rows(X=1.0, Y=34.0, ProposalSeedX=250.0, ProposalSeedY=113.0)

    config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=config,
    )
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": False,
                "candidateRows": rows,
                "candidateSummary": {
                    "uniqueFrames": 5,
                    "proposalCandidateFrames": 5,
                    "proposalCollapsedFrames": 5,
                },
                "selectedRows": selected,
                "selectedSummary": {"frames": 0, "segmentCount": 0},
            }
        ],
        selected_profile_name=None,
    )

    diagnostics = matrix["profiles"][0]["proposalFrameDiagnostics"]
    assert selected == []
    assert len(diagnostics) == 5
    assert {row["selectionGateTrace"]["edgeShareRejected"] for row in diagnostics} == {True}
    assert {row["selectionGateTrace"]["reviewedPositiveLineageMatch"] for row in diagnostics} == {True}
    assert {row["selectionGateTrace"]["edgeShareForSegment"] for row in diagnostics} == {1.0}


def test_reviewed_positive_edge_share_override_selects_reviewed_positive_edge_segment_only():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1"
    rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        ProposalSeedX=250.0,
        ProposalSeedY=113.0,
    )

    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    config = get_source_edge_share_repair_config(profile_name)
    assert config is not None
    assert config["reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate"] is True

    selected_config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=selected_config,
    )
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": False,
                "candidateRows": rows,
                "candidateSummary": {
                    "uniqueFrames": 5,
                    "proposalCandidateFrames": 5,
                    "proposalCollapsedFrames": 5,
                },
                "selectedRows": selected,
                "selectedSummary": {"frames": len(selected), "segmentCount": 1 if selected else 0},
            }
        ],
        selected_profile_name="proposal_windows_075" if selected else None,
    )

    diagnostics = matrix["profiles"][0]["proposalFrameDiagnostics"]
    assert [row["Frame_ID"] for row in selected] == [250, 255, 260, 265, 270]
    assert {row["selectionGateTrace"]["edgeShareOverrideApplied"] for row in diagnostics} == {True}
    assert {row["selectionGateTrace"]["edgeShareRejected"] for row in diagnostics} == {False}
    assert {row["selectionGateTrace"]["reviewedPositiveLineageMatch"] for row in diagnostics} == {True}
    assert {row["selectionGateTrace"]["edgeShareForSegment"] for row in diagnostics} == {1.0}


def test_reviewed_positive_edge_share_override_preserves_lineage_and_safety_guards():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1"
    non_reviewed_rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        ProposalWindowKind="direct_seed_tight",
        ProposalSeedMode="truth_seed",
    )
    synthetic_rows = _reviewed_positive_segment_rows(X=1.0, Y=34.0, SyntheticBallRow=True)
    repeated_anchor_rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        Source_X1=100.0,
        Source_Y1=110.0,
        Source_X2=106.0,
        Source_Y2=116.0,
        ProposalSeedCenterX=103.0,
        ProposalSeedCenterY=113.0,
    )

    for rows in (non_reviewed_rows, synthetic_rows, repeated_anchor_rows):
        selected_config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
            source_clip_id="trimed-5min.mp4",
            edge_share_repair_profile=profile_name,
        )
        assert (
            run_guerilla._select_reviewed_positive_selected_segment_rows(
                rows,
                config=selected_config,
            )
            == []
        )

    assert (
        run_guerilla.select_meaningful_recovered_ball_rows(
            _reviewed_positive_segment_rows(X=1.0, Y=34.0),
            source_clip_id="other.mp4",
            edge_share_repair_profile=profile_name,
        )
        == []
    )


def test_reviewed_positive_acceptance_profile_accepts_selected_real_reviewed_positive_rows_only():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_acceptance_profile_v1"
    rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        ProposalSeedX=250.0,
        ProposalSeedY=113.0,
    )

    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    config = get_source_edge_share_repair_config(profile_name)
    assert config is not None
    assert config["reviewedPositiveAcceptanceProfileEnabled"] is True
    assert config["reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate"] is True

    selected_config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=selected_config,
    )

    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        selected,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    ) == {
        "accepted": True,
        "reason": "reviewed_positive_viability_override",
    }
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        selected,
        source_clip_id="other.mp4",
        edge_share_repair_profile=profile_name,
    )["accepted"] is False
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        _reviewed_positive_segment_rows(ProposalWindowKind="direct_seed_tight"),
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )["accepted"] is False
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        _reviewed_positive_segment_rows(SyntheticBallRow=True),
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )["accepted"] is False
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        _reviewed_positive_segment_rows(
            Source_X1=100.0,
            Source_Y1=110.0,
            Source_X2=106.0,
            Source_Y2=116.0,
            ProposalSeedCenterX=103.0,
            ProposalSeedCenterY=113.0,
        ),
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )["accepted"] is False


def test_residual_segment_selection_microfix_selects_only_four_residual_frames():
    profile_name = "source_robustness_shadow_promoted_v6_residual_segment_selection_microfix_v1"
    rows = []
    for index, frame_id in enumerate([250, 255, 260, 265, 270, 305, 310, 315, 320]):
        rows.append(
            {
                "Frame_ID": frame_id,
                "Entity_Type": "ball",
                "X": 42.0 + (index * 0.25),
                "Y": 34.0,
                "Conf": 0.41,
                "ProposalWindowKind": "reviewed_positive_audit_context_12",
                "ProposalSeedMode": "reviewed_positive_anchor",
                "Source_X1": 100.0 + index,
                "Source_Y1": 110.0,
                "Source_X2": 106.0 + index,
                "Source_Y2": 116.0,
                "ProposalSeedCenterX": 103.0 + index,
                "ProposalSeedCenterY": 113.0,
            }
        )

    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    config = get_source_edge_share_repair_config(profile_name)
    assert config["reviewedPositiveSelectedSegmentFixMinSegmentFrames"] == 4
    assert config["reviewedPositiveSelectedSegmentFixFrameIds"] == [305, 310, 315, 320]
    assert config["reviewedPositiveAcceptanceProfileMinSelectedFrames"] == 4

    selected_config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=selected_config,
    )

    assert [row["Frame_ID"] for row in selected] == [305, 310, 315, 320]
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        selected,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    ) == {
        "accepted": True,
        "reason": "reviewed_positive_viability_override",
    }
    assert {
        rows[index]["selectionGateTrace"]["selectedProfileRankingRejected"]
        for index in range(5)
    } == {True}


def test_global_reachable_acceptance_probe_selects_only_baseline_aligned_reachable_frames():
    profile_name = "source_robustness_shadow_promoted_v6_global_reachable_acceptance_probe_v1"
    rows = []
    frame_ids = [250, 255, 260, 265, 270, 275, 280, 285, 305]
    for index, frame_id in enumerate(frame_ids):
        rows.append(
            {
                "Frame_ID": frame_id,
                "Entity_Type": "ball",
                "X": 36.0 + (index * 0.2),
                "Y": 94.0,
                "Conf": 0.41,
                "ProposalWindowKind": "reviewed_positive_audit_context_8",
                "ProposalSeedMode": "reviewed_positive_anchor",
                "Source_X1": 450.0 + index,
                "Source_Y1": 650.0,
                "Source_X2": 462.0 + index,
                "Source_Y2": 662.0,
            }
        )

    assert profile_name not in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    config = get_source_edge_share_repair_config(profile_name)
    assert config["reviewedPositiveSelectedSegmentFixFrameIds"] == [255, 260, 265, 270, 275, 280, 285]
    assert config["reviewedPositiveSelectedSegmentFixMinSegmentFrames"] == 7
    assert config["reviewedPositiveAcceptanceProfileMinSelectedFrames"] == 7

    selected_config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=selected_config,
    )

    assert [row["Frame_ID"] for row in selected] == [255, 260, 265, 270, 275, 280, 285]
    assert rows[0]["selectionGateTrace"]["selectedProfileRankingRejected"] is True
    assert rows[-1]["selectionGateTrace"]["selectedProfileRankingRejected"] is True
    assert run_guerilla._reviewed_positive_acceptance_profile_accepts_rows(
        selected,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    ) == {
        "accepted": True,
        "reason": "reviewed_positive_viability_override",
    }


def test_recovery_profile_matrix_marks_reviewed_positive_acceptance_override():
    rows = _reviewed_positive_segment_rows(
        X=1.0,
        Y=34.0,
        ProposalSeedX=250.0,
        ProposalSeedY=113.0,
    )
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": True,
                "reviewedPositiveAcceptanceProfileAccepted": True,
                "reviewedPositiveAcceptanceProfileReason": "reviewed_positive_viability_override",
                "candidateRows": rows,
                "candidateSummary": {
                    "uniqueFrames": 5,
                    "proposalCandidateFrames": 5,
                    "proposalCollapsedFrames": 5,
                },
                "selectedRows": rows,
                "selectedSummary": {"frames": len(rows), "segmentCount": 1},
            }
        ],
        selected_profile_name="proposal_windows_075",
    )

    diagnostics = matrix["profiles"][0]["proposalFrameDiagnostics"]
    assert {row["accepted"] for row in diagnostics} == {True}
    assert {
        row["acceptanceGateTrace"]["viabilityOverrideApplied"] for row in diagnostics
    } == {True}
    assert {
        row["acceptanceGateTrace"]["acceptedByReviewedPositiveProfile"] for row in diagnostics
    } == {True}
    assert {
        row["acceptanceGateTrace"]["acceptanceRejectionReason"] for row in diagnostics
    } == {"accepted_by_reviewed_positive_profile"}


def test_reviewed_positive_selected_segment_profile_records_continuity_gate_trace():
    profile_name = "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    rows = _reviewed_positive_segment_rows()
    for row, x in zip(rows, [20.0, 50.0, 80.0, 50.0, 20.0], strict=False):
        row["X"] = x
        row["Y"] = 34.0

    config = run_guerilla._touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=profile_name,
    )
    selected = run_guerilla._select_reviewed_positive_selected_segment_rows(
        rows,
        config=config,
    )
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": False,
                "candidateRows": rows,
                "candidateSummary": {
                    "uniqueFrames": 5,
                    "proposalCandidateFrames": 5,
                    "proposalCollapsedFrames": 5,
                },
                "selectedRows": selected,
                "selectedSummary": {"frames": 0, "segmentCount": 0},
            }
        ],
        selected_profile_name=None,
    )

    diagnostics = matrix["profiles"][0]["proposalFrameDiagnostics"]
    assert selected == []
    assert {row["selectionGateTrace"]["continuityRejected"] for row in diagnostics} == {True}
    assert {row["selectionGateTrace"]["edgeShareRejected"] for row in diagnostics} == {False}


def test_run_ball_recovery_experiment_applies_profile_hygiene_during_generation(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    recover_calls = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def release(self):
            return True

    def fake_recover_ball_rows(*_args, **kwargs):
        recover_calls.append(
            (
                int(kwargs["crop_edge_margin"]),
                float(kwargs["max_crop_center_y_ratio"]),
            )
        )
        if kwargs["crop_edge_margin"] == 0 and kwargs["max_crop_center_y_ratio"] == 0.0:
            return [
                {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.31},
            ]
        return []

    profiles = [
        {
            "name": "baseline_player_window",
            "settings": {"imgsz": 1600, "conf": 0.08},
            "usePlayerWindows": True,
            "maxCropWidthRatio": 0.75,
        },
        {
            "name": "edge_margin_40_upper_078",
            "settings": {"imgsz": 1600, "conf": 0.08},
            "usePlayerWindows": True,
            "maxCropWidthRatio": 0.75,
            "cropEdgeMargin": 40,
            "maxCropCenterYRatio": 0.78,
        },
    ]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla, "filter_recovered_ball_rows_for_profile", lambda rows, *_args, **_kwargs: list(rows))
    monkeypatch.setattr(run_guerilla, "suppress_repeated_false_ball_clusters", lambda rows, **_kwargs: list(rows))
    monkeypatch.setattr(run_guerilla, "select_meaningful_recovered_ball_rows", lambda rows, **_kwargs: list(rows))

    results = run_guerilla.run_ball_recovery_experiment(
        "/fake/video.mp4",
        model=object(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=5.0,
        frame_interval=1,
        imgsz=1600,
        conf=0.08,
        player_windows={0: [10.0, 10.0, 50.0, 50.0]},
        profiles=profiles,
    )

    assert recover_calls == [(0, 0.0), (40, 0.78)]
    assert [len(result["candidateRows"]) for result in results] == [1, 0]


def test_collect_player_windows_from_rows_aggregates_player_boxes_per_frame():
    rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Source_X1": 100.0,
            "Source_Y1": 200.0,
            "Source_X2": 160.0,
            "Source_Y2": 320.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Source_X1": 80.0,
            "Source_Y1": 240.0,
            "Source_X2": 180.0,
            "Source_Y2": 300.0,
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "player",
            "Source_X1": 300.0,
            "Source_Y1": 100.0,
            "Source_X2": 340.0,
            "Source_Y2": 240.0,
        },
    ]

    windows = collect_player_windows_from_rows(rows)

    assert windows == {
        10: [80.0, 200.0, 180.0, 320.0],
        15: [300.0, 100.0, 340.0, 240.0],
    }


def test_build_player_proposal_crop_windows_by_frame_prefers_anchor_near_boxes():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 5,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.61,
            "Source_X1": 60.0,
            "Source_Y1": 90.0,
            "Source_X2": 80.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.61,
            "Source_X1": 120.0,
            "Source_Y1": 90.0,
            "Source_X2": 140.0,
            "Source_Y2": 110.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={5: (130.0, 100.0)},
        frame_count=10,
        max_proposals_per_frame=2,
        proposal_crop_width_ratio=0.35,
    )

    assert summary["proposalCandidateFrames"] == 2
    assert summary["proposalWindowCount"] == 3
    assert summary["proposalFramesWithAnchorSeed"] == 1
    assert summary["proposalFramesWithoutAnchorSeed"] == 1
    assert summary["proposalDirectSeedWindowFrames"] == 2
    assert summary["proposalDirectSeedTightWindowFrames"] == 2
    assert summary["proposalDirectSeedContextWindowFrames"] == 0
    assert summary["proposalPlayerRankedWindowFrames"] == 1
    assert crop_windows[0][0]["proposalWindowKind"] == "direct_seed_tight"
    assert len(crop_windows[5]) == 2
    ranked_window = next(
        spec["window"] for spec in crop_windows[5] if spec["proposalWindowKind"] == "player_ranked"
    )
    ranked_left, ranked_top, ranked_right, ranked_bottom = ranked_window
    ranked_center_x = (ranked_left + ranked_right) / 2.0
    assert ranked_center_x < 100.0
    assert ranked_top < ranked_bottom


def test_build_player_proposal_crop_windows_by_frame_is_deterministic_on_ties():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 5,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.55,
            "Source_X1": 60.0,
            "Source_Y1": 90.0,
            "Source_X2": 80.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.55,
            "Source_X1": 120.0,
            "Source_Y1": 90.0,
            "Source_X2": 140.0,
            "Source_Y2": 110.0,
        },
    ]

    crop_windows, _summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={5: (100.0, 100.0)},
        frame_count=10,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    context_windows = [
        spec["window"] for spec in crop_windows[5] if spec["proposalWindowKind"] == "direct_seed_context"
    ]
    assert len(context_windows) == 1
    first_left, _first_top, first_right, _first_bottom = context_windows[0]
    assert (first_left + first_right) / 2.0 < 100.0


@pytest.mark.parametrize(
    ("frame_id", "observed_source_anchors", "frame_interval", "expected_mode"),
    [
        (10, {10: (100.0, 100.0)}, 5, "exact"),
        (5, {0: (20.0, 20.0), 10: (40.0, 40.0)}, 5, "interpolated"),
        (15, {5: (60.0, 60.0)}, 5, "single"),
        (40, {0: (20.0, 20.0)}, 5, "none"),
    ],
)
def test_player_proposal_seed_mode_classification(frame_id, observed_source_anchors, frame_interval, expected_mode):
    _center_x, _center_y, seed_mode = run_guerilla._player_proposal_seed_center_and_mode(
        frame_id,
        observed_source_anchors,
        frame_interval=frame_interval,
    )

    assert seed_mode == expected_mode


def test_player_proposal_seed_mode_rejects_wide_interpolation_gap_and_distant_single_anchor():
    interpolated_center = run_guerilla._player_proposal_seed_center_and_mode(
        20,
        {0: (20.0, 20.0), 40: (80.0, 80.0)},
        frame_interval=5,
    )
    single_center = run_guerilla._player_proposal_seed_center_and_mode(
        20,
        {0: (20.0, 20.0)},
        frame_interval=5,
    )

    assert interpolated_center[2] == "none"
    assert single_center[2] == "none"


def test_build_player_proposal_crop_windows_by_frame_uses_players_when_seed_expires():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 20,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.91,
            "Source_X1": 60.0,
            "Source_Y1": 90.0,
            "Source_X2": 80.0,
            "Source_Y2": 110.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={0: (20.0, 20.0)},
        frame_count=25,
        max_proposals_per_frame=1,
        proposal_crop_width_ratio=0.35,
    )

    assert crop_windows[20][0]["proposalWindowKind"] == "player_ranked"
    assert crop_windows[20][0]["proposalSeedMode"] == "none"
    assert "proposalSeedCenter" not in crop_windows[20][0]
    assert summary["proposalCandidateFrames"] == 4
    assert summary["proposalWindowCount"] == 4
    assert summary["proposalExactSeedFrames"] == 1
    assert summary["proposalInterpolatedSeedFrames"] == 0
    assert summary["proposalSingleSeedFrames"] == 2
    assert summary["proposalUnseededFrames"] == 2


def test_build_player_proposal_crop_windows_by_frame_prefers_lower_seed_distance_over_higher_confidence_incoherent_candidate():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.31,
            "Source_X1": 42.0,
            "Source_Y1": 42.0,
            "Source_X2": 62.0,
            "Source_Y2": 82.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.98,
            "Source_X1": 120.0,
            "Source_Y1": 120.0,
            "Source_X2": 140.0,
            "Source_Y2": 180.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (50.0, 60.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert summary["proposalExactSeedFrames"] == 1
    assert summary["proposalWindowCount"] == 5
    direct_window = next(spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_tight")
    ranked_window = next(spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "player_ranked")
    first_left, first_top, first_right, first_bottom = direct_window
    second_left, second_top, second_right, second_bottom = ranked_window
    first_center = ((first_left + first_right) / 2.0, (first_top + first_bottom) / 2.0)
    second_center = ((second_left + second_right) / 2.0, (second_top + second_bottom) / 2.0)
    seed_center = (50.0, 60.0)
    first_distance = ((first_center[0] - seed_center[0]) ** 2 + (first_center[1] - seed_center[1]) ** 2) ** 0.5
    second_distance = ((second_center[0] - seed_center[0]) ** 2 + (second_center[1] - seed_center[1]) ** 2) ** 0.5

    assert first_distance < second_distance
    assert first_center[0] < second_center[0]


def test_build_player_proposal_crop_windows_by_frame_reserves_direct_seed_window_within_cap():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.92,
            "Source_X1": 42.0,
            "Source_Y1": 44.0,
            "Source_X2": 62.0,
            "Source_Y2": 84.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.85,
            "Source_X1": 110.0,
            "Source_Y1": 118.0,
            "Source_X2": 134.0,
            "Source_Y2": 170.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (52.0, 64.0)},
        frame_count=15,
        max_proposals_per_frame=2,
        proposal_crop_width_ratio=0.35,
    )

    assert summary["proposalWindowCount"] == 4
    assert summary["proposalDirectSeedWindowFrames"] == 3
    assert summary["proposalDirectSeedTightWindowFrames"] == 3
    assert summary["proposalDirectSeedContextWindowFrames"] == 0
    assert summary["proposalPlayerRankedWindowFrames"] == 1
    assert len(crop_windows[10]) == 2
    direct_window = next(window for window in crop_windows[10] if window["proposalWindowKind"] == "direct_seed_tight")
    ranked_window = next(window for window in crop_windows[10] if window["proposalWindowKind"] == "player_ranked")
    assert direct_window["proposalSeedMode"] == "exact"
    assert direct_window["proposalSeedCenter"] == (52.0, 64.0)
    direct_left, direct_top, direct_right, direct_bottom = direct_window["window"]
    direct_center = ((direct_left + direct_right) / 2.0, (direct_top + direct_bottom) / 2.0)
    assert direct_center == pytest.approx((52.0, 64.0), abs=0.5)
    assert ranked_window["proposalSeedCenter"] == (52.0, 64.0)
    assert ranked_window["proposalSeedMode"] == "exact"


def test_build_player_proposal_crop_windows_by_frame_adds_distinct_direct_seed_context_window():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.92,
            "Source_X1": 75.0,
            "Source_Y1": 70.0,
            "Source_X2": 95.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.88,
            "Source_X1": 102.0,
            "Source_Y1": 74.0,
            "Source_X2": 122.0,
            "Source_Y2": 114.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (90.0, 90.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert len(crop_windows[10]) == 3
    assert summary["proposalDirectSeedWindowFrames"] == 4
    assert summary["proposalDirectSeedTightWindowFrames"] == 3
    assert summary["proposalDirectSeedContextWindowFrames"] == 1
    assert summary["proposalDirectSeedContextEligibleFrames"] == 1
    assert summary["proposalDirectSeedContextDuplicateFrames"] == 0
    assert summary["proposalDirectSeedContextMeanSeedToBoxDistance"] == pytest.approx(0.0, abs=0.01)
    assert summary["proposalPlayerRankedWindowFrames"] == 1

    tight_window = next(spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_tight")
    context_window = next(spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_context")

    tight_center_x = (tight_window[0] + tight_window[2]) / 2.0
    context_center_x = (context_window[0] + context_window[2]) / 2.0

    assert tight_center_x == pytest.approx(90.0, abs=0.5)
    assert context_center_x < tight_center_x


def test_build_player_proposal_crop_windows_by_frame_adds_context_when_box_is_near_seed_but_center_is_outside_tight_window():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.9,
            "Source_X1": 110.0,
            "Source_Y1": 80.0,
            "Source_X2": 122.0,
            "Source_Y2": 100.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (90.0, 90.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert len(crop_windows[10]) == 2
    assert summary["proposalDirectSeedContextWindowFrames"] == 1
    assert summary["proposalDirectSeedContextEligibleFrames"] == 1
    assert summary["proposalDirectSeedContextExpandedFrames"] == 0
    assert summary["proposalDirectSeedContextMeanExpansionPx"] == 0.0
    assert summary["proposalDirectSeedContextDuplicateFrames"] == 0
    assert summary["proposalDirectSeedContextMeanSeedToBoxDistance"] == pytest.approx(20.0, abs=0.01)
    assert {spec["proposalWindowKind"] for spec in crop_windows[10]} == {
        "direct_seed_tight",
        "direct_seed_context",
    }


def test_build_player_proposal_crop_windows_by_frame_skips_context_when_nearest_box_exceeds_bound():
    frame_shape = (240, 300, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.9,
            "Source_X1": 220.0,
            "Source_Y1": 80.0,
            "Source_X2": 250.0,
            "Source_Y2": 100.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (20.0, 90.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert [spec["proposalWindowKind"] for spec in crop_windows[10]] == ["direct_seed_tight", "player_ranked"]
    assert summary["proposalDirectSeedContextWindowFrames"] == 0
    assert summary["proposalDirectSeedContextEligibleFrames"] == 0
    assert summary["proposalDirectSeedContextDuplicateFrames"] == 0
    assert summary["proposalDirectSeedContextMeanSeedToBoxDistance"] == 0.0


def test_build_player_proposal_crop_windows_by_frame_dedupes_identical_direct_seed_context_window():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.92,
            "Source_X1": 80.0,
            "Source_Y1": 80.0,
            "Source_X2": 100.0,
            "Source_Y2": 100.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (90.0, 90.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert len(crop_windows[10]) == 1
    assert [spec["proposalWindowKind"] for spec in crop_windows[10]] == ["direct_seed_tight"]
    assert summary["proposalDirectSeedWindowFrames"] == 3
    assert summary["proposalDirectSeedTightWindowFrames"] == 3
    assert summary["proposalDirectSeedContextWindowFrames"] == 0
    assert summary["proposalDirectSeedContextEligibleFrames"] == 1
    assert summary["proposalDirectSeedContextDuplicateFrames"] == 1
    assert summary["proposalDirectSeedContextMeanSeedToBoxDistance"] == pytest.approx(0.0, abs=0.01)
    assert summary["proposalPlayerRankedWindowFrames"] == 0


def test_build_player_proposal_crop_windows_by_frame_adds_touchline_escape_window_for_acquisition_upgrade():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.9,
            "Source_X1": 8.0,
            "Source_Y1": 78.0,
            "Source_X2": 26.0,
            "Source_Y2": 118.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (12.0, 96.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_upgrade_v1",
    )

    window_kinds = [spec["proposalWindowKind"] for spec in crop_windows[10]]
    assert "touchline_escape" in window_kinds
    assert summary["proposalTouchlineEscapeEligibleFrames"] >= 1
    assert summary["proposalTouchlineEscapeWindowFrames"] >= 1

    touchline_escape_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "touchline_escape"
    )
    direct_seed_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_tight"
    )
    touchline_escape_center_x = (touchline_escape_window[0] + touchline_escape_window[2]) / 2.0
    direct_seed_center_x = (direct_seed_window[0] + direct_seed_window[2]) / 2.0

    assert touchline_escape_center_x > direct_seed_center_x
    assert touchline_escape_window[0] <= 12.0 <= touchline_escape_window[2]

    control_windows, control_summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (12.0, 96.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_upgrade_v1",
    )

    assert "touchline_escape" not in [spec["proposalWindowKind"] for spec in control_windows[10]]
    assert control_summary["proposalTouchlineEscapeEligibleFrames"] == 0
    assert control_summary["proposalTouchlineEscapeWindowFrames"] == 0


def test_build_player_proposal_crop_windows_by_frame_chooses_nearest_context_box_deterministically():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.92,
            "Source_X1": 108.0,
            "Source_Y1": 80.0,
            "Source_X2": 120.0,
            "Source_Y2": 100.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 2,
            "Conf": 0.91,
            "Source_X1": 120.0,
            "Source_Y1": 78.0,
            "Source_X2": 132.0,
            "Source_Y2": 102.0,
        },
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (90.0, 90.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    context_spec = next(spec for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_context")
    context_window = context_spec["window"]
    assert summary["proposalDirectSeedContextWindowFrames"] == 1
    assert summary["proposalDirectSeedContextEligibleFrames"] == 1
    assert summary["proposalDirectSeedContextDuplicateFrames"] == 0
    assert summary["proposalDirectSeedContextMeanSeedToBoxDistance"] == pytest.approx(18.0, abs=0.01)
    assert context_window[0] <= 90 <= context_window[2]
    assert context_window[0] < 120


def test_collapse_proposal_recovered_ball_candidates_acquisition_upgrade_prefers_touchline_escape_rows():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 96.0,
            "Conf": 0.94,
            "Source_X1": 6.0,
            "Source_Y1": 84.0,
            "Source_X2": 18.0,
            "Source_Y2": 104.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 32.0,
            "Y": 64.0,
            "Conf": 0.72,
            "Source_X1": 52.0,
            "Source_Y1": 74.0,
            "Source_X2": 66.0,
            "Source_Y2": 96.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "touchline_escape",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 3.0,
            "Y": 96.2,
            "Conf": 0.95,
            "Source_X1": 7.0,
            "Source_Y1": 84.0,
            "Source_X2": 19.0,
            "Source_Y2": 105.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 35.0,
            "Y": 60.0,
            "Conf": 0.7,
            "Source_X1": 54.0,
            "Source_Y1": 72.0,
            "Source_X2": 68.0,
            "Source_Y2": 94.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "touchline_escape",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_upgrade_v1",
    )

    assert [row["ProposalWindowKind"] for row in collapsed["rows"]] == [
        "touchline_escape",
        "touchline_escape",
    ]
    assert collapsed["proposalTouchlineEscapeDetectedFrames"] == 2
    assert collapsed["proposalTouchlineEscapeSelectedFrames"] == 2
    assert collapsed["proposalCandidateEdgeShareBeforeSelection"] == 1.0
    assert collapsed["proposalCandidateEdgeShareAfterSelection"] == 0.0
    assert collapsed["proposalTouchlineEscapeRejectionCounts"] == {}
    assert collapsed["proposalRepeatedAnchorSuppressedFrames"] == 0


def test_build_player_proposal_crop_windows_by_frame_adds_touchline_inboard_context_window_for_acquisition_reopen_v2():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.9,
            "Source_X1": 8.0,
            "Source_Y1": 78.0,
            "Source_X2": 26.0,
            "Source_Y2": 118.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (12.0, 96.0)},
        frame_count=15,
        max_proposals_per_frame=4,
        proposal_crop_width_ratio=0.35,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_reopen_v2",
    )

    window_kinds = [spec["proposalWindowKind"] for spec in crop_windows[10]]
    assert "touchline_escape" in window_kinds
    assert "touchline_inboard_context" in window_kinds
    assert summary["proposalTouchlineEscapeEligibleFrames"] >= 1
    assert summary["proposalTouchlineEscapeWindowFrames"] >= 1

    touchline_escape_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "touchline_escape"
    )
    inboard_context_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "touchline_inboard_context"
    )
    direct_seed_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_tight"
    )

    touchline_escape_center_x = (touchline_escape_window[0] + touchline_escape_window[2]) / 2.0
    inboard_context_center_x = (inboard_context_window[0] + inboard_context_window[2]) / 2.0
    direct_seed_center_x = (direct_seed_window[0] + direct_seed_window[2]) / 2.0

    assert inboard_context_center_x >= touchline_escape_center_x
    assert touchline_escape_center_x > direct_seed_center_x
    assert inboard_context_window[0] <= 12.0 <= inboard_context_window[2]


def test_build_player_proposal_crop_windows_by_frame_adds_inboard_context_without_escape_for_candidate_admission_reopen_v3():
    frame_shape = (200, 200, 3)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.9,
            "Source_X1": 6.0,
            "Source_Y1": 78.0,
            "Source_X2": 22.0,
            "Source_Y2": 118.0,
        }
    ]

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (8.0, 96.0)},
        frame_count=15,
        max_proposals_per_frame=4,
        proposal_crop_width_ratio=0.35,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )

    window_kinds = [spec["proposalWindowKind"] for spec in crop_windows[10]]
    assert "touchline_escape" not in window_kinds
    assert "touchline_inboard_context" in window_kinds
    assert summary["proposalTouchlineEscapeEligibleFrames"] == 0
    assert summary["proposalTouchlineEscapeWindowFrames"] == 0

    inboard_context_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "touchline_inboard_context"
    )
    direct_seed_window = next(
        spec["window"] for spec in crop_windows[10] if spec["proposalWindowKind"] == "direct_seed_tight"
    )

    inboard_context_center_x = (inboard_context_window[0] + inboard_context_window[2]) / 2.0
    direct_seed_center_x = (direct_seed_window[0] + direct_seed_window[2]) / 2.0

    assert inboard_context_center_x > direct_seed_center_x
    assert inboard_context_window[0] <= 8.0 <= inboard_context_window[2]


def test_collapse_proposal_recovered_ball_candidates_acquisition_reopen_v2_prefers_inboard_context_rows():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 96.0,
            "Conf": 0.94,
            "Source_X1": 6.0,
            "Source_Y1": 84.0,
            "Source_X2": 18.0,
            "Source_Y2": 104.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 28.0,
            "Y": 63.0,
            "Conf": 0.74,
            "Source_X1": 48.0,
            "Source_Y1": 70.0,
            "Source_X2": 62.0,
            "Source_Y2": 92.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 54.0,
            "ProposalCropHeight": 54.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 3.0,
            "Y": 96.2,
            "Conf": 0.95,
            "Source_X1": 7.0,
            "Source_Y1": 84.0,
            "Source_X2": 19.0,
            "Source_Y2": 105.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 31.0,
            "Y": 61.0,
            "Conf": 0.73,
            "Source_X1": 50.0,
            "Source_Y1": 72.0,
            "Source_X2": 64.0,
            "Source_Y2": 95.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 54.0,
            "ProposalCropHeight": 54.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_acquisition_reopen_v2",
    )

    assert [row["ProposalWindowKind"] for row in collapsed["rows"]] == [
        "touchline_inboard_context",
        "touchline_inboard_context",
    ]
    assert collapsed["proposalTouchlineEscapeDetectedFrames"] == 0
    assert collapsed["proposalTouchlineEscapeSelectedFrames"] == 0
    assert collapsed["proposalCandidateEdgeShareBeforeSelection"] == 1.0
    assert collapsed["proposalCandidateEdgeShareAfterSelection"] == 0.0
    assert collapsed["proposalWindowKindSelectedCounts"] == {"touchline_inboard_context": 2}


def test_ball_candidate_rows_for_frame_reopens_touchline_raw_candidate_when_crop_edge_rejected_under_reopen_v3():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [
        FakeBox([5.0, 40.0, 25.0, 60.0], conf=0.61),
    ]

    rows, diagnostics = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [400, 0], [400, 400], [0, 400]],
        x_offset=100.0,
        y_offset=100.0,
        crop_window=(100, 100, 300, 300),
        crop_edge_margin=20,
        proposal_seed_center=(108.0, 150.0),
        proposal_crop_size=(70.0, 70.0),
        proposal_window_kind="touchline_inboard_context",
        proposal_seed_mode="exact",
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
        frame_shape=(400, 400, 3),
        return_diagnostics=True,
    )

    assert len(rows) == 1
    assert rows[0]["Source_X1"] == 105.0
    assert rows[0]["TouchlineRawCandidateReopened"] is True
    assert rows[0]["TouchlineRawCandidateReopenReason"] == "crop_edge_rejected"
    assert diagnostics["reopenedRawCandidateCount"] == 1
    assert diagnostics["reopenedRawCandidateFrames"] == 1


def test_collapse_proposal_recovered_ball_candidates_candidate_admission_reopen_v3_prefers_reopened_touchline_rows():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 96.0,
            "Conf": 0.94,
            "Source_X1": 6.0,
            "Source_Y1": 84.0,
            "Source_X2": 18.0,
            "Source_Y2": 104.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 28.0,
            "Y": 63.0,
            "Conf": 0.72,
            "Source_X1": 48.0,
            "Source_Y1": 70.0,
            "Source_X2": 62.0,
            "Source_Y2": 92.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 58.0,
            "ProposalCropHeight": 58.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
            "TouchlineRawCandidateReopened": True,
            "TouchlineRawCandidateReopenReason": "crop_edge_rejected",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 3.0,
            "Y": 96.2,
            "Conf": 0.95,
            "Source_X1": 7.0,
            "Source_Y1": 84.0,
            "Source_X2": 19.0,
            "Source_Y2": 105.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 31.0,
            "Y": 61.0,
            "Conf": 0.73,
            "Source_X1": 50.0,
            "Source_Y1": 72.0,
            "Source_X2": 64.0,
            "Source_Y2": 95.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 96.0,
            "ProposalCropWidth": 58.0,
            "ProposalCropHeight": 58.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
            "TouchlineRawCandidateReopened": True,
            "TouchlineRawCandidateReopenReason": "pitch_polygon_rejected",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )

    assert [row["ProposalWindowKind"] for row in collapsed["rows"]] == [
        "touchline_inboard_context",
        "touchline_inboard_context",
    ]
    assert collapsed["proposalTouchlineEscapeDetectedFrames"] == 0
    assert collapsed["proposalCandidateEdgeShareBeforeSelection"] == 1.0
    assert collapsed["proposalCandidateEdgeShareAfterSelection"] == 0.0
    assert collapsed["proposalReopenedRawCandidateFrames"] == 2
    assert collapsed["proposalReopenedRawCandidateSelectedFrames"] == 2
    assert collapsed["proposalWindowKindSelectedCounts"] == {"touchline_inboard_context": 2}


def test_collapse_proposal_recovered_ball_candidates_promoted_v6_admission_widening_accepts_supported_inboard_candidate():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 50.0,
            "Y": 50.0,
            "Conf": 0.95,
            "Source_X1": 48.0,
            "Source_Y1": 48.0,
            "Source_X2": 52.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.9,
        }
    ]

    strict_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )
    widened_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_admission_widening_v1",
    )

    assert strict_collapsed["rows"][0]["ProposalWindowKind"] == "direct_seed_tight"
    assert strict_collapsed["proposalTouchlineEscapeRejectionCounts"] == {"edge_share_not_improved": 1}
    assert widened_collapsed["rows"][0]["ProposalWindowKind"] == "touchline_inboard_context"
    assert widened_collapsed["proposalAdmissionWideningAcceptedFrames"] == 1
    assert widened_collapsed["proposalAdmissionWideningRejectedCounts"] == {}


def test_collapse_proposal_recovered_ball_candidates_promoted_v6_admission_widening_keeps_repeated_anchor_guard():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 50.0,
            "Y": 50.0,
            "Conf": 0.95,
            "Source_X1": 48.0,
            "Source_Y1": 48.0,
            "Source_X2": 52.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 50.0,
            "Conf": 0.7,
            "Source_X1": 9.0,
            "Source_Y1": 48.0,
            "Source_X2": 13.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 11.0,
            "ProposalSeedY": 50.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_admission_widening_v1",
    )

    assert collapsed["rows"][0]["ProposalWindowKind"] == "direct_seed_tight"
    assert collapsed["proposalRepeatedAnchorSuppressedFrames"] == 1
    assert collapsed["proposalAdmissionWideningAcceptedFrames"] == 0
    assert collapsed["proposalAdmissionWideningRejectedCounts"] == {"repeated_anchor_suspicious": 1}


def test_build_player_proposal_crop_windows_by_frame_merges_missing_baseline_guided_reference_anchors():
    frame_shape = (240, 240, 3)
    reference_payload = {
        "sourceClipId": "trimed-5min.mp4",
        "anchors": [
            {
                "frameId": 10,
                "sourceCenterX": 20.0,
                "sourceCenterY": 30.0,
                "pitchX": 40.0,
                "pitchY": 40.0,
            },
            {
                "frameId": 15,
                "sourceCenterX": 30.0,
                "sourceCenterY": 40.0,
                "pitchX": 2.0,
                "pitchY": 40.0,
            },
            {
                "frameId": 20,
                "sourceCenterX": 80.0,
                "sourceCenterY": 90.0,
                "pitchX": 42.0,
                "pitchY": 44.0,
            },
        ],
    }

    windows, diagnostics = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=[],
        observed_source_anchors={10: (20.0, 30.0)},
        frame_count=25,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_baseline_guided_rescue_v1",
        baseline_guided_rescue_reference=reference_payload,
    )

    assert 10 in windows
    assert not any(spec["proposalSeedMode"] == "baseline_guided" for spec in windows.get(15, []))
    assert 20 in windows
    assert any(spec["proposalSeedMode"] == "baseline_guided" for spec in windows[20])
    assert diagnostics["proposalBaselineGuidedRescueAvailableFrames"] == 3
    assert diagnostics["proposalBaselineGuidedRescueUsedFrames"] == 1
    assert diagnostics["proposalBaselineGuidedRescueSkippedExistingFrames"] == 1
    assert diagnostics["proposalBaselineGuidedRescueSkippedEdgeFrames"] == 1


def test_collapse_proposal_recovered_ball_candidates_counts_baseline_guided_selected_frames():
    candidate_rows = [
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 44.0,
            "Y": 44.0,
            "Conf": 0.95,
            "Source_X1": 78.0,
            "Source_Y1": 88.0,
            "Source_X2": 82.0,
            "Source_Y2": 92.0,
            "ProposalSeedX": 80.0,
            "ProposalSeedY": 90.0,
            "ProposalCropWidth": 40.0,
            "ProposalCropHeight": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "baseline_guided",
        }
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_baseline_guided_rescue_v1",
    )

    assert collapsed["rows"][0]["ProposalSeedMode"] == "baseline_guided"
    assert collapsed["proposalBaselineGuidedRescueSelectedFrames"] == 1


def test_collapse_proposal_recovered_ball_candidates_continuity_bridge_accepts_supported_gap_candidate():
    candidate_rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 40.0,
            "Y": 40.0,
            "Conf": 0.95,
            "Source_X1": 38.0,
            "Source_Y1": 38.0,
            "Source_X2": 42.0,
            "Source_Y2": 42.0,
            "ProposalSeedX": 40.0,
            "ProposalSeedY": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 50.0,
            "Conf": 0.99,
            "Source_X1": 48.0,
            "Source_Y1": 48.0,
            "Source_X2": 52.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "interpolated",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 50.0,
            "Y": 50.0,
            "Conf": 0.62,
            "Source_X1": 78.0,
            "Source_Y1": 78.0,
            "Source_X2": 82.0,
            "Source_Y2": 82.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalWindowKind": "player_ranked",
            "ProposalSeedMode": "interpolated",
        },
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 60.0,
            "Y": 60.0,
            "Conf": 0.95,
            "Source_X1": 58.0,
            "Source_Y1": 58.0,
            "Source_X2": 62.0,
            "Source_Y2": 62.0,
            "ProposalSeedX": 60.0,
            "ProposalSeedY": 60.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 7, "X": 50.0, "Y": 50.0, "Conf": 0.9}
    ]

    strict_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile=None,
    )
    bridged_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1",
    )

    assert strict_collapsed["rows"][1]["X"] == 2.0
    assert bridged_collapsed["rows"][1]["X"] == 50.0
    assert bridged_collapsed["rows"][1]["ContinuityBridgeRecovered"] is True
    assert bridged_collapsed["proposalContinuityBridgeAcceptedFrames"] == 1
    assert bridged_collapsed["proposalContinuityBridgeCandidateFrames"] == 2


def test_collapse_proposal_recovered_ball_candidates_continuity_bridge_rejects_unsafe_candidates():
    candidate_rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 40.0,
            "Y": 40.0,
            "Conf": 0.95,
            "Source_X1": 38.0,
            "Source_Y1": 38.0,
            "Source_X2": 42.0,
            "Source_Y2": 42.0,
            "ProposalSeedX": 40.0,
            "ProposalSeedY": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 50.0,
            "Conf": 0.99,
            "Source_X1": 48.0,
            "Source_Y1": 48.0,
            "Source_X2": 52.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "interpolated",
        },
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 60.0,
            "Y": 60.0,
            "Conf": 0.95,
            "Source_X1": 58.0,
            "Source_Y1": 58.0,
            "Source_X2": 62.0,
            "Source_Y2": 62.0,
            "ProposalSeedX": 60.0,
            "ProposalSeedY": 60.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1",
    )

    assert collapsed["rows"][1]["X"] == 2.0
    assert collapsed["proposalContinuityBridgeAcceptedFrames"] == 0
    assert collapsed["proposalContinuityBridgeRejectedRepeatedAnchorFrames"] == 1


def test_collapse_proposal_recovered_ball_candidates_continuity_bridge_ignored_for_non_target_source():
    candidate_rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 40.0,
            "Y": 40.0,
            "Conf": 0.95,
            "Source_X1": 38.0,
            "Source_Y1": 38.0,
            "Source_X2": 42.0,
            "Source_Y2": 42.0,
            "ProposalSeedX": 40.0,
            "ProposalSeedY": 40.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 50.0,
            "Conf": 0.99,
            "Source_X1": 48.0,
            "Source_Y1": 48.0,
            "Source_X2": 52.0,
            "Source_Y2": 52.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "interpolated",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 50.0,
            "Y": 50.0,
            "Conf": 0.62,
            "Source_X1": 78.0,
            "Source_Y1": 78.0,
            "Source_X2": 82.0,
            "Source_Y2": 82.0,
            "ProposalSeedX": 50.0,
            "ProposalSeedY": 50.0,
            "ProposalWindowKind": "player_ranked",
            "ProposalSeedMode": "interpolated",
        },
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 60.0,
            "Y": 60.0,
            "Conf": 0.95,
            "Source_X1": 58.0,
            "Source_Y1": 58.0,
            "Source_X2": 62.0,
            "Source_Y2": 62.0,
            "ProposalSeedX": 60.0,
            "ProposalSeedY": 60.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1",
    )

    assert collapsed["rows"][1]["X"] == 2.0
    assert "proposalContinuityBridgeAcceptedFrames" in collapsed
    assert collapsed["proposalContinuityBridgeAcceptedFrames"] == 0


def test_collapse_proposal_recovered_ball_candidates_acceptance_support_gating_accepts_supported_inboard_candidate():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 85.0,
            "ProposalSeedY": 85.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 4,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.9,
        }
    ]

    strict_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_touchline_candidate_admission_reopen_v3",
    )
    gated_collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_acceptance_support_gating_v1",
    )

    assert strict_collapsed["rows"][0]["X"] == 70.0
    assert strict_collapsed["proposalTouchlineEscapeRejectionCounts"] == {"edge_share_not_improved": 1}
    assert gated_collapsed["rows"][0]["X"] == 45.0
    assert gated_collapsed["rows"][0]["AcceptanceSupportGatingRecovered"] is True
    assert gated_collapsed["proposalAcceptanceSupportGatingAcceptedFrames"] == 1
    assert gated_collapsed["proposalAcceptanceSupportGatingRejectedCounts"] == {}


def test_collapse_proposal_recovered_ball_candidates_acceptance_support_gating_rejects_repeated_anchor_candidate():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 9.0,
            "Source_Y1": 43.0,
            "Source_X2": 13.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 11.0,
            "ProposalSeedY": 45.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 4, "X": 2.0, "Y": 45.0, "Conf": 0.9}
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_acceptance_support_gating_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalAcceptanceSupportGatingAcceptedFrames"] == 0
    assert collapsed["proposalAcceptanceSupportGatingRejectedCounts"] == {
        "repeated_anchor_suspicious": 1
    }


def test_collapse_proposal_recovered_ball_candidates_acceptance_support_gating_rejects_edge_guard_regression():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 88.0,
            "Source_Y1": 88.0,
            "Source_X2": 92.0,
            "Source_Y2": 92.0,
            "ProposalSeedX": 20.0,
            "ProposalSeedY": 20.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 4, "X": 2.0, "Y": 45.0, "Conf": 0.9}
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_acceptance_support_gating_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalAcceptanceSupportGatingAcceptedFrames"] == 0
    assert collapsed["proposalAcceptanceSupportGatingRejectedCounts"] == {
        "projected_edge_share_too_high": 1
    }


def test_collapse_proposal_recovered_ball_candidates_acceptance_support_gating_ignored_for_non_target_source():
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 85.0,
            "ProposalSeedY": 85.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 4, "X": 45.0, "Y": 45.0, "Conf": 0.9}
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_acceptance_support_gating_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalAcceptanceSupportGatingAcceptedFrames"] == 0


def _write_proposal_selection_seed(path: Path, *, frame_id: int = 10, x: float = 45.0, y: float = 45.0):
    path.write_text(
        json.dumps(
            {
                "truthStatus": "bootstrap_seed_not_manual_gold",
                "acceptedBallSeedRows": [
                    {
                        "frameId": frame_id,
                        "bootstrapWindowId": "0010-0010",
                        "row": {
                            "Frame_ID": frame_id,
                            "X": x,
                            "Y": y,
                            "Source_X1": x - 2.0,
                            "Source_Y1": y - 2.0,
                            "Source_X2": x + 2.0,
                            "Source_Y2": y + 2.0,
                        },
                    }
                ],
                "controlledTruthCandidateRows": [
                    {
                        "frameId": frame_id,
                        "bootstrapWindowId": "0010-0010",
                        "row": {"Frame_ID": frame_id, "X": x, "Y": y},
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _proposal_selection_profile_config(seed_path: Path, *, approach: str = "truth_seed_guided_selection"):
    return {
        "requireRealDetectedCandidateRows": True,
        "maxProjectedEdgeShare": 0.6,
        "preserveRepeatedAnchorGuard": True,
        "preserveContinuityGuard": True,
        "truthSeedPath": str(seed_path),
        "maxSeedPitchDistance": 8.0,
        "approachFamily": approach,
    }


def _support_viability_profile_config(
    seed_path: Path,
    *,
    approach: str = "support_evidence_lift",
):
    return {
        "approachFamily": approach,
        "truthSeedPath": str(seed_path),
        "maxProjectedEdgeShare": 0.6,
        "requireRealDetectedCandidateRows": True,
        "preserveRepeatedAnchorGuard": True,
        "preserveContinuityGuard": True,
    }


def test_collapse_proposal_recovered_ball_candidates_support_evidence_lift_accepts_supported_seeded_candidate(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **_kwargs: _support_viability_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 7,
            "X": 46.0,
            "Y": 45.5,
            "Conf": 0.9,
        }
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 45.0
    assert collapsed["rows"][0]["SupportViabilityAdmissionFixRecovered"] is True
    assert collapsed["rows"][0]["SupportViabilityAdmissionFixApproachFamily"] == "support_evidence_lift"
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 1
    assert collapsed["proposalSupportViabilityAdmissionFixRejectedCounts"] == {}
    assert collapsed["proposalSupportViabilityAdmissionFixTruthSeedFrames"] == 1


def test_collapse_proposal_recovered_ball_candidates_support_evidence_lift_rejects_safety_failures(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **_kwargs: _support_viability_profile_config(seed_path),
        raising=False,
    )
    base_candidate = {
        "Frame_ID": 10,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": 70.0,
        "Y": 70.0,
        "Conf": 0.95,
        "Source_X1": 68.0,
        "Source_Y1": 68.0,
        "Source_X2": 72.0,
        "Source_Y2": 72.0,
        "ProposalSeedX": 70.0,
        "ProposalSeedY": 70.0,
        "ProposalWindowKind": "direct_seed_tight",
        "ProposalSeedMode": "exact",
    }
    repeated_anchor = {
        "Frame_ID": 10,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": 2.0,
        "Y": 45.0,
        "Conf": 0.7,
        "Source_X1": 8.0,
        "Source_Y1": 43.0,
        "Source_X2": 12.0,
        "Source_Y2": 47.0,
        "ProposalSeedX": 10.0,
        "ProposalSeedY": 45.0,
        "ProposalWindowKind": "touchline_inboard_context",
        "ProposalSeedMode": "exact",
    }
    edge_heavy = {
        "Frame_ID": 10,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": 2.0,
        "Y": 45.0,
        "Conf": 0.7,
        "Source_X1": 43.0,
        "Source_Y1": 43.0,
        "Source_X2": 47.0,
        "Source_Y2": 47.0,
        "ProposalSeedX": 84.0,
        "ProposalSeedY": 84.0,
        "ProposalWindowKind": "touchline_inboard_context",
        "ProposalSeedMode": "exact",
    }
    non_real = {
        "Frame_ID": 10,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": 44.0,
        "Y": 45.0,
        "Conf": 0.0,
        "ProposalWindowKind": "touchline_inboard_context",
        "ProposalSeedMode": "exact",
    }

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        [base_candidate, repeated_anchor, edge_heavy, non_real],
        player_rows=[
            {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 7, "X": 45.0, "Y": 45.0}
        ],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 0
    assert collapsed["proposalSupportViabilityAdmissionFixRejectedCounts"] == {
        "candidate_edge_heavy": 1,
        "real_detected_candidate_missing": 1,
        "repeated_anchor_suspicious": 1,
    }


def test_collapse_proposal_recovered_ball_candidates_support_evidence_lift_rejects_continuity_regression(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=15, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **_kwargs: _support_viability_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 10.0,
            "Y": 10.0,
            "Conf": 0.95,
            "Source_X1": 8.0,
            "Source_Y1": 8.0,
            "Source_X2": 12.0,
            "Source_Y2": 12.0,
            "ProposalSeedX": 10.0,
            "ProposalSeedY": 10.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 12.0,
            "Y": 10.0,
            "Conf": 0.95,
            "Source_X1": 10.0,
            "Source_Y1": 8.0,
            "Source_X2": 14.0,
            "Source_Y2": 12.0,
            "ProposalSeedX": 12.0,
            "ProposalSeedY": 10.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 80.0,
            "Y": 80.0,
            "Conf": 0.7,
            "Source_X1": 78.0,
            "Source_Y1": 78.0,
            "Source_X2": 82.0,
            "Source_Y2": 82.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[
            {"Frame_ID": 15, "Entity_Type": "player", "Track_ID": 7, "X": 80.0, "Y": 80.0}
        ],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1",
    )

    assert [row["X"] for row in collapsed["rows"]] == [10.0, 12.0]
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 0
    assert collapsed["proposalSupportViabilityAdmissionFixRejectedCounts"] == {
        "anchor_continuity_regressed": 1
    }


def test_collapse_proposal_recovered_ball_candidates_source_space_support_neighborhood_accepts_source_supported_candidate(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **_kwargs: _support_viability_profile_config(
            seed_path,
            approach="source_space_support_neighborhood",
        ),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 7,
            "Conf": 0.9,
            "Source_X1": 40.0,
            "Source_Y1": 38.0,
            "Source_X2": 50.0,
            "Source_Y2": 55.0,
        }
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v2",
    )

    assert collapsed["rows"][0]["X"] == 45.0
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 1
    assert collapsed["rows"][0]["SupportViabilityAdmissionFixApproachFamily"] == (
        "source_space_support_neighborhood"
    )


def test_collapse_proposal_recovered_ball_candidates_viability_neutral_seed_window_accepts_non_edge_candidate(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **_kwargs: _support_viability_profile_config(
            seed_path,
            approach="viability_neutral_seed_window",
        ),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3",
    )

    assert collapsed["rows"][0]["X"] == 45.0
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 1
    assert collapsed["rows"][0]["SupportViabilityAdmissionFixApproachFamily"] == (
        "viability_neutral_seed_window"
    )


def test_collapse_proposal_recovered_ball_candidates_support_viability_ignored_for_non_target_source(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=10.0, y=10.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_support_viability_admission_fix_config",
        lambda **kwargs: None
        if kwargs.get("source_clip_id") != "trimed-5min.mp4"
        else _support_viability_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[
            {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 7, "X": 45.0, "Y": 45.0}
        ],
        max_frame_gap=5,
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalSupportViabilityAdmissionFixAcceptedFrames"] == 0


def test_collapse_proposal_recovered_ball_candidates_truth_seed_guided_selection_accepts_seeded_real_candidate(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=45.0, y=45.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_proposal_selection_admission_fix_config",
        lambda **_kwargs: _proposal_selection_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 45.0
    assert collapsed["rows"][0]["ProposalSelectionAdmissionFixRecovered"] is True
    assert collapsed["proposalSelectionAdmissionFixAcceptedFrames"] == 1
    assert collapsed["proposalSelectionAdmissionFixRejectedCounts"] == {}


def test_collapse_proposal_recovered_ball_candidates_proposal_selection_rejects_repeated_anchor_seed(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=2.0, y=45.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_proposal_selection_admission_fix_config",
        lambda **_kwargs: _proposal_selection_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 8.0,
            "Source_Y1": 43.0,
            "Source_X2": 12.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 10.0,
            "ProposalSeedY": 45.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalSelectionAdmissionFixAcceptedFrames"] == 0
    assert collapsed["proposalSelectionAdmissionFixRejectedCounts"] == {
        "repeated_anchor_suspicious": 1
    }


def test_collapse_proposal_recovered_ball_candidates_proposal_selection_rejects_projected_edge_share(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=2.0, y=45.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_proposal_selection_admission_fix_config",
        lambda **_kwargs: {
            **_proposal_selection_profile_config(seed_path),
            "preserveRepeatedAnchorGuard": False,
        },
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 2.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalSelectionAdmissionFixAcceptedFrames"] == 0
    assert collapsed["proposalSelectionAdmissionFixRejectedCounts"] == {
        "projected_edge_share_too_high": 1
    }


def test_collapse_proposal_recovered_ball_candidates_proposal_selection_ignored_for_non_target_source(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=45.0, y=45.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_proposal_selection_admission_fix_config",
        lambda **kwargs: None
        if kwargs.get("source_clip_id") != "trimed-5min.mp4"
        else _proposal_selection_profile_config(seed_path),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 45.0,
            "Y": 45.0,
            "Conf": 0.7,
            "Source_X1": 43.0,
            "Source_Y1": 43.0,
            "Source_X2": 47.0,
            "Source_Y2": 47.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-football-2-1minute.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 70.0
    assert collapsed["proposalSelectionAdmissionFixAcceptedFrames"] == 0


def test_collapse_proposal_recovered_ball_candidates_window_local_rescue_stays_inside_seed_windows(
    tmp_path: Path,
    monkeypatch,
):
    seed_path = tmp_path / "accepted_controlled_truth_seed.json"
    _write_proposal_selection_seed(seed_path, frame_id=10, x=45.0, y=45.0)
    monkeypatch.setattr(
        run_guerilla,
        "_touchline_proposal_selection_admission_fix_config",
        lambda **_kwargs: _proposal_selection_profile_config(
            seed_path,
            approach="window_local_proposal_kind_rescue",
        ),
        raising=False,
    )
    candidate_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 70.0,
            "Y": 70.0,
            "Conf": 0.95,
            "Source_X1": 68.0,
            "Source_Y1": 68.0,
            "Source_X2": 72.0,
            "Source_Y2": 72.0,
            "ProposalSeedX": 70.0,
            "ProposalSeedY": 70.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 60.0,
            "Y": 60.0,
            "Conf": 0.7,
            "Source_X1": 58.0,
            "Source_Y1": 58.0,
            "Source_X2": 62.0,
            "Source_Y2": 62.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 60.0,
            "Y": 60.0,
            "Conf": 0.7,
            "Source_X1": 58.0,
            "Source_Y1": 58.0,
            "Source_X2": 62.0,
            "Source_Y2": 62.0,
            "ProposalSeedX": 84.0,
            "ProposalSeedY": 84.0,
            "ProposalWindowKind": "touchline_inboard_context",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 20,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 80.0,
            "Y": 80.0,
            "Conf": 0.95,
            "Source_X1": 78.0,
            "Source_Y1": 78.0,
            "Source_X2": 82.0,
            "Source_Y2": 82.0,
            "ProposalSeedX": 80.0,
            "ProposalSeedY": 80.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        candidate_rows,
        player_rows=[],
        max_frame_gap=5,
        source_clip_id="trimed-5min.mp4",
        edge_share_repair_profile="source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1",
    )

    assert collapsed["rows"][0]["X"] == 60.0
    assert collapsed["rows"][1]["X"] == 80.0
    assert collapsed["proposalSelectionAdmissionFixAcceptedFrames"] == 1
    assert collapsed["proposalSelectionAdmissionFixRejectedCounts"]["frame_not_in_truth_seed"] == 1


def test_build_player_proposal_crop_windows_by_frame_keeps_context_player_biased_while_expanding_toward_seed():
    frame_shape = (240, 240, 3)
    source_box = (150.0, 90.0, 170.0, 130.0)
    player_rows = [
        {
            "Frame_ID": 10,
            "Entity_Type": "player",
            "Track_ID": 1,
            "Conf": 0.93,
            "Source_X1": source_box[0],
            "Source_Y1": source_box[1],
            "Source_X2": source_box[2],
            "Source_Y2": source_box[3],
        }
    ]
    base_window = run_guerilla._player_proposal_crop_window(
        frame_shape,
        source_box,
        proposal_crop_width_ratio=0.35,
    )
    context_window, expansion_px, expanded = run_guerilla._player_biased_seed_context_crop_window(
        frame_shape,
        source_box,
        (80.0, 110.0),
        proposal_crop_width_ratio=0.35,
    )

    crop_windows, summary = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=5,
        player_rows=player_rows,
        observed_source_anchors={10: (80.0, 110.0)},
        frame_count=15,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
    )

    assert expanded is True
    assert expansion_px > 0.0
    assert summary["proposalDirectSeedContextWindowFrames"] == 1
    assert summary["proposalDirectSeedContextEligibleFrames"] == 1
    assert summary["proposalDirectSeedContextExpandedFrames"] == 1
    assert summary["proposalDirectSeedContextMeanExpansionPx"] > 0.0
    assert context_window[0] < base_window[0]
    assert context_window[2] >= (base_window[2] - 2)
    assert context_window[0] <= 80 <= context_window[2]


def test_summarize_and_score_ball_track_rows_prefer_meaningful_motion():
    moving_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 41.0, "Y": 54.0, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.5, "Y": 53.0, "Conf": 0.28},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.5, "Conf": 0.26},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 53.5, "Y": 47.0, "Conf": 0.25},
    ])
    static_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.30},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.29},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.28},
    ])

    assert moving_summary["showsMeaningfulMotion"] is True
    assert score_ball_track_summary(moving_summary) > score_ball_track_summary(static_summary)


def test_recover_ball_rows_handles_multiple_crop_windows_per_frame(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    predict_calls = []

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, coords):
            self.boxes = [FakeBox(coords)]

    class FakeModel:
        def predict(self, frame_image, **_kwargs):
            predict_calls.append(frame_image.shape[:2])
            if len(predict_calls) == 1:
                return [FakeResult([5.0, 5.0, 15.0, 15.0])]
            return [FakeResult([10.0, 10.0, 20.0, 20.0])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={0: [(0, 0, 40, 40), (40, 40, 80, 80)]},
    )

    assert predict_calls == [(40, 40), (40, 40)]
    assert len(rows) == 2
    assert [row["Source_X1"] for row in rows] == [5.0, 50.0]


def test_recover_ball_rows_preserves_true_seed_metadata_for_proposal_specs(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, coords):
            self.boxes = [FakeBox(coords)]

    class FakeModel:
        def __init__(self):
            self._calls = 0

        def predict(self, frame_image, **_kwargs):
            self._calls += 1
            if self._calls == 1:
                return [FakeResult([8.0, 8.0, 18.0, 18.0])]
            return [FakeResult([10.0, 10.0, 20.0, 20.0])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={
            0: [
                {
                    "window": (0, 0, 40, 40),
                    "proposalSeedCenter": (30.0, 32.0),
                    "proposalWindowKind": "direct_seed_tight",
                    "proposalSeedMode": "exact",
                },
                {
                    "window": (40, 40, 80, 80),
                    "proposalSeedCenter": (30.0, 32.0),
                    "proposalWindowKind": "player_ranked",
                    "proposalSeedMode": "exact",
                },
            ]
        },
    )

    assert len(rows) == 2
    assert rows[0]["ProposalSeedX"] == pytest.approx(30.0, abs=1e-6)
    assert rows[0]["ProposalSeedY"] == pytest.approx(32.0, abs=1e-6)
    assert rows[0]["ProposalWindowKind"] == "direct_seed_tight"
    assert rows[0]["ProposalSeedMode"] == "exact"
    assert rows[1]["ProposalSeedX"] == pytest.approx(30.0, abs=1e-6)
    assert rows[1]["ProposalSeedY"] == pytest.approx(32.0, abs=1e-6)
    assert rows[1]["ProposalWindowKind"] == "player_ranked"
    assert rows[1]["ProposalSeedMode"] == "exact"


def test_recover_ball_rows_retries_direct_seed_windows_at_hi_res_when_base_misses(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    predict_calls = []

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def predict(self, frame_image, **kwargs):
            predict_calls.append(
                {
                    "shape": frame_image.shape[:2],
                    "imgsz": kwargs["imgsz"],
                }
            )
            if len(predict_calls) == 1:
                return [FakeResult([])]
            if len(predict_calls) == 2:
                return [FakeResult([FakeBox([8.0, 8.0, 18.0, 18.0])])]
            return [FakeResult([])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows, diagnostics = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={
            0: [
                {
                    "window": (0, 0, 40, 40),
                    "proposalSeedCenter": (20.0, 20.0),
                    "proposalWindowKind": "direct_seed_tight",
                    "proposalSeedMode": "exact",
                },
                {
                    "window": (40, 0, 80, 40),
                    "proposalSeedCenter": (20.0, 20.0),
                    "proposalWindowKind": "player_ranked",
                    "proposalSeedMode": "exact",
                },
            ]
        },
        return_diagnostics=True,
    )

    default_recovery_imgsz = run_guerilla.resolve_ball_recovery_settings(
        run_guerilla.TRACKING_IMGSZ,
        run_guerilla.TRACKING_CONF,
    )["imgsz"]
    assert [call["imgsz"] for call in predict_calls] == [
        default_recovery_imgsz,
        960,
        default_recovery_imgsz,
    ]
    assert len(rows) == 1
    assert rows[0]["ProposalWindowKind"] == "direct_seed_tight"
    assert rows[0]["ProposalInferenceMode"] == "hi_res_retry"
    assert diagnostics["proposalDirectSeedHiResRetryFrames"] == 1
    assert diagnostics["proposalDirectSeedHiResRetryDetectedFrames"] == 1
    assert diagnostics["proposalDirectSeedZeroDetectFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale960RawDetectionFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1920RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale960CandidateFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1920CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale960AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1920AttemptFrames"] == 0
    assert diagnostics["proposalDirectSeedMultiScaleRetryFrames"] == 1
    assert diagnostics["proposalDirectSeedMultiScaleDetectedFrames"] == 1
    assert diagnostics["proposalDirectSeedRawHitFilteredOutFrames"] == 0
    assert diagnostics["proposalDirectSeedCropEdgeRejectedFrames"] == 0
    assert diagnostics["proposalDirectSeedCropCenterYRejectedFrames"] == 0
    assert diagnostics["proposalDirectSeedPitchPolygonRejectedFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedScale960ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedScale1920ElapsedSeconds"] == 0.0
    assert diagnostics["proposalDirectSeedFallbackElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedMeanCropArea"] == pytest.approx(1600.0, abs=0.01)
    assert diagnostics["proposalDirectSeedTightMeanCropArea"] == pytest.approx(1600.0, abs=0.01)
    assert diagnostics["proposalDirectSeedContextMeanCropArea"] == 0.0
    assert diagnostics["proposalPlayerRankedMeanCropArea"] == pytest.approx(1600.0, abs=0.01)
    assert diagnostics["proposalDirectSeedMeanDetectedBallBoxArea"] == pytest.approx(100.0, abs=0.01)
    assert diagnostics["proposalPlayerRankedMeanDetectedBallBoxArea"] == 0.0


def test_recover_ball_rows_retries_direct_seed_windows_at_1920_after_1600_and_960_miss(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    predict_calls = []

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def predict(self, frame_image, **kwargs):
            predict_calls.append(kwargs["imgsz"])
            if len(predict_calls) < 3:
                return [FakeResult([])]
            return [FakeResult([FakeBox([8.0, 8.0, 18.0, 18.0])])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows, diagnostics = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={
            0: [
                {
                    "window": (0, 0, 40, 40),
                    "proposalSeedCenter": (20.0, 20.0),
                    "proposalWindowKind": "direct_seed_context",
                    "proposalSeedMode": "exact",
                }
            ]
        },
        return_diagnostics=True,
    )

    default_recovery_imgsz = run_guerilla.resolve_ball_recovery_settings(
        run_guerilla.TRACKING_IMGSZ,
        run_guerilla.TRACKING_CONF,
    )["imgsz"]
    assert predict_calls == [default_recovery_imgsz, 960, 1920]
    assert len(rows) == 1
    assert rows[0]["ProposalWindowKind"] == "direct_seed_context"
    assert rows[0]["ProposalInferenceMode"] == "scale_1920_retry"
    assert diagnostics["proposalDirectSeedHiResRetryFrames"] == 1
    assert diagnostics["proposalDirectSeedHiResRetryDetectedFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale960RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1920RawDetectionFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1600CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale960CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1920CandidateFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1600AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale960AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1920AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedMultiScaleRetryFrames"] == 1
    assert diagnostics["proposalDirectSeedMultiScaleDetectedFrames"] == 1
    assert diagnostics["proposalDirectSeedZeroDetectFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedScale960ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedScale1920ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedFallbackElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedContextMeanCropArea"] == pytest.approx(1600.0, abs=0.01)
    assert diagnostics["proposalDirectSeedTightMeanCropArea"] == 0.0


def test_recover_ball_rows_respects_custom_direct_seed_retry_scales(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    predict_calls = []

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def predict(self, frame_image, **kwargs):
            predict_calls.append(kwargs["imgsz"])
            if kwargs["imgsz"] == 640:
                return [FakeResult([FakeBox([8.0, 8.0, 18.0, 18.0])])]
            return [FakeResult([])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows, diagnostics = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={
            0: [
                {
                    "window": (0, 0, 40, 40),
                    "proposalSeedCenter": (20.0, 20.0),
                    "proposalWindowKind": "reviewed_positive_audit_context_8",
                    "proposalSeedMode": "reviewed_positive_anchor",
                }
            ]
        },
        direct_seed_retry_scales=(1600, 640, 960),
        return_diagnostics=True,
    )

    assert predict_calls == [1600, 640]
    assert len(rows) == 1
    assert rows[0]["ProposalInferenceMode"] == "scale_640_retry"
    assert diagnostics["proposalDirectSeedScale640AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale640RawDetectionFrames"] == 1
    assert diagnostics["proposalDirectSeedScale640CandidateFrames"] == 1
    assert diagnostics["proposalDirectSeedScale960AttemptFrames"] == 0


def test_recover_ball_rows_does_not_retry_when_base_direct_seed_detection_is_filtered_out(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    predict_calls = []

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def predict(self, frame_image, **kwargs):
            predict_calls.append(kwargs["imgsz"])
            return [FakeResult([FakeBox([0.5, 0.5, 8.5, 8.5])])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows, diagnostics = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={
            0: [
                {
                    "window": (0, 0, 40, 40),
                    "proposalSeedCenter": (20.0, 20.0),
                    "proposalWindowKind": "direct_seed_tight",
                    "proposalSeedMode": "exact",
                }
            ]
        },
        crop_edge_margin=2,
        return_diagnostics=True,
    )

    assert predict_calls == [
        run_guerilla.resolve_ball_recovery_settings(
            run_guerilla.TRACKING_IMGSZ,
            run_guerilla.TRACKING_CONF,
        )["imgsz"]
    ]
    assert rows == []
    assert diagnostics["proposalDirectSeedHiResRetryFrames"] == 0
    assert diagnostics["proposalDirectSeedHiResRetryDetectedFrames"] == 0
    assert diagnostics["proposalDirectSeedZeroDetectFrames"] == 1
    assert diagnostics["proposalDirectSeedScale1600RawDetectionFrames"] == 1
    assert diagnostics["proposalDirectSeedScale960RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1920RawDetectionFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale960CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1920CandidateFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600AttemptFrames"] == 1
    assert diagnostics["proposalDirectSeedScale960AttemptFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1920AttemptFrames"] == 0
    assert diagnostics["proposalDirectSeedMultiScaleRetryFrames"] == 0
    assert diagnostics["proposalDirectSeedMultiScaleDetectedFrames"] == 0
    assert diagnostics["proposalDirectSeedRawHitFilteredOutFrames"] == 1
    assert diagnostics["proposalDirectSeedCropEdgeRejectedFrames"] == 1
    assert diagnostics["proposalDirectSeedCropCenterYRejectedFrames"] == 0
    assert diagnostics["proposalDirectSeedPitchPolygonRejectedFrames"] == 0
    assert diagnostics["proposalDirectSeedScale1600ElapsedSeconds"] >= 0.0
    assert diagnostics["proposalDirectSeedScale960ElapsedSeconds"] == 0.0
    assert diagnostics["proposalDirectSeedScale1920ElapsedSeconds"] == 0.0
    assert diagnostics["proposalDirectSeedFallbackElapsedSeconds"] >= 0.0


def test_build_recovery_profile_matrix_includes_elapsed_timing_fields():
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": True,
                "candidateSummary": {
                    "uniqueFrames": 8,
                    "proposalDirectSeedScale1600AttemptFrames": 8,
                    "proposalDirectSeedScale960AttemptFrames": 3,
                    "proposalDirectSeedScale1920AttemptFrames": 1,
                    "proposalDirectSeedScale1600ElapsedSeconds": 12.25,
                    "proposalDirectSeedScale960ElapsedSeconds": 4.5,
                    "proposalDirectSeedScale1920ElapsedSeconds": 1.75,
                    "proposalDirectSeedFallbackElapsedSeconds": 18.5,
                    "directSeedRetryPolicy": "bounded_multiscale_fallback",
                    "directSeedRetryScales": [1600, 960, 1920],
                },
                "selectedSummary": {"frames": 3},
                "elapsedSeconds": 21.0,
                "selectedRows": [{}, {}, {}],
                "candidateRows": [{}, {}, {}, {}],
            }
        ],
        selected_profile_name="proposal_windows_075",
    )

    profile = matrix["profiles"][0]
    assert profile["elapsedSeconds"] == 21.0
    assert profile["proposalDirectSeedScale1600AttemptFrames"] == 8
    assert profile["proposalDirectSeedScale960AttemptFrames"] == 3
    assert profile["proposalDirectSeedScale1920AttemptFrames"] == 1
    assert profile["proposalDirectSeedScale1600ElapsedSeconds"] == 12.25
    assert profile["proposalDirectSeedScale960ElapsedSeconds"] == 4.5
    assert profile["proposalDirectSeedScale1920ElapsedSeconds"] == 1.75
    assert profile["proposalDirectSeedFallbackElapsedSeconds"] == 18.5


def test_build_recovery_profile_matrix_includes_frame_level_proposal_selection_diagnostics():
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": False,
                "candidateSummary": {
                    "uniqueFrames": 2,
                    "proposalRawDetectedFrames": 2,
                    "proposalCollapsedFrames": 2,
                },
                "selectedSummary": {"frames": 1},
                "candidateRows": [
                    {"Frame_ID": 240, "ProposalWindowKind": "direct_seed_tight"},
                    {"Frame_ID": 245, "ProposalWindowKind": "player_ranked"},
                    {"Frame_ID": 245, "ProposalWindowKind": "direct_seed_context"},
                ],
                "selectedRows": [{"Frame_ID": 245}],
            }
        ],
        selected_profile_name=None,
    )

    profile = matrix["profiles"][0]
    assert profile["proposalRawDetectedFrameIds"] == [240, 245]
    assert profile["proposalCollapsedFrameIds"] == [240, 245]
    assert profile["proposalSelectedFrameIds"] == [245]
    assert profile["proposalFrameDiagnostics"] == [
        {
            "frameIndex": 240,
            "proposalGenerated": True,
            "rawDetected": True,
            "collapsed": True,
            "selected": False,
            "accepted": False,
            "proposalWindowKinds": ["direct_seed_tight"],
        },
        {
            "frameIndex": 245,
            "proposalGenerated": True,
            "rawDetected": True,
            "collapsed": True,
            "selected": True,
            "accepted": False,
            "acceptanceGateTrace": {
                "acceptedTruthLayerMatch": False,
                "acceptanceGateRejected": True,
                "continuityRejected": False,
                "repeatedAnchorRejected": False,
                "acceptedByReviewedPositiveProfile": False,
                "acceptanceRejectionReason": "source_profile_not_viable",
                "selectedProfileAccepted": False,
                "selectedProfileName": None,
                "sourceProfileName": "proposal_windows_075",
                "sourceProfileViable": False,
                "viabilityOverrideApplied": False,
                "viabilityOverrideReason": "",
                "viabilityRejected": True,
            },
            "proposalWindowKinds": ["direct_seed_context", "player_ranked"],
        },
    ]


def test_recover_ball_rows_dedupes_overlapping_multi_window_candidates(monkeypatch):
    frame = np.zeros((80, 80, 3), dtype=np.uint8)

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, coords):
            self.boxes = [FakeBox(coords)]

    class FakeModel:
        def predict(self, frame_image, **_kwargs):
            if frame_image.shape[:2] == (40, 40):
                return [FakeResult([5.0, 5.0, 15.0, 15.0])]
            return [FakeResult([5.0, 5.0, 15.0, 15.0])]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={0: [(0, 0, 40, 40), (4, 4, 44, 44)]},
    )

    assert len(rows) == 1
    assert rows[0]["Source_X1"] == 5.0


def test_run_ball_recovery_experiment_reports_proposal_diagnostics_in_profile_summaries(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    seen_crop_windows = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 10.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    def fake_recover_ball_rows(*_args, **kwargs):
        seen_crop_windows.append(kwargs.get("crop_windows_by_frame"))
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 50.0, "Conf": 0.31},
        ]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)

    results = run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        observed_source_anchors={0: (40.0, 50.0)},
        player_rows=[
            {
                "Frame_ID": 0,
                "Entity_Type": "player",
                "Track_ID": 10,
                "Conf": 0.9,
                "Source_X1": 10.0,
                "Source_Y1": 20.0,
                "Source_X2": 30.0,
                "Source_Y2": 60.0,
            },
            {
                "Frame_ID": 0,
                "Entity_Type": "player",
                "Track_ID": 11,
                "Conf": 0.7,
                "Source_X1": 60.0,
                "Source_Y1": 20.0,
                "Source_X2": 80.0,
                "Source_Y2": 60.0,
            },
            {
                "Frame_ID": 5,
                "Entity_Type": "player",
                "Track_ID": 12,
                "Conf": 0.8,
                "Source_X1": 90.0,
                "Source_Y1": 20.0,
                "Source_X2": 110.0,
                "Source_Y2": 60.0,
            },
        ],
        profiles=[
            {
                "name": "proposal_windows_075",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "cropMode": "proposal_windows",
                "maxCropWidthRatio": 0.35,
                "proposalMaxWindowsPerFrame": 2,
                "proposalCropWidthRatio": 0.35,
            }
        ],
    )

    assert seen_crop_windows[0] is not None
    assert len(seen_crop_windows[0][0]) == 2
    candidate_summary = results[0]["candidateSummary"]
    selected_summary = results[0]["selectedSummary"]
    assert candidate_summary["proposalCandidateFrames"] == 2
    assert candidate_summary["proposalWindowCount"] == 4
    assert candidate_summary["proposalDirectSeedWindowFrames"] == 4
    assert candidate_summary["proposalDirectSeedTightWindowFrames"] == 2
    assert candidate_summary["proposalDirectSeedContextWindowFrames"] == 2
    assert candidate_summary["proposalDirectSeedContextEligibleFrames"] == 2
    assert candidate_summary["proposalDirectSeedContextDuplicateFrames"] == 0
    assert candidate_summary["proposalDirectSeedContextMeanSeedToBoxDistance"] > 0.0
    assert candidate_summary["proposalPlayerRankedWindowFrames"] == 0
    assert candidate_summary["proposalFramesWithAnchorSeed"] == 1
    assert candidate_summary["proposalFramesWithoutAnchorSeed"] == 1
    assert candidate_summary["proposalMeanWindowWidth"] > 0.0
    assert candidate_summary["proposalRawDetectedFrames"] == 1
    assert candidate_summary["proposalAfterSeedCollapseFrames"] == 1
    assert candidate_summary["proposalAfterPlayerWindowFrames"] == 1
    assert candidate_summary["proposalAfterFalseBallSuppressionFrames"] == 1
    assert candidate_summary["proposalCollapsedFrames"] == 1
    assert candidate_summary["proposalCollapsedSegmentCount"] == 1
    assert selected_summary["proposalCandidateFrames"] == 2
    assert selected_summary["proposalWindowCount"] == 4


def test_run_ball_recovery_experiment_uses_raw_same_frame_rows_for_proposal_profiles(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    recover_kwargs = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 5.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    def fake_recover_ball_rows(*_args, **kwargs):
        recover_kwargs.append(dict(kwargs))
        return [
            {
                "Frame_ID": 0,
                "Entity_Type": "ball",
                "X": 18.0,
                "Y": 24.0,
                "Conf": 0.31,
                "Source_X1": 10.0,
                "Source_Y1": 16.0,
                "Source_X2": 18.0,
                "Source_Y2": 28.0,
                "ProposalSeedX": 14.0,
                "ProposalSeedY": 22.0,
                "ProposalCropWidth": 30.0,
                "ProposalCropHeight": 30.0,
            },
            {
                "Frame_ID": 0,
                "Entity_Type": "ball",
                "X": 42.0,
                "Y": 24.0,
                "Conf": 0.93,
                "Source_X1": 34.0,
                "Source_Y1": 16.0,
                "Source_X2": 42.0,
                "Source_Y2": 28.0,
                "ProposalSeedX": 14.0,
                "ProposalSeedY": 22.0,
                "ProposalCropWidth": 30.0,
                "ProposalCropHeight": 30.0,
            },
        ]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla, "filter_recovered_ball_rows_for_profile", lambda rows, *_args, **_kwargs: list(rows))
    monkeypatch.setattr(run_guerilla, "suppress_repeated_false_ball_clusters", lambda rows, **_kwargs: list(rows))
    monkeypatch.setattr(run_guerilla, "select_meaningful_recovered_ball_rows", lambda rows, **_kwargs: list(rows))

    results = run_guerilla.run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        observed_source_anchors={0: (14.0, 22.0)},
        player_rows=[
            {"Frame_ID": 0, "Entity_Type": "player", "X": 16.0, "Y": 24.0, "Conf": 0.9},
        ],
        profiles=[
            {
                "name": "proposal_windows_075",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "cropMode": "proposal_windows",
                "maxCropWidthRatio": 0.35,
                "proposalMaxWindowsPerFrame": 2,
                "proposalCropWidthRatio": 0.35,
            }
        ],
    )

    assert recover_kwargs[0]["dedupe_same_frame"] is False
    assert len(results[0]["candidateRows"]) == 1
    assert results[0]["candidateRows"][0]["Source_X1"] == 10.0
    assert results[0]["candidateSummary"]["proposalAfterSeedCollapseFrames"] == 1


def test_run_ball_recovery_experiment_emits_recovery_profile_progress(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    progress_events = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 10.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    def fake_recover_ball_rows(*_args, **kwargs):
        progress_callback = kwargs["progress_callback"]
        progress_callback(
            {
                "stageStatus": "profile_in_progress",
                "recoveryProfileName": "proposal_windows_075",
                "recoveryProfileIndex": 1,
                "recoveryProfileCount": 1,
                "proposalDirectSeedScale1600AttemptFrames": 12,
                "proposalDirectSeedScale1600ElapsedSeconds": 3.25,
            }
        )
        return (
            [{"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 50.0, "Conf": 0.31}],
            {
                "proposalDirectSeedHiResRetryFrames": 1,
                "proposalDirectSeedHiResRetryDetectedFrames": 1,
                "proposalDirectSeedScale1600AttemptFrames": 12,
                "proposalDirectSeedScale960AttemptFrames": 4,
                "proposalDirectSeedScale1920AttemptFrames": 1,
                "proposalDirectSeedScale1600ElapsedSeconds": 3.25,
                "proposalDirectSeedScale960ElapsedSeconds": 1.5,
                "proposalDirectSeedScale1920ElapsedSeconds": 0.75,
                "proposalDirectSeedFallbackElapsedSeconds": 5.5,
            },
        )

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)

    run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        observed_source_anchors={0: (40.0, 50.0)},
        player_rows=[
            {
                "Frame_ID": 0,
                "Entity_Type": "player",
                "Track_ID": 10,
                "Conf": 0.9,
                "Source_X1": 10.0,
                "Source_Y1": 20.0,
                "Source_X2": 30.0,
                "Source_Y2": 60.0,
            }
        ],
        profiles=[
            {
                "name": "proposal_windows_075",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "cropMode": "proposal_windows",
                "maxCropWidthRatio": 0.35,
                "proposalMaxWindowsPerFrame": 2,
                "proposalCropWidthRatio": 0.35,
            }
        ],
        progress_callback=progress_events.append,
    )

    stage_statuses = [payload["stageStatus"] for payload in progress_events]
    assert stage_statuses == [
        "profile_started",
        "profile_in_progress",
        "profile_recovered",
        "profile_completed",
    ]
    assert all(payload["recoveryProfileName"] == "proposal_windows_075" for payload in progress_events)
    assert progress_events[1]["proposalDirectSeedScale1600AttemptFrames"] == 12
    assert progress_events[2]["proposalDirectSeedScale960AttemptFrames"] == 4
    assert progress_events[3]["recoveryProfileElapsedSeconds"] >= 0.0
    assert "recoveryProfileAnchoredFrameCount" in progress_events[3]
    assert "recoveryProfileSupportedFrameShare" in progress_events[3]
    assert "recoveryProfileAnchoredFrameShare" in progress_events[3]
    assert "recoveryProfileAnchoredPathLength" in progress_events[3]
    assert "recoveryProfileUnsupportedEdgeFrameShare" in progress_events[3]
    assert "recoveryProfileBridgeFrameCount" in progress_events[3]
    assert "recoveryProfileSelectedScore" in progress_events[3]


def test_build_recovery_profile_matrix_persists_proposal_funnel_fields():
    matrix = run_guerilla._build_recovery_profile_matrix(
        [
            {
                "name": "proposal_windows_075",
                "cropMode": "proposal_windows",
                "viable": True,
                "candidateSummary": {
                    "uniqueFrames": 9,
                    "segmentCount": 6,
                    "proposalCandidateFrames": 111,
                    "proposalWindowCount": 333,
                    "proposalFramesWithAnchorSeed": 81,
                    "proposalFramesWithoutAnchorSeed": 30,
                    "proposalExactSeedFrames": 81,
                    "proposalInterpolatedSeedFrames": 4,
                    "proposalSingleSeedFrames": 26,
                    "proposalUnseededFrames": 1405,
                    "proposalDirectSeedWindowFrames": 73,
                    "proposalDirectSeedTightWindowFrames": 51,
                    "proposalDirectSeedContextWindowFrames": 22,
                    "proposalDirectSeedContextEligibleFrames": 24,
                    "proposalDirectSeedContextDuplicateFrames": 2,
                    "proposalDirectSeedContextMeanSeedToBoxDistance": 17.5,
                    "proposalPlayerRankedWindowFrames": 38,
                    "proposalMeanWindowWidth": 104.78,
                    "proposalRawDetectedFrames": 150,
                    "proposalAfterSeedCollapseFrames": 111,
                    "proposalAfterPlayerWindowFrames": 95,
                    "proposalAfterFalseBallSuppressionFrames": 87,
                    "proposalCollapsedFrames": 9,
                    "proposalCollapsedSegmentCount": 6,
                    "proposalDirectSeedDetectedFrames": 44,
                    "proposalDirectSeedTightDetectedFrames": 19,
                    "proposalDirectSeedContextDetectedFrames": 25,
                    "proposalDirectSeedHiResRetryFrames": 12,
                    "proposalDirectSeedHiResRetryDetectedFrames": 5,
                    "proposalDirectSeedZeroDetectFrames": 31,
                    "proposalDirectSeedMeanCropArea": 1024.5,
                    "proposalPlayerRankedMeanCropArea": 2048.0,
                    "proposalDirectSeedMeanDetectedBallBoxArea": 43.25,
                    "proposalPlayerRankedMeanDetectedBallBoxArea": 67.5,
                    "proposalPlayerRankedDetectedFrames": 106,
                    "proposalExactSeedDetectedFrames": 81,
                    "proposalInterpolatedSeedDetectedFrames": 27,
                    "proposalSingleSeedDetectedFrames": 42,
                },
                "selectedSummary": {
                    "frames": 9,
                    "segmentCount": 0,
                },
            }
        ],
        selected_profile_name="proposal_windows_075",
    )

    assert matrix["selectedProfileName"] == "proposal_windows_075"
    assert len(matrix["profiles"]) == 1
    profile = matrix["profiles"][0]
    assert profile["proposalRawDetectedFrames"] == 150
    assert profile["proposalAfterSeedCollapseFrames"] == 111
    assert profile["proposalAfterPlayerWindowFrames"] == 95
    assert profile["proposalAfterFalseBallSuppressionFrames"] == 87
    assert profile["proposalCollapsedFrames"] == 9
    assert profile["proposalCollapsedSegmentCount"] == 6
    assert profile["proposalDirectSeedDetectedFrames"] == 44
    assert profile["proposalDirectSeedTightDetectedFrames"] == 19
    assert profile["proposalDirectSeedContextDetectedFrames"] == 25
    assert profile["proposalDirectSeedHiResRetryFrames"] == 12
    assert profile["proposalDirectSeedHiResRetryDetectedFrames"] == 5
    assert profile["proposalDirectSeedZeroDetectFrames"] == 31
    assert profile["proposalDirectSeedMeanCropArea"] == 1024.5
    assert profile["proposalPlayerRankedMeanCropArea"] == 2048.0
    assert profile["proposalDirectSeedMeanDetectedBallBoxArea"] == 43.25
    assert profile["proposalPlayerRankedMeanDetectedBallBoxArea"] == 67.5
    assert profile["proposalDirectSeedContextEligibleFrames"] == 24
    assert profile["proposalDirectSeedContextDuplicateFrames"] == 2
    assert profile["proposalDirectSeedContextMeanSeedToBoxDistance"] == 17.5
    assert profile["proposalPlayerRankedDetectedFrames"] == 106
    assert profile["proposalExactSeedDetectedFrames"] == 81
    assert profile["proposalInterpolatedSeedDetectedFrames"] == 27
    assert profile["proposalSingleSeedDetectedFrames"] == 42


def test_proposal_windows_pre_collapse_prefers_lower_seed_distance_over_higher_confidence_farther_row(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 5.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    class FakeBox:
        def __init__(self, coords, conf):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def predict(self, frame_image, **_kwargs):
            if frame_image.shape[1] == 40:
                return [
                    FakeResult(
                        [
                            FakeBox([12.0, 18.0, 20.0, 30.0], 0.54),
                            FakeBox([28.0, 18.0, 36.0, 30.0], 0.91),
                        ]
                    )
                ]
            return [
                FakeResult(
                    [
                        FakeBox([1.0, 1.0, 9.0, 11.0], 0.95),
                    ]
                )
            ]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        crop_windows_by_frame={0: [(0, 0, 40, 40), (40, 0, 80, 40)]},
        dedupe_same_frame=False,
    )

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        rows,
        player_rows=[
            {"Frame_ID": 0, "Entity_Type": "player", "X": 26.0, "Y": 28.0, "Conf": 0.9},
        ],
        max_frame_gap=5,
    )

    assert collapsed["proposalRawDetectedFrames"] == 1
    assert collapsed["proposalAfterSeedCollapseFrames"] == 1
    assert collapsed["proposalCollapsedFrames"] == 1
    assert collapsed["proposalCollapsedSegmentCount"] == 1
    assert len(collapsed["rows"]) == 1
    assert collapsed["rows"][0]["Source_X1"] == 12.0
    assert collapsed["rows"][0]["Source_Y1"] == 18.0
    assert collapsed["proposalDirectSeedDetectedFrames"] == 0
    assert collapsed["proposalPlayerRankedDetectedFrames"] == 1
    assert collapsed["proposalExactSeedDetectedFrames"] == 1


def test_proposal_windows_pre_collapse_prefers_direct_seed_context_over_tight_on_full_tie():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "X": 10.0,
            "Y": 10.0,
            "Conf": 0.6,
            "Source_X1": 8.0,
            "Source_Y1": 8.0,
            "Source_X2": 12.0,
            "Source_Y2": 12.0,
            "ProposalSeedX": 10.0,
            "ProposalSeedY": 10.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_tight",
            "ProposalSeedMode": "exact",
        },
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "X": 10.0,
            "Y": 10.0,
            "Conf": 0.6,
            "Source_X1": 8.0,
            "Source_Y1": 8.0,
            "Source_X2": 12.0,
            "Source_Y2": 12.0,
            "ProposalSeedX": 10.0,
            "ProposalSeedY": 10.0,
            "ProposalCropWidth": 20.0,
            "ProposalCropHeight": 20.0,
            "ProposalWindowKind": "direct_seed_context",
            "ProposalSeedMode": "exact",
        },
    ]

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(rows, player_rows=[], max_frame_gap=5)

    assert len(collapsed["rows"]) == 1
    assert collapsed["rows"][0]["ProposalWindowKind"] == "direct_seed_context"
    assert collapsed["proposalDirectSeedDetectedFrames"] == 1
    assert collapsed["proposalDirectSeedTightDetectedFrames"] == 1
    assert collapsed["proposalDirectSeedContextDetectedFrames"] == 1


def test_score_ball_track_summary_penalizes_edge_dominated_motion():
    centered_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 52.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 51.0, "Conf": 0.20},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.0, "Conf": 0.20},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 52.0, "Y": 47.0, "Conf": 0.20},
    ])
    edge_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 12.0, "Y": 96.6, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 16.0, "Y": 96.8, "Conf": 0.20},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 20.0, "Y": 97.0, "Conf": 0.20},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 24.0, "Y": 97.2, "Conf": 0.20},
    ])

    assert edge_summary["edgeFrameShare"] == 1.0
    assert centered_summary["edgeFrameShare"] == 0.0
    assert score_ball_track_summary(centered_summary) > score_ball_track_summary(edge_summary)


def test_ball_track_summary_is_not_viable_when_edge_dominated():
    edge_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 12.0, "Y": 96.6, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 16.0, "Y": 96.8, "Conf": 0.20},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 20.0, "Y": 97.0, "Conf": 0.20},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 24.0, "Y": 97.2, "Conf": 0.20},
    ])
    centered_summary = summarize_ball_track_rows([
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 52.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 51.0, "Conf": 0.20},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.0, "Conf": 0.20},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 52.0, "Y": 47.0, "Conf": 0.20},
    ])

    assert ball_track_summary_is_viable(edge_summary) is False
    assert ball_track_summary_is_viable(centered_summary) is True


def test_summarize_recovered_ball_candidates_reports_edge_window_and_confidence_mix():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "X": 12.0,
            "Y": 96.6,
            "Conf": 0.08,
            "Source_X1": 90.0,
            "Source_Y1": 90.0,
            "Source_X2": 110.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "X": 45.0,
            "Y": 52.0,
            "Conf": 0.31,
            "Source_X1": 130.0,
            "Source_Y1": 130.0,
            "Source_X2": 150.0,
            "Source_Y2": 150.0,
        },
        {
            "Frame_ID": 15,
            "Entity_Type": "ball",
            "X": 48.0,
            "Y": 49.0,
            "Conf": 0.18,
            "Source_X1": 500.0,
            "Source_Y1": 500.0,
            "Source_X2": 520.0,
            "Source_Y2": 520.0,
        },
    ]
    player_windows = {
        0: [400.0, 400.0, 460.0, 460.0],
        5: [120.0, 120.0, 160.0, 160.0],
        15: [0.0, 0.0, 100.0, 100.0],
    }

    summary = summarize_recovered_ball_candidates(rows, player_windows=player_windows)

    assert summary["candidateRows"] == 3
    assert summary["uniqueFrames"] == 3
    assert summary["edgeCandidateShare"] == 0.333
    assert summary["nearPlayerWindowShare"] == 0.333
    assert summary["confidenceBands"] == {"low": 1, "medium": 1, "high": 1}
    assert summary["segmentCount"] == 2
    assert summary["longestSegmentFrames"] == 2


def test_summarize_recovered_ball_candidates_counts_unique_frames_per_segment():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 10.0, "Y": 20.0, "Conf": 0.09},
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 11.0, "Y": 21.0, "Conf": 0.08},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 12.0, "Y": 22.0, "Conf": 0.07},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 13.0, "Y": 23.0, "Conf": 0.06},
    ]

    summary = summarize_recovered_ball_candidates(rows, max_frame_gap=5)

    assert summary["segmentCount"] == 1
    assert summary["longestSegmentFrames"] == 3


def test_summarize_recovered_ball_candidates_reports_dominant_anchor_for_anchored_false_ball_pattern():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "X": 10.0,
            "Y": 20.0,
            "Conf": 0.09,
            "Source_X1": 90.0,
            "Source_Y1": 90.0,
            "Source_X2": 110.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "X": 10.0,
            "Y": 20.0,
            "Conf": 0.08,
            "Source_X1": 90.0,
            "Source_Y1": 90.0,
            "Source_X2": 110.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 10,
            "Entity_Type": "ball",
            "X": 65.0,
            "Y": 70.0,
            "Conf": 0.07,
            "Source_X1": 300.0,
            "Source_Y1": 300.0,
            "Source_X2": 340.0,
            "Source_Y2": 340.0,
        },
    ]

    summary = summarize_recovered_ball_candidates(rows)

    assert summary["dominantAnchorCoord"] == (10.0, 20.0)
    assert summary["dominantAnchorCount"] == 2
    assert summary["dominantAnchorShare"] == 0.667
    assert summary["meanSourceCenterY"] == 173.33
    assert summary["meanSourceBoxArea"] == 800.0


def test_summarize_recovered_ball_candidates_empty_summary_includes_new_keys_with_safe_defaults():
    summary = summarize_recovered_ball_candidates([])

    assert summary == {
        "candidateRows": 0,
        "uniqueFrames": 0,
        "meanConfidence": 0.0,
        "edgeCandidateShare": 0.0,
        "nearPlayerWindowShare": 0.0,
        "confidenceBands": {"low": 0, "medium": 0, "high": 0},
        "segmentCount": 0,
        "longestSegmentFrames": 0,
        "dominantAnchorCoord": None,
        "dominantAnchorCount": 0,
        "dominantAnchorShare": 0.0,
        "meanSourceCenterY": 0.0,
        "meanSourceBoxArea": 0.0,
    }


def test_suppress_repeated_false_ball_clusters_removes_edge_anchor_cluster():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.31},
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 42.0, "Y": 54.0, "Conf": 0.21},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 46.0, "Y": 52.0, "Conf": 0.22},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 49.0, "Conf": 0.23},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.28},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 55.0, "Y": 46.0, "Conf": 0.24},
    ]

    filtered_rows = suppress_repeated_false_ball_clusters(rows)

    assert [row["Frame_ID"] for row in filtered_rows] == [0, 5, 10, 15]
    assert max(row["X"] for row in filtered_rows) < 60.0
    assert ball_rows_show_meaningful_motion(filtered_rows) is True


def test_suppress_repeated_false_ball_clusters_preserves_non_anchor_moving_candidates():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 41.0, "Y": 54.0, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.5, "Y": 53.0, "Conf": 0.28},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.5, "Conf": 0.26},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 53.5, "Y": 47.0, "Conf": 0.25},
    ]

    filtered_rows = suppress_repeated_false_ball_clusters(rows)

    assert filtered_rows == rows


def test_suppress_repeated_false_ball_clusters_removes_jittered_edge_anchor_cluster():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.7, "Y": 95.1, "Conf": 0.31},
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 42.0, "Y": 54.0, "Conf": 0.21},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 97.6, "Y": 94.8, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 46.0, "Y": 52.0, "Conf": 0.22},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.2, "Y": 96.0, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 49.0, "Conf": 0.23},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 97.1, "Y": 95.4, "Conf": 0.28},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 55.0, "Y": 46.0, "Conf": 0.24},
    ]

    filtered_rows = suppress_repeated_false_ball_clusters(rows)

    assert [row["Frame_ID"] for row in filtered_rows] == [0, 5, 10, 15]
    assert max(row["X"] for row in filtered_rows) < 60.0
    assert ball_rows_show_meaningful_motion(filtered_rows) is True


def test_suppress_repeated_false_ball_clusters_keeps_nearby_legitimate_moving_chain():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.7, "Y": 95.1, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 95.0, "Y": 92.8, "Conf": 0.30},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 92.8, "Y": 89.9, "Conf": 0.29},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 89.4, "Y": 85.6, "Conf": 0.28},
    ]

    filtered_rows = suppress_repeated_false_ball_clusters(rows)

    assert filtered_rows == rows
    assert ball_rows_show_meaningful_motion(filtered_rows) is True


def test_collapse_recovered_ball_candidates_prefers_coherent_continuation_over_higher_confidence_incoherent_candidate():
    player_rows = []
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 42.0, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 90.0, "Y": 90.0, "Conf": 0.95},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 44.0, "Conf": 0.25},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=player_rows, max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5, 10]
    assert collapse["rows"][1]["X"] == 44.0
    assert collapse["continuityPreferredFrames"] == 2
    assert collapse["continuityRejectedFrames"] == 1


def test_collapse_recovered_ball_candidates_prefers_anchored_over_unanchored_when_continuity_ties():
    player_rows = [
        {"Frame_ID": 5, "Entity_Type": "player", "X": 93.0, "Y": 93.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 94.0, "Y": 94.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 93.0, "Y": 93.0, "Conf": 0.28},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.0, "Y": 96.0, "Conf": 0.40},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=player_rows, max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5]
    assert collapse["rows"][1]["X"] == 93.0


def test_collapse_recovered_ball_candidates_prefers_supported_over_unsupported_when_anchored_ties():
    player_rows = [
        {"Frame_ID": 5, "Entity_Type": "player", "X": 96.0, "Y": 50.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 94.0, "Y": 50.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.0, "Y": 50.0, "Conf": 0.28},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 70.0, "Y": 50.0, "Conf": 0.40},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=player_rows, max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5]
    assert collapse["rows"][1]["X"] == 96.0


def test_collapse_recovered_ball_candidates_prefers_non_edge_over_edge_when_support_ties():
    player_rows = [
        {"Frame_ID": 5, "Entity_Type": "player", "X": 96.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "player", "X": 90.0, "Y": 50.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 94.0, "Y": 50.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.0, "Y": 50.0, "Conf": 0.40},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 90.0, "Y": 50.0, "Conf": 0.28},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=player_rows, max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5]
    assert collapse["rows"][1]["X"] == 90.0


def test_collapse_recovered_ball_candidates_prefers_lower_step_distance_when_quality_ties_without_continuity():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 75.0, "Y": 75.0, "Conf": 0.40},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 43.0, "Conf": 0.40},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=[], max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5]
    assert collapse["rows"][1]["X"] == 44.0


def test_collapse_recovered_ball_candidates_is_deterministic_on_exact_ties():
    player_rows = [
        {"Frame_ID": 5, "Entity_Type": "player", "X": 50.0, "Y": 50.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 50.0, "Y": 50.0, "Conf": 0.20},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 60.0, "Y": 60.0, "Conf": 0.30, "Source_X1": 10.0, "Source_Y1": 20.0, "Source_X2": 30.0, "Source_Y2": 40.0},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 60.0, "Y": 60.0, "Conf": 0.30, "Source_X1": 50.0, "Source_Y1": 20.0, "Source_X2": 70.0, "Source_Y2": 40.0},
    ]

    collapse = run_guerilla._collapse_recovered_ball_candidates(rows, player_rows=player_rows, max_frame_gap=5)

    assert [row["Frame_ID"] for row in collapse["rows"]] == [0, 5]
    assert collapse["rows"][1]["Source_X1"] == 10.0


def test_run_ball_recovery_experiment_reports_collapsed_candidate_diagnostics(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    def fake_recover_ball_rows(*_args, **_kwargs):
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 95.0, "Y": 95.0, "Conf": 0.20},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 93.0, "Y": 93.0, "Conf": 0.28},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.0, "Y": 96.0, "Conf": 0.40},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 50.0, "Conf": 0.26},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 20.0, "Y": 20.0, "Conf": 0.25},
        ]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)

    results = run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        player_rows=[
            {"Frame_ID": 0, "Entity_Type": "player", "X": 95.0, "Y": 95.0, "Conf": 0.9},
            {"Frame_ID": 5, "Entity_Type": "player", "X": 93.0, "Y": 93.0, "Conf": 0.9},
        ],
        profiles=[
            {"name": "baseline", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": False},
        ],
    )

    summary = results[0]["candidateSummary"]
    assert summary["collapsedCandidateFrames"] == 3
    assert summary["collapsedSegmentCount"] == 1
    assert summary["collapsedLongestSegmentFrames"] == 3
    assert summary["continuityPreferredFrames"] == 1
    assert summary["continuityRejectedFrames"] == 1
    assert summary["midfieldCollapsedFrames"] == 1
    assert results[0]["rows"] == results[0]["selectedRows"]


def test_build_ball_truth_layers_prunes_repeated_probe_clusters_before_observed_ball_filter(monkeypatch):
    captured_probe_rows = []

    def fake_filter_probe_observed_ball_rows(probe_rows, **_kwargs):
        captured_probe_rows.extend(probe_rows)
        return {
            "rawRows": list(probe_rows),
            "filteredRows": list(probe_rows),
            "rawFrameCount": len({int(row["Frame_ID"]) for row in probe_rows}),
            "filteredFrameCount": len({int(row["Frame_ID"]) for row in probe_rows}),
            "suppressedFrameCount": 0,
            "anchoredFrameCount": 0,
            "bridgeFrameCount": 0,
        }

    probe_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.31},
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 42.0, "Y": 54.0, "Conf": 0.21},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 46.0, "Y": 52.0, "Conf": 0.22},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 49.0, "Conf": 0.23},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.28},
        {"Frame_ID": 15, "Entity_Type": "ball", "X": 55.0, "Y": 46.0, "Conf": 0.24},
    ]

    monkeypatch.setattr(run_guerilla, "_filter_probe_observed_ball_rows", fake_filter_probe_observed_ball_rows)

    layers = run_guerilla._build_ball_truth_layers(
        observed_rows=[],
        inferred_rows=[],
        probe_observed_rows=probe_rows,
        sample_interval=5,
        player_rows=[],
    )

    assert captured_probe_rows
    assert max(row["X"] for row in captured_probe_rows) < 60.0
    assert layers["observedBall"]["rows"]


def test_process_video_does_not_pre_drop_recovery_rows_before_final_observed_overlap_resolution(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 20.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60]), FakeBox(32, 0.41, None, [40, 20, 50, 60])])])

        def predict(self, *_args, **_kwargs):
            return [FakeResult([])]

    captured_selected_rows = {}
    real_build_ball_truth_layers = run_guerilla._build_ball_truth_layers

    def capture_build_ball_truth_layers(*args, **kwargs):
        captured_selected_rows["rows"] = list(args[1])
        return real_build_ball_truth_layers(*args, **kwargs)

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla, "_build_ball_truth_layers", capture_build_ball_truth_layers)
    monkeypatch.setattr(
        run_guerilla,
        "run_ball_recovery_experiment",
        lambda *args, **kwargs: [
            {
                "name": "baseline",
                "candidateSummary": {
                    "candidateRows": 3,
                    "uniqueFrames": 3,
                    "edgeCandidateShare": 0.0,
                    "nearPlayerWindowShare": 0.0,
                    "proposalRawDetectedFrames": 5,
                    "proposalAfterSeedCollapseFrames": 3,
                    "proposalAfterPlayerWindowFrames": 2,
                    "proposalAfterFalseBallSuppressionFrames": 2,
                    "proposalCollapsedFrames": 2,
                    "proposalCollapsedSegmentCount": 1,
                    "segmentCount": 1,
                    "longestSegmentFrames": 3,
                    "collapsedCandidateFrames": 3,
                    "collapsedSegmentCount": 1,
                    "collapsedLongestSegmentFrames": 3,
                    "continuityPreferredFrames": 1,
                    "continuityRejectedFrames": 0,
                    "midfieldCollapsedFrames": 3,
                },
                "selectedSummary": {"frames": 3, "pathLength": 0.0, "edgeFrameShare": 0.0},
                "selectedScore": 0.0,
                "viable": True,
                "selectedRows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 10.0, "Y": 20.0, "Conf": 0.2},
                    {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 12.0, "Y": 22.0, "Conf": 0.2},
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 14.0, "Y": 24.0, "Conf": 0.2},
                ],
            }
        ],
    )

    process_video(
        "demo.mp4",
        return_rows=True,
        auto_homography=False,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
    )

    assert [row["Frame_ID"] for row in captured_selected_rows["rows"]] == [0, 5, 10]


def test_process_video_keeps_observed_ball_rows_over_inferred_overlap_after_recovery_collapse(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 20.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60]), FakeBox(32, 0.41, None, [40, 20, 50, 60])])])

        def predict(self, *_args, **_kwargs):
            return [FakeResult([])]

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        run_guerilla,
        "run_ball_recovery_experiment",
        lambda *args, **kwargs: [
            {
                "name": "baseline",
                "candidateSummary": {
                    "candidateRows": 3,
                    "uniqueFrames": 3,
                    "edgeCandidateShare": 0.0,
                    "nearPlayerWindowShare": 0.0,
                    "proposalRawDetectedFrames": 5,
                    "proposalAfterSeedCollapseFrames": 3,
                    "proposalAfterPlayerWindowFrames": 2,
                    "proposalAfterFalseBallSuppressionFrames": 2,
                    "proposalCollapsedFrames": 2,
                    "proposalCollapsedSegmentCount": 1,
                    "segmentCount": 1,
                    "longestSegmentFrames": 3,
                    "collapsedCandidateFrames": 3,
                    "collapsedSegmentCount": 1,
                    "collapsedLongestSegmentFrames": 3,
                    "continuityPreferredFrames": 1,
                    "continuityRejectedFrames": 0,
                    "midfieldCollapsedFrames": 3,
                },
                "selectedSummary": {"frames": 3, "pathLength": 0.0, "edgeFrameShare": 0.0},
                "selectedScore": 0.0,
                "viable": True,
                "selectedRows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 10.0, "Y": 20.0, "Conf": 0.2},
                    {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 12.0, "Y": 22.0, "Conf": 0.2},
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 14.0, "Y": 24.0, "Conf": 0.2},
                ],
            }
        ],
    )

    result = process_video(
        "demo.mp4",
        return_rows=True,
        auto_homography=False,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
    )

    assert set(result["trackColors"]) == {"7"}
    ball_rows = [row for row in result["rows"] if row["Entity_Type"] == "ball"]

    assert [row["Frame_ID"] for row in ball_rows] == [0, 5, 10]
    assert ball_rows[0]["Conf"] == pytest.approx(0.41, abs=1e-6)
    assert result["ballTruthLayers"]["acceptedSourceBreakdown"] == {"observed": 1, "inferred": 2}
    assert result["recoveryDebug"]["collapsedCandidateFrames"] == 3
    assert result["recoveryDebug"]["collapsedSegmentCount"] == 1
    assert result["recoveryDebug"]["collapsedLongestSegmentFrames"] == 3
    assert result["recoveryDebug"]["continuityPreferredFrames"] == 1
    assert result["recoveryDebug"]["continuityRejectedFrames"] == 0
    assert result["recoveryDebug"]["midfieldCollapsedFrames"] == 3
    assert result["recoveryDebug"]["proposalRawDetectedFrames"] == 5
    assert result["recoveryDebug"]["proposalAfterSeedCollapseFrames"] == 3
    assert result["recoveryDebug"]["proposalAfterPlayerWindowFrames"] == 2
    assert result["recoveryDebug"]["proposalAfterFalseBallSuppressionFrames"] == 2
    assert result["recoveryDebug"]["proposalCollapsedFrames"] == 2
    assert result["recoveryDebug"]["proposalCollapsedSegmentCount"] == 1


def test_run_ball_recovery_experiment_suppresses_junk_cluster_before_summary_and_viability(monkeypatch):
    def fake_recover_ball_rows(*args, **kwargs):
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.31},
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 42.0, "Y": 54.0, "Conf": 0.21},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.30},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 46.0, "Y": 52.0, "Conf": 0.22},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.29},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 49.0, "Conf": 0.23},
            {"Frame_ID": 15, "Entity_Type": "ball", "X": 96.8, "Y": 95.3, "Conf": 0.28},
            {"Frame_ID": 15, "Entity_Type": "ball", "X": 55.0, "Y": 46.0, "Conf": 0.24},
        ]

    class FakeCapture:
        def __init__(self, _path):
            self.first_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            self.reads = 0

        def read(self):
            if self.reads > 0:
                return False, None
            self.reads += 1
            return True, self.first_frame

        def release(self):
            return None

    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", FakeCapture)

    results = run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        profiles=[
            {"name": "baseline", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": False},
        ],
    )

    assert len(results) == 1
    assert results[0]["candidateSummary"]["candidateRows"] == 4
    assert results[0]["candidateSummary"]["dominantAnchorShare"] == 0.25
    assert results[0]["selectedSummary"]["frames"] == 4
    assert results[0]["selectedSummary"]["showsMeaningfulMotion"] is True
    assert results[0]["viable"] is True


def test_run_ball_recovery_experiment_uses_player_windows_only_for_opt_in_profiles(monkeypatch):
    calls = []

    def fake_recover_ball_rows(*args, **kwargs):
        calls.append(kwargs.get("player_windows"))
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 41.0, "Y": 54.0, "Conf": 0.31},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.5, "Y": 53.0, "Conf": 0.28},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 48.0, "Y": 49.5, "Conf": 0.26},
            {"Frame_ID": 15, "Entity_Type": "ball", "X": 53.5, "Y": 47.0, "Conf": 0.25},
        ]

    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)

    profiles = [
        {"name": "baseline", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": False},
        {"name": "player_window", "settings": {"imgsz": 1920, "conf": 0.08}, "usePlayerWindows": True},
    ]

    results = run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        player_windows={0: [10.0, 20.0, 100.0, 200.0]},
        profiles=profiles,
    )

    assert [result["name"] for result in results] == ["baseline", "player_window"]
    assert calls == [None, {0: [10.0, 20.0, 100.0, 200.0]}]
    assert results[0]["candidateSummary"]["candidateRows"] == 4
    assert results[0]["selectedSummary"]["frames"] == 4
    assert results[0]["selectedScore"] == results[0]["score"]
    assert results[0]["viable"] is True
    assert results[0]["selectedRows"] == results[0]["rows"]


def test_summarize_recovered_ball_anchor_diagnostics_counts_supported_anchored_bridge_and_path_length():
    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "X": 4.0, "Y": 40.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "player", "X": 4.0, "Y": 42.0, "Conf": 0.9},
    ]
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "X": 4.0, "Y": 40.0, "Conf": 0.30},
        {"Frame_ID": 5, "Entity_Type": "ball", "X": 4.5, "Y": 41.0, "Conf": 0.20},
        {"Frame_ID": 10, "Entity_Type": "ball", "X": 4.0, "Y": 42.0, "Conf": 0.31},
    ]

    diagnostics = _summarize_recovered_ball_anchor_diagnostics(rows, player_rows=player_rows)

    assert diagnostics["supportedFrameCount"] == 2
    assert diagnostics["anchoredFrameCount"] == 2
    assert diagnostics["bridgeFrameCount"] == 1
    assert diagnostics["unsupportedEdgeFrameShare"] == pytest.approx(1 / 3, abs=1e-3)
    assert diagnostics["anchoredPathLength"] == pytest.approx(2.0, abs=1e-3)
    assert diagnostics["segmentDiagnostics"] == [
        {
            "startFrame": 0,
            "endFrame": 10,
            "frameCount": 3,
            "supportedFrameCount": 2,
            "anchoredFrameCount": 2,
            "bridgeFrameCount": 1,
            "unsupportedEdgeFrameShare": pytest.approx(1 / 3, abs=1e-3),
            "anchoredPathLength": pytest.approx(2.0, abs=1e-3),
        }
    ]


def test_run_ball_recovery_experiment_reports_anchor_diagnostics_in_profile_summaries(monkeypatch):
    def fake_recover_ball_rows(*args, **kwargs):
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 40.0, "Y": 50.0, "Conf": 0.31},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 44.0, "Y": 52.0, "Conf": 0.30},
            {"Frame_ID": 10, "Entity_Type": "ball", "X": 50.0, "Y": 55.0, "Conf": 0.29},
        ]

    player_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "X": 39.0, "Y": 51.0, "Conf": 0.9},
        {"Frame_ID": 5, "Entity_Type": "player", "X": 45.0, "Y": 51.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "player", "X": 51.0, "Y": 54.0, "Conf": 0.9},
    ]

    class FakeCapture:
        def __init__(self, _path):
            self.first_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            self.reads = 0

        def read(self):
            if self.reads > 0:
                return False, None
            self.reads += 1
            return True, self.first_frame

        def release(self):
            return None

    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", FakeCapture)

    results = run_ball_recovery_experiment(
        "demo.mp4",
        model=object(),
        H=object(),
        pitch_points=[],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        player_rows=player_rows,
        profiles=[
            {"name": "baseline", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": False},
        ],
    )

    assert len(results) == 1
    candidate_summary = results[0]["candidateSummary"]
    selected_summary = results[0]["selectedSummary"]
    for summary in (candidate_summary, selected_summary):
        assert summary["supportedFrameCount"] == 3
        assert summary["anchoredFrameCount"] == 3
        assert summary["bridgeFrameCount"] == 0
        assert summary["unsupportedEdgeFrameShare"] == 0.0
        assert summary["anchoredPathLength"] == pytest.approx(11.18, abs=1e-2)
        assert summary["segmentDiagnostics"] == [
            {
                "startFrame": 0,
                "endFrame": 10,
                "frameCount": 3,
                "supportedFrameCount": 3,
                "anchoredFrameCount": 3,
                "bridgeFrameCount": 0,
                "unsupportedEdgeFrameShare": 0.0,
                "anchoredPathLength": pytest.approx(11.18, abs=1e-2),
            }
        ]


def test_select_best_ball_recovery_profile_prefers_anchor_weighted_profile_over_frame_count_heavy_profile():
    results = [
        {
            "name": "frame_heavy_but_floaty",
            "selectedScore": 240.0,
            "viable": True,
            "selectedSummary": {
                "frames": 6,
                "supportedFrameCount": 1,
                "anchoredFrameCount": 2,
                "bridgeFrameCount": 0,
                "unsupportedEdgeFrameShare": 0.5,
                "anchoredPathLength": 9.0,
            },
        },
        {
            "name": "anchor_strong",
            "selectedScore": 120.0,
            "viable": True,
            "selectedSummary": {
                "frames": 3,
                "supportedFrameCount": 3,
                "anchoredFrameCount": 3,
                "bridgeFrameCount": 1,
                "unsupportedEdgeFrameShare": 0.0,
                "anchoredPathLength": 18.0,
            },
        },
    ]

    selected = select_best_ball_recovery_profile(results)

    assert selected is not None
    assert selected["name"] == "anchor_strong"


def test_select_best_ball_recovery_profile_returns_none_when_no_viable_profile_exists():
    results = [
        {"name": "baseline_player_window", "selectedScore": 120.0, "viable": False},
        {"name": "edge_margin_40_upper_075", "selectedScore": 155.0, "viable": False},
    ]

    assert select_best_ball_recovery_profile(results) is None


def test_process_video_does_not_merge_recovery_rows_when_no_viable_profile_exists(monkeypatch):
    class FakeBoxes(list):
        pass

    class FakeBox:
        def __init__(self):
            self.cls = [0]
            self.conf = [0.8]
            self.id = [7]
            self.xyxy = [np.array([100.0, 200.0, 160.0, 320.0], dtype=np.float32)]

    class FakeResult:
        def __init__(self):
            self.boxes = FakeBoxes([FakeBox()])
            self.orig_img = np.zeros((720, 1280, 3), dtype=np.uint8)

    class FakeModel:
        def __init__(self, _path):
            pass

        def track(self, **kwargs):
            return iter([FakeResult()] * 10)

    class FakeCapture:
        def __init__(self, _path):
            self.frames = [np.zeros((720, 1280, 3), dtype=np.uint8)] * 10
            self.index = 0

        def isOpened(self):
            return True

        def read(self):
            if self.index >= len(self.frames):
                return False, None
            frame = self.frames[self.index]
            self.index += 1
            return True, frame

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FPS:
                return 25.0
            return 0.0

        def set(self, *_args):
            return True

        def release(self):
            return None

    monkeypatch.setattr(run_guerilla, "YOLO", FakeModel)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(run_guerilla, "resolve_homography", lambda *_args, **_kwargs: (np.eye(3), []))
    monkeypatch.setattr(
        run_guerilla,
        "run_ball_recovery_experiment",
        lambda *args, **kwargs: [
            {
                "name": "edge_margin_40_upper_078",
                "candidateSummary": {
                    "candidateRows": 12,
                    "uniqueFrames": 12,
                    "edgeCandidateShare": 0.9,
                    "nearPlayerWindowShare": 0.0,
                    "segmentCount": 2,
                    "longestSegmentFrames": 6,
                },
                "selectedSummary": {"frames": 0, "edgeFrameShare": 1.0, "pathLength": 0.0},
                "selectedScore": 12.0,
                "viable": False,
                "selectedRows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 99.0, "Y": 99.0, "Conf": 0.2}
                ],
            }
        ],
    )

    result = process_video(
        "demo.mp4",
        return_rows=True,
        auto_homography=False,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
    )

    assert {row["Entity_Type"] for row in result["rows"]} == {"player"}
    assert result["recoveryDebug"]["recoveryAttempted"] is True
    assert result["recoveryDebug"]["recoveryApplied"] is False
    assert result["recoveryDebug"]["recoveryDecision"] == "no_viable_profile"


def test_collect_primary_player_windows_tracks_person_boxes_from_sampled_frames(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeBox:
        def __init__(self, cls, xyxy):
            self.cls = [cls]
            self.xyxy = [xyxy]

    class FakeResult:
        def __init__(self, boxes):
            self.boxes = boxes

    class FakeModel:
        def __init__(self):
            self.predict_calls = []

        def predict(self, *_args, **kwargs):
            self.predict_calls.append(kwargs)
            return [
                FakeResult([
                    FakeBox(0, [100.0, 200.0, 160.0, 320.0]),
                    FakeBox(32, [120.0, 240.0, 135.0, 255.0]),
                ])
            ] if len(self.predict_calls) == 1 else [
                FakeResult([
                    FakeBox(0, [80.0, 240.0, 180.0, 300.0]),
                ])
            ]

    class FakeCapture:
        def __init__(self, _path):
            self.frames = [frame.copy(), frame.copy()]
            self.index = 0

        def isOpened(self):
            return True

        def read(self):
            if self.index >= len(self.frames):
                return False, None
            current = self.frames[self.index]
            self.index += 1
            return True, current

        def release(self):
            return None

    model = FakeModel()
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", FakeCapture)

    windows = collect_primary_player_windows(
        "demo.mp4",
        model=model,
        frame_interval=1,
        imgsz=1280,
        conf=0.12,
        tracker="botsort.yaml",
    )
    assert windows == {
        0: [100.0, 200.0, 160.0, 320.0],
        1: [80.0, 240.0, 180.0, 300.0],
    }
    assert all(call["classes"] == [0] for call in model.predict_calls)


def test_collect_primary_player_windows_skips_ball_only_profiles_without_predicting():
    class FakeModel:
        def predict(self, *_args, **_kwargs):
            raise AssertionError("ball-only profile should not run primary player window prediction")

    windows = collect_primary_player_windows(
        "demo.mp4",
        model=FakeModel(),
        frame_interval=1,
        imgsz=1280,
        conf=0.12,
        tracker="botsort.yaml",
        detector_profile="ball_probe_only_v1",
    )

    assert windows == {}


def test_merge_missing_ball_rows_only_fills_frames_without_primary_ball():
    primary_rows = [
        {"Frame_ID": 0, "Entity_Type": "player", "Track_ID": 7, "X": 20.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 40.0, "Y": 50.0, "Conf": 0.5},
        {"Frame_ID": 5, "Entity_Type": "player", "Track_ID": 7, "X": 24.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "player", "Track_ID": 7, "X": 30.0, "Y": 50.0, "Conf": 0.9},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 47.0, "Conf": 0.55},
    ]
    recovered_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 42.0, "Y": 50.0, "Conf": 0.3},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 46.0, "Y": 49.0, "Conf": 0.31},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 54.0, "Y": 47.0, "Conf": 0.32},
    ]

    merged_rows = merge_missing_ball_rows(primary_rows, recovered_rows)

    merged_ball_rows = [row for row in merged_rows if row["Entity_Type"] == "ball"]
    assert [row["Frame_ID"] for row in merged_ball_rows] == [0, 5, 10]
    frame_zero = next(row for row in merged_ball_rows if row["Frame_ID"] == 0)
    frame_five = next(row for row in merged_ball_rows if row["Frame_ID"] == 5)
    frame_ten = next(row for row in merged_ball_rows if row["Frame_ID"] == 10)
    assert frame_zero["Conf"] == 0.5
    assert frame_five["Conf"] == 0.31
    assert frame_ten["Conf"] == 0.55


def test_ball_rows_need_supplemental_recovery_when_primary_ball_has_sampled_gaps():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 40.0, "Y": 50.0, "Conf": 0.41},
        {"Frame_ID": 4, "Entity_Type": "ball", "Track_ID": -1, "X": 47.0, "Y": 49.0, "Conf": 0.44},
        {"Frame_ID": 8, "Entity_Type": "ball", "Track_ID": -1, "X": 55.0, "Y": 46.0, "Conf": 0.46},
    ]

    assert ball_rows_need_supplemental_recovery(rows, frame_interval=2) is True
    assert ball_rows_need_supplemental_recovery(rows, frame_interval=4) is False


def test_recover_ball_rows_prefers_explicit_crop_windows_over_player_window_crops(monkeypatch):
    frame = np.zeros((200, 200, 3), dtype=np.uint8)

    class FakeBox:
        def __init__(self, coords):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self):
            self.boxes = [FakeBox([0.0, 0.0, 10.0, 10.0])]

    class FakeModel:
        def predict(self, frame_image, **_kwargs):
            if frame_image.shape[:2] == (40, 40):
                return [FakeResult()]
            return [FakeResult()]

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())

    rows = run_guerilla.recover_ball_rows(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=1,
        player_windows={0: [100.0, 100.0, 180.0, 180.0]},
        crop_windows_by_frame={0: (20, 30, 60, 70)},
    )

    assert rows[0]["Source_X1"] == 20.0
    assert rows[0]["Source_Y1"] == 30.0


def test_run_ball_recovery_experiment_reports_anchor_corridor_diagnostics(monkeypatch):
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    seen_crop_windows = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == run_guerilla.cv2.CAP_PROP_FRAME_COUNT:
                return 20.0
            return 25.0

        def read(self):
            if self._reads > 0:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def release(self):
            return True

    class FakeBox:
        def __init__(self):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([0.4], dtype=np.float32)
            self.xyxy = np.array([[0.0, 0.0, 10.0, 10.0]], dtype=np.float32)

    class FakeResult:
        def __init__(self):
            self.boxes = [FakeBox()]

    def fake_recover_ball_rows(*_args, **kwargs):
        seen_crop_windows.append(kwargs.get("crop_windows_by_frame"))
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "X": 10.0, "Y": 20.0, "Conf": 0.30},
            {"Frame_ID": 5, "Entity_Type": "ball", "X": 14.0, "Y": 24.0, "Conf": 0.31},
        ]

    class FakeModel:
        def predict(self, *_args, **_kwargs):
            return [FakeResult()]

    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)

    results = run_guerilla.run_ball_recovery_experiment(
        "demo.mp4",
        model=FakeModel(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25.0,
        frame_interval=5,
        imgsz=1280,
        conf=0.12,
        observed_source_anchors={0: (10.0, 20.0), 5: (14.0, 24.0)},
        player_windows={0: [0.0, 0.0, 40.0, 40.0], 5: [4.0, 4.0, 44.0, 44.0]},
        profiles=[
            {
                "name": "anchor_corridor_width_cap_075",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "cropMode": "anchor_corridor",
                "maxCropWidthRatio": 0.75,
                "corridorHalfWidthPx": 12,
                "corridorPaddingPx": 8,
            }
        ],
    )

    summary = results[0]["candidateSummary"]
    assert seen_crop_windows[0] is not None
    assert sorted(seen_crop_windows[0]) == [0, 5, 10, 15]
    assert summary["corridorCandidateFrames"] == 4
    assert summary["corridorFramesWithTwoAnchors"] == 0
    assert summary["corridorFramesWithSingleAnchor"] == 4
    assert summary["corridorMeanWidth"] > 0.0


def test_update_player_window_accumulates_bounds():
    window = update_player_window(None, 100.0, 200.0, 160.0, 320.0)
    window = update_player_window(window, 80.0, 240.0, 180.0, 300.0)

    assert window == [80.0, 200.0, 180.0, 320.0]


def test_ball_recovery_crop_window_expands_and_clamps():
    crop = ball_recovery_crop_window((1080, 4096, 3), [1000.0, 250.0, 1400.0, 500.0])

    assert crop is not None
    left, top, right, bottom = crop
    assert left >= 0
    assert top >= 0
    assert right <= 4096
    assert bottom <= 1080


def test_ball_recovery_crop_window_can_cap_width_ratio():
    crop = ball_recovery_crop_window(
        (1080, 1920, 3),
        [400.0, 200.0, 600.0, 500.0],
        max_crop_width_ratio=0.5,
    )

    assert crop is not None
    left, _, right, _ = crop
    assert (right - left) <= 960


def test_summarize_ball_recovery_crop_windows_reports_mean_coverage():
    summary = summarize_ball_recovery_crop_windows(
        frame_shape=(1080, 1920, 3),
        player_windows={
            0: [400.0, 200.0, 600.0, 500.0],
            5: [500.0, 250.0, 700.0, 550.0],
        },
    )

    assert summary["framesWithWindows"] == 2
    assert 0 < summary["meanCropWidth"] <= 1920
    assert 0 < summary["meanCropHeight"] <= 1080
    assert 0 < summary["meanFrameCoverageShare"] <= 1


def test_ball_candidate_rows_for_frame_can_reject_crop_edge_boxes():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [
        FakeBox([5.0, 40.0, 25.0, 60.0]),
        FakeBox([80.0, 80.0, 100.0, 100.0]),
    ]

    rows = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [400, 0], [400, 400], [0, 400]],
        x_offset=100.0,
        y_offset=100.0,
        crop_window=(100, 100, 300, 300),
        crop_edge_margin=20,
    )

    assert len(rows) == 1
    assert rows[0]["Source_X1"] == 180.0


def test_ball_candidate_rows_for_frame_can_reject_boxes_too_low_in_crop():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [
        FakeBox([80.0, 150.0, 100.0, 190.0]),
        FakeBox([80.0, 80.0, 100.0, 100.0]),
    ]

    rows = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [400, 0], [400, 400], [0, 400]],
        x_offset=100.0,
        y_offset=100.0,
        crop_window=(100, 100, 300, 300),
        max_crop_center_y_ratio=0.7,
    )

    assert len(rows) == 1
    assert rows[0]["Source_Y1"] == 180.0


def test_ball_candidate_rows_for_frame_keeps_rescue_fallback_only_when_normal_pitch_candidate_exists():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [
        FakeBox([40.0, 40.0, 60.0, 60.0], conf=0.9),
        FakeBox([95.0, 40.0, 115.0, 60.0], conf=0.8),
    ]

    rows, diagnostics = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        rescue_mode="primary_boundary",
        return_diagnostics=True,
    )

    assert len(rows) == 1
    assert "PrimaryPitchPolygonRescued" not in rows[0]
    assert "PitchPolygonRescueMode" not in rows[0]
    assert diagnostics["primaryPitchPolygonRescueEligibleCount"] == 1
    assert diagnostics["primaryPitchPolygonRescueEligibleFrames"] == 1
    assert diagnostics["primaryPitchPolygonRescuedCount"] == 0
    assert diagnostics["primaryPitchPolygonRescuedFrames"] == 0


def test_ball_candidate_rows_for_frame_rescues_primary_boundary_boxes_within_margin_and_stamps_mode():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [FakeBox([100.0, 40.0, 104.0, 60.0], conf=0.82)]

    rows, diagnostics = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        rescue_mode="primary_boundary",
        return_diagnostics=True,
    )

    assert len(rows) == 1
    assert rows[0]["PitchPolygonRescueMode"] == "primary_boundary"
    assert rows[0]["PrimaryPitchPolygonRescued"] is True
    assert rows[0]["Source_X1"] == 100.0
    assert diagnostics["primaryPitchPolygonRescueEligibleCount"] == 1
    assert diagnostics["primaryPitchPolygonRescueEligibleFrames"] == 1
    assert diagnostics["primaryPitchPolygonRescuedCount"] == 1
    assert diagnostics["primaryPitchPolygonRescuedFrames"] == 1


def test_ball_candidate_rows_for_frame_drops_primary_boundary_boxes_outside_margin():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [FakeBox([120.0, 40.0, 140.0, 60.0], conf=0.82)]

    rows, diagnostics = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        rescue_mode="primary_boundary",
        return_diagnostics=True,
    )

    assert rows == []
    assert diagnostics["primaryPitchPolygonRescueEligibleCount"] == 0
    assert diagnostics["primaryPitchPolygonRescueEligibleFrames"] == 0
    assert diagnostics["primaryPitchPolygonRescuedCount"] == 0
    assert diagnostics["primaryPitchPolygonRescuedFrames"] == 0


def test_ball_candidate_rows_for_frame_rescues_only_one_primary_boundary_box_with_deterministic_ranking():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [
        FakeBox([100.0, 40.0, 102.0, 60.0], conf=0.75),
        FakeBox([100.0, 40.0, 102.0, 60.0], conf=0.95),
        FakeBox([103.0, 40.0, 105.0, 60.0], conf=0.95),
        FakeBox([100.0, 40.0, 102.0, 60.0], conf=0.95),
    ]

    rows, diagnostics = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        rescue_mode="primary_boundary",
        return_diagnostics=True,
    )

    assert len(rows) == 1
    assert rows[0]["Conf"] == pytest.approx(0.95, abs=1e-6)
    assert rows[0]["Source_X1"] == 100.0
    assert rows[0]["PitchPolygonRescueMode"] == "primary_boundary"
    assert rows[0]["PrimaryPitchPolygonRescued"] is True
    assert diagnostics["primaryPitchPolygonRescueEligibleCount"] == 4
    assert diagnostics["primaryPitchPolygonRescuedCount"] == 1


def test_ball_candidate_rows_for_frame_keeps_direct_seed_rescue_mode_and_stamp():
    class FakeBox:
        def __init__(self, coords, conf=0.3):
            self.cls = np.array([32], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    boxes = [FakeBox([100.0, 40.0, 104.0, 60.0], conf=0.82)]

    rows = run_guerilla._ball_candidate_rows_for_frame(
        frame_id=0,
        timestamp=0.0,
        boxes=boxes,
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        rescue_mode="direct_seed",
    )

    assert len(rows) == 1
    assert rows[0]["PitchPolygonRescueMode"] == "direct_seed"
    assert "PrimaryPitchPolygonRescued" not in rows[0]


def test_process_video_uses_tuned_tracking_defaults_and_persists_source_boxes(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def __init__(self):
            self.track_calls = []
            self.predict_calls = []

        def track(self, **kwargs):
            self.track_calls.append(kwargs)
            return iter(
                [
                    FakeResult(
                        [
                            FakeBox(0, 0.93, 7, [10, 20, 30, 60]),
                            FakeBox(32, 0.41, None, [40, 20, 50, 60]),
                        ]
                    )
                ]
            )

        def predict(self, *args, **kwargs):
            self.predict_calls.append((args, kwargs))
            return [FakeResult([])]

    fake_model = FakeModel()

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: fake_model)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    assert fake_model.track_calls[0]["imgsz"] == run_guerilla.TRACKING_IMGSZ
    assert fake_model.track_calls[0]["conf"] == run_guerilla.TRACKING_CONF
    assert fake_model.track_calls[0]["classes"] == run_guerilla.TRACKING_CLASSES
    expected_recovery_passes = len(
        {
            run_guerilla._profile_recovery_cache_key(profile)
            for profile in run_guerilla.build_ball_recovery_quality_matrix_profiles()
        }
    )
    assert len(fake_model.predict_calls) >= (expected_recovery_passes + 2)
    assert any(call[1]["imgsz"] == 960 for call in fake_model.predict_calls)

    rows = result["rows"]
    assert len(rows) == 2
    player_row = next(row for row in rows if row["Entity_Type"] == "player")
    ball_row = next(row for row in rows if row["Entity_Type"] == "ball")
    trace = result["ballPipelineTrace"]
    assert player_row["Source_X1"] == 10.0
    assert player_row["Source_Y2"] == 60.0
    assert ball_row["Y"] == 40.0
    assert trace["traceVersion"] == run_guerilla.BALL_PIPELINE_TRACE_VERSION
    assert trace["detectorModelPath"] == "yolov10n.pt"
    assert trace["detectorModelName"] == "yolov10n.pt"
    assert trace["directSeedRetryPolicy"] == "bounded_multiscale_fallback"
    assert trace["directSeedRetryScales"] == [1600, 960, 1920]
    assert [stage["stage"] for stage in trace["stages"]] == [
        "processVideoPrimary",
        "processVideoRecovery",
        "processVideoReturnedRows",
    ]
    assert trace["stages"][0]["ballRowCount"] == 1
    assert trace["stages"][2]["ballFrameCount"] == 1


def test_process_video_keeps_recovered_frames_when_probe_observations_are_later_suppressed(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads >= 3:
                return False, None
            self._reads += 1
            return True, frame.copy()

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter(
                [
                    FakeResult([FakeBox(0, 0.93, 7, [90, 90, 98, 110])]),
                    FakeResult([FakeBox(0, 0.92, 7, [91, 90, 99, 110])]),
                    FakeResult([FakeBox(0, 0.91, 7, [92, 90, 100, 110])]),
                ]
            )

        def predict(self, *_args, **_kwargs):
            return [FakeResult([])]

    def fake_recover_ball_rows(*_args, **_kwargs):
        return [
            {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 96.8, "Y": 95.3, "Conf": 0.31},
            {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 96.8, "Y": 95.3, "Conf": 0.30},
            {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 96.8, "Y": 95.3, "Conf": 0.29},
        ]

    def fake_run_ball_recovery_experiment(*_args, **_kwargs):
        selected_rows = fake_recover_ball_rows()
        return [
            {
                "name": "edge_margin_40_upper_078",
                "candidateSummary": {
                    "candidateRows": len(selected_rows),
                    "uniqueFrames": len({int(row["Frame_ID"]) for row in selected_rows}),
                    "edgeCandidateShare": 1.0,
                    "nearPlayerWindowShare": 1.0,
                    "segmentCount": 1,
                    "longestSegmentFrames": 3,
                },
                "selectedSummary": {
                    "frames": len(selected_rows),
                    "edgeFrameShare": 1.0,
                    "pathLength": 0.0,
                    "supportedFrameCount": 3,
                    "anchoredFrameCount": 3,
                    "bridgeFrameCount": 0,
                    "unsupportedEdgeFrameShare": 0.0,
                    "anchoredPathLength": 0.0,
                },
                "selectedScore": 12.0,
                "viable": True,
                "selectedRows": selected_rows,
            }
        ]

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda *_args, **_kwargs: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", fake_run_ball_recovery_experiment)

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    ball_rows = [row for row in result["rows"] if row["Entity_Type"] == "ball"]

    assert [row["Frame_ID"] for row in ball_rows] == [0, 5, 10]
    assert len(ball_rows) == 3


def test_process_video_returns_ball_truth_layers_and_preserves_unknown_gaps(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter(
                [
                    FakeResult(
                        [
                            FakeBox(0, 0.93, 7, [10, 20, 30, 60]),
                            FakeBox(32, 0.41, None, [40, 20, 50, 60]),
                        ]
                    )
                ]
            )

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: False)
    monkeypatch.setattr(
        run_guerilla,
        "ball_rows_need_supplemental_recovery",
        lambda _rows, frame_interval: frame_interval == 5,
    )
    monkeypatch.setattr(
        run_guerilla,
        "select_meaningful_recovered_ball_rows",
        lambda rows, player_windows=None: rows,
    )
    recovered_rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 41.0, "Y": 50.0, "Conf": 0.2},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 46.0, "Y": 49.0, "Conf": 0.31},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 53.0, "Y": 47.0, "Conf": 0.28},
        {"Frame_ID": 20, "Entity_Type": "ball", "Track_ID": -1, "X": 60.0, "Y": 46.0, "Conf": 0.27},
        {"Frame_ID": 25, "Entity_Type": "ball", "Track_ID": -1, "X": 65.0, "Y": 45.0, "Conf": 0.29},
        {"Frame_ID": 30, "Entity_Type": "ball", "Track_ID": -1, "X": 70.0, "Y": 44.0, "Conf": 0.30},
    ]
    recovery_results = [
        {
            "name": "baseline_player_window",
            "candidateSummary": {
                "candidateRows": len(recovered_rows),
                "uniqueFrames": 6,
                "edgeCandidateShare": 0.0,
                "nearPlayerWindowShare": 0.0,
                "segmentCount": 2,
                "longestSegmentFrames": 3,
                "supportedFrameCount": 6,
                "anchoredFrameCount": 6,
                "bridgeFrameCount": 0,
                "unsupportedEdgeFrameShare": 0.0,
                "anchoredPathLength": 30.0,
                "segmentDiagnostics": [
                    {
                        "startFrame": 0,
                        "endFrame": 10,
                        "frameCount": 3,
                        "supportedFrameCount": 3,
                        "anchoredFrameCount": 3,
                        "bridgeFrameCount": 0,
                        "unsupportedEdgeFrameShare": 0.0,
                        "anchoredPathLength": 10.0,
                    },
                    {
                        "startFrame": 20,
                        "endFrame": 30,
                        "frameCount": 3,
                        "supportedFrameCount": 3,
                        "anchoredFrameCount": 3,
                        "bridgeFrameCount": 0,
                        "unsupportedEdgeFrameShare": 0.0,
                        "anchoredPathLength": 10.0,
                    },
                ],
            },
            "selectedSummary": {
                "frames": 6,
                "pathLength": 30.0,
                "edgeFrameShare": 0.0,
                "supportedFrameCount": 6,
                "anchoredFrameCount": 6,
                "bridgeFrameCount": 0,
                "unsupportedEdgeFrameShare": 0.0,
                "anchoredPathLength": 30.0,
                "segmentDiagnostics": [
                    {
                        "startFrame": 0,
                        "endFrame": 10,
                        "frameCount": 3,
                        "supportedFrameCount": 3,
                        "anchoredFrameCount": 3,
                        "bridgeFrameCount": 0,
                        "unsupportedEdgeFrameShare": 0.0,
                        "anchoredPathLength": 10.0,
                    },
                    {
                        "startFrame": 20,
                        "endFrame": 30,
                        "frameCount": 3,
                        "supportedFrameCount": 3,
                        "anchoredFrameCount": 3,
                        "bridgeFrameCount": 0,
                        "unsupportedEdgeFrameShare": 0.0,
                        "anchoredPathLength": 10.0,
                    },
                ],
            },
            "selectedScore": 60.0,
            "viable": True,
            "selectedRows": recovered_rows,
        }
    ]
    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", lambda *args, **kwargs: recovery_results)

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    ball_rows = [row for row in result["rows"] if row["Entity_Type"] == "ball"]
    assert [row["Frame_ID"] for row in ball_rows] == [0, 5, 10, 20, 25, 30]
    frame_zero = next(row for row in ball_rows if row["Frame_ID"] == 0)
    frame_five = next(row for row in ball_rows if row["Frame_ID"] == 5)
    frame_ten = next(row for row in ball_rows if row["Frame_ID"] == 10)
    assert frame_zero["Conf"] == pytest.approx(0.41, abs=1e-6)
    assert frame_five["Conf"] == pytest.approx(0.31, abs=1e-6)
    assert frame_ten["Conf"] == pytest.approx(0.28, abs=1e-6)
    assert result["recoveryDebug"]["recoveryProfileName"] == "baseline_player_window"
    assert result["recoveryDebug"]["recoveredSupportedFrames"] == 6
    assert result["recoveryDebug"]["recoveredAnchoredFrames"] == 6
    assert result["recoveryDebug"]["recoveredBridgeFrames"] == 0
    assert result["recoveryDebug"]["recoveredUnsupportedEdgeFrameShare"] == 0.0
    assert result["recoveryDebug"]["recoveredAnchoredPathLength"] == 30.0
    assert result["matchStateEvidence"]["frames"][0]["frameId"] == 0
    assert result["matchStateEvidence"]["frames"][0]["acceptedSource"] == "observed"
    assert result["matchStateEvidence"]["frames"][0]["hasAcceptedBall"] is True
    assert result["matchStateEvidence"]["frames"][1]["frameId"] == 5
    assert result["matchStateEvidence"]["frames"][1]["acceptedSource"] == "inferred"
    assert result["matchStateEvidence"]["frames"][1]["hasAcceptedBall"] is True
    truth_layers = result["ballTruthLayers"]
    assert truth_layers["observedBall"]["summary"]["frameCount"] == 1
    assert [row["Frame_ID"] for row in truth_layers["inferredBall"]["rows"]] == [5, 10, 20, 25, 30]
    assert truth_layers["inferredBall"]["summary"]["frameCount"] == 5
    assert truth_layers["acceptedBall"]["summary"]["frameCount"] == 6
    assert truth_layers["acceptedSourceBreakdown"] == {"observed": 1, "inferred": 5}
    assert truth_layers["acceptedSegments"] == [
        {"startFrame": 0, "endFrame": 10, "frameCount": 3, "source": "mixed"},
        {"startFrame": 20, "endFrame": 30, "frameCount": 3, "source": "inferred"},
    ]
    assert truth_layers["unknownGaps"] == [
        {"startFrame": 15, "endFrame": 15, "frameCount": 1},
    ]


def test_process_video_prefers_supported_tracking_ball_candidate_before_higher_confidence_same_frame(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter(
                [
                    FakeResult(
                        [
                            FakeBox(0, 0.93, 7, [10, 20, 30, 60]),
                            FakeBox(32, 0.40, None, [18, 54, 22, 58]),
                            FakeBox(32, 0.95, None, [0, 0, 2, 2]),
                        ]
                    )
                ]
            )

        def predict(self, *_args, **_kwargs):
            return [FakeResult([])]

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: False)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        run_guerilla,
        "recover_ball_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("track-only wrapped model must skip the probe-observed predict pass")
        ),
    )
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", lambda *_args, **_kwargs: [])

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    ball_rows = [row for row in result["rows"] if row["Entity_Type"] == "ball"]

    assert len(ball_rows) == 1
    assert ball_rows[0]["Conf"] == pytest.approx(0.40, abs=1e-6)
    assert ball_rows[0]["X"] == pytest.approx(20.0, abs=1e-6)
    assert ball_rows[0]["Y"] == pytest.approx(56.0, abs=1e-6)
    assert result["ballTruthLayers"]["supportDiagnostics"]["supportedObservedBallFrames"] == 1
    assert result["ballTruthLayers"]["supportDiagnostics"]["supportedAcceptedBallFrames"] == 1


def test_process_video_emits_heartbeat_updates_for_worker_stages(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    heartbeats = []

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 5.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter(
                [
                    FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60]), FakeBox(32, 0.40, None, [40, 20, 50, 60])]),
                    *(
                        FakeResult([FakeBox(0, 0.90, 7, [10, 20, 30, 60])])
                        for _ in range(250)
                    ),
                ]
            )

        def predict(self, *_args, **_kwargs):
            return [FakeResult([FakeBox(32, 0.40, None, [40, 20, 50, 60])])]

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: False)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", lambda *_args, **_kwargs: [])

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
        progress_callback=heartbeats.append,
        match_id="match-123",
        job_id="job-123",
    )

    stage_pairs = [(payload["workerStage"], payload["stageStatus"]) for payload in heartbeats]
    assert stage_pairs[:4] == [
        ("modelLoad", "started"),
        ("modelLoad", "completed"),
        ("videoOpenAndHomography", "started"),
        ("videoOpenAndHomography", "completed"),
    ]
    assert ("probeObservedPass", "started") in stage_pairs
    assert ("recoverySelection", "started") in stage_pairs
    assert ("truthLayerFinalize", "completed") in stage_pairs
    assert stage_pairs[-2:] == [
        ("resultSerialize", "started"),
        ("resultSerialize", "completed"),
    ]
    assert any(
        payload["matchId"] == "match-123"
        and payload["jobId"] == "job-123"
        and payload["workerStage"] == "trackingPass"
        and payload["stageStatus"] == "completed"
        and payload.get("trackingFramesSeen") == 1
        for payload in heartbeats
    )
    assert any(
        payload["workerStage"] == "resultSerialize"
        and payload["stageStatus"] == "completed"
        and payload["workerReturnedResult"] is True
        for payload in heartbeats
    )
    assert result["ballTruthLayers"]["acceptedBall"]["summary"]["frameCount"] >= 1


def test_process_video_skips_probe_pass_for_track_only_model_with_output_parquet(monkeypatch, tmp_path):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, *_args, **_kwargs):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter(
                [
                    FakeResult(
                        [
                            FakeBox(0, 0.93, 7, [10, 20, 30, 60]),
                            FakeBox(32, 0.41, None, [40, 20, 50, 60]),
                        ]
                    )
                ]
            )

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: False)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla.pd.DataFrame, "to_parquet", lambda self, *args, **kwargs: None)

    result = process_video(
        "/fake/video.mp4",
        output_parquet=tmp_path / "rows.parquet",
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=False,
        auto_homography=False,
    )

    assert isinstance(result, dict)
    assert "ballTruthLayers" in result
    assert result["ballTruthLayers"]["acceptedBall"]["summary"]["frameCount"] == 1


def test_process_video_forwards_recovery_profile_heartbeats(monkeypatch):
    heartbeats = []
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, *_args, **_kwargs):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60])])])

    def fake_run_ball_recovery_experiment(*_args, **kwargs):
        progress_callback = kwargs["progress_callback"]
        progress_callback(
            {
                "stageStatus": "profile_started",
                "recoveryProfileName": "proposal_windows_075",
                "recoveryProfileIndex": 1,
                "recoveryProfileCount": 2,
                "proposalDirectSeedScale1600AttemptFrames": 12,
            }
        )
        progress_callback(
            {
                "stageStatus": "profile_in_progress",
                "recoveryProfileName": "proposal_windows_075",
                "recoveryProfileIndex": 1,
                "recoveryProfileCount": 2,
                "proposalDirectSeedScale1920AttemptFrames": 2,
            }
        )
        return []

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", fake_run_ball_recovery_experiment)
    monkeypatch.setattr(run_guerilla, "select_best_ball_recovery_profile", lambda _results: None)
    monkeypatch.setattr(run_guerilla, "_build_recovery_profile_matrix", lambda *_args, **_kwargs: [])

    process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
        progress_callback=heartbeats.append,
        match_id="match-123",
        job_id="job-123",
    )

    assert any(
        payload["workerStage"] == "recoverySelection"
        and payload["stageStatus"] == "profile_started"
        and payload["recoveryProfileName"] == "proposal_windows_075"
        and payload["proposalDirectSeedScale1600AttemptFrames"] == 12
        for payload in heartbeats
    )
    assert any(
        payload["workerStage"] == "recoverySelection"
        and payload["stageStatus"] == "profile_in_progress"
        and payload["proposalDirectSeedScale1920AttemptFrames"] == 2
        for payload in heartbeats
    )


def test_process_video_rejects_non_viable_recovered_ball_rows(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakeModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60])])])

    monkeypatch.setattr(run_guerilla, "YOLO", lambda _model_path: FakeModel())
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    run_ball_recovery_experiment_calls = []

    def fake_run_ball_recovery_experiment(*args, **kwargs):
        run_ball_recovery_experiment_calls.append((args, kwargs))
        return [
            {
                "name": "edge_dominated_profile",
                "candidateSummary": {
                    "candidateRows": 3,
                    "uniqueFrames": 3,
                    "edgeCandidateShare": 1.0,
                    "nearPlayerWindowShare": 0.0,
                    "segmentCount": 1,
                    "longestSegmentFrames": 3,
                },
                "selectedSummary": {
                    "frames": 3,
                    "pathLength": 0.0,
                    "edgeFrameShare": 1.0,
                },
                "selectedScore": 0.0,
                "viable": False,
                "selectedRows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 12.0, "Y": 96.6, "Conf": 0.2},
                    {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 18.0, "Y": 96.8, "Conf": 0.31},
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 24.0, "Y": 97.0, "Conf": 0.28},
                ],
            }
        ]

    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", fake_run_ball_recovery_experiment)

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    assert len(run_ball_recovery_experiment_calls) == 1
    ball_rows = [row for row in result["rows"] if row["Entity_Type"] == "ball"]
    assert ball_rows == []
    assert result["recoveryDebug"]["recoveryDecision"] == "no_viable_profile"
    assert result["recoveryDebug"]["recoveryApplied"] is False
    assert result["ballTruthLayers"]["acceptedSourceBreakdown"]["inferred"] == 0


def test_process_video_uses_auxiliary_ball_model_for_probe_and_recovery_passes(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakePrimaryModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60])])])

    class FakeAuxiliaryModel:
        def predict(self, *_args, **_kwargs):
            return []

    primary_model = FakePrimaryModel()
    auxiliary_model = FakeAuxiliaryModel()
    loaded_models: list[str] = []

    def fake_yolo(model_path):
        loaded_models.append(str(model_path))
        if str(model_path) == "/workspace/weights/yolov10n.pt":
            return primary_model
        if str(model_path) == "/workspace/weights/touchline-best.pt":
            return auxiliary_model
        raise AssertionError(f"unexpected model path: {model_path}")

    recover_ball_rows_calls = []

    def fake_recover_ball_rows(*_args, **kwargs):
        recover_ball_rows_calls.append(kwargs)
        return []

    run_ball_recovery_experiment_calls = []

    def fake_run_ball_recovery_experiment(*_args, **kwargs):
        run_ball_recovery_experiment_calls.append(kwargs)
        return []

    monkeypatch.setattr(run_guerilla, "YOLO", fake_yolo)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", fake_run_ball_recovery_experiment)
    monkeypatch.setattr(run_guerilla, "select_best_ball_recovery_profile", lambda _results: None)
    monkeypatch.setattr(run_guerilla, "_build_recovery_profile_matrix", lambda *_args, **_kwargs: [])

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        model_path="/workspace/weights/yolov10n.pt",
        primary_model_path="/workspace/weights/yolov10n.pt",
        auxiliary_ball_model_path="/workspace/weights/touchline-best.pt",
        auxiliary_ball_model_profile="ball_probe_only_v1",
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    assert loaded_models == ["/workspace/weights/yolov10n.pt", "/workspace/weights/touchline-best.pt"]
    assert recover_ball_rows_calls[0]["model"]._model is auxiliary_model
    assert recover_ball_rows_calls[0]["detector_profile"] == "ball_probe_only_v1"
    assert run_ball_recovery_experiment_calls[0]["model"]._model is auxiliary_model
    assert run_ball_recovery_experiment_calls[0]["detector_profile"] == "ball_probe_only_v1"
    assert {row["Entity_Type"] for row in result["rows"]} == {"player"}
    trace = result["ballPipelineTrace"]
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


def test_process_video_uses_low_conf_auxiliary_probe_contract_only_for_explicit_profile(monkeypatch):
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    class FakeCapture:
        def __init__(self, *_args, **_kwargs):
            self._reads = 0

        def isOpened(self):
            return True

        def get(self, _prop):
            return 25.0

        def read(self):
            if self._reads == 0:
                self._reads += 1
                return True, frame.copy()
            return False, None

        def set(self, _prop, _value):
            return True

        def release(self):
            return True

    class FakeBox:
        def __init__(self, cls, conf, track_id, coords):
            self.cls = np.array([cls], dtype=np.float32)
            self.conf = np.array([conf], dtype=np.float32)
            self.id = None if track_id is None else np.array([track_id], dtype=np.float32)
            self.xyxy = np.array([coords], dtype=np.float32)

    class FakeResult:
        def __init__(self, boxes):
            self.orig_img = frame.copy()
            self.boxes = boxes

    class FakePrimaryModel:
        def track(self, **_kwargs):
            return iter([FakeResult([FakeBox(0, 0.93, 7, [10, 20, 30, 60])])])

    class FakeAuxiliaryModel:
        def predict(self, *_args, **_kwargs):
            return []

    primary_model = FakePrimaryModel()
    auxiliary_model = FakeAuxiliaryModel()

    def fake_yolo(model_path):
        if str(model_path) == "/workspace/weights/yolov10n.pt":
            return primary_model
        if str(model_path) == "/workspace/weights/touchline-best.pt":
            return auxiliary_model
        raise AssertionError(f"unexpected model path: {model_path}")

    recover_ball_rows_calls = []

    def fake_recover_ball_rows(*_args, **kwargs):
        recover_ball_rows_calls.append(kwargs)
        return []

    run_ball_recovery_experiment_calls = []

    def fake_run_ball_recovery_experiment(*_args, **kwargs):
        run_ball_recovery_experiment_calls.append(kwargs)
        return []

    monkeypatch.setattr(run_guerilla, "YOLO", fake_yolo)
    monkeypatch.setattr(run_guerilla.cv2, "VideoCapture", lambda _video_path: FakeCapture())
    monkeypatch.setattr(
        run_guerilla,
        "resolve_homography",
        lambda *_args, **_kwargs: (
            np.eye(3),
            [[0, 0], [100, 0], [100, 100], [0, 100]],
        ),
    )
    monkeypatch.setattr(run_guerilla, "recover_ball_rows", fake_recover_ball_rows)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_recovery", lambda _rows: True)
    monkeypatch.setattr(run_guerilla, "ball_rows_need_supplemental_recovery", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(run_guerilla, "run_ball_recovery_experiment", fake_run_ball_recovery_experiment)
    monkeypatch.setattr(run_guerilla, "select_best_ball_recovery_profile", lambda _results: None)
    monkeypatch.setattr(run_guerilla, "_build_recovery_profile_matrix", lambda *_args, **_kwargs: [])

    result = process_video(
        "/fake/video.mp4",
        output_parquet=None,
        model_path="/workspace/weights/yolov10n.pt",
        primary_model_path="/workspace/weights/yolov10n.pt",
        auxiliary_ball_model_path="/workspace/weights/touchline-best.pt",
        auxiliary_ball_model_profile="ball_probe_only_v1_low_conf_001",
        homography_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        return_rows=True,
        auto_homography=False,
    )

    assert run_guerilla.detector_profile_spec("ball_probe_only_v1_low_conf_001") == {
        "name": "ball_probe_only_v1_low_conf_001",
        "playerClassIds": [],
        "ballClassIds": [0],
        "supportsPrimaryTracking": False,
        "probeRecoveryConf": 0.01,
        "probeRecoveryImgsz": 960,
    }
    assert recover_ball_rows_calls[0]["model"]._model is auxiliary_model
    assert recover_ball_rows_calls[0]["detector_profile"] == "ball_probe_only_v1_low_conf_001"
    assert recover_ball_rows_calls[0]["recovery_conf"] == 0.01
    assert recover_ball_rows_calls[0]["recovery_imgsz"] == 960
    assert run_ball_recovery_experiment_calls[0]["detector_profile"] == "ball_probe_only_v1_low_conf_001"
    assert result["ballPipelineTrace"]["probeRecoveryConf"] == 0.01
    assert result["ballPipelineTrace"]["probeRecoveryImgsz"] == 960
