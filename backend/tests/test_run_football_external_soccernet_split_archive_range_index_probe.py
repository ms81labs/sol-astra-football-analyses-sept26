from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import backend.scripts.run_football_external_soccernet_split_archive_range_index_probe as range_probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_size_probe_inputs(tmp_path: Path, *, size_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    size_root = candidate_root / "football_external_soccernet_split_archive_size_probe_v1"
    _write_json(
        size_root / "split_archive_size_probe_summary.json",
        {
            "batchName": "football_external_soccernet_split_archive_size_probe",
            "goalAchieved": size_goal,
            "primaryBlocker": None if size_goal else "football_external_soccernet_selected_archive_metadata_missing",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "selectedArchiveSizeBytes": 2_042_230_928,
            "selectedArchiveSizeClass": "large_archive",
            "archiveDownloadExecuted": False,
            "partialArchiveContentDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_split_archive_range_index_probe",
        },
    )
    _write_json(
        size_root / "split_archive_range_index_probe_contract.json",
        {
            "contractName": "football_external_soccernet_split_archive_range_index_probe",
            "sourceBatch": "football_external_soccernet_split_archive_size_probe",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "selectedArchiveSizeBytes": 2_042_230_928,
            "downloadAllowedByThisBatch": False,
            "fullArchiveDownloadApproved": False,
            "partialRangeMetadataProbeOnly": True,
        },
    )
    return candidate_root


def _archive_bytes() -> bytes:
    handle = BytesIO()
    with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("england_efl/", "")
        archive.writestr("england_efl/2019-2020/", "")
        archive.writestr("england_efl/2019-2020/game/224p.mp4", b"video-low")
        archive.writestr("england_efl/2019-2020/game/720p.mp4", b"video-high")
        archive.writestr("england_efl/2019-2020/game/Labels-ball.json", b'{"annotations":[]}')
    return handle.getvalue()


def test_range_index_probe_parses_zip_index_and_routes_to_label_member_extract_approval(tmp_path: Path) -> None:
    candidate_root = _write_size_probe_inputs(tmp_path)

    payload = range_probe.run_football_external_soccernet_split_archive_range_index_probe(
        storage_root=tmp_path,
        archive_bytes=_archive_bytes(),
    )

    output_root = candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1"
    central_dir = json.loads((output_root / "zip_central_directory_audit.json").read_text(encoding="utf-8"))
    content_risk = json.loads((output_root / "split_archive_content_risk_audit.json").read_text(encoding="utf-8"))
    extract_contract = json.loads((output_root / "zip_label_member_extract_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["zipCentralDirectoryParsed"] is True
    assert payload["labelMemberCount"] == 1
    assert payload["videoMemberCount"] == 2
    assert payload["containsOriginalVideoFiles"] is True
    assert payload["archiveDownloadExecuted"] is False
    assert payload["videoMemberDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_zip_label_member_extract_approval"
    assert central_dir["zipEntryCount"] == 5
    assert content_risk["fullArchiveDownloadRecommended"] is False
    assert extract_contract["labelMemberPaths"] == ["england_efl/2019-2020/game/Labels-ball.json"]


def test_range_index_probe_blocks_without_size_probe_truth(tmp_path: Path) -> None:
    _write_size_probe_inputs(tmp_path, size_goal=False)

    payload = range_probe.run_football_external_soccernet_split_archive_range_index_probe(
        storage_root=tmp_path,
        archive_bytes=_archive_bytes(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_split_archive_size_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_size_probe"
    assert payload["archiveDownloadExecuted"] is False


def test_range_index_probe_routes_missing_labels_to_manual_content_review(tmp_path: Path) -> None:
    _write_size_probe_inputs(tmp_path)
    handle = BytesIO()
    with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("game/720p.mp4", b"video")

    payload = range_probe.run_football_external_soccernet_split_archive_range_index_probe(
        storage_root=tmp_path,
        archive_bytes=handle.getvalue(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_split_archive_label_member_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_manual_content_review"
    assert payload["archiveDownloadExecuted"] is False


def test_range_index_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_size_probe_inputs(tmp_path)

    payload = range_probe.run_football_external_soccernet_split_archive_range_index_probe(
        storage_root=tmp_path,
        archive_bytes=_archive_bytes(),
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_zip_central_directory_range_probe",
        "soccernet_zip_index_contract_repair",
        "soccernet_zip_index_blocker_summary",
    ]
