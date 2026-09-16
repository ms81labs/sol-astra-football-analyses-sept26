from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_api_metadata_probe as metadata_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_probe_inputs(tmp_path: Path, *, approval_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_nda_api_access_approval_v1"
    _write_json(
        approval_root / "soccernet_nda_api_access_approval_summary.json",
        {
            "batchName": "football_external_soccernet_nda_api_access_approval",
            "goalAchieved": approval_goal,
            "primaryBlocker": None if approval_goal else "football_external_soccernet_manual_audit_missing",
            "soccernetNdaAccessAvailable": approval_goal,
            "controlledApiMetadataProbeReady": approval_goal,
            "credentialPersisted": False,
            "passwordRedacted": True,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccernet_api_metadata_probe",
        },
    )
    _write_json(
        approval_root / "soccernet_api_access_contract.json",
        {
            "resourceId": "soccernet_broadcast_tasks",
            "pythonPackageName": "SoccerNet",
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersisted": False,
            "passwordRedacted": True,
            "approvedProbeScope": "api_metadata_or_listing_only",
            "fullOriginalVideoDownloadApproved": False,
            "trainingUseAllowed": False,
        },
    )
    return candidate_root


def _package_probe(*, package: bool = True, downloader: bool = True) -> dict[str, object]:
    return {
        "packageImportReady": package,
        "downloaderImportReady": downloader,
        "packageName": "SoccerNet",
        "downloaderClassName": "SoccerNetDownloader" if downloader else None,
        "packageVersion": "0.test",
    }


def test_api_metadata_probe_passes_with_package_and_runtime_credential(tmp_path: Path) -> None:
    candidate_root = _write_probe_inputs(tmp_path)

    payload = metadata_probe.run_football_external_soccernet_api_metadata_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        package_probe=lambda: _package_probe(),
    )

    output_root = candidate_root / "football_external_soccernet_api_metadata_probe_v1"
    package_audit = json.loads((output_root / "soccernet_api_package_audit.json").read_text(encoding="utf-8"))
    credential_audit = json.loads((output_root / "credential_runtime_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["apiPackageImportReady"] is True
    assert payload["apiDownloaderImportReady"] is True
    assert payload["credentialRuntimeAvailable"] is True
    assert payload["credentialPersisted"] is False
    assert payload["apiMetadataProbeReady"] is True
    assert payload["apiCallExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_listing_probe"
    assert package_audit["downloaderClassName"] == "SoccerNetDownloader"
    assert credential_audit["credentialPersisted"] is False
    assert "redacted-test-secret" not in json.dumps(credential_audit)


def test_api_metadata_probe_blocks_without_runtime_credential(tmp_path: Path) -> None:
    _write_probe_inputs(tmp_path)

    payload = metadata_probe.run_football_external_soccernet_api_metadata_probe(
        storage_root=tmp_path,
        env={},
        package_probe=lambda: _package_probe(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_credential_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_secret_env_setup"
    assert payload["credentialPersisted"] is False
    assert payload["datasetDownloadExecuted"] is False


def test_api_metadata_probe_blocks_without_package(tmp_path: Path) -> None:
    _write_probe_inputs(tmp_path)

    payload = metadata_probe.run_football_external_soccernet_api_metadata_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        package_probe=lambda: _package_probe(package=False, downloader=False),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_package_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_package_install"
    assert payload["apiCallExecuted"] is False


def test_api_metadata_probe_blocks_without_approval(tmp_path: Path) -> None:
    _write_probe_inputs(tmp_path, approval_goal=False)

    payload = metadata_probe.run_football_external_soccernet_api_metadata_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        package_probe=lambda: _package_probe(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_nda_api_access_approval"


def test_api_metadata_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_probe_inputs(tmp_path)

    payload = metadata_probe.run_football_external_soccernet_api_metadata_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        package_probe=lambda: _package_probe(),
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_api_package_and_credential_probe",
        "soccernet_api_probe_contract_repair",
        "soccernet_api_probe_blocker_summary",
    ]
