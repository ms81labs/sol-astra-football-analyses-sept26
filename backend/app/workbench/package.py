"""Appendix A reviewed match package for analyst and operator."""

from __future__ import annotations

from typing import Any


SECRET_KEYS = ("DAYTONA_API_KEY", "RUNPOD_", "OPENAI_API_KEY", "API_KEY", "TOKEN", "SECRET")


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _scrub(item)
            for key, item in value.items()
            if not any(token.lower() in str(key).lower() for token in SECRET_KEYS)
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str) and any(token.lower() in value.lower() for token in ("must-not-leak", "sk-")):
        return "[redacted]"
    return value


def assemble_match_package(
    *,
    playlist: list[dict[str, Any]],
    events: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    corrections: list[dict[str, Any]] | None = None,
    cost: dict[str, Any] | None = None,
    secrets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del secrets
    return {
        "analyst": {
            "playlist": _scrub(playlist),
            "events": _scrub(events),
            "metrics": _scrub(metrics),
            "corrections": _scrub(corrections or []),
            "coverage": {
                "unknownMetrics": [item for item in metrics if item.get("availability") != "available"],
            },
            "limitations": [
                "Independent labels 0/18 complete.",
                "Physical metrics withheld until identity and calibration gates pass.",
                "Optional language assistance is disabled; this package is deterministic.",
            ],
        },
        "operator": {
            "manifest": {"schema": "match_package_v1", "sourceSnapshot": "5099e1fd50d856a7cd0449f1ef4b1695d8f930c3"},
            "cost": _scrub(cost or {}),
            "cleanupStatus": "not_required",
            "errorCategories": [],
        },
    }
