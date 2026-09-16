from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_PLAN_DIR_NAME = "video_to_analysis_source_pool_replenishment_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_source_pool_replenishment_approval_v1"

BLOCKER_PLAN_MISSING = "video_to_analysis_source_pool_replenishment_plan_missing"
BLOCKER_ACCESS_METADATA_MISSING = "video_to_analysis_source_pool_access_metadata_missing"
BLOCKER_STORAGE_BUDGET_NOT_READY = "video_to_analysis_source_pool_storage_budget_not_ready"
BLOCKER_GUARDRAIL_UNSAFE = "video_to_analysis_source_pool_guardrail_contract_unsafe"

NEXT_PLAN = "video_to_analysis_source_pool_replenishment_plan"
NEXT_DATASET_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_STORAGE_CLEANUP_MAP = "video_to_analysis_source_and_artifact_cleanup_map"
NEXT_PLAN_REFRESH = "video_to_analysis_real_video_scaleout_plan_refresh"

REQUIRED_APPROVED_CASE_COUNT = 5


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "source_pool_replenishment_approval",
                "successCriteria": [
                    "fresh source candidate count >= 5",
                    "approved bounded scaleout case count >= 5",
                    "missing evidence count = 0",
                    "storage budget policy passed",
                    "download, training, promotion, runtime-default, and normal match storage mutation remain blocked",
                ],
                "failureAdaptation": "If the plan is missing or unsafe, route back to the plan or metadata repair.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "source_pool_approval_scope_repair",
                "successCriteria": ["repair only approval metadata or source evidence references"],
                "failureAdaptation": "Do not download, extract, train, promote, or mutate runtime defaults.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "source_pool_approval_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary if approval cannot stay bounded.",
            },
        ],
    }


def _rel(path: Path, storage_root: Path) -> str:
    return path.relative_to(storage_root).as_posix()


def _approval_cases(
    candidates: list[dict[str, Any]],
    *,
    approval_artifact_path: str,
) -> list[dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    for row in candidates:
        approved.append(
            {
                "id": str(row["candidateSourceId"]),
                "candidateSourceId": str(row["candidateSourceId"]),
                "sourceFamily": str(row["sourceFamily"]),
                "sourceLabel": str(row.get("sourceLabel") or row["candidateSourceId"]),
                "executionMode": "bounded_existing_or_approved_sample_only",
                "evidenceBasis": str(row.get("evidenceBasis") or "existing_artifact"),
                "expectedArtifactPaths": list(row.get("expectedArtifactPaths", [])),
                "approvalArtifactPath": approval_artifact_path,
                "downloadRequired": False,
                "downloadApprovalRequired": bool(row.get("downloadApprovalRequired") is True),
                "trainingEligible": False,
                "runtimeMutationEligible": False,
                "promotionMutationEligible": False,
                "normalMatchStorageMutationEligible": False,
            }
        )
    return approved


def _decision(
    *,
    condition: str,
    selected: bool,
    primary_blocker: str | None,
    next_lever: str,
) -> dict[str, Any]:
    return {
        "condition": condition,
        "selected": selected,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
    }


def _resolve_decision(
    *,
    plan_ready: bool,
    missing_evidence_count: int,
    storage_budget_passed: bool,
    guardrail_ready: bool,
    approved_case_count: int,
) -> tuple[bool, str | None, str, str]:
    if not plan_ready:
        return (
            False,
            BLOCKER_PLAN_MISSING,
            NEXT_PLAN,
            "Source-pool replenishment approval is blocked because the replenishment plan is missing or incomplete.",
        )
    if missing_evidence_count:
        return (
            False,
            BLOCKER_ACCESS_METADATA_MISSING,
            NEXT_DATASET_ACCESS_REVIEW,
            "Source-pool replenishment approval is blocked because source evidence or access metadata is missing.",
        )
    if not storage_budget_passed:
        return (
            False,
            BLOCKER_STORAGE_BUDGET_NOT_READY,
            NEXT_STORAGE_CLEANUP_MAP,
            "Source-pool replenishment approval is blocked because storage budget preflight did not pass.",
        )
    if not guardrail_ready or approved_case_count < REQUIRED_APPROVED_CASE_COUNT:
        return (
            False,
            BLOCKER_GUARDRAIL_UNSAFE,
            NEXT_PLAN,
            "Source-pool replenishment approval is blocked because the guardrail contract or approved case count is unsafe.",
        )
    return (
        True,
        None,
        NEXT_PLAN_REFRESH,
        "Bounded source pool replenishment is approved. Refresh the real-video scaleout plan next.",
    )


def run_video_to_analysis_source_pool_replenishment_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    plan_root = latest_versioned_dir(
        root,
        "video_to_analysis_source_pool_replenishment_plan",
        DEFAULT_PLAN_DIR_NAME,
    )
    output_root = reset_output(root, output_dir_name)
    approval_artifact_path = _rel(output_root / "source_pool_replenishment_approval_contract.json", storage_root)

    plan_summary = load_json(plan_root / "source_pool_replenishment_summary.json")
    bounded_plan = load_json(plan_root / "bounded_sample_replenishment_plan.json")
    guardrail_contract = load_json(plan_root / "source_access_guardrail_contract.json")
    storage_preflight = load_json(plan_root / "storage_budget_preflight_plan.json")

    raw_candidates = (
        bounded_plan.get("plannedFreshSourceCandidates", [])
        if isinstance(bounded_plan, dict)
        else []
    )
    candidates = [row for row in raw_candidates if isinstance(row, dict)]
    plan_ready = bool(
        plan_root.exists()
        and isinstance(plan_summary, dict)
        and plan_summary.get("goalAchieved") is True
        and plan_summary.get("sourcePoolReplenishmentPlanReady") is True
        and isinstance(bounded_plan, dict)
        and bounded_plan.get("plannedFreshSourceCandidateCount", 0) >= REQUIRED_APPROVED_CASE_COUNT
    )
    missing_evidence_count = int(
        (bounded_plan or {}).get("missingEvidenceCount", 0)
        if isinstance(bounded_plan, dict)
        else 0
    )
    storage_budget_passed = bool(
        isinstance(storage_preflight, dict)
        and storage_preflight.get("storageBudgetPolicyPassed") is True
    )
    guardrail_ready = bool(
        isinstance(guardrail_contract, dict)
        and guardrail_contract.get("sourceAccessGuardrailReady") is True
        and guardrail_contract.get("downloadExecutionApproved") is False
        and guardrail_contract.get("downloadExecutionExecuted") is False
        and guardrail_contract.get("trainingExecuted") is False
        and guardrail_contract.get("promotionMutationExecuted") is False
        and guardrail_contract.get("runtimeDefaultMutationExecuted") is False
        and guardrail_contract.get("normalMatchStorageMutationExecuted") is False
    )
    bounded_rows_safe = all(
        row.get("downloadRequired") is False
        and row.get("trainingEligible") is False
        and row.get("runtimeMutationEligible") is False
        and row.get("expectedArtifactPaths")
        and not row.get("missingEvidencePaths")
        for row in candidates
    )
    approved_cases = _approval_cases(candidates, approval_artifact_path=approval_artifact_path) if bounded_rows_safe else []
    goal, primary_blocker, next_lever, english = _resolve_decision(
        plan_ready=plan_ready,
        missing_evidence_count=missing_evidence_count,
        storage_budget_passed=storage_budget_passed,
        guardrail_ready=guardrail_ready and bounded_rows_safe,
        approved_case_count=len(approved_cases),
    )
    approved_cases = approved_cases if goal else []

    approved_pool = {
        "schemaVersion": "video_to_analysis_approved_bounded_source_pool_v1",
        "generatedAt": utc_now_iso(),
        "sourcePlanDir": plan_root.name if plan_root.exists() else None,
        "sourcePoolReplenishmentApproved": goal,
        "freshSourceCandidateCount": len(candidates) if goal else 0,
        "approvedBoundedScaleoutCases": approved_cases,
        "approvedBoundedScaleoutCaseCount": len(approved_cases),
        "missingEvidenceCount": missing_evidence_count,
        "storageBudgetPolicyPassed": storage_budget_passed,
        "downloadExecutionApproved": False,
        "downloadExecutionExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
    }
    contract = {
        "schemaVersion": "video_to_analysis_source_pool_replenishment_approval_contract_v1",
        "generatedAt": utc_now_iso(),
        "sourcePlanDir": plan_root.name if plan_root.exists() else None,
        "sourcePoolReplenishmentApproved": goal,
        "approvedExecutionMode": "bounded_existing_or_approved_sample_only" if goal else None,
        "approvedBoundedScaleoutCaseCount": len(approved_cases),
        "downloadExecutionApproved": False,
        "fullDatasetDownloadApproved": False,
        "archiveExtractionApproved": False,
        "trainingApproved": False,
        "promotionMutationApproved": False,
        "runtimeDefaultMutationApproved": False,
        "normalMatchStorageMutationApproved": False,
        "scaleoutExecutionRequiresPlanRefresh": True,
    }
    guardrail_audit = {
        "schemaVersion": "video_to_analysis_source_pool_approval_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "planReady": plan_ready,
        "boundedRowsSafe": bounded_rows_safe,
        "missingEvidenceCount": missing_evidence_count,
        "storageBudgetPolicyPassed": storage_budget_passed,
        "sourceAccessGuardrailReady": guardrail_ready,
        "downloadStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "normalMatchStorageMutationStillBlocked": True,
        "approvalGuardrailPassed": goal,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_source_pool_replenishment_approval",
        goal=goal,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "sourcePoolReplenishmentApproved": goal,
            "freshSourceCandidateCount": len(candidates) if goal else 0,
            "approvedBoundedScaleoutCaseCount": len(approved_cases),
            "missingEvidenceCount": missing_evidence_count,
            "storageBudgetPolicyPassed": storage_budget_passed,
            "downloadExecutionApproved": False,
            "downloadExecutionExecuted": False,
            "sourcePlanDir": plan_root.name if plan_root.exists() else None,
        },
    )
    summary.update(standard_false_flags())
    decision_matrix = {
        "schemaVersion": "video_to_analysis_source_pool_replenishment_approval_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "decisions": [
            _decision(
                condition="source_pool_replenishment_plan_missing",
                selected=not plan_ready,
                primary_blocker=BLOCKER_PLAN_MISSING,
                next_lever=NEXT_PLAN,
            ),
            _decision(
                condition="source_access_metadata_missing",
                selected=plan_ready and missing_evidence_count > 0,
                primary_blocker=BLOCKER_ACCESS_METADATA_MISSING,
                next_lever=NEXT_DATASET_ACCESS_REVIEW,
            ),
            _decision(
                condition="storage_budget_not_ready",
                selected=plan_ready and missing_evidence_count == 0 and not storage_budget_passed,
                primary_blocker=BLOCKER_STORAGE_BUDGET_NOT_READY,
                next_lever=NEXT_STORAGE_CLEANUP_MAP,
            ),
            _decision(
                condition="guardrail_contract_unsafe",
                selected=plan_ready and missing_evidence_count == 0 and storage_budget_passed and not goal,
                primary_blocker=BLOCKER_GUARDRAIL_UNSAFE,
                next_lever=NEXT_PLAN,
            ),
            _decision(
                condition="source_pool_replenishment_approved",
                selected=goal,
                primary_blocker=None,
                next_lever=NEXT_PLAN_REFRESH,
            ),
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="source_pool_replenishment_approval_summary.json",
        summary=summary,
        artifacts={
            "source_pool_replenishment_approval_contract.json": contract,
            "approved_bounded_source_pool.json": approved_pool,
            "source_pool_approval_guardrail_audit.json": guardrail_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Source Pool Replenishment Approval",
    )


def main() -> None:
    main_for("Approve bounded video-to-analysis source-pool replenishment.", run_video_to_analysis_source_pool_replenishment_approval)


if __name__ == "__main__":
    main()
