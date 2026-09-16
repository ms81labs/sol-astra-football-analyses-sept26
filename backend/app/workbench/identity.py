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


def rows_from_frames(frames: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in frames:
        stamp = float(getattr(frame, "timestamp", 0.0))
        frame_id = getattr(frame, "frameId", None)
        for team, players in (
            ("my_team", getattr(frame, "myTeam", None) or []),
            ("enemy", getattr(frame, "enemies", None) or []),
            ("unassigned", getattr(frame, "unassignedPlayers", None) or []),
        ):
            for player in players:
                rows.append(
                    {
                        "trackId": str(getattr(player, "id", "")),
                        "t": stamp,
                        "x": getattr(player, "x", None),
                        "y": getattr(player, "y", None),
                        "team": team,
                        "frameId": frame_id,
                    }
                )
    return rows


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


def appearance_embedding_policy() -> dict[str, bool]:
    """Embeddings after occlusion or rejoin only. Camera cuts and similar kits defeat matching."""

    return {
        "everyDetection": False,
        "afterOcclusion": True,
        "afterRejoin": True,
        "cameraCutDefeatsAppearance": True,
        "similarKitsDefeatAppearance": True,
        "substitutionsDefeatAppearance": True,
    }


def assign_tracklet(*, roster_id: str | None, reviewed: bool) -> dict[str, Any]:
    """Never force every tracklet into a known player."""

    if reviewed and roster_id:
        return {"kind": "roster_player", "forced": False, "rosterId": roster_id}
    return {"kind": "tracklet", "forced": False, "rosterId": None}


def candidate_rejoin() -> dict[str, bool]:
    return {
        "preserveCompetingHypotheses": True,
        "requestReview": True,
        "autoAccepted": False,
    }


def tracker_chunk(*, scene_discontinuity: bool, broadcast_replay: bool) -> dict[str, bool]:
    """Carry a bounded tracker state across overlap; reset at genuine discontinuities and replays."""

    reset = scene_discontinuity or broadcast_replay
    return {
        "reset": reset,
        "silentlyReconnected": False,
        "carryForwardBoundedState": not reset,
    }


def face_recognition(*, requested: bool) -> dict[str, Any]:
    del requested
    return {"enabled": False, "reasonCodes": ["FACE_RECOGNITION_EXCLUDED"]}


def cross_season_identity(*, requested: bool) -> dict[str, Any]:
    del requested
    return {"enabled": False, "reasonCodes": ["CROSS_SEASON_IDENTITY_EXCLUDED"]}


def next_available_track_id(frames: list[Any]) -> int:
    ids = [0]
    for frame in frames:
        for players in (
            getattr(frame, "myTeam", None) or [],
            getattr(frame, "enemies", None) or [],
            getattr(frame, "unassignedPlayers", None) or [],
        ):
            for player in players:
                try:
                    ids.append(int(getattr(player, "id")))
                except (TypeError, ValueError):
                    continue
    return max(ids) + 1


def _remap_player_id(player: Any, *, source: str, dest: int) -> Any:
    if str(getattr(player, "id", "")) != source:
        return player
    try:
        return player.model_copy(update={"id": dest})
    except AttributeError:
        from dataclasses import replace

        return replace(player, id=dest)


def apply_track_split(
    frames: list[Any],
    *,
    track_id: str,
    at_frame: int,
    new_track_id: int,
) -> list[Any]:
    """Rename a tracklet from at_frame onward. Does not rerun vision."""

    updated: list[Any] = []
    for frame in frames:
        frame_id = int(getattr(frame, "frameId", 0) or 0)
        if frame_id < at_frame:
            updated.append(frame)
            continue
        updated.append(_remap_frame_track(frame, source=track_id, dest=new_track_id))
    return updated


def apply_track_join(frames: list[Any], *, left_track_id: str, right_track_id: str) -> list[Any]:
    """Merge right into left when they never occupy the same frame."""

    dest = int(left_track_id)
    return [_remap_frame_track(frame, source=right_track_id, dest=dest) for frame in frames]


def frames_with_track(frames: list[Any], track_id: str) -> list[int]:
    found: list[int] = []
    for frame in frames:
        ids = {
            str(getattr(player, "id", ""))
            for players in (
                getattr(frame, "myTeam", None) or [],
                getattr(frame, "enemies", None) or [],
                getattr(frame, "unassignedPlayers", None) or [],
            )
            for player in players
        }
        if track_id in ids:
            found.append(int(getattr(frame, "frameId", 0) or 0))
    return found


def apply_track_unjoin(
    frames: list[Any],
    *,
    left_track_id: str,
    right_track_id: str,
    right_frame_ids: list[int],
) -> list[Any]:
    """Restore the right track only on frames that originally held it."""

    allowed = {int(frame_id) for frame_id in right_frame_ids}
    dest = int(right_track_id)
    updated: list[Any] = []
    for frame in frames:
        if int(getattr(frame, "frameId", 0) or 0) in allowed:
            updated.append(_remap_frame_track(frame, source=left_track_id, dest=dest))
        else:
            updated.append(frame)
    return updated


def apply_team_swap(frames: list[Any]) -> list[Any]:
    """Swap labeled my_team and enemy sides. Does not rerun vision."""

    updated: list[Any] = []
    for frame in frames:
        possession = getattr(frame, "possession", None)
        if possession is not None:
            team = getattr(possession, "team", None)
            if team == "my_team":
                possession = possession.model_copy(update={"team": "enemy"})
            elif team == "enemy":
                possession = possession.model_copy(update={"team": "my_team"})
        updated.append(
            frame.model_copy(
                update={
                    "myTeam": list(getattr(frame, "enemies", None) or []),
                    "enemies": list(getattr(frame, "myTeam", None) or []),
                    "possession": possession,
                }
            )
        )
    return updated


def frames_have_identity_overlap(frames: list[Any], left_track_id: str, right_track_id: str) -> bool:
    for frame in frames:
        ids = {
            str(getattr(player, "id", ""))
            for players in (
                getattr(frame, "myTeam", None) or [],
                getattr(frame, "enemies", None) or [],
                getattr(frame, "unassignedPlayers", None) or [],
            )
            for player in players
        }
        if left_track_id in ids and right_track_id in ids:
            return True
    return False


def remap_track_references(
    items: list[Any],
    *,
    track_id: str,
    new_track_id: int,
    at_frame: int = 0,
    frame_ids: list[int] | None = None,
    frame_attr: str = "frameId",
    fields: tuple[str, ...] = ("trackId", "fromTrackId", "toTrackId", "playerId", "controllingTrackId"),
) -> list[Any]:
    allowed = {int(frame_id) for frame_id in frame_ids} if frame_ids is not None else None
    updated: list[Any] = []
    for item in items:
        frame_id = int(getattr(item, frame_attr, 0) or 0)
        if allowed is not None and frame_id not in allowed:
            updated.append(item)
            continue
        if frame_id < at_frame:
            updated.append(item)
            continue
        changes: dict[str, Any] = {}
        for field in fields:
            if not hasattr(item, field):
                continue
            value = getattr(item, field)
            if value is not None and str(value) == track_id:
                changes[field] = new_track_id
        updated.append(item.model_copy(update=changes) if changes else item)
    return updated


def _remap_frame_track(frame: Any, *, source: str, dest: int) -> Any:
    possession = getattr(frame, "possession", None)
    if possession is not None and str(getattr(possession, "trackId", "")) == source:
        possession = possession.model_copy(update={"trackId": dest})
    return frame.model_copy(
        update={
            "myTeam": [_remap_player_id(player, source=source, dest=dest) for player in (getattr(frame, "myTeam", None) or [])],
            "enemies": [_remap_player_id(player, source=source, dest=dest) for player in (getattr(frame, "enemies", None) or [])],
            "unassignedPlayers": [
                _remap_player_id(player, source=source, dest=dest)
                for player in (getattr(frame, "unassignedPlayers", None) or [])
            ],
            "possession": possession,
        }
    )
