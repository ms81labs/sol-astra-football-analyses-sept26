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

DEFAULT_REPORT_DIR_NAME = "football_external_benchmark_real_report_and_product_binding_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_integration_plan_v1"

BLOCKER_REPORT_BINDING_MISSING = "football_external_benchmark_real_report_product_binding_missing"
NEXT_REPORT_BINDING = "football_external_benchmark_real_report_and_product_binding"
NEXT_EXECUTION_APPROVAL = "video_to_analysis_finish_line_execution_approval"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_finish_line_integration_plan",
                "successCriteria": ["write the product finish-line integration map from benchmark evidence"],
                "failureAdaptation": "If real report binding is missing, route back to report binding.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "video_to_analysis_finish_line_contract_repair",
                "successCriteria": ["repair only integration contracts and stage mapping"],
                "failureAdaptation": "If finish-line scope is still unclear, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "video_to_analysis_finish_line_blocker_summary",
                "successCriteria": ["write blocker truth and select exactly one next family"],
                "failureAdaptation": "Route to report binding, contract repair, or execution approval.",
            },
        ],
    }


def _report_ready(summary: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("realReportProductBindingReady") is True
        and isinstance(payload, dict)
        and payload.get("reportReady") is True
        and int(payload.get("sourceCount") or 0) >= 2
    )


def run_video_to_analysis_finish_line_integration_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    report_root = root / DEFAULT_REPORT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    report_summary = load_json(report_root / "real_report_and_product_binding_summary.json")
    report_payload = load_json(report_root / "real_report_payload.json")
    ready = _report_ready(report_summary, report_payload)
    integration_map = {
        "schemaVersion": "video_to_analysis_finish_line_integration_map_v1",
        "generatedAt": utc_now_iso(),
        "finishLineIntegrationPlanReady": ready,
        "sourceReportBatch": "football_external_benchmark_real_report_and_product_binding",
        "productGoal": "turn video inputs into auditable match analysis data and product-facing reports",
        "integrationStages": [
            {"stageId": "source_governance", "status": "ready", "nextLever": "football_external_benchmark_dataset_governance_plan"},
            {"stageId": "bounded_real_evaluation", "status": "ready", "nextLever": "football_external_benchmark_bounded_real_execution"},
            {"stageId": "report_product_binding", "status": "ready", "nextLever": "football_external_benchmark_real_report_and_product_binding"},
            {"stageId": "finish_line_execution_approval", "status": "next", "nextLever": NEXT_EXECUTION_APPROVAL},
        ],
    }
    execution_readiness = {
        "schemaVersion": "video_to_analysis_finish_line_execution_readiness_v1",
        "generatedAt": utc_now_iso(),
        "executionApprovalReady": ready,
        "requiresHumanApprovalBeforeNormalRuntimeMutation": True,
        "requiresNoPromotionBoundary": True,
        "requiresRunPodHygieneCheck": True,
        "recommendedNextLever": NEXT_EXECUTION_APPROVAL if ready else NEXT_REPORT_BINDING,
    }
    risk_register = {
        "schemaVersion": "video_to_analysis_finish_line_risk_register_v1",
        "generatedAt": utc_now_iso(),
        "risks": [
            {"riskId": "storage_growth_without_retention_policy", "mitigation": "dataset governance contract is now required before downloads"},
            {"riskId": "benchmark_truth_mistaken_for_promotion_truth", "mitigation": "candidate evaluation and promotion flags remain false"},
            {"riskId": "product_path_diverges_from_generated_truth", "mitigation": "route/report bindings must read generated truth artifacts"},
        ],
    }
    primary_blocker = None if ready else BLOCKER_REPORT_BINDING_MISSING
    next_lever = NEXT_EXECUTION_APPROVAL if ready else NEXT_REPORT_BINDING
    summary = {
        "batchName": "video_to_analysis_finish_line_integration_plan",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "finishLineIntegrationPlanReady": ready,
        "finishLineExecutionApprovalReady": ready,
        "sourceReportReady": ready,
        "productGoal": "video_to_auditable_match_analysis_data",
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "The video-to-analysis finish-line integration plan is ready. Next is explicit execution approval for the finish-line path." if ready else "Real report/product binding is missing; bind the real report first.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "report_binding_missing", "selected": primary_blocker == BLOCKER_REPORT_BINDING_MISSING, "primaryBlocker": BLOCKER_REPORT_BINDING_MISSING, "nextRecommendedNextLever": NEXT_REPORT_BINDING},
            {"condition": "finish_line_integration_ready", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EXECUTION_APPROVAL},
        ],
    }
    artifacts = {
        "finish_line_integration_map.json": integration_map,
        "finish_line_execution_readiness.json": execution_readiness,
        "finish_line_risk_register.json": risk_register,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_integration_plan_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Video To Analysis Finish Line Integration Plan",
    )


def main() -> None:
    main_for("Plan finish-line integration from external benchmark report truth.", run_video_to_analysis_finish_line_integration_plan)


if __name__ == "__main__":
    main()
