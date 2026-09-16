"""Match-library search over declared camera/source metadata."""

from __future__ import annotations

from typing import Any


def search_match_library(*, query: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = [token for token in query.lower().split() if token]
    results: list[dict[str, Any]] = []
    for match in matches:
        haystack = " ".join(str(value).replace("_", " ").lower() for value in match.values())
        if tokens and all(token in haystack for token in tokens):
            results.append(match)
    return {"results": results}
