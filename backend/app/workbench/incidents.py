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
