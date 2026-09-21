from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_GOVERNANCE_DIR_NAME = "football_external_benchmark_dataset_governance_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_real_evaluation_approval_v1"

BLOCKER_GOVERNANCE_MISSING = "football_external_benchmark_dataset_governance_missing"
NEXT_GOVERNANCE = "football_external_benchmark_dataset_governance_plan"
NEXT_BOUNDED_REAL_EXECUTION = "football_external_benchmark_bounded_real_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "external_benchmark_real_evaluation_approval",
                "successCriteria": ["approve only existing-artifact bounded real evaluation"],
                "failureAdaptation": "If governance truth is missing, route back to dataset governance.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "external_benchmark_real_evaluation_approval_scope_repair",
                "successCriteria": ["repair finite source and budget scope only"],
                "failureAdaptation": "If scope cannot stay bounded, keep execution blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "external_benchmark_real_evaluation_approval_blocker_summary",
                "successCriteria": ["write blocker truth and select exactly one next family"],
                "failureAdaptation": "Route to governance, approval repair, or bounded real execution.",
            },
        ],
    }


def _governance_ready(summary: dict[str, Any] | None, execution_budget: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("datasetGovernancePlanReady") is True
        and summary.get("storageBudgetPolicyReady") is True
        and summary.get("retentionPolicyReady") is True
        and summary.get("credentialPolicyReady") is True
        and summary.get("executionBudgetContractReady") is True
        and isinstance(execution_budget, dict)
        and execution_budget.get("boundedRealExecutionMayUseExistingArtifactsOnly") is True
        and execution_budget.get("newDownloadBudgetBytes") == 0
        and execution_budget.get("trainingAllowed") is False
        and execution_budget.get("promotionAllowed") is False
        and execution_budget.get("runtimeDefaultMutationAllowed") is False
    )


def run_football_external_benchmark_real_evaluation_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    governance_root = root / DEFAULT_GOVERNANCE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    governance_summary = load_json(governance_root / "dataset_governance_plan_summary.json")
    execution_budget = load_json(governance_root / "execution_budget_contract.json")
    ready = _governance_ready(governance_summary, execution_budget)

    approved_scope = {
        "schemaVersion": "external_benchmark_real_evaluation_approved_scope_v1",
        "generatedAt": utc_now_iso(),
        "realEvaluationExecutionApproved": ready,
        "executionMode": "bounded_existing_artifact_real_evaluation",
        "selectedExternalSourceIds": ["soccernet", "soccertrack"] if ready else [],
        "allowedInputRoots": [
            "football_external_soccernet_full_analysis_execution_v1",
            "football_external_soccertrack_lane_closeout_v1",
        ],
        "datasetDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "normalMatchStorageMutationAllowed": False,
        "detectorEvaluationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }
    guardrail = {
        "schemaVersion": "external_benchmark_real_evaluation_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "governanceReady": ready,
        "existingArtifactOnlyExecution": True,
        "downloadStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "approvalGuardrailPassed": ready,
    }
    primary_blocker = None if ready else BLOCKER_GOVERNANCE_MISSING
    next_lever = NEXT_BOUNDED_REAL_EXECUTION if ready else NEXT_GOVERNANCE
    summary = {
        "batchName": "football_external_benchmark_real_evaluation_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "realEvaluationExecutionApproved": ready,
        "realEvaluationExecutionReady": ready,
        "executionMode": "bounded_existing_artifact_real_evaluation" if ready else None,
        "approvedSourceIds": ["soccernet", "soccertrack"] if ready else [],
        "approvedSourceCount": 2 if ready else 0,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Bounded existing-artifact real evaluation is approved. Execute it next without downloads, training, promotion, or runtime mutation." if ready else "Dataset governance truth is missing or unsafe; rerun governance before approval.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "governance_missing", "selected": primary_blocker == BLOCKER_GOVERNANCE_MISSING, "primaryBlocker": BLOCKER_GOVERNANCE_MISSING, "nextRecommendedNextLever": NEXT_GOVERNANCE},
            {"condition": "bounded_real_execution_approved", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BOUNDED_REAL_EXECUTION},
        ],
    }
    artifacts = {
        "approved_real_evaluation_scope.json": approved_scope,
        "approval_guardrail_audit.json": guardrail,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="real_evaluation_approval_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Football External Benchmark Real Evaluation Approval",
    )


def main() -> None:
    main_for("Approve bounded existing-artifact real benchmark execution.", run_football_external_benchmark_real_evaluation_approval)


if __name__ == "__main__":
    main()
