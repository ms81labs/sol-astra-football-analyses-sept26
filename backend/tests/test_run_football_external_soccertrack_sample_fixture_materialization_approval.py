from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_sample_fixture_materialization_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_contract_inputs(tmp_path: Path, *, ready: bool = True, guardrail_passed: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    contract_root = candidate_root / "football_external_soccertrack_sample_ingestion_contract_prep_v1"
    _write_json(
        contract_root / "soccertrack_sample_ingestion_contract_prep_summary.json",
        {
            "batchName": "football_external_soccertrack_sample_ingestion_contract_prep",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_soccertrack_sample_mapping_incomplete",
            "sampleIngestionContractReady": ready,
            "selectedSampleResourceId": "soccertrack_v2",
            "requiredTaskFixtures": ["gsr", "bas", "mot"],
            "mappingCompletenessPassed": ready,
            "sampleDownloadApprovalRequired": True,
            "sampleDownloadApproved": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_sample_fixture_materialization_approval",
        },
    )
    _write_json(
        contract_root / "soccertrack_sample_ingestion_contract.json",
        {
            "schemaVersion": "soccertrack_sample_ingestion_contract_v1",
            "selectedSampleResourceId": "soccertrack_v2",
            "requiredTaskIds": ["gsr", "bas", "mot"],
            "schemaToAdapterMappingReady": ready,
            "allowedUse": "adapter_fixture_materialization_only_after_approval",
            "trainingUseAllowed": False,
            "sampleDownloadApproved": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "fullDatasetDownloadApproved": False,
        },
    )
    _write_json(
        contract_root / "soccertrack_sample_fixture_materialization_plan.json",
        {
            "schemaVersion": "soccertrack_sample_fixture_materialization_plan_v1",
            "materializationApproved": False,
            "materializationExecuted": False,
            "requiredTaskFixtures": ["gsr", "bas", "mot"],
            "approvalRequiredBeforeMaterialization": True,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    _write_json(
        contract_root / "download_scope_guardrail_audit.json",
        {
            "downloadScopeGuardrailPassed": guardrail_passed,
            "violationCount": 0 if guardrail_passed else 1,
            "sampleDownloadApproved": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def test_soccertrack_sample_fixture_materialization_approval_opens_controlled_fetch_only(tmp_path: Path) -> None:
    candidate_root = _write_contract_inputs(tmp_path)

    payload = approval.run_football_external_soccertrack_sample_fixture_materialization_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_sample_fixture_materialization_approval_v1"
    contract = json.loads((output_root / "soccertrack_sample_fixture_materialization_approval_contract.json").read_text(encoding="utf-8"))
    scope = json.loads((output_root / "approved_sample_scope.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "approval_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["sampleFixtureMaterializationApproved"] is True
    assert payload["sampleDownloadApproved"] is True
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadApproved"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_controlled_sample_fetch"
    assert contract["approvedUse"] == "adapter_fixture_materialization_only"
    assert contract["fullDatasetDownloadApproved"] is False
    assert scope["maxSampleMatches"] == 1
    assert guardrail["approvalGuardrailPassed"] is True


def test_soccertrack_sample_fixture_materialization_approval_blocks_without_contract(tmp_path: Path) -> None:
    _write_contract_inputs(tmp_path, ready=False)

    payload = approval.run_football_external_soccertrack_sample_fixture_materialization_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_sample_ingestion_contract_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_ingestion_contract_prep"


def test_soccertrack_sample_fixture_materialization_approval_blocks_guardrail_regression(tmp_path: Path) -> None:
    _write_contract_inputs(tmp_path, guardrail_passed=False)

    payload = approval.run_football_external_soccertrack_sample_fixture_materialization_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_sample_fixture_approval_guardrail_failed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_ingestion_contract_prep"
    assert payload["sampleDownloadExecuted"] is False


def test_soccertrack_sample_fixture_materialization_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_contract_inputs(tmp_path)

    payload = approval.run_football_external_soccertrack_sample_fixture_materialization_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_sample_fixture_materialization_approval",
        "soccertrack_sample_fixture_approval_contract_repair",
        "soccertrack_sample_fixture_approval_blocker_summary",
    ]
