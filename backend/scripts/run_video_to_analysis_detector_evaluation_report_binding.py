from __future__ import annotations

from html import escape
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

DEFAULT_EXECUTION_DIR_NAME = "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_report_binding_v1"

BLOCKER_EXECUTION_MISSING = "video_to_analysis_detector_evaluation_bounded_execution_missing"
NEXT_EXECUTION = "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution"
NEXT_ROUTE_BINDING = "video_to_analysis_detector_evaluation_report_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "detector_evaluation_report_binding",
                "successCriteria": ["bind bounded detector metrics to a stable report view model"],
                "failureAdaptation": "If execution truth is missing, route back to bounded artifact execution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "detector_evaluation_report_contract_repair",
                "successCriteria": ["repair only report view model and route contract"],
                "failureAdaptation": "If report contract remains invalid, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "detector_evaluation_report_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to execution, contract repair, or route binding.",
            },
        ],
    }


def _execution_ready(summary: dict[str, Any] | None, metrics: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("detectorEvaluationExecuted") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(metrics, dict)
        and metrics.get("boundedValPositiveLocalizationHitRate") is not None
        and metrics.get("sourceFrameLocalizationHitRate") is not None
        and metrics.get("precisionGuardrailPassed") is True
    )


def _view_model(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_detector_evaluation_report_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Detector Evaluation Report",
        "detectorEvaluationMode": "bounded_existing_v7_2_artifact_detector_evaluation",
        "activeRuntimeDefaultVersion": "v7.3",
        "runtimeDefaultRolloutClosed": True,
        "headlineMetrics": {
            "boundedValPositiveLocalizationHitRate": metrics.get("boundedValPositiveLocalizationHitRate"),
            "sourceFrameLocalizationHitRate": metrics.get("sourceFrameLocalizationHitRate"),
            "precisionGuardrailPassed": metrics.get("precisionGuardrailPassed"),
        },
        "guardrails": {
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": True,
            "candidateReadyForEvaluation": False,
        },
        "nextRecommendedNextLever": NEXT_ROUTE_BINDING,
    }


def _render_html(view_model: dict[str, Any]) -> str:
    metrics = view_model.get("headlineMetrics") if isinstance(view_model.get("headlineMetrics"), dict) else {}
    items = "\n".join(f"<li>{escape(str(key))}: {escape(str(value))}</li>" for key, value in metrics.items())
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Detector Evaluation Report</title></head>",
            "<body>",
            "<h1>Detector Evaluation Report</h1>",
            f"<p>Mode: {escape(str(view_model.get('detectorEvaluationMode')))}</p>",
            f"<ul>{items}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


def run_video_to_analysis_detector_evaluation_report_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    execution_root = root / DEFAULT_EXECUTION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    execution_summary = load_json(execution_root / "detector_evaluation_bounded_existing_artifact_execution_summary.json")
    metrics = load_json(execution_root / "detector_evaluation_metric_snapshot.json")
    ready = _execution_ready(execution_summary, metrics)

    if ready and isinstance(metrics, dict):
        primary_blocker = None
        next_lever = NEXT_ROUTE_BINDING
        goal = True
        english = "Detector evaluation report view model is ready. Bind and smoke the route next."
        view_model = _view_model(metrics)
    else:
        primary_blocker = BLOCKER_EXECUTION_MISSING
        next_lever = NEXT_EXECUTION
        goal = False
        english = "Bounded detector evaluation execution is missing or unsafe; execute it before report binding."
        view_model = _view_model({})

    route_contract = {
        "schemaVersion": "video_to_analysis_detector_evaluation_report_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/detector-evaluation-report",
        "htmlRoutePath": "/video-to-analysis/detector-evaluation-report",
        "detectorEvaluationReportReady": goal,
    }
    (output_root / "detector_evaluation_report_render_smoke.html").write_text(_render_html(view_model), encoding="utf-8")
    summary = {
        "batchName": "video_to_analysis_detector_evaluation_report_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "detectorEvaluationReportReady": goal,
        **standard_false_flags(),
        "runtimeDefaultMutationExecuted": goal,
        "runtimeDefaultRolloutClosed": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_report_binding_summary.json",
        summary=summary,
        artifacts={
            "detector_evaluation_report_view_model.json": view_model,
            "detector_evaluation_report_route_contract.json": route_contract,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Report Binding",
    )


def main() -> None:
    main_for("Bind video-to-analysis detector evaluation report.", run_video_to_analysis_detector_evaluation_report_binding)


if __name__ == "__main__":
    main()
