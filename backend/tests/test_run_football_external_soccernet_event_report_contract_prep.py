from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_report_contract_prep as report_prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, smoke_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    smoke_root = candidate_root / "football_external_soccernet_event_benchmark_smoke_v1"
    _write_json(
        smoke_root / "soccernet_event_benchmark_smoke_summary.json",
        {
            "batchName": "football_external_soccernet_event_benchmark_smoke",
            "goalAchieved": smoke_goal,
            "primaryBlocker": None if smoke_goal else "football_external_soccernet_benchmark_adapter_prep_missing",
            "eventBenchmarkSmokePassed": smoke_goal,
            "eventCount": 4 if smoke_goal else 0,
            "distinctEventTypeCount": 3 if smoke_goal else 0,
            "eventRatePerMinute": 12.0 if smoke_goal else 0.0,
            "coveredStageIds": ["possession_event_semantics"] if smoke_goal else [],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_event_report_contract_prep",
        },
    )
    _write_json(
        smoke_root / "event_benchmark_smoke_metrics.json",
        {
            "eventCount": 4,
            "distinctEventTypeCount": 3,
            "eventRatePerMinute": 12.0,
            "durationMs": 20_000,
            "eventTypeCounts": {"PASS": 2, "DRIVE": 1, "SHOT": 1},
            "teamCounts": {"left": 3, "right": 1},
            "coveredStageIds": ["possession_event_semantics"],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
        },
    )
    _write_json(
        smoke_root / "event_report_prep_contract.json",
        {
            "contractName": "football_external_soccernet_event_report_contract_prep",
            "sourceBatch": "football_external_soccernet_event_benchmark_smoke",
            "eventCount": 4 if smoke_goal else 0,
            "distinctEventTypeCount": 3 if smoke_goal else 0,
            "eventRatePerMinute": 12.0 if smoke_goal else 0.0,
            "eventReportContractReady": smoke_goal,
            "coveredStageIds": ["possession_event_semantics"] if smoke_goal else [],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "trainingUseAllowed": False,
            "videoDownloadAllowed": False,
        },
    )
    return candidate_root


def test_event_report_contract_prep_writes_report_summary(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = report_prep.run_football_external_soccernet_event_report_contract_prep(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_report_contract_prep_v1"
    report_summary = json.loads((output_root / "soccernet_event_report_summary.json").read_text(encoding="utf-8"))
    limitations = json.loads((output_root / "event_report_limitations_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["reportContractReady"] is True
    assert payload["eventCount"] == 4
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_smoke"
    assert report_summary["topEventTypes"][0] == {"eventType": "PASS", "count": 2}
    assert limitations["fullMatchAnalysisReady"] is False
    assert "ball_localization" in limitations["uncoveredStageIds"]


def test_event_report_contract_prep_blocks_without_benchmark_truth(tmp_path: Path) -> None:
    _write_inputs(tmp_path, smoke_goal=False)

    payload = report_prep.run_football_external_soccernet_event_report_contract_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_benchmark_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_benchmark_smoke"


def test_event_report_contract_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = report_prep.run_football_external_soccernet_event_report_contract_prep(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_report_contract_prep",
        "soccernet_event_report_contract_repair",
        "soccernet_event_report_blocker_summary",
    ]
