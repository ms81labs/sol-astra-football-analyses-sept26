"""6.3 repository adapter. Extends persistence; does not replace storage.py."""

from __future__ import annotations

from typing import Any, Iterable

DEFAULT_FRAME_PAGE_LIMIT = 240


def _frame_id(item: Any) -> int:
    if hasattr(item, "frameId"):
        return int(item.frameId)
    if isinstance(item, dict):
        return int(item.get("frameId") or item.get("Frame_ID") or 0)
    return 0


class RepositoryAdapter:
    backend_name = "sqlite_plus_artifacts"
    replaces_storage_module = False

    def page_frames(
        self,
        frames: Iterable[Any],
        *,
        after_frame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        ordered = list(frames)
        start = 0
        if cursor not in (None, ""):
            start = max(start, int(cursor))
        if after_frame is not None:
            match_index = next((index for index, item in enumerate(ordered) if _frame_id(item) >= after_frame), len(ordered))
            start = max(start, match_index)
        size = DEFAULT_FRAME_PAGE_LIMIT if limit is None else min(max(int(limit), 1), DEFAULT_FRAME_PAGE_LIMIT)
        page = ordered[start : start + size]
        next_index = start + size
        return {
            "frames": page,
            "nextCursor": str(next_index) if next_index < len(ordered) else None,
            "frameCount": len(ordered),
            "intervalEndpoint": "half_open",
        }


def http_may_run_gpu() -> bool:
    return False


def vector_broker_required() -> bool:
    return False
