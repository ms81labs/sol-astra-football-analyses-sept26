from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_benchmark_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, prep_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    prep_root = candidate_root / "football_external_soccernet_benchmark_adapter_contract_prep_v1"
    _write_json(
        prep_root / "soccernet_benchmark_adapter_contract_prep_summary.json",
        {
            "batchName": "football_external_soccernet_benchmark_adapter_contract_prep",
            "goalAchieved": prep_goal,
            "primaryBlocker": None if prep_goal else "football_external_soccernet_benchmark_adapter_schema_gap",
            "eventStreamRowCount": 2 if prep_goal else 0,
            "ballActionEventRowCount": 2 if prep_goal else 0,
            "coveredStageIds": ["possession_event_semantics"] if prep_goal else [],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "eventBenchmarkSmokeReady": prep_goal,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_event_benchmark_smoke",
        },
    )
    _write_json(
        prep_root / "soccernet_event_stream_fixture.json",
        {
            "schema": "EventStream",
            "rowCount": 2,
            "rows": [
                {"eventId": "evt-1", "timestampMs": 1000, "teamId": "left", "playerId": None, "eventType": "PASS", "pitchX": None, "pitchY": None},
                {"eventId": "evt-2", "timestampMs": 5000, "teamId": "right", "playerId": None, "eventType": "DRIVE", "pitchX": None, "pitchY": None},
            ],
        },
    )
    _write_json(
        prep_root / "soccernet_stage_coverage_audit.json",
        {
            "coveredStageIds": ["possession_event_semantics"] if prep_goal else [],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "eventOnlySource": True,
            "fullBenchmarkExecutionReady": False,
            "eventBenchmarkSmokeReady": prep_goal,
        },
    )
    return candidate_root


def test_event_benchmark_smoke_computes_event_metrics(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_benchmark_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_benchmark_smoke_v1"
    metrics = json.loads((output_root / "event_benchmark_smoke_metrics.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["eventBenchmarkSmokePassed"] is True
    assert payload["eventCount"] == 2
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_contract_prep"
    assert metrics["eventTypeCounts"] == {"DRIVE": 1, "PASS": 1}
    assert metrics["eventRatePerMinute"] == 30.0


def test_event_benchmark_smoke_blocks_without_adapter_prep(tmp_path: Path) -> None:
    _write_inputs(tmp_path, prep_goal=False)

    payload = smoke.run_football_external_soccernet_event_benchmark_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_benchmark_adapter_prep_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_benchmark_adapter_contract_prep"


def test_event_benchmark_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_benchmark_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_benchmark_smoke",
        "soccernet_event_benchmark_contract_repair",
        "soccernet_event_benchmark_blocker_summary",
    ]
