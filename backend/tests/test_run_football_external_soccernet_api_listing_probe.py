from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_api_listing_probe as listing_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_listing_inputs(
    tmp_path: Path,
    *,
    metadata_goal: bool = True,
    include_python_path: bool = True,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_nda_api_access_approval_v1"
    metadata_root = candidate_root / "football_external_soccernet_api_metadata_probe_v1"
    _write_json(
        approval_root / "soccernet_api_access_contract.json",
        {
            "resourceId": "soccernet_broadcast_tasks",
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersisted": False,
            "passwordRedacted": True,
            "approvedProbeScope": "api_metadata_or_listing_only",
            "fullOriginalVideoDownloadApproved": False,
            "trainingUseAllowed": False,
        },
    )
    _write_json(
        metadata_root / "soccernet_api_metadata_probe_summary.json",
        {
            "batchName": "football_external_soccernet_api_metadata_probe",
            "goalAchieved": metadata_goal,
            "primaryBlocker": None if metadata_goal else "football_external_soccernet_api_credential_missing",
            "apiPackageImportReady": metadata_goal,
            "apiDownloaderImportReady": metadata_goal,
            "apiPackageVersion": "0.test",
            "credentialRuntimeAvailable": metadata_goal,
            "credentialPersisted": False,
            "passwordRedacted": True,
            "apiCallExecuted": False,
            "apiListingExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccernet_api_listing_probe",
        },
    )
    package_audit: dict[str, object] = {
        "packageName": "SoccerNet",
        "packageImportReady": metadata_goal,
        "downloaderImportReady": metadata_goal,
        "packageVersion": "0.test",
    }
    if include_python_path:
        package_audit["pythonExecutable"] = str(tmp_path / "fake-venv" / "bin" / "python")
    _write_json(metadata_root / "soccernet_api_package_audit.json", package_audit)
    return candidate_root


def _local_index_probe() -> dict[str, object]:
    return {
        "listingSource": "package_local_index",
        "networkApiCallExecuted": False,
        "listedTaskCount": 2,
        "totalListedGameRefs": 6,
        "taskSplitCounts": {
            "spotting": {"train": 2, "valid": 1},
            "spotting-ball": {"train": 2, "valid": 1},
        },
        "sampleGameRefs": {
            "spotting": {"train": ["england_epl/2014-2015/a"], "valid": ["france_ligue-1/2015-2016/b"]},
            "spotting-ball": {"train": ["england_epl/2014-2015/a"], "valid": ["france_ligue-1/2015-2016/b"]},
        },
        "listingErrors": [],
    }


def test_api_listing_probe_lists_local_package_indexes_without_downloads(tmp_path: Path) -> None:
    candidate_root = _write_listing_inputs(tmp_path)

    payload = listing_probe.run_football_external_soccernet_api_listing_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        listing_probe=lambda _python: _local_index_probe(),
    )

    output_root = candidate_root / "football_external_soccernet_api_listing_probe_v1"
    summary = json.loads((output_root / "soccernet_api_listing_probe_summary.json").read_text(encoding="utf-8"))
    listing_audit = json.loads((output_root / "soccernet_api_listing_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["apiListingExecuted"] is True
    assert payload["listingSource"] == "package_local_index"
    assert payload["networkApiCallExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullOriginalVideoDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["credentialPersisted"] is False
    assert payload["passwordRedacted"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_metadata_probe"
    assert summary == payload
    assert listing_audit["totalListedGameRefs"] == 6
    assert "redacted-test-secret" not in json.dumps(listing_audit)


def test_api_listing_probe_blocks_without_runtime_credential(tmp_path: Path) -> None:
    _write_listing_inputs(tmp_path)

    payload = listing_probe.run_football_external_soccernet_api_listing_probe(
        storage_root=tmp_path,
        env={},
        listing_probe=lambda _python: _local_index_probe(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_listing_credential_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_secret_env_setup"
    assert payload["apiListingExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False


def test_api_listing_probe_blocks_without_metadata_probe_truth(tmp_path: Path) -> None:
    _write_listing_inputs(tmp_path, metadata_goal=False)

    payload = listing_probe.run_football_external_soccernet_api_listing_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        listing_probe=lambda _python: _local_index_probe(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_metadata_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_metadata_probe"
    assert payload["apiListingExecuted"] is False


def test_api_listing_probe_blocks_empty_listing(tmp_path: Path) -> None:
    _write_listing_inputs(tmp_path)

    payload = listing_probe.run_football_external_soccernet_api_listing_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        listing_probe=lambda _python: {
            "listingSource": "package_local_index",
            "networkApiCallExecuted": False,
            "listedTaskCount": 0,
            "totalListedGameRefs": 0,
            "taskSplitCounts": {},
            "sampleGameRefs": {},
            "listingErrors": [],
        },
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_listing_empty"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_listing_contract_repair"


def test_api_listing_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_listing_inputs(tmp_path)

    payload = listing_probe.run_football_external_soccernet_api_listing_probe(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        listing_probe=lambda _python: _local_index_probe(),
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_api_local_index_listing_probe",
        "soccernet_api_listing_contract_repair",
        "soccernet_api_listing_blocker_summary",
    ]
