"""GA-09 experimental shot-quality baseline. Not a calibrated xG model."""

from __future__ import annotations

from math import exp
from typing import Any

from pydantic import Field

from .contracts import StrictModel

POST_OUTCOME_FEATURES = frozenset({"goal", "save", "on_target", "xg_post", "outcome"})


class ShotQuality(StrictModel):
    publishedLabel: str = "experimental_shot_quality"
    availability: str = "experimental"
    compatibilityFields: list[str] = Field(default_factory=lambda: ["xg"])
    value: float
    reasonCodes: list[str] = Field(default_factory=list)


def extract_shot_features(shot: dict[str, Any]) -> dict[str, float | bool]:
    leaked = sorted(name for name in shot if name in POST_OUTCOME_FEATURES)
    if leaked:
        raise ValueError(f"post-outcome features are not allowed: {leaked}")
    x = float(shot["x"])
    y = float(shot["y"])
    dx = 100.0 - x
    dy = 50.0 - y
    distance = (dx * dx + dy * dy) ** 0.5
    angle = abs(dy) + 1.0
    return {
        "x": x,
        "y": y,
        "inBox": bool(shot.get("inBox", dx <= 16.5 and abs(dy) <= 20.16)),
        "distance": distance,
        "angle": angle,
    }


def experimental_shot_quality(features: dict[str, float | bool]) -> ShotQuality:
    distance = float(features["distance"])
    in_box = 1.0 if features.get("inBox") else 0.0
    logit = -2.2 + (0.04 * (40.0 - distance)) + (0.6 * in_box)
    value = 1.0 / (1.0 + exp(-logit))
    return ShotQuality(
        value=round(value, 4),
        reasonCodes=["EXPERIMENTAL_NOT_CALIBRATED_XG"],
    )


def missing_shot_features(shot: dict[str, Any]) -> dict[str, Any]:
    required = ("x", "y")
    missing = [name for name in required if name not in shot]
    return {
        "recorded": True,
        "missing": missing,
        "imputedAsCalibrated": False,
    }


def tree_challenger(*, logistic_calibrated: bool) -> dict[str, bool]:
    return {
        "enabled": logistic_calibrated,
        "comparedAfterLogisticBaseline": True,
        "calibratedXg": False,
    }
