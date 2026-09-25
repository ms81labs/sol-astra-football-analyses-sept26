from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import cv2
import numpy as np
import argparse
import pandas as pd
import time
from math import gcd, hypot

from backend.app.edge_share_repair import apply_source_conditioned_edge_share_repair as _shared_apply_source_conditioned_edge_share_repair
from backend.app.edge_share_repair_profiles import (
    SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
    get_source_edge_share_repair_config,
)
from backend.app.homography_utils import build_homography_from_points as _build_H, point_to_pitch as _point_to_pitch
from backend.app.analytics import MAX_OWNER_DISTANCE
from backend.app.runtime_options import SUPPORTED_PRIMARY_ACQUISITION_MODE, validate_primary_acquisition_mode


def YOLO(*args, **kwargs):
    """Load the detector only when video processing actually starts."""
    from ultralytics import YOLO as detector
    return detector(*args, **kwargs)


HEADLESS = os.environ.get("QT_QPA_PLATFORM") == "offscreen" or (
    sys.platform.startswith("linux")
    and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
)

try:
    from backend.pitch_detector import detect_and_compute_homography, detect_pitch_corners, compute_pitch_homography
    AUTO_HOMOGRAPHY_AVAILABLE = True
except ImportError:
    AUTO_HOMOGRAPHY_AVAILABLE = False

# --- Configuration ---
TARGET_FPS = 5  # Configurable extraction rate
PITCH_WIDTH = 100.0
PITCH_HEIGHT = 100.0
HOMOGRAPHY_RECALC_FRAMES = 150  # Recalculate every N frames for camera sway
TRACKING_IMGSZ = 1280
TRACKING_CONF = 0.12
DIRECT_SEED_HI_RES_RETRY_IMGSZ = 960
TRACKING_CLASSES = [0, 32]
BALL_RECOVERY_IMGSZ = 1600
BALL_RECOVERY_CONF = 0.08
BALL_RECOVERY_EXPERIMENT_IMGSZ = 1920
DIRECT_SEED_SCALE_1920_RETRY_IMGSZ = 1920
DIRECT_SEED_RETRY_POLICY = "bounded_multiscale_fallback"
DIRECT_SEED_RETRY_SCALES = (
    BALL_RECOVERY_IMGSZ,
    DIRECT_SEED_HI_RES_RETRY_IMGSZ,
    DIRECT_SEED_SCALE_1920_RETRY_IMGSZ,
)
DETECTOR_PROFILE_COCO_TRACKING_FULL = "coco_tracking_full"
DETECTOR_PROFILE_BALL_PROBE_ONLY_V1 = "ball_probe_only_v1"
DETECTOR_PROFILE_BALL_PROBE_ONLY_V1_LOW_CONF_001 = "ball_probe_only_v1_low_conf_001"
DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3 = "ball_probe_only_v7_3_crop_256"
# v7.3 export/guardrail contract: padded square source crops, class 0, imgsz 256, conf .1.
V7_3_SOURCE_CROP_SIZES = (128, 192, 256, 384)
BALL_RECOVERY_EXPERIMENT_LOW_CONF = 0.05
BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_CONF = 0.01
BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_IMGSZ = 960
MIN_RECOVERED_BALL_FRAMES = 3
MIN_RECOVERED_BALL_SPAN = 4.0
MIN_RECOVERED_BALL_PATH = 12.0
STATIC_FALSE_BALL_RADIUS = 3.0
BALL_EDGE_MARGIN = 5.0
MAX_VIABLE_EDGE_FRAME_SHARE = 0.6
MIN_FALSE_BALL_DOMINANT_ANCHOR_SHARE = 0.45
MIN_FALSE_BALL_EDGE_FRAME_SHARE = 0.75
MIN_FALSE_BALL_EDGE_CANDIDATE_SHARE = 0.45
MAX_RECOVERED_BALL_DISTANCE_FROM_PLAYER_WINDOW = 45.0
MAX_COHERENT_BALL_STEP_DISTANCE = 25.0
BALL_RECOVERY_PADDING_PX = 120
MIN_BALL_RECOVERY_CROP_WIDTH = 1280
MIN_BALL_RECOVERY_CROP_HEIGHT = 720
MAX_DUPLICATE_RECOVERED_SOURCE_DISTANCE_PX = 12.0
PLAYER_PROPOSAL_CROP_PADDING_PX = 24
MIN_PLAYER_PROPOSAL_CROP_WIDTH = 96
MIN_PLAYER_PROPOSAL_CROP_HEIGHT = 96
DIRECT_SEED_CONTEXT_MIN_CROP_RATIO = 0.5
DEFAULT_PLAYER_PROPOSAL_MAX_WINDOWS_PER_FRAME = 3
BALL_RECOVERY_CROP_EDGE_MARGIN_PX = 20
TRUSTED_BALL_RECOVERY_CROP_EDGE_MARGIN_PX = 40
TRUSTED_BALL_RECOVERY_MAX_CROP_CENTER_Y_RATIO = 0.78
TOUCHLINE_ESCAPE_WINDOW_KIND = "touchline_escape"
TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND = "touchline_inboard_context"
REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND = "reviewed_positive_anchor"
TOUCHLINE_ESCAPE_EDGE_PROXIMITY_RATIO = 0.18
TOUCHLINE_ESCAPE_SEED_MARGIN_RATIO = 0.2
TOUCHLINE_ESCAPE_REJECTION_EDGE_SHARE = "edge_share_not_improved"
TOUCHLINE_ESCAPE_REJECTION_CONTINUITY = "anchor_continuity_regressed"
TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR = "repeated_anchor_suspicious"
BASELINE_GUIDED_RESCUE_SEED_MODE = "baseline_guided"
TOUCHLINE_ESCAPE_REJECTION_VIABILITY = "candidate_viability_regressed"
TOUCHLINE_ESCAPE_REJECTION_NO_CANDIDATES = "no_touchline_candidates_available"
BALL_PIPELINE_TRACE_VERSION = 1


def _normalize_detector_profile(detector_profile=None):
    normalized = str(detector_profile or DETECTOR_PROFILE_COCO_TRACKING_FULL).strip()
    if normalized in {
        DETECTOR_PROFILE_COCO_TRACKING_FULL,
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V1,
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V1_LOW_CONF_001,
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3,
    }:
        return normalized
    raise ValueError(f"Unsupported detector profile: {normalized}")


def detector_profile_spec(detector_profile=None):
    normalized = _normalize_detector_profile(detector_profile)
    if normalized in {
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V1,
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V1_LOW_CONF_001,
        DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3,
    }:
        profile = {
            "name": normalized,
            "playerClassIds": [],
            "ballClassIds": [0],
            "supportsPrimaryTracking": False,
        }
        if normalized == DETECTOR_PROFILE_BALL_PROBE_ONLY_V1_LOW_CONF_001:
            profile.update(
                {
                    "probeRecoveryConf": BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_CONF,
                    "probeRecoveryImgsz": BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_IMGSZ,
                }
            )
        return profile
    return {
        "name": DETECTOR_PROFILE_COCO_TRACKING_FULL,
        "playerClassIds": [0],
        "ballClassIds": [32],
        "supportsPrimaryTracking": True,
    }


def detector_probe_recovery_settings(detector_profile=None):
    normalized = _normalize_detector_profile(detector_profile)
    if normalized == DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3:
        return {"recoveryConf": 0.1, "recoveryImgsz": 256}
    if normalized == DETECTOR_PROFILE_BALL_PROBE_ONLY_V1_LOW_CONF_001:
        return {
            "recoveryConf": BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_CONF,
            "recoveryImgsz": BALL_PROBE_ONLY_V1_LOW_CONF_001_RECOVERY_IMGSZ,
        }
    return {
        "recoveryConf": BALL_RECOVERY_EXPERIMENT_LOW_CONF,
        "recoveryImgsz": BALL_RECOVERY_EXPERIMENT_IMGSZ,
    }


def detector_player_class_ids(detector_profile=None):
    return list(detector_profile_spec(detector_profile)["playerClassIds"])


def detector_ball_class_ids(detector_profile=None):
    return list(detector_profile_spec(detector_profile)["ballClassIds"])


def detector_tracking_class_ids(detector_profile=None):
    spec = detector_profile_spec(detector_profile)
    return sorted({*spec["playerClassIds"], *spec["ballClassIds"]})


def detector_class_is_ball(cls, detector_profile=None):
    return int(cls) in set(detector_ball_class_ids(detector_profile))


def detector_class_is_player(cls, detector_profile=None):
    return int(cls) in set(detector_player_class_ids(detector_profile))


def _empty_phase_timings():
    return {
        "modelLoadSeconds": 0.0,
        "videoOpenAndHomographySeconds": 0.0,
        "trackingPassSeconds": 0.0,
        "probeObservedPassSeconds": 0.0,
        "recoverySelectionSeconds": 0.0,
        "truthLayerFinalizeSeconds": 0.0,
        "resultSerializeSeconds": 0.0,
        "totalProcessVideoSeconds": 0.0,
    }

def select_homography_points(frame, return_points=False):
    """Allow the user to click 4 points on the first frame to define the homography mapping."""
    if HEADLESS:
        raise RuntimeError(
            "Manual homography point selection requires a display. "
            "Please provide homography_points (4 corner coordinates) or enable auto-homography."
        )
    points = []

    def mouse_callback(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([x, y])
            cv2.circle(frame_copy, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow("Select 4 Pitch Corners (TL, TR, BR, BL)", frame_copy)

    frame_copy = frame.copy()
    cv2.imshow("Select 4 Pitch Corners (TL, TR, BR, BL)", frame_copy)
    cv2.setMouseCallback("Select 4 Pitch Corners (TL, TR, BR, BL)", mouse_callback)
    print("Click 4 points on the pitch to establish the 2D projection plane.")
    print("Order: Top-Left, Top-Right, Bottom-Right, Bottom-Left")
    while len(points) < 4:
        cv2.waitKey(1)
    cv2.destroyAllWindows()
    homography = _build_H(points)
    if return_points:
        return homography, points
    return homography


# Re-export so existing callers (e.g. tests in other modules) get the shared implementation
build_homography_from_points = _build_H
point_to_pitch = _point_to_pitch

def resolve_homography(first_frame, homography_points=None, use_auto=True):
    if homography_points:
        if len(homography_points) != 4:
            raise ValueError("homography_points must contain exactly 4 points.")
        return build_homography_from_points(homography_points), homography_points

    # Try automatic pitch detection first
    if use_auto and AUTO_HOMOGRAPHY_AVAILABLE:
        H_auto, was_auto = detect_and_compute_homography(first_frame)
        if was_auto and H_auto is not None:
            print("Auto-homography: pitch detected successfully.")
            pitch_points = detect_pitch_corners(first_frame)
            return H_auto, pitch_points if pitch_points else None
        print("Auto-homography: detection failed." + (" Cannot fall back to manual in headless mode." if HEADLESS else " Falling back to manual."))

    # Manual fallback: user clicks 4 points
    if HEADLESS:
        raise RuntimeError(
            "Homography could not be detected automatically. "
            "Please provide manualHomographyPoints (4 corner coordinates) when uploading."
        )
    display_frame = cv2.resize(first_frame, (1280, 720))
    scale_x = first_frame.shape[1] / 1280.0
    scale_y = first_frame.shape[0] / 720.0

    H_low_res, selected_points = select_homography_points(display_frame, return_points=True)
    S = np.array([
        [1.0 / scale_x, 0, 0],
        [0, 1.0 / scale_y, 0],
        [0, 0, 1]
    ])
    scaled_points = [[point[0] * scale_x, point[1] * scale_y] for point in selected_points]
    return H_low_res.dot(S), scaled_points


def projection_anchor_for_detection(cls, x1, y1, x2, y2, detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL):
    cx = (x1 + x2) / 2
    if detector_class_is_ball(cls, detector_profile):
        cy = (y1 + y2) / 2
    else:
        cy = y2
    return cx, cy


def should_keep_detection_for_pitch(cls, x, y, pitch_points, detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL):
    if not detector_class_is_ball(cls, detector_profile) or not pitch_points:
        return True

    polygon = np.array(pitch_points, dtype=np.float32)
    return cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0


def build_tracking_row(
    *,
    frame_id,
    timestamp,
    entity_type,
    track_id,
    pitch_x,
    pitch_y,
    detection_conf,
    source_box,
    proposal_seed_center=None,
    proposal_crop_size=None,
    proposal_window_kind=None,
    proposal_seed_mode=None,
    proposal_inference_mode=None,
    pts=None,
    time_base=None,
):
    source_x1, source_y1, source_x2, source_y2 = source_box
    row = {
        "Frame_ID": frame_id,
        "Timestamp": timestamp,
        "Entity_Type": entity_type,
        "Track_ID": track_id,
        "X": pitch_x,
        "Y": pitch_y,
        "Conf": detection_conf,
        "Source_X1": round(float(source_x1), 2),
        "Source_Y1": round(float(source_y1), 2),
        "Source_X2": round(float(source_x2), 2),
        "Source_Y2": round(float(source_y2), 2),
    }
    if pts is not None and time_base is not None:
        row.update({"PTS": int(pts), "TimeBaseNum": int(time_base[0]), "TimeBaseDen": int(time_base[1])})
    if proposal_seed_center is not None:
        row["ProposalSeedX"] = round(float(proposal_seed_center[0]), 2)
        row["ProposalSeedY"] = round(float(proposal_seed_center[1]), 2)
    if proposal_crop_size is not None:
        row["ProposalCropWidth"] = round(float(proposal_crop_size[0]), 2)
        row["ProposalCropHeight"] = round(float(proposal_crop_size[1]), 2)
    if proposal_window_kind is not None:
        row["ProposalWindowKind"] = str(proposal_window_kind)
    if proposal_seed_mode is not None:
        row["ProposalSeedMode"] = str(proposal_seed_mode)
    if proposal_inference_mode is not None:
        row["ProposalInferenceMode"] = str(proposal_inference_mode)
    return row


def update_player_window(window, x1, y1, x2, y2):
    if window is None:
        return [float(x1), float(y1), float(x2), float(y2)]
    return [
        min(float(window[0]), float(x1)),
        min(float(window[1]), float(y1)),
        max(float(window[2]), float(x2)),
        max(float(window[3]), float(y2)),
    ]


def _row_source_box(row):
    source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if not all(key in row for key in source_keys):
        return None
    return (
        float(row["Source_X1"]),
        float(row["Source_Y1"]),
        float(row["Source_X2"]),
        float(row["Source_Y2"]),
    )


def _row_source_box_center(row):
    source_box = _row_source_box(row)
    if source_box is not None:
        x1, y1, x2, y2 = source_box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    if "X" in row and "Y" in row:
        return (float(row["X"]), float(row["Y"]))
    return None


def _window_center(window):
    left, top, right, bottom = [float(value) for value in window]
    return ((left + right) / 2.0, (top + bottom) / 2.0)


def _is_crop_window(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    try:
        [float(component) for component in value]
    except (TypeError, ValueError):
        return False
    return True


def _normalize_crop_windows_for_frame(value):
    if value is None:
        return []
    if _is_crop_window(value):
        left, top, right, bottom = value
        window = (
            int(round(float(left))),
            int(round(float(top))),
            int(round(float(right))),
            int(round(float(bottom))),
        )
        return [
            {
                "window": window,
                "proposalSeedCenter": _window_center(window),
                "proposalWindowKind": "player_ranked",
                "proposalSeedMode": "exact",
            }
        ]
    if isinstance(value, dict):
        window = value.get("window")
        if not _is_crop_window(window):
            return []
        left, top, right, bottom = window
        normalized_window = (
            int(round(float(left))),
            int(round(float(top))),
            int(round(float(right))),
            int(round(float(bottom))),
        )
        seed_center = value.get("proposalSeedCenter")
        if isinstance(seed_center, (list, tuple)) and len(seed_center) == 2:
            normalized_seed_center = (float(seed_center[0]), float(seed_center[1]))
        else:
            normalized_seed_center = _window_center(normalized_window)
        return [
            {
                "window": normalized_window,
                "proposalSeedCenter": normalized_seed_center,
                "proposalWindowKind": str(value.get("proposalWindowKind") or "player_ranked"),
                "proposalSeedMode": str(value.get("proposalSeedMode") or "exact"),
            }
        ]
    if isinstance(value, (list, tuple)):
        windows = []
        for item in value:
            windows.extend(_normalize_crop_windows_for_frame(item))
        return windows
    return []


def _dedupe_same_frame_recovered_rows(rows, *, max_source_distance_px=MAX_DUPLICATE_RECOVERED_SOURCE_DISTANCE_PX):
    if not rows:
        return []

    deduped_rows = []
    rows_by_frame = _group_rows_by_frame(rows)
    for frame_id in sorted(rows_by_frame):
        frame_rows = list(rows_by_frame[frame_id])
        ranked_rows = sorted(
            enumerate(frame_rows),
            key=lambda item: (
                float(item[1].get("Conf", 0.0)),
                -float((_row_source_box_center(item[1]) or (0.0, 0.0))[1]),
                -int(item[0]),
            ),
            reverse=True,
        )
        kept_centers = []
        for _original_index, row in ranked_rows:
            center = _row_source_box_center(row)
            if center is None:
                deduped_rows.append(row)
                continue
            if any(
                hypot(float(center[0]) - float(existing[0]), float(center[1]) - float(existing[1]))
                <= float(max_source_distance_px)
                for existing in kept_centers
            ):
                continue
            kept_centers.append(center)
            deduped_rows.append(row)
    return sorted(
        deduped_rows,
        key=lambda row: (
            int(row.get("Frame_ID", 0)),
            float((_row_source_box_center(row) or (0.0, 0.0))[0]),
            float((_row_source_box_center(row) or (0.0, 0.0))[1]),
        ),
    )


def _crop_window_is_non_edge(crop_window, frame_shape, edge_margin=BALL_EDGE_MARGIN):
    if crop_window is None:
        return False
    frame_height, frame_width = frame_shape[:2]
    left, top, right, bottom = [float(value) for value in crop_window]
    return (
        left > float(edge_margin)
        and top > float(edge_margin)
        and right < float(frame_width - edge_margin)
        and bottom < float(frame_height - edge_margin)
    )


def _player_proposal_crop_window(
    frame_shape,
    player_window,
    *,
    proposal_crop_width_ratio=0.35,
    proposal_crop_height_ratio=None,
    proposal_crop_padding_px=PLAYER_PROPOSAL_CROP_PADDING_PX,
):
    if player_window is None:
        return None

    frame_height, frame_width = frame_shape[:2]
    left, top, right, bottom = [float(value) for value in player_window]
    left -= float(proposal_crop_padding_px)
    top -= float(proposal_crop_padding_px)
    right += float(proposal_crop_padding_px)
    bottom += float(proposal_crop_padding_px)

    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0
    width = max(right - left, float(MIN_PLAYER_PROPOSAL_CROP_WIDTH))
    height = max(bottom - top, float(MIN_PLAYER_PROPOSAL_CROP_HEIGHT))

    max_width = float(frame_width) * float(proposal_crop_width_ratio)
    if max_width > 0:
        width = min(width, max_width)
    if proposal_crop_height_ratio is None:
        proposal_crop_height_ratio = proposal_crop_width_ratio
    max_height = float(frame_height) * float(proposal_crop_height_ratio)
    if max_height > 0:
        height = min(height, max_height)

    left = max(0.0, center_x - (width / 2.0))
    top = max(0.0, center_y - (height / 2.0))
    right = min(float(frame_width), center_x + (width / 2.0))
    bottom = min(float(frame_height), center_y + (height / 2.0))

    left = max(0.0, right - width)
    top = max(0.0, bottom - height)
    return (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )


def _point_in_crop_window(point, crop_window):
    if point is None or crop_window is None:
        return False
    point_x, point_y = float(point[0]), float(point[1])
    left, top, right, bottom = [float(value) for value in crop_window]
    return left <= point_x <= right and top <= point_y <= bottom


def _proposal_context_source_box(seed_center, source_box):
    if seed_center is None or source_box is None:
        return None
    seed_x, seed_y = float(seed_center[0]), float(seed_center[1])
    return (
        min(float(source_box[0]), seed_x),
        min(float(source_box[1]), seed_y),
        max(float(source_box[2]), seed_x),
        max(float(source_box[3]), seed_y),
    )


def _player_biased_seed_context_crop_window(
    frame_shape,
    source_box,
    seed_center,
    *,
    proposal_crop_width_ratio=0.35,
    proposal_crop_height_ratio=None,
    proposal_crop_padding_px=PLAYER_PROPOSAL_CROP_PADDING_PX,
):
    base_window = _player_proposal_crop_window(
        frame_shape,
        source_box,
        proposal_crop_width_ratio=proposal_crop_width_ratio,
        proposal_crop_height_ratio=proposal_crop_height_ratio,
        proposal_crop_padding_px=proposal_crop_padding_px,
    )
    if base_window is None or seed_center is None:
        return base_window, 0.0, False
    if _point_in_crop_window(seed_center, base_window):
        return base_window, 0.0, False

    frame_height, frame_width = frame_shape[:2]
    effective_width_ratio = max(float(proposal_crop_width_ratio), float(DIRECT_SEED_CONTEXT_MIN_CROP_RATIO))
    if proposal_crop_height_ratio is None:
        effective_height_ratio = effective_width_ratio
    else:
        effective_height_ratio = max(float(proposal_crop_height_ratio), float(DIRECT_SEED_CONTEXT_MIN_CROP_RATIO))

    base_left, base_top, base_right, base_bottom = [float(value) for value in base_window]
    left = base_left
    top = base_top
    right = base_right
    bottom = base_bottom
    seed_x = float(seed_center[0])
    seed_y = float(seed_center[1])

    if seed_x < left:
        left = min(left, seed_x)
    elif seed_x > right:
        right = max(right, seed_x)
    if seed_y < top:
        top = min(top, seed_y)
    elif seed_y > bottom:
        bottom = max(bottom, seed_y)

    max_width = float(frame_width) * effective_width_ratio
    max_height = float(frame_height) * effective_height_ratio
    if max_width > 0 and (right - left) > max_width:
        if seed_x < base_left:
            left = max(0.0, min(seed_x, float(frame_width) - max_width))
            right = left + max_width
        elif seed_x > base_right:
            right = min(float(frame_width), max(seed_x, max_width))
            left = right - max_width
    if max_height > 0 and (bottom - top) > max_height:
        if seed_y < base_top:
            top = max(0.0, min(seed_y, float(frame_height) - max_height))
            bottom = top + max_height
        elif seed_y > base_bottom:
            bottom = min(float(frame_height), max(seed_y, max_height))
            top = bottom - max_height

    if left < 0.0:
        right = min(float(frame_width), right - left)
        left = 0.0
    if right > float(frame_width):
        left = max(0.0, left - (right - float(frame_width)))
        right = float(frame_width)
    if top < 0.0:
        bottom = min(float(frame_height), bottom - top)
        top = 0.0
    if bottom > float(frame_height):
        top = max(0.0, top - (bottom - float(frame_height)))
        bottom = float(frame_height)

    expanded_window = (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )
    total_expansion = (
        max(0.0, base_left - left)
        + max(0.0, right - base_right)
        + max(0.0, base_top - top)
        + max(0.0, bottom - base_bottom)
    )
    return expanded_window, round(total_expansion, 2), expanded_window != base_window


def _touchline_acquisition_mode(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    if str(source_clip_id or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    mode = str(config.get("mode") or "")
    if mode not in {
        "touchline_acquisition_upgrade",
        "touchline_acquisition_reopen",
        "touchline_candidate_admission_reopen",
    }:
        return None
    return mode


def _touchline_acquisition_upgrade_enabled(*, source_clip_id=None, edge_share_repair_profile=None):
    return _touchline_acquisition_mode(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    ) == "touchline_acquisition_upgrade"


def _touchline_acquisition_reopen_enabled(*, source_clip_id=None, edge_share_repair_profile=None):
    return _touchline_acquisition_mode(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    ) in {"touchline_acquisition_reopen", "touchline_candidate_admission_reopen"}


def _touchline_candidate_admission_reopen_enabled(*, source_clip_id=None, edge_share_repair_profile=None):
    return _touchline_acquisition_mode(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    ) == "touchline_candidate_admission_reopen"


def _touchline_admission_widening_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    if str(source_clip_id or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    if not bool(config.get("admissionWideningEnabled")):
        return None
    return {
        "requirePlayerSupport": bool(config.get("admissionWideningRequirePlayerSupport", True)),
        "maxProjectedEdgeShare": float(config.get("admissionWideningMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)),
    }


def _touchline_baseline_guided_rescue_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    if str(source_clip_id or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    if not bool(config.get("baselineGuidedRescueEnabled")):
        return None
    return {
        "maxProjectedEdgeShare": float(
            config.get("baselineGuidedRescueMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
    }


def _touchline_continuity_bridge_recovery_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    if str(source_clip_id or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    if not bool(config.get("continuityBridgeRecoveryEnabled")):
        return None
    return {
        "maxGapFrames": int(config.get("continuityBridgeRecoveryMaxGapFrames", 20)),
        "maxProjectedEdgeShare": float(
            config.get("continuityBridgeRecoveryMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
        "requireEndpointContinuity": bool(
            config.get("continuityBridgeRecoveryRequireEndpointContinuity", True)
        ),
    }


def _touchline_acceptance_support_gating_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    if str(source_clip_id or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    if not bool(config.get("acceptanceSupportGatingEnabled")):
        return None
    return {
        "requirePlayerSupport": bool(config.get("acceptanceSupportGatingRequirePlayerSupport", True)),
        "requireSupportImprovement": bool(
            config.get("acceptanceSupportGatingRequireSupportImprovement", True)
        ),
        "maxProjectedEdgeShare": float(
            config.get("acceptanceSupportGatingMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
        "requireRealDetectedCandidateRows": bool(
            config.get("acceptanceSupportGatingRequireRealDetectedCandidateRows", True)
        ),
    }


def _touchline_proposal_selection_admission_fix_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("proposalSelectionAdmissionFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("proposalSelectionAdmissionFixEnabled")):
        return None
    return {
        "approachFamily": str(
            config.get("proposalSelectionAdmissionFixApproachFamily") or "truth_seed_guided_selection"
        ),
        "truthSeedPath": str(config.get("proposalSelectionAdmissionFixTruthSeedPath") or ""),
        "maxProjectedEdgeShare": float(
            config.get("proposalSelectionAdmissionFixMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
        "requireRealDetectedCandidateRows": bool(
            config.get("proposalSelectionAdmissionFixRequireRealDetectedCandidateRows", True)
        ),
        "preserveRepeatedAnchorGuard": bool(
            config.get("proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard", True)
        ),
        "preserveContinuityGuard": bool(
            config.get("proposalSelectionAdmissionFixPreserveContinuityGuard", True)
        ),
        "maxSeedPitchDistance": float(
            config.get("proposalSelectionAdmissionFixMaxSeedPitchDistance", 8.0)
        ),
    }


def _touchline_support_viability_admission_fix_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("supportViabilityAdmissionFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("supportViabilityAdmissionFixEnabled")):
        return None
    return {
        "approachFamily": str(
            config.get("supportViabilityAdmissionFixApproachFamily") or "support_evidence_lift"
        ),
        "truthSeedPath": str(config.get("supportViabilityAdmissionFixTruthSeedPath") or ""),
        "maxProjectedEdgeShare": float(
            config.get("supportViabilityAdmissionFixMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
        "requireRealDetectedCandidateRows": bool(
            config.get("supportViabilityAdmissionFixRequireRealDetectedCandidateRows", True)
        ),
        "preserveRepeatedAnchorGuard": bool(
            config.get("supportViabilityAdmissionFixPreserveRepeatedAnchorGuard", True)
        ),
        "preserveContinuityGuard": bool(
            config.get("supportViabilityAdmissionFixPreserveContinuityGuard", True)
        ),
    }


def _touchline_proposal_crop_geometry_fix_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("proposalCropGeometryFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("proposalCropGeometryFixEnabled")):
        return None
    return {
        "truthSeedPath": str(config.get("proposalCropGeometryFixTruthSeedPath") or ""),
        "useTruthSeedRowsAsProposalAnchors": bool(
            config.get("proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors", True)
        ),
        "maxWindowsPerFrame": int(config.get("proposalCropGeometryFixMaxWindowsPerFrame", 4)),
        "minSeedWindowFrames": int(config.get("proposalCropGeometryFixMinSeedWindowFrames", 78)),
        "retryScales": [
            int(scale)
            for scale in config.get("proposalCropGeometryFixRetryScales", [1600, 960, 1920])
        ],
        "cropWidthRatio": float(config.get("proposalCropGeometryFixCropWidthRatio", 0.35)),
        "cropHeightRatio": float(
            config.get(
                "proposalCropGeometryFixCropHeightRatio",
                config.get("proposalCropGeometryFixCropWidthRatio", 0.35),
            )
        ),
        "cropPaddingPx": int(
            config.get("proposalCropGeometryFixCropPaddingPx", PLAYER_PROPOSAL_CROP_PADDING_PX)
        ),
    }


def _touchline_reviewed_positive_proposal_generation_fix_config(
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("reviewedPositiveProposalGenerationFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("reviewedPositiveProposalGenerationFixEnabled")):
        return None
    return {
        "anchorSeedPath": str(config.get("reviewedPositiveAnchorSeedPath") or ""),
        "maxWindowsPerFrame": int(config.get("reviewedPositiveProposalGenerationFixMaxWindowsPerFrame", 3)),
        "retryScales": [
            int(scale)
            for scale in config.get("reviewedPositiveProposalGenerationFixRetryScales", [1600, 960, 1920])
        ],
        "contextRatios": [
            float(ratio)
            for ratio in config.get("reviewedPositiveProposalGenerationFixContextRatios", [])
        ],
        "minCropSizePx": int(config.get("reviewedPositiveProposalGenerationFixMinCropSizePx", 64)),
        "useAuditBestAttempts": bool(
            config.get("reviewedPositiveProposalGenerationFixUseAuditBestAttempts", False)
        ),
        "auditMatrixPath": str(
            config.get("reviewedPositiveProposalGenerationFixAuditMatrixPath") or ""
        ),
        "excludeFrameIds": {
            int(frame_id)
            for frame_id in config.get("reviewedPositiveProposalGenerationFixExcludeFrameIds", [])
        },
        "requireRealDetectedCandidateRows": bool(
            config.get("reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows", True)
        ),
        "cropWidthRatio": float(config.get("reviewedPositiveProposalGenerationFixCropWidthRatio", 0.35)),
        "cropHeightRatio": float(config.get("reviewedPositiveProposalGenerationFixCropHeightRatio", 0.35)),
        "cropPaddingPx": int(config.get("reviewedPositiveProposalGenerationFixCropPaddingPx", PLAYER_PROPOSAL_CROP_PADDING_PX)),
    }


def _touchline_selection_segment_viability_fix_config(*, source_clip_id=None, edge_share_repair_profile=None):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("selectionSegmentViabilityFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("selectionSegmentViabilityFixEnabled")):
        return None
    return {
        "minSegmentFrames": int(config.get("selectionSegmentViabilityFixMinSegmentFrames", 3)),
        "maxProjectedEdgeShare": float(
            config.get("selectionSegmentViabilityFixMaxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
        ),
        "requireRealDetectedCandidateRows": bool(
            config.get("selectionSegmentViabilityFixRequireRealDetectedCandidateRows", True)
        ),
        "requireProposalLineage": bool(
            config.get("selectionSegmentViabilityFixRequireProposalLineage", True)
        ),
        "preserveRepeatedAnchorGuard": bool(
            config.get("selectionSegmentViabilityFixPreserveRepeatedAnchorGuard", True)
        ),
    }


def _touchline_reviewed_positive_selected_segment_fix_config(
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("reviewedPositiveSelectedSegmentFixTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("reviewedPositiveSelectedSegmentFixEnabled")):
        return None
    return {
        "requiredProposalWindowKindPrefix": str(
            config.get("reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix")
            or "reviewed_positive_"
        ),
        "minSegmentFrames": int(config.get("reviewedPositiveSelectedSegmentFixMinSegmentFrames", 5)),
        "frameIds": {
            int(frame_id)
            for frame_id in config.get("reviewedPositiveSelectedSegmentFixFrameIds", [])
        },
        "maxProjectedEdgeShare": float(
            config.get(
                "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare",
                MAX_VIABLE_EDGE_FRAME_SHARE,
            )
        ),
        "requireRealDetectedCandidateRows": bool(
            config.get("reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows", True)
        ),
        "preserveRepeatedAnchorGuard": bool(
            config.get("reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard", True)
        ),
        "preserveContinuityGuard": bool(
            config.get("reviewedPositiveSelectedSegmentFixPreserveContinuityGuard", True)
        ),
        "ignoreEdgeShareGate": bool(
            config.get("reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate", False)
        ),
    }


def _touchline_reviewed_positive_acceptance_profile_config(
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
):
    config = _source_edge_share_repair_config(edge_share_repair_profile)
    if not isinstance(config, dict):
        return None
    target_source_clip_id = str(
        config.get("reviewedPositiveAcceptanceProfileTargetSourceClipId")
        or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
    )
    if str(source_clip_id or "") != str(Path(target_source_clip_id).name):
        return None
    if not bool(config.get("reviewedPositiveAcceptanceProfileEnabled")):
        return None
    return {
        "requiredProposalWindowKindPrefix": str(
            config.get("reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix")
            or "reviewed_positive_"
        ),
        "minSelectedFrames": int(config.get("reviewedPositiveAcceptanceProfileMinSelectedFrames", 5)),
        "requireRealDetectedRows": bool(
            config.get("reviewedPositiveAcceptanceProfileRequireRealDetectedRows", True)
        ),
        "preserveRepeatedAnchorGuard": bool(
            config.get("reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard", True)
        ),
        "preserveContinuityGuard": bool(
            config.get("reviewedPositiveAcceptanceProfilePreserveContinuityGuard", True)
        ),
    }


def _pitch_coordinates_are_edge(x, y):
    return (
        float(x) <= BALL_EDGE_MARGIN
        or float(x) >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or float(y) <= BALL_EDGE_MARGIN
        or float(y) >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )


def _proposal_selection_truth_seed_payload(seed_path):
    if not isinstance(seed_path, str) or not seed_path.strip():
        return {"seedRowsByFrame": {}, "bootstrapWindowIdsByFrame": {}}
    path = Path(seed_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"seedRowsByFrame": {}, "bootstrapWindowIdsByFrame": {}}
    if not isinstance(payload, dict):
        return {"seedRowsByFrame": {}, "bootstrapWindowIdsByFrame": {}}
    seed_rows_by_frame = {}
    bootstrap_window_ids_by_frame = {}
    seed_rows = payload.get("acceptedBallSeedRows")
    if not isinstance(seed_rows, list):
        seed_rows = payload.get("acceptedSeedRows")
    if not isinstance(seed_rows, list):
        seed_rows = []
    for seed_entry in seed_rows:
        if not isinstance(seed_entry, dict):
            continue
        row = seed_entry.get("row")
        if not isinstance(row, dict):
            continue
        try:
            frame_id = int(seed_entry.get("frameId", row.get("Frame_ID")))
            x = float(row["X"])
            y = float(row["Y"])
        except (KeyError, TypeError, ValueError):
            continue
        seed_rows_by_frame[frame_id] = {**row, "Frame_ID": frame_id, "X": x, "Y": y}
        bootstrap_window_ids_by_frame[frame_id] = str(
            seed_entry.get("bootstrapWindowId") or seed_entry.get("windowId") or ""
        )
    return {
        "seedRowsByFrame": seed_rows_by_frame,
        "bootstrapWindowIdsByFrame": bootstrap_window_ids_by_frame,
    }


def _reviewed_positive_anchor_seed_payload(seed_path):
    if not isinstance(seed_path, str) or not seed_path.strip():
        return {"anchorRowsByFrame": {}}
    path = Path(seed_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"anchorRowsByFrame": {}}
    if not isinstance(payload, dict):
        return {"anchorRowsByFrame": {}}
    rows = payload.get("reviewedPositiveAnchorRows")
    if not isinstance(rows, list):
        rows = []
    anchors_by_frame = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            frame_id = int(row.get("frameIndex", row.get("frameId")))
        except (TypeError, ValueError):
            continue
        center = None
        source_center = row.get("sourceCenter")
        if isinstance(source_center, dict):
            try:
                center = (float(source_center["x"]), float(source_center["y"]))
            except (KeyError, TypeError, ValueError):
                center = None
        if center is None:
            bbox = row.get("reviewedBBox")
            if isinstance(bbox, dict):
                try:
                    center = (
                        (float(bbox["x1"]) + float(bbox["x2"])) / 2.0,
                        (float(bbox["y1"]) + float(bbox["y2"])) / 2.0,
                    )
                except (KeyError, TypeError, ValueError):
                    center = None
        if center is None:
            continue
        anchors_by_frame[frame_id] = {
            **row,
            "Frame_ID": frame_id,
            "ProposalSeedX": float(center[0]),
            "ProposalSeedY": float(center[1]),
        }
    return {"anchorRowsByFrame": anchors_by_frame}


def _reviewed_positive_bbox(row):
    if not isinstance(row, dict):
        return None
    bbox = row.get("reviewedBBox")
    if not isinstance(bbox, dict):
        return None
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _reviewed_positive_audit_context_crop_window(
    frame_shape,
    reviewed_bbox,
    *,
    context_ratio=1.0,
    min_crop_size_px=64,
):
    if frame_shape is None or reviewed_bbox is None:
        return None
    frame_height, frame_width = frame_shape[:2]
    x1, y1, x2, y2 = [float(value) for value in reviewed_bbox]
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    width = max((x2 - x1) * float(context_ratio), float(min_crop_size_px))
    height = max((y2 - y1) * float(context_ratio), float(min_crop_size_px))
    left = max(0.0, center_x - width / 2.0)
    top = max(0.0, center_y - height / 2.0)
    right = min(float(frame_width), center_x + width / 2.0)
    bottom = min(float(frame_height), center_y + height / 2.0)
    left = max(0.0, right - width)
    top = max(0.0, bottom - height)
    return (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )


def _reviewed_positive_audit_context_kind(context_ratio):
    numeric = float(context_ratio)
    if numeric.is_integer():
        suffix = str(int(numeric))
    else:
        suffix = str(numeric).replace(".", "_")
    return f"reviewed_positive_audit_context_{suffix}"


def _reviewed_positive_audit_best_context_kind(context_ratio, imgsz):
    numeric = float(context_ratio)
    if numeric.is_integer():
        ratio_suffix = str(int(numeric))
    else:
        ratio_suffix = str(numeric).replace(".", "_")
    return f"reviewed_positive_audit_best_context_{ratio_suffix}_scale_{int(imgsz)}"


def _reviewed_positive_audit_best_attempts_by_frame(audit_matrix_path):
    if not isinstance(audit_matrix_path, str) or not audit_matrix_path.strip():
        return {}
    path = Path(audit_matrix_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("reviewedPositiveCropRows")
    if not isinstance(rows, list):
        return {}
    best_by_frame = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        best_attempt = row.get("bestAttempt")
        if not isinstance(best_attempt, dict) or not best_attempt:
            continue
        try:
            frame_id = int(row.get("frameIndex"))
            context_ratio = float(best_attempt["contextRatio"])
            imgsz = int(best_attempt["imgsz"])
            crop_window = tuple(int(round(float(value))) for value in best_attempt["cropWindow"])
        except (KeyError, TypeError, ValueError):
            continue
        if len(crop_window) != 4:
            continue
        best_by_frame[frame_id] = {
            "contextRatio": context_ratio,
            "imgsz": imgsz,
            "cropWindow": crop_window,
        }
    return best_by_frame


def _truth_seed_source_center(row):
    if not isinstance(row, dict):
        return None
    try:
        if all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
            return (
                (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0,
                (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0,
            )
        if "ProposalSeedX" in row and "ProposalSeedY" in row:
            return float(row["ProposalSeedX"]), float(row["ProposalSeedY"])
    except (TypeError, ValueError):
        return None
    return None


def _load_baseline_guided_rescue_reference(reference_path=None, *, source_clip_id=None, edge_share_repair_profile=None):
    if _touchline_baseline_guided_rescue_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    ) is None:
        return None
    if not isinstance(reference_path, str) or not reference_path.strip():
        return None
    path = Path(reference_path).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("sourceClipId") or "") != str(Path(SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP).name):
        return None
    return payload


def _baseline_guided_rescue_anchor_payloads(reference_payload):
    if not isinstance(reference_payload, dict):
        return []
    anchors = reference_payload.get("anchors")
    if not isinstance(anchors, list):
        return []
    normalized = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        try:
            frame_id = int(anchor["frameId"])
            source_center_x = float(anchor["sourceCenterX"])
            source_center_y = float(anchor["sourceCenterY"])
            pitch_x = float(anchor.get("pitchX", 0.0))
            pitch_y = float(anchor.get("pitchY", 0.0))
        except (KeyError, TypeError, ValueError):
            continue
        normalized.append(
            {
                "frameId": frame_id,
                "sourceCenter": (source_center_x, source_center_y),
                "pitch": (pitch_x, pitch_y),
            }
        )
    return normalized


def _touchline_acquisition_enabled(*, source_clip_id=None, edge_share_repair_profile=None):
    return _touchline_acquisition_mode(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    ) is not None


def _touchline_adjacent_seed_side(frame_shape, seed_center):
    if seed_center is None:
        return None
    frame_height, frame_width = frame_shape[:2]
    seed_x, seed_y = float(seed_center[0]), float(seed_center[1])
    edge_distances = {
        "left": seed_x,
        "right": max(float(frame_width) - seed_x, 0.0),
        "top": seed_y,
        "bottom": max(float(frame_height) - seed_y, 0.0),
    }
    nearest_side, nearest_distance = min(
        edge_distances.items(),
        key=lambda item: (float(item[1]), item[0]),
    )
    frame_side_length = float(frame_width) if nearest_side in {"left", "right"} else float(frame_height)
    if nearest_distance > frame_side_length * float(TOUCHLINE_ESCAPE_EDGE_PROXIMITY_RATIO):
        return None
    return nearest_side


def _touchline_escape_crop_window(
    frame_shape,
    seed_center,
    *,
    proposal_crop_width_ratio=0.35,
    proposal_crop_height_ratio=None,
    proposal_crop_padding_px=PLAYER_PROPOSAL_CROP_PADDING_PX,
):
    if seed_center is None:
        return None
    base_window = _player_proposal_crop_window(
        frame_shape,
        (seed_center[0], seed_center[1], seed_center[0], seed_center[1]),
        proposal_crop_width_ratio=proposal_crop_width_ratio,
        proposal_crop_height_ratio=proposal_crop_height_ratio,
        proposal_crop_padding_px=proposal_crop_padding_px,
    )
    if base_window is None:
        return None
    side = _touchline_adjacent_seed_side(frame_shape, seed_center)
    if side is None:
        return None

    frame_height, frame_width = frame_shape[:2]
    seed_x, seed_y = float(seed_center[0]), float(seed_center[1])
    left, top, right, bottom = [float(value) for value in base_window]
    width = max(right - left, 1.0)
    height = max(bottom - top, 1.0)
    seed_margin_x = width * float(TOUCHLINE_ESCAPE_SEED_MARGIN_RATIO)
    seed_margin_y = height * float(TOUCHLINE_ESCAPE_SEED_MARGIN_RATIO)

    if side == "left":
        left = min(max(0.0, seed_x - seed_margin_x), max(float(frame_width) - width, 0.0))
        right = min(float(frame_width), left + width)
    elif side == "right":
        right = max(min(float(frame_width), seed_x + seed_margin_x), width)
        left = max(0.0, right - width)
    elif side == "top":
        top = min(max(0.0, seed_y - seed_margin_y), max(float(frame_height) - height, 0.0))
        bottom = min(float(frame_height), top + height)
    else:
        bottom = max(min(float(frame_height), seed_y + seed_margin_y), height)
        top = max(0.0, bottom - height)

    escaped_window = (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )
    if escaped_window == base_window or not _point_in_crop_window(seed_center, escaped_window):
        return None
    return escaped_window


def _touchline_inboard_context_crop_window(
    frame_shape,
    seed_center,
    *,
    proposal_crop_width_ratio=0.35,
    proposal_crop_height_ratio=None,
    proposal_crop_padding_px=PLAYER_PROPOSAL_CROP_PADDING_PX,
):
    if seed_center is None:
        return None
    base_window = _player_proposal_crop_window(
        frame_shape,
        (seed_center[0], seed_center[1], seed_center[0], seed_center[1]),
        proposal_crop_width_ratio=proposal_crop_width_ratio,
        proposal_crop_height_ratio=proposal_crop_height_ratio,
        proposal_crop_padding_px=proposal_crop_padding_px,
    )
    if base_window is None:
        return None
    side = _touchline_adjacent_seed_side(frame_shape, seed_center)
    if side is None:
        return None
    escape_window = _touchline_escape_crop_window(
        frame_shape,
        seed_center,
        proposal_crop_width_ratio=proposal_crop_width_ratio,
        proposal_crop_height_ratio=proposal_crop_height_ratio,
        proposal_crop_padding_px=proposal_crop_padding_px,
    )
    reference_window = escape_window if escape_window is not None else base_window

    frame_height, frame_width = frame_shape[:2]
    left, top, right, bottom = [float(value) for value in reference_window]
    reference_center_x = (left + right) / 2.0
    reference_center_y = (top + bottom) / 2.0
    width = max((right - left) * 1.4, 1.0)
    height = max((bottom - top) * 1.4, 1.0)
    seed_x, seed_y = float(seed_center[0]), float(seed_center[1])
    center_x = reference_center_x
    center_y = reference_center_y

    if side == "left":
        center_x = min(
            float(frame_width) - (width / 2.0),
            max(reference_center_x + (width * 0.18), seed_x + (width * 0.55)),
        )
    elif side == "right":
        center_x = max(
            width / 2.0,
            min(reference_center_x - (width * 0.18), seed_x - (width * 0.55)),
        )
    elif side == "top":
        center_y = min(
            float(frame_height) - (height / 2.0),
            max(reference_center_y + (height * 0.18), seed_y + (height * 0.55)),
        )
    else:
        center_y = max(
            height / 2.0,
            min(reference_center_y - (height * 0.18), seed_y - (height * 0.55)),
        )

    left = max(0.0, center_x - (width / 2.0))
    top = max(0.0, center_y - (height / 2.0))
    right = min(float(frame_width), center_x + (width / 2.0))
    bottom = min(float(frame_height), center_y + (height / 2.0))
    if seed_x < left:
        right = min(float(frame_width), right + (left - seed_x))
        left = seed_x
    elif seed_x > right:
        left = max(0.0, left - (seed_x - right))
        right = seed_x
    if seed_y < top:
        bottom = min(float(frame_height), bottom + (top - seed_y))
        top = seed_y
    elif seed_y > bottom:
        top = max(0.0, top - (seed_y - bottom))
        bottom = seed_y
    inboard_window = (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )
    if inboard_window == reference_window or not _point_in_crop_window(seed_center, inboard_window):
        return None
    return inboard_window


def _proposal_seed_to_source_box_rank(seed_center, source_box, original_index):
    if seed_center is None or source_box is None:
        return (float("inf"), float("inf"), int(original_index))
    box_distance = _distance_from_point_to_window(seed_center[0], seed_center[1], source_box)
    center_x = (float(source_box[0]) + float(source_box[2])) / 2.0
    center_y = (float(source_box[1]) + float(source_box[3])) / 2.0
    center_distance = hypot(float(seed_center[0]) - center_x, float(seed_center[1]) - center_y)
    return (box_distance, center_distance, int(original_index))


def _proposal_window_kind_priority(kind):
    normalized_kind = str(kind or "")
    if normalized_kind == REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND:
        return 5
    if normalized_kind == TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND:
        return 4
    if normalized_kind == TOUCHLINE_ESCAPE_WINDOW_KIND:
        return 3
    if normalized_kind == "direct_seed_context":
        return 2
    if normalized_kind in {"direct_seed_tight", "direct_seed"}:
        return 1
    if normalized_kind == "player_ranked":
        return 0
    return -1


def _proposal_window_kind_is_direct_seed(kind):
    normalized_kind = str(kind or "")
    return normalized_kind in {
        "direct_seed",
        "direct_seed_tight",
        "direct_seed_context",
        REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND,
    } or normalized_kind.startswith("reviewed_positive_audit_context_") or normalized_kind.startswith(
        "reviewed_positive_audit_best_context_"
    )


def _proposal_window_kind_is_anchor_seeded(kind):
    return _proposal_window_kind_is_direct_seed(kind) or str(kind or "") in {
        TOUCHLINE_ESCAPE_WINDOW_KIND,
        TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND,
    }


def _proposal_seed_distance_for_row(row):
    source_center = _row_source_box_center(row)
    proposal_seed_center = _proposal_seed_center_for_row(row)
    if source_center is None or proposal_seed_center is None:
        return float("inf")
    return hypot(
        float(source_center[0]) - float(proposal_seed_center[0]),
        float(source_center[1]) - float(proposal_seed_center[1]),
    )


def _player_proposal_window_rank(
    row,
    *,
    original_index,
    proposal_window,
    seed_center=None,
    support_window=None,
    frame_shape=None,
):
    proposal_center = _window_center(proposal_window)
    if seed_center is not None:
        seed_distance = hypot(
            proposal_center[0] - float(seed_center[0]),
            proposal_center[1] - float(seed_center[1]),
        )
        anchored_limit = max(
            float(proposal_window[2]) - float(proposal_window[0]),
            float(proposal_window[3]) - float(proposal_window[1]),
        ) / 2.0
        anchored = 1 if seed_distance <= anchored_limit else 0
    else:
        seed_distance = float("inf")
        anchored = 0

    if support_window is not None:
        support_center = _window_center(support_window)
        support_distance = hypot(
            proposal_center[0] - support_center[0],
            proposal_center[1] - support_center[1],
        )
        supported_limit = max(
            float(proposal_window[2]) - float(proposal_window[0]),
            float(proposal_window[3]) - float(proposal_window[1]),
        ) / 2.0
        supported = 1 if support_distance <= supported_limit else 0
    else:
        supported = 0

    non_edge_score = 1 if frame_shape is None or _crop_window_is_non_edge(proposal_window, frame_shape) else 0
    confidence_proxy = float(row.get("Conf", 0.0))
    return (
        -seed_distance,
        anchored,
        supported,
        non_edge_score,
        confidence_proxy,
        -int(original_index),
    )


def _player_proposal_seed_center_and_mode(
    frame_id,
    observed_source_anchors,
    *,
    frame_interval,
):
    if not observed_source_anchors:
        return None, None, "none"

    normalized_anchors = {
        int(anchor_frame_id): (float(anchor_center[0]), float(anchor_center[1]))
        for anchor_frame_id, anchor_center in observed_source_anchors.items()
    }
    if not normalized_anchors:
        return None, None, "none"

    frame_id = int(frame_id)
    max_single_gap = max(int(frame_interval), 1) * 2
    max_interpolated_gap = max(int(frame_interval), 1) * 6

    if frame_id in normalized_anchors:
        center_x, center_y = normalized_anchors[frame_id]
        return center_x, center_y, "exact"

    anchor_frame_ids = sorted(normalized_anchors)
    previous_frame_id = max(
        (anchor_frame_id for anchor_frame_id in anchor_frame_ids if anchor_frame_id < frame_id),
        default=None,
    )
    next_frame_id = min(
        (anchor_frame_id for anchor_frame_id in anchor_frame_ids if anchor_frame_id > frame_id),
        default=None,
    )

    if previous_frame_id is not None and next_frame_id is not None:
        total_gap = next_frame_id - previous_frame_id
        if total_gap <= max_interpolated_gap:
            previous_center_x, previous_center_y = normalized_anchors[previous_frame_id]
            next_center_x, next_center_y = normalized_anchors[next_frame_id]
            ratio = (frame_id - previous_frame_id) / float(total_gap)
            center_x = previous_center_x + ((next_center_x - previous_center_x) * ratio)
            center_y = previous_center_y + ((next_center_y - previous_center_y) * ratio)
            return center_x, center_y, "interpolated"

    nearby_anchor_frame_ids = []
    if previous_frame_id is not None and (frame_id - previous_frame_id) <= max_single_gap:
        nearby_anchor_frame_ids.append(previous_frame_id)
    if next_frame_id is not None and (next_frame_id - frame_id) <= max_single_gap:
        nearby_anchor_frame_ids.append(next_frame_id)

    if len(nearby_anchor_frame_ids) == 1:
        center_x, center_y = normalized_anchors[nearby_anchor_frame_ids[0]]
        return center_x, center_y, "single"

    return None, None, "none"


def _build_player_proposal_crop_windows_by_frame(
    frame_shape,
    *,
    frame_interval,
    player_rows,
    observed_source_anchors=None,
    baseline_guided_rescue_reference=None,
    frame_count=None,
    max_proposals_per_frame=DEFAULT_PLAYER_PROPOSAL_MAX_WINDOWS_PER_FRAME,
    proposal_crop_width_ratio=0.35,
    proposal_crop_height_ratio=None,
    proposal_crop_padding_px=PLAYER_PROPOSAL_CROP_PADDING_PX,
    source_clip_id=None,
    edge_share_repair_profile=None,
    proposal_selection_truth_seed_path=None,
    reviewed_positive_anchor_seed_path=None,
):
    observed_source_anchors = observed_source_anchors or {}
    crop_geometry_config = _touchline_proposal_crop_geometry_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if isinstance(crop_geometry_config, dict) and proposal_selection_truth_seed_path:
        crop_geometry_config["truthSeedPath"] = str(proposal_selection_truth_seed_path)
    crop_geometry_seed_payload = _proposal_selection_truth_seed_payload(
        str(crop_geometry_config.get("truthSeedPath") or "")
        if isinstance(crop_geometry_config, dict)
        else ""
    )
    crop_geometry_seed_rows_by_frame = (
        dict(crop_geometry_seed_payload.get("seedRowsByFrame") or {})
        if isinstance(crop_geometry_seed_payload, dict)
        else {}
    )
    reviewed_positive_config = _touchline_reviewed_positive_proposal_generation_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if isinstance(reviewed_positive_config, dict) and reviewed_positive_anchor_seed_path:
        reviewed_positive_config["anchorSeedPath"] = str(reviewed_positive_anchor_seed_path)
    reviewed_positive_anchor_seed_payload = _reviewed_positive_anchor_seed_payload(
        str(reviewed_positive_config.get("anchorSeedPath") or "")
        if isinstance(reviewed_positive_config, dict)
        else ""
    )
    reviewed_positive_anchor_rows_by_frame = (
        dict(reviewed_positive_anchor_seed_payload.get("anchorRowsByFrame") or {})
        if isinstance(reviewed_positive_anchor_seed_payload, dict)
        else {}
    )
    crop_geometry_anchor_frame_ids = set()
    crop_geometry_diagnostics = {
        "proposalCropGeometryFixTruthSeedFrames": len(crop_geometry_seed_rows_by_frame)
        if isinstance(crop_geometry_config, dict)
        else 0,
        "proposalCropGeometryFixUsedFrames": 0,
        "proposalCropGeometryFixSkippedExistingFrames": 0,
        "proposalCropGeometryFixSkippedMissingSourceFrames": 0,
        "proposalCropGeometryFixDuplicateWindowFrames": 0,
        "proposalCropGeometryFixMinSeedWindowFrames": int(
            crop_geometry_config.get("minSeedWindowFrames", 0)
        )
        if isinstance(crop_geometry_config, dict)
        else 0,
        "proposalCropGeometryFixCropWidthRatio": float(
            crop_geometry_config.get("cropWidthRatio", proposal_crop_width_ratio)
        )
        if isinstance(crop_geometry_config, dict)
        else 0.0,
        "proposalCropGeometryFixCropHeightRatio": float(
            crop_geometry_config.get("cropHeightRatio", proposal_crop_height_ratio or proposal_crop_width_ratio)
        )
        if isinstance(crop_geometry_config, dict)
        else 0.0,
        "proposalCropGeometryFixCropPaddingPx": int(
            crop_geometry_config.get("cropPaddingPx", proposal_crop_padding_px)
        )
        if isinstance(crop_geometry_config, dict)
        else 0,
    }
    reviewed_positive_anchor_frame_ids = set()
    reviewed_positive_diagnostics = {
        "reviewedPositiveAnchorSeedFrames": len(reviewed_positive_anchor_rows_by_frame)
        if isinstance(reviewed_positive_config, dict)
        else 0,
        "reviewedPositiveAnchorUsedFrames": 0,
        "reviewedPositiveAnchorWindowFrames": 0,
        "reviewedPositiveAuditContextWindowFrames": 0,
        "reviewedPositiveAuditBestAttemptWindowFrames": 0,
        "reviewedPositiveAnchorDuplicateWindowFrames": 0,
        "reviewedPositiveAnchorSkippedMissingSourceFrames": 0,
        "reviewedPositiveAnchorSkippedExistingFrames": 0,
        "reviewedPositiveAnchorSkippedNonTargetFrames": 0,
        "reviewedPositiveAnchorSkippedExcludedFrames": 0,
        "reviewedPositiveAnchorMaxWindowsPerFrame": int(
            reviewed_positive_config.get("maxWindowsPerFrame", 0)
        )
        if isinstance(reviewed_positive_config, dict)
        else 0,
    }
    if isinstance(crop_geometry_config, dict):
        max_proposals_per_frame = max(
            int(max_proposals_per_frame),
            int(crop_geometry_config.get("maxWindowsPerFrame", max_proposals_per_frame)),
        )
        proposal_crop_width_ratio = float(
            crop_geometry_config.get("cropWidthRatio", proposal_crop_width_ratio)
        )
        proposal_crop_height_ratio = float(
            crop_geometry_config.get(
                "cropHeightRatio",
                proposal_crop_height_ratio if proposal_crop_height_ratio is not None else proposal_crop_width_ratio,
            )
        )
        proposal_crop_padding_px = int(
            crop_geometry_config.get("cropPaddingPx", proposal_crop_padding_px)
        )
    if isinstance(reviewed_positive_config, dict):
        max_proposals_per_frame = max(
            int(max_proposals_per_frame),
            int(reviewed_positive_config.get("maxWindowsPerFrame", max_proposals_per_frame)),
        )
        proposal_crop_width_ratio = float(
            reviewed_positive_config.get("cropWidthRatio", proposal_crop_width_ratio)
        )
        proposal_crop_height_ratio = float(
            reviewed_positive_config.get(
                "cropHeightRatio",
                proposal_crop_height_ratio if proposal_crop_height_ratio is not None else proposal_crop_width_ratio,
            )
        )
        proposal_crop_padding_px = int(
            reviewed_positive_config.get("cropPaddingPx", proposal_crop_padding_px)
        )
    reviewed_positive_audit_best_attempts_by_frame = (
        _reviewed_positive_audit_best_attempts_by_frame(
            reviewed_positive_config.get("auditMatrixPath")
        )
        if isinstance(reviewed_positive_config, dict)
        and reviewed_positive_config.get("useAuditBestAttempts")
        else {}
    )
    baseline_guided_rescue_config = _touchline_baseline_guided_rescue_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    baseline_guided_anchor_payloads = (
        _baseline_guided_rescue_anchor_payloads(baseline_guided_rescue_reference)
        if baseline_guided_rescue_config is not None
        else []
    )
    baseline_guided_anchor_frame_ids = set()
    baseline_guided_diagnostics = {
        "proposalBaselineGuidedRescueAvailableFrames": len(baseline_guided_anchor_payloads),
        "proposalBaselineGuidedRescueUsedFrames": 0,
        "proposalBaselineGuidedRescueSkippedExistingFrames": 0,
        "proposalBaselineGuidedRescueSkippedEdgeFrames": 0,
        "proposalBaselineGuidedRescueSelectedFrames": 0,
    }

    if (
        not player_rows
        and not observed_source_anchors
        and not baseline_guided_anchor_payloads
        and not crop_geometry_seed_rows_by_frame
        and not reviewed_positive_anchor_rows_by_frame
    ):
        return {}, {
            "proposalCandidateFrames": 0,
            "proposalWindowCount": 0,
            "proposalFramesWithAnchorSeed": 0,
            "proposalFramesWithoutAnchorSeed": 0,
            "proposalExactSeedFrames": 0,
            "proposalInterpolatedSeedFrames": 0,
            "proposalSingleSeedFrames": 0,
            "proposalUnseededFrames": 0,
            "proposalDirectSeedWindowFrames": 0,
            "proposalDirectSeedTightWindowFrames": 0,
            "proposalDirectSeedContextWindowFrames": 0,
            "proposalDirectSeedContextEligibleFrames": 0,
            "proposalDirectSeedContextDuplicateFrames": 0,
            "proposalDirectSeedContextMeanSeedToBoxDistance": 0.0,
            "proposalDirectSeedContextExpandedFrames": 0,
            "proposalDirectSeedContextMeanExpansionPx": 0.0,
            "proposalTouchlineEscapeEligibleFrames": 0,
            "proposalTouchlineEscapeWindowFrames": 0,
            "proposalPlayerRankedWindowFrames": 0,
            "reviewedPositiveAnchorSeedFrames": 0,
            "reviewedPositiveAnchorUsedFrames": 0,
            "reviewedPositiveAnchorWindowFrames": 0,
            "reviewedPositiveAuditContextWindowFrames": 0,
            "reviewedPositiveAuditBestAttemptWindowFrames": 0,
            "reviewedPositiveAnchorDuplicateWindowFrames": 0,
            "reviewedPositiveAnchorSkippedMissingSourceFrames": 0,
            "reviewedPositiveAnchorSkippedExistingFrames": 0,
            "reviewedPositiveAnchorSkippedNonTargetFrames": 0,
            "reviewedPositiveAnchorSkippedExcludedFrames": 0,
            "reviewedPositiveAnchorMaxWindowsPerFrame": 0,
            "proposalMeanWindowWidth": 0.0,
            **crop_geometry_diagnostics,
            **reviewed_positive_diagnostics,
            **baseline_guided_diagnostics,
        }

    rows_by_frame = _group_rows_by_frame(
        [row for row in player_rows if row.get("Entity_Type") != "ball"]
    )
    observed_source_anchors = {
        int(frame_id): (float(center[0]), float(center[1]))
        for frame_id, center in observed_source_anchors.items()
    }
    non_crop_source_anchors = dict(observed_source_anchors)
    if (
        isinstance(crop_geometry_config, dict)
        and bool(crop_geometry_config.get("useTruthSeedRowsAsProposalAnchors", True))
    ):
        for frame_id, seed_row in sorted(crop_geometry_seed_rows_by_frame.items()):
            seed_center = _truth_seed_source_center(seed_row)
            if seed_center is None:
                crop_geometry_diagnostics["proposalCropGeometryFixSkippedMissingSourceFrames"] += 1
                continue
            frame_id = int(frame_id)
            if frame_id in observed_source_anchors:
                crop_geometry_diagnostics["proposalCropGeometryFixSkippedExistingFrames"] += 1
            observed_source_anchors[frame_id] = seed_center
            crop_geometry_anchor_frame_ids.add(frame_id)
            crop_geometry_diagnostics["proposalCropGeometryFixUsedFrames"] += 1
    if isinstance(reviewed_positive_config, dict):
        excluded_reviewed_positive_frames = {
            int(frame_id)
            for frame_id in reviewed_positive_config.get("excludeFrameIds", set())
        }
        for frame_id, anchor_row in sorted(reviewed_positive_anchor_rows_by_frame.items()):
            try:
                seed_center = (
                    float(anchor_row["ProposalSeedX"]),
                    float(anchor_row["ProposalSeedY"]),
                )
            except (KeyError, TypeError, ValueError):
                reviewed_positive_diagnostics["reviewedPositiveAnchorSkippedMissingSourceFrames"] += 1
                continue
            frame_id = int(frame_id)
            if frame_id in excluded_reviewed_positive_frames:
                reviewed_positive_diagnostics["reviewedPositiveAnchorSkippedExcludedFrames"] += 1
                continue
            if frame_id in observed_source_anchors:
                reviewed_positive_diagnostics["reviewedPositiveAnchorSkippedExistingFrames"] += 1
            observed_source_anchors[frame_id] = seed_center
            reviewed_positive_anchor_frame_ids.add(frame_id)
            reviewed_positive_diagnostics["reviewedPositiveAnchorUsedFrames"] += 1
    for anchor in baseline_guided_anchor_payloads:
        frame_id = int(anchor["frameId"])
        if frame_id in observed_source_anchors:
            baseline_guided_diagnostics["proposalBaselineGuidedRescueSkippedExistingFrames"] += 1
            continue
        pitch_x, pitch_y = anchor["pitch"]
        if _pitch_coordinates_are_edge(pitch_x, pitch_y):
            baseline_guided_diagnostics["proposalBaselineGuidedRescueSkippedEdgeFrames"] += 1
            continue
        observed_source_anchors[frame_id] = anchor["sourceCenter"]
        non_crop_source_anchors[frame_id] = anchor["sourceCenter"]
        baseline_guided_anchor_frame_ids.add(frame_id)
        baseline_guided_diagnostics["proposalBaselineGuidedRescueUsedFrames"] += 1
    if frame_count is not None and int(frame_count) > 0:
        max_frame_id = int(frame_count)
    else:
        max_frame_id = max(
            int(row["Frame_ID"])
            for frame_rows in rows_by_frame.values()
            for row in frame_rows
        ) + int(frame_interval)
    sampled_frame_ids = list(range(0, max_frame_id, max(int(frame_interval), 1)))

    crop_windows_by_frame = {}
    crop_widths = []
    frames_with_anchor_seed = 0
    frames_without_anchor_seed = 0
    exact_seed_frames = 0
    interpolated_seed_frames = 0
    single_seed_frames = 0
    unseeded_frames = 0
    direct_seed_window_frames = 0
    direct_seed_tight_window_frames = 0
    direct_seed_context_window_frames = 0
    direct_seed_context_eligible_frames = 0
    direct_seed_context_duplicate_frames = 0
    direct_seed_context_box_distances = []
    direct_seed_context_expanded_frames = 0
    direct_seed_context_expansion_totals = []
    touchline_escape_eligible_frames = 0
    touchline_escape_window_frames = 0
    player_ranked_window_frames = 0

    for sampled_frame_id in sampled_frame_ids:
        frame_rows = rows_by_frame.get(sampled_frame_id, [])
        if sampled_frame_id in crop_geometry_anchor_frame_ids:
            seed_center_x, seed_center_y = observed_source_anchors[sampled_frame_id]
            seed_mode = "truth_seed"
        elif sampled_frame_id in reviewed_positive_anchor_frame_ids:
            seed_center_x, seed_center_y = observed_source_anchors[sampled_frame_id]
            seed_mode = REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND
        else:
            seed_center_x, seed_center_y, seed_mode = _player_proposal_seed_center_and_mode(
                sampled_frame_id,
                non_crop_source_anchors,
                frame_interval=frame_interval,
            )
            if seed_mode == "exact" and sampled_frame_id in baseline_guided_anchor_frame_ids:
                seed_mode = BASELINE_GUIDED_RESCUE_SEED_MODE
        if seed_mode == "none":
            unseeded_frames += 1
        seed_center = None if seed_mode == "none" else (seed_center_x, seed_center_y)
        if seed_mode == "exact":
            exact_seed_frames += 1
        elif seed_mode == BASELINE_GUIDED_RESCUE_SEED_MODE:
            exact_seed_frames += 1
        elif seed_mode == "truth_seed":
            exact_seed_frames += 1
        elif seed_mode == REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND:
            exact_seed_frames += 1
        elif seed_mode == "interpolated":
            interpolated_seed_frames += 1
        elif seed_mode == "single":
            single_seed_frames += 1

        support_window = None
        candidate_rows = []
        direct_seed_window = _player_proposal_crop_window(
            frame_shape,
            (seed_center_x, seed_center_y, seed_center_x, seed_center_y),
            proposal_crop_width_ratio=proposal_crop_width_ratio,
            proposal_crop_height_ratio=proposal_crop_height_ratio,
            proposal_crop_padding_px=proposal_crop_padding_px,
        ) if seed_center is not None else None
        for original_index, row in enumerate(frame_rows):
            source_box = _row_source_box(row)
            if source_box is None:
                continue
            support_window = update_player_window(
                support_window,
                source_box[0],
                source_box[1],
                source_box[2],
                source_box[3],
            )
            proposal_window = _player_proposal_crop_window(
                frame_shape,
                source_box,
                proposal_crop_width_ratio=proposal_crop_width_ratio,
                proposal_crop_height_ratio=proposal_crop_height_ratio,
                proposal_crop_padding_px=proposal_crop_padding_px,
            )
            if proposal_window is None:
                continue
            candidate_rows.append(
                {
                    "row": row,
                    "proposal_window": proposal_window,
                    "original_index": original_index,
                }
            )

        selected_specs = []
        selected_windows = set()
        frame_has_player_ranked_window = False
        frame_has_direct_seed_tight_window = False
        frame_has_direct_seed_context_window = False
        frame_has_touchline_escape_window = False

        def _append_selected_spec(
            window,
            kind,
            *,
            selected_windows=selected_windows,
            sampled_frame_id=sampled_frame_id,
            selected_specs=selected_specs,
            seed_mode=seed_mode,
            seed_center=seed_center,
            seed_center_x=seed_center_x,
            seed_center_y=seed_center_y,
            **extra_fields,
        ):
            nonlocal frame_has_player_ranked_window
            nonlocal frame_has_direct_seed_tight_window
            nonlocal frame_has_direct_seed_context_window
            nonlocal frame_has_touchline_escape_window
            nonlocal direct_seed_window_frames
            nonlocal direct_seed_tight_window_frames
            nonlocal direct_seed_context_window_frames
            nonlocal touchline_escape_window_frames
            nonlocal player_ranked_window_frames
            if window is None:
                return False
            normalized_window = tuple(int(round(float(value))) for value in window)
            if normalized_window in selected_windows:
                if sampled_frame_id in crop_geometry_anchor_frame_ids and kind == "direct_seed_tight":
                    crop_geometry_diagnostics["proposalCropGeometryFixDuplicateWindowFrames"] += 1
                if sampled_frame_id in reviewed_positive_anchor_frame_ids and kind == REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND:
                    reviewed_positive_diagnostics["reviewedPositiveAnchorDuplicateWindowFrames"] += 1
                return False
            selected_windows.add(normalized_window)
            spec = {
                "window": normalized_window,
                "proposalWindowKind": kind,
                "proposalSeedMode": seed_mode,
            }
            if seed_center is not None:
                spec["proposalSeedCenter"] = (float(seed_center_x), float(seed_center_y))
            spec.update(extra_fields)
            if sampled_frame_id in reviewed_positive_anchor_frame_ids:
                spec["reviewedPositiveAnchorFrame"] = True
                spec["reviewedPositiveAnchorFrameIndex"] = int(sampled_frame_id)
            selected_specs.append(spec)
            if kind == "player_ranked" and not frame_has_player_ranked_window:
                frame_has_player_ranked_window = True
                player_ranked_window_frames += 1
            elif kind == "direct_seed_tight" and not frame_has_direct_seed_tight_window:
                frame_has_direct_seed_tight_window = True
                direct_seed_window_frames += 1
                direct_seed_tight_window_frames += 1
            elif kind == "direct_seed_context" and not frame_has_direct_seed_context_window:
                frame_has_direct_seed_context_window = True
                direct_seed_window_frames += 1
                direct_seed_context_window_frames += 1
            elif kind == TOUCHLINE_ESCAPE_WINDOW_KIND and not frame_has_touchline_escape_window:
                frame_has_touchline_escape_window = True
                touchline_escape_window_frames += 1
            elif kind == REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND:
                reviewed_positive_diagnostics["reviewedPositiveAnchorWindowFrames"] += 1
            elif str(kind).startswith("reviewed_positive_audit_context_"):
                reviewed_positive_diagnostics["reviewedPositiveAnchorWindowFrames"] += 1
                reviewed_positive_diagnostics["reviewedPositiveAuditContextWindowFrames"] += 1
            elif str(kind).startswith("reviewed_positive_audit_best_context_"):
                reviewed_positive_diagnostics["reviewedPositiveAnchorWindowFrames"] += 1
                reviewed_positive_diagnostics["reviewedPositiveAuditBestAttemptWindowFrames"] += 1
            return True

        if sampled_frame_id in reviewed_positive_anchor_frame_ids:
            context_ratios = (
                list(reviewed_positive_config.get("contextRatios") or [])
                if isinstance(reviewed_positive_config, dict)
                else []
            )
            anchor_row = reviewed_positive_anchor_rows_by_frame.get(sampled_frame_id, {})
            reviewed_bbox = _reviewed_positive_bbox(anchor_row)
            if context_ratios and reviewed_bbox is not None:
                best_attempt = reviewed_positive_audit_best_attempts_by_frame.get(sampled_frame_id)
                if isinstance(best_attempt, dict):
                    best_window = best_attempt.get("cropWindow")
                    if _is_crop_window(best_window):
                        left, top, right, bottom = [
                            int(round(float(value))) for value in best_window
                        ]
                        if frame_shape is not None:
                            frame_height, frame_width = frame_shape[:2]
                            left = max(0, min(int(frame_width), left))
                            top = max(0, min(int(frame_height), top))
                            right = max(0, min(int(frame_width), right))
                            bottom = max(0, min(int(frame_height), bottom))
                        if right > left and bottom > top:
                            _append_selected_spec(
                                (left, top, right, bottom),
                                _reviewed_positive_audit_best_context_kind(
                                    float(best_attempt.get("contextRatio", 0.0)),
                                    int(best_attempt.get("imgsz", 0)),
                                ),
                                reviewedPositiveAuditBestAttemptWindow=True,
                                reviewedPositiveAuditBestAttemptContextRatio=float(
                                    best_attempt.get("contextRatio", 0.0)
                                ),
                                reviewedPositiveAuditBestAttemptImgSz=int(
                                    best_attempt.get("imgsz", 0)
                                ),
                                reviewedPositiveSourceBBox=tuple(
                                    float(value) for value in reviewed_bbox
                                ),
                            )
                for context_ratio in context_ratios:
                    context_window = _reviewed_positive_audit_context_crop_window(
                        frame_shape,
                        reviewed_bbox,
                        context_ratio=float(context_ratio),
                        min_crop_size_px=int(
                            reviewed_positive_config.get("minCropSizePx", 64)
                            if isinstance(reviewed_positive_config, dict)
                            else 64
                        ),
                    )
                    _append_selected_spec(
                        context_window,
                        _reviewed_positive_audit_context_kind(context_ratio),
                        reviewedPositiveAuditContextWindow=True,
                        reviewedPositiveAuditContextRatio=float(context_ratio),
                        reviewedPositiveSourceBBox=tuple(float(value) for value in reviewed_bbox),
                    )
            else:
                _append_selected_spec(direct_seed_window, REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND)
        else:
            _append_selected_spec(direct_seed_window, "direct_seed_tight")

        direct_seed_context_window = None
        if direct_seed_window is not None and candidate_rows:
            eligible_context_candidates = []
            for candidate in candidate_rows:
                source_box = _row_source_box(candidate["row"])
                if source_box is None:
                    continue
                if _distance_from_point_to_window(seed_center_x, seed_center_y, source_box) > float(BALL_RECOVERY_PADDING_PX):
                    continue
                eligible_context_candidates.append(
                    (
                        *_proposal_seed_to_source_box_rank(
                            (seed_center_x, seed_center_y),
                            source_box,
                            candidate["original_index"],
                        ),
                        source_box,
                        candidate["proposal_window"],
                    )
                )
            if eligible_context_candidates:
                (
                    nearest_box_distance,
                    _center_distance,
                    _original_index,
                    nearest_source_box,
                    _nearest_player_ranked_window,
                ) = min(
                    eligible_context_candidates
                )
                direct_seed_context_eligible_frames += 1
                direct_seed_context_box_distances.append(float(nearest_box_distance))
                (
                    direct_seed_context_window,
                    direct_seed_context_expansion_px,
                    direct_seed_context_expanded,
                ) = _player_biased_seed_context_crop_window(
                    frame_shape,
                    nearest_source_box,
                    (seed_center_x, seed_center_y),
                    proposal_crop_width_ratio=proposal_crop_width_ratio,
                    proposal_crop_height_ratio=proposal_crop_height_ratio,
                    proposal_crop_padding_px=proposal_crop_padding_px,
                )
                if direct_seed_context_expanded:
                    direct_seed_context_expanded_frames += 1
                    direct_seed_context_expansion_totals.append(float(direct_seed_context_expansion_px))
                if not _append_selected_spec(direct_seed_context_window, "direct_seed_context"):
                    direct_seed_context_duplicate_frames += 1

        if seed_center is not None and _touchline_acquisition_enabled(
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        ):
            touchline_escape_window = _touchline_escape_crop_window(
                frame_shape,
                (seed_center_x, seed_center_y),
                proposal_crop_width_ratio=proposal_crop_width_ratio,
                proposal_crop_height_ratio=proposal_crop_height_ratio,
                proposal_crop_padding_px=proposal_crop_padding_px,
            )
            if touchline_escape_window is not None:
                touchline_escape_eligible_frames += 1
                _append_selected_spec(touchline_escape_window, TOUCHLINE_ESCAPE_WINDOW_KIND)
            if _touchline_acquisition_reopen_enabled(
                source_clip_id=source_clip_id,
                edge_share_repair_profile=edge_share_repair_profile,
            ):
                inboard_context_window = _touchline_inboard_context_crop_window(
                    frame_shape,
                    (seed_center_x, seed_center_y),
                    proposal_crop_width_ratio=proposal_crop_width_ratio,
                    proposal_crop_height_ratio=proposal_crop_height_ratio,
                    proposal_crop_padding_px=proposal_crop_padding_px,
                )
                _append_selected_spec(inboard_context_window, TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND)

        if candidate_rows:
            ranked_candidates = sorted(
                candidate_rows,
                key=lambda item: _player_proposal_window_rank(
                    item["row"],
                    original_index=item["original_index"],
                    proposal_window=item["proposal_window"],
                    seed_center=seed_center,
                    support_window=support_window,
                    frame_shape=frame_shape,
                ),
                reverse=True,
            )
            if seed_center is None:
                # ponytail: at most three players per cold-start frame by default; rotate
                # tracks for coverage, raise the proposal cap if acquisition latency matters.
                ranked_candidates.sort(key=lambda item: int(item["row"].get("Track_ID", -1)))
                offset = (sampled_frame_id // max(int(frame_interval), 1) * max(int(max_proposals_per_frame), 1)) % len(ranked_candidates)
                ranked_candidates = ranked_candidates[offset:] + ranked_candidates[:offset]
            remaining_slots = max(int(max_proposals_per_frame), 1) - len(selected_specs)
            if remaining_slots > 0:
                for candidate in ranked_candidates:
                    if len(selected_specs) >= max(int(max_proposals_per_frame), 1):
                        break
                    _append_selected_spec(candidate["proposal_window"], "player_ranked")

        if not selected_specs:
            continue

        crop_windows_by_frame[sampled_frame_id] = selected_specs
        crop_widths.extend(float(spec["window"][2]) - float(spec["window"][0]) for spec in selected_specs)
        if seed_mode in {"exact", BASELINE_GUIDED_RESCUE_SEED_MODE, "truth_seed"}:
            frames_with_anchor_seed += 1
        elif seed_mode == REVIEWED_POSITIVE_ANCHOR_WINDOW_KIND:
            frames_with_anchor_seed += 1
        else:
            frames_without_anchor_seed += 1

    if not crop_windows_by_frame:
        return crop_windows_by_frame, {
            "proposalCandidateFrames": 0,
            "proposalWindowCount": 0,
            "proposalFramesWithAnchorSeed": frames_with_anchor_seed,
            "proposalFramesWithoutAnchorSeed": frames_without_anchor_seed,
            "proposalExactSeedFrames": exact_seed_frames,
            "proposalInterpolatedSeedFrames": interpolated_seed_frames,
            "proposalSingleSeedFrames": single_seed_frames,
            "proposalUnseededFrames": unseeded_frames,
            "proposalDirectSeedWindowFrames": direct_seed_window_frames,
            "proposalDirectSeedTightWindowFrames": direct_seed_tight_window_frames,
            "proposalDirectSeedContextWindowFrames": direct_seed_context_window_frames,
            "proposalDirectSeedContextEligibleFrames": direct_seed_context_eligible_frames,
            "proposalDirectSeedContextDuplicateFrames": direct_seed_context_duplicate_frames,
            "proposalDirectSeedContextMeanSeedToBoxDistance": round(
                sum(direct_seed_context_box_distances) / len(direct_seed_context_box_distances),
                2,
            )
            if direct_seed_context_box_distances
            else 0.0,
            "proposalDirectSeedContextExpandedFrames": direct_seed_context_expanded_frames,
            "proposalDirectSeedContextMeanExpansionPx": round(
                sum(direct_seed_context_expansion_totals) / len(direct_seed_context_expansion_totals),
                2,
            )
            if direct_seed_context_expansion_totals
            else 0.0,
            "proposalTouchlineEscapeEligibleFrames": touchline_escape_eligible_frames,
            "proposalTouchlineEscapeWindowFrames": touchline_escape_window_frames,
            "proposalPlayerRankedWindowFrames": player_ranked_window_frames,
            "proposalMeanWindowWidth": 0.0,
            **crop_geometry_diagnostics,
            **reviewed_positive_diagnostics,
            **baseline_guided_diagnostics,
        }

    return crop_windows_by_frame, {
        "proposalCandidateFrames": len(crop_windows_by_frame),
        "proposalWindowCount": sum(len(windows) for windows in crop_windows_by_frame.values()),
        "proposalFramesWithAnchorSeed": frames_with_anchor_seed,
        "proposalFramesWithoutAnchorSeed": frames_without_anchor_seed,
        "proposalExactSeedFrames": exact_seed_frames,
        "proposalInterpolatedSeedFrames": interpolated_seed_frames,
        "proposalSingleSeedFrames": single_seed_frames,
        "proposalUnseededFrames": unseeded_frames,
        "proposalDirectSeedWindowFrames": direct_seed_window_frames,
        "proposalDirectSeedTightWindowFrames": direct_seed_tight_window_frames,
        "proposalDirectSeedContextWindowFrames": direct_seed_context_window_frames,
        "proposalDirectSeedContextEligibleFrames": direct_seed_context_eligible_frames,
        "proposalDirectSeedContextDuplicateFrames": direct_seed_context_duplicate_frames,
        "proposalDirectSeedContextMeanSeedToBoxDistance": round(
            sum(direct_seed_context_box_distances) / len(direct_seed_context_box_distances),
            2,
        )
        if direct_seed_context_box_distances
        else 0.0,
        "proposalDirectSeedContextExpandedFrames": direct_seed_context_expanded_frames,
        "proposalDirectSeedContextMeanExpansionPx": round(
            sum(direct_seed_context_expansion_totals) / len(direct_seed_context_expansion_totals),
            2,
        )
        if direct_seed_context_expansion_totals
        else 0.0,
        "proposalTouchlineEscapeEligibleFrames": touchline_escape_eligible_frames,
        "proposalTouchlineEscapeWindowFrames": touchline_escape_window_frames,
        "proposalPlayerRankedWindowFrames": player_ranked_window_frames,
        "proposalMeanWindowWidth": round(sum(crop_widths) / len(crop_widths), 2) if crop_widths else 0.0,
        **crop_geometry_diagnostics,
        **reviewed_positive_diagnostics,
        **baseline_guided_diagnostics,
    }


def ball_recovery_crop_window(
    frame_shape,
    player_window,
    max_crop_width_ratio=0.0,
):
    if player_window is None:
        return None

    frame_height, frame_width = frame_shape[:2]
    left, top, right, bottom = [float(value) for value in player_window]
    left -= BALL_RECOVERY_PADDING_PX
    top -= BALL_RECOVERY_PADDING_PX
    right += BALL_RECOVERY_PADDING_PX
    bottom += BALL_RECOVERY_PADDING_PX

    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0
    width = max(right - left, MIN_BALL_RECOVERY_CROP_WIDTH)
    height = max(bottom - top, MIN_BALL_RECOVERY_CROP_HEIGHT)
    if max_crop_width_ratio > 0:
        width = min(width, float(frame_width) * float(max_crop_width_ratio))

    left = max(0.0, center_x - (width / 2.0))
    top = max(0.0, center_y - (height / 2.0))
    right = min(float(frame_width), center_x + (width / 2.0))
    bottom = min(float(frame_height), center_y + (height / 2.0))

    left = max(0.0, right - width)
    top = max(0.0, bottom - height)

    return (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )


def summarize_ball_recovery_crop_windows(frame_shape, player_windows):
    if not player_windows:
        return {
            "framesWithWindows": 0,
            "meanCropWidth": 0.0,
            "meanCropHeight": 0.0,
            "meanFrameCoverageShare": 0.0,
        }

    frame_height, frame_width = frame_shape[:2]
    crop_widths = []
    crop_heights = []
    coverage_shares = []
    full_frame_area = max(float(frame_width * frame_height), 1.0)

    for player_window in player_windows.values():
        crop_window = ball_recovery_crop_window(frame_shape, player_window)
        if crop_window is None:
            continue
        left, top, right, bottom = crop_window
        crop_width = max(float(right - left), 0.0)
        crop_height = max(float(bottom - top), 0.0)
        crop_widths.append(crop_width)
        crop_heights.append(crop_height)
        coverage_shares.append((crop_width * crop_height) / full_frame_area)

    if not crop_widths:
        return {
            "framesWithWindows": 0,
            "meanCropWidth": 0.0,
            "meanCropHeight": 0.0,
            "meanFrameCoverageShare": 0.0,
        }

    return {
        "framesWithWindows": len(crop_widths),
        "meanCropWidth": round(sum(crop_widths) / len(crop_widths), 2),
        "meanCropHeight": round(sum(crop_heights) / len(crop_heights), 2),
        "meanFrameCoverageShare": round(sum(coverage_shares) / len(coverage_shares), 3),
    }


def _best_ball_rows_by_frame(rows):
    frame_best_rows = {}
    for row in rows:
        if row.get("Entity_Type") != "ball":
            continue
        frame_id = int(row["Frame_ID"])
        current_best = frame_best_rows.get(frame_id)
        if current_best is None or float(row["Conf"]) > float(current_best["Conf"]):
            frame_best_rows[frame_id] = row
    return [frame_best_rows[frame_id] for frame_id in sorted(frame_best_rows)]


def _ball_row_is_edge(row):
    x = float(row["X"])
    y = float(row["Y"])
    return (
        x <= BALL_EDGE_MARGIN
        or x >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or y <= BALL_EDGE_MARGIN
        or y >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )


def _group_rows_by_frame(rows):
    rows_by_frame = {}
    for row in rows:
        frame_id = int(row["Frame_ID"])
        rows_by_frame.setdefault(frame_id, []).append(row)
    return rows_by_frame


def _nearest_player_distance_for_ball_row(ball_row, player_rows_by_frame):
    player_rows = player_rows_by_frame.get(int(ball_row["Frame_ID"]), [])
    if not player_rows:
        return None

    if "X" in ball_row and "Y" in ball_row:
        ball_center = (float(ball_row["X"]), float(ball_row["Y"]))
    else:
        ball_center = _row_source_box_center(ball_row)
    if ball_center is None:
        return None

    player_distances = []
    for player_row in player_rows:
        if "X" in player_row and "Y" in player_row:
            player_center = (float(player_row["X"]), float(player_row["Y"]))
        else:
            player_center = _row_source_box_center(player_row)
        if player_center is None:
            continue
        player_distances.append(
            hypot(
                float(player_center[0]) - float(ball_center[0]),
                float(player_center[1]) - float(ball_center[1]),
            )
        )
    if not player_distances:
        return None
    return min(player_distances)


def _ball_row_is_player_supported(ball_row, player_rows_by_frame):
    nearest_player_distance = _nearest_player_distance_for_ball_row(ball_row, player_rows_by_frame)
    return nearest_player_distance is not None and nearest_player_distance <= MAX_OWNER_DISTANCE


def _summarize_ball_row_support(rows, player_rows):
    player_rows_by_frame = _group_rows_by_frame(
        [row for row in player_rows if row.get("Entity_Type") != "ball"]
    )
    supported_frames = 0
    unsupported_edge_frames = 0

    for row in _best_ball_rows_by_frame(rows):
        is_supported = _ball_row_is_player_supported(row, player_rows_by_frame)
        if is_supported:
            supported_frames += 1
        elif _ball_row_is_edge(row):
            unsupported_edge_frames += 1

    return {
        "supportedFrames": supported_frames,
        "unsupportedEdgeFrames": unsupported_edge_frames,
    }


def _build_ball_support_diagnostics(observed_rows, accepted_rows, player_rows=None):
    observed_support = _summarize_ball_row_support(observed_rows, player_rows or [])
    accepted_support = _summarize_ball_row_support(accepted_rows, player_rows or [])
    accepted_frame_count = len(_best_ball_rows_by_frame(accepted_rows or []))
    supported_accepted_ball_ratio = (
        round(accepted_support["supportedFrames"] / accepted_frame_count, 3) if accepted_frame_count else 0.0
    )
    return {
        "supportedObservedBallFrames": observed_support["supportedFrames"],
        "supportedAcceptedBallFrames": accepted_support["supportedFrames"],
        "supportedAcceptedBallRatio": supported_accepted_ball_ratio,
        "unsupportedAcceptedEdgeFrames": accepted_support["unsupportedEdgeFrames"],
    }


def _build_match_state_evidence(ball_truth_layers, player_rows=None):
    observed_rows = _best_ball_rows_by_frame(
        ball_truth_layers.get("observedBall", {}).get("rows", [])
        if isinstance(ball_truth_layers, dict)
        else []
    )
    inferred_rows = _best_ball_rows_by_frame(
        ball_truth_layers.get("inferredBall", {}).get("rows", [])
        if isinstance(ball_truth_layers, dict)
        else []
    )
    accepted_rows = _best_ball_rows_by_frame(
        ball_truth_layers.get("acceptedBall", {}).get("rows", [])
        if isinstance(ball_truth_layers, dict)
        else []
    )
    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    observed_frames = {int(row["Frame_ID"]) for row in observed_rows}
    inferred_frames = {int(row["Frame_ID"]) for row in inferred_rows}
    accepted_by_frame = {int(row["Frame_ID"]): row for row in accepted_rows}
    candidate_frame_ids = sorted(
        {
            *accepted_by_frame.keys(),
            *[int(frame_id) for frame_id in player_rows_by_frame],
        }
    )

    evidence_frames = []
    for frame_id in candidate_frame_ids:
        accepted_row = accepted_by_frame.get(frame_id)
        accepted_source = "none"
        if frame_id in observed_frames:
            accepted_source = "observed"
        elif frame_id in inferred_frames:
            accepted_source = "inferred"
        player_supported = accepted_row is not None and _ball_row_is_player_supported(
            accepted_row,
            player_rows_by_frame,
        )
        edge_heavy = accepted_row is not None and _ball_row_is_edge(accepted_row)
        reason_codes = ["accepted_ball" if accepted_row is not None else "no_accepted_ball"]
        if accepted_source == "observed":
            reason_codes.append("observed_ball")
        elif accepted_source == "inferred":
            reason_codes.append("inferred_ball")
        if player_supported:
            reason_codes.append("player_supported")
        if edge_heavy:
            reason_codes.append("edge_heavy")
        evidence_frames.append(
            {
                "frameId": frame_id,
                "hasAcceptedBall": accepted_row is not None,
                "acceptedSource": accepted_source,
                "playerSupported": bool(player_supported),
                "edgeHeavy": bool(edge_heavy),
                "reasonCodes": reason_codes,
            }
        )

    return {"frames": evidence_frames}


def _select_best_observed_ball_rows(tracking_rows, probe_rows, player_rows=None):
    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    candidates_by_frame = {}
    for source_name, rows in (("tracking", tracking_rows), ("probe", probe_rows)):
        for row in rows:
            if row.get("Entity_Type") != "ball":
                continue
            frame_id = int(row["Frame_ID"])
            candidates_by_frame.setdefault(frame_id, []).append((source_name, row))

    selected_rows = []
    for frame_id in sorted(candidates_by_frame):
        frame_candidates = candidates_by_frame[frame_id]

        def _candidate_rank(candidate):
            source_name, row = candidate
            is_supported = _ball_row_is_player_supported(row, player_rows_by_frame)
            is_non_edge = not _ball_row_is_edge(row)
            source_priority = 1 if source_name == "tracking" else 0
            return (
                is_supported,
                is_non_edge,
                float(row.get("Conf", 0.0)),
                source_priority,
            )

        selected_rows.append(max(frame_candidates, key=_candidate_rank)[1])

    return selected_rows


def _filter_probe_observed_ball_rows(probe_rows, *, player_rows=None, sample_interval=1):
    collapsed_probe_rows = _select_best_observed_ball_rows([], probe_rows, player_rows=player_rows)
    if not collapsed_probe_rows:
        return {
            "rawRows": [],
            "filteredRows": [],
            "rawFrameCount": 0,
            "filteredFrameCount": 0,
            "suppressedFrameCount": 0,
            "anchoredFrameCount": 0,
            "bridgeFrameCount": 0,
        }

    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    sample_interval = max(int(sample_interval), 1)
    filtered_rows = []
    anchored_frame_count = 0
    bridge_frame_count = 0

    for segment in split_ball_rows_into_segments(collapsed_probe_rows, max_frame_gap=sample_interval):
        segment_meta = []
        for row in segment:
            is_supported = _ball_row_is_player_supported(row, player_rows_by_frame)
            is_non_edge = not _ball_row_is_edge(row)
            segment_meta.append(
                {
                    "row": row,
                    "isAnchored": is_supported or is_non_edge,
                }
            )

        for index, meta in enumerate(segment_meta):
            row = meta["row"]
            if meta["isAnchored"]:
                filtered_rows.append(row)
                anchored_frame_count += 1
                continue

            previous_meta = segment_meta[index - 1] if index > 0 else None
            next_meta = segment_meta[index + 1] if index + 1 < len(segment_meta) else None
            if previous_meta is None or next_meta is None:
                continue
            if not previous_meta["isAnchored"] or not next_meta["isAnchored"]:
                continue

            previous_row = previous_meta["row"]
            next_row = next_meta["row"]
            previous_frame_gap = int(row["Frame_ID"]) - int(previous_row["Frame_ID"])
            next_frame_gap = int(next_row["Frame_ID"]) - int(row["Frame_ID"])
            if previous_frame_gap > sample_interval or next_frame_gap > sample_interval:
                continue

            previous_distance = hypot(
                float(row["X"]) - float(previous_row["X"]),
                float(row["Y"]) - float(previous_row["Y"]),
            )
            next_distance = hypot(
                float(next_row["X"]) - float(row["X"]),
                float(next_row["Y"]) - float(row["Y"]),
            )
            if previous_distance > MAX_COHERENT_BALL_STEP_DISTANCE or next_distance > MAX_COHERENT_BALL_STEP_DISTANCE:
                continue

            filtered_rows.append(row)
            bridge_frame_count += 1

    raw_frame_count = len({int(row["Frame_ID"]) for row in collapsed_probe_rows})
    filtered_frame_count = len({int(row["Frame_ID"]) for row in filtered_rows})
    return {
        "rawRows": collapsed_probe_rows,
        "filteredRows": filtered_rows,
        "rawFrameCount": raw_frame_count,
        "filteredFrameCount": filtered_frame_count,
        "suppressedFrameCount": max(raw_frame_count - filtered_frame_count, 0),
        "anchoredFrameCount": anchored_frame_count,
        "bridgeFrameCount": bridge_frame_count,
    }


def _summarize_recovered_ball_segment_anchor_diagnostics(segment_rows, player_rows_by_frame=None, max_frame_gap=5):
    ordered_rows = _best_ball_rows_by_frame(segment_rows)
    if not ordered_rows:
        return {
            "startFrame": None,
            "endFrame": None,
            "frameCount": 0,
            "supportedFrameCount": 0,
            "anchoredFrameCount": 0,
            "bridgeFrameCount": 0,
            "unsupportedEdgeFrameShare": 0.0,
            "anchoredPathLength": 0.0,
        }

    player_rows_by_frame = player_rows_by_frame or {}
    supported_frame_count = 0
    anchored_rows = []
    bridge_frame_count = 0
    unsupported_edge_frame_count = 0

    for index, row in enumerate(ordered_rows):
        supported = _ball_row_is_player_supported(row, player_rows_by_frame)
        non_edge = not _ball_row_is_edge(row)
        anchored = supported or non_edge
        if supported:
            supported_frame_count += 1
        if anchored:
            anchored_rows.append(row)
            continue
        if not _ball_row_is_edge(row):
            continue

        unsupported_edge_frame_count += 1
        previous_row = ordered_rows[index - 1] if index > 0 else None
        next_row = ordered_rows[index + 1] if index + 1 < len(ordered_rows) else None
        if previous_row is None or next_row is None:
            continue

        previous_anchored = _ball_row_is_player_supported(previous_row, player_rows_by_frame) or not _ball_row_is_edge(previous_row)
        next_anchored = _ball_row_is_player_supported(next_row, player_rows_by_frame) or not _ball_row_is_edge(next_row)
        if not previous_anchored or not next_anchored:
            continue

        previous_frame_gap = int(row["Frame_ID"]) - int(previous_row["Frame_ID"])
        next_frame_gap = int(next_row["Frame_ID"]) - int(row["Frame_ID"])
        if previous_frame_gap > int(max_frame_gap) or next_frame_gap > int(max_frame_gap):
            continue

        previous_distance = hypot(
            float(row["X"]) - float(previous_row["X"]),
            float(row["Y"]) - float(previous_row["Y"]),
        )
        next_distance = hypot(
            float(next_row["X"]) - float(row["X"]),
            float(next_row["Y"]) - float(row["Y"]),
        )
        if previous_distance > MAX_COHERENT_BALL_STEP_DISTANCE or next_distance > MAX_COHERENT_BALL_STEP_DISTANCE:
            continue

        bridge_frame_count += 1

    anchored_path_length = 0.0
    for index in range(1, len(anchored_rows)):
        anchored_path_length += hypot(
            float(anchored_rows[index]["X"]) - float(anchored_rows[index - 1]["X"]),
            float(anchored_rows[index]["Y"]) - float(anchored_rows[index - 1]["Y"]),
        )

    segment_frame_ids = [int(row["Frame_ID"]) for row in ordered_rows]
    return {
        "startFrame": min(segment_frame_ids),
        "endFrame": max(segment_frame_ids),
        "frameCount": len(ordered_rows),
        "supportedFrameCount": supported_frame_count,
        "anchoredFrameCount": len(anchored_rows),
        "bridgeFrameCount": bridge_frame_count,
        "unsupportedEdgeFrameShare": round(
            unsupported_edge_frame_count / len(ordered_rows),
            3,
        ),
        "anchoredPathLength": round(anchored_path_length, 2),
    }


def _summarize_recovered_ball_anchor_diagnostics(rows, player_rows=None, max_frame_gap=5):
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return {
            "supportedFrameCount": 0,
            "anchoredFrameCount": 0,
            "bridgeFrameCount": 0,
            "unsupportedEdgeFrameShare": 0.0,
            "anchoredPathLength": 0.0,
            "segmentDiagnostics": [],
        }

    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    segment_diagnostics = [
        _summarize_recovered_ball_segment_anchor_diagnostics(
            segment,
            player_rows_by_frame=player_rows_by_frame,
            max_frame_gap=max_frame_gap,
        )
        for segment in split_ball_rows_into_segments(ordered_rows, max_frame_gap=max_frame_gap)
    ]

    supported_frame_count = sum(int(segment["supportedFrameCount"]) for segment in segment_diagnostics)
    anchored_frame_count = sum(int(segment["anchoredFrameCount"]) for segment in segment_diagnostics)
    bridge_frame_count = sum(int(segment["bridgeFrameCount"]) for segment in segment_diagnostics)
    unsupported_edge_frame_count = sum(
        int(round(float(segment["unsupportedEdgeFrameShare"]) * int(segment["frameCount"])))
        for segment in segment_diagnostics
    )
    anchored_path_length = round(
        sum(float(segment["anchoredPathLength"]) for segment in segment_diagnostics),
        2,
    )
    return {
        "supportedFrameCount": supported_frame_count,
        "anchoredFrameCount": anchored_frame_count,
        "bridgeFrameCount": bridge_frame_count,
        "unsupportedEdgeFrameShare": round(
            unsupported_edge_frame_count / len(ordered_rows),
            3,
        ),
        "anchoredPathLength": anchored_path_length,
        "segmentDiagnostics": segment_diagnostics,
    }


def _score_anchor_weighted_recovery_profile(summary):
    if "anchoredFrameCount" not in summary and "supportedFrameCount" not in summary:
        return float(score_ball_track_summary(summary))

    frames = max(int(summary.get("frames", 0)), 1)
    anchored_frame_count = float(summary.get("anchoredFrameCount", 0))
    supported_frame_count = float(summary.get("supportedFrameCount", 0))
    bridge_frame_count = float(summary.get("bridgeFrameCount", 0))
    anchored_path_length = float(summary.get("anchoredPathLength", 0.0))
    unsupported_edge_frame_share = float(summary.get("unsupportedEdgeFrameShare", 0.0))
    anchored_frame_share = anchored_frame_count / frames
    supported_frame_share = supported_frame_count / frames
    return round(
        (anchored_frame_count * 100.0)
        + (supported_frame_share * 250.0)
        + (anchored_frame_share * 125.0)
        + (anchored_path_length * 10.0)
        + (bridge_frame_count * 5.0)
        - (unsupported_edge_frame_share * 300.0),
        3,
    )


def _recovery_profile_rank(result):
    selected_summary = dict(result.get("selectedSummary") or {})
    if "anchoredFrameCount" not in selected_summary and "supportedFrameCount" not in selected_summary:
        return (
            0,
            float(result.get("selectedScore", 0.0)),
        )

    frames = max(int(selected_summary.get("frames", 0)), 1)
    anchored_frame_count = int(selected_summary.get("anchoredFrameCount", 0))
    supported_frame_count = int(selected_summary.get("supportedFrameCount", 0))
    anchored_path_length = float(selected_summary.get("anchoredPathLength", 0.0))
    unsupported_edge_frame_share = float(selected_summary.get("unsupportedEdgeFrameShare", 0.0))
    bridge_frame_count = int(selected_summary.get("bridgeFrameCount", 0))
    supported_frame_share = supported_frame_count / frames
    anchored_frame_share = anchored_frame_count / frames
    return (
        1,
        anchored_frame_count,
        supported_frame_share,
        anchored_frame_share,
        anchored_path_length,
        -unsupported_edge_frame_share,
        bridge_frame_count,
        float(result.get("selectedScore", 0.0)),
    )


def _summarize_ball_truth_layer(rows, max_frame_gap=5):
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return {
            "rowCount": 0,
            "frameCount": 0,
            "pathLength": 0.0,
            "edgeFrameShare": 0.0,
            "segmentCount": 0,
            "firstFrame": None,
            "lastFrame": None,
        }

    frame_ids = [int(row["Frame_ID"]) for row in ordered_rows]
    return {
        "rowCount": len(ordered_rows),
        "frameCount": len(set(frame_ids)),
        "pathLength": round(
            sum(
                hypot(
                    float(ordered_rows[index]["X"]) - float(ordered_rows[index - 1]["X"]),
                    float(ordered_rows[index]["Y"]) - float(ordered_rows[index - 1]["Y"]),
                )
                for index in range(1, len(ordered_rows))
            ),
            2,
        ),
        "edgeFrameShare": round(
            sum(
                1
                for row in ordered_rows
                if (
                    float(row["X"]) <= BALL_EDGE_MARGIN
                    or float(row["X"]) >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
                    or float(row["Y"]) <= BALL_EDGE_MARGIN
                    or float(row["Y"]) >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
                )
            )
            / len(ordered_rows),
            3,
        ),
        "segmentCount": len(split_ball_rows_into_segments(ordered_rows, max_frame_gap=max_frame_gap)),
        "firstFrame": frame_ids[0],
        "lastFrame": frame_ids[-1],
    }


def _infer_ball_sample_interval(frame_ids):
    ordered_frame_ids = sorted({int(frame_id) for frame_id in frame_ids})
    if len(ordered_frame_ids) < 2:
        return 1

    inferred_interval = 0
    for previous_frame_id, current_frame_id in zip(ordered_frame_ids, ordered_frame_ids[1:]):
        frame_delta = current_frame_id - previous_frame_id
        if frame_delta <= 0:
            continue
        inferred_interval = frame_delta if inferred_interval == 0 else gcd(inferred_interval, frame_delta)
    return max(inferred_interval, 1)


def _row_is_edge_heavy_ball(row):
    try:
        x = float(row["X"])
        y = float(row["Y"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        x <= BALL_EDGE_MARGIN
        or x >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or y <= BALL_EDGE_MARGIN
        or y >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )


def _source_edge_share_repair_config(edge_share_repair_profile):
    return get_source_edge_share_repair_config(edge_share_repair_profile)


def _default_source_conditioned_acquisition_diagnostics(
    *,
    profile_name=None,
    source_clip_id=None,
):
    config = _source_edge_share_repair_config(profile_name)
    mode = str(config.get("mode")) if isinstance(config, dict) and config.get("mode") is not None else None
    return {
        "applied": False,
        "profileName": profile_name if isinstance(profile_name, str) else None,
        "mode": mode,
        "sourceClipId": source_clip_id,
        "selectedAcquisitionProfileName": profile_name if isinstance(profile_name, str) else None,
        "proposalWindowKindCandidateCounts": {},
        "proposalWindowKindSelectedCounts": {},
        "touchlineCandidateModeEntered": False,
        "touchlineEscapeWindowFrames": 0,
        "touchlineInboardWindowFrames": 0,
        "touchlineEscapeCandidateFrames": 0,
        "touchlineEscapeSelectedFrames": 0,
        "reopenedRawCandidateFrames": 0,
        "reopenedRawCandidateSelectedFrames": 0,
        "edgeStuckCandidateRejectionCounts": {},
        "zeroTouchlineCandidateReasonCounts": {},
        "repeatedAnchorSuppressionCount": 0,
        "proposalSelectionAdmissionFixAcceptedFrames": 0,
        "proposalSelectionAdmissionFixRejectedCounts": {},
        "proposalSelectionAdmissionFixTruthSeedFrames": 0,
        "proposalSelectionAdmissionFixApproachFamily": None,
        "supportViabilityAdmissionFixAcceptedFrames": 0,
        "supportViabilityAdmissionFixRejectedCounts": {},
        "supportViabilityAdmissionFixTruthSeedFrames": 0,
        "supportViabilityAdmissionFixApproachFamily": None,
        "candidateSourceEdgeShareBeforeSelection": 0.0,
        "candidateSourceEdgeShareAfterSelection": 0.0,
        "baselineGuidedRescueAvailableFrames": 0,
        "baselineGuidedRescueUsedFrames": 0,
        "baselineGuidedRescueSkippedExistingFrames": 0,
        "baselineGuidedRescueSkippedEdgeFrames": 0,
        "baselineGuidedRescueSelectedFrames": 0,
        "continuityBridgeGapFrames": 0,
        "continuityBridgeCandidateFrames": 0,
        "continuityBridgeAcceptedFrames": 0,
        "continuityBridgeRejectedEdgeFrames": 0,
        "continuityBridgeRejectedContinuityFrames": 0,
        "continuityBridgeRejectedSupportFrames": 0,
        "continuityBridgeRejectedRepeatedAnchorFrames": 0,
        "acceptanceSupportGatingAcceptedFrames": 0,
        "acceptanceSupportGatingRejectedCounts": {},
    }


def _build_source_conditioned_acquisition_diagnostics(
    *,
    profile_name=None,
    source_clip_id=None,
    candidate_summary=None,
):
    diagnostics = _default_source_conditioned_acquisition_diagnostics(
        profile_name=profile_name,
        source_clip_id=source_clip_id,
    )
    if not _touchline_acquisition_enabled(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=profile_name,
    ):
        return diagnostics

    candidate_summary = dict(candidate_summary or {})
    touchline_window_kinds = {TOUCHLINE_ESCAPE_WINDOW_KIND, TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND}
    proposal_window_kind_candidate_counts = {
        str(kind): int(count)
        for kind, count in (
            candidate_summary.get("proposalWindowKindCandidateCounts", {}).items()
            if isinstance(candidate_summary.get("proposalWindowKindCandidateCounts"), dict)
            else []
        )
        if str(kind) in touchline_window_kinds
    }
    proposal_window_kind_selected_counts = {
        str(kind): int(count)
        for kind, count in (
            candidate_summary.get("proposalWindowKindSelectedCounts", {}).items()
            if isinstance(candidate_summary.get("proposalWindowKindSelectedCounts"), dict)
            else []
        )
        if str(kind) in touchline_window_kinds
    }
    diagnostics.update(
        {
            "applied": True,
            "proposalWindowKindCandidateCounts": proposal_window_kind_candidate_counts,
            "proposalWindowKindSelectedCounts": proposal_window_kind_selected_counts,
            "touchlineCandidateModeEntered": bool(
                candidate_summary.get("proposalTouchlineCandidateModeEntered", False)
            ),
            "touchlineEscapeWindowFrames": int(
                candidate_summary.get("proposalTouchlineEscapeDetectedFrames", 0)
            ),
            "touchlineInboardWindowFrames": int(
                candidate_summary.get("proposalTouchlineInboardDetectedFrames", 0)
            ),
            "touchlineEscapeCandidateFrames": int(
                candidate_summary.get("proposalTouchlineEscapeDetectedFrames", 0)
            ),
            "touchlineEscapeSelectedFrames": int(
                candidate_summary.get("proposalTouchlineEscapeSelectedFrames", 0)
            ),
            "reopenedRawCandidateFrames": int(
                candidate_summary.get("proposalReopenedRawCandidateFrames", 0)
            ),
            "reopenedRawCandidateSelectedFrames": int(
                candidate_summary.get("proposalReopenedRawCandidateSelectedFrames", 0)
            ),
            "edgeStuckCandidateRejectionCounts": dict(
                candidate_summary.get("proposalTouchlineEscapeRejectionCounts")
                if isinstance(candidate_summary.get("proposalTouchlineEscapeRejectionCounts"), dict)
                else {}
            ),
            "zeroTouchlineCandidateReasonCounts": dict(
                candidate_summary.get("proposalZeroTouchlineCandidateReasonCounts")
                if isinstance(candidate_summary.get("proposalZeroTouchlineCandidateReasonCounts"), dict)
                else {}
            ),
            "repeatedAnchorSuppressionCount": int(
                candidate_summary.get("proposalRepeatedAnchorSuppressedFrames", 0)
            ),
            "candidateSourceEdgeShareBeforeSelection": round(
                float(candidate_summary.get("proposalCandidateEdgeShareBeforeSelection", 0.0)),
                3,
            ),
            "candidateSourceEdgeShareAfterSelection": round(
                float(candidate_summary.get("proposalCandidateEdgeShareAfterSelection", 0.0)),
                3,
            ),
            "baselineGuidedRescueAvailableFrames": int(
                candidate_summary.get("proposalBaselineGuidedRescueAvailableFrames", 0)
            ),
            "baselineGuidedRescueUsedFrames": int(
                candidate_summary.get("proposalBaselineGuidedRescueUsedFrames", 0)
            ),
            "baselineGuidedRescueSkippedExistingFrames": int(
                candidate_summary.get("proposalBaselineGuidedRescueSkippedExistingFrames", 0)
            ),
            "baselineGuidedRescueSkippedEdgeFrames": int(
                candidate_summary.get("proposalBaselineGuidedRescueSkippedEdgeFrames", 0)
            ),
            "baselineGuidedRescueSelectedFrames": int(
                candidate_summary.get("proposalBaselineGuidedRescueSelectedFrames", 0)
            ),
            "continuityBridgeGapFrames": int(
                candidate_summary.get("proposalContinuityBridgeGapFrames", 0)
            ),
            "continuityBridgeCandidateFrames": int(
                candidate_summary.get("proposalContinuityBridgeCandidateFrames", 0)
            ),
            "continuityBridgeAcceptedFrames": int(
                candidate_summary.get("proposalContinuityBridgeAcceptedFrames", 0)
            ),
            "continuityBridgeRejectedEdgeFrames": int(
                candidate_summary.get("proposalContinuityBridgeRejectedEdgeFrames", 0)
            ),
            "continuityBridgeRejectedContinuityFrames": int(
                candidate_summary.get("proposalContinuityBridgeRejectedContinuityFrames", 0)
            ),
            "continuityBridgeRejectedSupportFrames": int(
                candidate_summary.get("proposalContinuityBridgeRejectedSupportFrames", 0)
            ),
            "continuityBridgeRejectedRepeatedAnchorFrames": int(
                candidate_summary.get("proposalContinuityBridgeRejectedRepeatedAnchorFrames", 0)
            ),
            "acceptanceSupportGatingAcceptedFrames": int(
                candidate_summary.get("proposalAcceptanceSupportGatingAcceptedFrames", 0)
            ),
            "acceptanceSupportGatingRejectedCounts": dict(
                candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts")
                if isinstance(candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts"), dict)
                else {}
            ),
            "proposalSelectionAdmissionFixAcceptedFrames": int(
                candidate_summary.get("proposalSelectionAdmissionFixAcceptedFrames", 0)
            ),
            "proposalSelectionAdmissionFixRejectedCounts": dict(
                candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts")
                if isinstance(candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts"), dict)
                else {}
            ),
            "proposalSelectionAdmissionFixTruthSeedFrames": int(
                candidate_summary.get("proposalSelectionAdmissionFixTruthSeedFrames", 0)
            ),
            "proposalSelectionAdmissionFixApproachFamily": (
                str(candidate_summary.get("proposalSelectionAdmissionFixApproachFamily"))
                if candidate_summary.get("proposalSelectionAdmissionFixApproachFamily")
                else None
            ),
            "supportViabilityAdmissionFixAcceptedFrames": int(
                candidate_summary.get("proposalSupportViabilityAdmissionFixAcceptedFrames", 0)
            ),
            "supportViabilityAdmissionFixRejectedCounts": dict(
                candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts")
                if isinstance(candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts"), dict)
                else {}
            ),
            "supportViabilityAdmissionFixTruthSeedFrames": int(
                candidate_summary.get("proposalSupportViabilityAdmissionFixTruthSeedFrames", 0)
            ),
            "supportViabilityAdmissionFixApproachFamily": (
                str(candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily"))
                if candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily")
                else None
            ),
        }
    )
    return diagnostics


def _apply_source_conditioned_edge_share_repair(
    accepted_rows,
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
    player_rows=None,
    sample_interval=1,
    probe_filtered_rows=None,
    probe_raw_rows=None,
):
    repaired_rows, diagnostics, replacement_diagnostics = _shared_apply_source_conditioned_edge_share_repair(
        list(accepted_rows),
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
        player_rows=list(player_rows or []),
        sample_interval=sample_interval,
        probe_filtered_rows=list(probe_filtered_rows or []),
        probe_raw_rows=list(probe_raw_rows or []),
    )
    diagnostics = dict(diagnostics)
    diagnostics.pop("edgeRuns", None)
    return repaired_rows, diagnostics, replacement_diagnostics


def _select_viable_ball_segments(rows, max_frame_gap=5, player_rows=None):
    candidates = []
    for segment in split_ball_rows_into_segments(rows, max_frame_gap=max_frame_gap):
        for chain in _coherent_ball_subchains(segment):
            chain_summary = summarize_ball_track_rows(chain)
            if not ball_track_summary_is_viable(chain_summary):
                continue
            anchor_summary = _summarize_recovered_ball_anchor_diagnostics(
                chain,
                player_rows=player_rows,
                max_frame_gap=max_frame_gap,
            )
            frame_ids = sorted({int(row["Frame_ID"]) for row in chain})
            candidates.append(
                {
                    "rows": chain,
                    "summary": chain_summary,
                    "anchorSummary": anchor_summary,
                    "score": score_ball_track_summary(chain_summary),
                    "startFrame": frame_ids[0],
                    "endFrame": frame_ids[-1],
                    "frameIds": frame_ids,
                }
            )

    candidates.sort(
        key=lambda candidate: (
            float(candidate["anchorSummary"].get("anchoredFrameCount", 0)),
            float(candidate["anchorSummary"].get("supportedFrameCount", 0)),
            float(candidate["anchorSummary"].get("anchoredPathLength", 0.0)),
            -float(candidate["anchorSummary"].get("unsupportedEdgeFrameShare", 0.0)),
            float(candidate["score"]),
            len(candidate["frameIds"]),
            float(candidate["summary"].get("pathLength", 0.0)),
            float(candidate["summary"].get("meanConfidence", 0.0)),
        ),
        reverse=True,
    )

    accepted = []
    accepted_ranges = []
    for candidate in candidates:
        candidate_start = int(candidate["startFrame"])
        candidate_end = int(candidate["endFrame"])
        if any(
            candidate_start <= int(existing_end) and int(existing_start) <= candidate_end
            for existing_start, existing_end in accepted_ranges
        ):
            continue
        accepted.append(candidate)
        accepted_ranges.append((candidate_start, candidate_end))

    accepted.sort(key=lambda candidate: (candidate["startFrame"], candidate["endFrame"]))
    return accepted


def _build_ball_truth_layers(
    observed_rows,
    inferred_rows,
    *,
    probe_observed_rows=None,
    max_frame_gap=5,
    sample_interval=None,
    player_rows=None,
    source_clip_id=None,
    edge_share_repair_profile=None,
    acquisition_diagnostics=None,
):
    tracking_observed_rows = [row for row in observed_rows if row.get("Entity_Type") == "ball"]
    probe_observed_rows = [row for row in (probe_observed_rows or []) if row.get("Entity_Type") == "ball"]
    effective_sample_interval = max(int(sample_interval), 1) if sample_interval is not None else 1
    probe_player_windows = collect_player_windows_from_rows(player_rows or [])
    probe_observed_rows = suppress_repeated_false_ball_clusters(
        probe_observed_rows,
        player_windows=probe_player_windows,
    )
    probe_observation_breakdown = _filter_probe_observed_ball_rows(
        probe_observed_rows,
        player_rows=player_rows,
        sample_interval=effective_sample_interval,
    )
    filtered_probe_observed_rows = probe_observation_breakdown["filteredRows"]
    observed_ball_rows = _select_best_observed_ball_rows(
        tracking_observed_rows,
        filtered_probe_observed_rows,
        player_rows=player_rows,
    )
    observed_frames = {int(row["Frame_ID"]) for row in observed_ball_rows}
    inferred_ball_rows = [
        row
        for row in _best_ball_rows_by_frame(inferred_rows)
        if int(row["Frame_ID"]) not in observed_frames
    ]

    accepted_rows = list(observed_ball_rows)
    source_by_frame = {int(row["Frame_ID"]): "observed" for row in observed_ball_rows}
    for row in inferred_ball_rows:
        frame_id = int(row["Frame_ID"])
        source_by_frame[frame_id] = "inferred"
        accepted_rows.append(row)

    accepted_rows = sorted(accepted_rows, key=lambda row: int(row["Frame_ID"]))
    post_acceptance_profile = (
        None
        if _touchline_acquisition_enabled(
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        )
        or _touchline_reviewed_positive_acceptance_profile_config(
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        )
        is not None
        else edge_share_repair_profile
    )
    accepted_rows, edge_share_repair_diagnostics, run_replacement_diagnostics = _apply_source_conditioned_edge_share_repair(
        accepted_rows,
        source_clip_id=source_clip_id,
        edge_share_repair_profile=post_acceptance_profile,
        player_rows=player_rows,
        sample_interval=effective_sample_interval,
        probe_filtered_rows=filtered_probe_observed_rows,
        probe_raw_rows=probe_observation_breakdown["rawRows"],
    )
    sample_interval = (
        effective_sample_interval
        if sample_interval is not None
        else _infer_ball_sample_interval([int(row["Frame_ID"]) for row in accepted_rows])
    )

    def _layer_payload(rows):
        return {
            "rows": list(rows),
            "summary": _summarize_ball_truth_layer(rows, max_frame_gap=sample_interval),
        }

    accepted_segments = []
    for segment in split_ball_rows_into_segments(accepted_rows, max_frame_gap=sample_interval):
        segment_frame_ids = {int(row["Frame_ID"]) for row in segment}
        sources = {source_by_frame.get(frame_id) for frame_id in segment_frame_ids}
        sources.discard(None)
        if sources == {"observed"}:
            source = "observed"
        elif sources == {"inferred"}:
            source = "inferred"
        else:
            source = "mixed"
        accepted_segments.append(
            {
                "startFrame": min(segment_frame_ids),
                "endFrame": max(segment_frame_ids),
                "frameCount": len(segment_frame_ids),
                "source": source,
            }
        )

    unknown_gaps = []
    for previous_segment, next_segment in zip(accepted_segments, accepted_segments[1:]):
        gap_start = int(previous_segment["endFrame"]) + sample_interval
        gap_end = int(next_segment["startFrame"]) - sample_interval
        if gap_start > gap_end:
            continue
        unknown_gaps.append(
            {
                "startFrame": gap_start,
                "endFrame": gap_end,
                "frameCount": ((gap_end - gap_start) // sample_interval) + 1,
            }
        )

    observed_frame_count = len(observed_frames)
    inferred_frame_count = len({int(row["Frame_ID"]) for row in inferred_ball_rows})
    tracking_frame_count = len({int(row["Frame_ID"]) for row in _best_ball_rows_by_frame(tracking_observed_rows)})
    raw_probe_frame_count = int(probe_observation_breakdown["rawFrameCount"])
    filtered_probe_frame_count = int(probe_observation_breakdown["filteredFrameCount"])
    accepted_from_observed_frames = observed_frame_count
    accepted_from_observed_ratio = (
        round(accepted_from_observed_frames / len(accepted_rows), 3) if accepted_rows else 0.0
    )
    tracking_frame_ids = {int(row["Frame_ID"]) for row in tracking_observed_rows}
    filtered_probe_frame_ids = {int(row["Frame_ID"]) for row in filtered_probe_observed_rows}
    player_rows = list(player_rows or [])
    support_diagnostics = _build_ball_support_diagnostics(
        observed_ball_rows,
        accepted_rows,
        player_rows,
    )

    return {
        "sampleInterval": sample_interval,
        "observedBall": _layer_payload(observed_ball_rows),
        "inferredBall": _layer_payload(inferred_ball_rows),
        "acceptedBall": _layer_payload(accepted_rows),
        "acceptedSegments": accepted_segments,
        "unknownGaps": unknown_gaps,
        "acceptedSourceBreakdown": {
            "observed": observed_frame_count,
            "inferred": inferred_frame_count,
        },
        "probeObservedBall": {
            "rawRows": list(probe_observation_breakdown["rawRows"]),
            "filteredRows": list(filtered_probe_observed_rows),
        },
        "sourceConditionedAcquisitionDiagnostics": dict(
            acquisition_diagnostics
            if isinstance(acquisition_diagnostics, dict)
            else _default_source_conditioned_acquisition_diagnostics(
                profile_name=edge_share_repair_profile,
                source_clip_id=source_clip_id,
            )
        ),
        "edgeShareRepairDiagnostics": edge_share_repair_diagnostics,
        "sourceConditionedRunReplacementDiagnostics": run_replacement_diagnostics,
        "directObservationBreakdown": {
            "trackingObservedBallFrames": tracking_frame_count,
            "rawProbeObservedBallFrames": raw_probe_frame_count,
            "filteredProbeObservedBallFrames": filtered_probe_frame_count,
            "suppressedProbeObservedBallFrames": int(probe_observation_breakdown["suppressedFrameCount"]),
            "anchoredProbeObservedBallFrames": int(probe_observation_breakdown["anchoredFrameCount"]),
            "bridgeProbeObservedBallFrames": int(probe_observation_breakdown["bridgeFrameCount"]),
            "probeObservedBallFrames": filtered_probe_frame_count,
            "probeOnlyObservedBallFrames": len(filtered_probe_frame_ids - tracking_frame_ids),
            "acceptedFromObservedFrames": accepted_from_observed_frames,
            "acceptedFromObservedRatio": accepted_from_observed_ratio,
        },
        "supportDiagnostics": support_diagnostics,
    }


def resolve_ball_recovery_settings(
    configured_imgsz,
    configured_conf,
    recovery_imgsz=None,
    recovery_conf=None,
):
    fallback_imgsz = max(
        int(configured_imgsz),
        BALL_RECOVERY_IMGSZ if recovery_imgsz is None else int(recovery_imgsz),
    )
    fallback_conf = min(
        float(configured_conf),
        BALL_RECOVERY_CONF if recovery_conf is None else float(recovery_conf),
    )
    return {
        "imgsz": fallback_imgsz,
        "conf": fallback_conf,
    }


def build_ball_recovery_experiment_profiles(
    configured_imgsz,
    configured_conf,
    include_player_window_probe=False,
):
    profiles = [
        {
            "name": "baseline",
            "settings": resolve_ball_recovery_settings(configured_imgsz, configured_conf),
            "usePlayerWindows": False,
        },
        {
            "name": "highres_same_conf",
            "settings": resolve_ball_recovery_settings(
                configured_imgsz,
                configured_conf,
                recovery_imgsz=BALL_RECOVERY_EXPERIMENT_IMGSZ,
                recovery_conf=BALL_RECOVERY_CONF,
            ),
            "usePlayerWindows": False,
        },
        {
            "name": "highres_low_conf",
            "settings": resolve_ball_recovery_settings(
                configured_imgsz,
                configured_conf,
                recovery_imgsz=BALL_RECOVERY_EXPERIMENT_IMGSZ,
                recovery_conf=BALL_RECOVERY_EXPERIMENT_LOW_CONF,
            ),
            "usePlayerWindows": False,
        },
    ]
    if include_player_window_probe:
        profiles.append(
            {
                "name": "highres_player_window",
                "settings": resolve_ball_recovery_settings(
                    configured_imgsz,
                    configured_conf,
                    recovery_imgsz=BALL_RECOVERY_EXPERIMENT_IMGSZ,
                    recovery_conf=BALL_RECOVERY_CONF,
                ),
                "usePlayerWindows": True,
            }
        )
    return profiles


def build_ball_recovery_quality_matrix_profiles():
    shared_settings = {"imgsz": 1600, "conf": 0.08}
    return [
        {
            "name": "baseline_player_window",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
        },
        {
            "name": "width_cap_075",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "maxCropWidthRatio": 0.75,
        },
        {
            "name": "width_cap_06",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "maxCropWidthRatio": 0.6,
        },
        {
            "name": "crop_edge_margin_40",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "cropEdgeMargin": 40,
        },
        {
            "name": "upper_crop_band_075",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "maxCropCenterYRatio": 0.75,
        },
        {
            "name": "edge_margin_40_upper_075",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "cropEdgeMargin": 40,
            "maxCropCenterYRatio": 0.75,
        },
        {
            "name": "edge_margin_40_upper_078",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "cropEdgeMargin": 40,
            "maxCropCenterYRatio": 0.78,
        },
        {
            "name": "proposal_windows_075",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "cropMode": "proposal_windows",
            "maxCropWidthRatio": 0.35,
            "proposalMaxWindowsPerFrame": 3,
            "proposalCropWidthRatio": 0.35,
            "proposalCropPaddingPx": PLAYER_PROPOSAL_CROP_PADDING_PX,
            "directSeedRetryPolicy": DIRECT_SEED_RETRY_POLICY,
            "directSeedRetryScales": list(DIRECT_SEED_RETRY_SCALES),
        },
        {
            "name": "anchor_corridor_width_cap_075",
            "settings": dict(shared_settings),
            "usePlayerWindows": True,
            "cropMode": "anchor_corridor",
            "maxCropWidthRatio": 0.75,
            "corridorHalfWidthPx": 20,
            "corridorPaddingPx": 12,
        },
    ]


def build_detector_breadth_screen_ball_recovery_profiles():
    allowed_profile_names = {"baseline_player_window", "proposal_windows_075"}
    return [
        {
            **profile,
            "settings": dict(profile.get("settings", {})),
        }
        for profile in build_ball_recovery_quality_matrix_profiles()
        if str(profile.get("name") or "") in allowed_profile_names
    ]


def collect_player_windows_from_rows(rows):
    frame_player_windows = {}
    for row in rows:
        if row.get("Entity_Type") != "player":
            continue
        source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
        if not all(key in row for key in source_keys):
            continue
        frame_id = int(row["Frame_ID"])
        frame_player_windows[frame_id] = update_player_window(
            frame_player_windows.get(frame_id),
            float(row["Source_X1"]),
            float(row["Source_Y1"]),
            float(row["Source_X2"]),
            float(row["Source_Y2"]),
        )
    return frame_player_windows


def collect_observed_source_anchors(rows):
    observed_source_anchors = {}
    for row in _best_ball_rows_by_frame(rows):
        source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
        if all(key in row for key in source_keys):
            anchor_x = (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0
            anchor_y = (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
        else:
            anchor_x = float(row.get("X", 0.0))
            anchor_y = float(row.get("Y", 0.0))
        observed_source_anchors[int(row["Frame_ID"])] = (anchor_x, anchor_y)
    return observed_source_anchors


def collect_primary_player_windows(
    video_path,
    model,
    frame_interval,
    imgsz,
    conf,
    tracker,
    detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL,
    frame_source=None,
):
    frame_player_windows = {}
    player_classes = detector_player_class_ids(detector_profile)
    if not player_classes:
        return frame_player_windows
    from backend.app.workbench.media import (
        iter_bgr_frames,
        pixels_from_decoded_frame,
        presentation_seconds_or_none,
        should_sample_on_source_grid,
    )

    fps = None
    if frame_source is not None:
        try:
            fps = getattr(frame_source.probe(Path(video_path)), "nominalFps", None)
        except Exception:
            fps = None
    frame_count = 0
    last_sample_presentation_time = None
    grid_origin_presentation_time = None
    last_sample_pts = None
    grid_origin_pts = None
    for decoded in iter_bgr_frames(Path(video_path), frame_source, cv2_module=cv2):
        frame = pixels_from_decoded_frame(decoded)
        if frame is None:
            frame_count += 1
            continue
        presentation = presentation_seconds_or_none(decoded)
        if grid_origin_presentation_time is None and presentation is not None:
            grid_origin_presentation_time = presentation
        if grid_origin_pts is None and decoded.pts is not None:
            grid_origin_pts = decoded.pts
        if should_sample_on_source_grid(
            decoded,
            frame_count=frame_count,
            frame_interval=frame_interval,
            last_sample_presentation_time=last_sample_presentation_time,
            fps=fps,
            grid_origin_presentation_time=grid_origin_presentation_time,
            last_sample_pts=last_sample_pts,
            grid_origin_pts=grid_origin_pts,
        ):
            last_sample_presentation_time = presentation
            last_sample_pts = decoded.pts
            result = model.predict(
                frame,
                imgsz=imgsz,
                conf=conf,
                classes=player_classes,
                verbose=False,
            )[0]
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    cls = int(box.cls[0])
                    if not detector_class_is_player(cls, detector_profile):
                        continue
                    coords = box.xyxy[0]
                    if hasattr(coords, "tolist"):
                        coords = coords.tolist()
                    x1, y1, x2, y2 = coords
                    frame_player_windows[frame_count] = update_player_window(
                        frame_player_windows.get(frame_count),
                        x1,
                        y1,
                        x2,
                        y2,
                    )
        frame_count += 1
    return frame_player_windows


def _dominant_anchor_cluster(rows, cluster_radius=STATIC_FALSE_BALL_RADIUS):
    clusters = []
    for row in rows:
        if row.get("Entity_Type") != "ball":
            continue
        point = (float(row["X"]), float(row["Y"]))
        matching_cluster = None
        for cluster in clusters:
            if hypot(point[0] - cluster["center"][0], point[1] - cluster["center"][1]) <= float(cluster_radius):
                matching_cluster = cluster
                break
        if matching_cluster is None:
            clusters.append(
                {
                    "points": [point],
                    "center": point,
                }
            )
            continue

        matching_cluster["points"].append(point)
        point_count = len(matching_cluster["points"])
        matching_cluster["center"] = (
            sum(cluster_point[0] for cluster_point in matching_cluster["points"]) / point_count,
            sum(cluster_point[1] for cluster_point in matching_cluster["points"]) / point_count,
        )

    if not clusters:
        return None, 0

    dominant_cluster = max(clusters, key=lambda cluster: len(cluster["points"]))
    center_x, center_y = dominant_cluster["center"]
    return (round(center_x, 1), round(center_y, 1)), len(dominant_cluster["points"])


def summarize_recovered_ball_candidates(rows, player_windows=None, max_frame_gap=5):
    candidate_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not candidate_rows:
        return {
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

    confidence_bands = {"low": 0, "medium": 0, "high": 0}
    edge_candidate_count = 0
    near_player_window_count = 0
    confidence_sum = 0.0
    source_center_y_sum = 0.0
    source_box_area_sum = 0.0
    source_row_count = 0

    for row in candidate_rows:
        confidence = float(row["Conf"])
        confidence_sum += confidence
        if confidence < 0.12:
            confidence_bands["low"] += 1
        elif confidence < 0.25:
            confidence_bands["medium"] += 1
        else:
            confidence_bands["high"] += 1

        if (
            float(row["X"]) <= BALL_EDGE_MARGIN
            or float(row["X"]) >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
            or float(row["Y"]) <= BALL_EDGE_MARGIN
            or float(row["Y"]) >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
        ):
            edge_candidate_count += 1

        if (
            player_windows
            and all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2"))
        ):
            frame_window = player_windows.get(int(row["Frame_ID"]))
            if frame_window is not None:
                center_x = (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0
                center_y = (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
                if _distance_from_point_to_window(center_x, center_y, frame_window) <= MAX_RECOVERED_BALL_DISTANCE_FROM_PLAYER_WINDOW:
                    near_player_window_count += 1

        if all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
            source_center_y = (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
            source_box_area = max(float(row["Source_X2"]) - float(row["Source_X1"]), 0.0) * max(float(row["Source_Y2"]) - float(row["Source_Y1"]), 0.0)
            source_center_y_sum += source_center_y
            source_box_area_sum += source_box_area
            source_row_count += 1

    segments = split_ball_rows_into_segments(candidate_rows, max_frame_gap=max_frame_gap)
    longest_segment_frames = max(
        (len({int(segment_row["Frame_ID"]) for segment_row in segment}) for segment in segments),
        default=0,
    )
    dominant_anchor_coord, dominant_anchor_count = _dominant_anchor_cluster(candidate_rows)

    return {
        "candidateRows": len(candidate_rows),
        "uniqueFrames": len({int(row["Frame_ID"]) for row in candidate_rows}),
        "meanConfidence": round(confidence_sum / len(candidate_rows), 3),
        "edgeCandidateShare": round(edge_candidate_count / len(candidate_rows), 3),
        "nearPlayerWindowShare": round(near_player_window_count / len(candidate_rows), 3),
        "confidenceBands": confidence_bands,
        "segmentCount": len(segments),
        "longestSegmentFrames": longest_segment_frames,
        "dominantAnchorCoord": dominant_anchor_coord,
        "dominantAnchorCount": dominant_anchor_count,
        "dominantAnchorShare": round(dominant_anchor_count / len(candidate_rows), 3),
        "meanSourceCenterY": round(source_center_y_sum / source_row_count, 2) if source_row_count else 0.0,
        "meanSourceBoxArea": round(source_box_area_sum / source_row_count, 2) if source_row_count else 0.0,
    }


def summarize_ball_track_rows(rows):
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return {
            "frames": 0,
            "candidateRows": 0,
            "xSpan": 0.0,
            "ySpan": 0.0,
            "pathLength": 0.0,
            "meanConfidence": 0.0,
            "edgeFrameShare": 0.0,
            "showsMeaningfulMotion": False,
        }

    xs = [float(row["X"]) for row in ordered_rows]
    ys = [float(row["Y"]) for row in ordered_rows]
    path_length = sum(
        hypot(xs[index] - xs[index - 1], ys[index] - ys[index - 1])
        for index in range(1, len(ordered_rows))
    )
    frame_count = len(ordered_rows)
    mean_confidence = sum(float(row["Conf"]) for row in ordered_rows) / frame_count
    edge_frame_count = sum(
        1
        for row in ordered_rows
        if (
            float(row["X"]) <= BALL_EDGE_MARGIN
            or float(row["X"]) >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
            or float(row["Y"]) <= BALL_EDGE_MARGIN
            or float(row["Y"]) >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
        )
    )

    return {
        "frames": frame_count,
        "candidateRows": len([row for row in rows if row.get("Entity_Type") == "ball"]),
        "xSpan": round(max(xs) - min(xs), 2),
        "ySpan": round(max(ys) - min(ys), 2),
        "pathLength": round(path_length, 2),
        "meanConfidence": round(mean_confidence, 3),
        "edgeFrameShare": round(edge_frame_count / frame_count, 3),
        "showsMeaningfulMotion": ball_rows_show_meaningful_motion(ordered_rows),
    }


def score_ball_track_summary(summary):
    movement_score = float(summary["pathLength"]) + max(float(summary["xSpan"]), float(summary["ySpan"]))
    confidence_score = float(summary["meanConfidence"]) * 10.0
    frame_score = float(summary["frames"])
    edge_penalty = float(summary.get("edgeFrameShare", 0.0)) * 60.0
    meaningful_motion_bonus = 35.0 if summary["showsMeaningfulMotion"] else 0.0
    return round(
        frame_score + movement_score + confidence_score + meaningful_motion_bonus - edge_penalty,
        3,
    )


def ball_track_summary_is_viable(summary):
    if not summary.get("showsMeaningfulMotion"):
        return False
    return float(summary.get("edgeFrameShare", 0.0)) <= MAX_VIABLE_EDGE_FRAME_SHARE


def ball_rows_show_meaningful_motion(rows):
    ordered_rows = _best_ball_rows_by_frame(rows)
    if len(ordered_rows) < MIN_RECOVERED_BALL_FRAMES:
        return False

    xs = [float(row["X"]) for row in ordered_rows]
    ys = [float(row["Y"]) for row in ordered_rows]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    path_length = sum(
        hypot(xs[index] - xs[index - 1], ys[index] - ys[index - 1])
        for index in range(1, len(ordered_rows))
    )
    return max(x_span, y_span) >= MIN_RECOVERED_BALL_SPAN or path_length >= MIN_RECOVERED_BALL_PATH


def ball_rows_need_recovery(rows):
    ball_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not ball_rows:
        return True
    return not ball_rows_show_meaningful_motion(ball_rows)


def ball_rows_need_supplemental_recovery(rows, frame_interval):
    if frame_interval <= 0:
        return False

    ball_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not ball_rows or not ball_rows_show_meaningful_motion(ball_rows):
        return False

    ball_frame_ids = sorted({int(row["Frame_ID"]) for row in ball_rows})
    return any(
        (current_frame_id - previous_frame_id) > int(frame_interval)
        for previous_frame_id, current_frame_id in zip(ball_frame_ids, ball_frame_ids[1:])
    )


def split_ball_rows_into_segments(rows, max_frame_gap):
    ordered_rows = sorted(
        [row for row in rows if row.get("Entity_Type") == "ball"],
        key=lambda row: int(row["Frame_ID"]),
    )
    if not ordered_rows:
        return []

    segments = [[ordered_rows[0]]]
    for row in ordered_rows[1:]:
        previous_row = segments[-1][-1]
        if int(row["Frame_ID"]) - int(previous_row["Frame_ID"]) > int(max_frame_gap):
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments


def _distance_from_point_to_window(x, y, window):
    left, top, right, bottom = [float(value) for value in window]
    dx = max(left - float(x), 0.0, float(x) - right)
    dy = max(top - float(y), 0.0, float(y) - bottom)
    return hypot(dx, dy)


def filter_ball_rows_by_player_window_proximity(rows, player_windows):
    if not player_windows:
        return rows

    filtered_rows = []
    for row in rows:
        frame_window = player_windows.get(int(row["Frame_ID"]))
        if frame_window is None:
            filtered_rows.append(row)
            continue
        if not all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
            filtered_rows.append(row)
            continue

        center_x = (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0
        center_y = (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
        if _distance_from_point_to_window(center_x, center_y, frame_window) <= MAX_RECOVERED_BALL_DISTANCE_FROM_PLAYER_WINDOW:
            filtered_rows.append(row)

    return filtered_rows


def _coherent_ball_subchains(rows, max_step_distance=MAX_COHERENT_BALL_STEP_DISTANCE):
    ordered_rows = sorted(
        [row for row in rows if row.get("Entity_Type") == "ball"],
        key=lambda row: (int(row["Frame_ID"]), -float(row["Conf"])),
    )
    if not ordered_rows:
        return []

    rows_by_frame = {}
    for row in ordered_rows:
        rows_by_frame.setdefault(int(row["Frame_ID"]), []).append(row)
    frame_ids = sorted(rows_by_frame)

    processed_states = []

    for frame_id in frame_ids:
        frame_states = []
        for candidate in rows_by_frame[frame_id]:
            best_chain = [candidate]
            best_summary = summarize_ball_track_rows(best_chain)
            best_rank = (
                len(best_chain),
                float(score_ball_track_summary(best_summary)),
                float(best_summary.get("pathLength", 0.0)),
                float(best_summary.get("meanConfidence", 0.0)),
            )

            for previous_state in processed_states:
                previous_row = previous_state["rows"][-1]
                if int(previous_row["Frame_ID"]) >= frame_id:
                    continue

                step_distance = hypot(
                    float(candidate["X"]) - float(previous_row["X"]),
                    float(candidate["Y"]) - float(previous_row["Y"]),
                )
                if step_distance > float(max_step_distance):
                    continue

                candidate_chain = previous_state["rows"] + [candidate]
                candidate_summary = summarize_ball_track_rows(candidate_chain)
                candidate_rank = (
                    len(candidate_chain),
                    float(score_ball_track_summary(candidate_summary)),
                    float(candidate_summary.get("pathLength", 0.0)),
                    float(candidate_summary.get("meanConfidence", 0.0)),
                )
                if candidate_rank > best_rank:
                    best_chain = candidate_chain
                    best_summary = candidate_summary
                    best_rank = candidate_rank

            frame_states.append(
                {
                    "rows": best_chain,
                    "summary": best_summary,
                    "rank": best_rank,
                }
            )
        processed_states.extend(frame_states)

    unique_subchains = []
    seen_keys = set()
    for state in processed_states:
        chain = state["rows"]
        if len(chain) < MIN_RECOVERED_BALL_FRAMES:
            continue
        chain_key = tuple(
            (
                int(row["Frame_ID"]),
                round(float(row["X"]), 3),
                round(float(row["Y"]), 3),
                round(float(row["Conf"]), 3),
            )
            for row in chain
        )
        if chain_key in seen_keys:
            continue
        seen_keys.add(chain_key)
        unique_subchains.append(chain)
    return unique_subchains


def _select_best_viable_ball_segment(rows, max_frame_gap=5, player_rows=None):
    viable_segments = _select_viable_ball_segments(
        rows,
        max_frame_gap=max_frame_gap,
        player_rows=player_rows,
    )
    if not viable_segments:
        return None
    best_segment = max(
        viable_segments,
        key=lambda segment: (
            float(segment.get("anchorSummary", {}).get("anchoredFrameCount", 0)),
            float(segment.get("anchorSummary", {}).get("supportedFrameCount", 0)),
            float(segment.get("anchorSummary", {}).get("anchoredPathLength", 0.0)),
            -float(segment.get("anchorSummary", {}).get("unsupportedEdgeFrameShare", 0.0)),
            float(segment["score"]),
        ),
    )
    return {
        "rows": best_segment["rows"],
        "summary": best_segment["summary"],
        "score": best_segment["score"],
    }


def _recover_ball_candidate_source_center_y(row):
    source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if all(key in row for key in source_keys):
        return (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
    return float(row.get("Y", 0.0))


def _collapse_recovered_ball_candidates(rows, player_rows=None, max_frame_gap=5):
    candidate_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not candidate_rows:
        return {
            "rows": list(rows),
            "collapsedCandidateFrames": 0,
            "collapsedSegmentCount": 0,
            "collapsedLongestSegmentFrames": 0,
            "continuityPreferredFrames": 0,
            "continuityRejectedFrames": 0,
            "midfieldCollapsedFrames": 0,
        }

    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    rows_by_frame = {}
    for original_index, row in enumerate(candidate_rows):
        rows_by_frame.setdefault(int(row["Frame_ID"]), []).append((original_index, row))

    def _row_rank(row, original_index, *, prior_row=None, allow_continuity=False):
        supported = _ball_row_is_player_supported(row, player_rows_by_frame)
        non_edge = not _ball_row_is_edge(row)
        anchored = supported or non_edge
        source_center_y = _recover_ball_candidate_source_center_y(row)
        step_distance = (
            hypot(
                float(row["X"]) - float(prior_row["X"]),
                float(row["Y"]) - float(prior_row["Y"]),
            )
            if prior_row is not None
            else float("inf")
        )
        if allow_continuity:
            return (
                1,
                1 if anchored else 0,
                1 if supported else 0,
                1 if non_edge else 0,
                float(row.get("Conf", 0.0)),
                -step_distance,
                -source_center_y,
                -int(original_index),
            )
        return (
            1 if anchored else 0,
            1 if supported else 0,
            1 if non_edge else 0,
            float(row.get("Conf", 0.0)),
            -step_distance,
            -source_center_y,
            -int(original_index),
        )

    collapsed_rows = []
    continuity_preferred_frames = 0
    continuity_rejected_frames = 0
    midfield_collapsed_frames = 0
    prior_collapsed_row = None

    for frame_id in sorted(rows_by_frame):
        frame_candidates = rows_by_frame[frame_id]
        if len(frame_candidates) > 1:
            continuity_rejected_frames += 1

        extender_candidates = []
        prior_chain_is_coherent = (
            prior_collapsed_row is not None
            and (
                _ball_row_is_player_supported(prior_collapsed_row, player_rows_by_frame)
                or not _ball_row_is_edge(prior_collapsed_row)
            )
        )
        if prior_chain_is_coherent:
            for original_index, candidate_row in frame_candidates:
                step_distance = hypot(
                    float(candidate_row["X"]) - float(prior_collapsed_row["X"]),
                    float(candidate_row["Y"]) - float(prior_collapsed_row["Y"]),
                )
                if step_distance <= float(MAX_COHERENT_BALL_STEP_DISTANCE):
                    extender_candidates.append((original_index, candidate_row))

        if extender_candidates:
            _, best_candidate = max(
                extender_candidates,
                key=lambda item: _row_rank(
                    item[1],
                    item[0],
                    prior_row=prior_collapsed_row,
                    allow_continuity=True,
                ),
            )
            continuity_preferred_frames += 1
        else:
            _, best_candidate = max(
                frame_candidates,
                key=lambda item: _row_rank(item[1], item[0]),
            )

        collapsed_rows.append(best_candidate)
        if not _ball_row_is_edge(best_candidate):
            midfield_collapsed_frames += 1
        prior_collapsed_row = best_candidate

    collapsed_segments = split_ball_rows_into_segments(collapsed_rows, max_frame_gap=max_frame_gap)
    longest_segment_frames = max(
        (len({int(segment_row["Frame_ID"]) for segment_row in segment}) for segment in collapsed_segments),
        default=0,
    )
    return {
        "rows": collapsed_rows,
        "collapsedCandidateFrames": len({int(row["Frame_ID"]) for row in collapsed_rows}),
        "collapsedSegmentCount": len(collapsed_segments),
        "collapsedLongestSegmentFrames": longest_segment_frames,
        "continuityPreferredFrames": continuity_preferred_frames,
        "continuityRejectedFrames": continuity_rejected_frames,
        "midfieldCollapsedFrames": midfield_collapsed_frames,
    }


def _row_has_proposal_lineage(row):
    return bool(row.get("ProposalWindowKind")) or bool(row.get("ProposalSeedMode"))


def _row_has_reviewed_positive_proposal_lineage(row, *, required_prefix="reviewed_positive_"):
    prefix = str(required_prefix or "reviewed_positive_")
    return str(row.get("ProposalWindowKind") or "").startswith(prefix)


def _select_segment_viability_followthrough_rows(
    candidate_rows,
    *,
    player_rows=None,
    max_frame_gap=5,
    config=None,
):
    config = dict(config or {})
    if not candidate_rows:
        return []
    filtered_rows = []
    for row in candidate_rows:
        if bool(config.get("requireRealDetectedCandidateRows", True)) and bool(row.get("SyntheticBallRow")):
            continue
        if bool(config.get("requireProposalLineage", True)) and not _row_has_proposal_lineage(row):
            continue
        if bool(config.get("preserveRepeatedAnchorGuard", True)) and _proposal_candidate_repeated_anchor_suspicious(row):
            continue
        filtered_rows.append(row)
    if not filtered_rows:
        return []

    min_segment_frames = max(int(config.get("minSegmentFrames", MIN_RECOVERED_BALL_FRAMES)), 1)
    max_projected_edge_share = float(
        config.get("maxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
    )
    eligible_segments = []
    for segment in split_ball_rows_into_segments(filtered_rows, max_frame_gap=max_frame_gap):
        best_rows = _best_ball_rows_by_frame(segment)
        if len(best_rows) < min_segment_frames:
            continue
        if _edge_share_for_rows(best_rows) > max_projected_edge_share:
            continue
        anchor_summary = _summarize_recovered_ball_anchor_diagnostics(
            best_rows,
            player_rows=player_rows,
            max_frame_gap=max_frame_gap,
        )
        eligible_segments.append((best_rows, anchor_summary))
    if not eligible_segments:
        return []
    selected_rows, _anchor_summary = max(
        eligible_segments,
        key=lambda item: (
            len(item[0]),
            float(item[1].get("anchoredFrameCount", 0)),
            float(item[1].get("supportedFrameCount", 0)),
            -float(item[1].get("unsupportedEdgeFrameShare", 0.0)),
            sum(float(row.get("Conf", 0.0)) for row in item[0]) / max(len(item[0]), 1),
        ),
    )
    return selected_rows


def _segment_is_continuity_safe(segment):
    if len(segment) <= 1:
        return True
    ordered_rows = sorted(segment, key=lambda row: int(row["Frame_ID"]))
    for prior_row, row in zip(ordered_rows, ordered_rows[1:]):
        if not _proposal_candidate_continuity_ok(row, prior_row):
            return False
    return True


def _reviewed_positive_selection_trace_template(*, lineage_match):
    return {
        "reviewedPositiveLineageMatch": bool(lineage_match),
        "syntheticRowRejected": False,
        "repeatedAnchorRejected": False,
        "continuityRejected": False,
        "segmentLengthRejected": False,
        "edgeShareRejected": False,
        "edgeShareOverrideApplied": False,
        "selectedProfileRankingRejected": False,
        "edgeShareForSegment": None,
        "segmentFrameCount": None,
    }


def _set_reviewed_positive_selection_trace(row, **updates):
    trace = dict(
        row.get("SelectionGateTrace")
        or row.get("selectionGateTrace")
        or _reviewed_positive_selection_trace_template(
            lineage_match=_row_has_reviewed_positive_proposal_lineage(row)
        )
    )
    trace.update(updates)
    row["SelectionGateTrace"] = trace
    row["selectionGateTrace"] = trace
    return trace


def _select_reviewed_positive_selected_segment_rows(
    candidate_rows,
    *,
    player_rows=None,
    max_frame_gap=5,
    config=None,
):
    config = dict(config or {})
    if not candidate_rows:
        return []
    required_prefix = str(config.get("requiredProposalWindowKindPrefix") or "reviewed_positive_")
    filtered_rows = []
    allowed_frame_ids = {
        int(frame_id)
        for frame_id in config.get("frameIds", set())
    }
    for row in candidate_rows:
        lineage_match = _row_has_reviewed_positive_proposal_lineage(row, required_prefix=required_prefix)
        _set_reviewed_positive_selection_trace(
            row,
            reviewedPositiveLineageMatch=lineage_match,
        )
        if allowed_frame_ids and int(row.get("Frame_ID", -1)) not in allowed_frame_ids:
            _set_reviewed_positive_selection_trace(row, selectedProfileRankingRejected=True)
            continue
        if bool(config.get("requireRealDetectedCandidateRows", True)) and bool(row.get("SyntheticBallRow")):
            _set_reviewed_positive_selection_trace(row, syntheticRowRejected=True)
            continue
        if not lineage_match:
            continue
        if bool(config.get("preserveRepeatedAnchorGuard", True)) and _proposal_candidate_repeated_anchor_suspicious(row):
            _set_reviewed_positive_selection_trace(row, repeatedAnchorRejected=True)
            continue
        filtered_rows.append(row)
    if not filtered_rows:
        return []

    min_segment_frames = max(int(config.get("minSegmentFrames", 5)), 1)
    max_projected_edge_share = float(
        config.get("maxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
    )
    eligible_segments = []
    for segment in split_ball_rows_into_segments(filtered_rows, max_frame_gap=max_frame_gap):
        best_rows = _best_ball_rows_by_frame(segment)
        if len(best_rows) < min_segment_frames:
            for row in best_rows:
                _set_reviewed_positive_selection_trace(
                    row,
                    segmentLengthRejected=True,
                    segmentFrameCount=len(best_rows),
                )
            continue
        if bool(config.get("preserveContinuityGuard", True)) and not _segment_is_continuity_safe(best_rows):
            for row in best_rows:
                _set_reviewed_positive_selection_trace(
                    row,
                    continuityRejected=True,
                    segmentFrameCount=len(best_rows),
                )
            continue
        edge_share = _edge_share_for_rows(best_rows)
        if edge_share > max_projected_edge_share:
            if bool(config.get("ignoreEdgeShareGate", False)) and all(
                _row_has_reviewed_positive_proposal_lineage(
                    row,
                    required_prefix=required_prefix,
                )
                for row in best_rows
            ):
                for row in best_rows:
                    _set_reviewed_positive_selection_trace(
                        row,
                        edgeShareOverrideApplied=True,
                        edgeShareRejected=False,
                        edgeShareForSegment=round(float(edge_share), 3),
                        segmentFrameCount=len(best_rows),
                    )
            else:
                for row in best_rows:
                    _set_reviewed_positive_selection_trace(
                        row,
                        edgeShareRejected=True,
                        edgeShareOverrideApplied=False,
                        edgeShareForSegment=round(float(edge_share), 3),
                        segmentFrameCount=len(best_rows),
                    )
                continue
        else:
            for row in best_rows:
                _set_reviewed_positive_selection_trace(
                    row,
                    edgeShareOverrideApplied=False,
                    edgeShareForSegment=round(float(edge_share), 3),
                    segmentFrameCount=len(best_rows),
                )
        anchor_summary = _summarize_recovered_ball_anchor_diagnostics(
            best_rows,
            player_rows=player_rows,
            max_frame_gap=max_frame_gap,
        )
        eligible_segments.append((best_rows, anchor_summary))
    if not eligible_segments:
        return []
    selected_rows, _anchor_summary = max(
        eligible_segments,
        key=lambda item: (
            len(item[0]),
            float(item[1].get("anchoredFrameCount", 0)),
            float(item[1].get("supportedFrameCount", 0)),
            -float(item[1].get("unsupportedEdgeFrameShare", 0.0)),
            sum(float(row.get("Conf", 0.0)) for row in item[0]) / max(len(item[0]), 1),
        ),
    )
    for row in selected_rows:
        _set_reviewed_positive_selection_trace(
            row,
            selectedProfileRankingRejected=False,
        )
    return selected_rows


def _reviewed_positive_acceptance_profile_accepts_rows(
    rows,
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
):
    config = _touchline_reviewed_positive_acceptance_profile_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if config is None:
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_disabled",
        }
    selected_rows = _best_ball_rows_by_frame(rows or [])
    if len(selected_rows) < max(int(config.get("minSelectedFrames", 5)), 1):
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_segment_too_short",
        }
    required_prefix = str(config.get("requiredProposalWindowKindPrefix") or "reviewed_positive_")
    if not all(
        _row_has_reviewed_positive_proposal_lineage(row, required_prefix=required_prefix)
        for row in selected_rows
    ):
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_lineage_mismatch",
        }
    if bool(config.get("requireRealDetectedRows", True)) and any(
        bool(row.get("SyntheticBallRow")) for row in selected_rows
    ):
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_synthetic_row",
        }
    if bool(config.get("preserveRepeatedAnchorGuard", True)) and (
        any(_proposal_candidate_repeated_anchor_suspicious(row) for row in selected_rows)
        or _proposal_segment_reuses_static_source_box_as_seed(selected_rows)
    ):
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_repeated_anchor",
        }
    if bool(config.get("preserveContinuityGuard", True)) and not _segment_is_continuity_safe(selected_rows):
        return {
            "accepted": False,
            "reason": "reviewed_positive_acceptance_profile_continuity",
        }
    return {
        "accepted": True,
        "reason": "reviewed_positive_viability_override",
    }


def select_meaningful_recovered_ball_rows(
    rows,
    player_windows=None,
    player_rows=None,
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
):
    candidate_rows = filter_ball_rows_by_player_window_proximity(rows, player_windows)
    candidate_rows = suppress_repeated_false_ball_clusters(
        candidate_rows,
        player_windows=player_windows,
    )
    if not candidate_rows:
        return []

    candidate_rows = _collapse_recovered_ball_candidates(
        candidate_rows,
        player_rows=player_rows,
        max_frame_gap=5,
    )["rows"]

    accepted_segments = _select_viable_ball_segments(
        candidate_rows,
        player_rows=player_rows,
    )
    if accepted_segments:
        selected_rows = []
        seen_frames = set()
        for segment in accepted_segments:
            for row in segment["rows"]:
                frame_id = int(row["Frame_ID"])
                if frame_id in seen_frames:
                    continue
                seen_frames.add(frame_id)
                selected_rows.append(row)
        return selected_rows

    primary_rows = _best_ball_rows_by_frame(candidate_rows)
    if not primary_rows:
        return []

    primary_summary = summarize_ball_track_rows(primary_rows)
    if ball_track_summary_is_viable(primary_summary):
        return primary_rows

    center_x = sum(float(row["X"]) for row in primary_rows) / len(primary_rows)
    center_y = sum(float(row["Y"]) for row in primary_rows) / len(primary_rows)
    filtered_rows = [
        row
        for row in candidate_rows
        if hypot(float(row["X"]) - center_x, float(row["Y"]) - center_y) > STATIC_FALSE_BALL_RADIUS
    ]
    alternate_rows = _best_ball_rows_by_frame(filtered_rows)
    alternate_summary = summarize_ball_track_rows(alternate_rows)
    if ball_track_summary_is_viable(alternate_summary):
        return alternate_rows
    reviewed_positive_segment_config = _touchline_reviewed_positive_selected_segment_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if reviewed_positive_segment_config is not None:
        return _select_reviewed_positive_selected_segment_rows(
            candidate_rows,
            player_rows=player_rows,
            max_frame_gap=5,
            config=reviewed_positive_segment_config,
        )
    selection_segment_config = _touchline_selection_segment_viability_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if selection_segment_config is not None:
        return _select_segment_viability_followthrough_rows(
            candidate_rows,
            player_rows=player_rows,
            max_frame_gap=5,
            config=selection_segment_config,
        )
    return []


def suppress_repeated_false_ball_clusters(rows, player_windows=None):
    candidate_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not candidate_rows:
        return list(rows)

    primary_rows = _best_ball_rows_by_frame(candidate_rows)
    if len(primary_rows) < MIN_RECOVERED_BALL_FRAMES:
        return list(rows)

    candidate_summary = summarize_recovered_ball_candidates(
        candidate_rows,
        player_windows=player_windows,
    )
    dominant_anchor_coord = candidate_summary.get("dominantAnchorCoord")
    if dominant_anchor_coord is None:
        return list(rows)

    primary_summary = summarize_ball_track_rows(primary_rows)
    dominant_anchor_x, dominant_anchor_y = [float(value) for value in dominant_anchor_coord]
    dominant_anchor_is_on_edge = (
        dominant_anchor_x <= BALL_EDGE_MARGIN
        or dominant_anchor_x >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or dominant_anchor_y <= BALL_EDGE_MARGIN
        or dominant_anchor_y >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )
    repeated_anchor_is_suspicious = (
        float(candidate_summary.get("dominantAnchorShare", 0.0)) >= MIN_FALSE_BALL_DOMINANT_ANCHOR_SHARE
        and float(candidate_summary.get("edgeCandidateShare", 0.0)) >= MIN_FALSE_BALL_EDGE_CANDIDATE_SHARE
        and (
            float(primary_summary.get("edgeFrameShare", 0.0)) >= MIN_FALSE_BALL_EDGE_FRAME_SHARE
            or dominant_anchor_is_on_edge
        )
        and not bool(primary_summary.get("showsMeaningfulMotion"))
    )
    if not repeated_anchor_is_suspicious:
        return list(rows)

    filtered_rows = []
    for row in rows:
        if row.get("Entity_Type") != "ball":
            filtered_rows.append(row)
            continue
        if hypot(float(row["X"]) - dominant_anchor_x, float(row["Y"]) - dominant_anchor_y) > STATIC_FALSE_BALL_RADIUS:
            filtered_rows.append(row)
    return filtered_rows


def merge_missing_ball_rows(primary_rows, recovered_rows):
    primary_ball_frames = {
        int(row["Frame_ID"])
        for row in primary_rows
        if row.get("Entity_Type") == "ball"
    }
    missing_recovered_rows = [
        row
        for row in recovered_rows
        if int(row["Frame_ID"]) not in primary_ball_frames
    ]
    if not missing_recovered_rows:
        return list(primary_rows)

    merged_rows = list(primary_rows)
    merged_rows.extend(missing_recovered_rows)
    merged_rows.sort(
        key=lambda row: (
            int(row["Frame_ID"]),
            0 if row["Entity_Type"] == "ball" else 1,
            int(row["Track_ID"]),
        )
    )
    return merged_rows


def _source_box_is_too_close_to_crop_edge(source_box, crop_window, crop_edge_margin):
    if crop_window is None or crop_edge_margin <= 0:
        return False
    left, top, right, bottom = [float(value) for value in crop_window]
    x1, y1, x2, y2 = [float(value) for value in source_box]
    return (
        (x1 - left) < float(crop_edge_margin)
        or (y1 - top) < float(crop_edge_margin)
        or (right - x2) < float(crop_edge_margin)
        or (bottom - y2) < float(crop_edge_margin)
    )


def _source_box_center_is_too_low_in_crop(source_box, crop_window, max_crop_center_y_ratio):
    if crop_window is None or max_crop_center_y_ratio <= 0:
        return False
    left, top, right, bottom = [float(value) for value in crop_window]
    x1, y1, x2, y2 = [float(value) for value in source_box]
    crop_height = max(bottom - top, 1.0)
    center_y = (y1 + y2) / 2.0
    normalized_y = (center_y - top) / crop_height
    return normalized_y > float(max_crop_center_y_ratio)


def _pitch_polygon_rescue_distance(pitch_points, x, y):
    if not pitch_points:
        return None
    polygon = np.array(pitch_points, dtype=np.float32)
    return abs(float(cv2.pointPolygonTest(polygon, (float(x), float(y)), True)))


def _select_pitch_polygon_rescue_candidate(rescue_candidates):
    if not rescue_candidates:
        return None
    return max(
        rescue_candidates,
        key=lambda candidate: (
            float(candidate["Conf"]),
            -float(candidate["PitchPolygonBoundaryDistance"]),
            -int(candidate["OriginalIndex"]),
        ),
    )


def _ball_candidate_rows_for_frame(
    frame_id,
    timestamp,
    boxes,
    H,
    pitch_points,
    x_offset=0.0,
    y_offset=0.0,
    crop_window=None,
    crop_edge_margin=0,
    max_crop_center_y_ratio=0.0,
    proposal_seed_center=None,
    proposal_crop_size=None,
    proposal_window_kind=None,
    proposal_seed_mode=None,
    proposal_inference_mode=None,
    rescue_mode="none",
    source_clip_id=None,
    edge_share_repair_profile=None,
    frame_shape=None,
    detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL,
    return_diagnostics=False,
    pts=None,
    time_base=None,
):
    candidate_rows = []
    raw_ball_box_count = 0
    crop_edge_rejected_box_count = 0
    crop_center_y_rejected_box_count = 0
    pitch_polygon_rejected_box_count = 0
    pitch_polygon_rescue_eligible_rows = []
    reopened_raw_candidate_count = 0
    reopened_raw_candidate_frames = 0
    rescue_mode = str(rescue_mode or "none")
    for original_index, box in enumerate(boxes):
        cls = int(box.cls[0])
        if not detector_class_is_ball(cls, detector_profile):
            continue
        raw_ball_box_count += 1

        box_conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1 += x_offset
        x2 += x_offset
        y1 += y_offset
        y2 += y_offset
        source_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        touchline_candidate_admission_reopen_enabled = _touchline_candidate_admission_reopen_enabled(
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        )
        touchline_reopen_side = None
        if touchline_candidate_admission_reopen_enabled and frame_shape is not None:
            touchline_reopen_side = _touchline_adjacent_seed_side(frame_shape, proposal_seed_center)
            if touchline_reopen_side is None:
                touchline_reopen_side = _touchline_adjacent_seed_side(frame_shape, source_center)
            if (
                touchline_reopen_side is None
                and str(proposal_window_kind or "") in {
                    TOUCHLINE_ESCAPE_WINDOW_KIND,
                    TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND,
                }
            ):
                touchline_reopen_side = str(proposal_window_kind)

        reopen_reasons = []
        if _source_box_is_too_close_to_crop_edge(
            (x1, y1, x2, y2),
            crop_window,
            crop_edge_margin,
        ):
            crop_edge_rejected_box_count += 1
            if touchline_reopen_side is None:
                continue
            reopen_reasons.append("crop_edge_rejected")
        if _source_box_center_is_too_low_in_crop(
            (x1, y1, x2, y2),
            crop_window,
            max_crop_center_y_ratio,
        ):
            crop_center_y_rejected_box_count += 1
            continue
        cx, cy = projection_anchor_for_detection(cls, x1, y1, x2, y2, detector_profile=detector_profile)
        if not should_keep_detection_for_pitch(cls, cx, cy, pitch_points, detector_profile=detector_profile):
            pitch_polygon_rejected_box_count += 1
            if touchline_reopen_side is not None:
                reopen_reasons.append("pitch_polygon_rejected")
            elif rescue_mode != "none":
                boundary_distance = _pitch_polygon_rescue_distance(pitch_points, cx, cy)
                if boundary_distance is not None and (
                    rescue_mode == "direct_seed"
                    or (
                        rescue_mode == "primary_boundary"
                        and boundary_distance <= float(BALL_EDGE_MARGIN)
                    )
                ):
                    pitch_polygon_rescue_eligible_rows.append(
                        {
                            "OriginalIndex": int(original_index),
                            "Conf": box_conf,
                            "PitchPolygonBoundaryDistance": boundary_distance,
                            "SourceBox": (x1, y1, x2, y2),
                            "PitchAnchor": (cx, cy),
                        }
                    )
            if touchline_reopen_side is None:
                continue

        px, py = point_to_pitch(H, cx, cy)
        px = round(max(0, min(PITCH_WIDTH, px)), 2)
        py = round(max(0, min(PITCH_HEIGHT, py)), 2)
        candidate_row = build_tracking_row(
            frame_id=frame_id,
            timestamp=timestamp,
            entity_type="ball",
            track_id=-1,
            pitch_x=px,
            pitch_y=py,
            detection_conf=box_conf,
            source_box=(x1, y1, x2, y2),
            proposal_seed_center=proposal_seed_center,
            proposal_crop_size=proposal_crop_size,
            proposal_window_kind=proposal_window_kind,
            proposal_seed_mode=proposal_seed_mode,
            proposal_inference_mode=proposal_inference_mode,
            pts=pts,
            time_base=time_base,
        )
        if reopen_reasons:
            candidate_row["TouchlineRawCandidateReopened"] = True
            candidate_row["TouchlineRawCandidateReopenReason"] = (
                reopen_reasons[0] if len(reopen_reasons) == 1 else "multiple_rejects"
            )
            candidate_row["TouchlineRawCandidateReopenReasons"] = list(reopen_reasons)
            reopened_raw_candidate_count += 1
            reopened_raw_candidate_frames = 1
        candidate_rows.append(candidate_row)

    primary_pitch_polygon_rescue_eligible_count = len(pitch_polygon_rescue_eligible_rows)
    primary_pitch_polygon_rescue_eligible_frames = 1 if pitch_polygon_rescue_eligible_rows else 0
    primary_pitch_polygon_rescued_count = 0
    primary_pitch_polygon_rescued_frames = 0

    if not candidate_rows and pitch_polygon_rescue_eligible_rows:
        rescue_candidate = _select_pitch_polygon_rescue_candidate(pitch_polygon_rescue_eligible_rows)
        if rescue_candidate is not None:
            cx, cy = rescue_candidate["PitchAnchor"]
            x1, y1, x2, y2 = rescue_candidate["SourceBox"]
            px, py = point_to_pitch(H, cx, cy)
            px = round(max(0, min(PITCH_WIDTH, px)), 2)
            py = round(max(0, min(PITCH_HEIGHT, py)), 2)
            rescued_row = build_tracking_row(
                frame_id=frame_id,
                timestamp=timestamp,
                entity_type="ball",
                track_id=-1,
                pitch_x=px,
                pitch_y=py,
                detection_conf=float(rescue_candidate["Conf"]),
                source_box=(x1, y1, x2, y2),
                proposal_seed_center=proposal_seed_center,
                proposal_crop_size=proposal_crop_size,
                proposal_window_kind=proposal_window_kind,
                proposal_seed_mode=proposal_seed_mode,
                proposal_inference_mode=proposal_inference_mode,
                pts=pts,
                time_base=time_base,
            )
            rescued_row["PitchPolygonRescueMode"] = rescue_mode
            if rescue_mode == "primary_boundary":
                rescued_row["PrimaryPitchPolygonRescued"] = True
            candidate_rows.append(rescued_row)
            primary_pitch_polygon_rescued_count = 1
            primary_pitch_polygon_rescued_frames = 1

    if return_diagnostics:
        return candidate_rows, {
            "rawClass32BoxCount": raw_ball_box_count,
            "cropEdgeRejectedBoxCount": crop_edge_rejected_box_count,
            "cropCenterYRejectedBoxCount": crop_center_y_rejected_box_count,
            "pitchPolygonRejectedBoxCount": pitch_polygon_rejected_box_count,
            "candidateRowCount": len(candidate_rows),
            "primaryPitchPolygonRescueEligibleCount": primary_pitch_polygon_rescue_eligible_count,
            "primaryPitchPolygonRescueEligibleFrames": primary_pitch_polygon_rescue_eligible_frames,
            "primaryPitchPolygonRescuedCount": primary_pitch_polygon_rescued_count,
            "primaryPitchPolygonRescuedFrames": primary_pitch_polygon_rescued_frames,
            "reopenedRawCandidateCount": reopened_raw_candidate_count,
            "reopenedRawCandidateFrames": reopened_raw_candidate_frames,
        }
    return candidate_rows


def _source_box_area(row):
    if not all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
        return 0.0
    return max(float(row["Source_X2"]) - float(row["Source_X1"]), 0.0) * max(
        float(row["Source_Y2"]) - float(row["Source_Y1"]),
        0.0,
    )


def _mean_or_zero(values):
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _empty_direct_seed_attempt_diagnostics():
    return {
        "rawClass32BoxCount": 0,
        "cropEdgeRejectedBoxCount": 0,
        "cropCenterYRejectedBoxCount": 0,
        "pitchPolygonRejectedBoxCount": 0,
        "candidateRowCount": 0,
        "hadRawBallDetection": False,
        "hadCandidateRows": False,
        "elapsedSeconds": 0.0,
    }


def _empty_direct_seed_inference_diagnostics():
    return {
        "proposalDirectSeedHiResRetryFrames": 0,
        "proposalDirectSeedHiResRetryDetectedFrames": 0,
        "proposalDirectSeedZeroDetectFrames": 0,
        "proposalDirectSeedScale1600AttemptFrames": 0,
        "proposalDirectSeedScale960AttemptFrames": 0,
        "proposalDirectSeedScale1920AttemptFrames": 0,
        "proposalDirectSeedScale1600RawDetectionFrames": 0,
        "proposalDirectSeedScale960RawDetectionFrames": 0,
        "proposalDirectSeedScale1920RawDetectionFrames": 0,
        "proposalDirectSeedScale1600CandidateFrames": 0,
        "proposalDirectSeedScale960CandidateFrames": 0,
        "proposalDirectSeedScale1920CandidateFrames": 0,
        "proposalDirectSeedScale1600ElapsedSeconds": 0.0,
        "proposalDirectSeedScale960ElapsedSeconds": 0.0,
        "proposalDirectSeedScale1920ElapsedSeconds": 0.0,
        "proposalDirectSeedFallbackElapsedSeconds": 0.0,
        "proposalDirectSeedMultiScaleRetryFrames": 0,
        "proposalDirectSeedMultiScaleDetectedFrames": 0,
        "proposalDirectSeedRawHitFilteredOutFrames": 0,
        "proposalDirectSeedCropEdgeRejectedFrames": 0,
        "proposalDirectSeedCropCenterYRejectedFrames": 0,
        "proposalDirectSeedPitchPolygonRejectedFrames": 0,
        "primaryPitchPolygonRescueEligibleCount": 0,
        "primaryPitchPolygonRescueEligibleFrames": 0,
        "primaryPitchPolygonRescuedCount": 0,
        "primaryPitchPolygonRescuedFrames": 0,
        "proposalDirectSeedMeanCropArea": 0.0,
        "proposalDirectSeedTightMeanCropArea": 0.0,
        "proposalDirectSeedContextMeanCropArea": 0.0,
        "proposalTouchlineEscapeMeanCropArea": 0.0,
        "proposalPlayerRankedMeanCropArea": 0.0,
        "proposalDirectSeedMeanDetectedBallBoxArea": 0.0,
        "proposalTouchlineEscapeMeanDetectedBallBoxArea": 0.0,
        "proposalPlayerRankedMeanDetectedBallBoxArea": 0.0,
        "proposalTouchlineEscapeDetectedFrames": 0,
    }


def _v7_3_crop_windows(proposals):
    """Reuse proposal centers at the source scales used by the v7.3 export."""
    windows = []
    seen = set()
    for proposal in proposals:
        if proposal is None:
            continue
        spec = proposal if isinstance(proposal, dict) else {"window": proposal}
        center = spec.get("proposalSeedCenter") if spec.get("proposalWindowKind") == "direct_seed_tight" else None
        cx, cy = center or _window_center(spec["window"])
        for size in V7_3_SOURCE_CROP_SIZES:
            left, top = int(round(cx - size / 2)), int(round(cy - size / 2))
            window = (left, top, left + size, top + size)
            if window not in seen:
                seen.add(window)
                windows.append({**spec, "window": window})
    return windows


def _padded_source_crop(frame, window):
    """Keep source offsets at frame edges; v7.3 training uses zero padding."""
    left, top, right, bottom = window
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = max(0, left), max(0, top), min(width, right), min(height, bottom)
    if x1 >= x2 or y1 >= y2:
        return None
    crop = np.zeros((bottom - top, right - left, *frame.shape[2:]), dtype=frame.dtype)
    crop[y1 - top:y2 - top, x1 - left:x2 - left] = frame[y1:y2, x1:x2]
    return crop


def recover_ball_rows(
    video_path,
    model,
    H,
    pitch_points,
    fps,
    frame_interval,
    player_windows=None,
    crop_windows_by_frame=None,
    recovery_imgsz=None,
    recovery_conf=None,
    crop_edge_margin=0,
    max_crop_center_y_ratio=0.0,
    max_crop_width_ratio=0.0,
    dedupe_same_frame=True,
    return_diagnostics=False,
    direct_seed_retry_policy=DIRECT_SEED_RETRY_POLICY,
    direct_seed_retry_scales=DIRECT_SEED_RETRY_SCALES,
    progress_callback=None,
    progress_interval_seconds=30.0,
    progress_context=None,
    source_clip_id=None,
    edge_share_repair_profile=None,
    detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL,
    calibrations=None,
    frame_source=None,
):
    crop_detector = _normalize_detector_profile(detector_profile) == DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3
    if crop_detector:
        recovery_imgsz, recovery_conf = 256, 0.1
        direct_seed_retry_scales = (256,)
    calibration_index = 0
    ball_classes = detector_ball_class_ids(detector_profile)
    if not ball_classes:
        empty_rows = []
        if return_diagnostics:
            return empty_rows, _empty_direct_seed_inference_diagnostics()
        return empty_rows
    from backend.app.workbench.media import OpenCvFrameSource, iter_bgr_frames, pixels_from_decoded_frame

    decode_adapter = frame_source or OpenCvFrameSource(cv2_module=cv2)
    identity = decode_adapter.probe(Path(str(video_path)))
    if "opencv_open_failed" in identity.decodeErrors:
        empty_rows = []
        if return_diagnostics:
            return empty_rows, _empty_direct_seed_inference_diagnostics()
        return empty_rows

    prediction_settings = resolve_ball_recovery_settings(
        TRACKING_IMGSZ,
        TRACKING_CONF,
        recovery_imgsz=recovery_imgsz,
        recovery_conf=recovery_conf,
    )
    if crop_detector:
        prediction_settings = {"imgsz": 256, "conf": 0.1}
    base_direct_seed_scale = int(prediction_settings["imgsz"])
    normalized_direct_seed_retry_scales = []
    for scale in direct_seed_retry_scales or DIRECT_SEED_RETRY_SCALES:
        try:
            normalized_scale = int(scale)
        except (TypeError, ValueError):
            continue
        if normalized_scale not in normalized_direct_seed_retry_scales:
            normalized_direct_seed_retry_scales.append(normalized_scale)
    if base_direct_seed_scale not in normalized_direct_seed_retry_scales:
        normalized_direct_seed_retry_scales.insert(0, base_direct_seed_scale)
    diagnostic_scales = []
    for scale in (
        base_direct_seed_scale,
        *normalized_direct_seed_retry_scales,
        BALL_RECOVERY_IMGSZ,
        DIRECT_SEED_HI_RES_RETRY_IMGSZ,
        DIRECT_SEED_SCALE_1920_RETRY_IMGSZ,
    ):
        if int(scale) not in diagnostic_scales:
            diagnostic_scales.append(int(scale))

    recovered_rows = []
    frame_count = 0
    last_sample_presentation_time = None
    grid_origin_presentation_time = None
    last_sample_pts = None
    grid_origin_pts = None
    direct_seed_retry_frames = set()
    direct_seed_retry_detected_frames = set()
    direct_seed_multi_scale_retry_frames = set()
    direct_seed_multi_scale_detected_frames = set()
    direct_seed_frames = set()
    direct_seed_detected_frames = set()
    direct_seed_raw_hit_filtered_out_frames = set()
    direct_seed_crop_edge_rejected_frames = set()
    direct_seed_crop_center_y_rejected_frames = set()
    direct_seed_pitch_polygon_rejected_frames = set()
    primary_pitch_polygon_rescue_eligible_frames = set()
    primary_pitch_polygon_rescued_frames = set()
    primary_pitch_polygon_rescue_eligible_count = 0
    primary_pitch_polygon_rescued_count = 0
    direct_seed_scale_raw_detection_frames = {scale: set() for scale in diagnostic_scales}
    direct_seed_scale_attempt_frames = {scale: set() for scale in diagnostic_scales}
    direct_seed_scale_candidate_frames = {scale: set() for scale in diagnostic_scales}
    direct_seed_scale_elapsed_seconds = {scale: 0.0 for scale in diagnostic_scales}
    direct_seed_fallback_elapsed_seconds = 0.0
    direct_seed_crop_areas = []
    direct_seed_tight_crop_areas = []
    direct_seed_context_crop_areas = []
    touchline_escape_crop_areas = []
    player_ranked_crop_areas = []
    direct_seed_detected_box_areas = []
    touchline_escape_detected_box_areas = []
    player_ranked_detected_box_areas = []
    touchline_escape_detected_frames = set()
    touchline_inboard_detected_frames = set()
    reopened_raw_candidate_frames = set()
    progress_context_payload = dict(progress_context or {})
    last_progress_at = time.monotonic()

    def _scale_diagnostic_key(scale, suffix):
        return f"proposalDirectSeedScale{int(scale)}{suffix}"

    def _scale_diagnostic_payload():
        payload = {}
        for scale in sorted(direct_seed_scale_attempt_frames):
            payload[_scale_diagnostic_key(scale, "AttemptFrames")] = len(
                direct_seed_scale_attempt_frames[scale]
            )
            payload[_scale_diagnostic_key(scale, "RawDetectionFrames")] = len(
                direct_seed_scale_raw_detection_frames[scale]
            )
            payload[_scale_diagnostic_key(scale, "CandidateFrames")] = len(
                direct_seed_scale_candidate_frames[scale]
            )
            payload[_scale_diagnostic_key(scale, "ElapsedSeconds")] = round(
                direct_seed_scale_elapsed_seconds[scale],
                3,
            )
        return payload

    def _direct_seed_inference_mode_for_scale(scale):
        scale = int(scale)
        if scale == DIRECT_SEED_HI_RES_RETRY_IMGSZ:
            return "hi_res_retry"
        if scale == DIRECT_SEED_SCALE_1920_RETRY_IMGSZ:
            return "scale_1920_retry"
        return f"scale_{scale}_retry"

    def _build_progress_payload():
        return {
            **progress_context_payload,
            "proposalDirectSeedScale1600AttemptFrames": len(
                direct_seed_scale_attempt_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960AttemptFrames": len(
                direct_seed_scale_attempt_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920AttemptFrames": len(
                direct_seed_scale_attempt_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600CandidateFrames": len(
                direct_seed_scale_candidate_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960CandidateFrames": len(
                direct_seed_scale_candidate_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920CandidateFrames": len(
                direct_seed_scale_candidate_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[BALL_RECOVERY_IMGSZ], 3
            ),
            "proposalDirectSeedScale960ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[DIRECT_SEED_HI_RES_RETRY_IMGSZ], 3
            ),
            "proposalDirectSeedScale1920ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ], 3
            ),
            "proposalDirectSeedFallbackElapsedSeconds": round(
                direct_seed_fallback_elapsed_seconds, 3
            ),
            "proposalDirectSeedMultiScaleRetryFrames": len(direct_seed_multi_scale_retry_frames),
            "proposalDirectSeedMultiScaleDetectedFrames": len(direct_seed_multi_scale_detected_frames),
            "proposalDirectSeedRawHitFilteredOutFrames": len(direct_seed_raw_hit_filtered_out_frames),
            "proposalDirectSeedCropEdgeRejectedFrames": len(direct_seed_crop_edge_rejected_frames),
            "proposalDirectSeedCropCenterYRejectedFrames": len(direct_seed_crop_center_y_rejected_frames),
            "proposalDirectSeedPitchPolygonRejectedFrames": len(direct_seed_pitch_polygon_rejected_frames),
            "primaryPitchPolygonRescueEligibleCount": primary_pitch_polygon_rescue_eligible_count,
            "primaryPitchPolygonRescueEligibleFrames": len(primary_pitch_polygon_rescue_eligible_frames),
            "primaryPitchPolygonRescuedCount": primary_pitch_polygon_rescued_count,
            "primaryPitchPolygonRescuedFrames": len(primary_pitch_polygon_rescued_frames),
            **_scale_diagnostic_payload(),
        }

    def _emit_progress(stage_status="profile_in_progress", *, force=False):
        nonlocal last_progress_at
        if progress_callback is None:
            return
        now = time.monotonic()
        if not force and now - last_progress_at < float(progress_interval_seconds or 0.0):
            return
        try:
            progress_callback({"stageStatus": stage_status, **_build_progress_payload()})
            last_progress_at = now
        except Exception:
            return

    from backend.app.workbench.media import presentation_seconds_or_none, should_sample_on_source_grid

    sample_fps = float(fps or identity.nominalFps or 0.0) or None
    for decoded in iter_bgr_frames(Path(str(video_path)), decode_adapter, cv2_module=cv2):
        frame = pixels_from_decoded_frame(decoded)
        if frame is None:
            frame_count += 1
            continue
        presentation = presentation_seconds_or_none(decoded)
        if grid_origin_presentation_time is None and presentation is not None:
            grid_origin_presentation_time = presentation
        if grid_origin_pts is None and decoded.pts is not None:
            grid_origin_pts = decoded.pts
        if should_sample_on_source_grid(
            decoded,
            frame_count=frame_count,
            frame_interval=frame_interval,
            last_sample_presentation_time=last_sample_presentation_time,
            fps=sample_fps,
            grid_origin_presentation_time=grid_origin_presentation_time,
            last_sample_pts=last_sample_pts,
            grid_origin_pts=grid_origin_pts,
        ):
            last_sample_presentation_time = presentation
            last_sample_pts = decoded.pts
            timestamp = (
                last_sample_presentation_time
                if last_sample_presentation_time is not None
                else frame_count / (sample_fps or 1.0)
            )
            if calibrations:
                while calibration_index + 1 < len(calibrations) and calibrations[calibration_index + 1][0] <= frame_count:
                    calibration_index += 1
                _, H, pitch_points = calibrations[calibration_index]
            crop_windows = []
            if crop_windows_by_frame is not None and frame_count in crop_windows_by_frame:
                crop_windows = _normalize_crop_windows_for_frame(crop_windows_by_frame.get(frame_count))
            elif player_windows is not None:
                crop_window = ball_recovery_crop_window(
                    frame.shape,
                    player_windows.get(frame_count),
                    max_crop_width_ratio=max_crop_width_ratio,
                )
                crop_windows = [crop_window] if crop_window is not None else []
            if not crop_windows:
                crop_windows = [None]
            if crop_detector:
                crop_windows = _v7_3_crop_windows(crop_windows)
            for crop_window_spec in crop_windows:
                proposal_seed_center = None
                proposal_window_kind = None
                proposal_seed_mode = None
                rescue_mode = "none"
                if isinstance(crop_window_spec, dict):
                    crop_window = crop_window_spec.get("window")
                    seed_center = crop_window_spec.get("proposalSeedCenter")
                    if isinstance(seed_center, (list, tuple)) and len(seed_center) == 2:
                        proposal_seed_center = (float(seed_center[0]), float(seed_center[1]))
                    proposal_window_kind = crop_window_spec.get("proposalWindowKind")
                    proposal_seed_mode = crop_window_spec.get("proposalSeedMode")
                else:
                    crop_window = crop_window_spec
                if _proposal_window_kind_is_anchor_seeded(proposal_window_kind):
                    rescue_mode = "direct_seed"
                elif proposal_window_kind is None:
                    rescue_mode = "primary_boundary"
                if crop_window is not None:
                    crop_window = (
                        int(round(float(crop_window[0]))),
                        int(round(float(crop_window[1]))),
                        int(round(float(crop_window[2]))),
                        int(round(float(crop_window[3]))),
                    )
                prediction_frame = frame
                x_offset = 0.0
                y_offset = 0.0
                if crop_window is not None:
                    left, top, right, bottom = crop_window
                    prediction_frame = _padded_source_crop(frame, crop_window) if crop_detector else frame[top:bottom, left:right]
                    if prediction_frame is None or prediction_frame.size == 0:
                        continue
                    x_offset = float(left)
                    y_offset = float(top)
                    crop_area = max(float(right) - float(left), 0.0) * max(float(bottom) - float(top), 0.0)
                    if _proposal_window_kind_is_direct_seed(proposal_window_kind):
                        direct_seed_frames.add(frame_count)
                        direct_seed_crop_areas.append(crop_area)
                        if str(proposal_window_kind or "") == "direct_seed_tight":
                            direct_seed_tight_crop_areas.append(crop_area)
                        elif str(proposal_window_kind or "") == "direct_seed_context":
                            direct_seed_context_crop_areas.append(crop_area)
                    elif str(proposal_window_kind or "") == TOUCHLINE_ESCAPE_WINDOW_KIND:
                        touchline_escape_crop_areas.append(crop_area)
                    elif str(proposal_window_kind or "") == "player_ranked":
                        player_ranked_crop_areas.append(crop_area)

                def _predict_candidate_rows(
                    *,
                    imgsz,
                    inference_mode,
                    prediction_frame=prediction_frame,
                    frame_count=frame_count,
                    timestamp=timestamp,
                    H=H,
                    pitch_points=pitch_points,
                    x_offset=x_offset,
                    y_offset=y_offset,
                    crop_window=crop_window,
                    proposal_seed_center=proposal_seed_center,
                    proposal_seed_mode=proposal_seed_mode,
                    proposal_window_kind=proposal_window_kind,
                    rescue_mode=rescue_mode,
                    frame=frame,
                    decoded=decoded,
                ):
                    attempt_started_at = time.monotonic()
                    prediction = model.predict(
                        prediction_frame,
                        imgsz=imgsz,
                        conf=prediction_settings["conf"],
                        classes=ball_classes,
                        verbose=False,
                    )[0]
                    boxes = prediction.boxes
                    if boxes is None:
                        return [], _empty_direct_seed_attempt_diagnostics()
                    candidate_boxes = list(boxes)
                    candidate_rows, attempt_diagnostics = _ball_candidate_rows_for_frame(
                        frame_count,
                        timestamp,
                        candidate_boxes,
                        H,
                        pitch_points,
                        x_offset=x_offset,
                        y_offset=y_offset,
                        crop_window=crop_window,
                        crop_edge_margin=crop_edge_margin,
                        max_crop_center_y_ratio=max_crop_center_y_ratio,
                        proposal_seed_center=proposal_seed_center
                        if proposal_seed_center is not None
                        else (_window_center(crop_window) if crop_window is not None and proposal_seed_mode != "none" else None),
                        proposal_crop_size=(
                            float(crop_window[2]) - float(crop_window[0]),
                            float(crop_window[3]) - float(crop_window[1]),
                        )
                        if crop_window is not None
                        else None,
                        proposal_window_kind=proposal_window_kind,
                        proposal_seed_mode=proposal_seed_mode,
                        proposal_inference_mode=inference_mode,
                        rescue_mode=rescue_mode,
                        source_clip_id=source_clip_id,
                        edge_share_repair_profile=edge_share_repair_profile,
                        frame_shape=frame.shape,
                        detector_profile=detector_profile,
                        return_diagnostics=True,
                        pts=decoded.pts,
                        time_base=decoded.time_base,
                    )
                    attempt_diagnostics["elapsedSeconds"] = round(time.monotonic() - attempt_started_at, 6)
                    attempt_diagnostics["hadRawBallDetection"] = attempt_diagnostics["rawClass32BoxCount"] > 0
                    attempt_diagnostics["hadCandidateRows"] = bool(candidate_rows)
                    return candidate_rows, attempt_diagnostics

                candidate_rows, base_attempt_diagnostics = _predict_candidate_rows(
                    imgsz=prediction_settings["imgsz"],
                    inference_mode="base",
                )
                direct_seed_attempts = [(prediction_settings["imgsz"], base_attempt_diagnostics)]
                if _proposal_window_kind_is_anchor_seeded(proposal_window_kind):
                    if not base_attempt_diagnostics["hadRawBallDetection"]:
                        direct_seed_retry_frames.add(frame_count)
                        direct_seed_multi_scale_retry_frames.add(frame_count)
                        for retry_scale in normalized_direct_seed_retry_scales:
                            retry_scale = int(retry_scale)
                            if retry_scale == int(prediction_settings["imgsz"]):
                                continue
                            candidate_rows, retry_diagnostics = _predict_candidate_rows(
                                imgsz=retry_scale,
                                inference_mode=_direct_seed_inference_mode_for_scale(retry_scale),
                            )
                            direct_seed_attempts.append((retry_scale, retry_diagnostics))
                            if retry_diagnostics["hadCandidateRows"]:
                                if retry_scale == DIRECT_SEED_HI_RES_RETRY_IMGSZ:
                                    direct_seed_retry_detected_frames.add(frame_count)
                                direct_seed_multi_scale_detected_frames.add(frame_count)
                            if retry_diagnostics["hadRawBallDetection"]:
                                break

                    had_raw_detection_after_any_attempt = False
                    for attempt_scale, attempt_diagnostics in direct_seed_attempts:
                        if attempt_scale in direct_seed_scale_attempt_frames:
                            direct_seed_scale_attempt_frames[attempt_scale].add(frame_count)
                            direct_seed_scale_elapsed_seconds[attempt_scale] += float(
                                attempt_diagnostics.get("elapsedSeconds", 0.0)
                            )
                        direct_seed_fallback_elapsed_seconds += float(
                            attempt_diagnostics.get("elapsedSeconds", 0.0)
                        )
                        if attempt_diagnostics["hadRawBallDetection"]:
                            had_raw_detection_after_any_attempt = True
                            if attempt_scale in direct_seed_scale_raw_detection_frames:
                                direct_seed_scale_raw_detection_frames[attempt_scale].add(frame_count)
                    if attempt_diagnostics["hadCandidateRows"] and attempt_scale in direct_seed_scale_candidate_frames:
                        direct_seed_scale_candidate_frames[attempt_scale].add(frame_count)
                    if attempt_diagnostics["cropEdgeRejectedBoxCount"] > 0:
                        direct_seed_crop_edge_rejected_frames.add(frame_count)
                    if attempt_diagnostics["cropCenterYRejectedBoxCount"] > 0:
                        direct_seed_crop_center_y_rejected_frames.add(frame_count)
                    if attempt_diagnostics["pitchPolygonRejectedBoxCount"] > 0:
                        direct_seed_pitch_polygon_rejected_frames.add(frame_count)
                    if rescue_mode == "primary_boundary":
                        primary_pitch_polygon_rescue_eligible_count += int(
                            attempt_diagnostics.get("primaryPitchPolygonRescueEligibleCount", 0)
                        )
                        primary_pitch_polygon_rescued_count += int(
                            attempt_diagnostics.get("primaryPitchPolygonRescuedCount", 0)
                        )
                        if attempt_diagnostics.get("primaryPitchPolygonRescueEligibleCount", 0) > 0:
                            primary_pitch_polygon_rescue_eligible_frames.add(frame_count)
                        if attempt_diagnostics.get("primaryPitchPolygonRescuedCount", 0) > 0:
                            primary_pitch_polygon_rescued_frames.add(frame_count)
                    if had_raw_detection_after_any_attempt and not candidate_rows:
                        direct_seed_raw_hit_filtered_out_frames.add(frame_count)
                if _proposal_window_kind_is_direct_seed(proposal_window_kind) and candidate_rows:
                    direct_seed_detected_frames.add(frame_count)
                if str(proposal_window_kind or "") == TOUCHLINE_ESCAPE_WINDOW_KIND and candidate_rows:
                    touchline_escape_detected_frames.add(frame_count)
                if str(proposal_window_kind or "") == TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND and candidate_rows:
                    touchline_inboard_detected_frames.add(frame_count)
                if any(bool(row.get("TouchlineRawCandidateReopened")) for row in candidate_rows):
                    reopened_raw_candidate_frames.add(frame_count)
                if str(proposal_window_kind or "") == "player_ranked" and candidate_rows:
                    player_ranked_detected_box_areas.extend(
                        _source_box_area(row) for row in candidate_rows if _source_box_area(row) > 0.0
                    )
                if _proposal_window_kind_is_direct_seed(proposal_window_kind) and candidate_rows:
                    direct_seed_detected_box_areas.extend(
                        _source_box_area(row) for row in candidate_rows if _source_box_area(row) > 0.0
                    )
                if str(proposal_window_kind or "") == TOUCHLINE_ESCAPE_WINDOW_KIND and candidate_rows:
                    touchline_escape_detected_box_areas.extend(
                        _source_box_area(row) for row in candidate_rows if _source_box_area(row) > 0.0
                    )
                recovered_rows.extend(candidate_rows)
                if _proposal_window_kind_is_anchor_seeded(proposal_window_kind):
                    _emit_progress()
        frame_count += 1

    if dedupe_same_frame:
        recovered_rows = _dedupe_same_frame_recovered_rows(recovered_rows)

    _emit_progress(force=True)

    if return_diagnostics:
        return recovered_rows, {
            "proposalDirectSeedHiResRetryFrames": len(direct_seed_retry_frames),
            "proposalDirectSeedHiResRetryDetectedFrames": len(direct_seed_retry_detected_frames),
            "proposalDirectSeedZeroDetectFrames": len(direct_seed_frames - direct_seed_detected_frames),
            "proposalDirectSeedScale1600AttemptFrames": len(
                direct_seed_scale_attempt_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960AttemptFrames": len(
                direct_seed_scale_attempt_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920AttemptFrames": len(
                direct_seed_scale_attempt_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920RawDetectionFrames": len(
                direct_seed_scale_raw_detection_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600CandidateFrames": len(
                direct_seed_scale_candidate_frames[BALL_RECOVERY_IMGSZ]
            ),
            "proposalDirectSeedScale960CandidateFrames": len(
                direct_seed_scale_candidate_frames[DIRECT_SEED_HI_RES_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1920CandidateFrames": len(
                direct_seed_scale_candidate_frames[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ]
            ),
            "proposalDirectSeedScale1600ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[BALL_RECOVERY_IMGSZ], 3
            ),
            "proposalDirectSeedScale960ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[DIRECT_SEED_HI_RES_RETRY_IMGSZ], 3
            ),
            "proposalDirectSeedScale1920ElapsedSeconds": round(
                direct_seed_scale_elapsed_seconds[DIRECT_SEED_SCALE_1920_RETRY_IMGSZ], 3
            ),
            "proposalDirectSeedFallbackElapsedSeconds": round(direct_seed_fallback_elapsed_seconds, 3),
            "proposalDirectSeedMultiScaleRetryFrames": len(direct_seed_multi_scale_retry_frames),
            "proposalDirectSeedMultiScaleDetectedFrames": len(direct_seed_multi_scale_detected_frames),
            "proposalDirectSeedRawHitFilteredOutFrames": len(direct_seed_raw_hit_filtered_out_frames),
            "proposalDirectSeedCropEdgeRejectedFrames": len(direct_seed_crop_edge_rejected_frames),
            "proposalDirectSeedCropCenterYRejectedFrames": len(direct_seed_crop_center_y_rejected_frames),
            "proposalDirectSeedPitchPolygonRejectedFrames": len(direct_seed_pitch_polygon_rejected_frames),
            "proposalDirectSeedMeanCropArea": _mean_or_zero(direct_seed_crop_areas),
            "proposalDirectSeedTightMeanCropArea": _mean_or_zero(direct_seed_tight_crop_areas),
            "proposalDirectSeedContextMeanCropArea": _mean_or_zero(direct_seed_context_crop_areas),
            "proposalTouchlineEscapeMeanCropArea": _mean_or_zero(touchline_escape_crop_areas),
            "proposalPlayerRankedMeanCropArea": _mean_or_zero(player_ranked_crop_areas),
            "proposalDirectSeedMeanDetectedBallBoxArea": _mean_or_zero(direct_seed_detected_box_areas),
            "proposalTouchlineEscapeMeanDetectedBallBoxArea": _mean_or_zero(touchline_escape_detected_box_areas),
            "proposalPlayerRankedMeanDetectedBallBoxArea": _mean_or_zero(player_ranked_detected_box_areas),
            "proposalTouchlineEscapeDetectedFrames": len(touchline_escape_detected_frames),
            "proposalTouchlineInboardDetectedFrames": len(touchline_inboard_detected_frames),
            "proposalReopenedRawCandidateFrames": len(reopened_raw_candidate_frames),
            **_scale_diagnostic_payload(),
        }
    return recovered_rows


def _proposal_seed_center_for_row(row):
    if row.get("ProposalSeedMode") == "none":
        return None
    if "ProposalSeedX" in row and "ProposalSeedY" in row:
        return float(row["ProposalSeedX"]), float(row["ProposalSeedY"])
    return _row_source_box_center(row) or (
        (float(row["X"]), float(row["Y"])) if "X" in row and "Y" in row else None
    )


def _proposal_row_is_anchored(row):
    proposal_seed_center = _proposal_seed_center_for_row(row)
    source_center = _row_source_box_center(row)
    if proposal_seed_center is None or source_center is None:
        return False

    anchored_limit = max(
        float(row.get("ProposalCropWidth", 0.0)),
        float(row.get("ProposalCropHeight", 0.0)),
    ) / 2.0
    if anchored_limit <= 0:
        source_box = _row_source_box(row)
        if source_box is not None:
            anchored_limit = max(
                float(source_box[2]) - float(source_box[0]),
                float(source_box[3]) - float(source_box[1]),
            ) / 2.0
    if anchored_limit <= 0:
        return False
    return hypot(
        float(source_center[0]) - float(proposal_seed_center[0]),
        float(source_center[1]) - float(proposal_seed_center[1]),
    ) <= anchored_limit


def _proposal_candidate_repeated_anchor_suspicious(row):
    proposal_seed_center = _proposal_seed_center_for_row(row)
    source_center = _row_source_box_center(row)
    if proposal_seed_center is None or source_center is None:
        return False
    if not _ball_row_is_edge(row):
        return False
    return hypot(
        float(source_center[0]) - float(proposal_seed_center[0]),
        float(source_center[1]) - float(proposal_seed_center[1]),
    ) <= float(STATIC_FALSE_BALL_RADIUS * 4.0)


def _proposal_segment_reuses_static_source_box_as_seed(rows):
    repeated_centers = []
    for row in rows or []:
        proposal_seed_center = _proposal_seed_center_for_row(row)
        source_center = _row_source_box_center(row)
        if proposal_seed_center is None or source_center is None:
            continue
        if hypot(
            float(source_center[0]) - float(proposal_seed_center[0]),
            float(source_center[1]) - float(proposal_seed_center[1]),
        ) <= float(STATIC_FALSE_BALL_RADIUS * 4.0):
            repeated_centers.append(
                (
                    round(float(source_center[0]), 2),
                    round(float(source_center[1]), 2),
                )
            )
    return len(repeated_centers) >= 2 and len(set(repeated_centers)) == 1


def _proposal_candidate_continuity_ok(row, prior_row):
    if prior_row is None:
        return True
    return hypot(
        float(row["X"]) - float(prior_row["X"]),
        float(row["Y"]) - float(prior_row["Y"]),
    ) <= float(MAX_COHERENT_BALL_STEP_DISTANCE)


def _proposal_candidate_viability_proxy(row, player_rows_by_frame):
    return (
        _proposal_row_is_anchored(row)
        or _ball_row_is_player_supported(row, player_rows_by_frame)
        or not _ball_row_is_edge(row)
    )


def _proposal_candidate_viability_class(row, player_rows_by_frame):
    anchored = _proposal_row_is_anchored(row)
    supported = _ball_row_is_player_supported(row, player_rows_by_frame)
    non_edge = not _ball_row_is_edge(row)
    if non_edge and (anchored or supported):
        return 2
    if anchored or supported or non_edge:
        return 1
    return 0


def _edge_share_for_rows(rows):
    if not rows:
        return 0.0
    edge_rows = sum(1 for row in rows if _ball_row_is_edge(row))
    return round(edge_rows / len(rows), 3)


def _collapse_proposal_recovered_ball_candidates(
    rows,
    player_rows=None,
    max_frame_gap=5,
    *,
    source_clip_id=None,
    edge_share_repair_profile=None,
    proposal_selection_truth_seed_path=None,
):
    candidate_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
    if not candidate_rows:
        return {
            "rows": list(rows),
            "proposalRawDetectedFrames": 0,
            "proposalAfterSeedCollapseFrames": 0,
            "proposalAfterPlayerWindowFrames": 0,
            "proposalAfterFalseBallSuppressionFrames": 0,
            "proposalCollapsedFrames": 0,
            "proposalCollapsedSegmentCount": 0,
            "proposalCollapsedLongestSegmentFrames": 0,
            "proposalDirectSeedDetectedFrames": 0,
            "proposalDirectSeedTightDetectedFrames": 0,
            "proposalDirectSeedContextDetectedFrames": 0,
            "proposalPlayerRankedDetectedFrames": 0,
            "proposalTouchlineCandidateModeEntered": False,
            "proposalTouchlineEscapeDetectedFrames": 0,
            "proposalTouchlineInboardDetectedFrames": 0,
            "proposalTouchlineEscapeSelectedFrames": 0,
            "proposalTouchlineInboardSelectedFrames": 0,
            "proposalReopenedRawCandidateFrames": 0,
            "proposalReopenedRawCandidateSelectedFrames": 0,
            "proposalTouchlineEscapeRejectionCounts": {},
            "proposalZeroTouchlineCandidateReasonCounts": {},
            "proposalRepeatedAnchorSuppressedFrames": 0,
            "proposalAdmissionWideningAcceptedFrames": 0,
            "proposalAdmissionWideningRejectedCounts": {},
            "proposalAcceptanceSupportGatingAcceptedFrames": 0,
            "proposalAcceptanceSupportGatingRejectedCounts": {},
            "proposalSelectionAdmissionFixAcceptedFrames": 0,
            "proposalSelectionAdmissionFixRejectedCounts": {},
            "proposalSelectionAdmissionFixTruthSeedFrames": 0,
            "proposalSelectionAdmissionFixApproachFamily": None,
            "proposalSupportViabilityAdmissionFixAcceptedFrames": 0,
            "proposalSupportViabilityAdmissionFixRejectedCounts": {},
            "proposalSupportViabilityAdmissionFixTruthSeedFrames": 0,
            "proposalSupportViabilityAdmissionFixApproachFamily": None,
            "proposalBaselineGuidedRescueSelectedFrames": 0,
            "proposalBaselineGuidedRescueRejectedEdgeGuardFrames": 0,
            "proposalContinuityBridgeGapFrames": 0,
            "proposalContinuityBridgeCandidateFrames": 0,
            "proposalContinuityBridgeAcceptedFrames": 0,
            "proposalContinuityBridgeRejectedEdgeFrames": 0,
            "proposalContinuityBridgeRejectedContinuityFrames": 0,
            "proposalContinuityBridgeRejectedSupportFrames": 0,
            "proposalContinuityBridgeRejectedRepeatedAnchorFrames": 0,
            "proposalCandidateEdgeShareBeforeSelection": 0.0,
            "proposalCandidateEdgeShareAfterSelection": 0.0,
            "proposalWindowKindCandidateCounts": {},
            "proposalWindowKindSelectedCounts": {},
            "proposalExactSeedDetectedFrames": 0,
            "proposalInterpolatedSeedDetectedFrames": 0,
            "proposalSingleSeedDetectedFrames": 0,
        }

    player_rows_by_frame = _group_rows_by_frame(
        [row for row in (player_rows or []) if row.get("Entity_Type") != "ball"]
    )
    rows_by_frame = {}
    for original_index, row in enumerate(candidate_rows):
        rows_by_frame.setdefault(int(row["Frame_ID"]), []).append((original_index, row))

    def _row_rank(row, original_index):
        source_center = _row_source_box_center(row)
        proposal_seed_center = _proposal_seed_center_for_row(row)
        if source_center is None or proposal_seed_center is None:
            seed_distance = float("inf")
        else:
            seed_distance = hypot(
                float(source_center[0]) - float(proposal_seed_center[0]),
                float(source_center[1]) - float(proposal_seed_center[1]),
            )
        supported = _ball_row_is_player_supported(row, player_rows_by_frame)
        non_edge = not _ball_row_is_edge(row)
        return (
            -seed_distance,
            1 if _proposal_row_is_anchored(row) else 0,
            1 if supported else 0,
            1 if non_edge else 0,
            float(row.get("Conf", 0.0)),
            _proposal_window_kind_priority(row.get("ProposalWindowKind")),
            -int(original_index),
        )

    acquisition_mode = _touchline_acquisition_mode(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    acquisition_enabled = acquisition_mode is not None
    acquisition_reopen_enabled = acquisition_mode == "touchline_acquisition_reopen"
    candidate_admission_reopen_enabled = acquisition_mode == "touchline_candidate_admission_reopen"
    collapsed_rows = []
    baseline_collapsed_rows = []
    touchline_escape_selected_frames = 0
    touchline_inboard_selected_frames = 0
    repeated_anchor_suppressed_frames = 0
    touchline_escape_rejection_counts = {}
    zero_touchline_candidate_reason_counts = {}
    window_kind_candidate_counts = {}
    window_kind_selected_counts = {}
    prior_collapsed_row = None
    admission_widening_config = _touchline_admission_widening_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    admission_widening_enabled = admission_widening_config is not None
    admission_widening_accepted_row_ids = set()
    admission_widening_rejected_counts = {}
    admission_widening_selected_frames = 0
    acceptance_support_gating_config = _touchline_acceptance_support_gating_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    acceptance_support_gating_enabled = acceptance_support_gating_config is not None
    acceptance_support_gating_accepted_row_ids = set()
    acceptance_support_gating_rejected_counts = {}
    acceptance_support_gating_selected_frames = 0
    proposal_selection_config = _touchline_proposal_selection_admission_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if isinstance(proposal_selection_config, dict) and proposal_selection_truth_seed_path:
        proposal_selection_config["truthSeedPath"] = str(proposal_selection_truth_seed_path)
    proposal_selection_enabled = proposal_selection_config is not None
    proposal_selection_seed_payload = _proposal_selection_truth_seed_payload(
        proposal_selection_config.get("truthSeedPath")
        if isinstance(proposal_selection_config, dict)
        else None
    )
    proposal_selection_seed_rows_by_frame = dict(
        proposal_selection_seed_payload.get("seedRowsByFrame")
        if isinstance(proposal_selection_seed_payload.get("seedRowsByFrame"), dict)
        else {}
    )
    proposal_selection_accepted_row_ids = set()
    proposal_selection_rejected_counts = {}
    proposal_selection_selected_frames = 0
    support_viability_config = _touchline_support_viability_admission_fix_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    if isinstance(support_viability_config, dict) and proposal_selection_truth_seed_path:
        support_viability_config["truthSeedPath"] = str(proposal_selection_truth_seed_path)
    support_viability_enabled = support_viability_config is not None
    support_viability_seed_payload = _proposal_selection_truth_seed_payload(
        support_viability_config.get("truthSeedPath")
        if isinstance(support_viability_config, dict)
        else None
    )
    support_viability_seed_rows_by_frame = dict(
        support_viability_seed_payload.get("seedRowsByFrame")
        if isinstance(support_viability_seed_payload.get("seedRowsByFrame"), dict)
        else {}
    )
    support_viability_accepted_row_ids = set()
    support_viability_rejected_counts = {}
    support_viability_selected_frames = 0
    baseline_guided_rescue_selected_frames = 0
    baseline_guided_rescue_rejected_edge_guard_frames = 0
    baseline_guided_rescue_config = _touchline_baseline_guided_rescue_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    continuity_bridge_config = _touchline_continuity_bridge_recovery_config(
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    continuity_bridge_gap_frames = 0
    continuity_bridge_candidate_frames = 0
    continuity_bridge_accepted_frames = 0
    continuity_bridge_rejected_edge_frames = 0
    continuity_bridge_rejected_continuity_frames = 0
    continuity_bridge_rejected_support_frames = 0
    continuity_bridge_rejected_repeated_anchor_frames = 0

    sorted_frame_ids = sorted(rows_by_frame)

    def _best_stable_endpoint_for_frame(endpoint_frame_id):
        endpoint_candidates = rows_by_frame.get(int(endpoint_frame_id), [])
        stable_candidates = [
            (original_index, candidate_row)
            for original_index, candidate_row in endpoint_candidates
            if _proposal_candidate_viability_class(candidate_row, player_rows_by_frame) >= 2
        ]
        if not stable_candidates:
            return None
        return max(stable_candidates, key=lambda item: _row_rank(item[1], item[0]))[1]

    def _next_stable_endpoint_after(frame_id):
        for endpoint_frame_id in sorted_frame_ids:
            if int(endpoint_frame_id) <= int(frame_id):
                continue
            endpoint_row = _best_stable_endpoint_for_frame(endpoint_frame_id)
            if endpoint_row is not None:
                return endpoint_row
        return None

    def _record_admission_widening_rejection(reason):
        admission_widening_rejected_counts[str(reason)] = (
            int(admission_widening_rejected_counts.get(str(reason), 0)) + 1
        )

    def _record_acceptance_support_gating_rejection(reason):
        acceptance_support_gating_rejected_counts[str(reason)] = (
            int(acceptance_support_gating_rejected_counts.get(str(reason), 0)) + 1
        )

    def _record_proposal_selection_rejection(reason):
        proposal_selection_rejected_counts[str(reason)] = (
            int(proposal_selection_rejected_counts.get(str(reason), 0)) + 1
        )

    def _record_support_viability_rejection(reason):
        support_viability_rejected_counts[str(reason)] = (
            int(support_viability_rejected_counts.get(str(reason), 0)) + 1
        )

    def _ball_row_is_source_space_player_supported(ball_row):
        ball_center = _row_source_box_center(ball_row)
        if ball_center is None:
            return False
        player_rows_for_frame = player_rows_by_frame.get(int(ball_row["Frame_ID"]), [])
        for player_row in player_rows_for_frame:
            player_center = _row_source_box_center(player_row)
            if player_center is None:
                continue
            if hypot(
                float(player_center[0]) - float(ball_center[0]),
                float(player_center[1]) - float(ball_center[1]),
            ) <= float(MAX_OWNER_DISTANCE):
                return True
        return False

    def _admission_widening_allows_candidate(candidate_row):
        if not admission_widening_enabled:
            return False
        if str(candidate_row.get("ProposalWindowKind") or "") != TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND:
            _record_admission_widening_rejection("not_inboard_context")
            return False
        if bool(admission_widening_config.get("requirePlayerSupport")) and not _ball_row_is_player_supported(
            candidate_row,
            player_rows_by_frame,
        ):
            _record_admission_widening_rejection("player_support_missing")
            return False
        projected_rows = list(collapsed_rows) + [candidate_row]
        projected_edge_share = _edge_share_for_rows(projected_rows)
        if projected_edge_share > float(admission_widening_config.get("maxProjectedEdgeShare")):
            _record_admission_widening_rejection("projected_edge_share_too_high")
            return False
        return True

    def _acceptance_support_gating_allows_candidate(candidate_row, baseline_row):
        if not acceptance_support_gating_enabled:
            return False
        if str(candidate_row.get("ProposalWindowKind") or "") != TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND:
            _record_acceptance_support_gating_rejection("not_inboard_context")
            return False
        if bool(acceptance_support_gating_config.get("requireRealDetectedCandidateRows")) and (
            _row_source_box_center(candidate_row) is None or float(candidate_row.get("Conf", 0.0)) <= 0.0
        ):
            _record_acceptance_support_gating_rejection("real_detected_candidate_missing")
            return False
        if _proposal_candidate_repeated_anchor_suspicious(candidate_row):
            _record_acceptance_support_gating_rejection(TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR)
            return False
        candidate_supported = _ball_row_is_player_supported(candidate_row, player_rows_by_frame)
        baseline_supported = _ball_row_is_player_supported(baseline_row, player_rows_by_frame)
        if bool(acceptance_support_gating_config.get("requirePlayerSupport")) and not candidate_supported:
            _record_acceptance_support_gating_rejection("player_support_missing")
            return False
        projected_rows = list(collapsed_rows) + [candidate_row]
        projected_edge_share = _edge_share_for_rows(projected_rows)
        if projected_edge_share > float(acceptance_support_gating_config.get("maxProjectedEdgeShare")):
            _record_acceptance_support_gating_rejection("projected_edge_share_too_high")
            return False
        if _ball_row_is_edge(candidate_row):
            _record_acceptance_support_gating_rejection("candidate_edge_heavy")
            return False
        if (
            bool(acceptance_support_gating_config.get("requireSupportImprovement"))
            and baseline_supported
        ):
            _record_acceptance_support_gating_rejection("support_not_improved")
            return False
        return True

    def _proposal_selection_seed_distance(candidate_row, seed_row):
        try:
            return hypot(
                float(candidate_row["X"]) - float(seed_row["X"]),
                float(candidate_row["Y"]) - float(seed_row["Y"]),
            )
        except (KeyError, TypeError, ValueError):
            return float("inf")

    def _proposal_selection_admission_allows_candidate(candidate_row):
        if not proposal_selection_enabled:
            return False
        frame_id = int(candidate_row.get("Frame_ID"))
        seed_row = proposal_selection_seed_rows_by_frame.get(frame_id)
        if not isinstance(seed_row, dict):
            _record_proposal_selection_rejection("frame_not_in_truth_seed")
            return False
        if bool(proposal_selection_config.get("requireRealDetectedCandidateRows")) and (
            _row_source_box_center(candidate_row) is None or float(candidate_row.get("Conf", 0.0)) <= 0.0
        ):
            _record_proposal_selection_rejection("real_detected_candidate_missing")
            return False
        if (
            bool(proposal_selection_config.get("preserveRepeatedAnchorGuard", True))
            and _proposal_candidate_repeated_anchor_suspicious(candidate_row)
        ):
            _record_proposal_selection_rejection(TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR)
            return False
        projected_rows = list(collapsed_rows) + [candidate_row]
        projected_edge_share = _edge_share_for_rows(projected_rows)
        if projected_edge_share > float(proposal_selection_config.get("maxProjectedEdgeShare")):
            _record_proposal_selection_rejection("projected_edge_share_too_high")
            return False
        if (
            bool(proposal_selection_config.get("preserveContinuityGuard", True))
            and not _proposal_candidate_continuity_ok(candidate_row, prior_collapsed_row)
        ):
            _record_proposal_selection_rejection(TOUCHLINE_ESCAPE_REJECTION_CONTINUITY)
            return False
        approach_family = str(
            proposal_selection_config.get("approachFamily") or "truth_seed_guided_selection"
        )
        if approach_family == "truth_seed_guided_selection":
            seed_distance = _proposal_selection_seed_distance(candidate_row, seed_row)
            if seed_distance > float(proposal_selection_config.get("maxSeedPitchDistance", 8.0)):
                _record_proposal_selection_rejection("truth_seed_distance_too_far")
                return False
        elif approach_family == "window_local_proposal_kind_rescue":
            if str(candidate_row.get("ProposalWindowKind") or "") not in {
                TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND,
                TOUCHLINE_ESCAPE_WINDOW_KIND,
                "player_ranked",
            }:
                _record_proposal_selection_rejection("unsupported_window_kind")
                return False
        elif approach_family == "segment_level_seed_continuity":
            if _proposal_candidate_viability_class(candidate_row, player_rows_by_frame) <= 0:
                _record_proposal_selection_rejection("support_or_viability_missing")
                return False
        else:
            _record_proposal_selection_rejection("unsupported_approach_family")
            return False
        return True

    def _support_viability_admission_allows_candidate(candidate_row):
        if not support_viability_enabled:
            return False
        frame_id = int(candidate_row.get("Frame_ID"))
        seed_row = support_viability_seed_rows_by_frame.get(frame_id)
        if not isinstance(seed_row, dict):
            _record_support_viability_rejection("frame_not_in_truth_seed")
            return False
        if bool(support_viability_config.get("requireRealDetectedCandidateRows")) and (
            _row_source_box_center(candidate_row) is None or float(candidate_row.get("Conf", 0.0)) <= 0.0
        ):
            _record_support_viability_rejection("real_detected_candidate_missing")
            return False
        if (
            bool(support_viability_config.get("preserveRepeatedAnchorGuard", True))
            and _proposal_candidate_repeated_anchor_suspicious(candidate_row)
        ):
            _record_support_viability_rejection(TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR)
            return False
        if _ball_row_is_edge(candidate_row):
            _record_support_viability_rejection("candidate_edge_heavy")
            return False
        projected_rows = list(collapsed_rows) + [candidate_row]
        projected_edge_share = _edge_share_for_rows(projected_rows)
        if projected_edge_share > float(support_viability_config.get("maxProjectedEdgeShare")):
            _record_support_viability_rejection("projected_edge_share_too_high")
            return False
        if (
            bool(support_viability_config.get("preserveContinuityGuard", True))
            and not _proposal_candidate_continuity_ok(candidate_row, prior_collapsed_row)
        ):
            _record_support_viability_rejection(TOUCHLINE_ESCAPE_REJECTION_CONTINUITY)
            return False

        approach_family = str(
            support_viability_config.get("approachFamily") or "support_evidence_lift"
        )
        viability_class = _proposal_candidate_viability_class(candidate_row, player_rows_by_frame)
        player_supported = _ball_row_is_player_supported(candidate_row, player_rows_by_frame)
        source_space_supported = _ball_row_is_source_space_player_supported(candidate_row)
        if approach_family == "support_evidence_lift":
            if not player_supported and viability_class < 2:
                _record_support_viability_rejection("support_or_viability_missing")
                return False
        elif approach_family == "source_space_support_neighborhood":
            if not player_supported and not source_space_supported and viability_class < 2:
                _record_support_viability_rejection("source_space_support_missing")
                return False
        elif approach_family == "viability_neutral_seed_window":
            if viability_class < 1:
                _record_support_viability_rejection("viability_missing")
                return False
        else:
            _record_support_viability_rejection("unsupported_approach_family")
            return False
        return True

    for frame_id in sorted_frame_ids:
        frame_candidates = rows_by_frame[frame_id]
        for _original_index, candidate_row in frame_candidates:
            window_kind = str(candidate_row.get("ProposalWindowKind") or "player_ranked")
            window_kind_candidate_counts[window_kind] = (
                int(window_kind_candidate_counts.get(window_kind, 0)) + 1
            )
        if baseline_guided_rescue_config is not None:
            edge_guarded_frame_candidates = []
            for original_index, candidate_row in frame_candidates:
                if str(candidate_row.get("ProposalSeedMode") or "") != BASELINE_GUIDED_RESCUE_SEED_MODE:
                    edge_guarded_frame_candidates.append((original_index, candidate_row))
                    continue
                projected_edge_share = _edge_share_for_rows([*collapsed_rows, candidate_row])
                if projected_edge_share > float(
                    baseline_guided_rescue_config.get("maxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
                ):
                    baseline_guided_rescue_rejected_edge_guard_frames += 1
                    continue
                edge_guarded_frame_candidates.append((original_index, candidate_row))
            frame_candidates = edge_guarded_frame_candidates
            if not frame_candidates:
                continue
        _, baseline_best_candidate = max(frame_candidates, key=lambda item: _row_rank(item[1], item[0]))
        best_candidate = baseline_best_candidate
        if (
            acceptance_support_gating_enabled
            and _proposal_candidate_repeated_anchor_suspicious(best_candidate)
        ):
            safe_frame_candidates = [
                (original_index, candidate_row)
                for original_index, candidate_row in frame_candidates
                if not _proposal_candidate_repeated_anchor_suspicious(candidate_row)
            ]
            if safe_frame_candidates:
                _, best_candidate = max(
                    safe_frame_candidates,
                    key=lambda item: _row_rank(item[1], item[0]),
                )
        if continuity_bridge_config is not None and prior_collapsed_row is not None:
            next_endpoint_row = _next_stable_endpoint_after(frame_id)
            endpoint_gap = (
                int(next_endpoint_row["Frame_ID"]) - int(prior_collapsed_row["Frame_ID"])
                if next_endpoint_row is not None
                else 0
            )
            bridge_window_is_active = (
                next_endpoint_row is not None
                and endpoint_gap > int(max_frame_gap)
                and endpoint_gap <= int(continuity_bridge_config.get("maxGapFrames", max_frame_gap))
                and int(prior_collapsed_row["Frame_ID"]) < int(frame_id) < int(next_endpoint_row["Frame_ID"])
            )
            if bridge_window_is_active:
                continuity_bridge_gap_frames += 1
                accepted_bridge_candidates = []
                for original_index, candidate_row in frame_candidates:
                    continuity_bridge_candidate_frames += 1
                    if _proposal_candidate_repeated_anchor_suspicious(candidate_row):
                        continuity_bridge_rejected_repeated_anchor_frames += 1
                        continue
                    if _ball_row_is_edge(candidate_row):
                        continuity_bridge_rejected_edge_frames += 1
                        continue
                    if _proposal_candidate_viability_class(candidate_row, player_rows_by_frame) <= 0:
                        continuity_bridge_rejected_support_frames += 1
                        continue
                    if bool(continuity_bridge_config.get("requireEndpointContinuity", True)):
                        if (
                            not _proposal_candidate_continuity_ok(candidate_row, prior_collapsed_row)
                            or not _proposal_candidate_continuity_ok(candidate_row, next_endpoint_row)
                        ):
                            continuity_bridge_rejected_continuity_frames += 1
                            continue
                    projected_rows = [*collapsed_rows, candidate_row]
                    projected_edge_share = _edge_share_for_rows(projected_rows)
                    if projected_edge_share > float(
                        continuity_bridge_config.get("maxProjectedEdgeShare", MAX_VIABLE_EDGE_FRAME_SHARE)
                    ):
                        continuity_bridge_rejected_edge_frames += 1
                        continue
                    accepted_bridge_candidates.append((original_index, candidate_row))
                if accepted_bridge_candidates:
                    _bridge_original_index, bridge_candidate = max(
                        accepted_bridge_candidates,
                        key=lambda item: (
                            _proposal_candidate_viability_class(item[1], player_rows_by_frame),
                            1 if _ball_row_is_player_supported(item[1], player_rows_by_frame) else 0,
                            float(item[1].get("Conf", 0.0)),
                            -hypot(
                                float(item[1]["X"]) - float(prior_collapsed_row["X"]),
                                float(item[1]["Y"]) - float(prior_collapsed_row["Y"]),
                            ),
                            -int(item[0]),
                        ),
                    )
                    best_candidate = dict(bridge_candidate)
                    best_candidate["ContinuityBridgeRecovered"] = True
                    continuity_bridge_accepted_frames += 1

        if acquisition_enabled:
            candidate_window_kinds = {TOUCHLINE_ESCAPE_WINDOW_KIND}
            if acquisition_reopen_enabled:
                candidate_window_kinds.add(TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND)
            if candidate_admission_reopen_enabled:
                candidate_window_kinds.add(TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND)
            if proposal_selection_enabled:
                candidate_window_kinds.add(TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND)
            if support_viability_enabled:
                candidate_window_kinds.add(TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND)
            touchline_candidates = [
                candidate_row
                for _original_index, candidate_row in frame_candidates
                if str(candidate_row.get("ProposalWindowKind") or "") in candidate_window_kinds
            ]
            accepted_touchline_candidates = []
            rejection_reason = None
            baseline_edge_score = 1.0 if _ball_row_is_edge(baseline_best_candidate) else 0.0
            baseline_viable_proxy = _proposal_candidate_viability_proxy(
                baseline_best_candidate,
                player_rows_by_frame,
            )
            baseline_viability_class = _proposal_candidate_viability_class(
                baseline_best_candidate,
                player_rows_by_frame,
            )
            for candidate_row in touchline_candidates:
                candidate_edge_score = 1.0 if _ball_row_is_edge(candidate_row) else 0.0
                candidate_viability_class = _proposal_candidate_viability_class(
                    candidate_row,
                    player_rows_by_frame,
                )
                minimum_edge_improvement = 0.05
                if (
                    (
                        candidate_admission_reopen_enabled
                        or acceptance_support_gating_enabled
                        or proposal_selection_enabled
                        or support_viability_enabled
                    )
                    and baseline_viability_class == 0
                    and candidate_viability_class > 0
                ):
                    minimum_edge_improvement = 0.03
                if (
                    (
                        admission_widening_enabled
                        or acceptance_support_gating_enabled
                        or (
                            proposal_selection_enabled
                            and bool(
                                proposal_selection_config.get("preserveRepeatedAnchorGuard", True)
                            )
                        )
                        or (
                            support_viability_enabled
                            and bool(
                                support_viability_config.get("preserveRepeatedAnchorGuard", True)
                            )
                        )
                    )
                    and _proposal_candidate_repeated_anchor_suspicious(candidate_row)
                ):
                    rejection_reason = TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR
                    repeated_anchor_suppressed_frames += 1
                    if admission_widening_enabled:
                        _record_admission_widening_rejection(rejection_reason)
                    if acceptance_support_gating_enabled:
                        _record_acceptance_support_gating_rejection(rejection_reason)
                    if proposal_selection_enabled:
                        _record_proposal_selection_rejection(rejection_reason)
                    if support_viability_enabled:
                        _record_support_viability_rejection(rejection_reason)
                    continue
                admission_widening_used = False
                acceptance_support_gating_used = False
                proposal_selection_used = False
                support_viability_used = False
                if (baseline_edge_score - candidate_edge_score) < minimum_edge_improvement:
                    if _acceptance_support_gating_allows_candidate(candidate_row, baseline_best_candidate):
                        acceptance_support_gating_used = True
                    elif _support_viability_admission_allows_candidate(candidate_row):
                        support_viability_used = True
                    elif _proposal_selection_admission_allows_candidate(candidate_row):
                        proposal_selection_used = True
                    elif _admission_widening_allows_candidate(candidate_row):
                        admission_widening_used = True
                    else:
                        rejection_reason = TOUCHLINE_ESCAPE_REJECTION_EDGE_SHARE
                        continue
                if not _proposal_candidate_continuity_ok(candidate_row, prior_collapsed_row):
                    rejection_reason = TOUCHLINE_ESCAPE_REJECTION_CONTINUITY
                    if admission_widening_used:
                        _record_admission_widening_rejection(rejection_reason)
                    if acceptance_support_gating_used:
                        _record_acceptance_support_gating_rejection(rejection_reason)
                    if proposal_selection_used:
                        _record_proposal_selection_rejection(rejection_reason)
                    if support_viability_used:
                        _record_support_viability_rejection(rejection_reason)
                    continue
                if (
                    not admission_widening_enabled
                    and not acceptance_support_gating_enabled
                    and not proposal_selection_enabled
                    and not support_viability_enabled
                    and _proposal_candidate_repeated_anchor_suspicious(candidate_row)
                ):
                    rejection_reason = TOUCHLINE_ESCAPE_REJECTION_REPEATED_ANCHOR
                    repeated_anchor_suppressed_frames += 1
                    continue
                candidate_viable_proxy = _proposal_candidate_viability_proxy(candidate_row, player_rows_by_frame)
                if baseline_viability_class > candidate_viability_class or (
                    baseline_viable_proxy and not candidate_viable_proxy
                ):
                    if not acceptance_support_gating_used and not proposal_selection_used and not support_viability_used:
                        rejection_reason = TOUCHLINE_ESCAPE_REJECTION_VIABILITY
                        if admission_widening_used:
                            _record_admission_widening_rejection(rejection_reason)
                        if support_viability_used:
                            _record_support_viability_rejection(rejection_reason)
                        continue
                if admission_widening_used:
                    admission_widening_accepted_row_ids.add(id(candidate_row))
                if acceptance_support_gating_used:
                    acceptance_support_gating_accepted_row_ids.add(id(candidate_row))
                if proposal_selection_used:
                    proposal_selection_accepted_row_ids.add(id(candidate_row))
                if support_viability_used:
                    support_viability_accepted_row_ids.add(id(candidate_row))
                accepted_touchline_candidates.append(candidate_row)

            if accepted_touchline_candidates:
                best_candidate = max(
                    accepted_touchline_candidates,
                    key=lambda row: (
                        _proposal_candidate_viability_class(row, player_rows_by_frame),
                        -(1.0 if _ball_row_is_edge(row) else 0.0),
                        1 if _proposal_candidate_continuity_ok(row, prior_collapsed_row) else 0,
                        -_proposal_seed_distance_for_row(row),
                        float(row.get("Conf", 0.0)),
                        _proposal_window_kind_priority(row.get("ProposalWindowKind")),
                    ),
                )
                if str(best_candidate.get("ProposalWindowKind") or "") == TOUCHLINE_ESCAPE_WINDOW_KIND:
                    touchline_escape_selected_frames += 1
                if str(best_candidate.get("ProposalWindowKind") or "") == TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND:
                    touchline_inboard_selected_frames += 1
                if id(best_candidate) in admission_widening_accepted_row_ids:
                    admission_widening_selected_frames += 1
                if id(best_candidate) in acceptance_support_gating_accepted_row_ids:
                    best_candidate = dict(best_candidate)
                    best_candidate["AcceptanceSupportGatingRecovered"] = True
                    acceptance_support_gating_selected_frames += 1
                if id(best_candidate) in proposal_selection_accepted_row_ids:
                    best_candidate = dict(best_candidate)
                    best_candidate["ProposalSelectionAdmissionFixRecovered"] = True
                    best_candidate["ProposalSelectionAdmissionFixApproachFamily"] = str(
                        proposal_selection_config.get("approachFamily")
                        or "truth_seed_guided_selection"
                    )
                    proposal_selection_selected_frames += 1
                if id(best_candidate) in support_viability_accepted_row_ids:
                    best_candidate = dict(best_candidate)
                    best_candidate["SupportViabilityAdmissionFixRecovered"] = True
                    best_candidate["SupportViabilityAdmissionFixApproachFamily"] = str(
                        support_viability_config.get("approachFamily")
                        or "support_evidence_lift"
                    )
                    support_viability_selected_frames += 1
            elif touchline_candidates:
                rejection_key = str(rejection_reason or TOUCHLINE_ESCAPE_REJECTION_EDGE_SHARE)
                touchline_escape_rejection_counts[rejection_key] = (
                    int(touchline_escape_rejection_counts.get(rejection_key, 0)) + 1
                )
            else:
                rejection_key = TOUCHLINE_ESCAPE_REJECTION_NO_CANDIDATES
                zero_touchline_candidate_reason_counts[rejection_key] = (
                    int(zero_touchline_candidate_reason_counts.get(rejection_key, 0)) + 1
                )

        baseline_collapsed_rows.append(baseline_best_candidate)
        if str(best_candidate.get("ProposalSeedMode") or "") == BASELINE_GUIDED_RESCUE_SEED_MODE:
            baseline_guided_rescue_selected_frames += 1
        collapsed_rows.append(best_candidate)
        selected_window_kind = str(best_candidate.get("ProposalWindowKind") or "player_ranked")
        window_kind_selected_counts[selected_window_kind] = (
            int(window_kind_selected_counts.get(selected_window_kind, 0)) + 1
        )
        prior_collapsed_row = best_candidate

    collapsed_segments = split_ball_rows_into_segments(collapsed_rows, max_frame_gap=max_frame_gap)
    longest_segment_frames = max(
        (len({int(segment_row["Frame_ID"]) for segment_row in segment}) for segment in collapsed_segments),
        default=0,
    )
    proposal_direct_seed_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if _proposal_window_kind_is_direct_seed(row.get("ProposalWindowKind"))
        }
    )
    proposal_direct_seed_tight_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalWindowKind", "")) in {"direct_seed", "direct_seed_tight"}
        }
    )
    proposal_direct_seed_context_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalWindowKind", "")) == "direct_seed_context"
        }
    )
    proposal_player_ranked_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalWindowKind", "player_ranked")) == "player_ranked"
        }
    )
    proposal_touchline_escape_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalWindowKind", "")) == TOUCHLINE_ESCAPE_WINDOW_KIND
        }
    )
    proposal_touchline_inboard_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalWindowKind", "")) == TOUCHLINE_INBOARD_CONTEXT_WINDOW_KIND
        }
    )
    proposal_reopened_raw_candidate_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if bool(row.get("TouchlineRawCandidateReopened"))
        }
    )
    proposal_reopened_raw_candidate_selected_frames = len(
        {
            int(row["Frame_ID"])
            for row in collapsed_rows
            if bool(row.get("TouchlineRawCandidateReopened"))
        }
    )
    proposal_exact_seed_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalSeedMode", "")) == "exact"
        }
    )
    proposal_interpolated_seed_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalSeedMode", "")) == "interpolated"
        }
    )
    proposal_single_seed_detected_frames = len(
        {
            int(row["Frame_ID"])
            for row in candidate_rows
            if str(row.get("ProposalSeedMode", "")) == "single"
        }
    )
    return {
        "rows": collapsed_rows,
        "proposalRawDetectedFrames": len({int(row["Frame_ID"]) for row in candidate_rows}),
        "proposalAfterSeedCollapseFrames": len({int(row["Frame_ID"]) for row in collapsed_rows}),
        "proposalAfterPlayerWindowFrames": len({int(row["Frame_ID"]) for row in collapsed_rows}),
        "proposalAfterFalseBallSuppressionFrames": len({int(row["Frame_ID"]) for row in collapsed_rows}),
        "proposalCollapsedFrames": len({int(row["Frame_ID"]) for row in collapsed_rows}),
        "proposalCollapsedSegmentCount": len(collapsed_segments),
        "proposalCollapsedLongestSegmentFrames": longest_segment_frames,
        "proposalDirectSeedDetectedFrames": proposal_direct_seed_detected_frames,
        "proposalDirectSeedTightDetectedFrames": proposal_direct_seed_tight_detected_frames,
        "proposalDirectSeedContextDetectedFrames": proposal_direct_seed_context_detected_frames,
        "proposalPlayerRankedDetectedFrames": proposal_player_ranked_detected_frames,
        "proposalTouchlineCandidateModeEntered": acquisition_enabled,
        "proposalTouchlineEscapeDetectedFrames": proposal_touchline_escape_detected_frames,
        "proposalTouchlineInboardDetectedFrames": proposal_touchline_inboard_detected_frames,
        "proposalTouchlineEscapeSelectedFrames": touchline_escape_selected_frames,
        "proposalTouchlineInboardSelectedFrames": touchline_inboard_selected_frames,
        "proposalReopenedRawCandidateFrames": proposal_reopened_raw_candidate_frames,
        "proposalReopenedRawCandidateSelectedFrames": proposal_reopened_raw_candidate_selected_frames,
        "proposalTouchlineEscapeRejectionCounts": dict(sorted(touchline_escape_rejection_counts.items())),
        "proposalZeroTouchlineCandidateReasonCounts": dict(
            sorted(zero_touchline_candidate_reason_counts.items())
        ),
        "proposalRepeatedAnchorSuppressedFrames": repeated_anchor_suppressed_frames,
        "proposalAdmissionWideningAcceptedFrames": admission_widening_selected_frames,
        "proposalAdmissionWideningRejectedCounts": dict(sorted(admission_widening_rejected_counts.items())),
        "proposalAcceptanceSupportGatingAcceptedFrames": acceptance_support_gating_selected_frames,
        "proposalAcceptanceSupportGatingRejectedCounts": dict(
            sorted(acceptance_support_gating_rejected_counts.items())
        ),
        "proposalSelectionAdmissionFixAcceptedFrames": proposal_selection_selected_frames,
        "proposalSelectionAdmissionFixRejectedCounts": dict(
            sorted(proposal_selection_rejected_counts.items())
        ),
        "proposalSelectionAdmissionFixTruthSeedFrames": len(proposal_selection_seed_rows_by_frame),
        "proposalSelectionAdmissionFixApproachFamily": (
            str(proposal_selection_config.get("approachFamily"))
            if isinstance(proposal_selection_config, dict)
            else None
        ),
        "proposalSupportViabilityAdmissionFixAcceptedFrames": support_viability_selected_frames,
        "proposalSupportViabilityAdmissionFixRejectedCounts": dict(
            sorted(support_viability_rejected_counts.items())
        ),
        "proposalSupportViabilityAdmissionFixTruthSeedFrames": len(support_viability_seed_rows_by_frame),
        "proposalSupportViabilityAdmissionFixApproachFamily": (
            str(support_viability_config.get("approachFamily"))
            if isinstance(support_viability_config, dict)
            else None
        ),
        "proposalBaselineGuidedRescueSelectedFrames": baseline_guided_rescue_selected_frames,
        "proposalBaselineGuidedRescueRejectedEdgeGuardFrames": baseline_guided_rescue_rejected_edge_guard_frames,
        "proposalContinuityBridgeGapFrames": continuity_bridge_gap_frames,
        "proposalContinuityBridgeCandidateFrames": continuity_bridge_candidate_frames,
        "proposalContinuityBridgeAcceptedFrames": continuity_bridge_accepted_frames,
        "proposalContinuityBridgeRejectedEdgeFrames": continuity_bridge_rejected_edge_frames,
        "proposalContinuityBridgeRejectedContinuityFrames": continuity_bridge_rejected_continuity_frames,
        "proposalContinuityBridgeRejectedSupportFrames": continuity_bridge_rejected_support_frames,
        "proposalContinuityBridgeRejectedRepeatedAnchorFrames": continuity_bridge_rejected_repeated_anchor_frames,
        "proposalCandidateEdgeShareBeforeSelection": _edge_share_for_rows(baseline_collapsed_rows),
        "proposalCandidateEdgeShareAfterSelection": _edge_share_for_rows(collapsed_rows),
        "proposalWindowKindCandidateCounts": dict(sorted(window_kind_candidate_counts.items())),
        "proposalWindowKindSelectedCounts": dict(sorted(window_kind_selected_counts.items())),
        "proposalExactSeedDetectedFrames": proposal_exact_seed_detected_frames,
        "proposalInterpolatedSeedDetectedFrames": proposal_interpolated_seed_detected_frames,
        "proposalSingleSeedDetectedFrames": proposal_single_seed_detected_frames,
    }


def filter_recovered_ball_rows_for_profile(
    rows,
    player_windows,
    frame_shape,
    *,
    max_crop_width_ratio=0.0,
    crop_edge_margin=0,
    max_crop_center_y_ratio=0.0,
):
    if not rows:
        return []

    filtered_rows = []
    for row in rows:
        source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
        if not all(key in row for key in source_keys):
            filtered_rows.append(row)
            continue

        crop_window = None
        if player_windows is not None:
            crop_window = ball_recovery_crop_window(
                frame_shape,
                player_windows.get(int(row["Frame_ID"])),
                max_crop_width_ratio=max_crop_width_ratio,
            )

        source_box = (
            float(row["Source_X1"]),
            float(row["Source_Y1"]),
            float(row["Source_X2"]),
            float(row["Source_Y2"]),
        )
        if _source_box_is_too_close_to_crop_edge(source_box, crop_window, crop_edge_margin):
            continue
        if _source_box_center_is_too_low_in_crop(source_box, crop_window, max_crop_center_y_ratio):
            continue
        filtered_rows.append(row)

    return filtered_rows


def build_anchor_corridor_crop_window(
    frame_shape,
    frame_id,
    observed_source_anchors,
    player_window,
    *,
    corridor_half_width_px,
    corridor_padding_px,
):
    center_x, center_y, _anchor_mode = _anchor_corridor_center_and_mode(
        frame_id,
        observed_source_anchors,
    )
    if center_x is None or center_y is None:
        return ball_recovery_crop_window(frame_shape, player_window)

    crop_width = max(
        int(corridor_half_width_px) * 2 + int(corridor_padding_px) * 2,
        1,
    )
    crop_height = crop_width
    frame_height, frame_width = frame_shape[:2]

    left = max(0.0, center_x - (crop_width / 2.0))
    top = max(0.0, center_y - (crop_height / 2.0))
    right = min(float(frame_width), left + crop_width)
    bottom = min(float(frame_height), top + crop_height)

    left = max(0.0, right - crop_width)
    top = max(0.0, bottom - crop_height)
    return (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )


def _anchor_corridor_center_and_mode(frame_id, observed_source_anchors):
    if not observed_source_anchors:
        return None, None, "none"

    anchor_frame_ids = sorted(int(frame_id_value) for frame_id_value in observed_source_anchors)
    if not anchor_frame_ids:
        return None, None, "none"

    frame_id = int(frame_id)
    previous_frame_id = max((anchor_frame_id for anchor_frame_id in anchor_frame_ids if anchor_frame_id < frame_id), default=None)
    next_frame_id = min((anchor_frame_id for anchor_frame_id in anchor_frame_ids if anchor_frame_id > frame_id), default=None)

    if frame_id in observed_source_anchors:
        center_x, center_y = observed_source_anchors[frame_id]
        anchor_mode = "two" if previous_frame_id is not None and next_frame_id is not None else "single"
        return center_x, center_y, anchor_mode

    if previous_frame_id is None and next_frame_id is None:
        return None, None, "none"
    if previous_frame_id is None:
        center_x, center_y = observed_source_anchors[next_frame_id]
        return center_x, center_y, "single"
    if next_frame_id is None:
        center_x, center_y = observed_source_anchors[previous_frame_id]
        return center_x, center_y, "single"

    previous_center_x, previous_center_y = observed_source_anchors[previous_frame_id]
    next_center_x, next_center_y = observed_source_anchors[next_frame_id]
    ratio = (frame_id - previous_frame_id) / float(next_frame_id - previous_frame_id)
    center_x = previous_center_x + ((next_center_x - previous_center_x) * ratio)
    center_y = previous_center_y + ((next_center_y - previous_center_y) * ratio)
    return center_x, center_y, "two"


def _build_anchor_corridor_crop_windows_by_frame(
    frame_shape,
    *,
    frame_interval,
    observed_source_anchors,
    player_windows=None,
    frame_count=None,
    corridor_half_width_px,
    corridor_padding_px,
):
    if not observed_source_anchors:
        return {}, {
            "corridorCandidateFrames": 0,
            "corridorFramesWithTwoAnchors": 0,
            "corridorFramesWithSingleAnchor": 0,
            "corridorMeanWidth": 0.0,
        }

    observed_frame_ids = sorted(int(frame_id) for frame_id in observed_source_anchors)
    if frame_count is not None and int(frame_count) > 0:
        max_frame_id = int(frame_count)
    else:
        max_frame_id = max(observed_frame_ids) + int(frame_interval)
    sampled_frame_ids = list(range(0, max_frame_id, max(int(frame_interval), 1)))
    crop_windows_by_frame = {}
    crop_widths = []
    two_anchor_frames = 0
    single_anchor_frames = 0
    for sampled_frame_id in sampled_frame_ids:
        _center_x, _center_y, anchor_mode = _anchor_corridor_center_and_mode(
            sampled_frame_id,
            observed_source_anchors,
        )
        crop_window = build_anchor_corridor_crop_window(
            frame_shape,
            sampled_frame_id,
            observed_source_anchors,
            None if player_windows is None else player_windows.get(sampled_frame_id),
            corridor_half_width_px=corridor_half_width_px,
            corridor_padding_px=corridor_padding_px,
        )
        if crop_window is None:
            continue
        crop_windows_by_frame[sampled_frame_id] = crop_window
        left, top, right, bottom = crop_window
        crop_widths.append(max(float(right - left), 0.0))
        if anchor_mode == "two":
            two_anchor_frames += 1
        elif anchor_mode == "single":
            single_anchor_frames += 1

    if not crop_windows_by_frame:
        return crop_windows_by_frame, {
            "corridorCandidateFrames": 0,
            "corridorFramesWithTwoAnchors": 0,
            "corridorFramesWithSingleAnchor": 0,
            "corridorMeanWidth": 0.0,
        }

    return crop_windows_by_frame, {
        "corridorCandidateFrames": len({int(frame_id) for frame_id in crop_windows_by_frame}),
        "corridorFramesWithTwoAnchors": two_anchor_frames,
        "corridorFramesWithSingleAnchor": single_anchor_frames,
        "corridorMeanWidth": round(sum(crop_widths) / len(crop_widths), 2) if crop_widths else 0.0,
    }


def _profile_recovery_cache_key(profile):
    settings = dict(profile["settings"])
    retry_scales = tuple(int(scale) for scale in (profile.get("directSeedRetryScales") or []))
    return (
        bool(profile.get("usePlayerWindows")),
        int(settings["imgsz"]),
        float(settings["conf"]),
        float(profile.get("maxCropWidthRatio", 0.0)),
        int(profile.get("cropEdgeMargin", 0)),
        float(profile.get("maxCropCenterYRatio", 0.0)),
        str(profile.get("cropMode", "")),
        int(profile.get("corridorHalfWidthPx", 0)),
        int(profile.get("corridorPaddingPx", 0)),
        int(profile.get("proposalMaxWindowsPerFrame", 0)),
        float(profile.get("proposalCropWidthRatio", 0.0)),
        float(profile.get("proposalCropHeightRatio", 0.0)),
        int(profile.get("proposalCropPaddingPx", 0)),
        str(profile.get("directSeedRetryPolicy", "")),
        retry_scales,
    )


def run_ball_recovery_experiment(
    video_path,
    model,
    H,
    pitch_points,
    fps,
    frame_interval,
    imgsz,
    conf,
    observed_source_anchors=None,
    player_windows=None,
    player_rows=None,
    profiles=None,
    progress_callback=None,
    progress_interval_seconds=30.0,
    edge_share_repair_profile=None,
    baseline_guided_rescue_reference=None,
    baseline_guided_rescue_reference_path=None,
    proposal_selection_truth_seed_path=None,
    reviewed_positive_anchor_seed_path=None,
    detector_profile=DETECTOR_PROFILE_COCO_TRACKING_FULL,
    calibrations=None,
    frame_source=None,
):
    if baseline_guided_rescue_reference is None and baseline_guided_rescue_reference_path is not None:
        baseline_guided_rescue_reference = _load_baseline_guided_rescue_reference(
            baseline_guided_rescue_reference_path,
            source_clip_id=Path(str(video_path)).name,
            edge_share_repair_profile=edge_share_repair_profile,
        )
    experiment_profiles = profiles or build_ball_recovery_experiment_profiles(
        configured_imgsz=imgsz,
        configured_conf=conf,
        include_player_window_probe=bool(player_windows),
    )
    from backend.app.workbench.media import OpenCvFrameSource, first_bgr_frame, pixels_from_decoded_frame

    decode_adapter = frame_source or OpenCvFrameSource(cv2_module=cv2)
    identity = decode_adapter.probe(Path(str(video_path)))
    first_decoded = first_bgr_frame(Path(str(video_path)), decode_adapter, cv2_module=cv2)
    first_frame = pixels_from_decoded_frame(first_decoded) if first_decoded is not None else None
    ret = first_frame is not None
    total_frame_count = int(identity.frameCount or 0)
    frame_shape = first_frame.shape if ret and first_frame is not None else None
    cached_rows = {}
    experiment_results = []
    profile_count = len(experiment_profiles)
    source_clip_id = Path(str(video_path)).name
    for profile_index, profile in enumerate(experiment_profiles, start=1):
        profile = dict(profile)
        reviewed_positive_profile_config = _touchline_reviewed_positive_proposal_generation_fix_config(
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        )
        if (
            profile.get("cropMode") == "proposal_windows"
            and isinstance(reviewed_positive_profile_config, dict)
            and reviewed_positive_profile_config.get("retryScales")
        ):
            profile["directSeedRetryScales"] = [
                int(scale) for scale in reviewed_positive_profile_config.get("retryScales", [])
            ]
        profile_started_at = time.monotonic()
        settings = profile["settings"]
        profile_player_windows = player_windows if profile.get("usePlayerWindows") else None
        profile_player_rows = player_rows if profile.get("cropMode") == "proposal_windows" else None
        cache_key = _profile_recovery_cache_key(profile)
        base_rows = cached_rows.get(cache_key)
        crop_windows_by_frame = None
        corridor_breakdown = {
            "corridorCandidateFrames": 0,
            "corridorFramesWithTwoAnchors": 0,
            "corridorFramesWithSingleAnchor": 0,
            "corridorMeanWidth": 0.0,
        }
        proposal_breakdown = {
            "proposalCandidateFrames": 0,
            "proposalWindowCount": 0,
            "proposalFramesWithAnchorSeed": 0,
            "proposalFramesWithoutAnchorSeed": 0,
            "proposalExactSeedFrames": 0,
            "proposalInterpolatedSeedFrames": 0,
            "proposalSingleSeedFrames": 0,
            "proposalUnseededFrames": 0,
            "proposalDirectSeedWindowFrames": 0,
            "proposalDirectSeedTightWindowFrames": 0,
            "proposalDirectSeedContextWindowFrames": 0,
            "proposalDirectSeedContextEligibleFrames": 0,
            "proposalDirectSeedContextDuplicateFrames": 0,
            "proposalDirectSeedContextMeanSeedToBoxDistance": 0.0,
            "proposalDirectSeedContextExpandedFrames": 0,
            "proposalDirectSeedContextMeanExpansionPx": 0.0,
            "proposalTouchlineEscapeEligibleFrames": 0,
            "proposalTouchlineEscapeWindowFrames": 0,
            "proposalPlayerRankedWindowFrames": 0,
            "proposalMeanWindowWidth": 0.0,
            "proposalRawDetectedFrames": 0,
            "proposalAfterSeedCollapseFrames": 0,
            "proposalAfterPlayerWindowFrames": 0,
            "proposalAfterFalseBallSuppressionFrames": 0,
            "proposalCollapsedFrames": 0,
            "proposalCollapsedSegmentCount": 0,
            "proposalDirectSeedDetectedFrames": 0,
            "proposalDirectSeedTightDetectedFrames": 0,
            "proposalDirectSeedContextDetectedFrames": 0,
            "proposalTouchlineEscapeDetectedFrames": 0,
            "proposalTouchlineEscapeSelectedFrames": 0,
            "proposalTouchlineEscapeRejectionCounts": {},
            "proposalRepeatedAnchorSuppressedFrames": 0,
            "proposalAcceptanceSupportGatingAcceptedFrames": 0,
            "proposalAcceptanceSupportGatingRejectedCounts": {},
            "proposalSelectionAdmissionFixAcceptedFrames": 0,
            "proposalSelectionAdmissionFixRejectedCounts": {},
            "proposalSelectionAdmissionFixTruthSeedFrames": 0,
            "proposalSelectionAdmissionFixApproachFamily": None,
            "proposalSupportViabilityAdmissionFixAcceptedFrames": 0,
            "proposalSupportViabilityAdmissionFixRejectedCounts": {},
            "proposalSupportViabilityAdmissionFixTruthSeedFrames": 0,
            "proposalSupportViabilityAdmissionFixApproachFamily": None,
            "proposalBaselineGuidedRescueAvailableFrames": 0,
            "proposalBaselineGuidedRescueUsedFrames": 0,
            "proposalBaselineGuidedRescueSkippedExistingFrames": 0,
            "proposalBaselineGuidedRescueSkippedEdgeFrames": 0,
            "proposalBaselineGuidedRescueSelectedFrames": 0,
            "proposalContinuityBridgeGapFrames": 0,
            "proposalContinuityBridgeCandidateFrames": 0,
            "proposalContinuityBridgeAcceptedFrames": 0,
            "proposalContinuityBridgeRejectedEdgeFrames": 0,
            "proposalContinuityBridgeRejectedContinuityFrames": 0,
            "proposalContinuityBridgeRejectedSupportFrames": 0,
            "proposalContinuityBridgeRejectedRepeatedAnchorFrames": 0,
            "proposalCandidateEdgeShareBeforeSelection": 0.0,
            "proposalCandidateEdgeShareAfterSelection": 0.0,
            "proposalWindowKindCandidateCounts": {},
            "proposalWindowKindSelectedCounts": {},
            "proposalDirectSeedHiResRetryFrames": 0,
            "proposalDirectSeedHiResRetryDetectedFrames": 0,
            "proposalDirectSeedZeroDetectFrames": 0,
            "proposalDirectSeedScale1600AttemptFrames": 0,
            "proposalDirectSeedScale960AttemptFrames": 0,
            "proposalDirectSeedScale1920AttemptFrames": 0,
            "proposalDirectSeedScale1600RawDetectionFrames": 0,
            "proposalDirectSeedScale960RawDetectionFrames": 0,
            "proposalDirectSeedScale1920RawDetectionFrames": 0,
            "proposalDirectSeedScale1600CandidateFrames": 0,
            "proposalDirectSeedScale960CandidateFrames": 0,
            "proposalDirectSeedScale1920CandidateFrames": 0,
            "proposalDirectSeedScale1600ElapsedSeconds": 0.0,
            "proposalDirectSeedScale960ElapsedSeconds": 0.0,
            "proposalDirectSeedScale1920ElapsedSeconds": 0.0,
            "proposalDirectSeedFallbackElapsedSeconds": 0.0,
            "proposalDirectSeedMultiScaleRetryFrames": 0,
            "proposalDirectSeedMultiScaleDetectedFrames": 0,
            "proposalDirectSeedRawHitFilteredOutFrames": 0,
            "proposalDirectSeedCropEdgeRejectedFrames": 0,
            "proposalDirectSeedCropCenterYRejectedFrames": 0,
            "proposalDirectSeedPitchPolygonRejectedFrames": 0,
            "primaryPitchPolygonRescueEligibleCount": 0,
            "primaryPitchPolygonRescueEligibleFrames": 0,
            "primaryPitchPolygonRescuedCount": 0,
            "primaryPitchPolygonRescuedFrames": 0,
            "proposalDirectSeedMeanCropArea": 0.0,
            "proposalDirectSeedTightMeanCropArea": 0.0,
            "proposalDirectSeedContextMeanCropArea": 0.0,
            "proposalTouchlineEscapeMeanCropArea": 0.0,
            "proposalPlayerRankedMeanCropArea": 0.0,
            "proposalDirectSeedMeanDetectedBallBoxArea": 0.0,
            "proposalTouchlineEscapeMeanDetectedBallBoxArea": 0.0,
            "proposalPlayerRankedMeanDetectedBallBoxArea": 0.0,
            "proposalPlayerRankedDetectedFrames": 0,
            "proposalExactSeedDetectedFrames": 0,
            "proposalInterpolatedSeedDetectedFrames": 0,
            "proposalSingleSeedDetectedFrames": 0,
            "directSeedRetryPolicy": str(profile.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)),
            "directSeedRetryScales": [
                int(scale)
                for scale in (profile.get("directSeedRetryScales") or DIRECT_SEED_RETRY_SCALES)
            ],
        }
        profile_progress_context = {
            "recoveryProfileName": str(profile.get("name", "")),
            "recoveryProfileIndex": profile_index,
            "recoveryProfileCount": profile_count,
            "recoveryProfileCropMode": str(profile.get("cropMode", "")),
            "recoveryProfileImgsz": int(settings["imgsz"]),
            "recoveryProfileConf": float(settings["conf"]),
            "directSeedRetryPolicy": str(profile.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)),
            "directSeedRetryScales": [
                int(scale)
                for scale in (profile.get("directSeedRetryScales") or DIRECT_SEED_RETRY_SCALES)
            ],
        }

        def emit_profile_progress(stage_status, profile_progress_context=profile_progress_context, **extra_fields):
            if progress_callback is None:
                return
            try:
                progress_callback(
                    {
                        "stageStatus": stage_status,
                        **profile_progress_context,
                        **extra_fields,
                    }
                )
            except Exception:
                return

        emit_profile_progress("profile_started")
        if (
            profile.get("cropMode") == "anchor_corridor"
            and frame_shape is not None
            and observed_source_anchors
        ):
            crop_windows_by_frame, corridor_breakdown = _build_anchor_corridor_crop_windows_by_frame(
                frame_shape,
                frame_interval=frame_interval,
                observed_source_anchors=observed_source_anchors,
                player_windows=profile_player_windows,
                frame_count=total_frame_count,
                corridor_half_width_px=int(profile.get("corridorHalfWidthPx", 0)),
                corridor_padding_px=int(profile.get("corridorPaddingPx", 0)),
            )
        if (
            profile.get("cropMode") == "proposal_windows"
            and frame_shape is not None
        ):
            crop_windows_by_frame, proposal_breakdown = _build_player_proposal_crop_windows_by_frame(
                frame_shape,
                frame_interval=frame_interval,
                player_rows=profile_player_rows or [],
                observed_source_anchors=observed_source_anchors,
                baseline_guided_rescue_reference=baseline_guided_rescue_reference,
                frame_count=total_frame_count,
                max_proposals_per_frame=int(profile.get("proposalMaxWindowsPerFrame", DEFAULT_PLAYER_PROPOSAL_MAX_WINDOWS_PER_FRAME)),
                proposal_crop_width_ratio=float(profile.get("proposalCropWidthRatio", profile.get("maxCropWidthRatio", 0.35))),
                proposal_crop_height_ratio=float(profile.get("proposalCropHeightRatio", profile.get("proposalCropWidthRatio", profile.get("maxCropWidthRatio", 0.35)))),
                proposal_crop_padding_px=int(profile.get("proposalCropPaddingPx", PLAYER_PROPOSAL_CROP_PADDING_PX)),
                source_clip_id=source_clip_id,
                edge_share_repair_profile=edge_share_repair_profile,
                proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
                reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
            )
        if base_rows is None:
            recover_result = recover_ball_rows(
                video_path,
                model=model,
                detector_profile=detector_profile,
                calibrations=calibrations,
                H=H,
                pitch_points=pitch_points,
                fps=fps,
                frame_interval=frame_interval,
                player_windows=profile_player_windows,
                crop_windows_by_frame=crop_windows_by_frame,
                recovery_imgsz=settings["imgsz"],
                recovery_conf=settings["conf"],
                crop_edge_margin=int(profile.get("cropEdgeMargin", 0)),
                max_crop_center_y_ratio=float(profile.get("maxCropCenterYRatio", 0.0)),
                max_crop_width_ratio=float(profile.get("maxCropWidthRatio", 0.0)),
                dedupe_same_frame=profile.get("cropMode") != "proposal_windows",
                return_diagnostics=profile.get("cropMode") == "proposal_windows",
                direct_seed_retry_policy=str(profile.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)),
                direct_seed_retry_scales=tuple(
                    int(scale)
                    for scale in (profile.get("directSeedRetryScales") or DIRECT_SEED_RETRY_SCALES)
                ),
                progress_callback=progress_callback,
                progress_interval_seconds=progress_interval_seconds,
                progress_context=profile_progress_context,
                source_clip_id=source_clip_id,
                edge_share_repair_profile=edge_share_repair_profile,
                frame_source=decode_adapter,
            )
            if profile.get("cropMode") == "proposal_windows":
                if (
                    isinstance(recover_result, tuple)
                    and len(recover_result) == 2
                    and isinstance(recover_result[1], dict)
                ):
                    base_rows, inference_diagnostics = recover_result
                else:
                    base_rows = recover_result
                    inference_diagnostics = {}
                proposal_breakdown.update(
                    {
                        "proposalDirectSeedHiResRetryFrames": int(
                            inference_diagnostics.get("proposalDirectSeedHiResRetryFrames", 0)
                        ),
                        "proposalDirectSeedHiResRetryDetectedFrames": int(
                            inference_diagnostics.get("proposalDirectSeedHiResRetryDetectedFrames", 0)
                        ),
                        "proposalDirectSeedZeroDetectFrames": int(
                            inference_diagnostics.get("proposalDirectSeedZeroDetectFrames", 0)
                        ),
                        "proposalDirectSeedScale1600AttemptFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1600AttemptFrames", 0)
                        ),
                        "proposalDirectSeedScale960AttemptFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale960AttemptFrames", 0)
                        ),
                        "proposalDirectSeedScale1920AttemptFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1920AttemptFrames", 0)
                        ),
                        "proposalDirectSeedScale1600RawDetectionFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1600RawDetectionFrames", 0)
                        ),
                        "proposalDirectSeedScale960RawDetectionFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale960RawDetectionFrames", 0)
                        ),
                        "proposalDirectSeedScale1920RawDetectionFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1920RawDetectionFrames", 0)
                        ),
                        "proposalDirectSeedScale1600CandidateFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1600CandidateFrames", 0)
                        ),
                        "proposalDirectSeedScale960CandidateFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale960CandidateFrames", 0)
                        ),
                        "proposalDirectSeedScale1920CandidateFrames": int(
                            inference_diagnostics.get("proposalDirectSeedScale1920CandidateFrames", 0)
                        ),
                        "proposalDirectSeedScale1600ElapsedSeconds": round(
                            float(inference_diagnostics.get("proposalDirectSeedScale1600ElapsedSeconds", 0.0)),
                            3,
                        ),
                        "proposalDirectSeedScale960ElapsedSeconds": round(
                            float(inference_diagnostics.get("proposalDirectSeedScale960ElapsedSeconds", 0.0)),
                            3,
                        ),
                        "proposalDirectSeedScale1920ElapsedSeconds": round(
                            float(inference_diagnostics.get("proposalDirectSeedScale1920ElapsedSeconds", 0.0)),
                            3,
                        ),
                        "proposalDirectSeedFallbackElapsedSeconds": round(
                            float(inference_diagnostics.get("proposalDirectSeedFallbackElapsedSeconds", 0.0)),
                            3,
                        ),
                        "proposalDirectSeedMultiScaleRetryFrames": int(
                            inference_diagnostics.get("proposalDirectSeedMultiScaleRetryFrames", 0)
                        ),
                        "proposalDirectSeedMultiScaleDetectedFrames": int(
                            inference_diagnostics.get("proposalDirectSeedMultiScaleDetectedFrames", 0)
                        ),
                        "proposalDirectSeedRawHitFilteredOutFrames": int(
                            inference_diagnostics.get("proposalDirectSeedRawHitFilteredOutFrames", 0)
                        ),
                        "proposalDirectSeedCropEdgeRejectedFrames": int(
                            inference_diagnostics.get("proposalDirectSeedCropEdgeRejectedFrames", 0)
                        ),
                        "proposalDirectSeedCropCenterYRejectedFrames": int(
                            inference_diagnostics.get("proposalDirectSeedCropCenterYRejectedFrames", 0)
                        ),
                        "proposalDirectSeedPitchPolygonRejectedFrames": int(
                            inference_diagnostics.get("proposalDirectSeedPitchPolygonRejectedFrames", 0)
                        ),
                        "primaryPitchPolygonRescueEligibleCount": int(
                            inference_diagnostics.get("primaryPitchPolygonRescueEligibleCount", 0)
                        ),
                        "primaryPitchPolygonRescueEligibleFrames": int(
                            inference_diagnostics.get("primaryPitchPolygonRescueEligibleFrames", 0)
                        ),
                        "primaryPitchPolygonRescuedCount": int(
                            inference_diagnostics.get("primaryPitchPolygonRescuedCount", 0)
                        ),
                        "primaryPitchPolygonRescuedFrames": int(
                            inference_diagnostics.get("primaryPitchPolygonRescuedFrames", 0)
                        ),
                        "proposalDirectSeedMeanCropArea": round(
                            float(inference_diagnostics.get("proposalDirectSeedMeanCropArea", 0.0)),
                            2,
                        ),
                        "proposalDirectSeedTightMeanCropArea": round(
                            float(inference_diagnostics.get("proposalDirectSeedTightMeanCropArea", 0.0)),
                            2,
                        ),
                        "proposalDirectSeedContextMeanCropArea": round(
                            float(inference_diagnostics.get("proposalDirectSeedContextMeanCropArea", 0.0)),
                            2,
                        ),
                        "proposalTouchlineEscapeMeanCropArea": round(
                            float(inference_diagnostics.get("proposalTouchlineEscapeMeanCropArea", 0.0)),
                            2,
                        ),
                        "proposalPlayerRankedMeanCropArea": round(
                            float(inference_diagnostics.get("proposalPlayerRankedMeanCropArea", 0.0)),
                            2,
                        ),
                        "proposalDirectSeedMeanDetectedBallBoxArea": round(
                            float(inference_diagnostics.get("proposalDirectSeedMeanDetectedBallBoxArea", 0.0)),
                            2,
                        ),
                        "proposalTouchlineEscapeMeanDetectedBallBoxArea": round(
                            float(inference_diagnostics.get("proposalTouchlineEscapeMeanDetectedBallBoxArea", 0.0)),
                            2,
                        ),
                        "proposalPlayerRankedMeanDetectedBallBoxArea": round(
                            float(inference_diagnostics.get("proposalPlayerRankedMeanDetectedBallBoxArea", 0.0)),
                            2,
                        ),
                        "proposalTouchlineEscapeDetectedFrames": int(
                            inference_diagnostics.get("proposalTouchlineEscapeDetectedFrames", 0)
                        ),
                        "proposalTouchlineInboardDetectedFrames": int(
                            inference_diagnostics.get("proposalTouchlineInboardDetectedFrames", 0)
                        ),
                        "proposalReopenedRawCandidateFrames": int(
                            inference_diagnostics.get("proposalReopenedRawCandidateFrames", 0)
                        ),
                    }
                )
                for diagnostic_key, diagnostic_value in inference_diagnostics.items():
                    if not str(diagnostic_key).startswith("proposalDirectSeedScale"):
                        continue
                    if str(diagnostic_key).endswith("ElapsedSeconds"):
                        proposal_breakdown[diagnostic_key] = round(float(diagnostic_value), 3)
                    else:
                        proposal_breakdown[diagnostic_key] = int(diagnostic_value)
                emit_profile_progress(
                    "profile_recovered",
                    proposalDirectSeedHiResRetryFrames=proposal_breakdown["proposalDirectSeedHiResRetryFrames"],
                    proposalDirectSeedHiResRetryDetectedFrames=proposal_breakdown["proposalDirectSeedHiResRetryDetectedFrames"],
                    proposalDirectSeedScale1600AttemptFrames=proposal_breakdown["proposalDirectSeedScale1600AttemptFrames"],
                    proposalDirectSeedScale960AttemptFrames=proposal_breakdown["proposalDirectSeedScale960AttemptFrames"],
                    proposalDirectSeedScale1920AttemptFrames=proposal_breakdown["proposalDirectSeedScale1920AttemptFrames"],
                    proposalDirectSeedScale1600ElapsedSeconds=proposal_breakdown["proposalDirectSeedScale1600ElapsedSeconds"],
                    proposalDirectSeedScale960ElapsedSeconds=proposal_breakdown["proposalDirectSeedScale960ElapsedSeconds"],
                    proposalDirectSeedScale1920ElapsedSeconds=proposal_breakdown["proposalDirectSeedScale1920ElapsedSeconds"],
                    proposalDirectSeedFallbackElapsedSeconds=proposal_breakdown["proposalDirectSeedFallbackElapsedSeconds"],
                )
            else:
                base_rows = recover_result
            cached_rows[cache_key] = base_rows

        recovered_rows = list(base_rows)
        if profile.get("cropMode") == "proposal_windows":
            proposal_seed_collapse = _collapse_proposal_recovered_ball_candidates(
                recovered_rows,
                player_rows=player_rows,
                max_frame_gap=frame_interval,
                source_clip_id=source_clip_id,
                edge_share_repair_profile=edge_share_repair_profile,
                proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
            )
            recovered_rows = list(proposal_seed_collapse.get("rows") or [])
            proposal_breakdown.update(
                {
                    "proposalRawDetectedFrames": int(
                        proposal_seed_collapse.get("proposalRawDetectedFrames", 0)
                    ),
                    "proposalAfterSeedCollapseFrames": int(
                        proposal_seed_collapse.get("proposalAfterSeedCollapseFrames", 0)
                    ),
                    "proposalAfterPlayerWindowFrames": int(
                        proposal_seed_collapse.get("proposalAfterPlayerWindowFrames", 0)
                    ),
                    "proposalAfterFalseBallSuppressionFrames": int(
                        proposal_seed_collapse.get("proposalAfterFalseBallSuppressionFrames", 0)
                    ),
                    "proposalCollapsedFrames": int(
                        proposal_seed_collapse.get("proposalCollapsedFrames", 0)
                    ),
                    "proposalCollapsedSegmentCount": int(
                        proposal_seed_collapse.get("proposalCollapsedSegmentCount", 0)
                    ),
                    "proposalDirectSeedDetectedFrames": int(
                        proposal_seed_collapse.get("proposalDirectSeedDetectedFrames", 0)
                    ),
                    "proposalDirectSeedTightDetectedFrames": int(
                        proposal_seed_collapse.get("proposalDirectSeedTightDetectedFrames", 0)
                    ),
                    "proposalDirectSeedContextDetectedFrames": int(
                        proposal_seed_collapse.get("proposalDirectSeedContextDetectedFrames", 0)
                    ),
                    "proposalTouchlineEscapeDetectedFrames": int(
                        proposal_seed_collapse.get("proposalTouchlineEscapeDetectedFrames", 0)
                    ),
                    "proposalTouchlineInboardDetectedFrames": int(
                        proposal_seed_collapse.get("proposalTouchlineInboardDetectedFrames", 0)
                    ),
                    "proposalTouchlineEscapeSelectedFrames": int(
                        proposal_seed_collapse.get("proposalTouchlineEscapeSelectedFrames", 0)
                    ),
                    "proposalReopenedRawCandidateFrames": int(
                        proposal_seed_collapse.get("proposalReopenedRawCandidateFrames", 0)
                    ),
                    "proposalReopenedRawCandidateSelectedFrames": int(
                        proposal_seed_collapse.get("proposalReopenedRawCandidateSelectedFrames", 0)
                    ),
                    "proposalTouchlineEscapeRejectionCounts": dict(
                        proposal_seed_collapse.get("proposalTouchlineEscapeRejectionCounts", {})
                        if isinstance(proposal_seed_collapse.get("proposalTouchlineEscapeRejectionCounts"), dict)
                        else {}
                    ),
                    "proposalZeroTouchlineCandidateReasonCounts": dict(
                        proposal_seed_collapse.get("proposalZeroTouchlineCandidateReasonCounts", {})
                        if isinstance(proposal_seed_collapse.get("proposalZeroTouchlineCandidateReasonCounts"), dict)
                        else {}
                    ),
                    "proposalRepeatedAnchorSuppressedFrames": int(
                        proposal_seed_collapse.get("proposalRepeatedAnchorSuppressedFrames", 0)
                    ),
                    "proposalAcceptanceSupportGatingAcceptedFrames": int(
                        proposal_seed_collapse.get("proposalAcceptanceSupportGatingAcceptedFrames", 0)
                    ),
                    "proposalAcceptanceSupportGatingRejectedCounts": dict(
                        proposal_seed_collapse.get("proposalAcceptanceSupportGatingRejectedCounts", {})
                        if isinstance(
                            proposal_seed_collapse.get("proposalAcceptanceSupportGatingRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSelectionAdmissionFixAcceptedFrames": int(
                        proposal_seed_collapse.get("proposalSelectionAdmissionFixAcceptedFrames", 0)
                    ),
                    "proposalSelectionAdmissionFixRejectedCounts": dict(
                        proposal_seed_collapse.get("proposalSelectionAdmissionFixRejectedCounts", {})
                        if isinstance(
                            proposal_seed_collapse.get("proposalSelectionAdmissionFixRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSelectionAdmissionFixTruthSeedFrames": int(
                        proposal_seed_collapse.get("proposalSelectionAdmissionFixTruthSeedFrames", 0)
                    ),
                    "proposalSelectionAdmissionFixApproachFamily": (
                        str(proposal_seed_collapse.get("proposalSelectionAdmissionFixApproachFamily"))
                        if proposal_seed_collapse.get("proposalSelectionAdmissionFixApproachFamily")
                        else None
                    ),
                    "proposalSupportViabilityAdmissionFixAcceptedFrames": int(
                        proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixAcceptedFrames", 0)
                    ),
                    "proposalSupportViabilityAdmissionFixRejectedCounts": dict(
                        proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixRejectedCounts", {})
                        if isinstance(
                            proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSupportViabilityAdmissionFixTruthSeedFrames": int(
                        proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixTruthSeedFrames", 0)
                    ),
                    "proposalSupportViabilityAdmissionFixApproachFamily": (
                        str(proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixApproachFamily"))
                        if proposal_seed_collapse.get("proposalSupportViabilityAdmissionFixApproachFamily")
                        else None
                    ),
                    "proposalBaselineGuidedRescueSelectedFrames": int(
                        proposal_seed_collapse.get("proposalBaselineGuidedRescueSelectedFrames", 0)
                    ),
                    "proposalContinuityBridgeGapFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeGapFrames", 0)
                    ),
                    "proposalContinuityBridgeCandidateFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeCandidateFrames", 0)
                    ),
                    "proposalContinuityBridgeAcceptedFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeAcceptedFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedEdgeFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeRejectedEdgeFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedContinuityFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeRejectedContinuityFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedSupportFrames": int(
                        proposal_seed_collapse.get("proposalContinuityBridgeRejectedSupportFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedRepeatedAnchorFrames": int(
                        proposal_seed_collapse.get(
                            "proposalContinuityBridgeRejectedRepeatedAnchorFrames", 0
                        )
                    ),
                    "proposalCandidateEdgeShareBeforeSelection": round(
                        float(proposal_seed_collapse.get("proposalCandidateEdgeShareBeforeSelection", 0.0)),
                        3,
                    ),
                    "proposalCandidateEdgeShareAfterSelection": round(
                        float(proposal_seed_collapse.get("proposalCandidateEdgeShareAfterSelection", 0.0)),
                        3,
                    ),
                    "proposalWindowKindCandidateCounts": dict(
                        proposal_seed_collapse.get("proposalWindowKindCandidateCounts", {})
                        if isinstance(proposal_seed_collapse.get("proposalWindowKindCandidateCounts"), dict)
                        else {}
                    ),
                    "proposalWindowKindSelectedCounts": dict(
                        proposal_seed_collapse.get("proposalWindowKindSelectedCounts", {})
                        if isinstance(proposal_seed_collapse.get("proposalWindowKindSelectedCounts"), dict)
                        else {}
                    ),
                    "proposalTouchlineCandidateModeEntered": bool(
                        proposal_seed_collapse.get("proposalTouchlineCandidateModeEntered", False)
                    ),
                    "proposalPlayerRankedDetectedFrames": int(
                        proposal_seed_collapse.get("proposalPlayerRankedDetectedFrames", 0)
                    ),
                    "proposalExactSeedDetectedFrames": int(
                        proposal_seed_collapse.get("proposalExactSeedDetectedFrames", 0)
                    ),
                    "proposalInterpolatedSeedDetectedFrames": int(
                        proposal_seed_collapse.get("proposalInterpolatedSeedDetectedFrames", 0)
                    ),
                    "proposalSingleSeedDetectedFrames": int(
                        proposal_seed_collapse.get("proposalSingleSeedDetectedFrames", 0)
                    ),
                }
            )
        else:
            recovered_rows = _dedupe_same_frame_recovered_rows(recovered_rows)
        if frame_shape is not None and profile_player_windows is not None:
            recovered_rows = filter_recovered_ball_rows_for_profile(
                recovered_rows,
                profile_player_windows,
                frame_shape,
                max_crop_width_ratio=float(profile.get("maxCropWidthRatio", 0.0)),
                crop_edge_margin=int(profile.get("cropEdgeMargin", 0)),
                max_crop_center_y_ratio=float(profile.get("maxCropCenterYRatio", 0.0)),
            )
            if profile.get("cropMode") == "proposal_windows":
                proposal_breakdown["proposalAfterPlayerWindowFrames"] = len(
                    {int(row["Frame_ID"]) for row in recovered_rows if row.get("Entity_Type") == "ball"}
                )
        recovered_rows = suppress_repeated_false_ball_clusters(
            recovered_rows,
            player_windows=profile_player_windows,
        )
        if profile.get("cropMode") == "proposal_windows":
            proposal_breakdown["proposalAfterFalseBallSuppressionFrames"] = len(
                {int(row["Frame_ID"]) for row in recovered_rows if row.get("Entity_Type") == "ball"}
            )
        candidate_summary = summarize_recovered_ball_candidates(
            recovered_rows,
            player_windows=profile_player_windows,
        )
        collapsed_candidate_breakdown = _collapse_recovered_ball_candidates(
            recovered_rows,
            player_rows=player_rows,
            max_frame_gap=frame_interval,
        )
        if profile.get("cropMode") == "proposal_windows":
            proposal_breakdown["proposalCollapsedFrames"] = int(
                collapsed_candidate_breakdown.get("collapsedCandidateFrames", 0)
            )
            proposal_breakdown["proposalCollapsedSegmentCount"] = int(
                collapsed_candidate_breakdown.get("collapsedSegmentCount", 0)
            )
        candidate_summary.update(
            _summarize_recovered_ball_anchor_diagnostics(
                recovered_rows,
                player_rows=player_rows,
                max_frame_gap=frame_interval,
            )
        )
        candidate_summary.update({k: v for k, v in collapsed_candidate_breakdown.items() if k != "rows"})
        candidate_summary.update(corridor_breakdown)
        if profile.get("cropMode") == "proposal_windows":
            candidate_summary.update(proposal_breakdown)
        selected_rows = select_meaningful_recovered_ball_rows(
            recovered_rows,
            player_windows=profile_player_windows,
            player_rows=player_rows,
            source_clip_id=source_clip_id,
            edge_share_repair_profile=edge_share_repair_profile,
        )
        summary = summarize_ball_track_rows(selected_rows)
        summary.update(
            _summarize_recovered_ball_anchor_diagnostics(
                selected_rows,
                player_rows=player_rows,
                max_frame_gap=frame_interval,
            )
        )
        if profile.get("cropMode") == "proposal_windows":
            summary.update(proposal_breakdown)
        reviewed_positive_acceptance_profile_result = (
            _reviewed_positive_acceptance_profile_accepts_rows(
                selected_rows,
                source_clip_id=source_clip_id,
                edge_share_repair_profile=edge_share_repair_profile,
            )
        )
        reviewed_positive_acceptance_profile_accepted = bool(
            reviewed_positive_acceptance_profile_result.get("accepted")
        )
        if reviewed_positive_acceptance_profile_accepted:
            for row in selected_rows:
                row["ReviewedPositiveAcceptanceProfileApplied"] = True
                row["reviewedPositiveAcceptanceProfileApplied"] = True
        selected_score = _score_anchor_weighted_recovery_profile(summary)
        profile_elapsed_seconds = round(time.monotonic() - profile_started_at, 3)
        selected_viable = bool(ball_track_summary_is_viable(summary))
        profile_viable = selected_viable or reviewed_positive_acceptance_profile_accepted
        experiment_results.append(
            {
                "name": profile["name"],
                "cropMode": str(profile.get("cropMode", "")),
                "settings": dict(settings),
                "usePlayerWindows": bool(profile.get("usePlayerWindows")),
                "candidateRows": recovered_rows,
                "candidateSummary": candidate_summary,
                "rows": selected_rows,
                "selectedRows": selected_rows,
                "selectedSummary": summary,
                "selectedScore": selected_score,
                "viable": profile_viable,
                "selectedRowsViable": selected_viable,
                "reviewedPositiveAcceptanceProfileAccepted": (
                    reviewed_positive_acceptance_profile_accepted
                ),
                "reviewedPositiveAcceptanceProfileReason": str(
                    reviewed_positive_acceptance_profile_result.get("reason") or ""
                ),
                "summary": summary,
                "score": selected_score,
                "elapsedSeconds": profile_elapsed_seconds,
                "directSeedRetryPolicy": str(
                    proposal_breakdown.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)
                ),
                "directSeedRetryScales": [
                    int(scale)
                    for scale in (
                        proposal_breakdown.get("directSeedRetryScales")
                        or DIRECT_SEED_RETRY_SCALES
                    )
                ],
            }
        )
        summary_frames = max(int(summary.get("frames", 0)), 1)
        anchored_frame_count = int(summary.get("anchoredFrameCount", 0))
        supported_frame_count = int(summary.get("supportedFrameCount", 0))
        emit_profile_progress(
            "profile_completed",
            recoveryProfileElapsedSeconds=profile_elapsed_seconds,
            recoveryProfileCandidateRows=len(recovered_rows),
            recoveryProfileSelectedFrames=int(summary.get("frames", 0)),
            recoveryProfileAnchoredFrameCount=anchored_frame_count,
            recoveryProfileSupportedFrameShare=round(
                supported_frame_count / summary_frames,
                6,
            ),
            recoveryProfileAnchoredFrameShare=round(
                anchored_frame_count / summary_frames,
                6,
            ),
            recoveryProfileAnchoredPathLength=round(
                float(summary.get("anchoredPathLength", 0.0)),
                3,
            ),
            recoveryProfileUnsupportedEdgeFrameShare=round(
                float(summary.get("unsupportedEdgeFrameShare", 0.0)),
                6,
            ),
            recoveryProfileBridgeFrameCount=int(summary.get("bridgeFrameCount", 0)),
            recoveryProfileSelectedScore=selected_score,
        )
    return experiment_results


def _build_recovery_profile_matrix(results, *, selected_profile_name=None):
    def _frame_id_set(rows):
        frame_ids = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                frame_id = int(row.get("Frame_ID"))
            except (TypeError, ValueError):
                continue
            if frame_id >= 0:
                frame_ids.add(frame_id)
        return sorted(frame_ids)

    def _proposal_frame_diagnostics(
        candidate_rows,
        selected_rows,
        *,
        source_profile_name=None,
        selected_profile_name=None,
        source_profile_viable=False,
        reviewed_positive_acceptance_profile_accepted=False,
        reviewed_positive_acceptance_profile_reason="",
    ):
        selected_frame_ids = set(_frame_id_set(selected_rows))
        by_frame = {}
        for row in candidate_rows or []:
            if not isinstance(row, dict):
                continue
            try:
                frame_id = int(row.get("Frame_ID"))
            except (TypeError, ValueError):
                continue
            if frame_id < 0:
                continue
            diagnostic = by_frame.setdefault(
                frame_id,
                {
                    "frameIndex": frame_id,
                    "proposalGenerated": True,
                    "rawDetected": True,
                    "collapsed": True,
                    "selected": frame_id in selected_frame_ids,
                    "accepted": False,
                    "proposalWindowKinds": set(),
                },
            )
            window_kind = row.get("ProposalWindowKind")
            if window_kind:
                diagnostic["proposalWindowKinds"].add(str(window_kind))
            selection_gate_trace = row.get("SelectionGateTrace") or row.get("selectionGateTrace")
            if isinstance(selection_gate_trace, dict):
                diagnostic["selectionGateTrace"] = dict(selection_gate_trace)
        diagnostics = []
        for frame_id in sorted(by_frame):
            diagnostic = dict(by_frame[frame_id])
            diagnostic["proposalWindowKinds"] = sorted(diagnostic["proposalWindowKinds"])
            if bool(diagnostic.get("selected")):
                selected_profile_accepted = (
                    bool(source_profile_viable)
                    and bool(source_profile_name)
                    and str(source_profile_name) == str(selected_profile_name or "")
                )
                reviewed_positive_override_applied = (
                    selected_profile_accepted
                    and bool(reviewed_positive_acceptance_profile_accepted)
                )
                acceptance_rejection_reason = "accepted_by_selected_profile"
                if reviewed_positive_override_applied:
                    acceptance_rejection_reason = "accepted_by_reviewed_positive_profile"
                elif not bool(source_profile_viable):
                    acceptance_rejection_reason = "source_profile_not_viable"
                elif not selected_profile_accepted:
                    acceptance_rejection_reason = "not_selected_profile"
                diagnostic["acceptanceGateTrace"] = {
                    "acceptedTruthLayerMatch": False,
                    "acceptanceGateRejected": not selected_profile_accepted,
                    "continuityRejected": False,
                    "repeatedAnchorRejected": False,
                    "acceptedByReviewedPositiveProfile": reviewed_positive_override_applied,
                    "acceptanceRejectionReason": acceptance_rejection_reason,
                    "selectedProfileAccepted": selected_profile_accepted,
                    "selectedProfileName": selected_profile_name,
                    "sourceProfileName": source_profile_name,
                    "sourceProfileViable": bool(source_profile_viable),
                    "viabilityOverrideApplied": reviewed_positive_override_applied,
                    "viabilityOverrideReason": (
                        str(reviewed_positive_acceptance_profile_reason or "")
                        if reviewed_positive_override_applied
                        else ""
                    ),
                    "viabilityRejected": (
                        not bool(source_profile_viable)
                        and not reviewed_positive_override_applied
                    ),
                }
                diagnostic["accepted"] = selected_profile_accepted
            diagnostics.append(diagnostic)
        return diagnostics

    profiles = []
    for result in results or []:
        candidate_summary = dict(result.get("candidateSummary") or {})
        selected_summary = dict(result.get("selectedSummary") or {})
        candidate_rows = result.get("candidateRows") or []
        selected_rows = result.get("selectedRows") or []
        candidate_frame_ids = _frame_id_set(candidate_rows)
        selected_frame_ids = _frame_id_set(selected_rows)
        profiles.append(
            {
                "name": str(result.get("name", "")),
                "cropMode": str(result.get("cropMode", "")),
                "viable": bool(result.get("viable")),
                "elapsedSeconds": round(float(result.get("elapsedSeconds", 0.0)), 3),
                "candidateFrames": int(candidate_summary.get("uniqueFrames", 0)),
                "selectedFrames": int(selected_summary.get("frames", 0)),
                "candidateSegmentCount": int(candidate_summary.get("segmentCount", 0)),
                "selectedSegmentCount": int(selected_summary.get("segmentCount", 0)),
                "corridorCandidateFrames": int(candidate_summary.get("corridorCandidateFrames", 0)),
                "corridorFramesWithTwoAnchors": int(candidate_summary.get("corridorFramesWithTwoAnchors", 0)),
                "corridorFramesWithSingleAnchor": int(candidate_summary.get("corridorFramesWithSingleAnchor", 0)),
                "corridorMeanWidth": round(float(candidate_summary.get("corridorMeanWidth", 0.0)), 2),
                "proposalCandidateFrames": int(candidate_summary.get("proposalCandidateFrames", 0)),
                "proposalWindowCount": int(candidate_summary.get("proposalWindowCount", 0)),
                "proposalFramesWithAnchorSeed": int(candidate_summary.get("proposalFramesWithAnchorSeed", 0)),
                "proposalFramesWithoutAnchorSeed": int(candidate_summary.get("proposalFramesWithoutAnchorSeed", 0)),
                "proposalExactSeedFrames": int(candidate_summary.get("proposalExactSeedFrames", 0)),
                "proposalInterpolatedSeedFrames": int(candidate_summary.get("proposalInterpolatedSeedFrames", 0)),
                "proposalSingleSeedFrames": int(candidate_summary.get("proposalSingleSeedFrames", 0)),
                "proposalUnseededFrames": int(candidate_summary.get("proposalUnseededFrames", 0)),
                "proposalBaselineGuidedRescueAvailableFrames": int(
                    candidate_summary.get("proposalBaselineGuidedRescueAvailableFrames", 0)
                ),
                "proposalBaselineGuidedRescueUsedFrames": int(
                    candidate_summary.get("proposalBaselineGuidedRescueUsedFrames", 0)
                ),
                "proposalBaselineGuidedRescueSkippedExistingFrames": int(
                    candidate_summary.get("proposalBaselineGuidedRescueSkippedExistingFrames", 0)
                ),
                "proposalBaselineGuidedRescueSkippedEdgeFrames": int(
                    candidate_summary.get("proposalBaselineGuidedRescueSkippedEdgeFrames", 0)
                ),
                "proposalBaselineGuidedRescueSelectedFrames": int(
                    candidate_summary.get("proposalBaselineGuidedRescueSelectedFrames", 0)
                ),
                "reviewedPositiveAnchorSeedFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorSeedFrames", 0)
                ),
                "reviewedPositiveAnchorUsedFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorUsedFrames", 0)
                ),
                "reviewedPositiveAnchorWindowFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorWindowFrames", 0)
                ),
                "reviewedPositiveAnchorDuplicateWindowFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorDuplicateWindowFrames", 0)
                ),
                "reviewedPositiveAnchorSkippedMissingSourceFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorSkippedMissingSourceFrames", 0)
                ),
                "reviewedPositiveAnchorSkippedExistingFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorSkippedExistingFrames", 0)
                ),
                "reviewedPositiveAnchorSkippedExcludedFrames": int(
                    candidate_summary.get("reviewedPositiveAnchorSkippedExcludedFrames", 0)
                ),
                "reviewedPositiveAnchorMaxWindowsPerFrame": int(
                    candidate_summary.get("reviewedPositiveAnchorMaxWindowsPerFrame", 0)
                ),
                "proposalContinuityBridgeGapFrames": int(
                    candidate_summary.get("proposalContinuityBridgeGapFrames", 0)
                ),
                "proposalContinuityBridgeCandidateFrames": int(
                    candidate_summary.get("proposalContinuityBridgeCandidateFrames", 0)
                ),
                "proposalContinuityBridgeAcceptedFrames": int(
                    candidate_summary.get("proposalContinuityBridgeAcceptedFrames", 0)
                ),
                "proposalAcceptanceSupportGatingAcceptedFrames": int(
                    candidate_summary.get("proposalAcceptanceSupportGatingAcceptedFrames", 0)
                ),
                "proposalAcceptanceSupportGatingRejectedCounts": dict(
                    candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts")
                    if isinstance(candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts"), dict)
                    else {}
                ),
                "proposalSelectionAdmissionFixAcceptedFrames": int(
                    candidate_summary.get("proposalSelectionAdmissionFixAcceptedFrames", 0)
                ),
                "proposalSelectionAdmissionFixRejectedCounts": dict(
                    candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts")
                    if isinstance(candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts"), dict)
                    else {}
                ),
                "proposalSelectionAdmissionFixTruthSeedFrames": int(
                    candidate_summary.get("proposalSelectionAdmissionFixTruthSeedFrames", 0)
                ),
                "proposalSelectionAdmissionFixApproachFamily": (
                    str(candidate_summary.get("proposalSelectionAdmissionFixApproachFamily"))
                    if candidate_summary.get("proposalSelectionAdmissionFixApproachFamily")
                    else None
                ),
                "proposalSupportViabilityAdmissionFixAcceptedFrames": int(
                    candidate_summary.get("proposalSupportViabilityAdmissionFixAcceptedFrames", 0)
                ),
                "proposalSupportViabilityAdmissionFixRejectedCounts": dict(
                    candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts")
                    if isinstance(candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts"), dict)
                    else {}
                ),
                "proposalSupportViabilityAdmissionFixTruthSeedFrames": int(
                    candidate_summary.get("proposalSupportViabilityAdmissionFixTruthSeedFrames", 0)
                ),
                "proposalSupportViabilityAdmissionFixApproachFamily": (
                    str(candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily"))
                    if candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily")
                    else None
                ),
                "proposalContinuityBridgeRejectedEdgeFrames": int(
                    candidate_summary.get("proposalContinuityBridgeRejectedEdgeFrames", 0)
                ),
                "proposalContinuityBridgeRejectedContinuityFrames": int(
                    candidate_summary.get("proposalContinuityBridgeRejectedContinuityFrames", 0)
                ),
                "proposalContinuityBridgeRejectedSupportFrames": int(
                    candidate_summary.get("proposalContinuityBridgeRejectedSupportFrames", 0)
                ),
                "proposalContinuityBridgeRejectedRepeatedAnchorFrames": int(
                    candidate_summary.get("proposalContinuityBridgeRejectedRepeatedAnchorFrames", 0)
                ),
                "proposalDirectSeedWindowFrames": int(candidate_summary.get("proposalDirectSeedWindowFrames", 0)),
                "proposalDirectSeedTightWindowFrames": int(
                    candidate_summary.get("proposalDirectSeedTightWindowFrames", 0)
                ),
                "proposalDirectSeedContextWindowFrames": int(
                    candidate_summary.get("proposalDirectSeedContextWindowFrames", 0)
                ),
                "proposalDirectSeedContextEligibleFrames": int(
                    candidate_summary.get("proposalDirectSeedContextEligibleFrames", 0)
                ),
                "proposalDirectSeedContextDuplicateFrames": int(
                    candidate_summary.get("proposalDirectSeedContextDuplicateFrames", 0)
                ),
                "proposalDirectSeedContextMeanSeedToBoxDistance": round(
                    float(candidate_summary.get("proposalDirectSeedContextMeanSeedToBoxDistance", 0.0)),
                    2,
                ),
                "proposalDirectSeedContextExpandedFrames": int(
                    candidate_summary.get("proposalDirectSeedContextExpandedFrames", 0)
                ),
                "proposalDirectSeedContextMeanExpansionPx": round(
                    float(candidate_summary.get("proposalDirectSeedContextMeanExpansionPx", 0.0)),
                    2,
                ),
                "proposalDirectSeedHiResRetryFrames": int(
                    candidate_summary.get("proposalDirectSeedHiResRetryFrames", 0)
                ),
                "proposalDirectSeedHiResRetryDetectedFrames": int(
                    candidate_summary.get("proposalDirectSeedHiResRetryDetectedFrames", 0)
                ),
                "proposalDirectSeedZeroDetectFrames": int(
                    candidate_summary.get("proposalDirectSeedZeroDetectFrames", 0)
                ),
                "proposalDirectSeedScale1600AttemptFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1600AttemptFrames", 0)
                ),
                "proposalDirectSeedScale960AttemptFrames": int(
                    candidate_summary.get("proposalDirectSeedScale960AttemptFrames", 0)
                ),
                "proposalDirectSeedScale1920AttemptFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1920AttemptFrames", 0)
                ),
                "proposalDirectSeedScale1600RawDetectionFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1600RawDetectionFrames", 0)
                ),
                "proposalDirectSeedScale960RawDetectionFrames": int(
                    candidate_summary.get("proposalDirectSeedScale960RawDetectionFrames", 0)
                ),
                "proposalDirectSeedScale1920RawDetectionFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1920RawDetectionFrames", 0)
                ),
                "proposalDirectSeedScale1600CandidateFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1600CandidateFrames", 0)
                ),
                "proposalDirectSeedScale960CandidateFrames": int(
                    candidate_summary.get("proposalDirectSeedScale960CandidateFrames", 0)
                ),
                "proposalDirectSeedScale1920CandidateFrames": int(
                    candidate_summary.get("proposalDirectSeedScale1920CandidateFrames", 0)
                ),
                "proposalDirectSeedScale1600ElapsedSeconds": round(
                    float(candidate_summary.get("proposalDirectSeedScale1600ElapsedSeconds", 0.0)),
                    3,
                ),
                "proposalDirectSeedScale960ElapsedSeconds": round(
                    float(candidate_summary.get("proposalDirectSeedScale960ElapsedSeconds", 0.0)),
                    3,
                ),
                "proposalDirectSeedScale1920ElapsedSeconds": round(
                    float(candidate_summary.get("proposalDirectSeedScale1920ElapsedSeconds", 0.0)),
                    3,
                ),
                "proposalDirectSeedFallbackElapsedSeconds": round(
                    float(candidate_summary.get("proposalDirectSeedFallbackElapsedSeconds", 0.0)),
                    3,
                ),
                "proposalDirectSeedMultiScaleRetryFrames": int(
                    candidate_summary.get("proposalDirectSeedMultiScaleRetryFrames", 0)
                ),
                "proposalDirectSeedMultiScaleDetectedFrames": int(
                    candidate_summary.get("proposalDirectSeedMultiScaleDetectedFrames", 0)
                ),
                "proposalDirectSeedRawHitFilteredOutFrames": int(
                    candidate_summary.get("proposalDirectSeedRawHitFilteredOutFrames", 0)
                ),
                "proposalDirectSeedCropEdgeRejectedFrames": int(
                    candidate_summary.get("proposalDirectSeedCropEdgeRejectedFrames", 0)
                ),
                "proposalDirectSeedCropCenterYRejectedFrames": int(
                    candidate_summary.get("proposalDirectSeedCropCenterYRejectedFrames", 0)
                ),
                "proposalDirectSeedPitchPolygonRejectedFrames": int(
                    candidate_summary.get("proposalDirectSeedPitchPolygonRejectedFrames", 0)
                ),
                "proposalDirectSeedMeanCropArea": round(
                    float(candidate_summary.get("proposalDirectSeedMeanCropArea", 0.0)),
                    2,
                ),
                "proposalDirectSeedTightMeanCropArea": round(
                    float(candidate_summary.get("proposalDirectSeedTightMeanCropArea", 0.0)),
                    2,
                ),
                "proposalDirectSeedContextMeanCropArea": round(
                    float(candidate_summary.get("proposalDirectSeedContextMeanCropArea", 0.0)),
                    2,
                ),
                "proposalPlayerRankedMeanCropArea": round(
                    float(candidate_summary.get("proposalPlayerRankedMeanCropArea", 0.0)),
                    2,
                ),
                "proposalDirectSeedMeanDetectedBallBoxArea": round(
                    float(candidate_summary.get("proposalDirectSeedMeanDetectedBallBoxArea", 0.0)),
                    2,
                ),
                "proposalPlayerRankedMeanDetectedBallBoxArea": round(
                    float(candidate_summary.get("proposalPlayerRankedMeanDetectedBallBoxArea", 0.0)),
                    2,
                ),
                "proposalPlayerRankedWindowFrames": int(
                    candidate_summary.get("proposalPlayerRankedWindowFrames", 0)
                ),
                "proposalMeanWindowWidth": round(float(candidate_summary.get("proposalMeanWindowWidth", 0.0)), 2),
                "proposalRawDetectedFrames": int(candidate_summary.get("proposalRawDetectedFrames", 0)),
                "proposalRawDetectedFrameIds": candidate_frame_ids,
                "proposalAfterSeedCollapseFrames": int(candidate_summary.get("proposalAfterSeedCollapseFrames", 0)),
                "proposalAfterPlayerWindowFrames": int(candidate_summary.get("proposalAfterPlayerWindowFrames", 0)),
                "proposalAfterFalseBallSuppressionFrames": int(
                    candidate_summary.get("proposalAfterFalseBallSuppressionFrames", 0)
                ),
                "proposalCollapsedFrames": int(candidate_summary.get("proposalCollapsedFrames", 0)),
                "proposalCollapsedFrameIds": candidate_frame_ids,
                "proposalSelectedFrameIds": selected_frame_ids,
                "proposalFrameDiagnostics": _proposal_frame_diagnostics(
                    candidate_rows,
                    selected_rows,
                    source_profile_name=str(result.get("name", "")),
                    selected_profile_name=selected_profile_name,
                    source_profile_viable=bool(result.get("viable")),
                    reviewed_positive_acceptance_profile_accepted=bool(
                        result.get("reviewedPositiveAcceptanceProfileAccepted")
                    ),
                    reviewed_positive_acceptance_profile_reason=str(
                        result.get("reviewedPositiveAcceptanceProfileReason") or ""
                    ),
                ),
                "proposalCollapsedSegmentCount": int(
                    candidate_summary.get("proposalCollapsedSegmentCount", 0)
                ),
                "proposalDirectSeedDetectedFrames": int(
                    candidate_summary.get("proposalDirectSeedDetectedFrames", 0)
                ),
                "proposalDirectSeedTightDetectedFrames": int(
                    candidate_summary.get("proposalDirectSeedTightDetectedFrames", 0)
                ),
                "proposalDirectSeedContextDetectedFrames": int(
                    candidate_summary.get("proposalDirectSeedContextDetectedFrames", 0)
                ),
                "proposalPlayerRankedDetectedFrames": int(
                    candidate_summary.get("proposalPlayerRankedDetectedFrames", 0)
                ),
                "proposalExactSeedDetectedFrames": int(
                    candidate_summary.get("proposalExactSeedDetectedFrames", 0)
                ),
                "proposalInterpolatedSeedDetectedFrames": int(
                    candidate_summary.get("proposalInterpolatedSeedDetectedFrames", 0)
                ),
                "proposalSingleSeedDetectedFrames": int(
                    candidate_summary.get("proposalSingleSeedDetectedFrames", 0)
                ),
                "directSeedRetryPolicy": str(
                    candidate_summary.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)
                ),
                "directSeedRetryScales": [
                    int(scale)
                    for scale in (
                        candidate_summary.get("directSeedRetryScales")
                        or DIRECT_SEED_RETRY_SCALES
                    )
                ],
            }
        )
    return {
        "selectedProfileName": selected_profile_name,
        "profiles": profiles,
    }


def select_best_ball_recovery_profile(results):
    viable_results = [result for result in results if bool(result.get("viable"))]
    if not viable_results:
        return None
    return max(viable_results, key=_recovery_profile_rank)


def extract_torso_color(frame, x1, y1, x2, y2):
    # Note: Assumes BGR channel order (OpenCV default). If frame source changes to RGB,
    # the BGR->RGB swap below would produce incorrect colors.
    height, width = frame.shape[:2]
    left = max(0, min(width, int(x1 + (x2 - x1) * 0.2)))
    right = max(0, min(width, int(x2 - (x2 - x1) * 0.2)))
    top = max(0, min(height, int(y1 + (y2 - y1) * 0.15)))
    bottom = max(0, min(height, int(y1 + (y2 - y1) * 0.55)))

    if right <= left or bottom <= top:
        return None

    patch = frame[top:bottom, left:right]
    if patch.size == 0:
        return None

    mean_bgr = patch.reshape(-1, 3).mean(axis=0)
    return [round(float(mean_bgr[2]), 2), round(float(mean_bgr[1]), 2), round(float(mean_bgr[0]), 2)]


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


class _CountingPredictor:
    def __init__(self, model, on_predict):
        self._model = model
        self._on_predict = on_predict

    def predict(self, *args, **kwargs):
        self._on_predict()
        return self._model.predict(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._model, name)


def process_video(
    video_path,
    output_parquet=None,
    model_path='yolov10n.pt',
    primary_model_path=None,
    auxiliary_ball_model_path=None,
    auxiliary_ball_model_profile=None,
    edge_share_repair_profile=None,
    baseline_guided_rescue_reference_path=None,
    proposal_selection_truth_seed_path=None,
    reviewed_positive_anchor_seed_path=None,
    homography_points=None,
    return_rows=False,
    auto_homography=True,
    progress_callback=None,
    match_id=None,
    job_id=None,
    primary_acquisition_mode=SUPPORTED_PRIMARY_ACQUISITION_MODE,
    frame_source=None,
):
    validate_primary_acquisition_mode(primary_acquisition_mode)
    sample_interval = None
    total_process_video_started_at = time.monotonic()
    phase_timings = _empty_phase_timings()
    source_clip_id = Path(str(video_path)).name
    baseline_guided_rescue_reference = _load_baseline_guided_rescue_reference(
        baseline_guided_rescue_reference_path,
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
    )

    def complete_phase(phase_key, started_at):
        phase_timings[phase_key] = round(max(time.monotonic() - started_at, 0.0), 3)

    def ball_trace_from_rows(stage_name, rows):
        ball_rows = [row for row in rows if row.get("Entity_Type") == "ball"]
        player_rows = [row for row in rows if row.get("Entity_Type") != "ball"]
        ball_frames = sorted({int(row.get("Frame_ID", 0)) for row in ball_rows})
        frame_ids = {int(row.get("Frame_ID", 0)) for row in rows}
        return {
            "stage": stage_name,
            "ballRowCount": len(ball_rows),
            "ballFrameCount": len(ball_frames),
            "playerRowCount": len(player_rows),
            "frameCount": len(frame_ids),
            "trackedPossessionFrames": 0,
            "controlledPossessionFrames": 0,
            "eventCount": 0,
            "eventTypes": {},
            "firstBallFrame": ball_frames[0] if ball_frames else None,
            "lastBallFrame": ball_frames[-1] if ball_frames else None,
        }

    def emit_worker_heartbeat(
        worker_stage,
        stage_status,
        *,
        tracking_frames_seen=None,
        observed_ball_frames=None,
        accepted_ball_frames=None,
        worker_returned_result=False,
        **extra_fields,
    ):
        if progress_callback is None:
            return
        heartbeat = {
            "matchId": match_id,
            "jobId": job_id,
            "workerStage": worker_stage,
            "stageStatus": stage_status,
            "heartbeatAt": _utc_now_iso(),
            "workerStartedProcessing": True,
            "workerReturnedResult": worker_returned_result,
        }
        if tracking_frames_seen is not None:
            heartbeat["trackingFramesSeen"] = int(tracking_frames_seen)
        if sample_interval is not None:
            heartbeat["sampleInterval"] = int(sample_interval)
        if observed_ball_frames is not None:
            heartbeat["observedBallFrames"] = int(observed_ball_frames)
        if accepted_ball_frames is not None:
            heartbeat["acceptedBallFrames"] = int(accepted_ball_frames)
        heartbeat.update(extra_fields)
        try:
            progress_callback(heartbeat)
        except Exception:
            # Heartbeats are best-effort telemetry and must never take down inference.
            return

    def emit_recovery_selection_progress(progress_payload):
        if not isinstance(progress_payload, dict):
            return
        stage_status = str(progress_payload.get("stageStatus", "profile_in_progress") or "profile_in_progress")
        extra_fields = {
            key: value for key, value in progress_payload.items() if key != "stageStatus"
        }
        emit_worker_heartbeat("recoverySelection", stage_status, **extra_fields)

    ball_truth_layers = _build_ball_truth_layers([], [])

    def empty_result():
        return {
            "rows": [],
            "trackColors": {},
            "recoveryDebug": recovery_debug,
            "ballPipelineTrace": ball_pipeline_trace,
            "ballTruthLayers": ball_truth_layers,
            "matchStateEvidence": {"frames": []},
        }

    recovery_debug = {
        "primaryBallFrames": 0,
        "recoveryAttempted": False,
        "recoveryProfileName": None,
        "recoveredCandidateRows": 0,
        "recoveredUniqueFrames": 0,
        "recoveredSelectedFrames": 0,
        "candidateSupportedFrames": 0,
        "candidateAnchoredFrames": 0,
        "candidateBridgeFrames": 0,
        "candidateUnsupportedEdgeFrameShare": 0.0,
        "candidateAnchoredPathLength": 0.0,
        "recoveredSupportedFrames": 0,
        "recoveredAnchoredFrames": 0,
        "recoveredBridgeFrames": 0,
        "recoveredUnsupportedEdgeFrameShare": 0.0,
        "recoveredAnchoredPathLength": 0.0,
        "proposalDirectSeedWindowFrames": 0,
        "proposalDirectSeedTightWindowFrames": 0,
        "proposalDirectSeedContextWindowFrames": 0,
        "proposalDirectSeedContextEligibleFrames": 0,
        "proposalDirectSeedContextDuplicateFrames": 0,
        "proposalDirectSeedContextMeanSeedToBoxDistance": 0.0,
        "proposalDirectSeedContextExpandedFrames": 0,
        "proposalDirectSeedContextMeanExpansionPx": 0.0,
        "proposalDirectSeedHiResRetryFrames": 0,
        "proposalDirectSeedHiResRetryDetectedFrames": 0,
        "proposalDirectSeedZeroDetectFrames": 0,
        "proposalDirectSeedScale1600RawDetectionFrames": 0,
        "proposalDirectSeedScale960RawDetectionFrames": 0,
        "proposalDirectSeedScale1920RawDetectionFrames": 0,
        "proposalDirectSeedScale1600CandidateFrames": 0,
        "proposalDirectSeedScale960CandidateFrames": 0,
        "proposalDirectSeedScale1920CandidateFrames": 0,
        "proposalDirectSeedMultiScaleRetryFrames": 0,
        "proposalDirectSeedMultiScaleDetectedFrames": 0,
        "proposalDirectSeedRawHitFilteredOutFrames": 0,
        "proposalDirectSeedCropEdgeRejectedFrames": 0,
        "proposalDirectSeedCropCenterYRejectedFrames": 0,
        "proposalDirectSeedPitchPolygonRejectedFrames": 0,
        "primaryPitchPolygonRescueEligibleCount": 0,
        "primaryPitchPolygonRescueEligibleFrames": 0,
        "primaryPitchPolygonRescuedCount": 0,
        "primaryPitchPolygonRescuedFrames": 0,
        "proposalDirectSeedMeanCropArea": 0.0,
        "proposalDirectSeedTightMeanCropArea": 0.0,
        "proposalDirectSeedContextMeanCropArea": 0.0,
        "proposalPlayerRankedMeanCropArea": 0.0,
        "proposalDirectSeedMeanDetectedBallBoxArea": 0.0,
        "proposalPlayerRankedMeanDetectedBallBoxArea": 0.0,
        "proposalPlayerRankedWindowFrames": 0,
        "proposalDirectSeedDetectedFrames": 0,
        "proposalDirectSeedTightDetectedFrames": 0,
        "proposalDirectSeedContextDetectedFrames": 0,
        "proposalPlayerRankedDetectedFrames": 0,
        "proposalExactSeedDetectedFrames": 0,
        "proposalInterpolatedSeedDetectedFrames": 0,
        "proposalSingleSeedDetectedFrames": 0,
        "proposalContinuityBridgeGapFrames": 0,
        "proposalContinuityBridgeCandidateFrames": 0,
        "proposalContinuityBridgeAcceptedFrames": 0,
        "proposalContinuityBridgeRejectedEdgeFrames": 0,
        "proposalContinuityBridgeRejectedContinuityFrames": 0,
        "proposalContinuityBridgeRejectedSupportFrames": 0,
        "proposalContinuityBridgeRejectedRepeatedAnchorFrames": 0,
        "proposalAcceptanceSupportGatingAcceptedFrames": 0,
        "proposalAcceptanceSupportGatingRejectedCounts": {},
        "proposalSelectionAdmissionFixAcceptedFrames": 0,
        "proposalSelectionAdmissionFixRejectedCounts": {},
        "proposalSelectionAdmissionFixTruthSeedFrames": 0,
        "proposalSelectionAdmissionFixApproachFamily": None,
        "proposalSupportViabilityAdmissionFixAcceptedFrames": 0,
        "proposalSupportViabilityAdmissionFixRejectedCounts": {},
        "proposalSupportViabilityAdmissionFixTruthSeedFrames": 0,
        "proposalSupportViabilityAdmissionFixApproachFamily": None,
        "candidateEdgeShare": 0.0,
        "nearPlayerWindowShare": 0.0,
        "segmentCount": 0,
        "longestSegmentFrames": 0,
        "selectedEdgeFrameShare": 0.0,
        "selectedPathLength": 0.0,
        "selectedViable": False,
        "recoveryDecision": "not_needed",
        "recoveryApplied": False,
        "directSeedRetryPolicy": DIRECT_SEED_RETRY_POLICY,
        "directSeedRetryScales": list(DIRECT_SEED_RETRY_SCALES),
        "phaseTimings": phase_timings,
        "profileTimings": [],
    }
    ball_pipeline_trace = {
        "traceVersion": BALL_PIPELINE_TRACE_VERSION,
        "matchId": None,
        "jobId": None,
        "processingBackend": None,
        "inputMode": "video",
        "videoPath": str(video_path) if video_path else None,
        "workerPath": None,
        "detectorModelPath": str(primary_model_path or model_path),
        "detectorModelName": Path(str(primary_model_path or model_path)).name,
        "primaryModelPath": str(primary_model_path or model_path),
        "primaryModelName": Path(str(primary_model_path or model_path)).name,
        "primaryAcquisitionMode": primary_acquisition_mode,
        "primaryDetectorModelPath": str(primary_model_path or model_path),
        "primaryDetectorModelName": Path(str(primary_model_path or model_path)).name,
        "auxiliaryBallModelPath": (
            str(auxiliary_ball_model_path) if auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelName": (
            Path(str(auxiliary_ball_model_path)).name if auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelProfile": (
            _normalize_detector_profile(auxiliary_ball_model_profile)
            if auxiliary_ball_model_path is not None
            else None
        ),
        "trackingModelPath": str(primary_model_path or model_path),
        "trackingDetectorProfile": DETECTOR_PROFILE_COCO_TRACKING_FULL,
        "probeModelPath": (
            str(auxiliary_ball_model_path)
            if auxiliary_ball_model_path is not None
            else str(primary_model_path or model_path)
        ),
        "probeDetectorProfile": (
            _normalize_detector_profile(auxiliary_ball_model_profile)
            if auxiliary_ball_model_path is not None
            else DETECTOR_PROFILE_COCO_TRACKING_FULL
        ),
        "probeRecoveryConf": None,
        "probeRecoveryImgsz": None,
        "recoveryModelPath": (
            str(auxiliary_ball_model_path)
            if auxiliary_ball_model_path is not None
            else str(primary_model_path or model_path)
        ),
        "recoveryDetectorProfile": (
            _normalize_detector_profile(auxiliary_ball_model_profile)
            if auxiliary_ball_model_path is not None
            else DETECTOR_PROFILE_COCO_TRACKING_FULL
        ),
        "directSeedRetryPolicy": DIRECT_SEED_RETRY_POLICY,
        "directSeedRetryScales": list(DIRECT_SEED_RETRY_SCALES),
        "baselineGuidedRescueReferencePath": (
            str(baseline_guided_rescue_reference_path)
            if baseline_guided_rescue_reference_path is not None
            else None
        ),
        "baselineGuidedRescueReferenceLoaded": baseline_guided_rescue_reference is not None,
        "phaseTimings": phase_timings,
        "stages": [],
    }

    resolved_primary_model_path = str(primary_model_path or model_path)
    resolved_primary_detector_profile = DETECTOR_PROFILE_COCO_TRACKING_FULL
    resolved_auxiliary_ball_model_profile = (
        _normalize_detector_profile(auxiliary_ball_model_profile)
        if auxiliary_ball_model_path is not None
        else None
    )
    model_load_started_at = time.monotonic()
    emit_worker_heartbeat("modelLoad", "started")
    print(f"Loading YOLO model from {resolved_primary_model_path}...")
    try:
        primary_model = YOLO(resolved_primary_model_path)
        auxiliary_ball_model = YOLO(auxiliary_ball_model_path) if auxiliary_ball_model_path is not None else None
    except Exception as e:
        print(f"Error loading model '{resolved_primary_model_path}': {e}")
        return empty_result() if return_rows or not output_parquet else []
    try:
        observed_precision = str(next(primary_model.model.parameters()).dtype).removeprefix("torch.")
    except (AttributeError, StopIteration, TypeError):
        observed_precision = None
    complete_phase("modelLoadSeconds", model_load_started_at)
    emit_worker_heartbeat("modelLoad", "completed")
    
    video_open_started_at = time.monotonic()
    from backend.app.workbench.media import OpenCvFrameSource, first_bgr_frame, pixels_from_decoded_frame, SamplingAudit, should_export_on_source_grid, export_timestamp_seconds

    decode_source = frame_source or OpenCvFrameSource(cv2_module=cv2)
    identity = decode_source.probe(Path(video_path))
    first_decoded = first_bgr_frame(Path(video_path), decode_source, cv2_module=cv2)
    first_frame = pixels_from_decoded_frame(first_decoded) if first_decoded is not None else None
    if first_frame is None:
        print(f"Error opening video {video_path}")
        return empty_result() if return_rows or not output_parquet else []
    emit_worker_heartbeat("videoOpenAndHomography", "started")

    fps = float(identity.nominalFps or 0.0) or 1.0
    frame_interval = int(fps / TARGET_FPS) if fps > TARGET_FPS else 1
    sample_interval = frame_interval
    sampling_audit = SamplingAudit(
        source_sha256=str(identity.sourceSha256 or ""),
        declared_target_fps=float(TARGET_FPS),
        nominal_fps=float(fps) if fps else None,
        frame_interval=int(frame_interval),
        selected_backend=f"{decode_source.name}+ultralytics_track",
        temporal_policy="source_global_grid",
    )
        
    H, pitch_points = resolve_homography(first_frame, homography_points=homography_points, use_auto=auto_homography)
    calibrations = [(0, H, pitch_points)]
    complete_phase("videoOpenAndHomographySeconds", video_open_started_at)
    emit_worker_heartbeat(
        "videoOpenAndHomography",
        "completed",
        tracking_frames_seen=0,
    )
    
    # List of flat dictionaries for DataFrame conversion
    match_data_rows = []
    track_color_samples = {}
    frame_player_windows = {}
    frame_count = 0
    last_homography_recalc = 0
    last_export_presentation_time = None
    grid_origin_presentation_time = None
    grid_origin_pts = None
    last_export_pts = None
    exported_presentation_times = []
    observed_device = None
    recalc_interval = HOMOGRAPHY_RECALC_FRAMES
    
    print("\nStarting BoT-SORT/YOLO Video Processing...")
    tracking_pass_started_at = time.monotonic()
    emit_worker_heartbeat("trackingPass", "started", tracking_frames_seen=0)
    tracking_progress_started_at = time.monotonic()
    last_tracking_progress_frames_seen = 0
    
    # We will use generator to track frame by frame
    def _frame_source_track_results():
            from backend.app.workbench.media import iter_bgr_frames, pixels_from_decoded_frame
            from backend.app.workbench.perception import DetectorAdapter, TrackerAdapter, unwrap_ultralytics_track_result

            detector = DetectorAdapter()
            tracker = TrackerAdapter()
            for decoded in iter_bgr_frames(Path(video_path), decode_source, cv2_module=cv2):
                frame = pixels_from_decoded_frame(decoded)
                tracked = primary_model.track(
                    source=frame,
                    persist=True,
                    tracker="botsort.yaml",
                    imgsz=TRACKING_IMGSZ,
                    conf=TRACKING_CONF,
                    classes=detector_tracking_class_ids(resolved_primary_detector_profile),
                    verbose=False,
                )
                result = unwrap_ultralytics_track_result(tracked)
                if getattr(result, "orig_img", None) is None:
                    try:
                        result.orig_img = frame
                    except Exception:
                        pass
                detector.from_ultralytics(result, frame_id=decoded.source_frame_index)
                tracker.from_ultralytics(result)
                try:
                    result.presentation_time_seconds = decoded.presentation_time_seconds
                    result.source_frame_index = decoded.source_frame_index
                    result.pts = decoded.pts
                    result.time_base = decoded.time_base
                    result.presentation_clock = getattr(decoded, "presentation_clock", "decoder_pts")
                except Exception:
                    pass
                yield result

    results = _frame_source_track_results()
    
    for r in results:
        sampling_audit.record_decoded_frame()
        sampling_audit.record_primary_inference()
        sampling_audit.record_tracker_update()
        frame_image = getattr(r, "orig_img", None)
        tensor = getattr(getattr(r, "boxes", None), "data", None)
        if observed_device is None and getattr(tensor, "device", None) is not None:
            observed_device = str(tensor.device)
        
        # Periodic homography recalculation to handle camera sway
        if frame_count - last_homography_recalc >= recalc_interval:
            if frame_image is not None and auto_homography and AUTO_HOMOGRAPHY_AVAILABLE:
                corners = detect_pitch_corners(frame_image)
                if corners:
                    try:
                        new_H = compute_pitch_homography(corners)
                        H = new_H
                        pitch_points = corners
                        calibrations.append((frame_count, H, pitch_points))
                        last_homography_recalc = frame_count
                    except ValueError:
                        pass  # Keep current H
        
        presentation = None if getattr(r, "presentation_clock", "decoder_pts") == "missing" else getattr(r, "presentation_time_seconds", None)
        if grid_origin_presentation_time is None and presentation is not None:
            grid_origin_presentation_time = presentation
        pts = getattr(r, "pts", None)
        time_base = getattr(r, "time_base", None)
        if grid_origin_pts is None and pts is not None:
            grid_origin_pts = pts
        if should_export_on_source_grid(
            presentation,
            frame_count=frame_count,
            frame_interval=frame_interval,
            last_export_presentation_time=last_export_presentation_time,
            grid_step_seconds=frame_interval / fps if fps else 0.0,
            grid_origin_presentation_time=grid_origin_presentation_time,
            pts=pts,
            time_base=time_base,
            last_export_pts=last_export_pts,
            grid_origin_pts=grid_origin_pts,
            target_fps=(fps / frame_interval) if fps and frame_interval else None,
        ):
            sampling_audit.record_export_sample()
            timestamp = export_timestamp_seconds(
                presentation_time_seconds=presentation,
                frame_count=frame_count,
                fps=fps,
            )
            last_export_presentation_time = presentation if presentation is not None else timestamp
            last_export_pts = pts
            exported_presentation_times.append(timestamp)
            
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # class 0 is usually person, 32 is sports ball (COCO dataset)
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    if box.id is not None:
                        track_id = int(box.id[0])
                    else:
                        track_id = -1
                        
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = projection_anchor_for_detection(
                        cls,
                        x1,
                        y1,
                        x2,
                        y2,
                        detector_profile=resolved_primary_detector_profile,
                    )
                    if not should_keep_detection_for_pitch(
                        cls,
                        cx,
                        cy,
                        pitch_points,
                        detector_profile=resolved_primary_detector_profile,
                    ):
                        continue
                    
                    # Project to pitch coordinates (0-100) using homography
                    px, py = point_to_pitch(H, cx, cy)
                    px = round(max(0, min(PITCH_WIDTH, px)), 2)
                    py = round(max(0, min(PITCH_HEIGHT, py)), 2)
                    
                    entity_type = "unknown"
                    if detector_class_is_ball(cls, resolved_primary_detector_profile):
                        entity_type = "ball"
                    elif detector_class_is_player(cls, resolved_primary_detector_profile):
                        entity_type = "player"
                        frame_player_windows[frame_count] = update_player_window(
                            frame_player_windows.get(frame_count),
                            x1,
                            y1,
                            x2,
                            y2,
                        )
                        if track_id >= 0 and frame_image is not None:
                            color_sample = extract_torso_color(frame_image, x1, y1, x2, y2)
                            if color_sample is not None:
                                track_color_samples.setdefault(track_id, []).append(color_sample)

                    match_data_rows.append(
                        build_tracking_row(
                            frame_id=frame_count,
                            timestamp=timestamp,
                            entity_type=entity_type,
                            track_id=track_id,
                            pitch_x=px,
                            pitch_y=py,
                            detection_conf=conf,
                            source_box=(x1, y1, x2, y2),
                            pts=pts,
                            time_base=time_base,
                        )
                    )
        processed_source_frames = frame_count + 1
        if (
            processed_source_frames - last_tracking_progress_frames_seen >= 250
            or time.monotonic() - tracking_progress_started_at >= 30.0
        ):
            emit_worker_heartbeat(
                "trackingPass",
                "started",
                tracking_frames_seen=processed_source_frames,
            )
            last_tracking_progress_frames_seen = processed_source_frames
            tracking_progress_started_at = time.monotonic()
            
        frame_count += 1
        
    ball_pipeline_trace["samplingReceipt"] = sampling_audit.receipt().model_dump(mode="json")
    if not match_data_rows:
        print("No tracking data found.")
        return empty_result() if return_rows or not output_parquet else []
    complete_phase("trackingPassSeconds", tracking_pass_started_at)
    emit_worker_heartbeat("trackingPass", "completed", tracking_frames_seen=frame_count)

    primary_ball_frames = len({int(row["Frame_ID"]) for row in match_data_rows if row["Entity_Type"] == "ball"})
    recovery_debug["primaryBallFrames"] = primary_ball_frames
    ball_pipeline_trace["stages"].append(ball_trace_from_rows("processVideoPrimary", match_data_rows))

    tracking_observed_ball_rows = [row for row in match_data_rows if row["Entity_Type"] == "ball"]
    player_rows = [row for row in match_data_rows if row["Entity_Type"] != "ball"]
    probe_observed_ball_rows = []
    filtered_probe_observed_ball_rows = []
    probe_observed_pass_started_at = time.monotonic()
    emit_worker_heartbeat("probeObservedPass", "started")
    probe_source_model = auxiliary_ball_model or primary_model
    probe_model = _CountingPredictor(
        probe_source_model,
        sampling_audit.record_recovery_inference,
    )
    probe_detector_profile = resolved_auxiliary_ball_model_profile or resolved_primary_detector_profile
    probe_recovery_settings = detector_probe_recovery_settings(probe_detector_profile)
    probe_crop_windows = None
    recovery_profiles = build_ball_recovery_quality_matrix_profiles()
    if probe_detector_profile == DETECTOR_PROFILE_BALL_PROBE_ONLY_V7_3:
        probe_crop_windows, _ = _build_player_proposal_crop_windows_by_frame(
            first_frame.shape,
            frame_interval=frame_interval,
            frame_count=frame_count,
            player_rows=player_rows,
            observed_source_anchors=collect_observed_source_anchors(tracking_observed_ball_rows),
        )
        # The crop-trained model reuses bounded proposals; full-frame/large-window profiles
        # are training-incompatible and repeat the same crop predictions.
        recovery_profiles = [profile for profile in recovery_profiles if profile.get("cropMode") == "proposal_windows"]
        for profile in recovery_profiles:
            profile["settings"] = {"imgsz": 256, "conf": 0.1}
            profile["directSeedRetryScales"] = [256]
    ball_pipeline_trace["probeRecoveryConf"] = probe_recovery_settings["recoveryConf"]
    ball_pipeline_trace["probeRecoveryImgsz"] = probe_recovery_settings["recoveryImgsz"]
    if hasattr(probe_source_model, "predict"):
        probe_observed_ball_rows = recover_ball_rows(
            video_path,
            model=probe_model,
            detector_profile=probe_detector_profile,
            calibrations=calibrations,
            H=H,
            pitch_points=pitch_points,
            fps=fps,
            frame_interval=frame_interval,
            player_windows=None,
            crop_windows_by_frame=probe_crop_windows,
            recovery_imgsz=probe_recovery_settings["recoveryImgsz"],
            recovery_conf=probe_recovery_settings["recoveryConf"],
            crop_edge_margin=0,
            max_crop_center_y_ratio=0.0,
            max_crop_width_ratio=0.0,
            frame_source=decode_source,
        )
        from backend.app.workbench.perception import DetectorAdapter as _RecoveryDetectorAdapter

        _RecoveryDetectorAdapter().ingest_recovery_rows(probe_observed_ball_rows)
    probe_observed_ball_rows = suppress_repeated_false_ball_clusters(
        probe_observed_ball_rows,
        player_windows=frame_player_windows,
    )
    filtered_probe_observed_ball_rows = _filter_probe_observed_ball_rows(
        probe_observed_ball_rows,
        player_rows=player_rows,
        sample_interval=frame_interval,
    )["filteredRows"]
    observed_ball_rows = _select_best_observed_ball_rows(
        tracking_observed_ball_rows,
        filtered_probe_observed_ball_rows,
        player_rows=player_rows,
    )
    observed_source_anchors = collect_observed_source_anchors(observed_ball_rows)
    complete_phase("probeObservedPassSeconds", probe_observed_pass_started_at)
    emit_worker_heartbeat(
        "probeObservedPass",
        "completed",
        observed_ball_frames=len(observed_ball_rows),
    )

    needs_primary_recovery = ball_rows_need_recovery(match_data_rows)
    needs_supplemental_recovery = (
        not needs_primary_recovery
        and ball_rows_need_supplemental_recovery(match_data_rows, frame_interval)
    )
    selected_ball_rows = []
    selected_profile = None
    recovery_profile_matrix = None
    recovery_selection_started_at = time.monotonic()
    emit_worker_heartbeat("recoverySelection", "started")
    if needs_primary_recovery or needs_supplemental_recovery:
        recovery_debug["recoveryAttempted"] = True
        recovery_results = run_ball_recovery_experiment(
            video_path,
            model=probe_model,
            detector_profile=probe_detector_profile,
            calibrations=calibrations,
            H=H,
            pitch_points=pitch_points,
            fps=fps,
            frame_interval=frame_interval,
            imgsz=TRACKING_IMGSZ,
            conf=TRACKING_CONF,
            observed_source_anchors=observed_source_anchors,
            player_windows=frame_player_windows,
            player_rows=player_rows,
            profiles=recovery_profiles,
            progress_callback=emit_recovery_selection_progress,
            edge_share_repair_profile=edge_share_repair_profile,
            baseline_guided_rescue_reference=baseline_guided_rescue_reference,
            proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
            reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
            frame_source=decode_source,
        )
        selected_profile = select_best_ball_recovery_profile(recovery_results)
        recovery_profile_matrix = _build_recovery_profile_matrix(
            recovery_results,
            selected_profile_name=selected_profile.get("name") if selected_profile is not None else None,
        )
        recovery_debug["profileTimings"] = [
            {
                "name": str(result.get("name", "")),
                "cropMode": str(result.get("cropMode", "")),
                "elapsedSeconds": round(float(result.get("elapsedSeconds", 0.0)), 3),
                "candidateRows": len(result.get("candidateRows") or []),
                "selectedFrames": int((result.get("selectedSummary") or {}).get("frames", 0)),
                "directSeedRetryPolicy": str(
                    result.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)
                ),
                "directSeedRetryScales": [
                    int(scale)
                    for scale in (result.get("directSeedRetryScales") or DIRECT_SEED_RETRY_SCALES)
                ],
            }
            for result in recovery_results
        ]
        if selected_profile is None:
            recovery_debug["recoveryDecision"] = "no_viable_profile"
        else:
            candidate_summary = dict(selected_profile.get("candidateSummary") or {})
            selected_summary = dict(selected_profile.get("selectedSummary") or {})
            selected_ball_rows = list(selected_profile.get("selectedRows") or selected_profile.get("rows") or [])
            recovery_debug.update(
                {
                    "recoveryProfileName": selected_profile.get("name"),
                    "recoveredCandidateRows": int(candidate_summary.get("candidateRows", 0)),
                    "recoveredUniqueFrames": int(candidate_summary.get("uniqueFrames", 0)),
                    "recoveredSelectedFrames": int(selected_summary.get("frames", len(selected_ball_rows))),
                    "candidateSupportedFrames": int(candidate_summary.get("supportedFrameCount", 0)),
                    "candidateAnchoredFrames": int(candidate_summary.get("anchoredFrameCount", 0)),
                    "candidateBridgeFrames": int(candidate_summary.get("bridgeFrameCount", 0)),
                    "candidateUnsupportedEdgeFrameShare": float(
                        candidate_summary.get("unsupportedEdgeFrameShare", 0.0)
                    ),
                    "candidateAnchoredPathLength": float(candidate_summary.get("anchoredPathLength", 0.0)),
                    "recoveredSupportedFrames": int(selected_summary.get("supportedFrameCount", 0)),
                    "recoveredAnchoredFrames": int(selected_summary.get("anchoredFrameCount", 0)),
                    "recoveredBridgeFrames": int(selected_summary.get("bridgeFrameCount", 0)),
                    "recoveredUnsupportedEdgeFrameShare": float(
                        selected_summary.get("unsupportedEdgeFrameShare", 0.0)
                    ),
                    "recoveredAnchoredPathLength": float(selected_summary.get("anchoredPathLength", 0.0)),
                    "corridorCandidateFrames": int(candidate_summary.get("corridorCandidateFrames", 0)),
                    "corridorFramesWithTwoAnchors": int(candidate_summary.get("corridorFramesWithTwoAnchors", 0)),
                    "corridorFramesWithSingleAnchor": int(candidate_summary.get("corridorFramesWithSingleAnchor", 0)),
                    "corridorMeanWidth": float(candidate_summary.get("corridorMeanWidth", 0.0)),
                    "proposalCandidateFrames": int(candidate_summary.get("proposalCandidateFrames", 0)),
                    "proposalWindowCount": int(candidate_summary.get("proposalWindowCount", 0)),
                    "proposalFramesWithAnchorSeed": int(candidate_summary.get("proposalFramesWithAnchorSeed", 0)),
                    "proposalFramesWithoutAnchorSeed": int(candidate_summary.get("proposalFramesWithoutAnchorSeed", 0)),
                    "proposalExactSeedFrames": int(candidate_summary.get("proposalExactSeedFrames", 0)),
                    "proposalInterpolatedSeedFrames": int(candidate_summary.get("proposalInterpolatedSeedFrames", 0)),
                    "proposalSingleSeedFrames": int(candidate_summary.get("proposalSingleSeedFrames", 0)),
                    "proposalUnseededFrames": int(candidate_summary.get("proposalUnseededFrames", 0)),
                    "proposalContinuityBridgeGapFrames": int(
                        candidate_summary.get("proposalContinuityBridgeGapFrames", 0)
                    ),
                    "proposalContinuityBridgeCandidateFrames": int(
                        candidate_summary.get("proposalContinuityBridgeCandidateFrames", 0)
                    ),
                    "proposalContinuityBridgeAcceptedFrames": int(
                        candidate_summary.get("proposalContinuityBridgeAcceptedFrames", 0)
                    ),
                    "proposalAcceptanceSupportGatingAcceptedFrames": int(
                        candidate_summary.get("proposalAcceptanceSupportGatingAcceptedFrames", 0)
                    ),
                    "proposalAcceptanceSupportGatingRejectedCounts": dict(
                        candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts")
                        if isinstance(
                            candidate_summary.get("proposalAcceptanceSupportGatingRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSelectionAdmissionFixAcceptedFrames": int(
                        candidate_summary.get("proposalSelectionAdmissionFixAcceptedFrames", 0)
                    ),
                    "proposalSelectionAdmissionFixRejectedCounts": dict(
                        candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts")
                        if isinstance(
                            candidate_summary.get("proposalSelectionAdmissionFixRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSelectionAdmissionFixTruthSeedFrames": int(
                        candidate_summary.get("proposalSelectionAdmissionFixTruthSeedFrames", 0)
                    ),
                    "proposalSelectionAdmissionFixApproachFamily": (
                        str(candidate_summary.get("proposalSelectionAdmissionFixApproachFamily"))
                        if candidate_summary.get("proposalSelectionAdmissionFixApproachFamily")
                        else None
                    ),
                    "proposalSupportViabilityAdmissionFixAcceptedFrames": int(
                        candidate_summary.get("proposalSupportViabilityAdmissionFixAcceptedFrames", 0)
                    ),
                    "proposalSupportViabilityAdmissionFixRejectedCounts": dict(
                        candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts")
                        if isinstance(
                            candidate_summary.get("proposalSupportViabilityAdmissionFixRejectedCounts"),
                            dict,
                        )
                        else {}
                    ),
                    "proposalSupportViabilityAdmissionFixTruthSeedFrames": int(
                        candidate_summary.get("proposalSupportViabilityAdmissionFixTruthSeedFrames", 0)
                    ),
                    "proposalSupportViabilityAdmissionFixApproachFamily": (
                        str(candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily"))
                        if candidate_summary.get("proposalSupportViabilityAdmissionFixApproachFamily")
                        else None
                    ),
                    "proposalContinuityBridgeRejectedEdgeFrames": int(
                        candidate_summary.get("proposalContinuityBridgeRejectedEdgeFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedContinuityFrames": int(
                        candidate_summary.get("proposalContinuityBridgeRejectedContinuityFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedSupportFrames": int(
                        candidate_summary.get("proposalContinuityBridgeRejectedSupportFrames", 0)
                    ),
                    "proposalContinuityBridgeRejectedRepeatedAnchorFrames": int(
                        candidate_summary.get(
                            "proposalContinuityBridgeRejectedRepeatedAnchorFrames", 0
                        )
                    ),
                    "proposalDirectSeedWindowFrames": int(
                        candidate_summary.get("proposalDirectSeedWindowFrames", 0)
                    ),
                    "proposalDirectSeedTightWindowFrames": int(
                        candidate_summary.get("proposalDirectSeedTightWindowFrames", 0)
                    ),
                "proposalDirectSeedContextWindowFrames": int(
                    candidate_summary.get("proposalDirectSeedContextWindowFrames", 0)
                ),
                "proposalDirectSeedContextEligibleFrames": int(
                    candidate_summary.get("proposalDirectSeedContextEligibleFrames", 0)
                ),
                "proposalDirectSeedContextDuplicateFrames": int(
                    candidate_summary.get("proposalDirectSeedContextDuplicateFrames", 0)
                ),
                "proposalDirectSeedContextMeanSeedToBoxDistance": round(
                    float(candidate_summary.get("proposalDirectSeedContextMeanSeedToBoxDistance", 0.0)),
                    2,
                ),
                "proposalDirectSeedContextExpandedFrames": int(
                    candidate_summary.get("proposalDirectSeedContextExpandedFrames", 0)
                ),
                    "proposalDirectSeedContextMeanExpansionPx": round(
                        float(candidate_summary.get("proposalDirectSeedContextMeanExpansionPx", 0.0)),
                        2,
                    ),
                    "proposalDirectSeedHiResRetryFrames": int(
                        candidate_summary.get("proposalDirectSeedHiResRetryFrames", 0)
                    ),
                    "proposalDirectSeedHiResRetryDetectedFrames": int(
                        candidate_summary.get("proposalDirectSeedHiResRetryDetectedFrames", 0)
                    ),
                    "proposalDirectSeedZeroDetectFrames": int(
                        candidate_summary.get("proposalDirectSeedZeroDetectFrames", 0)
                    ),
                    "proposalDirectSeedScale1600AttemptFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1600AttemptFrames", 0)
                    ),
                    "proposalDirectSeedScale960AttemptFrames": int(
                        candidate_summary.get("proposalDirectSeedScale960AttemptFrames", 0)
                    ),
                    "proposalDirectSeedScale1920AttemptFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1920AttemptFrames", 0)
                    ),
                    "proposalDirectSeedScale1600RawDetectionFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1600RawDetectionFrames", 0)
                    ),
                    "proposalDirectSeedScale960RawDetectionFrames": int(
                        candidate_summary.get("proposalDirectSeedScale960RawDetectionFrames", 0)
                    ),
                    "proposalDirectSeedScale1920RawDetectionFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1920RawDetectionFrames", 0)
                    ),
                    "proposalDirectSeedScale1600CandidateFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1600CandidateFrames", 0)
                    ),
                    "proposalDirectSeedScale960CandidateFrames": int(
                        candidate_summary.get("proposalDirectSeedScale960CandidateFrames", 0)
                    ),
                    "proposalDirectSeedScale1920CandidateFrames": int(
                        candidate_summary.get("proposalDirectSeedScale1920CandidateFrames", 0)
                    ),
                    "proposalDirectSeedScale1600ElapsedSeconds": round(
                        float(candidate_summary.get("proposalDirectSeedScale1600ElapsedSeconds", 0.0)),
                        3,
                    ),
                    "proposalDirectSeedScale960ElapsedSeconds": round(
                        float(candidate_summary.get("proposalDirectSeedScale960ElapsedSeconds", 0.0)),
                        3,
                    ),
                    "proposalDirectSeedScale1920ElapsedSeconds": round(
                        float(candidate_summary.get("proposalDirectSeedScale1920ElapsedSeconds", 0.0)),
                        3,
                    ),
                    "proposalDirectSeedFallbackElapsedSeconds": round(
                        float(candidate_summary.get("proposalDirectSeedFallbackElapsedSeconds", 0.0)),
                        3,
                    ),
                    "proposalDirectSeedMultiScaleRetryFrames": int(
                        candidate_summary.get("proposalDirectSeedMultiScaleRetryFrames", 0)
                    ),
                    "proposalDirectSeedMultiScaleDetectedFrames": int(
                        candidate_summary.get("proposalDirectSeedMultiScaleDetectedFrames", 0)
                    ),
                    "proposalDirectSeedRawHitFilteredOutFrames": int(
                        candidate_summary.get("proposalDirectSeedRawHitFilteredOutFrames", 0)
                    ),
                    "proposalDirectSeedCropEdgeRejectedFrames": int(
                        candidate_summary.get("proposalDirectSeedCropEdgeRejectedFrames", 0)
                    ),
                    "proposalDirectSeedCropCenterYRejectedFrames": int(
                        candidate_summary.get("proposalDirectSeedCropCenterYRejectedFrames", 0)
                    ),
                    "proposalDirectSeedPitchPolygonRejectedFrames": int(
                        candidate_summary.get("proposalDirectSeedPitchPolygonRejectedFrames", 0)
                    ),
                    "proposalDirectSeedMeanCropArea": round(
                        float(candidate_summary.get("proposalDirectSeedMeanCropArea", 0.0)),
                        2,
                    ),
                    "proposalDirectSeedTightMeanCropArea": round(
                        float(candidate_summary.get("proposalDirectSeedTightMeanCropArea", 0.0)),
                        2,
                    ),
                    "proposalDirectSeedContextMeanCropArea": round(
                        float(candidate_summary.get("proposalDirectSeedContextMeanCropArea", 0.0)),
                        2,
                    ),
                    "proposalPlayerRankedMeanCropArea": round(
                        float(candidate_summary.get("proposalPlayerRankedMeanCropArea", 0.0)),
                        2,
                    ),
                    "proposalDirectSeedMeanDetectedBallBoxArea": round(
                        float(candidate_summary.get("proposalDirectSeedMeanDetectedBallBoxArea", 0.0)),
                        2,
                    ),
                    "proposalPlayerRankedMeanDetectedBallBoxArea": round(
                        float(candidate_summary.get("proposalPlayerRankedMeanDetectedBallBoxArea", 0.0)),
                        2,
                    ),
                    "proposalPlayerRankedWindowFrames": int(
                        candidate_summary.get("proposalPlayerRankedWindowFrames", 0)
                    ),
                    "proposalMeanWindowWidth": float(candidate_summary.get("proposalMeanWindowWidth", 0.0)),
                    "proposalRawDetectedFrames": int(candidate_summary.get("proposalRawDetectedFrames", 0)),
                    "proposalAfterSeedCollapseFrames": int(
                        candidate_summary.get("proposalAfterSeedCollapseFrames", 0)
                    ),
                    "proposalAfterPlayerWindowFrames": int(
                        candidate_summary.get("proposalAfterPlayerWindowFrames", 0)
                    ),
                    "proposalAfterFalseBallSuppressionFrames": int(
                        candidate_summary.get("proposalAfterFalseBallSuppressionFrames", 0)
                    ),
                    "proposalCollapsedFrames": int(candidate_summary.get("proposalCollapsedFrames", 0)),
                    "proposalCollapsedSegmentCount": int(
                        candidate_summary.get("proposalCollapsedSegmentCount", 0)
                    ),
                    "proposalDirectSeedDetectedFrames": int(
                        candidate_summary.get("proposalDirectSeedDetectedFrames", 0)
                    ),
                    "proposalDirectSeedTightDetectedFrames": int(
                        candidate_summary.get("proposalDirectSeedTightDetectedFrames", 0)
                    ),
                    "proposalDirectSeedContextDetectedFrames": int(
                        candidate_summary.get("proposalDirectSeedContextDetectedFrames", 0)
                    ),
                    "proposalPlayerRankedDetectedFrames": int(
                        candidate_summary.get("proposalPlayerRankedDetectedFrames", 0)
                    ),
                    "proposalExactSeedDetectedFrames": int(
                        candidate_summary.get("proposalExactSeedDetectedFrames", 0)
                    ),
                    "proposalInterpolatedSeedDetectedFrames": int(
                        candidate_summary.get("proposalInterpolatedSeedDetectedFrames", 0)
                    ),
                    "proposalSingleSeedDetectedFrames": int(
                        candidate_summary.get("proposalSingleSeedDetectedFrames", 0)
                    ),
                    "directSeedRetryPolicy": str(
                        candidate_summary.get("directSeedRetryPolicy", DIRECT_SEED_RETRY_POLICY)
                    ),
                    "directSeedRetryScales": [
                        int(scale)
                        for scale in (
                            candidate_summary.get("directSeedRetryScales")
                            or DIRECT_SEED_RETRY_SCALES
                        )
                    ],
                    "collapsedCandidateFrames": int(candidate_summary.get("collapsedCandidateFrames", 0)),
                    "collapsedSegmentCount": int(candidate_summary.get("collapsedSegmentCount", 0)),
                    "collapsedLongestSegmentFrames": int(
                        candidate_summary.get("collapsedLongestSegmentFrames", 0)
                    ),
                    "continuityPreferredFrames": int(candidate_summary.get("continuityPreferredFrames", 0)),
                    "continuityRejectedFrames": int(candidate_summary.get("continuityRejectedFrames", 0)),
                    "midfieldCollapsedFrames": int(candidate_summary.get("midfieldCollapsedFrames", 0)),
                    "candidateEdgeShare": float(candidate_summary.get("edgeCandidateShare", 0.0)),
                    "nearPlayerWindowShare": float(candidate_summary.get("nearPlayerWindowShare", 0.0)),
                    "segmentCount": int(candidate_summary.get("segmentCount", 0)),
                    "longestSegmentFrames": int(candidate_summary.get("longestSegmentFrames", 0)),
                    "selectedEdgeFrameShare": float(selected_summary.get("edgeFrameShare", 0.0)),
                    "selectedPathLength": float(selected_summary.get("pathLength", 0.0)),
                    "selectedViable": bool(selected_profile.get("viable")),
                }
            )
            if needs_primary_recovery:
                print(
                    "Recovered fallback ball rows after primary pass lacked meaningful ball motion "
                    f"({len(selected_ball_rows)} selected from {recovery_debug['recoveredCandidateRows']} candidates) "
                    f"using profile {recovery_debug['recoveryProfileName']}."
                )
                recovery_debug["recoveryApplied"] = True
                recovery_debug["recoveryDecision"] = "applied_profile_primary"
            else:
                if selected_ball_rows:
                    print(
                        "Supplemented sparse primary ball frames with recovered fallback rows "
                        f"({len(selected_ball_rows)} selected) "
                        f"using profile {recovery_debug['recoveryProfileName']}."
                    )
                    recovery_debug["recoveryApplied"] = True
                    recovery_debug["recoveryDecision"] = "applied_profile_supplemental"
                else:
                    recovery_debug["recoveryDecision"] = "selected_profile_no_additions"
    complete_phase("recoverySelectionSeconds", recovery_selection_started_at)
    emit_worker_heartbeat(
        "recoverySelection",
        "completed",
        observed_ball_frames=len(observed_ball_rows),
    )
    truth_layer_finalize_started_at = time.monotonic()
    emit_worker_heartbeat("truthLayerFinalize", "started")
    source_conditioned_acquisition_diagnostics = _build_source_conditioned_acquisition_diagnostics(
        profile_name=edge_share_repair_profile,
        source_clip_id=source_clip_id,
        candidate_summary=dict(selected_profile.get("candidateSummary") or {}) if isinstance(selected_profile, dict) else {},
    )
    ball_truth_layers = _build_ball_truth_layers(
        tracking_observed_ball_rows,
        selected_ball_rows,
        probe_observed_rows=probe_observed_ball_rows,
        sample_interval=frame_interval,
        player_rows=player_rows,
        source_clip_id=source_clip_id,
        edge_share_repair_profile=edge_share_repair_profile,
        acquisition_diagnostics=source_conditioned_acquisition_diagnostics,
    )
    match_state_evidence = _build_match_state_evidence(
        ball_truth_layers,
        player_rows=player_rows,
    )
    inferred_frame_count = int(ball_truth_layers["acceptedSourceBreakdown"]["inferred"])
    if recovery_debug["recoveryAttempted"]:
        if inferred_frame_count > 0:
            recovery_debug["recoveryApplied"] = True
            if recovery_debug["recoveryDecision"] != "no_viable_profile":
                recovery_debug["recoveryDecision"] = (
                    "applied_profile_primary" if needs_primary_recovery else "applied_profile_supplemental"
                )
        elif recovery_debug["recoveryDecision"] in {"applied_profile_primary", "applied_profile_supplemental"}:
            recovery_debug["recoveryApplied"] = False
            recovery_debug["recoveryDecision"] = "selected_profile_no_additions"
    accepted_ball_rows = ball_truth_layers["acceptedBall"]["rows"]
    complete_phase("truthLayerFinalizeSeconds", truth_layer_finalize_started_at)
    emit_worker_heartbeat(
        "truthLayerFinalize",
        "completed",
        observed_ball_frames=int(ball_truth_layers["observedBall"]["summary"]["frameCount"]),
        accepted_ball_frames=int(ball_truth_layers["acceptedBall"]["summary"]["frameCount"]),
    )
    match_data_rows = player_rows + accepted_ball_rows
    match_data_rows.sort(
        key=lambda row: (
            int(row["Frame_ID"]),
            0 if row["Entity_Type"] == "ball" else 1,
            int(row["Track_ID"]),
        )
    )
    ball_pipeline_trace["stages"].append(ball_trace_from_rows("processVideoRecovery", selected_ball_rows))
    ball_pipeline_trace["stages"].append(ball_trace_from_rows("processVideoReturnedRows", match_data_rows))

    result_serialize_started_at = time.monotonic()
    emit_worker_heartbeat(
        "resultSerialize",
        "started",
        observed_ball_frames=int(ball_truth_layers["observedBall"]["summary"]["frameCount"]),
        accepted_ball_frames=int(ball_truth_layers["acceptedBall"]["summary"]["frameCount"]),
    )
    if output_parquet:
        df = pd.DataFrame(match_data_rows)
        print(f"Processing complete. Saving DataFrame ({len(df)} rows) to {output_parquet}")
        df.to_parquet(output_parquet, engine='fastparquet')

    complete_phase("resultSerializeSeconds", result_serialize_started_at)
    complete_phase("totalProcessVideoSeconds", total_process_video_started_at)
    emit_worker_heartbeat(
        "resultSerialize",
        "completed",
        observed_ball_frames=int(ball_truth_layers["observedBall"]["summary"]["frameCount"]),
        accepted_ball_frames=int(ball_truth_layers["acceptedBall"]["summary"]["frameCount"]),
        worker_returned_result=True,
    )

    ball_pipeline_trace["samplingReceipt"] = sampling_audit.receipt().model_dump(mode="json")
    rates = sampling_audit.four_rates()

    return {
        "rows": match_data_rows,
        "trackColors": {str(track_id): samples for track_id, samples in track_color_samples.items()},
        "recoveryDebug": recovery_debug,
        "recoveryProfileMatrix": recovery_profile_matrix,
        "ballPipelineTrace": ball_pipeline_trace,
        "ballTruthLayers": ball_truth_layers,
        "matchStateEvidence": match_state_evidence,
        "samplingReceipt": ball_pipeline_trace["samplingReceipt"],
        "fourRates": {
            "decodeCount": rates.decodeCount,
            "detectorPrimaryCount": rates.detectorPrimaryCount,
            "detectorRecoveryCount": rates.detectorRecoveryCount,
            "trackerUpdateCount": rates.trackerUpdateCount,
            "exportCount": rates.exportCount,
            "exportFpsEqualsInferenceFps": False,
            "decodeFpsEqualsExportFps": False,
            "notes": list(rates.notes),
        },
        "decodeAnchors": {
            "beginning": exported_presentation_times[0] if exported_presentation_times else None,
            "middle": (
                exported_presentation_times[len(exported_presentation_times) // 2]
                if len(exported_presentation_times) >= 3
                else None
            ),
            "end": exported_presentation_times[-1] if len(exported_presentation_times) >= 2 else None,
            "source": "production_decode",
            "discontinuities": [],
        },
        "hardware": {"declaredBackend": "auto", "observedDevice": observed_device},
        "precision": observed_precision,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guerilla Analytics - Video Processing (V2)")
    parser.add_argument('--video', type=str, required=True, help="Path to input match.mp4")
    parser.add_argument('--output', type=str, default='meci_data.parquet', help="Output Parquet file path")
    parser.add_argument('--homography-points-json', type=str, default=None, help="Optional JSON list of 4 homography points")
    parser.add_argument('--no-auto-homography', action='store_true', help='Disable auto pitch detection, require manual calibration')
    
    args = parser.parse_args()
    homography_points = None
    if args.homography_points_json:
        import json
        homography_points = json.loads(args.homography_points_json)
    process_video(args.video, args.output, homography_points=homography_points, auto_homography=not args.no_auto_homography)
