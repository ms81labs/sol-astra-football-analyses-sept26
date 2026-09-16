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
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_compatible(left: str, right: str) -> bool:
    return left == right
