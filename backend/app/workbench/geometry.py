"""GA-05 versioned calibration and geometry checks."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Literal

from pydantic import Field, model_validator

from ..domain_types import FiniteFloat, Homography3x3
from ..schemas import BallData, FrameData, PlayerData
from .contracts import StrictModel

CameraModel = Literal["planar_homography", "distortion_corrected", "segmented"]
CameraSide = Literal["touchline_north", "touchline_south", "goal_east", "goal_west"]


class CalibrationUnavailable(Exception):
    pass


class Landmark(StrictModel):
    name: str
    imageX: FiniteFloat
    imageY: FiniteFloat
    pitchX: FiniteFloat
    pitchY: FiniteFloat
    independentHoldout: bool = False


class CalibrationProfile(StrictModel):
    calibrationId: str
    sourceStreamId: str = "video:0"
    sourceWidth: int | None = Field(default=None, gt=0)
    sourceHeight: int | None = Field(default=None, gt=0)
    schemaVersion: str = "calibration_v2"
    cameraModel: CameraModel
    cameraSide: CameraSide | None = None
    pitchLengthM: FiniteFloat | None = Field(default=None, gt=0)
    pitchWidthM: FiniteFloat | None = Field(default=None, gt=0)
    validRegion: Literal["full_pitch", "near", "middle", "far", "unknown"] = "unknown"
    homography: Homography3x3 | None = None
    distortionK: list[FiniteFloat] = Field(default_factory=list)
    landmarks: list[Landmark] = Field(default_factory=list)
    sourceIntervalStart: FiniteFloat = 0.0
    sourceIntervalEnd: FiniteFloat | None = None
    residualP95M: FiniteFloat | None = None
    regionErrorsM: dict[str, FiniteFloat] = Field(default_factory=dict)
    compatibleWithFourPointV1: bool = True

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.sourceIntervalEnd is not None and self.sourceIntervalStart > self.sourceIntervalEnd:
            raise ValueError("calibration interval start must not exceed end")
        return self


def from_legacy_four_points(
    points: list[dict[str, float]],
    *,
    calibration_id: str,
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
) -> CalibrationProfile:
    if len(points) != 4:
        raise ValueError("legacy calibration must keep exactly four points")
    landmarks = [
        Landmark(
            name=f"legacy_corner_{index}",
            imageX=point["x"],
            imageY=point["y"],
            pitchX=pitch[0],
            pitchY=pitch[1],
            independentHoldout=False,
        )
        for index, (point, pitch) in enumerate(
            zip(
                points,
                (
                    (0.0, 0.0),
                    (pitch_length_m, 0.0),
                    (pitch_length_m, pitch_width_m),
                    (0.0, pitch_width_m),
                ),
                strict=True,
            )
        )
    ]
    return CalibrationProfile(
        calibrationId=calibration_id,
        cameraModel="planar_homography",
        pitchLengthM=pitch_length_m,
        pitchWidthM=pitch_width_m,
        landmarks=landmarks,
        compatibleWithFourPointV1=True,
        validRegion="unknown",
        homography=homography_from_four_points(
            points,
            pitch_length_m=pitch_length_m,
            pitch_width_m=pitch_width_m,
        ),
    )


def homography_from_four_points(
    points: list[dict[str, float]],
    *,
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
) -> list[list[float]] | None:
    if validate_fit_points(points):
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    source = np.array([[float(point["x"]), float(point["y"])] for point in points], dtype=np.float32)
    destination = np.array(
        [
            [0.0, 0.0],
            [pitch_length_m, 0.0],
            [pitch_length_m, pitch_width_m],
            [0.0, pitch_width_m],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    result = [[float(value) for value in row] for row in matrix.tolist()]
    return None if validate_homography(result) else result


def evaluate_landmarks(profile: CalibrationProfile, *, max_p95_m: float) -> dict[str, Any]:
    transform_errors = validate_homography(profile.homography)
    if transform_errors:
        return {"accepted": False, "reasonCodes": transform_errors, "holdoutCount": 0, "farSideCount": 0}
    holdout = [mark for mark in profile.landmarks if mark.independentHoldout]
    holdout_errors = validate_holdouts(holdout, profile)
    if holdout_errors:
        return {
            "accepted": False,
            "reasonCodes": ["CALIBRATION_UNAVAILABLE", *holdout_errors],
            "holdoutCount": len(holdout),
            "farSideCount": 0,
        }
    try:
        pairs = [
            (mark, math.hypot(projected[0] - mark.pitchX, projected[1] - mark.pitchY))
            for mark in holdout
            for projected in [project_point(profile, mark.imageX, mark.imageY)]
        ]
    except CalibrationUnavailable as exc:
        return {
            "accepted": False,
            "reasonCodes": [str(exc)],
            "holdoutCount": len(holdout),
            "farSideCount": 0,
        }
    residuals = sorted(value for _, value in pairs)
    p95 = residuals[min(len(residuals) - 1, max(0, int(round(0.95 * (len(residuals) - 1)))))]
    far, heuristic = _far_side_residuals(pairs, profile)
    region_ok = (max(far) if far else p95) <= max_p95_m
    reason_codes = [] if p95 <= max_p95_m and region_ok else ["CALIBRATION_UNAVAILABLE"]
    if heuristic:
        reason_codes.append("FAR_SIDE_HEURISTIC")
    return {
        "accepted": p95 <= max_p95_m and region_ok,
        "p95M": p95,
        "holdoutCount": len(holdout),
        "farSideCount": len(far),
        "farSideMaxM": max(far) if far else None,
        "reasonCodes": reason_codes,
    }


def validate_homography(matrix: list[list[float]] | None) -> list[str]:
    if matrix is None:
        return ["NO_TRANSFORM"]
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        return ["INVALID_TRANSFORM_SHAPE"]
    if any(not math.isfinite(value) for row in matrix for value in row):
        return ["NONFINITE_TRANSFORM"]
    try:
        import numpy as np

        values = np.asarray(matrix, dtype=float)
        if abs(float(np.linalg.det(values))) <= 1e-9 or float(np.linalg.cond(values)) >= 1e8:
            return ["SINGULAR_TRANSFORM"]
        if not np.isfinite(np.linalg.inv(values)).all() or matrix[2][2] == 0:
            return ["SINGULAR_TRANSFORM"]
    except (ImportError, ValueError, TypeError, OverflowError):
        return ["INVALID_TRANSFORM"]
    return []


def validate_fit_points(
    points: list[dict[str, float]],
    *,
    width: float | None = None,
    height: float | None = None,
) -> list[str]:
    if len(points) != 4:
        return ["INVALID_FIT_POINT_COUNT"]
    pairs = [(float(point["x"]), float(point["y"])) for point in points]
    if any(not math.isfinite(value) for pair in pairs for value in pair):
        return ["NONFINITE_FIT_POINT"]
    if any(
        x < 0
        or y < 0
        or (width is not None and x > width)
        or (height is not None and y > height)
        for x, y in pairs
    ):
        return ["FIT_POINT_OUTSIDE_SOURCE"]
    if len(set(pairs)) != 4:
        return ["DUPLICATE_FIT_POINT"]
    area = abs(
        sum(
            pairs[index][0] * pairs[(index + 1) % 4][1]
            - pairs[(index + 1) % 4][0] * pairs[index][1]
            for index in range(4)
        )
    ) / 2
    return ["COLLINEAR_FIT_POINTS"] if area <= 1e-9 else []


def validate_holdouts(holdouts: list[Landmark], profile: CalibrationProfile) -> list[str]:
    if len(holdouts) < 4:
        return ["INSUFFICIENT_HOLDOUTS"]
    fit_coordinates = {
        (mark.imageX, mark.imageY)
        for mark in profile.landmarks
        if not mark.independentHoldout
    }
    if any((mark.imageX, mark.imageY) in fit_coordinates for mark in holdouts):
        return ["HOLDOUT_OVERLAPS_FIT_POINT"]
    length = profile.pitchLengthM or 105.0
    width = profile.pitchWidthM or 68.0
    if any(not (0 <= mark.pitchX <= length and 0 <= mark.pitchY <= width) for mark in holdouts):
        return ["HOLDOUT_OUTSIDE_PITCH"]
    x_halves = {mark.pitchX >= length / 2 for mark in holdouts}
    y_halves = {mark.pitchY >= width / 2 for mark in holdouts}
    return [] if len(x_halves) == len(y_halves) == 2 else ["INSUFFICIENT_HOLDOUT_COVERAGE"]


def _far_side_residuals(
    pairs: list[tuple[Landmark, float]], profile: CalibrationProfile
) -> tuple[list[float], bool]:
    length = profile.pitchLengthM or 105.0
    width = profile.pitchWidthM or 68.0
    if profile.cameraSide == "touchline_north":
        return [value for mark, value in pairs if mark.pitchY >= width / 2], False
    if profile.cameraSide == "touchline_south":
        return [value for mark, value in pairs if mark.pitchY <= width / 2], False
    if profile.cameraSide == "goal_west":
        return [value for mark, value in pairs if mark.pitchX >= length / 2], False
    if profile.cameraSide == "goal_east":
        return [value for mark, value in pairs if mark.pitchX <= length / 2], False
    fit_points = [mark for mark in profile.landmarks if not mark.independentHoldout]
    north = [mark.imageY for mark in fit_points if mark.pitchY <= width / 4]
    south = [mark.imageY for mark in fit_points if mark.pitchY >= width * 3 / 4]
    if north and south:
        camera_side = "touchline_north" if sum(north) / len(north) > sum(south) / len(south) else "touchline_south"
        if camera_side == "touchline_north":
            return [value for mark, value in pairs if mark.pitchY >= width / 2], False
        return [value for mark, value in pairs if mark.pitchY <= width / 2], False
    return [value for mark, value in pairs if mark.pitchY >= 45], True


def commit_calibration(profile: CalibrationProfile, *, max_p95_m: float = 3.0) -> dict[str, Any]:
    """Persist a live calibration only when holdout residuals exist. Never a certification."""

    evaluation = evaluate_landmarks(profile, max_p95_m=max_p95_m)
    return {
        "committed": bool(evaluation.get("accepted")),
        "certified": False,
        "evaluation": evaluation,
        "profile": profile.model_dump(mode="json") if evaluation.get("accepted") else None,
    }


def withhold_if_invalid(profile: CalibrationProfile, metric_name: str, *, max_p95_m: float = 3.0) -> dict[str, Any]:
    result = evaluate_landmarks(profile, max_p95_m=max_p95_m)
    if not result["accepted"]:
        return {
            "metric": metric_name,
            "availability": "withheld",
            "reasonCodes": result["reasonCodes"],
            "value": None,
        }
    return {"metric": metric_name, "availability": "available", "reasonCodes": [], "value": "computed"}


def review_incident_geometry(
    *,
    my_team: list[dict[str, float | int]],
    enemies: list[dict[str, float | int]],
    ball: dict[str, float] | None,
    attack_direction: Literal["left_to_right", "right_to_left"],
    calibration_accepted: bool = False,
    touch_timing_known: bool = False,
    pitch_length_m: float | None = None,
    uncertainty_m: float | None = None,
) -> dict[str, Any]:
    """Deterministic geometry for review. Never publishes a validated offside decision."""

    attacking_increasing_x = attack_direction == "left_to_right"
    opponent_xs = sorted(float(player["x"]) for player in enemies)
    teammate_xs = [float(player["x"]) for player in my_team]
    reasons: list[str] = []
    if not calibration_accepted or pitch_length_m is None:
        reasons.append("CALIBRATION_REQUIRED")
    if len(opponent_xs) < 2:
        reasons.append("SECOND_LAST_DEFENDER_UNKNOWN")
    if ball is None:
        reasons.append("BALL_POSITION_UNKNOWN")
    if not touch_timing_known:
        reasons.append("TOUCH_TIMING_UNKNOWN")
    if len(teammate_xs) < 2:
        reasons.append("TEAM_SPACING_UNKNOWN")
    second_last = (
        opponent_xs[-2] if attacking_increasing_x else opponent_xs[1]
    ) if len(opponent_xs) >= 2 else None
    most_advanced = (
        max(teammate_xs) if attacking_increasing_x else min(teammate_xs)
    ) if teammate_xs else None
    ready = not reasons
    scale = float(pitch_length_m or 0) / 100.0
    margin = None
    if ready and second_last is not None and most_advanced is not None:
        signed = most_advanced - second_last
        margin = signed * scale if attacking_increasing_x else -signed * scale
    return {
        "decision": None,
        "status": "review_only" if ready else "unknown",
        "availability": "review_only" if ready else "unknown",
        "validatedMeasurement": False,
        "reasonCodes": ["IFAB_LAW_11_NOT_APPLIED", *reasons],
        "attackDirection": attack_direction,
        "secondLastOpponentX": second_last,
        "mostAdvancedTeammateX": most_advanced,
        "ballX": None if ball is None else float(ball["x"]),
        "spacingWidthM": round((max(teammate_xs) - min(teammate_xs)) * scale, 3) if ready else None,
        "attackerBeyondSecondLastDefender": margin > 0 if margin is not None else None,
        "marginM": None if margin is None else round(margin, 3),
        "uncertaintyM": uncertainty_m if ready else None,
        "limitations": [
            "Position facts are not an offside offence.",
            "Eligible body parts, first contact, restarts and involvement are not measured.",
        ],
    }


def ground_contact_point(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """Bottom-centre of the box is the foot estimate. The box centre is not a foot."""

    x1, _y1, x2, y2 = bbox
    return {
        "imageX": (x1 + x2) / 2.0,
        "imageY": y2,
        "boxCentreIsFoot": False,
    }


def project_to_pitch(
    *,
    kind: Literal["player", "ball"],
    airborne: bool,
    bbox: tuple[float, float, float, float],
) -> dict[str, Any]:
    """Homography of an airborne ball is not a measured ground location."""

    contact = ground_contact_point(bbox)
    if kind == "ball" and airborne:
        return {
            "kind": kind,
            "airborne": True,
            "measuredGroundLocation": False,
            "boxCentreIsFoot": False,
            "imageX": None,
            "imageY": None,
            "reasonCodes": ["AERIAL_NOT_GROUND_PLANE"],
        }
    return {
        "kind": kind,
        "airborne": airborne,
        "measuredGroundLocation": True,
        "boxCentreIsFoot": False,
        "imageX": contact["imageX"],
        "imageY": contact["imageY"],
        "reasonCodes": [],
    }


def derived_distance(
    *,
    delta_m: float,
    uncertainty_m: float,
    cut_bridged: bool,
    identity_gap: bool,
    calibration_missing: bool = False,
) -> dict[str, Any]:
    """Never bridge camera cuts or identity gaps to create physical totals."""

    if cut_bridged:
        return {
            "availability": "withheld",
            "value": None,
            "uncertaintyM": uncertainty_m,
            "bridged": False,
            "reasonCodes": ["CAMERA_CUT"],
        }
    if identity_gap:
        return {
            "availability": "withheld",
            "value": None,
            "uncertaintyM": uncertainty_m,
            "bridged": False,
            "reasonCodes": ["IDENTITY_DISCONTINUITY"],
        }
    if calibration_missing:
        return {
            "availability": "withheld",
            "value": None,
            "uncertaintyM": uncertainty_m,
            "bridged": False,
            "reasonCodes": ["CALIBRATION_UNAVAILABLE"],
        }
    return {
        "availability": "available",
        "value": delta_m,
        "uncertaintyM": uncertainty_m,
        "bridged": False,
        "reasonCodes": [],
    }


def path_distance_m(frames: list[Any], profile: CalibrationProfile) -> float:
    """Sum accepted same-identity steps in metres without bridging missing tracks."""

    from math import hypot

    total = 0.0
    for index, frame in enumerate(frames):
        if index == 0:
            continue
        previous_by_id = {int(player.id): player for player in _frame_players(frames[index - 1])}
        for player in _frame_players(frame):
            previous = previous_by_id.get(int(player.id))
            if previous is None:
                continue
            x0, y0 = project_point(profile, float(previous.x), float(previous.y))
            x1, y1 = project_point(profile, float(player.x), float(player.y))
            total += hypot(x1 - x0, y1 - y0)
    return total


def _frame_players(frame: Any) -> list[Any]:
    return [
        *list(getattr(frame, "myTeam", None) or []),
        *list(getattr(frame, "enemies", None) or []),
        *list(getattr(frame, "unassignedPlayers", None) or []),
    ]


def detect_zoom_or_cut(previous: CalibrationProfile, current: CalibrationProfile) -> bool:
    if previous.cameraModel != current.cameraModel:
        return True
    if previous.homography and current.homography:
        delta = abs(previous.homography[0][0] - current.homography[0][0])
        return delta > 0.15
    return False


def preview_landmark_fit(*, residual_p95_m: float, max_p95_m: float) -> dict[str, Any]:
    return {
        "preview": True,
        "committed": False,
        "accepted": residual_p95_m <= max_p95_m,
        "visionRerun": False,
        "residualP95M": residual_p95_m,
        "rebuild": ["pitch_positions", "physical_metrics", "tactical_metrics", "report"],
    }


def project_point(profile: CalibrationProfile, image_x: float, image_y: float) -> tuple[float, float]:
    errors = validate_homography(profile.homography)
    if errors:
        raise CalibrationUnavailable(errors[0])
    h = profile.homography
    assert h is not None
    denom = h[2][0] * image_x + h[2][1] * image_y + h[2][2]
    if denom == 0:
        raise CalibrationUnavailable("DEGENERATE_POINT")
    x = (h[0][0] * image_x + h[0][1] * image_y + h[0][2]) / denom
    y = (h[1][0] * image_x + h[1][1] * image_y + h[1][2]) / denom
    if not math.isfinite(x) or not math.isfinite(y):
        raise CalibrationUnavailable("NONFINITE_PROJECTION")
    return x, y


def project_tracking_frames(
    frames: list[FrameData],
    profile: CalibrationProfile,
    *,
    pitch_length_m: float,
    pitch_width_m: float,
) -> list[FrameData]:
    def coordinates(x: float, y: float) -> tuple[float, float]:
        pitch_x, pitch_y = project_point(profile, x, y)
        return pitch_x / pitch_length_m * 100, pitch_y / pitch_width_m * 100

    def player(item: PlayerData) -> PlayerData:
        x, y = coordinates(item.x, item.y)
        return replace(item, x=x, y=y)

    projected: list[FrameData] = []
    for frame in frames:
        ball = None
        if frame.ball is not None:
            x, y = coordinates(frame.ball.x, frame.ball.y)
            ball = BallData(x=x, y=y, confidence=frame.ball.confidence)
        projected.append(
            frame.model_copy(
                update={
                    "ball": ball,
                    "myTeam": [player(item) for item in frame.myTeam],
                    "enemies": [player(item) for item in frame.enemies],
                    "unassignedPlayers": [player(item) for item in frame.unassignedPlayers],
                }
            )
        )
    return projected


def normalized_path_distance_m(frames: list[Any], *, pitch_length_m: float, pitch_width_m: float) -> float:
    """Distances of canonical 0..100 pitch coordinates; no image homography."""
    total = 0.0
    for previous, current in zip(frames, frames[1:], strict=False):
        if current.timestamp <= previous.timestamp:
            continue
        for field in ("myTeam", "enemies", "unassignedPlayers"):
            previous_by_id = {p.id:p for p in getattr(previous,field)}
            for p in getattr(current,field):
                old = previous_by_id.get(p.id)
                if old is not None:
                    total += math.hypot((p.x-old.x)*pitch_length_m/100, (p.y-old.y)*pitch_width_m/100)
    return total
