"""Correction-log persistence behind the Storage compatibility facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .workbench.review import CorrectionLog

if TYPE_CHECKING:
    from .storage import Storage


class CorrectionStorage:
    def __init__(self, owner: "Storage") -> None:
        self._owner = owner

    def path(self, match_id: str) -> Path:
        self._owner.get_match(match_id)
        path = self._owner._match_dir(match_id) / "corrections.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def load_log(self, match_id: str) -> CorrectionLog:
        path = self.path(match_id)
        if not path.exists():
            return CorrectionLog()
        return CorrectionLog.from_payload(self._owner._read_json(path))

    def save_log(self, match_id: str, log: CorrectionLog) -> None:
        self._owner._write_json(self.path(match_id), log.dump())

    def list_corrections(
        self,
        match_id: str,
        *,
        state: str | None = None,
    ) -> list[dict]:
        log = self.load_log(match_id)
        items = log.pending(match_id) if state == "pending" else log.history(match_id)
        return [item.model_dump(mode="json") for item in items]
