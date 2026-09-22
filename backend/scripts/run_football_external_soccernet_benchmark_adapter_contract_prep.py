from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SMOKE_DIR_NAME = "football_external_soccernet_event_adapter_smoke_test_v1"
DEFAULT_FIXTURE_DIR_NAME = "football_external_soccernet_event_adapter_fixture_materialization_v1"
DEFAULT_HARNESS_DIR_NAME = "football_external_benchmark_harness_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_benchmark_adapter_contract_prep_v1"

BLOCKER_SMOKE_MISSING = "football_external_soccernet_event_adapter_smoke_missing"
BLOCKER_SCHEMA_GAP = "football_external_soccernet_benchmark_adapter_schema_gap"

NEXT_SMOKE = "football_external_soccernet_event_adapter_smoke_test"
NEXT_CONTRACT_REPAIR = "football_external_soccernet_benchmark_adapter_contract_repair"
NEXT_EVENT_BENCHMARK_SMOKE = "football_external_soccernet_event_benchmark_smoke"

EVENT_ONLY_STAGE = "possession_event_semantics"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_benchmark_adapter_contract_prep",
            "successCriteria": [
                "map canonical SoccerNet events into benchmark EventStream/BallActionEvent rows",
                "classify benchmark stage coverage honestly as event-only",
                "do not train, promote, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If schema coverage is incomplete, repair adapter contract from saved fixture truth only.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_benchmark_adapter_contract_repair",
            "successCriteria": [
                "repair required field mapping or stage-coverage metadata",
                "preserve event-only scope and no-download guardrails",
            ],
            "failureAdaptation": "If contract remains invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_benchmark_adapter_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before benchmark execution or training",
            ],
            "failureAdaptation": "Route to smoke test or adapter contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    smoke_root = candidate_root / DEFAULT_SMOKE_DIR_NAME
    fixture_root = candidate_root / DEFAULT_FIXTURE_DIR_NAME
    harness_root = candidate_root / DEFAULT_HARNESS_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "smokeSummary": _load_json(smoke_root / "soccernet_event_adapter_smoke_summary.json"),
        "benchmarkPrepContract": _load_json(smoke_root / "benchmark_adapter_prep_contract.json"),
        "canonicalTimeline": _load_json(fixture_root / "canonical_event_timeline.json"),
        "adapterContract": _load_json(harness_root / "dataset_adapter_contract.json"),
        "stageGateContract": _load_json(harness_root / "stage_gate_contract.json"),
    }


def _smoke_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None, timeline: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("adapterSmokePassed") is True
        and int(summary.get("canonicalEventCount") or 0) > 0
        and summary.get("eventIdUnique") is True
        and summary.get("positionMsMonotonicNonDecreasing") is True
        and summary.get("trainingExecuted") is False
        and isinstance(contract, dict)
        and contract.get("benchmarkAdapterPrepReady") is True
        and contract.get("trainingUseAllowed") is False
        and contract.get("videoDownloadAllowed") is False
        and isinstance(timeline, dict)
        and isinstance(timeline.get("events"), list)
    )


def _schemas(adapter_contract: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (adapter_contract or {}).get("schemas")
    if not isinstance(raw, dict):
        return {}
    return {str(name): dict(schema) for name, schema in raw.items() if isinstance(schema, dict)}


def _required_fields(schema: dict[str, Any]) -> list[str]:
    fields = schema.get("requiredFields")
    if not isinstance(fields, list):
        return []
    return [str(field) for field in fields]


def _events(timeline: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (timeline or {}).get("events")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _event_stream_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        rows.append(
            {
                "eventId": event.get("eventId"),
                "timestampMs": event.get("positionMs"),
                "teamId": event.get("team"),
                "playerId": None,
                "eventType": event.get("eventType"),
                "pitchX": None,
                "pitchY": None,
                "sourceDataset": event.get("sourceDataset") or "SoccerNet SN-BAS-2025",
                "sourceGameId": event.get("sourceGameId"),
                "visibility": event.get("visibility"),
            }
        )
    return rows


def _ball_action_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, event in enumerate(events):
        rows.append(
            {
                "eventId": event.get("eventId"),
                "frameIndex": None,
                "eventType": event.get("eventType"),
                "ballPitchX": None,
                "ballPitchY": None,
                "confidence": 1.0,
                "timestampMs": event.get("positionMs"),
                "sourceAnnotationIndex": event.get("sourceAnnotationIndex", index),
            }
        )
    return rows


def _schema_rows_valid(rows: list[dict[str, Any]], required_fields: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    failures = []
    for index, row in enumerate(rows):
        missing = [field for field in required_fields if field not in row]
        if missing:
            failures.append({"rowIndex": index, "missingFields": missing})
    return len(failures) == 0, failures[:20]


def _adapter_manifest(
    event_stream_rows: list[dict[str, Any]],
    ball_action_rows: list[dict[str, Any]],
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    event_ok, event_failures = _schema_rows_valid(event_stream_rows, _required_fields(schemas.get("EventStream", {})))
    ball_ok, ball_failures = _schema_rows_valid(ball_action_rows, _required_fields(schemas.get("BallActionEvent", {})))
    labels = Counter(str(row.get("eventType") or "<missing>") for row in event_stream_rows)
    return {
        "adapterName": "soccernet_event_benchmark_adapter",
        "sourceDataset": "SoccerNet SN-BAS-2025",
        "eventStreamRowCount": len(event_stream_rows),
        "ballActionEventRowCount": len(ball_action_rows),
        "eventStreamSchemaSatisfied": event_ok,
        "ballActionEventSchemaSatisfied": ball_ok,
        "schemaFailuresSample": event_failures + ball_failures,
        "distinctEventTypeCount": len(labels),
        "eventTypeCounts": dict(sorted(labels.items())),
        "benchmarkAdapterContractReady": event_ok and ball_ok and bool(event_stream_rows),
        "eventOnlySource": True,
        "trainingUseAllowed": False,
    }


def _stage_coverage(stage_contract: dict[str, Any] | None) -> dict[str, Any]:
    required = (stage_contract or {}).get("requiredStageCoverage")
    if not isinstance(required, list):
        required = []
    required_stage_ids = [str(stage) for stage in required]
    covered = [EVENT_ONLY_STAGE] if EVENT_ONLY_STAGE in required_stage_ids else []
    uncovered = [stage for stage in required_stage_ids if stage not in covered]
    return {
        "requiredStageIds": required_stage_ids,
        "coveredStageIds": covered,
        "uncoveredStageIds": uncovered,
        "eventOnlySource": True,
        "fullBenchmarkExecutionReady": False,
        "eventBenchmarkSmokeReady": bool(covered),
        "stageCoverageDecision": "SoccerNet Labels-ball event stream supports possession/event semantics smoke only; it does not provide video, calibration, tracking, or ball localization truth.",
    }


def _classify(smoke_ready: bool, adapter_manifest: dict[str, Any], stage_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not smoke_ready:
        return (
            BLOCKER_SMOKE_MISSING,
            NEXT_SMOKE,
            False,
            "SoccerNet event adapter smoke truth is missing or unsafe; rerun smoke test before benchmark adapter prep.",
        )
    if adapter_manifest.get("benchmarkAdapterContractReady") is not True or stage_audit.get("eventBenchmarkSmokeReady") is not True:
        return (
            BLOCKER_SCHEMA_GAP,
            NEXT_CONTRACT_REPAIR,
            False,
            "SoccerNet benchmark adapter contract is not ready; repair schema or stage coverage mapping.",
        )
    return (
        None,
        NEXT_EVENT_BENCHMARK_SMOKE,
        True,
        "SoccerNet benchmark adapter contract is ready for event-only benchmark smoke. Non-event benchmark stages remain explicitly uncovered.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_adapter_smoke_missing", "selected": primary_blocker == BLOCKER_SMOKE_MISSING, "primaryBlocker": BLOCKER_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_SMOKE},
            {"condition": "benchmark_adapter_schema_gap", "selected": primary_blocker == BLOCKER_SCHEMA_GAP, "primaryBlocker": BLOCKER_SCHEMA_GAP, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "event_benchmark_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_EVENT_BENCHMARK_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Benchmark Adapter Contract Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- EventStream rows: `{summary.get('eventStreamRowCount')}`",
            f"- Covered stages: `{summary.get('coveredStageIds')}`",
            f"- Uncovered stages: `{summary.get('uncoveredStageIds')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_benchmark_adapter_contract_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_benchmark_adapter_contract_prep",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _smoke_ready(inputs["smokeSummary"], inputs["benchmarkPrepContract"], inputs["canonicalTimeline"])
    schemas = _schemas(inputs["adapterContract"])
    canonical_events = _events(inputs["canonicalTimeline"])
    event_stream_rows = _event_stream_rows(canonical_events)
    ball_action_rows = _ball_action_rows(canonical_events)
    adapter_manifest = _adapter_manifest(event_stream_rows, ball_action_rows, schemas)
    stage_audit = _stage_coverage(inputs["stageGateContract"])
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, adapter_manifest, stage_audit)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()

    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_benchmark_adapter_contract_prep",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_adapter_smoke_test",
        "eventStreamRowCount": len(event_stream_rows),
        "ballActionEventRowCount": len(ball_action_rows),
        "coveredStageIds": stage_audit.get("coveredStageIds"),
        "uncoveredStageIds": stage_audit.get("uncoveredStageIds"),
        "fullBenchmarkExecutionReady": False,
        "eventBenchmarkSmokeReady": stage_audit.get("eventBenchmarkSmokeReady"),
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
    event_fixture = {"schema": "EventStream", "rowCount": len(event_stream_rows), "rows": event_stream_rows}
    ball_fixture = {"schema": "BallActionEvent", "rowCount": len(ball_action_rows), "rows": ball_action_rows}
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "soccernetBenchmarkAdapterManifest": adapter_manifest,
        "soccernetStageCoverageAudit": stage_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_benchmark_adapter_contract_prep_summary.json", summary)
    _write_json(output_root / "soccernet_benchmark_adapter_manifest.json", adapter_manifest)
    _write_json(output_root / "soccernet_stage_coverage_audit.json", stage_audit)
    _write_json(output_root / "soccernet_event_stream_fixture.json", event_fixture)
    _write_json(output_root / "soccernet_ball_action_event_fixture.json", ball_fixture)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_benchmark_adapter_contract_prep")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_benchmark_adapter_contract_prep(
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
