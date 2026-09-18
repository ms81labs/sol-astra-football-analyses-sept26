from __future__ import annotations

from dataclasses import dataclass

MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK = 4
MIN_VISIBLE_PLAYERS_FOR_DEFENSIVE_LINE = 5


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    version: str
    unit: str | None
    denominator: str
    scope: str
    prerequisites: tuple[str, ...]
    aggregation: str


METRIC_DEFINITIONS = {
    "possession_pct": MetricDefinition(
        "possession_pct", "2", "percent", "eligible_seconds", "team", (), "time_weighted_share"
    ),
    "distance_m": MetricDefinition(
        "distance_m", "2", "metres", "identity_continuous_eligible_seconds", "team",
        ("identity_continuous", "calibration_accepted"), "sum",
    ),
    "speed_kmh": MetricDefinition(
        "speed_kmh", "2", "km/h", "identity_continuous_eligible_seconds", "team",
        ("identity_continuous", "calibration_accepted"), "maximum",
    ),
    "sprints": MetricDefinition(
        "sprints", "2", "count", "identity_continuous_eligible_seconds", "team",
        ("identity_continuous", "calibration_accepted"), "count_threshold_crossings",
    ),
    "defensive_line_height": MetricDefinition(
        "defensive_line_height", "2", "normalized_pitch_percent", "visible_defending_frames", "team",
        (f"minimum_{MIN_VISIBLE_PLAYERS_FOR_DEFENSIVE_LINE}_visible_players", "deepest_player_assumed_goalkeeper"),
        "mean",
    ),
    "line_breaking_events": MetricDefinition(
        "line_breaking_events", "2", "count", "eligible_visible_frames", "team",
        (f"minimum_{MIN_VISIBLE_DEFENDERS_FOR_LINE_BREAK}_visible_defenders", "defensive_roles_unassigned"),
        "count",
    ),
}
