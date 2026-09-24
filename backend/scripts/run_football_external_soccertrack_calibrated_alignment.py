from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.scripts.run_football_external_soccertrack_adapter_smoke_test import (
    _gsr_entity,
    _gsr_frame_index,
    _iter_json_array,
)


def project_raw_points_to_pitch(
    points_xy: np.ndarray,
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    calibrated_camera_matrix: np.ndarray,
    pitch_to_calibrated_homography: np.ndarray,
) -> np.ndarray:
    """Project raw fisheye pixels into SoccerTrack centre-origin pitch metres."""
    raw = np.asarray(points_xy, dtype=np.float64).reshape(-1, 1, 2)
    calibrated = cv2.fisheye.undistortPoints(
        raw,
        np.asarray(camera_matrix, dtype=np.float64),
        np.asarray(distortion, dtype=np.float64),
        P=np.asarray(calibrated_camera_matrix, dtype=np.float64),
    )
    corner_pitch = cv2.perspectiveTransform(
        calibrated.astype(np.float32),
        np.linalg.inv(np.asarray(pitch_to_calibrated_homography, dtype=np.float64)),
    ).reshape(-1, 2).astype(np.float64)
    corner_pitch[:, 0] -= 52.5
    corner_pitch[:, 1] = 34.0 - corner_pitch[:, 1]
    return corner_pitch


def summarize_calibration(
    raw_keypoints: np.ndarray,
    corner_pitch_keypoints: np.ndarray,
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    calibrated_camera_matrix: np.ndarray,
    pitch_to_calibrated_homography: np.ndarray,
    *,
    tolerance_meters: float,
) -> dict[str, float | int | bool]:
    projected = project_raw_points_to_pitch(
        raw_keypoints,
        camera_matrix,
        distortion,
        calibrated_camera_matrix,
        pitch_to_calibrated_homography,
    )
    expected = np.asarray(corner_pitch_keypoints, dtype=float).reshape(-1, 2).copy()
    expected[:, 0] -= 52.5
    expected[:, 1] = 34.0 - expected[:, 1]
    errors = np.linalg.norm(projected - expected, axis=1)
    p95 = float(np.percentile(errors, 95))
    return {
        "keypointCount": len(errors),
        "assignmentToleranceMeters": float(tolerance_meters),
        "meanRoundTripErrorMeters": float(np.mean(errors)),
        "medianRoundTripErrorMeters": float(np.median(errors)),
        "p95RoundTripErrorMeters": p95,
        "maxRoundTripErrorMeters": float(np.max(errors)),
        "withinAssignmentTolerance": p95 <= tolerance_meters,
    }


def cross_validate_direct_homography(
    raw_keypoints: np.ndarray,
    corner_pitch_keypoints: np.ndarray,
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    calibrated_camera_matrix: np.ndarray,
    *,
    tolerance_meters: float,
) -> dict[str, object]:
    """Fit on every control point except the one being scored."""
    raw = np.asarray(raw_keypoints, dtype=np.float64).reshape(-1, 1, 2)
    pitch = np.asarray(corner_pitch_keypoints, dtype=np.float64).reshape(-1, 2)
    if len(raw) != len(pitch) or len(raw) < 5 or tolerance_meters <= 0:
        raise ValueError("matching keypoint arrays need at least five points and a positive tolerance")
    calibrated = cv2.fisheye.undistortPoints(
        raw,
        np.asarray(camera_matrix, dtype=np.float64),
        np.asarray(distortion, dtype=np.float64),
        P=np.asarray(calibrated_camera_matrix, dtype=np.float64),
    ).reshape(-1, 2)
    errors = []
    for withheld in range(len(pitch)):
        training = np.arange(len(pitch)) != withheld
        homography, _ = cv2.findHomography(calibrated[training], pitch[training], method=0)
        if homography is None:
            raise ValueError(f"homography fit failed for withheld keypoint {withheld}")
        projected = cv2.perspectiveTransform(
            calibrated[withheld].reshape(1, 1, 2), homography
        ).reshape(2)
        errors.append(float(np.linalg.norm(projected - pitch[withheld])))
    full_fit, _ = cv2.findHomography(calibrated, pitch, method=0)
    if full_fit is None:
        raise ValueError("full homography fit failed")
    p95 = float(np.percentile(errors, 95))
    return {
        "method": "leave_one_keypoint_out",
        "fitAndScoreUseSameKeypoint": False,
        "foldCount": len(errors),
        "trainingKeypointsPerFold": len(errors) - 1,
        "assignmentToleranceMeters": float(tolerance_meters),
        "meanWithheldErrorMeters": float(np.mean(errors)),
        "medianWithheldErrorMeters": float(np.median(errors)),
        "p95WithheldErrorMeters": p95,
        "maxWithheldErrorMeters": float(np.max(errors)),
        "withinAssignmentTolerance": p95 <= tolerance_meters,
        "fullFitCalibratedToPitchHomography": full_fit.tolist(),
    }


def score_pitch_alignment(
    predictions_by_frame: dict[int, np.ndarray],
    references_by_frame: dict[int, np.ndarray],
    *,
    threshold_meters: float,
) -> dict[str, float | int | None]:
    """Score frame-local Hungarian assignments, then gate them by distance."""
    predicted_count = sum(len(points) for points in predictions_by_frame.values())
    reference_count = sum(len(points) for points in references_by_frame.values())
    matched_errors: list[float] = []
    for frame in sorted(set(predictions_by_frame) | set(references_by_frame)):
        predictions = np.asarray(predictions_by_frame.get(frame, []), dtype=float).reshape(-1, 2)
        references = np.asarray(references_by_frame.get(frame, []), dtype=float).reshape(-1, 2)
        if not len(predictions) or not len(references):
            continue
        distances = np.linalg.norm(predictions[:, None, :] - references[None, :, :], axis=2)
        prediction_indices, reference_indices = linear_sum_assignment(distances)
        matched_errors.extend(
            float(distance)
            for distance in distances[prediction_indices, reference_indices]
            if distance <= threshold_meters
        )
    matched_count = len(matched_errors)
    return {
        "thresholdMeters": float(threshold_meters),
        "predictedEntityCount": predicted_count,
        "referenceEntityCount": reference_count,
        "matchedEntityCount": matched_count,
        "unmatchedPredictedCount": predicted_count - matched_count,
        "unmatchedReferenceCount": reference_count - matched_count,
        "precision": matched_count / predicted_count if predicted_count else None,
        "recall": matched_count / reference_count if reference_count else None,
        "medianMatchedErrorMeters": float(np.median(matched_errors)) if matched_errors else None,
        "p95MatchedErrorMeters": float(np.percentile(matched_errors, 95)) if matched_errors else None,
    }


def evaluate_prediction_result(
    prediction_path: Path,
    gsr_path: Path,
    intrinsics_path: Path,
    homography_path: Path,
    *,
    sampled_frames: set[int],
    threshold_meters: float,
) -> dict[str, object]:
    """Compare already-produced raw-image player tracks with GSR pitch references."""
    if not sampled_frames or threshold_meters <= 0:
        raise ValueError("sampled_frames must be non-empty and threshold_meters must be positive")
    prediction = json.loads(Path(prediction_path).read_text(encoding="utf-8"))
    rows = [
        row
        for row in prediction.get("rows", [])
        if row.get("Entity_Type") == "player" and int(row.get("Frame_ID", -1)) in sampled_frames
    ]
    intrinsics = np.load(intrinsics_path)
    projected = (
        project_raw_points_to_pitch(
            np.array(
                [
                    [
                        (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0,
                        float(row["Source_Y2"]),
                    ]
                    for row in rows
                ]
            ),
            intrinsics["K"],
            intrinsics["D"],
            intrinsics["Knew"],
            np.load(homography_path),
        )
        if rows
        else np.empty((0, 2))
    )
    predictions_by_frame: dict[int, list[np.ndarray]] = {frame: [] for frame in sampled_frames}
    for row, point in zip(rows, projected, strict=False):
        predictions_by_frame[int(row["Frame_ID"])].append(point)

    references_by_frame: dict[int, list[list[float]]] = {frame: [] for frame in sampled_frames}
    with Path(gsr_path).open(encoding="utf-8") as stream:
        annotations = _iter_json_array(stream, "annotations")
        try:
            for annotation in annotations:
                frame = _gsr_frame_index(annotation.get("image_id"))
                if frame > max(sampled_frames):
                    break
                if frame not in sampled_frames or annotation.get("supercategory") != "object":
                    continue
                entity = _gsr_entity(annotation)
                if entity is not None:
                    point = entity["pitchPositionMeters"]
                    references_by_frame[frame].append([point["x"], point["y"]])
        finally:
            annotations.close()

    return {
        "predictionPath": str(prediction_path),
        "referencePath": str(gsr_path),
        "sampledFrames": sorted(sampled_frames),
        "referenceLabelsUsedForInference": False,
        "referenceUse": "post_inference_scoring_only",
        "imageSpaceScoringPerformed": False,
        "imageSpaceScoringReason": "SoccerTrack v2 GSR has no ground-truth detections",
        "gsHota": None,
        "gsHotaReason": (
            "official pitch-space GS-HOTA requires role, team, and jersey attributes that "
            "the application result does not emit"
        ),
        "motHotaAndIdf1": None,
        "motHotaAndIdf1Reason": (
            "SoccerTrack v2 GSR has no ground-truth image detections and no MOTChallenge "
            "ground-truth file is present"
        ),
        "pitchAlignment": score_pitch_alignment(
            {frame: np.asarray(points) for frame, points in predictions_by_frame.items()},
            {frame: np.asarray(points) for frame, points in references_by_frame.items()},
            threshold_meters=threshold_meters,
        ),
    }


def _load_keypoints(path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return (
        np.asarray(list(payload.values()), dtype=float),
        np.asarray([list(map(float, key.strip("()").split(","))) for key in payload], dtype=float),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score raw-fisheye pipeline tracks against bounded SoccerTrack GSR references."
    )
    parser.add_argument("--prediction", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--gsr", type=Path, required=True)
    parser.add_argument("--intrinsics", type=Path, required=True)
    parser.add_argument("--homography", type=Path, required=True)
    parser.add_argument("--keypoints", type=Path, required=True)
    parser.add_argument("--frame-count", type=int, default=100)
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--threshold-meters", type=float, default=5.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.frame_count <= 0 or args.frame_stride <= 0 or args.threshold_meters <= 0:
        parser.error("frame-count, frame-stride, and threshold-meters must be positive")

    runs: dict[str, Path] = {}
    for value in args.prediction:
        name, separator, path = value.partition("=")
        if not separator or not name or not path or name in runs:
            parser.error("each --prediction must be a unique NAME=PATH")
        runs[name] = Path(path)

    intrinsics = np.load(args.intrinsics)
    raw_keypoints, pitch_keypoints = _load_keypoints(args.keypoints)
    calibration = summarize_calibration(
        raw_keypoints,
        pitch_keypoints,
        intrinsics["K"],
        intrinsics["D"],
        intrinsics["Knew"],
        np.load(args.homography),
        tolerance_meters=args.threshold_meters,
    )
    sampled_frames = set(range(0, args.frame_count, args.frame_stride))
    payload = {
        "schemaVersion": "football_external_soccertrack_calibrated_alignment_v1",
        "evaluationMode": "bounded_post_inference_diagnostic",
        "readinessQualified": False,
        "readinessReason": (
            "calibration p95 exceeds the assignment tolerance"
            if not calibration["withinAssignmentTolerance"]
            else "single bounded slice is not an independent analyst pilot"
        ),
        "projection": "raw fisheye feet -> undistortPoints(K,D,Knew) -> inverse pitch-to-calibrated homography -> centre-origin metres",
        "calibration": calibration,
        "identityAndTeamScoringPerformed": False,
        "identityAndTeamScoringReason": "the application result does not emit reference-compatible player identity, jersey, role, or team labels",
        "runs": {
            name: evaluate_prediction_result(
                path,
                args.gsr,
                args.intrinsics,
                args.homography,
                sampled_frames=sampled_frames,
                threshold_meters=args.threshold_meters,
            )
            for name, path in runs.items()
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
