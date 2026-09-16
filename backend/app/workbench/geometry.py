"""GA-05 versioned calibration and geometry checks."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel

CameraModel = Literal["planar_homography", "distortion_corrected", "segmented"]


class Landmark(StrictModel):
    name: str
    imageX: float
    imageY: float
    pitchX: float
    pitchY: float
    independentHoldout: bool = False


class CalibrationProfile(StrictModel):
    calibrationId: str
    schemaVersion: str = "calibration_v2"
    cameraModel: CameraModel
    pitchLengthM: float | None = None
    pitchWidthM: float | None = None
    validRegion: Literal["full_pitch", "near", "middle", "far", "unknown"] = "unknown"
    homography: list[list[float]] | None = None
    distortionK: list[float] = Field(default_factory=list)
    landmarks: list[Landmark] = Field(default_factory=list)
    sourceIntervalStart: float = 0.0
    sourceIntervalEnd: float | None = None
    residualP95M: float | None = None
    regionErrorsM: dict[str, float] = Field(default_factory=dict)
    compatibleWithFourPointV1: bool = True


def from_legacy_four_points(
    points: list[dict[str, float]],
    *,
    calibration_id: str,
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
                ((0.0, 0.0), (105.0, 0.0), (105.0, 68.0), (0.0, 68.0)),
                strict=True,
            )
        )
    ]
    return CalibrationProfile(
        calibrationId=calibration_id,
        cameraModel="planar_homography",
        landmarks=landmarks,
        compatibleWithFourPointV1=True,
        validRegion="unknown",
    )


def evaluate_landmarks(profile: CalibrationProfile, *, max_p95_m: float) -> dict[str, Any]:
    holdout = [mark for mark in profile.landmarks if mark.independentHoldout]
    if not holdout:
        return {
            "accepted": False,
            "reasonCodes": ["CALIBRATION_UNAVAILABLE"],
            "holdoutCount": 0,
        }
    residuals = []
    for mark in holdout:
        projected = _project(profile, mark.imageX, mark.imageY)
        residuals.append(((projected[0] - mark.pitchX) ** 2 + (projected[1] - mark.pitchY) ** 2) ** 0.5)
    residuals.sort()
    p95 = residuals[min(len(residuals) - 1, max(0, int(round(0.95 * (len(residuals) - 1)))))]
    far = [value for mark, value in zip(holdout, residuals) if mark.pitchY >= 45]
    region_ok = (max(far) if far else p95) <= max_p95_m
    return {
        "accepted": p95 <= max_p95_m and region_ok,
        "p95M": p95,
        "holdoutCount": len(holdout),
        "farSideMaxM": max(far) if far else None,
        "reasonCodes": [] if p95 <= max_p95_m and region_ok else ["CALIBRATION_UNAVAILABLE"],
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
) -> dict[str, Any]:
    """Deterministic geometry for review. Never publishes a validated offside decision."""

    attacking_increasing_x = attack_direction == "left_to_right"
    opponent_xs = sorted(float(player["x"]) for player in enemies)
    if len(opponent_xs) >= 2:
        second_last = opponent_xs[-2] if attacking_increasing_x else opponent_xs[1]
    else:
        second_last = opponent_xs[0] if opponent_xs else None
    most_advanced = None
    if my_team:
        xs = [float(player["x"]) for player in my_team]
        most_advanced = max(xs) if attacking_increasing_x else min(xs)
    return {
        "decision": None,
        "availability": "review_only",
        "validatedMeasurement": False,
        "reasonCodes": ["IFAB_LAW_11_NOT_APPLIED", "INVOLVEMENT_AND_TIMING_UNMEASURED"],
        "attackDirection": attack_direction,
        "secondLastOpponentX": second_last,
        "mostAdvancedTeammateX": most_advanced,
        "ballX": None if ball is None else float(ball["x"]),
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


def detect_zoom_or_cut(previous: CalibrationProfile, current: CalibrationProfile) -> bool:
    if previous.cameraModel != current.cameraModel:
        return True
    if previous.homography and current.homography:
        delta = abs(previous.homography[0][0] - current.homography[0][0])
        return delta > 0.15
    return False


def _project(profile: CalibrationProfile, image_x: float, image_y: float) -> tuple[float, float]:
    if profile.homography:
        h = profile.homography
        denom = h[2][0] * image_x + h[2][1] * image_y + h[2][2]
        if denom == 0:
            return (float("nan"), float("nan"))
        x = (h[0][0] * image_x + h[0][1] * image_y + h[0][2]) / denom
        y = (h[1][0] * image_x + h[1][1] * image_y + h[1][2]) / denom
        return x, y
    if profile.landmarks:
        return profile.landmarks[0].pitchX, profile.landmarks[0].pitchY
    return 0.0, 0.0
