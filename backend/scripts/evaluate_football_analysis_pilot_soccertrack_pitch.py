from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from backend.scripts.run_football_external_soccertrack_calibrated_alignment import (
    project_raw_points_to_pitch,
    score_pitch_alignment,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"
CALIBRATION_PATH = (
    REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_soccertrack_calibration_cv.json"
)
REFERENCE_PATH = REPO_ROOT / (
    "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/"
    "football_analysis_pilot_corpus_v1/soccertrack/117093/pilot_reference_intervals.jsonl.gz"
)
INTRINSICS_PATH = REPO_ROOT / (
    "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/"
    "football_analysis_pilot_corpus_v1/soccertrack/117093/calibration/117093_camera_intrinsics.npz"
)
OUTPUT_PATH = REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_soccertrack_pitch_diagnostic.json"
ARTIFACTS = {
    "soccertrack-v2-117093-01": REPO_ROOT
    / "backend/storage/football-analysis-pilot-predictions-v1/matches/dd7c1e792cae4d46bf452e079ca461d5",
    "soccertrack-v2-117093-02": REPO_ROOT
    / "backend/storage/football-analysis-pilot-predictions-v1/matches/dda6be8971a34f9f841008dca7ced4c4",
    "soccertrack-v2-117093-03": REPO_ROOT
    / "backend/storage/football-analysis-pilot-predictions-v1/matches/a49358f5360348a7b7135d90abb85dab",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_task_references(
    task: Mapping[str, object], rows: Sequence[Mapping[str, object]]
) -> list[Mapping[str, object]]:
    start, end = float(task["globalStartSeconds"]), float(task["globalEndSeconds"])
    return [row for row in rows if start <= float(row["videoTimelineSeconds"]) < end]


def score_task_pitch_alignment(
    prediction_rows: Sequence[Mapping[str, object]],
    reference_rows: Sequence[Mapping[str, object]],
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    calibrated_camera_matrix: np.ndarray,
    calibrated_to_pitch_homography: np.ndarray,
    *,
    frame_count: int,
    frame_stride: int,
    threshold_meters: float,
) -> dict[str, object]:
    if len(reference_rows) != frame_count or frame_count <= 0 or frame_stride <= 0:
        raise ValueError("reference rows must cover the positive task frame count")
    evaluation_frames = set(range(0, frame_count, frame_stride))
    players = [
        row
        for row in prediction_rows
        if row.get("Entity_Type") == "player" and int(row.get("Frame_ID", -1)) in evaluation_frames
    ]
    raw_points = np.asarray(
        [
            [
                (float(row["Source_X1"]) + float(row["Source_X2"])) / 2,
                float(row["Source_Y2"]),
            ]
            for row in players
        ],
        dtype=float,
    ).reshape(-1, 2)
    projected = project_raw_points_to_pitch(
        raw_points,
        camera_matrix,
        distortion,
        calibrated_camera_matrix,
        np.linalg.inv(calibrated_to_pitch_homography),
    )
    predictions_by_frame: dict[int, list[np.ndarray]] = defaultdict(list)
    for row, point in zip(players, projected, strict=True):
        predictions_by_frame[int(row["Frame_ID"])].append(point)

    references_by_frame: dict[int, list[list[float]]] = defaultdict(list)
    normalized_positions: list[tuple[float, float]] = []
    for frame in evaluation_frames:
        for entity in reference_rows[frame].get("entities", []):
            if entity.get("entityType") != "player":
                continue
            position = entity["pitchPositionNormalized"]
            x, y = float(position["x"]), float(position["y"])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("reference pitch coordinates must be finite")
            normalized_positions.append((x, y))
            references_by_frame[frame].append([x * 105 - 52.5, 34 - y * 68])

    return {
        "evaluatedFrameCount": len(evaluation_frames),
        "outOfPitchReferenceCount": sum(
            not 0 <= x <= 1 or not 0 <= y <= 1 for x, y in normalized_positions
        ),
        "referenceNormalizedCoordinateRange": {
            "x": [min(x for x, _ in normalized_positions), max(x for x, _ in normalized_positions)],
            "y": [min(y for _, y in normalized_positions), max(y for _, y in normalized_positions)],
        },
        "pitchAlignment": score_pitch_alignment(
            {frame: np.asarray(points) for frame, points in predictions_by_frame.items()},
            {frame: np.asarray(points) for frame, points in references_by_frame.items()},
            threshold_meters=threshold_meters,
        ),
    }


def main() -> None:
    tasks = [
        task
        for task in json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]
        if task["sourceId"] == "soccertrack-v2-117093"
    ]
    with gzip.open(REFERENCE_PATH, "rt", encoding="utf-8") as stream:
        all_references = [json.loads(line) for line in stream]
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))["resultsBySource"][
        "soccertrack-v2-117093"
    ]
    if not calibration["withinAssignmentTolerance"]:
        raise ValueError("117093 withheld calibration must pass before pitch scoring")
    direct_homography = np.asarray(calibration["fullFitCalibratedToPitchHomography"], dtype=float)
    intrinsics = np.load(INTRINSICS_PATH)
    task_results = []
    prediction_hashes = {}
    for task in tasks:
        task_id = task["taskId"]
        references = select_task_references(task, all_references)
        raw_rows_path = ARTIFACTS[task_id] / "raw_rows.json"
        prediction_hashes[str(raw_rows_path.relative_to(REPO_ROOT))] = _sha256(raw_rows_path)
        result = score_task_pitch_alignment(
            json.loads(raw_rows_path.read_text(encoding="utf-8")),
            references,
            intrinsics["K"],
            intrinsics["D"],
            intrinsics["Knew"],
            direct_homography,
            frame_count=int(task["frameCount"]),
            frame_stride=int(task["evaluationFrameStep"]),
            threshold_meters=5.0,
        )
        task_results.append({"taskId": task_id, "referenceFrameCount": len(references), **result})
    counts = {
        key: sum(result["pitchAlignment"][key] for result in task_results)
        for key in ("predictedEntityCount", "referenceEntityCount", "matchedEntityCount")
    }
    out_of_pitch = sum(result["outOfPitchReferenceCount"] for result in task_results)
    payload = {
        "schemaVersion": "football_analysis_pilot_soccertrack_pitch_diagnostic_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceId": "soccertrack-v2-117093",
        "developmentDiagnosticOnly": True,
        "pilotAcceptanceEligible": False,
        "exclusionReasons": [
            "only pitch-position detection alignment on one validation source is scored",
            "the validation source informed prior training and calibration work",
            "anonymous frame-local matching does not score identity, team, role, or possession",
            "the 5 m diagnostic association threshold is looser than the frozen 3 m pilot p95 bar",
        ],
        "referenceLabelsUsedForInference": False,
        "heldOutSourceAccessed": False,
        "runtimeCalibrationChanged": False,
        "frameAlignment": (
            "select each frozen task by video timeline time, index its exact 2500 reference frames "
            "from zero, and score local prediction frames 0..2495 at stride five"
        ),
        "calibrationPath": str(CALIBRATION_PATH.relative_to(REPO_ROOT)),
        "calibrationSha256": _sha256(CALIBRATION_PATH),
        "referencePath": str(REFERENCE_PATH.relative_to(REPO_ROOT)),
        "referenceSha256": _sha256(REFERENCE_PATH),
        "intrinsicsPath": str(INTRINSICS_PATH.relative_to(REPO_ROOT)),
        "intrinsicsSha256": _sha256(INTRINSICS_PATH),
        "predictionSha256ByPath": prediction_hashes,
        "taskResults": task_results,
        "pooledCountSummary": {
            **counts,
            "outOfPitchReferenceCount": out_of_pitch,
            "outOfPitchReferenceShare": out_of_pitch / counts["referenceEntityCount"],
            "precision": counts["matchedEntityCount"] / counts["predictedEntityCount"],
            "recall": counts["matchedEntityCount"] / counts["referenceEntityCount"],
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["pooledCountSummary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
