"""GA-01 research-lane containment. Planned tracks stay inert."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from .contracts import REASON_CODES

SUPPORTED_COVERAGE = "supported-coverage"
PLANNED_TRACKS = (
    "possession/events",
    "trust-crops",
    "gpu-bounded-loops",
    "later-training",
)
_PRODUCT_PREFIXES = ("backend/", "frontend/", "detector/", "analytics/", "truth-gate/")


def research_lane() -> dict[str, Any]:
    tracks = [
        {"id": SUPPORTED_COVERAGE, "executable": True, "inert": False, "role": "addon_only"},
    ]
    tracks.extend({"id": name, "executable": False, "inert": True, "role": "planned"} for name in PLANNED_TRACKS)
    return {
        "isolated": True,
        "supportedCoverageExecutable": True,
        "autonomousProductionChanges": False,
        "appendOnlyTrialHistory": True,
        "tracks": tracks,
    }


def may_write_product_paths(paths: list[str]) -> bool:
    for path in paths:
        normalised = path.replace("\\", "/").lstrip("./")
        if any(normalised == prefix.rstrip("/") or normalised.startswith(prefix) for prefix in _PRODUCT_PREFIXES):
            return False
    return True


def execute_track(track_id: str, *, in_production: bool = True) -> dict[str, Any]:
    resolved = unquote(track_id)
    if resolved != SUPPORTED_COVERAGE:
        return {
            "executed": False,
            "trackId": resolved,
            "productionMutation": False,
            "reasonCodes": ["PLANNED_TRACK_INERT"],
            "detail": REASON_CODES["PLANNED_TRACK_INERT"],
        }
    if in_production:
        return {
            "executed": False,
            "trackId": resolved,
            "productionMutation": False,
            "reasonCodes": ["RESEARCH_ADDON_ONLY"],
            "detail": REASON_CODES["RESEARCH_ADDON_ONLY"],
        }
    return {
        "executed": True,
        "trackId": resolved,
        "productionMutation": False,
        "reasonCodes": [],
    }
