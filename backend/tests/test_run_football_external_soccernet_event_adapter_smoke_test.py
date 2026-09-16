from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_event_adapter_smoke_test as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fixture_inputs(tmp_path: Path, *, fixture_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fixture_root = candidate_root / "football_external_soccernet_event_adapter_fixture_materialization_v1"
    _write_json(
        fixture_root / "soccernet_event_fixture_materialization_summary.json",
        {
            "batchName": "football_external_soccernet_event_adapter_fixture_materialization",
            "goalAchieved": fixture_goal,
            "primaryBlocker": None if fixture_goal else "football_external_soccernet_event_adapter_fixture_invalid",
            "canonicalEventCount": 2 if fixture_goal else 0,
            "distinctEventTypeCount": 2 if fixture_goal else 0,
            "eventFixtureQualityPassed": fixture_goal,
            "eventIdUnique": fixture_goal,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_event_adapter_smoke_test",
        },
    )
    _write_json(
        fixture_root / "soccernet_event_fixture_manifest.json",
        {
            "fixtureName": "soccernet_ball_action_spotting_valid_label_fixture",
            "sourceDataset": "SoccerNet SN-BAS-2025",
            "canonicalEventTimelinePath": "canonical_event_timeline.json",
            "canonicalEventCount": 2 if fixture_goal else 0,
            "qualityPassed": fixture_goal,
            "trainingUseAllowed": False,
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
    return candidate_root


def test_soccernet_event_adapter_smoke_passes_fixture_contract(tmp_path: Path) -> None:
    candidate_root = _write_fixture_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_adapter_smoke_test(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_event_adapter_smoke_test_v1"
    adapter_audit = json.loads((output_root / "event_adapter_contract_smoke_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["adapterSmokePassed"] is True
    assert payload["canonicalEventCount"] == 2
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_benchmark_adapter_contract_prep"
    assert adapter_audit["requiredFieldsPresent"] is True


def test_soccernet_event_adapter_smoke_blocks_without_fixture_truth(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path, fixture_goal=False)

    payload = smoke.run_football_external_soccernet_event_adapter_smoke_test(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_fixture_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_adapter_fixture_materialization"


def test_soccernet_event_adapter_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_event_adapter_smoke_test(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_adapter_smoke",
        "soccernet_event_adapter_contract_repair",
        "soccernet_event_adapter_smoke_blocker_summary",
    ]
