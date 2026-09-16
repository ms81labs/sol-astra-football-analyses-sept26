from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_split_archive_size_probe as size_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_access_review_inputs(tmp_path: Path, *, access_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    access_root = candidate_root / "football_external_soccernet_split_archive_access_review_v1"
    _write_json(
        access_root / "split_archive_access_review_summary.json",
        {
            "batchName": "football_external_soccernet_split_archive_access_review",
            "goalAchieved": access_goal,
            "primaryBlocker": None if access_goal else "football_external_soccernet_split_archive_surface_missing",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedSplit": "valid",
            "selectedAccessMode": "huggingface_snapshot_allow_pattern",
            "selectedArchiveFileOrPattern": "*valid.zip",
            "splitArchiveDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "fullOriginalVideoDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_split_archive_size_probe",
        },
    )
    _write_json(
        access_root / "split_archive_size_probe_contract.json",
        {
            "contractName": "football_external_soccernet_split_archive_size_probe",
            "sourceBatch": "football_external_soccernet_split_archive_access_review",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedSplit": "valid",
            "selectedAccessMode": "huggingface_snapshot_allow_pattern",
            "selectedArchiveFileOrPattern": "*valid.zip",
            "approvalRequiredBeforeArchiveDownload": True,
            "downloadAllowedByThisBatch": False,
            "metadataOnly": True,
            "fullOriginalVideoDownloadApproved": False,
            "videoDownloadAllowed": False,
            "trainingUseAllowed": False,
        },
    )
    return candidate_root


def _remote_tree_rows() -> list[dict[str, object]]:
    return [
        {"type": "file", "path": ".gitattributes", "size": 2419},
        {"type": "file", "path": "valid.zip", "size": 2_042_230_928},
        {"type": "file", "path": "train.zip", "size": 8_454_740_433},
        {"type": "file", "path": "ExtraLabelsActionSpotting500games/valid_labels.zip", "size": 4_427_873},
    ]


def test_split_archive_size_probe_routes_large_archive_to_range_index_probe(tmp_path: Path) -> None:
    candidate_root = _write_access_review_inputs(tmp_path)

    payload = size_probe.run_football_external_soccernet_split_archive_size_probe(
        storage_root=tmp_path,
        remote_tree_rows=_remote_tree_rows(),
    )

    output_root = candidate_root / "football_external_soccernet_split_archive_size_probe_v1"
    selected_audit = json.loads((output_root / "selected_archive_size_audit.json").read_text(encoding="utf-8"))
    labels_audit = json.loads((output_root / "labels_only_archive_candidate_audit.json").read_text(encoding="utf-8"))
    range_contract = json.loads((output_root / "split_archive_range_index_probe_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedArchivePath"] == "valid.zip"
    assert payload["selectedArchiveSizeBytes"] == 2_042_230_928
    assert payload["selectedArchiveSizeClass"] == "large_archive"
    assert payload["archiveDownloadExecuted"] is False
    assert payload["partialArchiveContentDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_range_index_probe"
    assert selected_audit["fullArchiveDownloadRecommended"] is False
    assert labels_audit["labelsOnlyArchiveCandidateCount"] == 1
    assert range_contract["downloadAllowedByThisBatch"] is False


def test_split_archive_size_probe_blocks_without_access_review_truth(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path, access_goal=False)

    payload = size_probe.run_football_external_soccernet_split_archive_size_probe(
        storage_root=tmp_path,
        remote_tree_rows=_remote_tree_rows(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_split_archive_access_review_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_access_review"
    assert payload["archiveDownloadExecuted"] is False


def test_split_archive_size_probe_blocks_when_selected_archive_metadata_missing(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path)

    payload = size_probe.run_football_external_soccernet_split_archive_size_probe(
        storage_root=tmp_path,
        remote_tree_rows=[{"type": "file", "path": "train.zip", "size": 8_454_740_433}],
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_selected_archive_metadata_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_metadata_contract_repair"
    assert payload["archiveDownloadExecuted"] is False


def test_split_archive_size_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_access_review_inputs(tmp_path)

    payload = size_probe.run_football_external_soccernet_split_archive_size_probe(
        storage_root=tmp_path,
        remote_tree_rows=_remote_tree_rows(),
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_huggingface_split_archive_metadata_probe",
        "soccernet_split_archive_metadata_contract_repair",
        "soccernet_split_archive_size_blocker_summary",
    ]
