# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2

from ultralytics import YOLO, __version__ as ultralytics_version

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import (
    DEFAULT_MANUAL_POINTS,
    DEFAULT_TRIMMED_CLIP_PATH,
)
from backend.app.homography_utils import build_homography_from_points
from backend.run_guerilla import (
    TRACKING_CONF,
    TRACKING_IMGSZ,
    TARGET_FPS,
    build_ball_recovery_quality_matrix_profiles,
    build_detector_breadth_screen_ball_recovery_profiles,
    collect_primary_player_windows,
    run_ball_recovery_experiment,
    select_best_ball_recovery_profile,
)


def _default_profiles(profile_mode: str = "full_matrix") -> list[dict[str, object]]:
    if profile_mode == "detector_breadth_screen":
        return build_detector_breadth_screen_ball_recovery_profiles()
    return build_ball_recovery_quality_matrix_profiles()


def _json_ready_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    json_results: list[dict[str, object]] = []
    for result in results:
        candidate_summary = result["candidateSummary"]
        json_results.append(
            {
                "name": result["name"],
                "settings": result["settings"],
                "usePlayerWindows": result["usePlayerWindows"],
                "candidateSummary": candidate_summary,
                "selectedSummary": result["selectedSummary"],
                "selectedScore": result["selectedScore"],
                "viable": result["viable"],
                "dominantAnchorCoord": candidate_summary.get("dominantAnchorCoord"),
                "dominantAnchorShare": candidate_summary.get("dominantAnchorShare", 0.0),
                "meanSourceCenterY": candidate_summary.get("meanSourceCenterY", 0.0),
            }
        )
    return json_results


def run_local_ball_recovery_matrix(
    *,
    video_path: Path,
    manual_points: list[list[float]] | None = None,
    name: str | None = None,
    model_path: str = "yolov10n.pt",
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    profile_mode: str = "full_matrix",
) -> dict[str, object]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    frame_interval = int(fps / TARGET_FPS) if fps > TARGET_FPS else 1

    pitch_points = manual_points or [[point.x, point.y] for point in DEFAULT_MANUAL_POINTS]
    homography = build_homography_from_points(pitch_points)
    resolved_primary_model_path = str(primary_model_path or model_path)
    primary_model = YOLO(resolved_primary_model_path)
    auxiliary_model = YOLO(auxiliary_ball_model_path) if auxiliary_ball_model_path else None
    player_windows = collect_primary_player_windows(
        str(video_path),
        model=primary_model,
        frame_interval=frame_interval,
        imgsz=TRACKING_IMGSZ,
        conf=TRACKING_CONF,
        tracker="botsort.yaml",
    )
    recovery_model = auxiliary_model or primary_model
    recovery_detector_profile = auxiliary_ball_model_profile or "coco_tracking_full"

    results = run_ball_recovery_experiment(
        video_path=str(video_path),
        model=recovery_model,
        detector_profile=recovery_detector_profile,
        H=homography,
        pitch_points=pitch_points,
        fps=fps,
        frame_interval=frame_interval,
        imgsz=TRACKING_IMGSZ,
        conf=TRACKING_CONF,
        player_windows=player_windows,
        profiles=_default_profiles(profile_mode),
    )
    profiles = sorted(_json_ready_results(results), key=lambda result: float(result["selectedScore"]), reverse=True)
    recommended = select_best_ball_recovery_profile(results)
    return {
        "name": name,
        "videoPath": str(video_path),
        "profileMode": profile_mode,
        "primaryDetectorModelPath": resolved_primary_model_path,
        "primaryDetectorModelName": Path(resolved_primary_model_path).name,
        "auxiliaryBallModelPath": auxiliary_ball_model_path,
        "auxiliaryBallModelName": (
            Path(str(auxiliary_ball_model_path)).name if auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelProfile": auxiliary_ball_model_profile,
        "runtimeStamp": {
            "pythonExecutable": sys.executable,
            "cv2Version": cv2.__version__,
            "ultralyticsVersion": ultralytics_version,
        },
        "profiles": profiles,
        "recommendedProfile": recommended["name"] if recommended is not None else "no_viable_profile",
    }


def _parse_manual_points(payload: str | None) -> list[list[float]] | None:
    if payload is None:
        return None
    return [[float(point[0]), float(point[1])] for point in json.loads(payload)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the trimmed-clip ball-recovery experiment matrix.")
    parser.add_argument("--video-path", default=str(DEFAULT_TRIMMED_CLIP_PATH))
    parser.add_argument("--name", default=None)
    parser.add_argument("--model-path", default="yolov10n.pt")
    parser.add_argument("--primary-model-path", default=None)
    parser.add_argument("--auxiliary-ball-model-path", default=None)
    parser.add_argument("--auxiliary-ball-model-profile", default=None)
    parser.add_argument("--profile-mode", choices=("full_matrix", "detector_breadth_screen"), default="full_matrix")
    parser.add_argument("--manual-points-json", default=None)
    args = parser.parse_args()

    payload = run_local_ball_recovery_matrix(
        video_path=Path(args.video_path),
        manual_points=_parse_manual_points(args.manual_points_json),
        name=args.name,
        model_path=args.model_path,
        primary_model_path=args.primary_model_path,
        auxiliary_ball_model_path=args.auxiliary_ball_model_path,
        auxiliary_ball_model_profile=args.auxiliary_ball_model_profile,
        profile_mode=args.profile_mode,
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
