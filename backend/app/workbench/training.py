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


class ExperimentLedger:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, item: dict[str, Any]) -> dict[str, Any]:
        recorded = {"seq": len(self.entries), **item}
        self.entries.append(recorded)
        return recorded


def experiment_ledger() -> ExperimentLedger:
    return ExperimentLedger()


def experiment_cycle(
    stage: str,
    *,
    measurable_failure: bool = True,
    budget_remaining: float = 1.0,
    development_benefit: bool = True,
    gate_regressed: bool = False,
) -> dict[str, Any]:
    proceed = True
    reason = "ok"
    if stage == "diagnose" and not measurable_failure:
        proceed, reason = False, "no_specific_measurable_failure"
    if stage == "train" and (budget_remaining <= 0 or not development_benefit):
        proceed, reason = False, "cost_cap_or_no_development_benefit"
    if stage == "validate" and gate_regressed:
        proceed, reason = False, "safety_or_coverage_gate_regressed"
    return {"stage": stage, "proceed": proceed, "reason": reason}


def pseudo_label(*, suggestion: str, human_change: str | None, approved: bool) -> dict[str, Any]:
    return {
        "suggestion": suggestion,
        "humanChange": human_change,
        "approved": approved,
        "independentGroundTruth": False,
    }


def sampling_policy() -> dict[str, Any]:
    return {
        "uncertaintyOnly": False,
        "mix": ["difficult", "random_representative"],
        "trackPolicy": True,
    }


def drill_library() -> dict[str, Any]:
    return {
        "items": [{"name": "near-side recovery 2v2", "coachReviewed": True}],
        "prescribesMedicalLoad": False,
        "diagnosesFatigueOrInjury": False,
    }


def promote_candidate(*, independent_accepted: bool, rollback_artifact: bool) -> dict[str, Any]:
    return {
        "promoted": bool(independent_accepted and rollback_artifact),
        "rollbackArtifact": rollback_artifact,
        "reasonCodes": [] if independent_accepted else ["INDEPENDENT_ACCEPTANCE_MISSING"],
    }
