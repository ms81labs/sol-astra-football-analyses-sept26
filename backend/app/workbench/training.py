"""GA-05.4 training pools. Locked evaluation labels never become fine-tuning material."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel

DataPool = Literal["operational_corrections", "training", "development_validation", "locked_evaluation"]


class Admission(StrictModel):
    admitted: bool
    sourcePool: DataPool
    destination: DataPool
    reasonCodes: list[str] = Field(default_factory=list)


def data_pools() -> tuple[DataPool, DataPool, DataPool, DataPool]:
    return ("operational_corrections", "training", "development_validation", "locked_evaluation")


def admit_example(item: dict[str, Any], *, source_pool: DataPool, destination: DataPool) -> Admission:
    reasons: list[str] = []
    if source_pool == "locked_evaluation":
        reasons.append("LOCKED_EVALUATION_ISOLATION")
    if item.get("rights") not in {"granted", "club_agreement"}:
        reasons.append("RIGHTS_UNCLEAR")
    return Admission(
        admitted=not reasons,
        sourcePool=source_pool,
        destination=destination,
        reasonCodes=reasons,
    )
