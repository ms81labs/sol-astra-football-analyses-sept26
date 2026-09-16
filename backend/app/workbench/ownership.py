"""GA-08 ownership states: nearest player is not control."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel

OwnershipMode = Literal["controlled_possession", "loose_ball", "aerial_transit", "restart_or_out", "unknown"]


class OwnershipObservation(StrictModel):
    mode: OwnershipMode
    controllingTeam: Literal["my_team", "enemy", "unassigned", "contested", "none"] = "none"
    reasonCodes: list[str] = Field(default_factory=list)


class PossessionSummary(StrictModel):
    availability: str
    unknownSeconds: float
    eligibleSeconds: float
    requestedSeconds: float
    myTeamSeconds: float = 0.0
    enemySeconds: float = 0.0
    value: float | None = None
    reasonCodes: list[str] = Field(default_factory=list)

    def published_value(self) -> float | None:
        if self.availability not in {"available", "experimental"}:
            return None
        return self.value


class OwnershipHysteresis:
    def __init__(self, min_persistence: int = 3):
        self.min_persistence = min_persistence
        self.current = "unknown"
        self.pending: str | None = None
        self.count = 0

    def observe(self, team: str) -> str:
        if team == self.current:
            self.pending = None
            self.count = 0
            return self.current
        if self.pending != team:
            self.pending = team
            self.count = 1
        else:
            self.count += 1
        if self.count >= self.min_persistence:
            self.current = team
            self.pending = None
            self.count = 0
            return self.current
        return self.current if self.current != "unknown" else "unknown"


def classify_ownership(
    *,
    ball_visible: bool,
    nearest_team: str | None,
    nearest_distance: float | None,
    relative_motion: str | None,
    persistence_frames: int,
    calibrated: bool = False,
) -> OwnershipObservation:
    del nearest_distance
    if not ball_visible:
        return OwnershipObservation(mode="unknown", reasonCodes=["UNKNOWN_BALL_STATE"])
    if relative_motion is None or persistence_frames < 3 or not calibrated or nearest_team is None:
        return OwnershipObservation(mode="unknown", reasonCodes=["NEAREST_PLAYER_INSUFFICIENT"])
    if nearest_team not in {"my_team", "enemy"}:
        return OwnershipObservation(mode="loose_ball", controllingTeam="contested", reasonCodes=["UNASSIGNED_NEAR_PLAYER"])
    return OwnershipObservation(mode="controlled_possession", controllingTeam=nearest_team, reasonCodes=[])


def possession_from_states(states: list[dict[str, Any]], requested_seconds: float) -> PossessionSummary:
    unknown = sum(float(item.get("seconds") or 0.0) for item in states if item.get("mode") == "unknown")
    my_team = sum(
        float(item.get("seconds") or 0.0)
        for item in states
        if item.get("mode") == "controlled_possession" and item.get("controllingTeam") == "my_team"
    )
    enemy = sum(
        float(item.get("seconds") or 0.0)
        for item in states
        if item.get("mode") == "controlled_possession" and item.get("controllingTeam") == "enemy"
    )
    eligible = my_team + enemy
    reasons = []
    if unknown > 0:
        reasons.append("UNKNOWN_INTERVALS_EXCLUDED")
    availability = "insufficient_coverage" if unknown > 0 or eligible <= 0 else "available"
    value = None if availability != "available" else round(100.0 * my_team / eligible, 4)
    return PossessionSummary(
        availability=availability,
        unknownSeconds=unknown,
        eligibleSeconds=eligible,
        requestedSeconds=requested_seconds,
        myTeamSeconds=my_team,
        enemySeconds=enemy,
        value=value,
        reasonCodes=reasons,
    )
