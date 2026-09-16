from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_football_external_soccernet_video_frame_probe as probe


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_tiny_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 48))
    assert writer.isOpened()
    for idx in range(4):
        frame = np.full((48, 64, 3), idx * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _write_inputs(tmp_path: Path, *, extracted: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    video_rel = "extracted_video/game/224p.mp4"
    video_path = candidate_root / "football_external_soccernet_video_member_extract_v1" / video_rel
    if extracted:
        _write_tiny_video(video_path)
    _write_json(
        candidate_root / "football_external_soccernet_video_member_extract_v1/video_member_extract_summary.json",
        {
            "goalAchieved": extracted,
            "primaryBlocker": None if extracted else "football_external_soccernet_video_member_extract_failed",
            "videoMemberExtractionExecuted": extracted,
            "extractedVideoFileCount": 1 if extracted else 0,
            "archiveDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video_member_inventory.json",
        {
            "extractedVideoFileCount": 1 if extracted else 0,
            "extractedVideoFiles": [
                {
                    "memberPath": "game/224p.mp4",
                    "relativePath": video_rel,
                    "sizeBytes": video_path.stat().st_size if video_path.exists() else 0,
                    "mp4FtypPresent": True,
                }
            ] if extracted else [],
            "archiveDownloadExecuted": False,
        },
    )
    return candidate_root


def test_video_frame_probe_reads_metadata_and_exports_frames(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = probe.run_football_external_soccernet_video_frame_probe(storage_root=tmp_path, sample_frame_count=3)

    output_root = candidate_root / "football_external_soccernet_video_frame_probe_v1"
    frame_audit = json.loads((output_root / "video_frame_probe_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoFrameProbePassed"] is True
    assert payload["sampledFrameCount"] == 3
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_product_path_smoke"
    assert frame_audit["videoOpenable"] is True
    assert len(list((output_root / "sampled_frames").glob("*.jpg"))) == 3


def test_video_frame_probe_blocks_without_extract(tmp_path: Path) -> None:
    _write_inputs(tmp_path, extracted=False)

    payload = probe.run_football_external_soccernet_video_frame_probe(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_member_extract_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_member_extract"


def test_video_frame_probe_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = probe.run_football_external_soccernet_video_frame_probe(storage_root=tmp_path, sample_frame_count=1)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_extracted_video_frame_probe",
        "soccernet_video_frame_probe_contract_repair",
        "soccernet_video_frame_probe_blocker_summary",
    ]
