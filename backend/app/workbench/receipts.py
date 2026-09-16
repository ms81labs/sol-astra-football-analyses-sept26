"""8.5 promotion receipts. A stage benchmark is not complete-match acceptance."""

from __future__ import annotations

from typing import Any


def promotion_receipt(
    *,
    source_sha256: str,
    weights: str,
    configuration: str,
    hardware: str,
    native_builds: list[str],
    selected_backend: str,
    frame_count: int,
    call_count: int,
    cold_timing_ms: float,
    warm_timing_ms: float,
    peak_memory_bytes: int,
    transferred_bytes: int,
    output_quality: str,
    accepted_coverage: float,
    failure_cases: list[str],
    allocated_spend: float,
    fallback_event: str | None,
) -> dict[str, Any]:
    return {
        "sourceSha256": source_sha256,
        "weights": weights,
        "configuration": configuration,
        "hardware": hardware,
        "nativeBuilds": list(native_builds),
        "selectedBackend": selected_backend,
        "frameCount": frame_count,
        "callCount": call_count,
        "coldTimingMs": cold_timing_ms,
        "warmTimingMs": warm_timing_ms,
        "peakMemoryBytes": peak_memory_bytes,
        "transferredBytes": transferred_bytes,
        "outputQuality": output_quality,
        "acceptedCoverage": accepted_coverage,
        "failureCases": list(failure_cases),
        "allocatedSpend": allocated_spend,
        "fallbackEvent": fallback_event,
        "stageBenchmarkIsCompleteMatchAcceptance": False,
        "completeMatchAccepted": False,
    }
