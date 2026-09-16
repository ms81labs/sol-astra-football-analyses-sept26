from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_benchmark_adapter_contract_prep as prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, smoke_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    smoke_root = candidate_root / "football_external_soccernet_event_adapter_smoke_test_v1"
    fixture_root = candidate_root / "football_external_soccernet_event_adapter_fixture_materialization_v1"
    harness_root = candidate_root / "football_external_benchmark_harness_prep_v1"
    _write_json(
        smoke_root / "soccernet_event_adapter_smoke_summary.json",
        {
            "batchName": "football_external_soccernet_event_adapter_smoke_test",
            "goalAchieved": smoke_goal,
            "primaryBlocker": None if smoke_goal else "football_external_soccernet_event_fixture_missing",
            "adapterSmokePassed": smoke_goal,
            "canonicalEventCount": 2 if smoke_goal else 0,
            "distinctEventTypeCount": 2 if smoke_goal else 0,
            "eventIdUnique": smoke_goal,
            "positionMsMonotonicNonDecreasing": smoke_goal,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_benchmark_adapter_contract_prep",
        },
    )
    _write_json(
        smoke_root / "benchmark_adapter_prep_contract.json",
        {
            "contractName": "football_external_soccernet_benchmark_adapter_contract_prep",
            "sourceBatch": "football_external_soccernet_event_adapter_smoke_test",
            "sourceDataset": "SoccerNet SN-BAS-2025",
            "canonicalEventCount": 2 if smoke_goal else 0,
            "benchmarkAdapterPrepReady": smoke_goal,
            "trainingUseAllowed": False,
            "videoDownloadAllowed": False,
        },
    )
    _write_json(
        fixture_root / "canonical_event_timeline.json",
        {
            "sourceDataset": "SoccerNet SN-BAS-2025",
            "eventCount": 2,
            "events": [
                {"eventId": "evt-1", "sourceGameId": "game", "period": 1, "positionMs": 1160, "eventType": "PASS", "team": "left", "visibility": "visible"},
                {"eventId": "evt-2", "sourceGameId": "game", "period": 1, "positionMs": 2840, "eventType": "DRIVE", "team": "right", "visibility": "visible"},
            ],
        },
    )
    _write_json(
        harness_root / "dataset_adapter_contract.json",
        {
            "externalBenchmarkExecutionReady": False,
            "adapterImplementationStatus": "contract_only",
            "schemas": {
                "EventStream": {"requiredFields": ["eventId", "timestampMs", "teamId", "playerId", "eventType", "pitchX", "pitchY"]},
                "BallActionEvent": {"requiredFields": ["eventId", "frameIndex", "eventType", "ballPitchX", "ballPitchY", "confidence"]},
            },
        },
    )
    _write_json(
        harness_root / "stage_gate_contract.json",
        {
            "requiredStageCoverage": [
                "camera_shot_gate",
                "calibration",
                "tracking",
                "ball_localization",
                "possession_event_semantics",
                "tactical_reporting",
            ]
        },
    )
    return candidate_root


def test_benchmark_adapter_contract_prep_maps_events_and_stage_coverage(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = prep.run_football_external_soccernet_benchmark_adapter_contract_prep(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_benchmark_adapter_contract_prep_v1"
    stage_audit = json.loads((output_root / "soccernet_stage_coverage_audit.json").read_text(encoding="utf-8"))
    adapter_manifest = json.loads((output_root / "soccernet_benchmark_adapter_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["eventStreamRowCount"] == 2
    assert payload["coveredStageIds"] == ["possession_event_semantics"]
    assert payload["uncoveredStageIds"] == ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"]
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_benchmark_smoke"
    assert stage_audit["eventOnlySource"] is True
    assert adapter_manifest["benchmarkAdapterContractReady"] is True


def test_benchmark_adapter_contract_prep_blocks_without_smoke_truth(tmp_path: Path) -> None:
    _write_inputs(tmp_path, smoke_goal=False)

    payload = prep.run_football_external_soccernet_benchmark_adapter_contract_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_adapter_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_adapter_smoke_test"


def test_benchmark_adapter_contract_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = prep.run_football_external_soccernet_benchmark_adapter_contract_prep(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_benchmark_adapter_contract_prep",
        "soccernet_benchmark_adapter_contract_repair",
        "soccernet_benchmark_adapter_blocker_summary",
    ]
