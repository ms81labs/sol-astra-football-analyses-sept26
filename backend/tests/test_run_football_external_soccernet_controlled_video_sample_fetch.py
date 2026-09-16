from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_controlled_video_sample_fetch as fetch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    _write_json(
        candidate_root / "football_external_soccernet_video_sample_download_approval_v1/video_sample_download_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_video_member_selection_gap",
            "videoSampleDownloadApproved": approved,
            "selectedVideoMemberPath": "game/224p.mp4",
            "selectedCompressedSizeBytes": 236289867,
            "selectedUncompressedSizeBytes": 237589445,
            "maxApprovedBytes": 50_000_000,
            "fullArchiveDownloadApproved": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_video_sample_download_approval_v1/video_sample_download_approval_contract.json",
        {
            "contractName": "football_external_soccernet_controlled_video_sample_fetch",
            "videoSampleDownloadApproved": approved,
            "selectedVideoMemberPath": "game/224p.mp4",
            "selectedCompressedSizeBytes": 236289867,
            "selectedUncompressedSizeBytes": 237589445,
            "selectedLocalHeaderOffset": 226,
            "maxApprovedBytes": 50_000_000,
            "fullArchiveDownloadApproved": False,
            "videoMemberDownloadExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1/zip_central_directory_audit.json",
        {
            "archiveSizeBytes": 2042230928,
            "centralDirectoryOffset": 2042230255,
            "zipEntries": [
                {"path": "game/224p.mp4", "isDirectory": False, "localHeaderOffset": 226, "compressedSizeBytes": 236289867, "uncompressedSizeBytes": 237589445},
                {"path": "game/720p.mp4", "isDirectory": False, "localHeaderOffset": 236290211, "compressedSizeBytes": 1805926920, "uncompressedSizeBytes": 1806605353},
            ],
        },
    )
    return candidate_root


def test_controlled_video_sample_fetch_writes_capped_sample(tmp_path: Path, monkeypatch) -> None:
    candidate_root = _write_inputs(tmp_path)

    def fake_fetch(url: str, start: int, end: int, timeout_seconds: int):  # noqa: ANN001
        return b"sample-bytes", {
            "rangeStart": start,
            "rangeEnd": end,
            "httpStatus": 206,
            "contentLength": len(b"sample-bytes"),
            "contentRange": f"bytes {start}-{end}/2042230928",
            "bytesFetched": len(b"sample-bytes"),
            "resolvedHost": "huggingface.co",
        }

    monkeypatch.setattr(fetch, "_range_fetch", fake_fetch)

    payload = fetch.run_football_external_soccernet_controlled_video_sample_fetch(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_controlled_video_sample_fetch_v1"
    audit = json.loads((output_root / "controlled_video_sample_fetch_audit.json").read_text(encoding="utf-8"))
    sample = output_root / "video_member_sample_bytes.bin"

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoSampleFetchExecuted"] is True
    assert payload["videoMemberFullDownloadExecuted"] is False
    assert payload["archiveDownloadExecuted"] is False
    assert payload["sampleBytesFetched"] == len(b"sample-bytes")
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_sample_probe"
    assert sample.read_bytes() == b"sample-bytes"
    assert audit["requestedByteCount"] == 50_000_000


def test_controlled_video_sample_fetch_blocks_without_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approved=False)

    payload = fetch.run_football_external_soccernet_controlled_video_sample_fetch(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_sample_download_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_sample_download_approval"


def test_controlled_video_sample_fetch_contains_three_adaptive_attempts(tmp_path: Path, monkeypatch) -> None:
    _write_inputs(tmp_path)
    monkeypatch.setattr(fetch, "_range_fetch", lambda *args, **kwargs: (b"x", {"httpStatus": 206, "bytesFetched": 1}))

    payload = fetch.run_football_external_soccernet_controlled_video_sample_fetch(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "controlled_video_member_byte_sample_fetch",
        "video_sample_range_contract_repair",
        "controlled_video_sample_fetch_blocker_summary",
    ]
