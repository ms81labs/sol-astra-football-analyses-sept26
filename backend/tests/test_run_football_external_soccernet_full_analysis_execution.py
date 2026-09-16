from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_football_external_soccernet_full_analysis_execution as execution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_video(path: Path, *, frame_count: int = 12, width: int = 32, height: int = 18) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 6.0, (width, height))
    assert writer.isOpened()
    for index in range(frame_count):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 1] = 50 + index
        frame[:, :, 0] = index % 20
        frame[:, :, 2] = index % 10
        writer.write(frame)
    writer.release()


def _write_inputs(tmp_path: Path, *, approved: bool = True, frame_count: int = 12) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_full_analysis_execution_approval_v1"
    video_path = candidate_root / "video/224p.mp4"
    _write_video(video_path, frame_count=frame_count)
    _write_json(
        approval_root / "full_analysis_execution_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_full_analysis_execution_scope_gap",
            "fullAnalysisExecutionApproved": approved,
            "fullAnalysisExecutionExecuted": False,
            "selectedVideoPath": str(video_path),
            "approvedFrameCount": frame_count if approved else 0,
            "fps": 6.0,
            "resolution": {"width": 32, "height": 18},
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        approval_root / "full_analysis_execution_contract.json",
        {
            "contractName": "football_external_soccernet_full_analysis_execution",
            "selectedVideoPath": str(video_path),
            "approvedFrameCount": frame_count if approved else 0,
            "fps": 6.0,
            "resolution": {"width": 32, "height": 18},
            "inputVideoMember": "224p.mp4",
            "fullAnalysisExecutionApproved": approved,
            "fullAnalysisExecutionExecuted": False,
            "video720pMemberDownloadAllowed": False,
            "archiveDownloadAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "candidateEvaluationReadinessAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    return candidate_root


def test_full_analysis_execution_processes_all_approved_frames(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_full_analysis_execution(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_full_analysis_execution_v1"
    signal_summary = json.loads((output_root / "full_video_frame_signal_summary.json").read_text(encoding="utf-8"))
    product_payload = json.loads((output_root / "full_analysis_product_payload.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["fullAnalysisExecutionExecuted"] is True
    assert payload["processedFrameCount"] == 12
    assert payload["approvedFrameCount"] == 12
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_report_smoke"
    assert signal_summary["aggregate"]["processedFrameCount"] == 12
    assert signal_summary["aggregate"]["unreadableFrameCount"] == 0
    assert product_payload["schemaVersion"] == "soccernet_external_full_analysis_product_payload_v1"
    assert product_payload["readiness"]["fullAnalysisExecutionReady"] is True
    assert product_payload["readiness"]["candidateEvaluationReady"] is False


def test_full_analysis_execution_blocks_without_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approved=False)

    payload = execution.run_football_external_soccernet_full_analysis_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_full_analysis_execution_not_approved"
    assert payload["fullAnalysisExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_execution_approval"


def test_full_analysis_execution_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_full_analysis_execution(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_full_video_frame_signal_execution",
        "soccernet_full_analysis_frame_read_repair",
        "soccernet_full_analysis_execution_blocker_summary",
    ]
