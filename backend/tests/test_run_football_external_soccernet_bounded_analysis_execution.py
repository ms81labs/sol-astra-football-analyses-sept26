from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_football_external_soccernet_bounded_analysis_execution as execution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, approved: bool = True, frame_count: int = 300) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_bounded_analysis_execution_approval_v1"
    bridge_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
    dry_run_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_v1"
    frames = []
    for index in range(frame_count):
        relative = f"sampled_frames/frame_{index:06d}.jpg"
        path = dry_run_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        image = np.zeros((16, 24, 3), dtype=np.uint8)
        image[:, :, 1] = 40 + (index % 120)
        image[:, :, 0] = index % 30
        image[:, :, 2] = index % 20
        cv2.imwrite(str(path), image)
        frames.append({"frameIndex": index, "relativePath": relative, "exists": True, "width": 24, "height": 16})
    _write_json(
        approval_root / "bounded_analysis_execution_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_bounded_analysis_execution_scope_gap",
            "boundedAnalysisExecutionApproved": approved,
            "boundedAnalysisExecutionExecuted": False,
            "approvedFrameCount": frame_count if approved else 0,
            "maxApprovedFrameCount": 300,
            "fullAnalysisAllowed": False,
            "fullAnalysisExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        approval_root / "bounded_analysis_execution_contract.json",
        {
            "contractName": "football_external_soccernet_bounded_analysis_execution",
            "selectedVideoPath": str(candidate_root / "video.mp4"),
            "approvedFrameCount": frame_count if approved else 0,
            "maxApprovedFrameCount": 300,
            "boundedAnalysisOnly": True,
            "fullAnalysisAllowed": False,
            "boundedAnalysisExecutionApproved": approved,
            "boundedAnalysisExecutionExecuted": False,
        },
    )
    _write_json(
        bridge_root / "dry_run_product_bridge_payload.json",
        {
            "schemaVersion": "soccernet_external_video_dry_run_product_bridge_v1",
            "selectedVideoPath": str(candidate_root / "video.mp4"),
            "frameCount": frame_count,
            "frames": frames,
            "readiness": {
                "productBridgeSmokePassed": True,
                "boundedDryRunFrameManifestReady": True,
                "fullAnalysisReady": False,
            },
        },
    )
    return candidate_root


def test_bounded_analysis_execution_analyzes_approved_300_frame_manifest(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_bounded_analysis_execution(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_bounded_analysis_execution_v1"
    frame_analysis = json.loads((output_root / "bounded_frame_analysis.json").read_text(encoding="utf-8"))
    product_payload = json.loads((output_root / "bounded_analysis_product_payload.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["boundedAnalysisExecutionExecuted"] is True
    assert payload["fullAnalysisExecuted"] is False
    assert payload["analyzedFrameCount"] == 300
    assert payload["missingFrameCount"] == 0
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_report_smoke"
    assert len(frame_analysis["frames"]) == 300
    assert frame_analysis["aggregate"]["analyzedFrameCount"] == 300
    assert product_payload["schemaVersion"] == "soccernet_external_bounded_analysis_product_payload_v1"
    assert product_payload["readiness"]["fullAnalysisReady"] is False


def test_bounded_analysis_execution_blocks_without_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approved=False)

    payload = execution.run_football_external_soccernet_bounded_analysis_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_bounded_analysis_execution_not_approved"
    assert payload["boundedAnalysisExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_execution_approval"


def test_bounded_analysis_execution_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_bounded_analysis_execution(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_bounded_frame_analysis_execution",
        "soccernet_bounded_analysis_frame_manifest_repair",
        "soccernet_bounded_analysis_execution_blocker_summary",
    ]
