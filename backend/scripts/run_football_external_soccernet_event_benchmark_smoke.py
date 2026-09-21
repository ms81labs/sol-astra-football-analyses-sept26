from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_PREP_DIR_NAME = "football_external_soccernet_benchmark_adapter_contract_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_benchmark_smoke_v1"

BLOCKER_PREP_MISSING = "football_external_soccernet_benchmark_adapter_prep_missing"
BLOCKER_EVENT_FIXTURE_INVALID = "football_external_soccernet_event_benchmark_fixture_invalid"

NEXT_PREP = "football_external_soccernet_benchmark_adapter_contract_prep"
NEXT_REPAIR = "football_external_soccernet_event_benchmark_contract_repair"
NEXT_REPORT = "football_external_soccernet_event_report_contract_prep"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_benchmark_smoke",
            "successCriteria": [
                "compute event-only benchmark smoke metrics from SoccerNet EventStream rows",
                "preserve stage coverage limits",
                "do not train, promote, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If event fixture metrics fail, repair event benchmark contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_benchmark_contract_repair",
            "successCriteria": [
                "repair event timing or taxonomy metric contract from saved fixture rows only",
                "keep non-event stages uncovered",
            ],
            "failureAdaptation": "If metrics remain invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_benchmark_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before report contract prep or training",
            ],
            "failureAdaptation": "Route to adapter prep or benchmark contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    prep_root = candidate_root / DEFAULT_PREP_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "prepSummary": _load_json(prep_root / "soccernet_benchmark_adapter_contract_prep_summary.json"),
        "eventStreamFixture": _load_json(prep_root / "soccernet_event_stream_fixture.json"),
        "stageCoverageAudit": _load_json(prep_root / "soccernet_stage_coverage_audit.json"),
    }


def _prep_ready(summary: dict[str, Any] | None, fixture: dict[str, Any] | None, stage: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and int(summary.get("eventStreamRowCount") or 0) > 0
        and summary.get("eventBenchmarkSmokeReady") is True
        and summary.get("trainingExecuted") is False
        and isinstance(fixture, dict)
        and isinstance(fixture.get("rows"), list)
        and isinstance(stage, dict)
        and stage.get("eventOnlySource") is True
    )


def _event_rows(fixture: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (fixture or {}).get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _metrics(rows: list[dict[str, Any]], stage: dict[str, Any] | None) -> dict[str, Any]:
    event_types = Counter(str(row.get("eventType") or "<missing>") for row in rows)
    teams = Counter(str(row.get("teamId") or "<missing>") for row in rows)
    timestamps = [int(row["timestampMs"]) for row in rows if isinstance(row.get("timestampMs"), int)]
    duration_ms = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0
    duration_minutes = duration_ms / 60000 if duration_ms > 0 else 0.0
    event_rate = (len(rows) / duration_minutes) if duration_minutes > 0 else 0.0
    ids = [str(row.get("eventId")) for row in rows]
    return {
        "eventCount": len(rows),
        "distinctEventTypeCount": len(event_types),
        "eventTypeCounts": dict(sorted(event_types.items())),
        "teamCounts": dict(sorted(teams.items())),
        "timestampMsMin": min(timestamps) if timestamps else None,
        "timestampMsMax": max(timestamps) if timestamps else None,
        "durationMs": duration_ms,
        "eventRatePerMinute": round(event_rate, 6),
        "eventIdUnique": len(ids) == len(set(ids)) and bool(ids),
        "timestampMsMonotonicNonDecreasing": timestamps == sorted(timestamps),
        "coveredStageIds": (stage or {}).get("coveredStageIds") or [],
        "uncoveredStageIds": (stage or {}).get("uncoveredStageIds") or [],
        "eventOnlyBenchmark": True,
    }


def _report_contract(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_REPORT,
        "sourceBatch": "football_external_soccernet_event_benchmark_smoke",
        "eventCount": metrics.get("eventCount"),
        "distinctEventTypeCount": metrics.get("distinctEventTypeCount"),
        "eventRatePerMinute": metrics.get("eventRatePerMinute"),
        "eventReportContractReady": bool(metrics.get("eventIdUnique") and metrics.get("timestampMsMonotonicNonDecreasing")),
        "coveredStageIds": metrics.get("coveredStageIds"),
        "uncoveredStageIds": metrics.get("uncoveredStageIds"),
        "trainingUseAllowed": False,
        "videoDownloadAllowed": False,
    }


def _classify(prep_ready: bool, metrics: dict[str, Any], report_contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not prep_ready:
        return (
            BLOCKER_PREP_MISSING,
            NEXT_PREP,
            False,
            "SoccerNet benchmark adapter prep truth is missing or unsafe; rerun adapter contract prep.",
        )
    if int(metrics.get("eventCount") or 0) <= 0 or report_contract.get("eventReportContractReady") is not True:
        return (
            BLOCKER_EVENT_FIXTURE_INVALID,
            NEXT_REPAIR,
            False,
            "SoccerNet event benchmark smoke metrics are invalid; repair event benchmark contract.",
        )
    return (
        None,
        NEXT_REPORT,
        True,
        "SoccerNet event-only benchmark smoke passed. Advance to event report contract prep; non-event stages remain uncovered.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "benchmark_adapter_prep_missing", "selected": primary_blocker == BLOCKER_PREP_MISSING, "primaryBlocker": BLOCKER_PREP_MISSING, "nextRecommendedNextLever": NEXT_PREP},
            {"condition": "event_benchmark_fixture_invalid", "selected": primary_blocker == BLOCKER_EVENT_FIXTURE_INVALID, "primaryBlocker": BLOCKER_EVENT_FIXTURE_INVALID, "nextRecommendedNextLever": NEXT_REPAIR},
            {"condition": "event_report_contract_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_REPORT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Benchmark Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Event count: `{summary.get('eventCount')}`",
            f"- Event rate per minute: `{summary.get('eventRatePerMinute')}`",
            f"- Covered stages: `{summary.get('coveredStageIds')}`",
            f"- Uncovered stages: `{summary.get('uncoveredStageIds')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_benchmark_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_benchmark_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _prep_ready(inputs["prepSummary"], inputs["eventStreamFixture"], inputs["stageCoverageAudit"])
    rows = _event_rows(inputs["eventStreamFixture"])
    metrics = _metrics(rows, inputs["stageCoverageAudit"])
    report_contract = _report_contract(metrics)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, metrics, report_contract)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_benchmark_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_benchmark_adapter_contract_prep",
        "eventBenchmarkSmokePassed": goal_achieved,
        "eventCount": metrics.get("eventCount"),
        "distinctEventTypeCount": metrics.get("distinctEventTypeCount"),
        "eventRatePerMinute": metrics.get("eventRatePerMinute"),
        "coveredStageIds": metrics.get("coveredStageIds"),
        "uncoveredStageIds": metrics.get("uncoveredStageIds"),
        "eventOnlyBenchmark": True,
        "fullBenchmarkExecutionReady": False,
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
        "eventBenchmarkSmokeMetrics": metrics,
        "eventReportPrepContract": report_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_benchmark_smoke_summary.json", summary)
    _write_json(output_root / "event_benchmark_smoke_metrics.json", metrics)
    _write_json(output_root / "event_report_prep_contract.json", report_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_event_benchmark_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_benchmark_smoke(
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
