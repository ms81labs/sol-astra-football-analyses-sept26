"""One immutable billing view; terminal execution is not final settlement."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from .money import ZERO, total


@dataclass(frozen=True)
class AttemptBilling:
    settled: Decimal
    outstanding: Decimal
    unsettled: Decimal
    complete: bool
    uncertain: bool
    reasons: tuple[str, ...]


class CostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: int = 2
    currency: str
    authorisedBudget: float
    attemptCount: int
    settledTotal: float
    outstandingReserved: float
    unsettledTotal: float
    unsettledAttemptCount: int
    billingComplete: bool
    actualTotal: float | None
    reasonCodes: tuple[str, ...] = ()
    # Deprecated alias. It always includes both non-overlapping exposures.
    reservedTotal: float = Field(description="Deprecated: outstandingReserved + unsettledTotal")

    @classmethod
    def project(cls, *, currency: str, budget: Decimal, attempts: list[AttemptBilling]):
        settled = total(item.settled for item in attempts)
        outstanding = total(item.outstanding for item in attempts)
        unsettled = total(item.unsettled for item in attempts)
        complete = bool(attempts) and all(item.complete for item in attempts)
        reasons = {reason for item in attempts for reason in item.reasons}
        if not attempts:
            reasons.add("NO_BILLING_EVIDENCE")
        if settled + outstanding + unsettled > budget:
            reasons.add("BUDGET_BREACH")
        return cls(currency=currency, authorisedBudget=float(budget), attemptCount=len(attempts),
            settledTotal=float(settled), outstandingReserved=float(outstanding),
            unsettledTotal=float(unsettled), unsettledAttemptCount=sum(item.uncertain for item in attempts),
            billingComplete=complete, actualTotal=float(settled) if complete else None,
            reservedTotal=float(outstanding + unsettled), reasonCodes=tuple(sorted(reasons)))
