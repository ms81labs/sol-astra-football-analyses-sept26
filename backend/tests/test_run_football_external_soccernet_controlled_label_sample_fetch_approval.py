from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_controlled_label_sample_fetch_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_approval_inputs(
    tmp_path: Path,
    *,
    metadata_goal: bool = True,
    files: list[str] | None = None,
    max_game_count: int = 1,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    metadata_root = candidate_root / "football_external_soccernet_controlled_label_metadata_probe_v1"
    _write_json(
        metadata_root / "soccernet_controlled_label_metadata_probe_summary.json",
        {
            "batchName": "football_external_soccernet_controlled_label_metadata_probe",
            "goalAchieved": metadata_goal,
            "primaryBlocker": None if metadata_goal else "football_external_soccernet_ball_label_surface_missing",
            "labelMetadataProbeReady": metadata_goal,
            "selectedTask": "spotting-ball",
            "selectedSplit": "valid",
            "selectedGameRefCount": max_game_count,
            "labelDownloadExecuted": False,
            "fullOriginalVideoDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccernet_controlled_label_sample_fetch_approval",
        },
    )
    _write_json(
        metadata_root / "controlled_label_sample_fetch_contract.json",
        {
            "contractName": "football_external_soccernet_controlled_label_sample_fetch",
            "resourceId": "soccernet_broadcast_tasks",
            "task": "spotting-ball",
            "split": "valid",
            "gameRefs": ["england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End"],
            "files": files or ["Labels.json"],
            "maxGameCount": max_game_count,
            "fetchScope": "single_game_label_metadata_only",
            "approvalRequiredBeforeDownload": True,
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
    return candidate_root


def test_label_sample_fetch_approval_allows_single_label_file_only(tmp_path: Path) -> None:
    candidate_root = _write_approval_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_controlled_label_sample_fetch_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_controlled_label_sample_fetch_approval_v1"
    contract = json.loads((output_root / "label_sample_fetch_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["labelSampleFetchApproved"] is True
    assert payload["approvedTask"] == "spotting-ball"
    assert payload["approvedSplit"] == "valid"
    assert payload["approvedGameRefCount"] == 1
    assert payload["approvedFiles"] == ["Labels.json"]
    assert payload["labelDownloadExecuted"] is False
    assert payload["fullOriginalVideoDownloadApproved"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_sample_fetch"
    assert contract["labelSampleFetchApproved"] is True
    assert contract["files"] == ["Labels.json"]
    assert contract["maxGameCount"] == 1


def test_label_sample_fetch_approval_blocks_without_metadata_probe(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, metadata_goal=False)

    payload = approval.run_football_external_soccernet_controlled_label_sample_fetch_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_metadata_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_metadata_probe"
    assert payload["labelDownloadExecuted"] is False


def test_label_sample_fetch_approval_blocks_video_or_bulk_files(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, files=["Labels.json", "1.mkv"])

    payload = approval.run_football_external_soccernet_controlled_label_sample_fetch_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_scope_unsafe"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_metadata_probe"
    assert payload["fullOriginalVideoDownloadExecuted"] is False


def test_label_sample_fetch_approval_blocks_more_than_one_game(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, max_game_count=2)

    payload = approval.run_football_external_soccernet_controlled_label_sample_fetch_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_scope_unsafe"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_metadata_probe"


def test_label_sample_fetch_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_controlled_label_sample_fetch_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_label_sample_fetch_scope_approval",
        "soccernet_label_fetch_contract_repair",
        "soccernet_label_fetch_approval_blocker_summary",
    ]
