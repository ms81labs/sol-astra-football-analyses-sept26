from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.scripts.run_football_external_soccertrack_calibrated_alignment import (
    _load_keypoints,
    cross_validate_direct_homography,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = (
    REPO_ROOT / "backend/benchmark_suites/football_analysis_pilot_soccertrack_calibration_cv.json"
)
SOURCES = {
    "soccertrack-v2-117092": REPO_ROOT
    / "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccertrack_google_drive_bounded_fixture_fetch_v1/sample_fixture_files/selected_match_117092",
    "soccertrack-v2-117093": REPO_ROOT
    / "backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/soccertrack/117093/calibration",
}
FILES = {
    "soccertrack-v2-117092": (
        "raw__117092__117092_camera_intrinsics.npz",
        "raw__117092__117092_homography.npy",
        "raw__117092__117092_keypoints.json",
    ),
    "soccertrack-v2-117093": (
        "117093_camera_intrinsics.npz",
        "117093_homography.npy",
        "117093_keypoints.json",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    results = {}
    for source_id, root in SOURCES.items():
        intrinsics_name, homography_name, keypoints_name = FILES[source_id]
        intrinsics_path = root / intrinsics_name
        homography_path = root / homography_name
        keypoints_path = root / keypoints_name
        intrinsics = np.load(intrinsics_path)
        raw_keypoints, pitch_keypoints = _load_keypoints(keypoints_path)
        results[source_id] = {
            "inputs": {
                str(path.relative_to(REPO_ROOT)): _sha256(path)
                for path in (intrinsics_path, homography_path, keypoints_path)
            },
            "shippedHomographyUsedForFit": False,
            "shippedHomographyInputRetainedForProvenanceOnly": str(
                homography_path.relative_to(REPO_ROOT)
            ),
            **cross_validate_direct_homography(
                raw_keypoints,
                pitch_keypoints,
                intrinsics["K"],
                intrinsics["D"],
                intrinsics["Knew"],
                tolerance_meters=5.0,
            ),
        }
    payload = {
        "schemaVersion": "football_analysis_pilot_soccertrack_calibration_cv_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evaluationMode": "validation_only_leave_one_keypoint_out",
        "validationSourceIds": sorted(SOURCES),
        "heldOutSourceAccessed": False,
        "pipelineInferenceRun": False,
        "runtimeCalibrationChanged": False,
        "resultsBySource": results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
