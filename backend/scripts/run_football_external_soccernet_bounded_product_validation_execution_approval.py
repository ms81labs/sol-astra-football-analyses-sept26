from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
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

DEFAULT_PLAN_DIR_NAME = "football_external_soccernet_bounded_product_validation_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_product_validation_execution_approval_v1"

BLOCKER_PLAN_MISSING = "football_external_soccernet_product_validation_plan_missing"
BLOCKER_GUARDRAIL_VIOLATION = "football_external_soccernet_product_validation_guardrail_violation"
BLOCKER_SCOPE_GAP = "football_external_soccernet_product_validation_scope_gap"

NEXT_PLAN = "football_external_soccernet_bounded_product_validation_plan"
NEXT_PLAN_REPAIR = "football_external_soccernet_bounded_product_validation_plan_repair"
NEXT_SCOPE_REPAIR = "football_external_soccernet_bounded_product_validation_scope_repair"
NEXT_EXECUTION = "football_external_soccernet_bounded_product_validation_execution"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_bounded_product_validation_execution_approval",
                "successCriteria": [
                    "approve only existing-artifact bounded product validation",
                    "approve all planned product validation slices",
                    "do not execute validation in this approval batch",
                    "keep bulk downloads, training, promotion, runtime mutation, and normal storage mutation blocked",
                ],
                "failureAdaptation": "If the plan is ready, write a non-executed approval contract for the next batch.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_product_validation_scope_repair",
                "successCriteria": ["repair only slice scope or plan references from existing local truth"],
                "failureAdaptation": "If guardrails fail, route to plan repair instead of execution.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_product_validation_approval_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before execution if approval is unsafe.",
            },
        ],
    }


def _summary_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("existingArtifactReusePlanned") is True
        and summary.get("sourceGovernanceReady") is True
        and summary.get("storageBudgetReady") is True
        and int(summary.get("productValidationSlices") or 0) >= 3
        and summary.get("executionApproved") is False
        and summary.get("executionApprovalRequired") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _plan_guardrails_ready(
    plan: dict[str, Any] | None,
    governance: dict[str, Any] | None,
    storage_budget: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
) -> bool:
    boundary = plan.get("expectedExecutionBoundary") if isinstance(plan, dict) else {}
    artifact_rows = inventory.get("artifactRows") if isinstance(inventory, dict) else []
    return bool(
        isinstance(plan, dict)
        and plan.get("schemaVersion") == "soccernet_bounded_product_validation_plan_v1"
        and plan.get("sourceMode") == "existing_artifact_reuse_only"
        and plan.get("bulkDownloadPlanned") is False
        and plan.get("executionApproved") is False
        and isinstance(plan.get("productValidationSlices"), list)
        and len(plan.get("productValidationSlices") or []) >= 3
        and isinstance(boundary, dict)
        and boundary.get("trainingAllowed") is False
        and boundary.get("promotionMutationAllowed") is False
        and boundary.get("runtimeDefaultMutationAllowed") is False
        and boundary.get("bulkDownloadAllowed") is False
        and boundary.get("normalMatchStorageMutationAllowed") is False
        and isinstance(governance, dict)
        and governance.get("sourceGovernanceReady") is True
        and governance.get("bulkDownloadAllowed") is False
        and governance.get("bulkDownloadPlanned") is False
        and governance.get("additionalVideoDownloadAllowedWithoutApproval") is False
        and governance.get("additionalDataDownloadAllowedWithoutApproval") is False
        and governance.get("allInputGuardrailsPreserved") is True
        and isinstance(storage_budget, dict)
        and storage_budget.get("storageBudgetReady") is True
        and storage_budget.get("bulkDownloadPlanned") is False
        and isinstance(inventory, dict)
        and inventory.get("existingArtifactReusePlanned") is True
        and int(inventory.get("readyArtifactCount") or 0) >= 4
        and isinstance(artifact_rows, list)
        and all(isinstance(row, dict) and row.get("ready") is True and row.get("guardrailsPreserved") is True for row in artifact_rows)
    )


def run_football_external_soccernet_bounded_product_validation_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    plan_dir_name: str = DEFAULT_PLAN_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    plan_root = root / plan_dir_name
    output_root = reset_output(root, output_dir_name)

    summary_in = load_json(plan_root / "soccernet_bounded_product_validation_plan_summary.json")
    plan = load_json(plan_root / "soccernet_bounded_product_validation_plan.json")
    governance = load_json(plan_root / "soccernet_source_governance_audit.json")
    storage_budget = load_json(plan_root / "soccernet_storage_budget_audit.json")
    inventory = load_json(plan_root / "soccernet_existing_artifact_inventory.json")

    summary_ready = _summary_ready(summary_in)
    guardrails_ready = _plan_guardrails_ready(plan, governance, storage_budget, inventory)
    slices = plan.get("productValidationSlices") if isinstance(plan, dict) and isinstance(plan.get("productValidationSlices"), list) else []
    approved_count = len(slices)

    if not summary_ready:
        goal = False
        primary_blocker = BLOCKER_PLAN_MISSING
        next_lever = NEXT_PLAN
        english = "SoccerNet bounded product validation plan is missing or not ready; rebuild the plan before approval."
    elif not guardrails_ready:
        goal = False
        primary_blocker = BLOCKER_GUARDRAIL_VIOLATION
        next_lever = NEXT_PLAN_REPAIR
        english = "SoccerNet validation plan guardrails are unsafe; repair the plan before approval."
    elif approved_count < 3:
        goal = False
        primary_blocker = BLOCKER_SCOPE_GAP
        next_lever = NEXT_SCOPE_REPAIR
        english = "SoccerNet product validation scope has too few slices; repair scope before approval."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        english = (
            "Bounded SoccerNet/external product validation execution is approved for the next batch only. "
            "Execution has not run; bulk downloads, training, promotion, runtime mutation, and normal storage mutation remain blocked."
        )

    approved_scope = {
        "schemaVersion": "soccernet_bounded_product_validation_approved_scope_v1",
        "generatedAt": utc_now_iso(),
        "sourcePlanBatch": "football_external_soccernet_bounded_product_validation_plan",
        "productValidationExecutionApproved": goal,
        "productValidationExecutionExecuted": False,
        "executionMode": "bounded_existing_artifact_product_validation",
        "approvedProductValidationSliceCount": approved_count if goal else 0,
        "approvedProductValidationSlices": slices if goal else [],
        "bulkDownloadApproved": False,
        "videoDownloadApproved": False,
        "dataDownloadApproved": False,
        "normalMatchStorageMutationApproved": False,
        "trainingApproved": False,
        "promotionApproved": False,
        "runtimeDefaultMutationApproved": False,
    }
    execution_contract = {
        "schemaVersion": "soccernet_bounded_product_validation_execution_contract_v1",
        "generatedAt": utc_now_iso(),
        "contractName": NEXT_EXECUTION,
        "sourceApprovalBatch": "football_external_soccernet_bounded_product_validation_execution_approval",
        "productValidationExecutionApproved": goal,
        "productValidationExecutionExecuted": False,
        "allowedOperations": [
            "read_existing_soccernet_product_artifacts",
            "validate_product_bridge_payloads",
            "validate_existing_route_bound_reports",
            "write_bounded_product_validation_artifacts",
        ]
        if goal
        else [],
        "disallowedOperations": [
            "bulk_soccernet_download",
            "new_video_download_without_approval",
            "new_data_download_without_approval",
            "training",
            "promotion",
            "runtime_default_mutation",
            "normal_match_storage_mutation",
        ],
    }
    guardrail = {
        "schemaVersion": "soccernet_bounded_product_validation_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "summaryReady": summary_ready,
        "planGuardrailsReady": guardrails_ready,
        "approvalGuardrailPassed": goal,
        "bulkDownloadApproved": False,
        "productValidationExecutionExecuted": False,
        **standard_false_flags(),
    }
    decision_matrix = {
        "schemaVersion": "soccernet_bounded_product_validation_execution_approval_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "plan_missing_or_not_ready",
                "selected": primary_blocker == BLOCKER_PLAN_MISSING,
                "primaryBlocker": BLOCKER_PLAN_MISSING,
                "nextRecommendedNextLever": NEXT_PLAN,
            },
            {
                "condition": "plan_guardrail_violation",
                "selected": primary_blocker == BLOCKER_GUARDRAIL_VIOLATION,
                "primaryBlocker": BLOCKER_GUARDRAIL_VIOLATION,
                "nextRecommendedNextLever": NEXT_PLAN_REPAIR,
            },
            {
                "condition": "scope_gap",
                "selected": primary_blocker == BLOCKER_SCOPE_GAP,
                "primaryBlocker": BLOCKER_SCOPE_GAP,
                "nextRecommendedNextLever": NEXT_SCOPE_REPAIR,
            },
            {
                "condition": "bounded_product_validation_execution_approved",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_EXECUTION,
            },
        ],
    }
    summary = {
        "batchName": "football_external_soccernet_bounded_product_validation_execution_approval",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "productValidationExecutionApproved": goal,
        "productValidationExecutionExecuted": False,
        "approvedProductValidationSliceCount": approved_count if goal else 0,
        "executionMode": "bounded_existing_artifact_product_validation" if goal else None,
        "bulkDownloadApproved": False,
        "videoDownloadApproved": False,
        "dataDownloadApproved": False,
        "normalMatchStorageMutationApproved": False,
        "trainingApproved": False,
        "promotionApproved": False,
        "runtimeDefaultMutationApproved": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_bounded_product_validation_execution_approval_summary.json",
        summary=summary,
        artifacts={
            "approved_product_validation_scope.json": approved_scope,
            "product_validation_execution_contract.json": execution_contract,
            "approval_guardrail_audit.json": guardrail,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Bounded Product Validation Execution Approval",
    )


def main() -> None:
    main_for(
        "Approve bounded SoccerNet/external product validation execution.",
        run_football_external_soccernet_bounded_product_validation_execution_approval,
    )


if __name__ == "__main__":
    main()
