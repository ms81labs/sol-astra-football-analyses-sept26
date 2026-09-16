from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, dry_run_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    dry_run_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_v1"
    frame_path = dry_run_root / "sampled_frames/frame_000000.jpg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run_ready:
        frame_path.write_bytes(b"fake-jpeg")
    _write_json(
        dry_run_root / "video_analysis_dry_run_summary.json",
        {
            "goalAchieved": dry_run_ready,
            "primaryBlocker": None if dry_run_ready else "football_external_soccernet_video_analysis_dry_run_frame_sample_failed",
            "analysisExecutionExecuted": dry_run_ready,
            "fullAnalysisExecuted": False,
            "sampledFrameCount": 1 if dry_run_ready else 0,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        dry_run_root / "dry_run_artifact_manifest.json",
        {
            "schemaVersion": "soccernet_external_video_analysis_dry_run_manifest_v1",
            "selectedVideoPath": str(candidate_root / "video.mp4"),
            "sampledFrames": [{"frameIndex": 0, "relativePath": "sampled_frames/frame_000000.jpg", "width": 398, "height": 224}] if dry_run_ready else [],
            "fullAnalysisExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    return candidate_root


def test_dry_run_product_bridge_smoke_writes_product_payload(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
    product_payload = json.loads((output_root / "dry_run_product_bridge_payload.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productBridgeSmokePassed"] is True
    assert payload["productPayloadFrameCount"] == 1
    assert payload["fullAnalysisReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_execution_approval"
    assert product_payload["schemaVersion"] == "soccernet_external_video_dry_run_product_bridge_v1"
    assert product_payload["readiness"]["fullAnalysisReady"] is False


def test_dry_run_product_bridge_smoke_blocks_without_dry_run(tmp_path: Path) -> None:
    _write_inputs(tmp_path, dry_run_ready=False)

    payload = smoke.run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_analysis_dry_run_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run"


def test_dry_run_product_bridge_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_dry_run_product_bridge_smoke",
        "soccernet_dry_run_product_bridge_manifest_repair",
        "soccernet_dry_run_product_bridge_blocker_summary",
    ]
