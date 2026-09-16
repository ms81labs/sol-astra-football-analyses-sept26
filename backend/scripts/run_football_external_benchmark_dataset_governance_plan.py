from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guardrails_false,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_DESIGN_DIR_NAME = "football_external_benchmark_real_evaluation_design_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_dataset_governance_plan_v1"

BLOCKER_DESIGN_MISSING = "football_external_benchmark_real_evaluation_design_missing"
NEXT_DESIGN = "football_external_benchmark_real_evaluation_design"
NEXT_APPROVAL = "football_external_benchmark_real_evaluation_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "external_benchmark_dataset_governance_plan",
                "successCriteria": ["write storage, retention, credential, and execution-budget contracts"],
                "failureAdaptation": "If design truth is missing, route back to real-evaluation design.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "external_benchmark_dataset_governance_contract_repair",
                "successCriteria": ["repair only governance contract derivation"],
                "failureAdaptation": "If source contracts remain unsafe, keep execution approval blocked.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "external_benchmark_dataset_governance_blocker_summary",
                "successCriteria": ["write blocker truth and select exactly one next family"],
                "failureAdaptation": "Route to design, governance repair, or approval.",
            },
        ],
    }


def _design_ready(summary: dict[str, Any] | None, source_scope: dict[str, Any] | None, metric_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("realEvaluationDesignReady") is True
        and summary.get("realEvaluationExecutionReady") is False
        and int(summary.get("externalSourceCount") or 0) >= 2
        and guardrails_false(summary)
        and isinstance(source_scope, dict)
        and source_scope.get("sourceScopeMode") == "finite_bounded_design"
        and source_scope.get("selectedExternalSourceIds") == ["soccernet", "soccertrack"]
        and isinstance(metric_contract, dict)
        and metric_contract.get("metricFamilies") == ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"]
    )


def run_football_external_benchmark_dataset_governance_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    design_root = root / DEFAULT_DESIGN_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    design_summary = load_json(design_root / "real_evaluation_design_summary.json")
    source_scope = load_json(design_root / "real_evaluation_source_scope_contract.json")
    metric_contract = load_json(design_root / "real_evaluation_metric_contract.json")
    storage_estimate = load_json(design_root / "storage_budget_estimate.json") or {}
    ready = _design_ready(design_summary, source_scope, metric_contract)

    storage_budget_policy = {
        "schemaVersion": "external_benchmark_dataset_storage_budget_policy_v1",
        "generatedAt": utc_now_iso(),
        "sourceScopeMode": "finite_bounded_design",
        "selectedExternalSourceIds": ["soccernet", "soccertrack"],
        "currentRepoFootprintObserved": storage_estimate.get("currentRepoFootprintObserved") or "17G",
        "existingArtifactsOnlyUntilApproval": True,
        "additionalDownloadApproved": False,
        "fullDatasetDownloadApproved": False,
        "videoDownloadApproved": False,
        "normalMatchStorageMutationApproved": False,
        "maxAdditionalDownloadBytesBeforeApproval": 0,
        "largeArtifactRetentionRequiresExplicitPolicy": True,
    }
    retention_policy = {
        "schemaVersion": "external_benchmark_dataset_retention_policy_v1",
        "generatedAt": utc_now_iso(),
        "preserveGeneratedTruthArtifacts": True,
        "preserveCurrentVideoEvidence": True,
        "deleteCachesWithoutApproval": True,
        "deleteExternalFixturesWithoutApproval": False,
        "retentionReviewRequiredForArtifactsOverBytes": 1_000_000_000,
    }
    credential_policy = {
        "schemaVersion": "external_benchmark_credential_handling_policy_v1",
        "generatedAt": utc_now_iso(),
        "credentialPersistenceApproved": False,
        "allowedCredentialUse": "runtime_only_when_needed",
        "redactSecretsInArtifacts": True,
        "soccernetPasswordMayBeUsedFromUserProvidedRuntimeContext": True,
    }
    execution_budget_contract = {
        "schemaVersion": "external_benchmark_execution_budget_contract_v1",
        "generatedAt": utc_now_iso(),
        "boundedRealExecutionMayUseExistingArtifactsOnly": True,
        "newDownloadBudgetBytes": 0,
        "detectorEvaluationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }
    goal = ready
    primary_blocker = None if goal else BLOCKER_DESIGN_MISSING
    next_lever = NEXT_APPROVAL if goal else NEXT_DESIGN
    summary = {
        "batchName": "football_external_benchmark_dataset_governance_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "datasetGovernancePlanReady": goal,
        "realEvaluationExecutionApproved": False,
        "externalSourceCount": 2 if goal else 0,
        "selectedExternalSourceIds": ["soccernet", "soccertrack"] if goal else [],
        "storageBudgetPolicyReady": goal,
        "retentionPolicyReady": goal,
        "credentialPolicyReady": goal,
        "executionBudgetContractReady": goal,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Dataset governance is ready; approve a finite existing-artifact real evaluation next." if goal else "Real-evaluation design truth is missing or unsafe; rerun the design batch.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "design_missing", "selected": primary_blocker == BLOCKER_DESIGN_MISSING, "primaryBlocker": BLOCKER_DESIGN_MISSING, "nextRecommendedNextLever": NEXT_DESIGN},
            {"condition": "governance_ready", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_APPROVAL},
        ],
    }
    artifacts = {
        "storage_budget_policy.json": storage_budget_policy,
        "retention_policy.json": retention_policy,
        "credential_handling_policy.json": credential_policy,
        "execution_budget_contract.json": execution_budget_contract,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="dataset_governance_plan_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Football External Benchmark Dataset Governance Plan",
    )


def main() -> None:
    main_for("Write dataset governance before real benchmark execution approval.", run_football_external_benchmark_dataset_governance_plan)


if __name__ == "__main__":
    main()
