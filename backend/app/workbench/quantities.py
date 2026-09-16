"""GA-03/6.1 distinct score quantities and pitch-axis conventions."""

from __future__ import annotations

from typing import Any


def pitch_axes() -> dict[str, str]:
    return {"x": "longitudinal", "y": "lateral", "origin": "declared_calibration", "legacyDisplay": "transform_explicitly"}


def split_scores(
    *,
    detector_score: float | None,
    calibrated_probability: float | None,
    interval: tuple[float, float] | None,
) -> dict[str, Any]:
    return {
        "detectorScore": detector_score,
        "calibratedProbability": calibrated_probability,
        "confidenceInterval": list(interval) if interval else None,
    }


def attack_direction_for(
    *,
    team: str,
    period: int,
    mapping: dict[tuple[str, int], str],
) -> str | None:
    return mapping.get((team, period))


def formation_availability(*, eligible_windows: int, role_context: bool) -> dict[str, Any]:
    if eligible_windows < 2 or not role_context:
        return {
            "availability": "withheld",
            "reasonCodes": ["SINGLE_FRAME_FORMATION"],
            "value": None,
        }
    return {"availability": "available", "reasonCodes": [], "value": "computed"}
