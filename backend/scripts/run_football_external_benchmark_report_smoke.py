from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_EXECUTION_DIR_NAME = "football_external_benchmark_bounded_execution_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_report_smoke_v1"

BLOCKER_REPORT_PAYLOAD_MISSING = "football_external_benchmark_report_payload_missing"
BLOCKER_REPORT_RENDER_GAP = "football_external_benchmark_report_render_gap"

NEXT_EXECUTION_SMOKE = "football_external_benchmark_bounded_execution_smoke"
NEXT_REPORT_REPAIR = "football_external_benchmark_report_payload_repair"
NEXT_PRODUCT_BINDING = "football_external_benchmark_product_ui_binding"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_report_smoke",
            "successCriteria": [
                "render markdown and view-model artifacts from bounded execution payload",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If payload is missing, rerun bounded execution smoke.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_report_payload_repair",
            "successCriteria": [
                "repair report payload from bounded execution result rows only",
                "do not rerun detector evaluation or download data",
            ],
            "failureAdaptation": "If report cannot render, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_report_smoke_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to bounded execution smoke, payload repair, or product UI binding.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, execution_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    execution_root = candidate_root / execution_dir_name
    return {
        "candidateRoot": candidate_root,
        "executionSummary": _load_json(execution_root / "external_benchmark_bounded_execution_summary.json"),
        "reportPayload": _load_json(execution_root / "benchmark_report_payload.json"),
    }


def _payload_ready(summary: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("boundedBenchmarkExecutionSmokePassed") is True
        and summary.get("externalBenchmarkReportReady") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "football_external_benchmark_report_payload_v1"
        and payload.get("reportReady") is True
        and isinstance(payload.get("resultRows"), list)
        and len(payload["resultRows"]) >= 2
        and payload.get("detectorEvaluationIncluded") is False
        and payload.get("trainingIncluded") is False
    )


def _rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (payload or {}).get("resultRows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _view_model(rows: list[dict[str, Any]], ready: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_report_view_model_v1",
        "generatedAt": _utc_now_iso(),
        "title": "External Football Benchmark Smoke",
        "reportReady": ready and len(rows) >= 2,
        "sourceCount": len(rows),
        "sources": rows,
        "detectorEvaluationIncluded": False,
        "trainingIncluded": False,
        "mutationIncluded": False,
    }


def _render_markdown(view_model: dict[str, Any]) -> str:
    lines = [
        "# External Football Benchmark Smoke",
        "",
        f"- Report ready: `{view_model.get('reportReady')}`",
        f"- Source count: `{view_model.get('sourceCount')}`",
        "- Detector evaluation included: `False`",
        "- Training included: `False`",
        "",
        "| Source | Events | Frames | Segments | Metric families |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in view_model.get("sources") or []:
        families = ", ".join(str(item) for item in row.get("metricFamilies") or [])
        lines.append(
            f"| {row.get('sourceId')} | {row.get('eventCount') or 0} | {row.get('reportedFrameCount') or 0} | {row.get('segmentCount') or 0} | {families} |"
        )
    lines.extend(
        [
            "",
            "This report is generated from bounded saved artifacts only. It is not a detector benchmark, training run, promotion, or runtime-default mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def _payload_audit(payload_ready: bool, rows: list[dict[str, Any]], markdown: str, view_model: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "payloadReady": payload_ready,
        "rowCountValid": len(rows) >= 2,
        "markdownRendered": "# External Football Benchmark Smoke" in markdown,
        "viewModelReady": view_model.get("reportReady") is True,
        "detectorEvaluationStillBlocked": True,
        "downloadStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "normalStorageMutationStillBlocked": True,
    }
    return {
        "schemaVersion": "football_external_benchmark_report_payload_audit_v1",
        "generatedAt": _utc_now_iso(),
        **checks,
        "reportPayloadAuditPassed": all(checks.values()),
    }


def _classify(payload_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not payload_ready:
        return (
            BLOCKER_REPORT_PAYLOAD_MISSING,
            NEXT_EXECUTION_SMOKE,
            False,
            "External benchmark report payload is missing or unsafe; rerun bounded execution smoke.",
        )
    if audit.get("reportPayloadAuditPassed") is not True:
        return (
            BLOCKER_REPORT_RENDER_GAP,
            NEXT_REPORT_REPAIR,
            False,
            "External benchmark report payload could not render safely; repair report payload.",
        )
    return (
        None,
        NEXT_PRODUCT_BINDING,
        True,
        "External benchmark report smoke passed and produced markdown plus a UI-ready view model. Advance to product UI binding; no detector evaluation, data/video download, training, promotion, normal storage mutation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "report_payload_missing", "selected": primary_blocker == BLOCKER_REPORT_PAYLOAD_MISSING, "primaryBlocker": BLOCKER_REPORT_PAYLOAD_MISSING, "nextRecommendedNextLever": NEXT_EXECUTION_SMOKE},
            {"condition": "report_render_gap", "selected": primary_blocker == BLOCKER_REPORT_RENDER_GAP, "primaryBlocker": BLOCKER_REPORT_RENDER_GAP, "nextRecommendedNextLever": NEXT_REPORT_REPAIR},
            {"condition": "product_ui_binding_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_BINDING},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Report Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Report rows: `{summary.get('reportRowCount')}`",
            f"- Product UI binding ready: `{summary.get('productUiBindingReady')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_report_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    execution_dir_name: str = DEFAULT_EXECUTION_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_report_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, execution_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _payload_ready(inputs["executionSummary"], inputs["reportPayload"])
    rows = _rows(inputs["reportPayload"])
    view_model = _view_model(rows, ready)
    markdown = _render_markdown(view_model)
    audit = _payload_audit(ready, rows, markdown, view_model)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, audit)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_report_smoke",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_bounded_execution_smoke",
        "externalBenchmarkReportSmokePassed": goal_achieved,
        "reportRowCount": len(rows),
        "productUiBindingReady": goal_achieved,
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "datasetDownloadExecuted": False,
        "videoDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    failsafe = {"attemptBudget": 3, "attempts": attempts}
    outcome = {
        "summary": summary,
        "reportPayloadAudit": audit,
        "externalBenchmarkReportViewModel": view_model,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": failsafe,
    }
    _write_json(output_root / "external_benchmark_report_smoke_summary.json", summary)
    (output_root / "external_benchmark_report.md").write_text(markdown, encoding="utf-8")
    _write_json(output_root / "external_benchmark_report_view_model.json", view_model)
    _write_json(output_root / "report_payload_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", failsafe)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--execution-dir-name", default=DEFAULT_EXECUTION_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    args = parser.parse_args()
    summary = run_football_external_benchmark_report_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        execution_dir_name=args.execution_dir_name,
        output_dir_name=args.output_dir_name,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("goalAchieved") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
