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
DEFAULT_EVENT_BENCHMARK_DIR_NAME = "football_external_soccernet_event_benchmark_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_report_contract_prep_v1"

BLOCKER_BENCHMARK_MISSING = "football_external_soccernet_event_benchmark_smoke_missing"
BLOCKER_REPORT_CONTRACT = "football_external_soccernet_event_report_contract_gap"

NEXT_EVENT_BENCHMARK = "football_external_soccernet_event_benchmark_smoke"
NEXT_REPORT_REPAIR = "football_external_soccernet_event_report_contract_repair"
NEXT_REPORT_SMOKE = "football_external_soccernet_event_report_smoke"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_report_contract_prep",
            "successCriteria": [
                "convert event-only benchmark metrics into report-facing summary fields",
                "preserve explicit non-event stage limitations",
                "do not train, promote, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If report metrics are incomplete, repair event report contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_report_contract_repair",
            "successCriteria": [
                "repair report summary fields from saved event benchmark metrics only",
                "keep full-match analysis readiness false",
            ],
            "failureAdaptation": "If report summary remains invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_report_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before report smoke or training",
            ],
            "failureAdaptation": "Route to event benchmark smoke or report contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    event_root = candidate_root / DEFAULT_EVENT_BENCHMARK_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "benchmarkSummary": _load_json(event_root / "soccernet_event_benchmark_smoke_summary.json"),
        "benchmarkMetrics": _load_json(event_root / "event_benchmark_smoke_metrics.json"),
        "reportPrepContract": _load_json(event_root / "event_report_prep_contract.json"),
    }


def _benchmark_ready(summary: dict[str, Any] | None, metrics: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("eventBenchmarkSmokePassed") is True
        and int(summary.get("eventCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and isinstance(metrics, dict)
        and int(metrics.get("eventCount") or 0) > 0
        and isinstance(contract, dict)
        and contract.get("eventReportContractReady") is True
        and contract.get("trainingUseAllowed") is False
        and contract.get("videoDownloadAllowed") is False
    )


def _sorted_counts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [{"eventType": str(key), "count": int(value)} for key, value in raw.items()]
    return sorted(rows, key=lambda row: (-row["count"], row["eventType"]))


def _team_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    total = sum(int(value) for value in raw.values())
    rows = []
    for key, value in sorted(raw.items()):
        count = int(value)
        rows.append({"team": str(key), "count": count, "share": round(count / total, 6) if total else 0.0})
    return rows


def _report_summary(metrics: dict[str, Any] | None) -> dict[str, Any]:
    metrics = metrics or {}
    event_counts = metrics.get("eventTypeCounts") if isinstance(metrics.get("eventTypeCounts"), dict) else {}
    team_counts = metrics.get("teamCounts") if isinstance(metrics.get("teamCounts"), dict) else {}
    top_event_types = _sorted_counts(event_counts)
    return {
        "reportName": "SoccerNet Event-Only Match Summary",
        "sourceDataset": "SoccerNet SN-BAS-2025",
        "eventCount": int(metrics.get("eventCount") or 0),
        "distinctEventTypeCount": int(metrics.get("distinctEventTypeCount") or 0),
        "durationMs": int(metrics.get("durationMs") or 0),
        "eventRatePerMinute": metrics.get("eventRatePerMinute"),
        "topEventTypes": top_event_types[:8],
        "teamEventSplit": _team_rows(team_counts),
        "coveredStageIds": metrics.get("coveredStageIds") or [],
        "uncoveredStageIds": metrics.get("uncoveredStageIds") or [],
        "fullMatchAnalysisReady": False,
        "reportSmokeReady": bool(metrics.get("eventCount")),
    }


def _limitations(report: dict[str, Any]) -> dict[str, Any]:
    uncovered = report.get("uncoveredStageIds") if isinstance(report.get("uncoveredStageIds"), list) else []
    return {
        "eventOnlyReport": True,
        "fullMatchAnalysisReady": False,
        "coveredStageIds": report.get("coveredStageIds") or [],
        "uncoveredStageIds": uncovered,
        "cannotClaim": [
            "camera shot quality",
            "pitch calibration",
            "player tracking",
            "ball localization",
            "full tactical report readiness",
        ],
        "plainEnglish": "This SoccerNet fixture supports event-frequency and event-taxonomy reporting only. It does not include video-derived localization, tracking, calibration, or tactical state truth.",
    }


def _report_smoke_contract(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_REPORT_SMOKE,
        "sourceBatch": "football_external_soccernet_event_report_contract_prep",
        "reportSmokeReady": report.get("reportSmokeReady") is True,
        "eventCount": report.get("eventCount"),
        "distinctEventTypeCount": report.get("distinctEventTypeCount"),
        "eventRatePerMinute": report.get("eventRatePerMinute"),
        "coveredStageIds": report.get("coveredStageIds"),
        "uncoveredStageIds": report.get("uncoveredStageIds"),
        "fullMatchAnalysisReady": False,
        "trainingUseAllowed": False,
        "videoDownloadAllowed": False,
    }


def _classify(benchmark_ready: bool, report: dict[str, Any], smoke_contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not benchmark_ready:
        return (
            BLOCKER_BENCHMARK_MISSING,
            NEXT_EVENT_BENCHMARK,
            False,
            "SoccerNet event benchmark smoke truth is missing or unsafe; rerun event benchmark smoke.",
        )
    if smoke_contract.get("reportSmokeReady") is not True or int(report.get("eventCount") or 0) <= 0:
        return (
            BLOCKER_REPORT_CONTRACT,
            NEXT_REPORT_REPAIR,
            False,
            "SoccerNet event report contract is incomplete; repair report summary mapping.",
        )
    return (
        None,
        NEXT_REPORT_SMOKE,
        True,
        "SoccerNet event report contract is ready for report smoke. It remains event-only and not full match-analysis ready.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_benchmark_smoke_missing", "selected": primary_blocker == BLOCKER_BENCHMARK_MISSING, "primaryBlocker": BLOCKER_BENCHMARK_MISSING, "nextRecommendedNextLever": NEXT_EVENT_BENCHMARK},
            {"condition": "event_report_contract_gap", "selected": primary_blocker == BLOCKER_REPORT_CONTRACT, "primaryBlocker": BLOCKER_REPORT_CONTRACT, "nextRecommendedNextLever": NEXT_REPORT_REPAIR},
            {"condition": "event_report_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT_SMOKE},
        ],
    }


def _markdown_report(report: dict[str, Any], limitations: dict[str, Any]) -> str:
    lines = [
        "# SoccerNet Event-Only Match Summary",
        "",
        f"- Events: `{report.get('eventCount')}`",
        f"- Distinct event types: `{report.get('distinctEventTypeCount')}`",
        f"- Event rate per minute: `{report.get('eventRatePerMinute')}`",
        "",
        "## Top Event Types",
        "",
    ]
    for row in report.get("topEventTypes") or []:
        lines.append(f"- `{row['eventType']}`: `{row['count']}`")
    lines.extend(["", "## Limits", "", str(limitations.get("plainEnglish") or ""), ""])
    return "\n".join(lines)


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Report Contract Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Report contract ready: `{summary.get('reportContractReady')}`",
            f"- Event count: `{summary.get('eventCount')}`",
            f"- Full match analysis ready: `{summary.get('fullMatchAnalysisReady')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_report_contract_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_report_contract_prep",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _benchmark_ready(inputs["benchmarkSummary"], inputs["benchmarkMetrics"], inputs["reportPrepContract"])
    report = _report_summary(inputs["benchmarkMetrics"])
    limitation_audit = _limitations(report)
    smoke_contract = _report_smoke_contract(report)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, report, smoke_contract)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_report_contract_prep",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_benchmark_smoke",
        "reportContractReady": goal_achieved,
        "eventCount": report.get("eventCount"),
        "distinctEventTypeCount": report.get("distinctEventTypeCount"),
        "eventRatePerMinute": report.get("eventRatePerMinute"),
        "fullMatchAnalysisReady": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadApproved": False,
        "fullOriginalVideoDownloadExecuted": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "soccernetEventReportSummary": report,
        "eventReportLimitationsAudit": limitation_audit,
        "eventReportSmokeContract": smoke_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_report_contract_prep_summary.json", summary)
    _write_json(output_root / "soccernet_event_report_summary.json", report)
    _write_json(output_root / "event_report_limitations_audit.json", limitation_audit)
    _write_json(output_root / "event_report_smoke_contract.json", smoke_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "soccernet_event_report_summary.md").write_text(_markdown_report(report, limitation_audit), encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_event_report_contract_prep")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_report_contract_prep(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
