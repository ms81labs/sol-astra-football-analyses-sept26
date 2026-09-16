from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_safe_source_sample_ingestion_plan as ingestion_plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resource(resource_id: str, *, priority: int = 1, download_allowed: bool = False) -> dict[str, object]:
    return {
        "resourceId": resource_id,
        "resourceName": resource_id.replace("_", " ").title(),
        "accessDecision": "approved_smoke_only",
        "accessRiskClass": "low_with_attribution",
        "adapterPriority": priority,
        "benchmarkSmokeUseAllowed": True,
        "coveredStages": ["tracking", "ball_localization"],
        "downloadAllowedByThisBatch": download_allowed,
        "executionStatus": "not_downloaded",
        "officialSourceUrls": [f"https://example.invalid/{resource_id}"],
        "trainingUseAllowed": False,
    }


def _write_plan_inputs(
    tmp_path: Path,
    *,
    fixture_goal: bool = True,
    resources: list[dict[str, object]] | None = None,
    download_executed: bool = False,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fixture_root = candidate_root / "football_external_safe_adapter_fixture_implementation_v1"
    resources = resources if resources is not None else [
        _resource("soccertrack_v2", priority=1),
        _resource("skillcorner_open_data", priority=3),
        _resource("statsbomb_open_data_360", priority=5),
    ]
    _write_json(
        fixture_root / "safe_adapter_fixture_implementation_summary.json",
        {
            "batchName": "football_external_safe_adapter_fixture_implementation",
            "goalAchieved": fixture_goal,
            "primaryBlocker": None if fixture_goal else "football_external_safe_adapter_fixture_contract_gap",
            "adapterFixtureImplementationReady": fixture_goal,
            "fixtureResourceCount": len(resources),
            "frameStateFixtureCount": len(resources),
            "gameStateFixtureCount": len(resources),
            "fixtureRoundTripPassed": fixture_goal,
            "datasetDownloadExecuted": download_executed,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_safe_source_sample_ingestion_plan",
        },
    )
    _write_json(
        fixture_root / "adapter_fixture_manifest.json",
        {
            "adapterImplementationMode": "synthetic_fixture_only",
            "datasetDownloadExecuted": download_executed,
            "resources": resources,
            "fixtureOutputs": {
                "frameStates": "canonical_frame_state_fixtures.json",
                "gameStates": "canonical_game_state_fixtures.json",
            },
        },
    )
    _write_json(
        fixture_root / "fixture_roundtrip_audit.json",
        {
            "roundTripPassed": fixture_goal,
            "sourceSyntheticRowCount": len(resources),
            "frameStateFixtureCount": len(resources),
            "gameStateFixtureCount": len(resources),
        },
    )
    _write_json(
        fixture_root / "dataset_download_guardrail_audit.json",
        {"downloadGuardrailPassed": not download_executed, "datasetDownloadExecuted": False, "violations": []},
    )
    return candidate_root


def test_sample_ingestion_plan_writes_download_approval_gated_plan(tmp_path: Path) -> None:
    candidate_root = _write_plan_inputs(tmp_path)

    payload = ingestion_plan.run_football_external_safe_source_sample_ingestion_plan(storage_root=tmp_path)

    output_root = candidate_root / "football_external_safe_source_sample_ingestion_plan_v1"
    approval = json.loads((output_root / "sample_download_approval_checklist.json").read_text(encoding="utf-8"))
    sequence = json.loads((output_root / "controlled_sample_ingestion_sequence.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "sample_ingestion_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["sampleIngestionPlanReady"] is True
    assert payload["selectedFirstSampleResourceId"] == "soccertrack_v2"
    assert payload["sampleDownloadApprovalRequired"] is True
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_download_approval"
    assert approval["approvalRequiredBeforeDownload"] is True
    assert sequence["steps"][0]["action"] == "manual_license_confirmation"
    assert guardrail["sampleIngestionGuardrailPassed"] is True
    assert (output_root / "safe_source_sample_ingestion_plan_summary.json").exists()
    assert (output_root / "decision_matrix.json").exists()


def test_sample_ingestion_plan_blocks_without_fixture_implementation(tmp_path: Path) -> None:
    _write_plan_inputs(tmp_path, fixture_goal=False)

    payload = ingestion_plan.run_football_external_safe_source_sample_ingestion_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_sample_ingestion_fixture_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_adapter_fixture_implementation"
    assert payload["sampleDownloadExecuted"] is False


def test_sample_ingestion_plan_blocks_download_guardrail_regression(tmp_path: Path) -> None:
    _write_plan_inputs(tmp_path, download_executed=True)

    payload = ingestion_plan.run_football_external_safe_source_sample_ingestion_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_sample_ingestion_download_guardrail_violation"
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"
    assert payload["datasetDownloadExecuted"] is False


def test_sample_ingestion_plan_blocks_when_no_safe_resource_available(tmp_path: Path) -> None:
    _write_plan_inputs(tmp_path, resources=[])

    payload = ingestion_plan.run_football_external_safe_source_sample_ingestion_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_sample_ingestion_no_safe_resource"
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"


def test_sample_ingestion_plan_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_plan_inputs(tmp_path)

    payload = ingestion_plan.run_football_external_safe_source_sample_ingestion_plan(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "safe_source_sample_ingestion_plan",
        "sample_ingestion_access_contract_repair",
        "sample_ingestion_blocker_summary",
    ]
