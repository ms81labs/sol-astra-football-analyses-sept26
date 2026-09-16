from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_football_external_soccernet_video_analysis_dry_run as dry_run


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_video(path: Path, *, frame_count: int = 12, width: int = 64, height: int = 36) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (width, height))
    assert writer.isOpened()
    for index in range(frame_count):
        frame = np.full((height, width, 3), index * 15 % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _write_inputs(tmp_path: Path, *, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_approval_v1"
    video_path = candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"
    _write_video(video_path)
    _write_json(
        approval_root / "video_analysis_dry_run_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_video_analysis_dry_run_scope_gap",
            "analysisDryRunApproved": approved,
            "analysisExecutionApproved": approved,
            "analysisExecutionExecuted": False,
            "selectedVideoPath": str(video_path),
            "maxDryRunFrames": 5,
            "sampleEveryNFrames": 2,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        approval_root / "video_analysis_dry_run_contract.json",
        {
            "contractName": "football_external_soccernet_video_analysis_dry_run",
            "selectedVideoPath": str(video_path),
            "videoExists": True,
            "maxDryRunFrames": 5,
            "sampleEveryNFrames": 2,
            "boundedDryRunOnly": True,
            "fullAnalysisAllowed": False,
            "analysisDryRunApproved": approved,
            "analysisExecutionApproved": approved,
            "analysisExecutionExecuted": False,
            "trainingUseAllowed": False,
            "promotionUseAllowed": False,
            "candidateEvaluationUseAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    return candidate_root


def test_video_analysis_dry_run_samples_approved_video_without_full_analysis(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = dry_run.run_football_external_soccernet_video_analysis_dry_run(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_v1"
    manifest = json.loads((output_root / "dry_run_artifact_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisExecutionExecuted"] is True
    assert payload["fullAnalysisExecuted"] is False
    assert payload["sampledFrameCount"] == 5
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke"
    assert len(manifest["sampledFrames"]) == 5
    assert all((output_root / row["relativePath"]).exists() for row in manifest["sampledFrames"])


def test_video_analysis_dry_run_blocks_without_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approved=False)

    payload = dry_run.run_football_external_soccernet_video_analysis_dry_run(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_analysis_dry_run_not_approved"
    assert payload["analysisExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run_approval"


def test_video_analysis_dry_run_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = dry_run.run_football_external_soccernet_video_analysis_dry_run(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_video_bounded_frame_dry_run",
        "soccernet_video_dry_run_sampling_repair",
        "soccernet_video_dry_run_blocker_summary",
    ]
