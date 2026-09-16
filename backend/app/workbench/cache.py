"""GA-12 cache identity for selective recomputation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def cache_identity(
    *,
    source_sha256: str,
    interval_start: float,
    interval_end: float,
    decoder_version: str,
    model_hash: str,
    temporal_policy: str,
    output_schema: str,
    crop: tuple[int, int, int, int] | None = None,
    colour_order: str = "bgr",
    calibration_id: str | None = None,
    namespace: str = "development",
) -> str:
    payload: dict[str, Any] = {
        "sourceSha256": source_sha256,
        "intervalStart": interval_start,
        "intervalEnd": interval_end,
        "decoderVersion": decoder_version,
        "modelHash": model_hash,
        "temporalPolicy": temporal_policy,
        "outputSchema": output_schema,
        "crop": list(crop) if crop else None,
        "colourOrder": colour_order,
        "calibrationId": calibration_id,
        "namespace": namespace,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_compatible(left: str, right: str) -> bool:
    return left == right


REBUILD_FOR: dict[str, list[str]] = {
    "report": ["report"],
    "team_mapping": ["team_state", "events", "metrics", "report"],
    "track_edit": ["ownership", "player_events", "metrics", "report"],
    "calibration": ["pitch_positions", "physical_metrics", "tactical_metrics", "report"],
    "perception": ["observations", "tracking", "dependants"],
    "ownership": ["events", "metrics", "report"],
}


def recompute_plan(
    *,
    previous_identity: str | None,
    current_identity: str,
    change: str,
) -> dict[str, Any]:
    if previous_identity == current_identity:
        return {"reuse": True, "rebuild": [], "reason": "identical_cache_identity"}
    return {
        "reuse": False,
        "rebuild": list(REBUILD_FOR[change]),
        "reason": "cache_identity_changed",
    }
