from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_member_extract_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, probe_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    _write_json(
        candidate_root / "football_external_soccernet_video_sample_probe_v1/video_sample_probe_summary.json",
        {
            "goalAchieved": probe_ready,
            "primaryBlocker": None if probe_ready else "football_external_soccernet_video_sample_probe_gap",
            "sampleProbeCompleted": probe_ready,
            "sampleIsEncryptedZipMember": probe_ready,
            "sampleIsPlayableVideo": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_video_sample_download_approval_v1/video_sample_download_approval_contract.json",
        {
            "selectedVideoMemberPath": "game/224p.mp4",
            "selectedCompressedSizeBytes": 236289867,
            "selectedUncompressedSizeBytes": 237589445,
            "selectedLocalHeaderOffset": 226,
            "fullArchiveDownloadApproved": False,
            "requiresRuntimeCredential": True,
            "credentialPersistenceAllowed": False,
        },
    )
    return candidate_root


def test_video_member_extract_approval_writes_scoped_contract(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_member_extract_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_member_extract_approval_v1"
    contract = json.loads((output_root / "video_member_extract_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoMemberExtractionApproved"] is True
    assert payload["videoMemberExtractionExecuted"] is False
    assert payload["fullArchiveDownloadApproved"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_member_extract"
    assert contract["approvedVideoMemberPath"] == "game/224p.mp4"
    assert contract["credentialPersistenceAllowed"] is False


def test_video_member_extract_approval_blocks_without_probe(tmp_path: Path) -> None:
    _write_inputs(tmp_path, probe_ready=False)

    payload = approval.run_football_external_soccernet_video_member_extract_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_sample_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_sample_probe"


def test_video_member_extract_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_member_extract_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "scoped_video_member_extract_approval",
        "video_member_extract_contract_repair",
        "video_member_extract_approval_blocker_summary",
    ]
