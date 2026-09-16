"""GA-08 identity lifecycle: tracklet, match identity and roster player are distinct."""

from __future__ import annotations

from typing import Any, Literal

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


class ClusterMapping(StrictModel):
    clusterId: int
    semanticTeam: Literal["my_team", "enemy"] | None = None
    suggestion: bool = True
    notes: str = "Numeric cluster IDs are not stable home/away labels."


def cluster_mapping(*, cluster_id: int, selected_semantic: str | None) -> ClusterMapping:
    semantic = selected_semantic if selected_semantic in {"my_team", "enemy"} else None
    return ClusterMapping(clusterId=cluster_id, semanticTeam=semantic, suggestion=semantic is None)


def player_observations(rows: list[dict[str, Any]], *, identity_continuous: bool) -> dict[str, Any]:
    if identity_continuous:
        return {"intervalLimited": False, "totalsWithheld": False, "rows": rows, "reasonCodes": []}
    return {
        "intervalLimited": True,
        "totalsWithheld": True,
        "rows": rows,
        "reasonCodes": ["IDENTITY_DISCONTINUITY"],
    }


def reconnect_across_cut(*, cut_detected: bool) -> dict[str, Any]:
    """Camera cuts reset identity. Never silently reconnect across a cut."""

    if cut_detected:
        return {
            "reset": True,
            "silentlyReconnected": False,
            "reasonCodes": ["CAMERA_CUT"],
        }
    return {"reset": False, "silentlyReconnected": False, "reasonCodes": []}


def face_recognition(*, requested: bool) -> dict[str, Any]:
    del requested
    return {"enabled": False, "reasonCodes": ["FACE_RECOGNITION_EXCLUDED"]}


def cross_season_identity(*, requested: bool) -> dict[str, Any]:
    del requested
    return {"enabled": False, "reasonCodes": ["CROSS_SEASON_IDENTITY_EXCLUDED"]}
