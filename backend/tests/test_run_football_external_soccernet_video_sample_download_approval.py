from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_sample_download_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, product_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    _write_json(
        candidate_root / "football_external_soccernet_event_report_product_integration_v1/soccernet_event_report_product_integration_summary.json",
        {
            "goalAchieved": product_ready,
            "primaryBlocker": None if product_ready else "football_external_soccernet_event_report_product_contract_gap",
            "productEventReportReady": product_ready,
            "eventCount": 1604 if product_ready else 0,
            "fullMatchAnalysisReady": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1/zip_central_directory_audit.json",
        {
            "archiveSizeBytes": 2042230928,
            "zipCentralDirectoryParsed": True,
            "zipEntries": [
                {"path": "game/224p.mp4", "isDirectory": False, "compressionMethod": 99, "compressedSizeBytes": 236289867, "uncompressedSizeBytes": 237589445, "localHeaderOffset": 226},
                {"path": "game/720p.mp4", "isDirectory": False, "compressionMethod": 99, "compressedSizeBytes": 1805926920, "uncompressedSizeBytes": 1806605353, "localHeaderOffset": 236290211},
                {"path": "game/Labels-ball.json", "isDirectory": False, "compressionMethod": 99, "compressedSizeBytes": 12880, "uncompressedSizeBytes": 312333, "localHeaderOffset": 2042217249},
            ],
        },
    )
    return candidate_root


def test_video_sample_download_approval_selects_small_224p_member(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_sample_download_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_sample_download_approval_v1"
    contract = json.loads((output_root / "video_sample_download_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoSampleDownloadApproved"] is True
    assert payload["videoMemberDownloadExecuted"] is False
    assert payload["fullArchiveDownloadApproved"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_video_sample_fetch"
    assert contract["selectedVideoMemberPath"] == "game/224p.mp4"
    assert contract["maxApprovedBytes"] <= 50_000_000


def test_video_sample_download_approval_blocks_without_product_payload(tmp_path: Path) -> None:
    _write_inputs(tmp_path, product_ready=False)

    payload = approval.run_football_external_soccernet_video_sample_download_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_event_report_product_integration_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_event_report_product_integration"


def test_video_sample_download_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_sample_download_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "controlled_video_sample_download_approval",
        "video_member_selection_contract_repair",
        "video_sample_approval_blocker_summary",
    ]
