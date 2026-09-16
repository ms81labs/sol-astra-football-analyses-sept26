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
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_EXECUTION_DIR_NAME = "football_external_benchmark_bounded_real_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_real_report_and_product_binding_v1"

BLOCKER_EXECUTION_MISSING = "football_external_benchmark_bounded_real_execution_missing"
NEXT_EXECUTION = "football_external_benchmark_bounded_real_execution"
NEXT_FINISH_LINE = "video_to_analysis_finish_line_integration_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "external_benchmark_real_report_product_binding",
                "successCriteria": ["write report payload, markdown report, and product view model from bounded real rows"],
                "failureAdaptation": "If bounded execution truth is missing, route back to bounded real execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "external_benchmark_real_report_binding_repair",
                "successCriteria": ["repair only result-row to report/view-model mapping"],
                "failureAdaptation": "If rows still cannot be rendered, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "external_benchmark_real_report_blocker_summary",
                "successCriteria": ["write blocker truth and select exactly one next family"],
                "failureAdaptation": "Route to execution, binding repair, or finish-line integration.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, result_table: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("boundedRealEvaluationExecuted") is True
        and int(summary.get("realEvaluationResultRowCount") or 0) >= 2
        and isinstance(result_table, dict)
        and int(result_table.get("rowCount") or 0) >= 2
    )


def _markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# External Benchmark Real Evaluation Report",
        "",
        "This report binds the bounded existing-artifact real evaluation into the product lane.",
        "",
        "| Source | Frames | Events | Notes |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in rows:
        notes = row.get("sourceArtifactFamily") or "bounded artifact"
        lines.append(f"| {row.get('sourceId')} | {row.get('reportedFrameCount', 0)} | {row.get('eventCount', 0)} | {notes} |")
    lines.extend(
        [
            "",
            "Detector evaluation, training, promotion, runtime-default mutation, downloads, and normal match storage mutation were not executed in this batch.",
            "",
        ]
    )
    return "\n".join(lines)


def run_football_external_benchmark_real_report_and_product_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "bounded_real_execution_summary.json")
    result_table = load_json(execution_root / "bounded_real_result_table.json")
    ready = _execution_ready(execution_summary, result_table)
    rows = [row for row in (result_table or {}).get("rows") or [] if isinstance(row, dict)]
    report_payload = {
        "schemaVersion": "external_benchmark_real_report_payload_v1",
        "generatedAt": utc_now_iso(),
        "reportReady": ready,
        "sourceBatch": "football_external_benchmark_bounded_real_execution",
        "sourceCount": len(rows),
        "rows": rows,
        "metricFamilies": ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"],
        "detectorEvaluationIncluded": False,
        "trainingIncluded": False,
    }
    view_model = {
        "schemaVersion": "external_benchmark_real_product_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "External benchmark real evaluation",
        "subtitle": "Bounded existing-artifact benchmark report",
        "sourceCards": rows,
        "nextAction": NEXT_FINISH_LINE if ready else NEXT_EXECUTION,
    }
    route_contract = {
        "schemaVersion": "external_benchmark_real_report_product_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/external/benchmark/real-report",
        "htmlRoutePath": "/external/benchmark/real-report",
        "routeImplementationReady": False,
        "productBindingReady": ready,
    }
    primary_blocker = None if ready else BLOCKER_EXECUTION_MISSING
    next_lever = NEXT_FINISH_LINE if ready else NEXT_EXECUTION
    summary = {
        "batchName": "football_external_benchmark_real_report_and_product_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "realReportProductBindingReady": ready,
        "realReportReady": ready,
        "realReportRouteImplementationReady": False,
        "sourceCount": len(rows),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Real benchmark report and product binding are ready. Plan the video-to-analysis finish line next." if ready else "Bounded real execution truth is missing; execute the bounded real evaluation first.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "bounded_real_execution_missing", "selected": primary_blocker == BLOCKER_EXECUTION_MISSING, "primaryBlocker": BLOCKER_EXECUTION_MISSING, "nextRecommendedNextLever": NEXT_EXECUTION},
            {"condition": "real_report_product_binding_ready", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_FINISH_LINE},
        ],
    }
    artifacts = {
        "real_report_payload.json": report_payload,
        "real_product_view_model.json": view_model,
        "real_report_product_route_contract.json": route_contract,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    output = write_outcome(
        output_root=output_root,
        summary_filename="real_report_and_product_binding_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Football External Benchmark Real Report And Product Binding",
    )
    (output_root / "external_benchmark_real_report.md").write_text(_markdown(rows), encoding="utf-8")
    return output


def main() -> None:
    main_for("Bind bounded real benchmark results into report and product payloads.", run_football_external_benchmark_real_report_and_product_binding)


if __name__ == "__main__":
    main()
