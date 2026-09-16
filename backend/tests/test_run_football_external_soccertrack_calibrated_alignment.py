from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from backend.scripts import evaluate_football_analysis_pilot_soccertrack_pitch as pitch
from backend.scripts.evaluate_football_analysis_pilot_soccertrack_pitch import score_task_pitch_alignment


def test_pitch_reference_selection_uses_video_clock_not_match_clock() -> None:
    task = {"globalStartSeconds": 10.0, "globalEndSeconds": 11.0}
    rows = [
        {"matchTimeSeconds": 8.2, "videoTimelineSeconds": 10.2, "sourceFrameNumber": 1},
        {"matchTimeSeconds": 10.2, "videoTimelineSeconds": 12.2, "sourceFrameNumber": 2},
    ]

    assert [row["sourceFrameNumber"] for row in pitch.select_task_references(task, rows)] == [1]

from backend.scripts.run_football_external_soccertrack_calibrated_alignment import (
    cross_validate_direct_homography,
    evaluate_prediction_result,
    project_raw_points_to_pitch,
    score_pitch_alignment,
    summarize_calibration,
)


def test_cross_validate_direct_homography_scores_only_withheld_points() -> None:
    camera = np.array([[1000.0, 0.0, 500.0], [0.0, 1000.0, 400.0], [0.0, 0.0, 1.0]])
    distortion = np.zeros((4, 1))
    corner_pitch = np.array(
        [[0.0, 0.0], [105.0, 0.0], [105.0, 68.0], [0.0, 68.0], [52.5, 34.0], [16.5, 13.84]]
    )
    pitch_to_calibrated = np.array([[4.0, 0.2, 100.0], [0.1, 3.0, 80.0], [0.0002, 0.0001, 1.0]])
    calibrated = cv2.perspectiveTransform(corner_pitch.reshape(-1, 1, 2), pitch_to_calibrated)
    normalized = calibrated.copy()
    normalized[..., 0] = (normalized[..., 0] - camera[0, 2]) / camera[0, 0]
    normalized[..., 1] = (normalized[..., 1] - camera[1, 2]) / camera[1, 1]
    raw = cv2.fisheye.distortPoints(normalized, camera, distortion).reshape(-1, 2)

    result = cross_validate_direct_homography(
        raw,
        corner_pitch,
        camera,
        distortion,
        camera,
        tolerance_meters=0.01,
    )

    assert result["method"] == "leave_one_keypoint_out"
    assert result["fitAndScoreUseSameKeypoint"] is False
    assert result["foldCount"] == 6
    assert result["trainingKeypointsPerFold"] == 5
    assert result["withinAssignmentTolerance"] is True
    assert result["p95WithheldErrorMeters"] < 0.01
    fitted = np.asarray(result["fullFitCalibratedToPitchHomography"])
    reconstructed = cv2.perspectiveTransform(calibrated, fitted).reshape(-1, 2)
    np.testing.assert_allclose(reconstructed, corner_pitch, atol=0.01)


def test_score_task_pitch_alignment_uses_declared_evaluation_cadence() -> None:
    camera = np.array([[1000.0, 0.0, 500.0], [0.0, 1000.0, 400.0], [0.0, 0.0, 1.0]])
    distortion = np.zeros((4, 1))
    corner_pitch = np.array([[[52.5, 34.0]]], dtype=np.float64)
    pitch_to_calibrated = np.array([[2.0, 0.0, 400.0], [0.0, 2.0, 300.0], [0.0, 0.0, 1.0]])
    calibrated = cv2.perspectiveTransform(corner_pitch, pitch_to_calibrated)
    normalized = calibrated.copy()
    normalized[..., 0] = (normalized[..., 0] - camera[0, 2]) / camera[0, 0]
    normalized[..., 1] = (normalized[..., 1] - camera[1, 2]) / camera[1, 1]
    raw_x, raw_y = cv2.fisheye.distortPoints(normalized, camera, distortion).reshape(2)
    prediction_rows = [
        {
            "Entity_Type": "player",
            "Frame_ID": frame,
            "Source_X1": raw_x,
            "Source_X2": raw_x,
            "Source_Y2": raw_y,
        }
        for frame in (0, 5)
    ]
    reference_rows = [
        {
            "entities": [
                {"entityType": "player", "pitchPositionNormalized": {"x": 0.5, "y": 0.5}}
            ]
        }
        for _ in range(10)
    ]

    result = score_task_pitch_alignment(
        prediction_rows,
        reference_rows,
        camera,
        distortion,
        camera,
        np.linalg.inv(pitch_to_calibrated),
        frame_count=10,
        frame_stride=5,
        threshold_meters=5.0,
    )

    assert result["evaluatedFrameCount"] == 2
    assert result["outOfPitchReferenceCount"] == 0
    assert result["pitchAlignment"]["predictedEntityCount"] == 2
    assert result["pitchAlignment"]["referenceEntityCount"] == 2
    assert result["pitchAlignment"]["matchedEntityCount"] == 2


def test_project_raw_points_to_pitch_undistorts_before_inverse_homography() -> None:
    camera = np.array([[1000.0, 0.0, 500.0], [0.0, 1000.0, 400.0], [0.0, 0.0, 1.0]])
    distortion = np.array([[-0.12], [0.03], [0.0], [0.0]])
    pitch_to_calibrated = np.array([[2.0, 0.0, 400.0], [0.0, 2.0, 300.0], [0.0, 0.0, 1.0]])

    corner_pitch = np.array([[[52.5, 34.0]]], dtype=np.float64)
    calibrated = cv2.perspectiveTransform(corner_pitch, pitch_to_calibrated)
    normalized = calibrated.copy()
    normalized[..., 0] = (normalized[..., 0] - camera[0, 2]) / camera[0, 0]
    normalized[..., 1] = (normalized[..., 1] - camera[1, 2]) / camera[1, 1]
    raw = cv2.fisheye.distortPoints(normalized, camera, distortion)

    projected = project_raw_points_to_pitch(
        raw.reshape(-1, 2), camera, distortion, camera, pitch_to_calibrated
    )

    np.testing.assert_allclose(projected, [[0.0, 0.0]], atol=1e-4)


def test_score_pitch_alignment_discloses_unmatched_entities() -> None:
    scored = score_pitch_alignment(
        {0: np.array([[0.0, 0.0], [10.0, 0.0]])},
        {0: np.array([[1.0, 0.0], [20.0, 0.0]])},
        threshold_meters=5.0,
    )

    assert scored == {
        "thresholdMeters": 5.0,
        "predictedEntityCount": 2,
        "referenceEntityCount": 2,
        "matchedEntityCount": 1,
        "unmatchedPredictedCount": 1,
        "unmatchedReferenceCount": 1,
        "precision": 0.5,
        "recall": 0.5,
        "medianMatchedErrorMeters": 1.0,
        "p95MatchedErrorMeters": 1.0,
    }


def test_evaluate_prediction_result_scores_only_post_inference_pitch_positions(tmp_path: Path) -> None:
    camera = np.array([[1000.0, 0.0, 500.0], [0.0, 1000.0, 400.0], [0.0, 0.0, 1.0]])
    distortion = np.array([[-0.12], [0.03], [0.0], [0.0]])
    homography = np.array([[2.0, 0.0, 400.0], [0.0, 2.0, 300.0], [0.0, 0.0, 1.0]])
    corner_pitch = np.array([[[52.5, 34.0]]], dtype=np.float64)
    calibrated = cv2.perspectiveTransform(corner_pitch, homography)
    normalized = calibrated.copy()
    normalized[..., 0] = (normalized[..., 0] - camera[0, 2]) / camera[0, 0]
    normalized[..., 1] = (normalized[..., 1] - camera[1, 2]) / camera[1, 1]
    raw_x, raw_y = cv2.fisheye.distortPoints(normalized, camera, distortion).reshape(2)

    intrinsics = tmp_path / "intrinsics.npz"
    np.savez(intrinsics, K=camera, D=distortion, Knew=camera)
    homography_path = tmp_path / "homography.npy"
    np.save(homography_path, homography)
    gsr = tmp_path / "gsr.json"
    gsr.write_text(
        json.dumps(
            {
                "annotations": [
                    {
                        "image_id": "3000001",
                        "track_id": 7,
                        "supercategory": "object",
                        "attributes": {"role": "player", "jersey": "9", "team": "left"},
                        "bbox_pitch": {"x_bottom_middle": 0.0, "y_bottom_middle": 0.0},
                    }
                ]
            }
        )
    )
    prediction = tmp_path / "prediction.json"
    prediction.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "Entity_Type": "player",
                        "Frame_ID": 0,
                        "Track_ID": 1,
                        "Source_X1": raw_x,
                        "Source_X2": raw_x,
                        "Source_Y2": raw_y,
                    }
                ]
            }
        )
    )

    result = evaluate_prediction_result(
        prediction,
        gsr,
        intrinsics,
        homography_path,
        sampled_frames={0},
        threshold_meters=5.0,
    )

    assert result["imageSpaceScoringPerformed"] is False
    assert result["referenceLabelsUsedForInference"] is False
    assert result["gsHota"] is None
    assert result["gsHotaReason"] == (
        "official pitch-space GS-HOTA requires role, team, and jersey attributes that "
        "the application result does not emit"
    )
    assert result["motHotaAndIdf1"] is None
    assert result["motHotaAndIdf1Reason"] == (
        "SoccerTrack v2 GSR has no ground-truth image detections and no MOTChallenge "
        "ground-truth file is present"
    )
    assert result["pitchAlignment"]["matchedEntityCount"] == 1
    assert result["pitchAlignment"]["medianMatchedErrorMeters"] < 1e-4


def test_summarize_calibration_rejects_error_above_assignment_tolerance() -> None:
    camera = np.array([[1000.0, 0.0, 500.0], [0.0, 1000.0, 400.0], [0.0, 0.0, 1.0]])
    distortion = np.zeros((4, 1))
    homography = np.array([[2.0, 0.0, 400.0], [0.0, 2.0, 300.0], [0.0, 0.0, 1.0]])
    wrong_corner_pitch = np.array([[[20.0, 20.0]]], dtype=np.float64)
    calibrated = cv2.perspectiveTransform(wrong_corner_pitch, homography)
    normalized = calibrated.copy()
    normalized[..., 0] = (normalized[..., 0] - camera[0, 2]) / camera[0, 0]
    normalized[..., 1] = (normalized[..., 1] - camera[1, 2]) / camera[1, 1]
    raw = cv2.fisheye.distortPoints(normalized, camera, distortion).reshape(-1, 2)

    result = summarize_calibration(
        raw,
        np.array([[52.5, 34.0]]),
        camera,
        distortion,
        camera,
        homography,
        tolerance_meters=5.0,
    )

    assert result["withinAssignmentTolerance"] is False
    assert result["p95RoundTripErrorMeters"] > 5.0
