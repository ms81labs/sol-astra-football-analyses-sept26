"""C03 auxiliary analytical state. Unknown is not an empty measured state."""
from __future__ import annotations

from typing import Any
from .schemas import BallOwnership, MatchStateFrame


def bind_state(match_id: str, generation_id: str, value: dict | None, *, frame_count: int = 0) -> dict:
    if value is None:
        return {"schemaVersion": 1, "matchId": match_id, "generationId": generation_id,
                "availability": "unknown", "reasonCodes": ["ACCEPTED_STATE_NOT_RECONSTRUCTED"],
                "frames": []}
    if not isinstance(value, dict) or not isinstance(value.get("frames"), list):
        raise ValueError("Malformed accepted match state")
    if frame_count and not value["frames"]:
        # Some admitted observation-only paths have no ownership/state result.
        # Publish explicit unavailability, not an empty measured match state.
        if value.get("stateContinuityAppliedFrames", 0):
            raise ValueError("Empty state cannot have applied continuity")
        return {**bind_state(match_id, generation_id, None),
                "reasonCodes": ["STATE_ASSIGNMENTS_UNAVAILABLE"]}
    return {**value, "schemaVersion": 1, "matchId": match_id, "generationId": generation_id,
            "availability": "available", "reasonCodes": []}


def validate_state(
    value: Any, match_id: str, generation_id: str, frames: list[dict], assignments: list[dict]
) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ValueError("Unsupported accepted-state envelope")
    if value.get("matchId") != match_id or value.get("generationId") != generation_id:
        raise ValueError("Accepted state belongs to another snapshot")
    if value.get("availability") == "unknown":
        if value.get("frames") != [] or not value.get("reasonCodes"):
            raise ValueError("Unknown accepted state requires a reason and no measured frames")
        return
    if value.get("availability") != "available" or not isinstance(value.get("frames"), list):
        raise ValueError("Invalid accepted-state availability")
    if len(frames) != len(value["frames"]) or len(frames) != len(assignments):
        raise ValueError("Accepted-state coverage differs from published frames/assignments")
    # An occluded control track may be supported by adjacent samples. It must
    # nevertheless exist in this corrected generation, with its declared team.
    identities = {(p["id"], team) for f in frames
                  for team, players in (("my_team", f.get("myTeam", [])), ("enemy", f.get("enemies", [])))
                  for p in players}
    for frame, payload, assignment_payload in zip(frames, value["frames"], assignments, strict=False):
        state = MatchStateFrame.model_validate(payload)
        assignment = BallOwnership.model_validate(assignment_payload)
        if (assignment.frameId, assignment.timestamp) != (state.frameId, state.timestamp):
            raise ValueError("Accepted-state clock differs from published assignments")
        # Both artifacts describe the final, continuity-adjusted ownership. A
        # valid identity elsewhere in the match cannot certify this frame.
        controlled = state.mode == "controlled_possession"
        if controlled or assignment.team in {"my_team", "enemy"}:
            if (not controlled or state.controllingTrackId is None
                    or (state.controllingTeam, state.controllingTrackId)
                    != (assignment.team, assignment.trackId)):
                raise ValueError("Accepted-state controller differs from published assignment")
        elif state.controllingTrackId is not None or state.controllingTeam in {"my_team", "enemy"}:
            raise ValueError("Non-controlled accepted state cannot name a controlling track/team")
        if frame["frameId"] != state.frameId or frame["timestamp"] != state.timestamp:
            raise ValueError("Accepted-state clock differs from published frames")
        if state.controllingTrackId is not None and (
            state.controllingTrackId, state.controllingTeam
        ) not in identities:
            raise ValueError("Accepted state refers to an unknown corrected identity/team")
