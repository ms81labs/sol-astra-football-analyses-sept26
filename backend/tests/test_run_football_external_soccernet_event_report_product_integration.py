from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_report_product_integration as integration


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, closeout_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    closeout_root = candidate_root / "football_external_soccernet_event_lane_closeout_v1"
    report_root = candidate_root / "football_external_soccernet_event_report_smoke_v1"
    prep_root = candidate_root / "football_external_soccernet_event_report_contract_prep_v1"
    _write_json(
        closeout_root / "soccernet_event_lane_closeout_summary.json",
        {
            "batchName": "football_external_soccernet_event_lane_closeout",
            "goalAchieved": closeout_goal,
            "primaryBlocker": None if closeout_goal else "football_external_soccernet_event_lane_artifact_inventory_gap",
            "eventOnlyLaneClosed": closeout_goal,
            "eventCount": 1604 if closeout_goal else 0,
            "distinctEventTypeCount": 12 if closeout_goal else 0,
            "fullMatchAnalysisReady": False,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        closeout_root / "remaining_gap_analysis.json",
        {
            "remainingUnprovenStages": [
                "camera_shot_gate",
                "calibration",
                "tracking",
                "ball_localization",
                "tactical_reporting",
                "full_original_video_analysis",
            ],
        },
    )
    _write_json(
        prep_root / "soccernet_event_report_summary.json",
        {
            "reportName": "SoccerNet Event-Only Match Summary",
            "sourceDataset": "SoccerNet SN-BAS-2025",
            "eventCount": 1604,
            "distinctEventTypeCount": 12,
            "eventRatePerMinute": 16.393666,
            "topEventTypes": [{"eventType": "PASS", "count": 585}, {"eventType": "DRIVE", "count": 554}],
            "teamEventSplit": [{"team": "left", "count": 813, "share": 0.506858}, {"team": "right", "count": 791, "share": 0.493142}],
            "coveredStageIds": ["possession_event_semantics"],
            "uncoveredStageIds": ["camera_shot_gate", "calibration", "tracking", "ball_localization", "tactical_reporting"],
            "fullMatchAnalysisReady": False,
        },
    )
    (report_root / "soccernet_event_only_report.md").parent.mkdir(parents=True, exist_ok=True)
    (report_root / "soccernet_event_only_report.md").write_text("# SoccerNet Event-Only Report\n\n- Events: `1604`\n", encoding="utf-8")
    return candidate_root


def test_event_report_product_integration_writes_safe_payload(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = integration.run_football_external_soccernet_event_report_product_integration(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_report_product_integration_v1"
    product_payload = json.loads((output_root / "product_event_report_payload.json").read_text(encoding="utf-8"))
    copy = json.loads((output_root / "product_ui_copy.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productEventReportReady"] is True
    assert payload["fullMatchAnalysisReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_sample_download_approval"
    assert product_payload["readiness"]["eventOnlyReportReady"] is True
    assert product_payload["readiness"]["fullMatchAnalysisReady"] is False
    assert "not a full video-analysis report" in copy["limitationsBanner"]


def test_event_report_product_integration_blocks_without_closeout(tmp_path: Path) -> None:
    _write_inputs(tmp_path, closeout_goal=False)

    payload = integration.run_football_external_soccernet_event_report_product_integration(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_lane_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_lane_closeout"


def test_event_report_product_integration_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = integration.run_football_external_soccernet_event_report_product_integration(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_report_product_payload",
        "soccernet_event_report_product_contract_repair",
        "soccernet_event_report_product_blocker_summary",
    ]
