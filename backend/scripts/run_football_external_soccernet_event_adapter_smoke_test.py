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
DEFAULT_FIXTURE_DIR_NAME = "football_external_soccernet_event_adapter_fixture_materialization_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_adapter_smoke_test_v1"

BLOCKER_FIXTURE_MISSING = "football_external_soccernet_event_fixture_missing"
BLOCKER_ADAPTER_CONTRACT = "football_external_soccernet_event_adapter_contract_gap"

NEXT_FIXTURE = "football_external_soccernet_event_adapter_fixture_materialization"
NEXT_CONTRACT_REPAIR = "football_external_soccernet_event_adapter_contract_repair"
NEXT_BENCHMARK_PREP = "football_external_soccernet_benchmark_adapter_contract_prep"

REQUIRED_EVENT_FIELDS = ["eventId", "sourceGameId", "period", "positionMs", "eventType", "team", "visibility"]



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_adapter_smoke",
            "successCriteria": [
                "load canonical SoccerNet event timeline fixture",
                "verify required adapter fields, ordering, IDs, and taxonomy",
                "do not train, evaluate candidates, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If the adapter contract fails, repair event fixture mapping.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_adapter_contract_repair",
            "successCriteria": [
                "repair field mapping or timeline contract from saved fixture truth only",
                "preserve no-download/no-training guardrails",
            ],
            "failureAdaptation": "If contract remains invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_adapter_smoke_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before benchmark execution or training",
            ],
            "failureAdaptation": "Route to fixture materialization or adapter contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fixture_root = candidate_root / DEFAULT_FIXTURE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fixtureRoot": fixture_root,
        "fixtureSummary": _load_json(fixture_root / "soccernet_event_fixture_materialization_summary.json"),
        "fixtureManifest": _load_json(fixture_root / "soccernet_event_fixture_manifest.json"),
        "canonicalTimeline": _load_json(fixture_root / "canonical_event_timeline.json"),
    }


def _fixture_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None, timeline: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and int(summary.get("canonicalEventCount") or 0) > 0
        and summary.get("eventFixtureQualityPassed") is True
        and summary.get("eventIdUnique") is True
        and summary.get("archiveDownloadExecuted") is False
        and summary.get("videoMemberDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("qualityPassed") is True
        and isinstance(timeline, dict)
        and isinstance(timeline.get("events"), list)
    )


def _event_adapter_audit(timeline: dict[str, Any] | None) -> dict[str, Any]:
    events = timeline.get("events") if isinstance(timeline, dict) else []
    if not isinstance(events, list):
        events = []
    failures = []
    ids = []
    positions = []
    labels = Counter()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            failures.append({"eventIndex": index, "reason": "event_not_object"})
            continue
        missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
        if missing:
            failures.append({"eventIndex": index, "missingFields": missing})
        ids.append(str(event.get("eventId")))
        if isinstance(event.get("positionMs"), int):
            positions.append(int(event["positionMs"]))
        else:
            failures.append({"eventIndex": index, "reason": "positionMs_not_int"})
        labels[str(event.get("eventType") or "<missing>")] += 1
    return {
        "requiredFields": REQUIRED_EVENT_FIELDS,
        "requiredFieldsPresent": len(failures) == 0 and bool(events),
        "adapterFailureCount": len(failures),
        "adapterFailuresSample": failures[:20],
        "eventIdUnique": len(ids) == len(set(ids)) and bool(ids),
        "positionMsMonotonicNonDecreasing": positions == sorted(positions),
        "eventCount": len(events),
        "distinctEventTypeCount": len(labels),
        "eventTypeCounts": dict(sorted(labels.items())),
    }


def _benchmark_contract(timeline: dict[str, Any] | None, adapter_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_BENCHMARK_PREP,
        "sourceBatch": "football_external_soccernet_event_adapter_smoke_test",
        "sourceDataset": (timeline or {}).get("sourceDataset"),
        "canonicalEventCount": adapter_audit.get("eventCount"),
        "requiredFieldsPresent": adapter_audit.get("requiredFieldsPresent"),
        "eventIdUnique": adapter_audit.get("eventIdUnique"),
        "positionMsMonotonicNonDecreasing": adapter_audit.get("positionMsMonotonicNonDecreasing"),
        "benchmarkAdapterPrepReady": bool(
            adapter_audit.get("requiredFieldsPresent")
            and adapter_audit.get("eventIdUnique")
            and adapter_audit.get("positionMsMonotonicNonDecreasing")
        ),
        "trainingUseAllowed": False,
        "videoDownloadAllowed": False,
    }


def _classify(fixture_ready: bool, adapter_audit: dict[str, Any], benchmark_contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not fixture_ready:
        return (
            BLOCKER_FIXTURE_MISSING,
            NEXT_FIXTURE,
            False,
            "SoccerNet canonical event fixture truth is missing or unsafe; rerun fixture materialization.",
        )
    if benchmark_contract.get("benchmarkAdapterPrepReady") is not True:
        return (
            BLOCKER_ADAPTER_CONTRACT,
            NEXT_CONTRACT_REPAIR,
            False,
            "SoccerNet event fixture failed the adapter smoke contract; repair mapping before benchmark prep.",
        )
    return (
        None,
        NEXT_BENCHMARK_PREP,
        True,
        "SoccerNet event adapter smoke passed. Advance to benchmark adapter contract prep; do not train or fetch videos.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_fixture_missing", "selected": primary_blocker == BLOCKER_FIXTURE_MISSING, "primaryBlocker": BLOCKER_FIXTURE_MISSING, "nextRecommendedNextLever": NEXT_FIXTURE},
            {"condition": "event_adapter_contract_gap", "selected": primary_blocker == BLOCKER_ADAPTER_CONTRACT, "primaryBlocker": BLOCKER_ADAPTER_CONTRACT, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "benchmark_adapter_contract_prep_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BENCHMARK_PREP},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Adapter Smoke Test",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Adapter smoke passed: `{summary.get('adapterSmokePassed')}`",
            f"- Canonical event count: `{summary.get('canonicalEventCount')}`",
            f"- Distinct event types: `{summary.get('distinctEventTypeCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_adapter_smoke_test(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_adapter_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _fixture_ready(inputs["fixtureSummary"], inputs["fixtureManifest"], inputs["canonicalTimeline"])
    adapter_audit = _event_adapter_audit(inputs["canonicalTimeline"])
    benchmark_contract = _benchmark_contract(inputs["canonicalTimeline"], adapter_audit)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, adapter_audit, benchmark_contract)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_adapter_smoke_test",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_adapter_fixture_materialization",
        "adapterSmokePassed": goal_achieved,
        "canonicalEventCount": adapter_audit.get("eventCount"),
        "distinctEventTypeCount": adapter_audit.get("distinctEventTypeCount"),
        "eventIdUnique": adapter_audit.get("eventIdUnique"),
        "positionMsMonotonicNonDecreasing": adapter_audit.get("positionMsMonotonicNonDecreasing"),
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
        "eventAdapterContractSmokeAudit": adapter_audit,
        "benchmarkAdapterPrepContract": benchmark_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_adapter_smoke_summary.json", summary)
    _write_json(output_root / "event_adapter_contract_smoke_audit.json", adapter_audit)
    _write_json(output_root / "benchmark_adapter_prep_contract.json", benchmark_contract)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_event_adapter_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_adapter_smoke_test(
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
