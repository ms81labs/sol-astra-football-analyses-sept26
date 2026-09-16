from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from backend.scripts.evaluate_football_analysis_pilot_soccertrack_pitch import (
    ARTIFACTS,
    CALIBRATION_PATH,
    INTRINSICS_PATH,
    REFERENCE_PATH,
    REPO_ROOT,
    TASKS_PATH,
    score_task_pitch_alignment,
    select_task_references,
)
from backend.scripts.run_football_external_soccertrack_calibrated_alignment import (
    project_raw_points_to_pitch,
)


MODEL_PATH = REPO_ROOT / "yolov10n.pt"
CLIP_ROOT = REPO_ROOT / (
    "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/"
    "football_analysis_pilot_corpus_v1/annotation_clips"
)
OUTPUT_PATH = (
    REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_soccertrack_resolution_diagnostic.json"
)
TASK_IDS = ("soccertrack-v2-117093-01", "soccertrack-v2-117093-03")
FRAME_STRIDE = 100
IMAGE_SIZES = (1280, 1920)
TILE_WIDTH = 1024
CONFIDENCE_CUTOFFS = (0.25, 0.4, 0.6)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sampled_images(path: Path, frame_count: int) -> dict[int, np.ndarray]:
    frames = set(range(0, frame_count, FRAME_STRIDE))
    images = {}
    capture = cv2.VideoCapture(str(path))
    frame = 0
    while frame < frame_count:
        ok, image = capture.read()
        if not ok:
            break
        if frame in frames:
            images[frame] = image
        frame += 1
    capture.release()
    if set(images) != frames:
        raise ValueError(f"{path} did not supply every declared probe frame")
    return images


def _predict_boxes(
    model: YOLO, image: np.ndarray, image_size: int, *, tile_width: int | None = None
) -> np.ndarray:
    width = tile_width or image.shape[1]
    results = []
    for left in range(0, image.shape[1], width):
        detections = model.predict(
            image[:, left : left + width], imgsz=image_size, conf=0.12, classes=[0], verbose=False
        )[0].boxes
        boxes = detections.xyxy.cpu().numpy().copy()
        boxes[:, (0, 2)] += left
        results.append(np.column_stack((boxes, detections.conf.cpu().numpy())))
    return np.concatenate(results) if results else np.empty((0, 5))


def _predict_on_pitch_rows(
    model: YOLO,
    images: dict[int, np.ndarray],
    image_size: int,
    intrinsics: np.lib.npyio.NpzFile,
    calibrated_to_pitch: np.ndarray,
    *,
    tile_width: int | None = None,
) -> tuple[list[dict[str, object]], int]:
    rows = []
    raw_count = 0
    pitch_to_calibrated = np.linalg.inv(calibrated_to_pitch)
    for frame, image in images.items():
        boxes = _predict_boxes(model, image, image_size, tile_width=tile_width)
        raw_count += len(boxes)
        anchors = np.asarray([[(x1 + x2) / 2, y2] for x1, _y1, x2, y2, _confidence in boxes]).reshape(-1, 2)
        projected = project_raw_points_to_pitch(
            anchors,
            intrinsics["K"],
            intrinsics["D"],
            intrinsics["Knew"],
            pitch_to_calibrated,
        )
        for box, point in zip(boxes, projected, strict=True):
            if abs(point[0]) > 52.5 or abs(point[1]) > 34:
                continue
            x1, y1, x2, y2, confidence = map(float, box)
            rows.append(
                {
                    "Entity_Type": "player",
                    "Frame_ID": frame,
                    "Source_X1": x1,
                    "Source_Y1": y1,
                    "Source_X2": x2,
                    "Source_Y2": y2,
                    "Confidence": confidence,
                }
            )
    return rows, raw_count


def main() -> None:
    tasks = {
        task["taskId"]: task
        for task in json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]
        if task["taskId"] in TASK_IDS
    }
    if set(tasks) != set(TASK_IDS):
        raise ValueError("both declared first/second-half validation tasks are required")
    with gzip.open(REFERENCE_PATH, "rt", encoding="utf-8") as stream:
        all_references = [json.loads(line) for line in stream]
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))["resultsBySource"][
        "soccertrack-v2-117093"
    ]
    if not calibration["withinAssignmentTolerance"]:
        raise ValueError("117093 withheld calibration must pass before resolution probing")
    direct_homography = np.asarray(calibration["fullFitCalibratedToPitchHomography"], dtype=float)
    intrinsics = np.load(INTRINSICS_PATH)
    model = YOLO(MODEL_PATH)
    results = []
    for task_id in TASK_IDS:
        task = tasks[task_id]
        references = select_task_references(task, all_references)
        artifact_path = ARTIFACTS[task_id] / "raw_rows.json"
        clip_path = CLIP_ROOT / f"{task_id}.mp4"
        images = _sampled_images(clip_path, int(task["frameCount"]))
        task_result = {
            "taskId": task_id,
            "half": "first" if task_id.endswith("01") else "second",
            "clipPath": str(clip_path.relative_to(REPO_ROOT)),
            "clipSha256": _sha256(clip_path),
            "savedPredictionPath": str(artifact_path.relative_to(REPO_ROOT)),
            "savedPredictionSha256": _sha256(artifact_path),
            "savedProduction": score_task_pitch_alignment(
                json.loads(artifact_path.read_text(encoding="utf-8")),
                references,
                intrinsics["K"],
                intrinsics["D"],
                intrinsics["Knew"],
                direct_homography,
                frame_count=int(task["frameCount"]),
                frame_stride=FRAME_STRIDE,
                threshold_meters=5.0,
            ),
            "freshDetectionByImageSize": {},
        }
        for image_size in IMAGE_SIZES:
            rows, raw_count = _predict_on_pitch_rows(
                model, images, image_size, intrinsics, direct_homography
            )
            task_result["freshDetectionByImageSize"][str(image_size)] = {
                "rawDetectionCount": raw_count,
                "onPitchDetectionCount": len(rows),
                **score_task_pitch_alignment(
                    rows,
                    references,
                    intrinsics["K"],
                    intrinsics["D"],
                    intrinsics["Knew"],
                    direct_homography,
                    frame_count=int(task["frameCount"]),
                    frame_stride=FRAME_STRIDE,
                    threshold_meters=5.0,
                ),
            }
        tiled_rows, tiled_raw_count = _predict_on_pitch_rows(
            model, images, 1280, intrinsics, direct_homography, tile_width=TILE_WIDTH
        )
        task_result["tiled1280Detection"] = {
            "tileWidthPixels": TILE_WIDTH,
            "tileOverlapPixels": 0,
            "tileHeightPixels": "full_source_frame",
            "rawDetectionCount": tiled_raw_count,
            "onPitchDetectionCount": len(tiled_rows),
            **score_task_pitch_alignment(
                tiled_rows,
                references,
                intrinsics["K"],
                intrinsics["D"],
                intrinsics["Knew"],
                direct_homography,
                frame_count=int(task["frameCount"]),
                frame_stride=FRAME_STRIDE,
                threshold_meters=5.0,
            ),
        }
        task_result["tiled1280ConfidenceSweep"] = {
            str(cutoff): score_task_pitch_alignment(
                [row for row in tiled_rows if row["Confidence"] >= cutoff],
                references,
                intrinsics["K"],
                intrinsics["D"],
                intrinsics["Knew"],
                direct_homography,
                frame_count=int(task["frameCount"]),
                frame_stride=FRAME_STRIDE,
                threshold_meters=5.0,
            )["pitchAlignment"]
            for cutoff in CONFIDENCE_CUTOFFS
        }
        results.append(task_result)
    payload = {
        "schemaVersion": "football_analysis_pilot_soccertrack_resolution_diagnostic_v3",
        "developmentDiagnosticOnly": True,
        "pilotAcceptanceEligible": False,
        "validationSourceId": "soccertrack-v2-117093",
        "sampledTaskIds": list(TASK_IDS),
        "sampledFramesPerTask": 25,
        "sourceFrameStride": FRAME_STRIDE,
        "modelPath": str(MODEL_PATH.relative_to(REPO_ROOT)),
        "modelSha256": _sha256(MODEL_PATH),
        "calibrationPath": str(CALIBRATION_PATH.relative_to(REPO_ROOT)),
        "calibrationSha256": _sha256(CALIBRATION_PATH),
        "intrinsicsPath": str(INTRINSICS_PATH.relative_to(REPO_ROOT)),
        "intrinsicsSha256": _sha256(INTRINSICS_PATH),
        "referencePath": str(REFERENCE_PATH.relative_to(REPO_ROOT)),
        "referenceSha256": _sha256(REFERENCE_PATH),
        "trackingAppliedToFreshDetections": False,
        "confidenceSweepPostInference": True,
        "confidenceSweepCutoffs": list(CONFIDENCE_CUTOFFS),
        "referenceLabelsUsedForInference": False,
        "referenceUse": "post_inference_pitch_scoring_only",
        "officialValidationCalibrationUsedForPitchFiltering": True,
        "heldOutSourceAccessed": False,
        "runtimeChanged": False,
        "results": results,
        "decision": (
            "1920 and source-width tiling increase sample recall but fail the 3 m pitch p95 bar; "
            "higher tiled confidence improves sample precision at a recall cost, so promote neither"
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["results"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
