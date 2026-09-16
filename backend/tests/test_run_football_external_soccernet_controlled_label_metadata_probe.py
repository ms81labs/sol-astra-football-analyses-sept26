from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_controlled_label_metadata_probe as label_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_label_probe_inputs(tmp_path: Path, *, listing_goal: bool = True, include_ball: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    listing_root = candidate_root / "football_external_soccernet_api_listing_probe_v1"
    access_root = candidate_root / "football_external_soccernet_nda_api_access_approval_v1"
    task_split_counts: dict[str, object] = {
        "spotting": {"train": 2, "valid": 1, "test": 1, "challenge": 1},
    }
    sample_refs: dict[str, object] = {
        "spotting": {"valid": ["england_epl/2014-2015/a"]},
    }
    if include_ball:
        task_split_counts["spotting-ball"] = {"train": 4, "valid": 1, "test": 2, "challenge": 2}
        sample_refs["spotting-ball"] = {
            "train": ["england_efl/2019-2020/train-a"],
            "valid": ["england_efl/2019-2020/valid-a"],
            "test": ["england_efl/2019-2020/test-a"],
            "challenge": ["england_efl/2019-2020/challenge-a"],
        }
    _write_json(
        listing_root / "soccernet_api_listing_probe_summary.json",
        {
            "batchName": "football_external_soccernet_api_listing_probe",
            "goalAchieved": listing_goal,
            "primaryBlocker": None if listing_goal else "football_external_soccernet_api_listing_empty",
            "apiListingExecuted": listing_goal,
            "listingSource": "package_local_index",
            "listedTaskCount": len(task_split_counts),
            "totalListedGameRefs": 13 if include_ball else 5,
            "networkApiCallExecuted": False,
            "datasetDownloadExecuted": False,
            "labelDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccernet_controlled_label_metadata_probe",
        },
    )
    _write_json(
        listing_root / "soccernet_api_listing_audit.json",
        {
            "listingSource": "package_local_index",
            "networkApiCallExecuted": False,
            "taskSplitCounts": task_split_counts,
            "sampleGameRefs": sample_refs,
            "listingErrors": [],
            "totalListedGameRefs": 13 if include_ball else 5,
        },
    )
    _write_json(
        access_root / "soccernet_api_access_contract.json",
        {
            "resourceId": "soccernet_broadcast_tasks",
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersisted": False,
            "passwordRedacted": True,
            "fullOriginalVideoDownloadApproved": False,
            "labelDownloadApproved": False,
            "approvedProbeScope": "api_metadata_or_listing_only",
        },
    )
    return candidate_root


def test_controlled_label_metadata_probe_selects_tiny_ball_label_contract(tmp_path: Path) -> None:
    candidate_root = _write_label_probe_inputs(tmp_path)

    payload = label_probe.run_football_external_soccernet_controlled_label_metadata_probe(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_controlled_label_metadata_probe_v1"
    fetch_contract = json.loads((output_root / "controlled_label_sample_fetch_contract.json").read_text(encoding="utf-8"))
    ball_audit = json.loads((output_root / "soccernet_ball_label_surface_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedTask"] == "spotting-ball"
    assert payload["selectedSplit"] == "valid"
    assert payload["selectedGameRefCount"] == 1
    assert payload["labelMetadataProbeReady"] is True
    assert payload["labelDownloadExecuted"] is False
    assert payload["fullOriginalVideoDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_sample_fetch_approval"
    assert fetch_contract["files"] == ["Labels.json"]
    assert fetch_contract["approvalRequiredBeforeDownload"] is True
    assert fetch_contract["fullOriginalVideoDownloadApproved"] is False
    assert ball_audit["ballTaskAvailable"] is True


def test_controlled_label_metadata_probe_blocks_without_listing_truth(tmp_path: Path) -> None:
    _write_label_probe_inputs(tmp_path, listing_goal=False)

    payload = label_probe.run_football_external_soccernet_controlled_label_metadata_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_api_listing_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_listing_probe"
    assert payload["labelDownloadExecuted"] is False


def test_controlled_label_metadata_probe_blocks_without_ball_surface(tmp_path: Path) -> None:
    _write_label_probe_inputs(tmp_path, include_ball=False)

    payload = label_probe.run_football_external_soccernet_controlled_label_metadata_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_ball_label_surface_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_listing_contract_repair"
    assert payload["datasetDownloadExecuted"] is False


def test_controlled_label_metadata_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_label_probe_inputs(tmp_path)

    payload = label_probe.run_football_external_soccernet_controlled_label_metadata_probe(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_controlled_label_metadata_surface_probe",
        "soccernet_label_metadata_contract_repair",
        "soccernet_label_metadata_blocker_summary",
    ]
