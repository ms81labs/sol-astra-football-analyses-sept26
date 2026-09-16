"""GA-08 identity lifecycle: tracklet, match identity and roster player are distinct."""

from __future__ import annotations

from typing import Literal

from .contracts import StrictModel

IdentityKind = Literal["tracklet", "match_identity", "roster_player"]


class IdentityRecord(StrictModel):
    kind: IdentityKind
    trackId: str
    intervalStart: float = 0.0
    intervalEnd: float = 0.0
    rosterId: str | None = None


def promote_identity(
    record: IdentityRecord,
    *,
    target: IdentityKind,
    reviewed: bool,
    rosterId: str | None = None,
) -> IdentityRecord:
    if not reviewed:
        return record
    if target == "match_identity" and record.kind == "tracklet":
        return record.model_copy(update={"kind": "match_identity"})
    if target == "roster_player" and record.kind == "match_identity" and rosterId:
        return record.model_copy(update={"kind": "roster_player", "rosterId": rosterId})
    return record
