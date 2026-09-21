from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_benchmark_execution_approval_v1"
DEFAULT_SMOKE_DIR_NAME = "football_external_benchmark_harness_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_bounded_execution_smoke_v1"

BLOCKER_APPROVAL_MISSING = "football_external_benchmark_execution_approval_missing"
BLOCKER_EXECUTION_CONTRACT_GAP = "football_external_benchmark_bounded_execution_contract_gap"

NEXT_APPROVAL = "football_external_benchmark_execution_approval"
NEXT_CONTRACT_REPAIR = "football_external_benchmark_bounded_execution_contract_repair"
NEXT_REPORT_SMOKE = "football_external_benchmark_report_smoke"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_bounded_execution_smoke",
            "successCriteria": [
                "execute generated-truth aggregation for approved SoccerNet and SoccerTrack cases",
                "write normalized result rows and a report payload",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If approval is missing, rerun execution approval.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_bounded_execution_contract_repair",
            "successCriteria": [
                "repair bounded result mapping from source summaries only",
                "do not run detector inference or download data",
            ],
            "failureAdaptation": "If source rows still cannot be mapped, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_bounded_execution_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to approval, contract repair, or report smoke.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, approval_dir_name: str, smoke_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / approval_dir_name
    smoke_root = candidate_root / smoke_dir_name
    return {
        "candidateRoot": candidate_root,
        "approvalSummary": _load_json(approval_root / "external_benchmark_execution_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "external_benchmark_execution_approval_contract.json"),
        "smokeCaseManifest": _load_json(smoke_root / "benchmark_smoke_case_manifest.json"),
    }


def _approval_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("externalBenchmarkExecutionApproved") is True
        and summary.get("approvedExecutionMode") == "generated_truth_bounded_smoke"
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("externalBenchmarkExecutionApproved") is True
        and contract.get("detectorBenchmarkAllowed") is False
        and contract.get("datasetDownloadAllowed") is False
        and contract.get("videoDownloadAllowed") is False
        and contract.get("normalMatchStorageMutationAllowed") is False
    )


def _smoke_cases(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (manifest or {}).get("smokeCases")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _artifact_payloads(case: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path_value in case.get("artifactPaths") or []:
        path = _resolve_path(str(path_value))
        payload = _load_json(path)
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _result_row(case: dict[str, Any]) -> dict[str, Any]:
    source_id = str(case.get("sourceId"))
    payloads = _artifact_payloads(case)
    event_count = 0
    distinct_event_type_count = 0
    frame_count = 0
    segment_count = 0
    fixture_file_count = 0
    selected_match_id = None
    for payload in payloads:
        event_count = max(event_count, int(payload.get("eventCount") or payload.get("reportedEventCount") or 0))
        distinct_event_type_count = max(distinct_event_type_count, int(payload.get("distinctEventTypeCount") or 0))
        frame_count = max(frame_count, int(payload.get("reportedFrameCount") or 0))
        segment_count = max(segment_count, int(payload.get("segmentCount") or 0))
        fixture_file_count = max(fixture_file_count, int(payload.get("downloadedFixtureFileCount") or 0))
        selected_match_id = selected_match_id or payload.get("selectedMatchId")
    return {
        "sourceId": source_id,
        "caseId": case.get("caseId"),
        "metricFamilies": case.get("expectedMetricFamilies") or [],
        "artifactCount": len(payloads),
        "eventCount": event_count,
        "distinctEventTypeCount": distinct_event_type_count,
        "reportedFrameCount": frame_count,
        "segmentCount": segment_count,
        "downloadedFixtureFileCount": fixture_file_count,
        "selectedMatchId": selected_match_id,
        "detectorEvaluationExecuted": False,
        "trainingExecuted": False,
        "videoDownloadExecuted": False,
    }


def _result_table(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_result_row(case) for case in cases]
    return {
        "schemaVersion": "football_external_benchmark_bounded_execution_result_table_v1",
        "generatedAt": utc_now_iso(),
        "executionMode": "generated_truth_bounded_smoke",
        "rowCount": len(rows),
        "rows": rows,
    }


def _comparison_audit(result_table: dict[str, Any]) -> dict[str, Any]:
    rows = result_table.get("rows") or []
    source_ids = [row.get("sourceId") for row in rows if isinstance(row, dict)]
    event_counts = {row.get("sourceId"): row.get("eventCount") for row in rows if isinstance(row, dict)}
    return {
        "schemaVersion": "football_external_benchmark_cross_source_comparison_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceIds": source_ids,
        "sourceCount": len(source_ids),
        "eventCountsBySource": event_counts,
        "comparisonSmokePassed": set(source_ids) >= {"soccernet", "soccertrack"} and all((row.get("eventCount") or 0) > 0 for row in rows if isinstance(row, dict)),
        "detectorScoreComparisonExecuted": False,
    }


def _report_payload(result_table: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_report_payload_v1",
        "generatedAt": utc_now_iso(),
        "reportReady": comparison.get("comparisonSmokePassed") is True,
        "sourceBatch": "football_external_benchmark_bounded_execution_smoke",
        "resultRows": result_table.get("rows") or [],
        "comparisonSummary": comparison,
        "detectorEvaluationIncluded": False,
        "trainingIncluded": False,
    }


def _guardrail_audit(approval_ready: bool, result_table: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "approvalReady": approval_ready,
        "resultRowsPresent": int(result_table.get("rowCount") or 0) >= 2,
        "reportReady": report_payload.get("reportReady") is True,
        "detectorEvaluationStillBlocked": True,
        "downloadStillBlocked": True,
        "trainingStillBlocked": True,
        "promotionStillBlocked": True,
        "runtimeMutationStillBlocked": True,
        "normalStorageMutationStillBlocked": True,
    }
    return {
        "schemaVersion": "football_external_benchmark_bounded_execution_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        **checks,
        "boundedExecutionGuardrailPassed": all(checks.values()),
    }


def _classify(approval_ready: bool, guardrail: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "External benchmark execution approval is missing or unsafe; rerun execution approval.",
        )
    if guardrail.get("boundedExecutionGuardrailPassed") is not True:
        return (
            BLOCKER_EXECUTION_CONTRACT_GAP,
            NEXT_CONTRACT_REPAIR,
            False,
            "External benchmark bounded execution smoke could not produce safe report-ready result rows; repair the contract.",
        )
    return (
        None,
        NEXT_REPORT_SMOKE,
        True,
        "External benchmark bounded execution smoke passed over generated truth for SoccerNet and SoccerTrack. Advance to benchmark report smoke; no detector evaluation, data/video download, training, promotion, normal storage mutation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "execution_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "bounded_execution_contract_gap", "selected": primary_blocker == BLOCKER_EXECUTION_CONTRACT_GAP, "primaryBlocker": BLOCKER_EXECUTION_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "benchmark_report_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Bounded Execution Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Result rows: `{summary.get('resultRowCount')}`",
            f"- Report ready: `{summary.get('externalBenchmarkReportReady')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime-default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_bounded_execution_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    approval_dir_name: str = DEFAULT_APPROVAL_DIR_NAME,
    smoke_dir_name: str = DEFAULT_SMOKE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_bounded_execution_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, approval_dir_name, smoke_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    cases = _smoke_cases(inputs["smokeCaseManifest"])
    result_table = _result_table(cases)
    comparison = _comparison_audit(result_table)
    report_payload = _report_payload(result_table, comparison)
    guardrail = _guardrail_audit(ready, result_table, report_payload)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, guardrail)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_bounded_execution_smoke",
        "generatedAt": utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_execution_approval",
        "boundedBenchmarkExecutionSmokePassed": goal_achieved,
        "boundedExternalBenchmarkExecuted": goal_achieved,
        "executionMode": "generated_truth_bounded_smoke",
        "resultRowCount": result_table.get("rowCount"),
        "externalBenchmarkReportReady": goal_achieved,
        "externalBenchmarkExecutionReady": False,
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
        "boundedExecutionResultTable": result_table,
        "crossSourceComparisonAudit": comparison,
        "benchmarkReportPayload": report_payload,
        "executionGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": failsafe,
    }

    _write_json(output_root / "external_benchmark_bounded_execution_summary.json", summary)
    _write_json(output_root / "bounded_execution_result_table.json", result_table)
    _write_json(output_root / "cross_source_comparison_audit.json", comparison)
    _write_json(output_root / "benchmark_report_payload.json", report_payload)
    _write_json(output_root / "execution_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", failsafe)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--approval-dir-name", default=DEFAULT_APPROVAL_DIR_NAME)
    parser.add_argument("--smoke-dir-name", default=DEFAULT_SMOKE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    args = parser.parse_args()
    summary = run_football_external_benchmark_bounded_execution_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        approval_dir_name=args.approval_dir_name,
        smoke_dir_name=args.smoke_dir_name,
        output_dir_name=args.output_dir_name,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("goalAchieved") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
