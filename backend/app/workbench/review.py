"""GA-04 setup/review corrections, playlists, and identity repair edits."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel, jsonable
from .cache import REBUILD_FOR

EditKind = Literal[
    "team_mapping",
    "track_split",
    "track_join",
    "event_reject",
    "event_accept",
    "calibration",
    "playlist_item",
]
SaveState = Literal["saved", "pending", "conflicted"]

CORRECTION_INVALIDATION: dict[str, str] = {
    "team_mapping": "team_mapping",
    "track_split": "track_edit",
    "track_join": "track_edit",
    "event_reject": "ownership",
    "event_accept": "ownership",
    "ownership": "ownership",
    "calibration": "calibration",
    "playlist_item": "report",
}


class Correction(StrictModel):
    correctionId: str
    matchId: str
    kind: EditKind
    author: str
    createdAt: str
    payload: dict[str, Any]
    undoOf: str | None = None
    saveState: SaveState = "saved"
    version: int = 1


class PlaylistExport(StrictModel):
    playlistId: str
    matchId: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class CorrectionLog:
    def __init__(self) -> None:
        self._items: list[Correction] = []
        self._lock = threading.Lock()
        self._pending: dict[str, Correction] = {}

    def submit(
        self,
        correction: Correction,
        *,
        crash_before_commit: bool = False,
        expected_version: int | None = None,
    ) -> Correction:
        with self._lock:
            current = 0
            for item in self._items:
                if item.matchId == correction.matchId:
                    current = max(current, item.version)
            if expected_version is not None and current != expected_version:
                return correction.model_copy(update={"saveState": "conflicted"})
            pending = correction.model_copy(update={"saveState": "pending"})
            self._pending[pending.correctionId] = pending
            if crash_before_commit:
                return pending
            version = current + 1 if expected_version is not None else (correction.version if current == 0 else current + 1)
            committed = pending.model_copy(update={"saveState": "saved", "version": version})
            self._items.append(committed)
            self._pending.pop(pending.correctionId, None)
            return committed

    def recover(self, correction_id: str) -> Correction:
        with self._lock:
            if correction_id in self._pending:
                pending = self._pending[correction_id]
                committed = pending.model_copy(update={"saveState": "saved"})
                self._items.append(committed)
                self._pending.pop(correction_id)
                return committed
            for item in self._items:
                if item.correctionId == correction_id:
                    return item
        raise KeyError(correction_id)

    def undo(self, correction_id: str, *, author: str) -> Correction:
        original = self._require(correction_id)
        inverse = Correction(
            correctionId=str(uuid.uuid4()),
            matchId=original.matchId,
            kind=original.kind,
            author=author,
            createdAt=_now(),
            payload={"undo": original.payload, "restoredFrom": original.correctionId},
            undoOf=original.correctionId,
            saveState="saved",
            version=original.version + 1,
        )
        return self.submit(inverse)

    def pending(self, match_id: str) -> list[Correction]:
        with self._lock:
            return [item for item in self._pending.values() if item.matchId == match_id]

    def history(self, match_id: str) -> list[Correction]:
        return [item for item in self._items if item.matchId == match_id]

    def dump(self) -> dict[str, Any]:
        with self._lock:
            return {
                "items": [item.model_dump(mode="json") for item in self._items],
                "pending": [item.model_dump(mode="json") for item in self._pending.values()],
            }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "CorrectionLog":
        log = cls()
        if not payload:
            return log
        for item in payload.get("items") or []:
            log._items.append(Correction.model_validate(item))
        for item in payload.get("pending") or []:
            pending = Correction.model_validate(item)
            log._pending[pending.correctionId] = pending
        return log

    def _require(self, correction_id: str) -> Correction:
        for item in self._items:
            if item.correctionId == correction_id:
                return item
        raise KeyError(correction_id)


def new_correction(
    match_id: str,
    kind: EditKind,
    payload: dict[str, Any],
    *,
    author: str = "analyst",
) -> Correction:
    return Correction(
        correctionId=str(uuid.uuid4()),
        matchId=match_id,
        kind=kind,
        author=author,
        createdAt=_now(),
        payload=payload,
        saveState="pending",
    )


def change_history(items: list[Correction] | list[dict[str, Any]]) -> dict[str, Any]:
    serialised: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Correction):
            serialised.append(item.model_dump())
        else:
            serialised.append(dict(item))
    return {
        "undoable": True,
        "rewrotePastOutcomes": False,
        "items": serialised,
    }


def collaboration_lock(
    *,
    mode: str,
    lock_holder: str | None = None,
    requester: str | None = None,
) -> dict[str, Any]:
    if mode == "local_only":
        return {
            "required": False,
            "admitted": True,
            "acquired": True,
            "silentlyReplaced": False,
            "mode": mode,
        }
    acquired = bool(lock_holder) and lock_holder == requester
    return {
        "required": True,
        "admitted": False,
        "acquired": acquired,
        "silentlyReplaced": False,
        "mode": mode,
        "lockHolder": lock_holder,
        "requester": requester,
    }


def playlist_export_interval(item: dict[str, Any], source_fps: float) -> dict[str, float | int]:
    start = float(item["timestampStart"])
    end = float(item["timestampEnd"])
    if end < start:
        raise ValueError("playlist interval is reversed")
    return {
        "sourceStartSeconds": start,
        "sourceEndSeconds": end,
        "sourceStartFrame": int(round(start * source_fps)),
        "sourceEndFrameExclusive": int(round(end * source_fps)),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def correction_api_payload(saved: Correction) -> dict[str, Any]:
    payload = jsonable(saved)
    if saved.saveState == "saved":
        change = CORRECTION_INVALIDATION.get(saved.kind, "report")
        payload["rebuild"] = list(REBUILD_FOR[change])
    else:
        payload["rebuild"] = []
    return payload
