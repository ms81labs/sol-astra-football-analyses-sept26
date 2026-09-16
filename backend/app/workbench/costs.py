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


VARIABLE_TECHNICAL_PER_MATCH = 2.34
REVIEW_LABOUR_PER_MATCH = 10.0
FIXED_MONTHLY = 50.0


def scale_scenario(matches_per_month: int) -> dict[str, object]:
    variable = round(VARIABLE_TECHNICAL_PER_MATCH * matches_per_month, 2)
    labour = round(REVIEW_LABOUR_PER_MATCH * matches_per_month, 2)
    return {
        "matchesPerMonth": matches_per_month,
        "variableTechnical": variable,
        "reviewLabour": labour,
        "fixed": FIXED_MONTHLY,
        "totalIncludingFixed": round(variable + labour + FIXED_MONTHLY, 2),
        "measuredApplicationPerformance": False,
        "notes": [
            "Planning model, not measured application performance or a supplier quote.",
            "Review labour is a productivity target; present tracking quality may require more effort.",
        ],
    }


def decimal_gb_to_gib(decimal_gb: float) -> float:
    return (decimal_gb * 1_000_000_000) / (1024 ** 3)


def deployment_choice(
    *,
    privacy_required: bool,
    irregular_usage: bool,
    suitable_local_hardware: bool,
) -> dict[str, object]:
    if privacy_required or suitable_local_hardware and not irregular_usage:
        selected = "local"
    elif irregular_usage and not privacy_required:
        selected = "cloud_burst"
    else:
        selected = "reassess_after_pilot"
    return {
        "selected": selected,
        "alwaysOnGpuCommitted": False,
        "rule": "measured_workload_privacy_utilisation",
    }
