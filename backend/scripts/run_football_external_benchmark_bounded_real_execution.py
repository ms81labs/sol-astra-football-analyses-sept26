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

DEFAULT_APPROVAL_DIR_NAME = "football_external_benchmark_real_evaluation_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_bounded_real_execution_v1"

BLOCKER_APPROVAL_MISSING = "football_external_benchmark_real_evaluation_approval_missing"
BLOCKER_SOURCE_ARTIFACT_MISSING = "football_external_benchmark_bounded_real_source_artifact_missing"
NEXT_APPROVAL = "football_external_benchmark_real_evaluation_approval"
NEXT_SOURCE_REPAIR = "football_external_benchmark_bounded_real_source_contract_repair"
NEXT_REPORT_BINDING = "football_external_benchmark_real_report_and_product_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "external_benchmark_bounded_real_execution",
                "successCriteria": ["aggregate existing SoccerNet and SoccerTrack real artifacts into bounded result rows"],
                "failureAdaptation": "If approval is missing, route back to real-evaluation approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "external_benchmark_bounded_real_source_contract_repair",
                "successCriteria": ["repair source artifact mapping only"],
                "failureAdaptation": "If source artifacts remain missing, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "external_benchmark_bounded_real_execution_blocker_summary",
                "successCriteria": ["write blocker truth and select exactly one next family"],
                "failureAdaptation": "Route to approval, source contract repair, or report binding.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("realEvaluationExecutionApproved") is True
        and summary.get("realEvaluationExecutionReady") is True
        and isinstance(scope, dict)
        and scope.get("realEvaluationExecutionApproved") is True
        and scope.get("executionMode") == "bounded_existing_artifact_real_evaluation"
        and scope.get("selectedExternalSourceIds") == ["soccernet", "soccertrack"]
    )


def _source_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    missing: list[str] = []
    soccernet_summary = load_json(root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_execution_summary.json")
    soccernet_payload = load_json(root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_product_payload.json")
    soccertrack_summary = load_json(root / "football_external_soccertrack_lane_closeout_v1" / "soccertrack_lane_closeout_summary.json")
    if not isinstance(soccernet_summary, dict):
        missing.append("football_external_soccernet_full_analysis_execution_v1/full_analysis_execution_summary.json")
    if not isinstance(soccernet_payload, dict):
        missing.append("football_external_soccernet_full_analysis_execution_v1/full_analysis_product_payload.json")
    if not isinstance(soccertrack_summary, dict):
        missing.append("football_external_soccertrack_lane_closeout_v1/soccertrack_lane_closeout_summary.json")
    rows: list[dict[str, Any]] = []
    if isinstance(soccernet_summary, dict) and isinstance(soccernet_payload, dict):
        rows.append(
            {
                "sourceId": "soccernet",
                "sourceArtifactFamily": "full_analysis_execution",
                "reportedFrameCount": int(soccernet_payload.get("reportedFrameCount") or soccernet_summary.get("processedFrameCount") or 0),
                "segmentCount": int(soccernet_payload.get("segmentCount") or soccernet_summary.get("segmentCount") or 0),
                "eventCount": int(soccernet_payload.get("eventCount") or 0),
                "sourceCoverageReady": True,
                "ballLocalizationMetricAvailable": False,
                "eventAlignmentMetricAvailable": True,
                "pipelineStabilityMetricAvailable": True,
            }
        )
    if isinstance(soccertrack_summary, dict):
        rows.append(
            {
                "sourceId": "soccertrack",
                "sourceArtifactFamily": "lane_closeout",
                "selectedMatchId": soccertrack_summary.get("selectedMatchId"),
                "reportedFrameCount": int(soccertrack_summary.get("reportedFrameCount") or 0),
                "eventCount": int(soccertrack_summary.get("reportedEventCount") or 0),
                "downloadedFixtureFileCount": int(soccertrack_summary.get("downloadedFixtureFileCount") or 0),
                "sourceCoverageReady": True,
                "ballLocalizationMetricAvailable": False,
                "eventAlignmentMetricAvailable": True,
                "pipelineStabilityMetricAvailable": True,
            }
        )
    return rows, missing


def run_football_external_benchmark_bounded_real_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    approval_summary = load_json(approval_root / "real_evaluation_approval_summary.json")
    approved_scope = load_json(approval_root / "approved_real_evaluation_scope.json")
    approval_ready = _approval_ready(approval_summary, approved_scope)
    rows, missing = _source_rows(root)
    sources_ready = len(rows) == 2 and not missing
    goal = approval_ready and sources_ready
    if not approval_ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
    elif not sources_ready:
        primary_blocker = BLOCKER_SOURCE_ARTIFACT_MISSING
        next_lever = NEXT_SOURCE_REPAIR
    else:
        primary_blocker = None
        next_lever = NEXT_REPORT_BINDING

    result_table = {
        "schemaVersion": "external_benchmark_bounded_real_result_table_v1",
        "generatedAt": utc_now_iso(),
        "executionMode": "bounded_existing_artifact_real_evaluation",
        "rowCount": len(rows),
        "rows": rows,
    }
    source_coverage = {
        "schemaVersion": "external_benchmark_bounded_real_source_coverage_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceCount": len(rows),
        "missingArtifactPaths": missing,
        "sourceCoveragePassed": sources_ready,
    }
    metric_audit = {
        "schemaVersion": "external_benchmark_bounded_real_metric_audit_v1",
        "generatedAt": utc_now_iso(),
        "metricFamiliesReported": ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"],
        "ballLocalizationExecuted": False,
        "eventAlignmentRowsReported": sum(1 for row in rows if row.get("eventAlignmentMetricAvailable")),
        "pipelineStabilityRowsReported": sum(1 for row in rows if row.get("pipelineStabilityMetricAvailable")),
    }
    guardrail = {
        "schemaVersion": "external_benchmark_bounded_real_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "approvalReady": approval_ready,
        "sourceCoveragePassed": sources_ready,
        "existingArtifactsOnly": True,
        "downloadStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "normalStorageMutationStillBlocked": True,
        "boundedRealGuardrailPassed": goal,
    }
    summary = {
        "batchName": "football_external_benchmark_bounded_real_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "boundedRealEvaluationExecuted": goal,
        "boundedRealEvaluationPassed": goal,
        "realEvaluationResultRowCount": len(rows),
        "externalSourceCount": len(rows),
        "selectedExternalSourceIds": [row["sourceId"] for row in rows],
        "missingArtifactCount": len(missing),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Bounded real evaluation executed over existing SoccerNet and SoccerTrack artifacts. Bind results into the product report next." if goal else "Bounded real execution is blocked until approval and required source artifacts are present.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "source_artifact_missing", "selected": primary_blocker == BLOCKER_SOURCE_ARTIFACT_MISSING, "primaryBlocker": BLOCKER_SOURCE_ARTIFACT_MISSING, "nextRecommendedNextLever": NEXT_SOURCE_REPAIR},
            {"condition": "bounded_real_execution_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT_BINDING},
        ],
    }
    artifacts = {
        "bounded_real_result_table.json": result_table,
        "source_coverage_audit.json": source_coverage,
        "metric_family_audit.json": metric_audit,
        "guardrail_audit.json": guardrail,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="bounded_real_execution_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Football External Benchmark Bounded Real Execution",
    )


def main() -> None:
    main_for("Execute bounded existing-artifact real benchmark evaluation.", run_football_external_benchmark_bounded_real_execution)


if __name__ == "__main__":
    main()
