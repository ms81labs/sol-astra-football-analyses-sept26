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
DEFAULT_SMOKE_DIR_NAME = "football_external_safe_source_adapter_smoke_test_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_safe_adapter_fixture_implementation_v1"

BLOCKER_SMOKE_MISSING = "football_external_safe_adapter_fixture_smoke_missing"
BLOCKER_DOWNLOAD_GUARDRAIL = "football_external_safe_adapter_fixture_download_guardrail_violation"
BLOCKER_FIXTURE_CONTRACT = "football_external_safe_adapter_fixture_contract_gap"

NEXT_SAFE_SMOKE = "football_external_safe_source_adapter_smoke_test"
NEXT_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_CONTRACT_REPAIR = "football_external_safe_adapter_fixture_contract_repair"
NEXT_SAMPLE_INGESTION_PLAN = "football_external_safe_source_sample_ingestion_plan"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "safe_adapter_fixture_materialization",
            "successCriteria": [
                "materialize canonical FrameState and GameState fixture files from safe synthetic smoke rows",
                "round-trip fixture rows without dropping resource identity or frame identity",
                "preserve no-download, no-training, no-promotion, and no-runtime-mutation invariants",
            ],
            "failureAdaptation": "If fixture rows are malformed, move to fixture-contract repair using saved smoke artifacts only.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "fixture_contract_repair",
            "successCriteria": [
                "repair missing fixture metadata without fetching data",
                "keep rows synthetic and evidence-only",
                "write a manifest that names remaining schema gaps",
            ],
            "failureAdaptation": "If fixture materialization still fails, write a blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "safe_adapter_fixture_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not execute external downloads or benchmark runs",
            ],
            "failureAdaptation": "Stop after blocker truth; do not advance to sample ingestion.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    smoke_root = candidate_root / DEFAULT_SMOKE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "smokeRoot": smoke_root,
        "smokeSummary": _load_json(smoke_root / "safe_source_adapter_smoke_summary.json"),
        "resourceManifest": _load_json(smoke_root / "safe_source_adapter_resource_manifest.json"),
        "downloadAudit": _load_json(smoke_root / "dataset_download_guardrail_audit.json"),
    }


def _synthetic_rows(resource_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (resource_manifest or {}).get("syntheticFixtureRows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _resource_rows(resource_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (resource_manifest or {}).get("safeSmokeResources")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _materialize_frame_states(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame_states: list[dict[str, Any]] = []
    for row in rows:
        frame_state = row.get("FrameState")
        if not isinstance(frame_state, dict):
            continue
        payload = dict(frame_state)
        payload["resourceId"] = row.get("resourceId")
        payload["adapterFixtureKind"] = "FrameState"
        payload["syntheticOnly"] = True
        frame_states.append(payload)
    return frame_states


def _materialize_game_states(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    game_states: list[dict[str, Any]] = []
    for row in rows:
        game_state = row.get("GameState")
        if not isinstance(game_state, dict):
            continue
        payload = dict(game_state)
        payload["resourceId"] = row.get("resourceId")
        payload["adapterFixtureKind"] = "GameState"
        payload["syntheticOnly"] = True
        game_states.append(payload)
    return game_states


def _download_guardrail(
    smoke_summary: dict[str, Any] | None,
    resource_manifest: dict[str, Any] | None,
    download_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if bool((smoke_summary or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "smokeSummary", "field": "datasetDownloadExecuted"})
    if bool((resource_manifest or {}).get("datasetDownloadExecuted")):
        violations.append({"scope": "resourceManifest", "field": "datasetDownloadExecuted"})
    if (download_audit or {}).get("downloadGuardrailPassed") is False:
        violations.append({"scope": "downloadAudit", "field": "downloadGuardrailPassed"})
    return {
        "downloadGuardrailPassed": not violations,
        "violationCount": len(violations),
        "violations": violations,
        "datasetDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
    }


def _roundtrip_audit(frame_states: list[dict[str, Any]], game_states: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_ids = [str(row.get("resourceId")) for row in rows]
    frame_ids = [str(row.get("resourceId")) for row in frame_states]
    game_ids = [str(row.get("resourceId")) for row in game_states]
    missing_frame = sorted(set(source_ids) - set(frame_ids))
    missing_game = sorted(set(source_ids) - set(game_ids))
    missing_frame_identity = [
        row.get("resourceId")
        for row in frame_states
        if "matchId" not in row or "frameIndex" not in row or "timestampMs" not in row
    ]
    missing_game_identity = [
        row.get("resourceId")
        for row in game_states
        if "matchId" not in row or "frameIndex" not in row or "timestampMs" not in row
    ]
    return {
        "sourceSyntheticRowCount": len(rows),
        "frameStateFixtureCount": len(frame_states),
        "gameStateFixtureCount": len(game_states),
        "missingFrameStateResourceIds": missing_frame,
        "missingGameStateResourceIds": missing_game,
        "missingFrameIdentityResourceIds": missing_frame_identity,
        "missingGameIdentityResourceIds": missing_game_identity,
        "roundTripPassed": (
            len(rows) > 0
            and len(frame_states) == len(rows)
            and len(game_states) == len(rows)
            and not missing_frame
            and not missing_game
            and not missing_frame_identity
            and not missing_game_identity
        ),
    }


def _classify(
    *,
    smoke_summary: dict[str, Any] | None,
    download_audit: dict[str, Any],
    roundtrip_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(smoke_summary, dict)
        and smoke_summary.get("goalAchieved") is True
        and smoke_summary.get("safeSourceAdapterSmokePassed") is True
    ):
        return (
            BLOCKER_SMOKE_MISSING,
            NEXT_SAFE_SMOKE,
            False,
            "Safe-source adapter smoke truth is missing or failed; rerun smoke before fixture materialization.",
        )
    if not download_audit["downloadGuardrailPassed"]:
        return (
            BLOCKER_DOWNLOAD_GUARDRAIL,
            NEXT_ACCESS_REVIEW,
            False,
            "Download guardrail regressed; return to dataset access review before materializing fixtures.",
        )
    if not roundtrip_audit["roundTripPassed"]:
        return (
            BLOCKER_FIXTURE_CONTRACT,
            NEXT_CONTRACT_REPAIR,
            False,
            "Synthetic adapter fixture rows did not round-trip through canonical FrameState/GameState outputs.",
        )
    return (
        None,
        NEXT_SAMPLE_INGESTION_PLAN,
        True,
        "Safe adapter fixture implementation passed on synthetic approved-source fixtures. Plan sample ingestion next; do not download datasets, train, promote, or mutate runtime defaults.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Safe Adapter Fixture Implementation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Fixture resources: `{summary.get('fixtureResourceCount')}`",
            f"- FrameState fixtures: `{summary.get('frameStateFixtureCount')}`",
            f"- GameState fixtures: `{summary.get('gameStateFixtureCount')}`",
            f"- Round trip passed: `{summary.get('fixtureRoundTripPassed')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_safe_adapter_fixture_implementation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "safe_adapter_fixture_materialization",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    resources = _resource_rows(inputs["resourceManifest"])
    synthetic_rows = _synthetic_rows(inputs["resourceManifest"])
    frame_states = _materialize_frame_states(synthetic_rows)
    game_states = _materialize_game_states(synthetic_rows)
    download_audit = _download_guardrail(inputs["smokeSummary"], inputs["resourceManifest"], inputs["downloadAudit"])
    roundtrip_audit = _roundtrip_audit(frame_states, game_states, synthetic_rows)
    attempts = _attempt_plan()
    primary_blocker, next_lever, goal_achieved, english = _classify(
        smoke_summary=inputs["smokeSummary"],
        download_audit=download_audit,
        roundtrip_audit=roundtrip_audit,
    )
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_safe_adapter_fixture_implementation",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_safe_source_adapter_smoke_test",
        "adapterImplementationMode": "synthetic_fixture_only",
        "adapterFixtureImplementationReady": goal_achieved,
        "fixtureResourceCount": len(resources),
        "frameStateFixtureCount": len(frame_states),
        "gameStateFixtureCount": len(game_states),
        "fixtureRoundTripPassed": roundtrip_audit["roundTripPassed"],
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "fullExternalBenchmarkExecutionReady": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    manifest = {
        "generatedAt": generated_at,
        "adapterImplementationMode": "synthetic_fixture_only",
        "sourceBatch": "football_external_safe_source_adapter_smoke_test",
        "resources": resources,
        "fixtureOutputs": {
            "frameStates": "canonical_frame_state_fixtures.json",
            "gameStates": "canonical_game_state_fixtures.json",
        },
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "safe_smoke_missing", "selected": primary_blocker == BLOCKER_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_SAFE_SMOKE},
            {"condition": "download_guardrail_violation", "selected": primary_blocker == BLOCKER_DOWNLOAD_GUARDRAIL, "nextRecommendedNextLever": NEXT_ACCESS_REVIEW},
            {"condition": "fixture_contract_gap", "selected": primary_blocker == BLOCKER_FIXTURE_CONTRACT, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "fixture_implementation_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_SAMPLE_INGESTION_PLAN},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "adapterFixtureManifest": manifest,
        "fixtureRoundtripAudit": roundtrip_audit,
        "datasetDownloadGuardrailAudit": download_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "safe_adapter_fixture_implementation_summary.json", summary)
    _write_json(output_root / "adapter_fixture_manifest.json", manifest)
    _write_json(output_root / "canonical_frame_state_fixtures.json", {"frameStates": frame_states})
    _write_json(output_root / "canonical_game_state_fixtures.json", {"gameStates": game_states})
    _write_json(output_root / "fixture_roundtrip_audit.json", roundtrip_audit)
    _write_json(output_root / "dataset_download_guardrail_audit.json", download_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize safe external-source adapter fixtures from synthetic smoke rows.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="safe_adapter_fixture_materialization")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_safe_adapter_fixture_implementation(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
