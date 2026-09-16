from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_zip_label_member_extract_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_range_index_inputs(tmp_path: Path, *, range_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    range_root = candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1"
    label_path = "england_efl/2019-2020/game/Labels-ball.json"
    _write_json(
        range_root / "split_archive_range_index_probe_summary.json",
        {
            "batchName": "football_external_soccernet_split_archive_range_index_probe",
            "goalAchieved": range_goal,
            "primaryBlocker": None if range_goal else "football_external_soccernet_split_archive_range_index_probe_failed",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "zipCentralDirectoryParsed": True,
            "labelMemberCount": 1,
            "videoMemberCount": 2,
            "containsOriginalVideoFiles": True,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadExecuted": False,
            "labelMemberExtractionApproved": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_zip_label_member_extract_approval",
        },
    )
    _write_json(
        range_root / "zip_central_directory_audit.json",
        {
            "zipCentralDirectoryParsed": True,
            "zipEntryCount": 3,
            "zipEntries": [
                {
                    "path": "england_efl/2019-2020/game/224p.mp4",
                    "isDirectory": False,
                    "compressionMethod": 99,
                    "compressedSizeBytes": 236_289_867,
                    "uncompressedSizeBytes": 237_589_445,
                    "localHeaderOffset": 226,
                },
                {
                    "path": "england_efl/2019-2020/game/720p.mp4",
                    "isDirectory": False,
                    "compressionMethod": 99,
                    "compressedSizeBytes": 1_805_926_920,
                    "uncompressedSizeBytes": 1_806_605_353,
                    "localHeaderOffset": 236_290_211,
                },
                {
                    "path": label_path,
                    "isDirectory": False,
                    "compressionMethod": 99,
                    "compressedSizeBytes": 12_880,
                    "uncompressedSizeBytes": 312_333,
                    "localHeaderOffset": 2_042_217_249,
                },
            ],
        },
    )
    _write_json(
        range_root / "zip_label_member_extract_approval_contract.json",
        {
            "contractName": "football_external_soccernet_zip_label_member_extract_approval",
            "sourceBatch": "football_external_soccernet_split_archive_range_index_probe",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "labelMemberPaths": [label_path],
            "videoMemberPaths": [
                "england_efl/2019-2020/game/224p.mp4",
                "england_efl/2019-2020/game/720p.mp4",
            ],
            "approvalRequiredBeforeLabelMemberExtraction": True,
            "fullArchiveDownloadApproved": False,
            "videoMemberDownloadAllowed": False,
            "labelMemberRangeExtractionOnly": True,
            "trainingUseAllowed": False,
        },
    )
    return candidate_root


def test_zip_label_member_extract_approval_allows_only_label_member_range_extraction(tmp_path: Path) -> None:
    candidate_root = _write_range_index_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_zip_label_member_extract_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_zip_label_member_extract_approval_v1"
    contract = json.loads((output_root / "zip_label_member_extract_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["labelMemberExtractionApproved"] is True
    assert payload["approvedLabelMemberCount"] == 1
    assert payload["videoMemberDownloadAllowed"] is False
    assert payload["fullArchiveDownloadApproved"] is False
    assert payload["credentialRequired"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_zip_label_member_extract"
    assert contract["labelMemberRangeExtractionOnly"] is True
    assert contract["videoMemberDownloadAllowed"] is False


def test_zip_label_member_extract_approval_blocks_without_range_index_truth(tmp_path: Path) -> None:
    _write_range_index_inputs(tmp_path, range_goal=False)

    payload = approval.run_football_external_soccernet_zip_label_member_extract_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_zip_label_member_range_index_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_range_index_probe"
    assert payload["labelMemberExtractionApproved"] is False


def test_zip_label_member_extract_approval_blocks_when_label_member_missing(tmp_path: Path) -> None:
    _write_range_index_inputs(tmp_path)
    range_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "football_external_soccernet_split_archive_range_index_probe_v1"
    _write_json(
        range_root / "zip_label_member_extract_approval_contract.json",
        {
            "contractName": "football_external_soccernet_zip_label_member_extract_approval",
            "sourceBatch": "football_external_soccernet_split_archive_range_index_probe",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "labelMemberPaths": [],
            "videoMemberPaths": ["game/720p.mp4"],
            "approvalRequiredBeforeLabelMemberExtraction": True,
            "fullArchiveDownloadApproved": False,
            "videoMemberDownloadAllowed": False,
            "labelMemberRangeExtractionOnly": True,
        },
    )

    payload = approval.run_football_external_soccernet_zip_label_member_extract_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_zip_label_member_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_manual_content_review"


def test_zip_label_member_extract_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_range_index_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_zip_label_member_extract_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_label_member_extract_approval",
        "soccernet_encrypted_label_member_contract_repair",
        "soccernet_label_member_extract_blocker_summary",
    ]
