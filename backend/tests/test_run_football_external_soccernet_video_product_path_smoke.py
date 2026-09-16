from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_product_path_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, frame_probe_passed: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    frame_root = candidate_root / "football_external_soccernet_video_frame_probe_v1"
    video_root = candidate_root / "football_external_soccernet_video_member_extract_v1"
    video_path = video_root / "extracted_video/game/224p.mp4"
    frame_path = frame_root / "sampled_frames/frame_000000.jpg"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42payload")
    frame_path.write_bytes(b"fake-jpeg")
    _write_json(
        frame_root / "video_frame_probe_summary.json",
        {
            "goalAchieved": frame_probe_passed,
            "primaryBlocker": None if frame_probe_passed else "football_external_soccernet_video_frame_probe_open_failed",
            "videoFrameProbePassed": frame_probe_passed,
            "videoOpenable": frame_probe_passed,
            "frameCount": 100,
            "fps": 25.0,
            "width": 398,
            "height": 224,
            "sampledFrameCount": 1 if frame_probe_passed else 0,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        frame_root / "video_frame_probe_audit.json",
        {
            "videoPath": str(video_path),
            "videoOpenable": frame_probe_passed,
            "frameCount": 100,
            "fps": 25.0,
            "width": 398,
            "height": 224,
            "sampledFrameCount": 1 if frame_probe_passed else 0,
            "sampledFrames": [{"frameIndex": 0, "relativePath": "sampled_frames/frame_000000.jpg", "width": 398, "height": 224}] if frame_probe_passed else [],
        },
    )
    return candidate_root


def test_video_product_path_smoke_writes_external_video_bundle(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_video_product_path_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_product_path_smoke_v1"
    bundle = json.loads((output_root / "external_video_product_bundle.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["externalVideoProductPathReady"] is True
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_to_analysis_bridge_prep"
    assert bundle["video"]["exists"] is True
    assert bundle["readiness"]["frameSamplingReady"] is True
    assert bundle["readiness"]["fullAnalysisReady"] is False


def test_video_product_path_smoke_blocks_without_frame_probe(tmp_path: Path) -> None:
    _write_inputs(tmp_path, frame_probe_passed=False)

    payload = smoke.run_football_external_soccernet_video_product_path_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_frame_probe_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_frame_probe"


def test_video_product_path_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_video_product_path_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_video_product_path_smoke",
        "soccernet_video_product_bundle_repair",
        "soccernet_video_product_path_blocker_summary",
    ]
