from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_sample_probe as probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, fetched: bool = True, sample_bytes: bytes = b"PK\x03\x04sample") -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_soccernet_controlled_video_sample_fetch_v1"
    sample_path = fetch_root / "video_member_sample_bytes.bin"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    if fetched:
        sample_path.write_bytes(sample_bytes)
    _write_json(
        fetch_root / "controlled_video_sample_fetch_summary.json",
        {
            "goalAchieved": fetched,
            "primaryBlocker": None if fetched else "football_external_soccernet_controlled_video_sample_fetch_failed",
            "videoSampleFetchExecuted": fetched,
            "selectedVideoMemberPath": "game/224p.mp4",
            "requestedByteCount": len(sample_bytes),
            "sampleBytesFetched": len(sample_bytes) if fetched else 0,
            "sampleSha256": "abc",
            "videoMemberFullDownloadExecuted": False,
            "archiveDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        fetch_root / "controlled_video_sample_fetch_audit.json",
        {
            "samplePath": str(sample_path),
            "sampleBytesFetched": len(sample_bytes) if fetched else 0,
            "videoMemberFullDownloadExecuted": False,
            "archiveDownloadExecuted": False,
        },
    )
    return candidate_root


def test_video_sample_probe_classifies_encrypted_zip_sample(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path, sample_bytes=b"PK\x03\x043\x03\x01\x00c\x00" + b"x" * 64)

    payload = probe.run_football_external_soccernet_video_sample_probe(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_sample_probe_v1"
    sample_probe = json.loads((output_root / "video_sample_probe_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["sampleProbeCompleted"] is True
    assert payload["sampleIsPlayableVideo"] is False
    assert payload["sampleIsEncryptedZipMember"] is True
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_member_extract_approval"
    assert sample_probe["fileSignatureClass"] == "zip_local_file_header"


def test_video_sample_probe_blocks_without_sample_fetch(tmp_path: Path) -> None:
    _write_inputs(tmp_path, fetched=False)

    payload = probe.run_football_external_soccernet_video_sample_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_controlled_video_sample_fetch_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_video_sample_fetch"


def test_video_sample_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = probe.run_football_external_soccernet_video_sample_probe(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "controlled_video_sample_signature_probe",
        "video_sample_probe_contract_repair",
        "video_sample_probe_blocker_summary",
    ]
