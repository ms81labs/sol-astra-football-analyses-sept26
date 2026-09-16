"""8.2 delivery milestones. Planning estimates, not delivery commitments."""

from __future__ import annotations

from typing import Any


def milestone_plan() -> list[dict[str, Any]]:
    return [
        {"id": "M0", "deliverable": "baseline_dossier", "planningEstimateNotCommitment": True, "analystAccepted": False},
        {"id": "M1", "deliverable": "useful_manual_workbench", "planningEstimateNotCommitment": True, "analystAccepted": False, "llmRequired": False},
        {"id": "M2", "deliverable": "qualified_perception", "planningEstimateNotCommitment": True, "analystAccepted": False, "ga17MayRemainDeferred": True},
        {"id": "M3", "deliverable": "reliable_derived_analytics", "planningEstimateNotCommitment": True, "analystAccepted": False},
        {"id": "M4", "deliverable": "optional_ai_assistance", "planningEstimateNotCommitment": True, "analystAccepted": False},
        {"id": "M5", "deliverable": "deployment_hardening", "planningEstimateNotCommitment": True, "analystAccepted": False, "loopbackPilotSufficient": True},
    ]


def owners() -> dict[str, str]:
    return {
        "backend_media": "backend/media",
        "frontend": "frontend",
        "cv": "cv",
        "independent_evaluation": "independent_reviewer",
        "operations": "operations",
    }


def progress_signal(*, completed_analyst_tasks: int, validated_capability_gates: int, merged_files: int) -> dict[str, Any]:
    del merged_files
    return {
        "complete": completed_analyst_tasks > 0 and validated_capability_gates > 0,
        "completedAnalystTasks": completed_analyst_tasks,
        "validatedCapabilityGates": validated_capability_gates,
        "usesMergedFilesAsSuccess": False,
    }
