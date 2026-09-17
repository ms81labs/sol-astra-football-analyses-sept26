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
    attacker_x: float | None,
    offside_line_x: float | None,
    uncertainty_m: float,
    attacker_x_by_time: tuple[tuple[float, float], ...] | None = None,
) -> dict[str, Any]:
    if attacker_x is None or offside_line_x is None:
        samples_in: tuple[tuple[float, float], ...] = ()
    else:
        samples_in = attacker_x_by_time if attacker_x_by_time is not None else (
            (touch_interval[0], attacker_x),
            (touch_interval[1], attacker_x),
        )
    samples: list[dict[str, Any]] = []
    any_cross = False
    for time, x in samples_in:
        if offside_line_x is None:
            break
        low = x - uncertainty_m
        high = x + uncertainty_m
        crosses = low < offside_line_x < high or abs(x - offside_line_x) <= uncertainty_m
        any_cross = any_cross or crosses
        samples.append(
            {
                "time": time,
                "attackerX": x,
                "offsideLineX": offside_line_x,
                "indeterminate": crosses,
                "decision": None,
            }
        )
    return {
        "level": 1,
        "touchInterval": touch_interval,
        "uncertaintyM": uncertainty_m,
        "indeterminate": any_cross or not samples,
        "decision": None,
        "validatedMeasurement": False,
        "singleExactFrame": False,
        "samples": samples,
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


def vlm_confidence_is_not_referee(*, confidence: float) -> dict[str, Any]:
    del confidence
    return {
        "refereeGroundTruth": False,
        "decision": None,
        "validatedMeasurement": False,
        "reasonCodes": ["VLM_CONFIDENCE_IS_NOT_REFEREE_GROUND_TRUTH"],
    }


def broadcast_replay_not_simultaneous(*, same_timestamp: bool) -> dict[str, Any]:
    return {
        "simultaneous": False,
        "admitted": bool(same_timestamp),
        "reasonCodes": [] if same_timestamp else ["SIMULTANEOUS_EVIDENCE_UNPROVEN"],
    }


def elevated_body_part_homography(*, part: str) -> dict[str, Any]:
    del part
    return {
        "preciseOffsideLine": False,
        "validatedMeasurement": False,
        "reasonCodes": ["GROUND_PLANE_NOT_BODY_PART"],
    }


def invisible_entity_not_repaired_by_larger_model(*, visible: bool) -> dict[str, Any]:
    return {
        "visible": visible,
        "repaired": False,
        "admitted": bool(visible),
        "reasonCodes": [] if visible else ["INVISIBLE_ENTITY_NOT_REPAIRED_BY_LARGER_MODEL"],
    }
