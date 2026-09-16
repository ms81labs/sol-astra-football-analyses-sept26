"""GA-04.8 incident review ladder. Level 0 is manual clips, notes and bookmarks."""

from __future__ import annotations

from typing import Any


def level0_incident_package(
    *,
    clips: list[dict[str, Any]],
    notes: list[str],
    bookmarks: list[float],
) -> dict[str, Any]:
    return {
        "level": 0,
        "clips": clips,
        "notes": notes,
        "bookmarks": bookmarks,
        "decision": None,
        "validatedMeasurement": False,
        "reasonCodes": ["IFAB_LAW_11_NOT_APPLIED", "MANUAL_INCIDENT_PACKAGE"],
        "limitations": [
            "Synchronized source clips and notes only.",
            "Position facts are not an offside offence.",
        ],
    }


def level1_positional_aid(
    *,
    touch_interval: tuple[float, float],
    attacker_x: float,
    offside_line_x: float,
    uncertainty_m: float,
) -> dict[str, Any]:
    low = min(attacker_x - uncertainty_m, attacker_x + uncertainty_m)
    high = max(attacker_x - uncertainty_m, attacker_x + uncertainty_m)
    crosses = low < offside_line_x < high or abs(attacker_x - offside_line_x) <= uncertainty_m
    return {
        "level": 1,
        "touchInterval": touch_interval,
        "uncertaintyM": uncertainty_m,
        "indeterminate": crosses,
        "decision": None,
        "validatedMeasurement": False,
        "reasonCodes": ["GROUND_PLANE_NOT_BODY_PART_BOUNDARY", "IFAB_LAW_11_NOT_APPLIED"],
        "limitations": ["Estimated pitch positions with uncertainty bands. Not an official ruling."],
    }


def level2_schematic_replay(*, coordinates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "level": 2,
        "coordinates": coordinates,
        "photorealistic": False,
        "schematic": True,
        "decision": None,
        "validatedMeasurement": False,
        "reasonCodes": ["SCHEMATIC_NOT_RECOVERED_SCENE"],
    }


def level3_multiview() -> dict[str, Any]:
    return {
        "level": 3,
        "enabled": False,
        "decision": None,
        "validatedMeasurement": False,
        "reasonCodes": ["NEW_DATASET_REQUIRED", "CALIBRATION_PROTOCOL_REQUIRED"],
    }
