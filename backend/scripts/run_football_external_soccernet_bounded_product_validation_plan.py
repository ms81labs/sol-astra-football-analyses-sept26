from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

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

DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_bounded_product_validation_plan_v1"
DEFAULT_DOCS_ROOT = REPO_ROOT / "docs"

NEXT_EXECUTION_APPROVAL = "football_external_soccernet_bounded_product_validation_execution_approval"
NEXT_INVENTORY_REPAIR = "football_external_soccernet_existing_artifact_inventory_repair"
NEXT_GOVERNANCE_REPAIR = "football_external_soccernet_source_governance_repair"
NEXT_STORAGE_BUDGET_REPAIR = "football_external_soccernet_storage_budget_repair"
NEXT_SLICE_REPAIR = "football_external_soccernet_product_validation_slice_repair"

BLOCKER_INVENTORY_GAP = "soccernet_existing_artifact_inventory_gap"
BLOCKER_GOVERNANCE_GAP = "soccernet_source_governance_gap"
BLOCKER_STORAGE_BUDGET_GAP = "soccernet_storage_budget_gap"
BLOCKER_SLICE_GAP = "soccernet_product_validation_slice_gap"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_bounded_product_validation_plan",
                "successCriteria": [
                    "reuse existing SoccerNet/external artifacts",
                    "keep bulk downloads blocked",
                    "define at least three product validation slices",
                    "preserve training/promotion/runtime/download guardrails",
                ],
                "failureAdaptation": "If all inputs exist, write a bounded product validation plan and approval next lever.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_source_inventory_repair",
                "successCriteria": ["repair only artifact inventory references from existing local truth"],
                "failureAdaptation": "If inventory or governance is incomplete, route to the exact repair family.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_validation_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop without download, training, promotion, runtime mutation, or normal storage mutation.",
            },
        ],
    }


def _ready(summary: dict[str, Any] | None, flag: str | None = None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and (flag is None or summary.get(flag) is True)
        and _no_guardrail_true(summary)
    )


def _no_guardrail_true(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    return all(summary.get(key) is not True for key in standard_false_flags())


def _artifact_rows(root: Path) -> list[dict[str, Any]]:
    specs = [
        {
            "artifactId": "external_real_report_product_binding",
            "path": root
            / "football_external_benchmark_real_report_and_product_binding_v1"
            / "real_report_and_product_binding_summary.json",
            "flag": None,
        },
        {
            "artifactId": "soccernet_analysis_product_lane_closeout",
            "path": root
            / "football_external_soccernet_analysis_product_lane_closeout_v1"
            / "analysis_product_lane_closeout_summary.json",
            "flag": "analysisProductLaneClosed",
        },
        {
            "artifactId": "soccernet_full_analysis_lane_closeout",
            "path": root
            / "football_external_soccernet_full_analysis_lane_closeout_v1"
            / "full_analysis_lane_closeout_summary.json",
            "flag": "fullAnalysisLaneClosed",
        },
        {
            "artifactId": "soccernet_video_analysis_dry_run",
            "path": root / "football_external_soccernet_video_analysis_dry_run_v1" / "video_analysis_dry_run_summary.json",
            "flag": None,
        },
        {
            "artifactId": "soccernet_dry_run_product_bridge_smoke",
            "path": root
            / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
            / "dry_run_product_bridge_smoke_summary.json",
            "flag": "productBridgeSmokePassed",
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        summary = load_json(spec["path"])
        rows.append(
            {
                "artifactId": spec["artifactId"],
                "path": str(spec["path"]),
                "exists": spec["path"].exists(),
                "ready": _ready(summary, spec["flag"]),
                "guardrailsPreserved": _no_guardrail_true(summary),
                "goalAchieved": summary.get("goalAchieved") if isinstance(summary, dict) else None,
                "primaryBlocker": summary.get("primaryBlocker") if isinstance(summary, dict) else None,
            }
        )
    return rows


def _docs_signal(docs_root: Path) -> dict[str, Any]:
    path = Path(docs_root) / "foot-soccer-deepresearch.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    terms = ["SoccerNet", "calibration", "tracking", "ball", "game_state", "pitch"]
    return {
        "path": str(path),
        "exists": path.exists(),
        "matchedResearchTerms": [term for term in terms if term.lower() in text.lower()],
        "researchContextReady": path.exists() and "soccernet" in text.lower(),
    }


def _validation_slices(research: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sliceId": "soccernet_dry_run_product_bridge",
            "purpose": "Validate that existing SoccerNet dry-run frame payloads still bridge into product-facing analysis output.",
            "sourceArtifacts": [
                "football_external_soccernet_video_analysis_dry_run_v1",
                "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1",
            ],
            "executionRequiresApproval": True,
        },
        {
            "sliceId": "soccernet_full_analysis_product_lane",
            "purpose": "Validate route/product readiness from the existing SoccerNet full-analysis lane closeout.",
            "sourceArtifacts": [
                "football_external_soccernet_full_analysis_lane_closeout_v1",
                "football_external_soccernet_analysis_product_lane_closeout_v1",
            ],
            "executionRequiresApproval": True,
        },
        {
            "sliceId": "external_benchmark_report_product_binding",
            "purpose": "Validate the external benchmark product report binding as the cross-source credibility surface.",
            "sourceArtifacts": ["football_external_benchmark_real_report_and_product_binding_v1"],
            "executionRequiresApproval": True,
        },
        {
            "sliceId": "research_game_state_gap_probe",
            "purpose": "Map research recommendations into product gaps for calibration, tracking, pitch coordinates, and game-state output.",
            "sourceArtifacts": [research["path"]],
            "executionRequiresApproval": False,
        },
    ]


def run_football_external_soccernet_bounded_product_validation_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    docs_root: Path = DEFAULT_DOCS_ROOT,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)

    artifact_rows = _artifact_rows(root)
    ready_count = sum(1 for row in artifact_rows if row["ready"])
    guardrails_ok = all(row["guardrailsPreserved"] for row in artifact_rows if row["exists"])
    inventory_ready = ready_count >= 4
    research = _docs_signal(Path(docs_root))
    slices = _validation_slices(research)
    product_slice_count = len(slices)
    source_governance_ready = bool(inventory_ready and guardrails_ok and research["researchContextReady"])
    total, used, free = shutil.disk_usage(root if root.exists() else Path(storage_root))
    free_gb = free / (1024**3)
    storage_budget_ready = free_gb >= 10.0

    if not inventory_ready:
        goal = False
        primary_blocker = BLOCKER_INVENTORY_GAP
        next_lever = NEXT_INVENTORY_REPAIR
        english = "Existing SoccerNet/product artifacts are insufficient; rebuild the local artifact inventory before validation planning."
    elif not source_governance_ready:
        goal = False
        primary_blocker = BLOCKER_GOVERNANCE_GAP
        next_lever = NEXT_GOVERNANCE_REPAIR
        english = "SoccerNet source governance is incomplete or a guardrail violation was detected; repair governance before validation."
    elif not storage_budget_ready:
        goal = False
        primary_blocker = BLOCKER_STORAGE_BUDGET_GAP
        next_lever = NEXT_STORAGE_BUDGET_REPAIR
        english = "Storage budget is not ready for bounded validation planning; repair storage budget before continuing."
    elif product_slice_count < 3:
        goal = False
        primary_blocker = BLOCKER_SLICE_GAP
        next_lever = NEXT_SLICE_REPAIR
        english = "Not enough product validation slices exist; repair the slice plan."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_EXECUTION_APPROVAL
        english = (
            "Bounded SoccerNet/external product validation plan is ready from existing artifacts. "
            "Advance to execution approval; do not bulk-download, train, promote, or mutate runtime defaults."
        )

    inventory = {
        "schemaVersion": "soccernet_existing_artifact_inventory_v1",
        "generatedAt": utc_now_iso(),
        "existingArtifactReusePlanned": inventory_ready,
        "readyArtifactCount": ready_count,
        "requiredReadyArtifactCount": 4,
        "artifactRows": artifact_rows,
    }
    governance = {
        "schemaVersion": "soccernet_source_governance_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceGovernanceReady": source_governance_ready,
        "bulkDownloadAllowed": False,
        "bulkDownloadPlanned": False,
        "additionalVideoDownloadAllowedWithoutApproval": False,
        "additionalDataDownloadAllowedWithoutApproval": False,
        "researchContext": research,
        "allInputGuardrailsPreserved": guardrails_ok,
    }
    storage_budget = {
        "schemaVersion": "soccernet_storage_budget_audit_v1",
        "generatedAt": utc_now_iso(),
        "storageBudgetReady": storage_budget_ready,
        "diskTotalBytes": total,
        "diskUsedBytes": used,
        "diskFreeBytes": free,
        "diskFreeGb": round(free_gb, 3),
        "minimumFreeGbForBoundedValidationPlan": 10.0,
        "bulkDownloadPlanned": False,
    }
    validation_plan = {
        "schemaVersion": "soccernet_bounded_product_validation_plan_v1",
        "generatedAt": utc_now_iso(),
        "sourceMode": "existing_artifact_reuse_only",
        "bulkDownloadPlanned": False,
        "executionApproved": False,
        "executionApprovalRequiredBefore": NEXT_EXECUTION_APPROVAL,
        "productValidationSlices": slices,
        "expectedExecutionBoundary": {
            "trainingAllowed": False,
            "promotionMutationAllowed": False,
            "runtimeDefaultMutationAllowed": False,
            "bulkDownloadAllowed": False,
            "normalMatchStorageMutationAllowed": False,
        },
    }
    gap_matrix = {
        "schemaVersion": "soccernet_product_gap_matrix_v1",
        "generatedAt": utc_now_iso(),
        "currentV72RuntimeScopePreserved": True,
        "currentProductGaps": [
            {
                "gapId": "metric_pitch_coordinates_not_canonical",
                "researchSignal": "pitch coordinates and game_state output",
                "blocksCurrentValidationPlan": False,
            },
            {
                "gapId": "calibration_tracking_event_stack_future_lane",
                "researchSignal": "calibration, tracking, ball actions",
                "blocksCurrentValidationPlan": False,
            },
            {
                "gapId": "bounded_soccernet_product_validation_not_executed_yet",
                "researchSignal": "external benchmark confidence",
                "blocksCurrentValidationPlan": False,
                "nextLever": NEXT_EXECUTION_APPROVAL,
            },
        ],
    }
    decision_matrix = {
        "schemaVersion": "soccernet_bounded_product_validation_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "existing_artifact_inventory_gap",
                "selected": primary_blocker == BLOCKER_INVENTORY_GAP,
                "primaryBlocker": BLOCKER_INVENTORY_GAP,
                "nextRecommendedNextLever": NEXT_INVENTORY_REPAIR,
            },
            {
                "condition": "source_governance_gap",
                "selected": primary_blocker == BLOCKER_GOVERNANCE_GAP,
                "primaryBlocker": BLOCKER_GOVERNANCE_GAP,
                "nextRecommendedNextLever": NEXT_GOVERNANCE_REPAIR,
            },
            {
                "condition": "storage_budget_gap",
                "selected": primary_blocker == BLOCKER_STORAGE_BUDGET_GAP,
                "primaryBlocker": BLOCKER_STORAGE_BUDGET_GAP,
                "nextRecommendedNextLever": NEXT_STORAGE_BUDGET_REPAIR,
            },
            {
                "condition": "bounded_product_validation_plan_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_EXECUTION_APPROVAL,
            },
        ],
    }
    summary = {
        "batchName": "football_external_soccernet_bounded_product_validation_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "existingArtifactReusePlanned": inventory_ready,
        "readyArtifactCount": ready_count,
        "sourceGovernanceReady": source_governance_ready,
        "storageBudgetReady": storage_budget_ready,
        "productValidationSlices": product_slice_count,
        "bulkDownloadPlanned": False,
        "executionApproved": False,
        "executionApprovalRequired": True,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_bounded_product_validation_plan_summary.json",
        summary=summary,
        artifacts={
            "soccernet_bounded_product_validation_plan.json": validation_plan,
            "soccernet_source_governance_audit.json": governance,
            "soccernet_existing_artifact_inventory.json": inventory,
            "soccernet_storage_budget_audit.json": storage_budget,
            "soccernet_product_gap_matrix.json": gap_matrix,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Bounded Product Validation Plan",
    )


def main() -> None:
    main_for(
        "Plan bounded SoccerNet/external product validation from existing artifacts.",
        run_football_external_soccernet_bounded_product_validation_plan,
    )


if __name__ == "__main__":
    main()
