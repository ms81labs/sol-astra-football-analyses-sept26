from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_controlled_label_sample_fetch as label_fetch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fetch_inputs(tmp_path: Path, *, approval_goal: bool = True, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_controlled_label_sample_fetch_approval_v1"
    metadata_root = candidate_root / "football_external_soccernet_api_metadata_probe_v1"
    _write_json(
        approval_root / "label_sample_fetch_approval_summary.json",
        {
            "batchName": "football_external_soccernet_controlled_label_sample_fetch_approval",
            "goalAchieved": approval_goal,
            "primaryBlocker": None if approval_goal else "football_external_soccernet_label_fetch_scope_unsafe",
            "labelSampleFetchApproved": approved,
            "approvedTask": "spotting-ball",
            "approvedSplit": "valid",
            "approvedGameRefCount": 1,
            "approvedFiles": ["Labels.json"],
            "labelDownloadExecuted": False,
            "fullOriginalVideoDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccernet_controlled_label_sample_fetch",
        },
    )
    _write_json(
        approval_root / "label_sample_fetch_approval_contract.json",
        {
            "contractName": "football_external_soccernet_controlled_label_sample_fetch_approval",
            "labelSampleFetchApproved": approved,
            "resourceId": "soccernet_broadcast_tasks",
            "task": "spotting-ball",
            "split": "valid",
            "gameRefs": ["england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End"],
            "files": ["Labels.json"],
            "maxGameCount": 1,
            "fetchScope": "single_game_label_metadata_only",
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersisted": False,
            "passwordRedacted": True,
            "fullOriginalVideoDownloadApproved": False,
            "videoDownloadAllowed": False,
            "featureDownloadAllowed": False,
            "datasetBulkDownloadAllowed": False,
            "trainingUseAllowed": False,
        },
    )
    _write_json(
        metadata_root / "soccernet_api_package_audit.json",
        {
            "packageImportReady": True,
            "downloaderImportReady": True,
            "pythonExecutable": str(tmp_path / "fake-venv" / "bin" / "python"),
        },
    )
    return candidate_root


def _fake_fetcher(contract: dict[str, object], output_root: Path, _python_executable: Path | None, _env: dict[str, str]) -> dict[str, object]:
    game = str(contract["gameRefs"][0])  # type: ignore[index]
    target = output_root / "sample_labels" / game / "Labels.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"annotations": [{"gameTime": "1 - 00:01", "label": "Ball out"}]}), encoding="utf-8")
    return {
        "fetchExecuted": True,
        "files": [
            {
                "name": "Labels.json",
                "gameRef": game,
                "relativePath": str(target.relative_to(output_root)),
                "sizeBytes": target.stat().st_size,
                "sha256": "abc123",
            }
        ],
        "failures": [],
    }


def test_label_sample_fetch_downloads_only_approved_label_file(tmp_path: Path) -> None:
    candidate_root = _write_fetch_inputs(tmp_path)

    payload = label_fetch.run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        fetcher=_fake_fetcher,
    )

    output_root = candidate_root / "football_external_soccernet_controlled_label_sample_fetch_v1"
    manifest = json.loads((output_root / "controlled_label_fetch_manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_root / "label_fetch_provenance_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["labelDownloadExecuted"] is True
    assert payload["downloadedLabelFileCount"] == 1
    assert payload["fullOriginalVideoDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_schema_probe"
    assert manifest["fetchScope"] == "single_game_label_metadata_only"
    assert provenance["files"][0]["name"] == "Labels.json"
    assert "redacted-test-secret" not in json.dumps(provenance)


def test_label_sample_fetch_blocks_without_approval(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path, approval_goal=False)

    payload = label_fetch.run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        fetcher=_fake_fetcher,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_sample_fetch_approval"
    assert payload["labelDownloadExecuted"] is False


def test_label_sample_fetch_blocks_without_runtime_credential(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path)

    payload = label_fetch.run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=tmp_path,
        env={},
        fetcher=_fake_fetcher,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_credential_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_secret_env_setup"
    assert payload["labelDownloadExecuted"] is False


def test_label_sample_fetch_blocks_fetch_failure(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path)

    def failing_fetcher(_contract: dict[str, object], _output_root: Path, _python_executable: Path | None, _env: dict[str, str]) -> dict[str, object]:
        return {"fetchExecuted": True, "files": [], "failures": [{"file": "Labels.json", "error": "not found"}]}

    payload = label_fetch.run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        fetcher=failing_fetcher,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_failed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_fetch_contract_repair"


def test_label_sample_fetch_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path)

    payload = label_fetch.run_football_external_soccernet_controlled_label_sample_fetch(
        storage_root=tmp_path,
        env={"SOCCERNET_PASSWORD": "redacted-test-secret"},
        fetcher=_fake_fetcher,
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_single_label_file_fetch",
        "soccernet_label_fetch_contract_repair",
        "soccernet_label_fetch_blocker_summary",
    ]
