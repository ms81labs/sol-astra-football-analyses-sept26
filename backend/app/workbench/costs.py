"""GA-12/7.1 match cost. Export fps is not inference cost."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from .contracts import StrictModel

HISTORICAL_TWO_HALF_SECONDS = 8378.199 + 8145.772


class MatchCost(StrictModel):
    allocatedCompute: float
    retainedStorage: float
    transfer: float
    modelApi: float
    retryOverhead: float
    reviewLabour: float
    fixedShare: float
    total: float
    currency: str = "USD"
    rateCardDate: str
    exportFpsEqualsInferenceFps: bool = False
    notes: list[str] = Field(default_factory=list)


def match_cost(
    *,
    allocated_compute: float,
    retained_storage: float = 0.0,
    transfer: float = 0.0,
    model_api: float = 0.0,
    retry_overhead: float = 0.0,
    review_labour: float = 0.0,
    fixed_share: float = 0.0,
    export_fps: float | None = None,
    inference_fps: float | None = None,
    rate_card_date: str | None = None,
) -> MatchCost:
    del export_fps
    total = round(
        allocated_compute + retained_storage + transfer + model_api + retry_overhead + review_labour + fixed_share,
        4,
    )
    return MatchCost(
        allocatedCompute=allocated_compute,
        retainedStorage=retained_storage,
        transfer=transfer,
        modelApi=model_api,
        retryOverhead=retry_overhead,
        reviewLabour=review_labour,
        fixedShare=fixed_share,
        total=total,
        rateCardDate=rate_card_date or date(2026, 9, 16).isoformat(),
        exportFpsEqualsInferenceFps=False,
        notes=[
            "Export fps is not an inference-cost measurement.",
            "Historical two-half times are diagnostics, not current billable duration.",
            f"Inference fps recorded as {inference_fps}." if inference_fps is not None else "Inference fps unknown.",
        ],
    )


def historical_capacity_seconds() -> dict[str, float | bool]:
    return {
        "seconds": round(HISTORICAL_TWO_HALF_SECONDS, 3),
        "billableCurrentSource": False,
        "exportFpsEqualsInferenceFps": False,
    }


def credit_allocation() -> dict[str, object]:
    return {
        "illustrativeUsd": 1200,
        "authorised": False,
        "accountBalance": None,
        "gpuCreditsDoNotPayForLabels": True,
        "notes": [
            "Illustrative experiment envelope, not a verified account balance or job authorisation.",
            "GPU credits do not pay for independent annotators, APIs, licences or cash-only services.",
        ],
        "lineItems": [
            {"name": "GA-15/16 fixtures", "usd": 180, "status": "software_only"},
            {"name": "GA-17 hardware", "usd": 120, "status": "deferred_no_gpu_proof"},
            {"name": "GA-18 native", "usd": 0, "status": "inert"},
        ],
    }
