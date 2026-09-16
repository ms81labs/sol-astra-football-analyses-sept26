from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_report_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, prep_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    prep_root = candidate_root / "football_external_soccernet_event_report_contract_prep_v1"
    _write_json(
        prep_root / "soccernet_event_report_contract_prep_summary.json",
        {
            "batchName": "football_external_soccernet_event_report_contract_prep",
            "goalAchieved": prep_goal,
            "primaryBlocker": None if prep_goal else "football_external_soccernet_event_report_contract_gap",
            "reportContractReady": prep_goal,
            "eventCount": 4 if prep_goal else 0,
            "distinctEventTypeCount": 3 if prep_goal else 0,
            "eventRatePerMinute": 12.0 if prep_goal else 0.0,
            "fullMatchAnalysisReady": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_event_report_smoke",
        },
    )
    _write_json(
        prep_root / "soccernet_event_report_summary.json",
        {
            "reportName": "SoccerNet Event-Only Match Summary",
            "eventCount": 4,
            "distinctEventTypeCount": 3,
            "eventRatePerMinute": 12.0,
            "topEventTypes": [{"eventType": "PASS", "count": 2}, {"eventType": "DRIVE", "count": 1}],
            "teamEventSplit": [{"team": "left", "count": 3, "share": 0.75}, {"team": "right", "count": 1, "share": 0.25}],
            "coveredStageIds": ["possession_event_semantics"],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "fullMatchAnalysisReady": False,
            "reportSmokeReady": prep_goal,
        },
    )
    _write_json(
        prep_root / "event_report_smoke_contract.json",
        {
            "contractName": "football_external_soccernet_event_report_smoke",
            "sourceBatch": "football_external_soccernet_event_report_contract_prep",
            "reportSmokeReady": prep_goal,
            "eventCount": 4 if prep_goal else 0,
            "fullMatchAnalysisReady": False,
            "trainingUseAllowed": False,
            "videoDownloadAllowed": False,
        },
    )
    return candidate_root


def test_event_report_smoke_writes_renderable_report(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_report_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_report_smoke_v1"
    rendered = (output_root / "soccernet_event_only_report.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["eventReportSmokePassed"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_lane_closeout"
    assert "SoccerNet Event-Only Report" in rendered
    assert "PASS" in rendered


def test_event_report_smoke_accepts_event_frequency_limitation_wording(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)
    prep_root = candidate_root / "football_external_soccernet_event_report_contract_prep_v1"
    _write_json(
        prep_root / "event_report_limitations_audit.json",
        {
            "eventOnlyReport": True,
            "fullMatchAnalysisReady": False,
            "coveredStageIds": ["possession_event_semantics"],
            "uncoveredStageIds": ["ball_localization"],
            "plainEnglish": "This SoccerNet fixture supports event-frequency and event-taxonomy reporting only. It does not include video-derived localization.",
        },
    )

    payload = smoke.run_football_external_soccernet_event_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None


def test_event_report_smoke_blocks_without_contract_prep(tmp_path: Path) -> None:
    _write_inputs(tmp_path, prep_goal=False)

    payload = smoke.run_football_external_soccernet_event_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_report_contract_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_contract_prep"


def test_event_report_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_report_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_report_smoke",
        "soccernet_event_report_render_contract_repair",
        "soccernet_event_report_smoke_blocker_summary",
    ]
