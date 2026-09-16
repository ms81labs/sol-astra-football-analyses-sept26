from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_safe_adapter_fixture_implementation as fixture_impl


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fixture_inputs(tmp_path: Path, *, goal: bool = True, download_executed: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    smoke_root = candidate_root / "football_external_safe_source_adapter_smoke_test_v1"
    resources = [
        {"resourceId": "soccertrack_v2", "coveredStages": ["tracking", "ball_localization"]},
        {"resourceId": "skillcorner_open_data", "coveredStages": ["calibration", "tracking", "ball_localization"]},
        {"resourceId": "statsbomb_open_data_360", "coveredStages": ["possession_event_semantics", "tactical_reporting"]},
    ]
    synthetic_rows = [
        {
            "resourceId": row["resourceId"],
            "FrameState": {
                "source": row["resourceId"],
                "matchId": f"{row['resourceId']}_synthetic_match",
                "frameIndex": index + 1,
                "timestampMs": (index + 1) * 100,
                "imagePath": f"synthetic://{row['resourceId']}/frame.jpg",
                "homography": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "players": [],
                "ball": {"visible": False},
                "events": [],
                "possession": None,
            },
            "GameState": {
                "matchId": f"{row['resourceId']}_synthetic_match",
                "frameIndex": index + 1,
                "timestampMs": (index + 1) * 100,
                "entities": [],
                "ball": {"visible": False},
                "teamInPossession": None,
                "phaseOfPlay": "unknown",
                "sourceConfidence": 1.0,
            },
            "datasetDownloadExecuted": False,
            "syntheticOnly": True,
        }
        for index, row in enumerate(resources)
    ]
    _write_json(
        smoke_root / "safe_source_adapter_smoke_summary.json",
        {
            "batchName": "football_external_safe_source_adapter_smoke_test",
            "goalAchieved": goal,
            "primaryBlocker": None if goal else "football_external_safe_source_adapter_schema_contract_gap",
            "safeSourceAdapterSmokePassed": goal,
            "safeSmokeResourceCount": len(resources),
            "syntheticFixtureRowCount": len(synthetic_rows),
            "datasetDownloadExecuted": download_executed,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_safe_adapter_fixture_implementation",
        },
    )
    _write_json(
        smoke_root / "safe_source_adapter_resource_manifest.json",
        {
            "datasetDownloadExecuted": download_executed,
            "safeSmokeResources": resources,
            "syntheticFixtureRows": synthetic_rows,
        },
    )
    _write_json(
        smoke_root / "dataset_download_guardrail_audit.json",
        {"downloadGuardrailPassed": not download_executed, "datasetDownloadExecuted": False, "violations": []},
    )
    return candidate_root


def test_fixture_implementation_writes_adapter_outputs_without_downloads(tmp_path: Path) -> None:
    candidate_root = _write_fixture_inputs(tmp_path)

    payload = fixture_impl.run_football_external_safe_adapter_fixture_implementation(storage_root=tmp_path)

    output_root = candidate_root / "football_external_safe_adapter_fixture_implementation_v1"
    manifest = json.loads((output_root / "adapter_fixture_manifest.json").read_text(encoding="utf-8"))
    roundtrip = json.loads((output_root / "fixture_roundtrip_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["adapterFixtureImplementationReady"] is True
    assert payload["fixtureResourceCount"] == 3
    assert payload["frameStateFixtureCount"] == 3
    assert payload["gameStateFixtureCount"] == 3
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_ingestion_plan"
    assert manifest["adapterImplementationMode"] == "synthetic_fixture_only"
    assert roundtrip["roundTripPassed"] is True
    assert (output_root / "canonical_frame_state_fixtures.json").exists()
    assert (output_root / "canonical_game_state_fixtures.json").exists()
    assert (output_root / "decision_matrix.json").exists()


def test_fixture_implementation_blocks_without_successful_smoke(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path, goal=False)

    payload = fixture_impl.run_football_external_safe_adapter_fixture_implementation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_safe_adapter_fixture_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_adapter_smoke_test"


def test_fixture_implementation_blocks_download_guardrail_regression(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path, download_executed=True)

    payload = fixture_impl.run_football_external_safe_adapter_fixture_implementation(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_safe_adapter_fixture_download_guardrail_violation"
    assert payload["datasetDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"


def test_fixture_implementation_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fixture_inputs(tmp_path)

    payload = fixture_impl.run_football_external_safe_adapter_fixture_implementation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "safe_adapter_fixture_materialization",
        "fixture_contract_repair",
        "safe_adapter_fixture_blocker_summary",
    ]
