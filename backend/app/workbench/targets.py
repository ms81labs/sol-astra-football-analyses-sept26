"""Planning targets. These are not measured results or decode-latency promises."""

from __future__ import annotations

from typing import Any


def metadata_api_targets() -> dict[str, Any]:
    return {
        "p95MetadataApiReadMs": 500,
        "measured": False,
        "planningTargetNotMeasurement": True,
        "localTestSetup": True,
        "doesNotPromiseVideoDecodeLatency": True,
        "timelineLoadsAllFrameRecords": False,
    }
