"""Release rollback. Preserve artifacts; do not rewrite past trial outcomes."""

from __future__ import annotations

from typing import Any


def rollback_release(*, flag_name: str, affected_outputs: list[str] | None = None) -> dict[str, Any]:
    return {
        "flagName": flag_name,
        "flagReverted": True,
        "newJobsAdmitted": False,
        "artifactsPreserved": True,
        "staleOutputs": list(affected_outputs or []),
        "rewrotePastTrialOutcomes": False,
    }
