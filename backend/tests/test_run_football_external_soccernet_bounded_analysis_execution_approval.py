from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_analysis_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, bridge_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    bridge_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
    frame_path = candidate_root / "football_external_soccernet_video_analysis_dry_run_v1/sampled_frames/frame_000000.jpg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(b"fake-jpeg")
    frames = [
        {
            "frameIndex": index,
            "relativePath": "../football_external_soccernet_video_analysis_dry_run_v1/sampled_frames/frame_000000.jpg",
            "exists": True,
        }
        for index in range(300 if bridge_ready else 0)
    ]
    _write_json(
        bridge_root / "dry_run_product_bridge_smoke_summary.json",
        {
            "goalAchieved": bridge_ready,
            "primaryBlocker": None if bridge_ready else "football_external_soccernet_video_analysis_dry_run_product_bridge_gap",
            "productBridgeSmokePassed": bridge_ready,
            "productPayloadFrameCount": 300 if bridge_ready else 0,
            "missingSampledFrameCount": 0 if bridge_ready else 1,
            "fullAnalysisReady": False,
            "fullAnalysisExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        bridge_root / "dry_run_product_bridge_payload.json",
        {
            "schemaVersion": "soccernet_external_video_dry_run_product_bridge_v1",
            "selectedVideoPath": str(candidate_root / "video.mp4"),
            "frameCount": 300 if bridge_ready else 0,
            "frames": frames,
            "readiness": {
                "productBridgeSmokePassed": bridge_ready,
                "boundedDryRunFrameManifestReady": bridge_ready,
                "fullAnalysisReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    _write_json(
        bridge_root / "sampled_frame_existence_audit.json",
        {
            "sampledFrameCount": 300 if bridge_ready else 0,
            "missingSampledFrameCount": 0 if bridge_ready else 1,
            "allSampledFramesExist": bridge_ready,
            "sampledFrames": frames,
        },
    )
    return candidate_root


def test_bounded_analysis_execution_approval_writes_non_executed_contract(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_bounded_analysis_execution_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_bounded_analysis_execution_approval_v1"
    contract = json.loads((output_root / "bounded_analysis_execution_contract.json").read_text(encoding="utf-8"))
    scope = json.loads((output_root / "bounded_analysis_scope_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["boundedAnalysisExecutionApproved"] is True
    assert payload["boundedAnalysisExecutionExecuted"] is False
    assert payload["fullAnalysisAllowed"] is False
    assert payload["fullAnalysisExecuted"] is False
    assert payload["approvedFrameCount"] == 300
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_execution"
    assert contract["boundedAnalysisExecutionApproved"] is True
    assert contract["boundedAnalysisExecutionExecuted"] is False
    assert scope["approvedFrameCount"] == 300
    assert scope["maxApprovedFrameCount"] == 300


def test_bounded_analysis_execution_approval_blocks_without_product_bridge(tmp_path: Path) -> None:
    _write_inputs(tmp_path, bridge_ready=False)

    payload = approval.run_football_external_soccernet_bounded_analysis_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_dry_run_product_bridge_missing"
    assert payload["boundedAnalysisExecutionApproved"] is False
    assert payload["boundedAnalysisExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke"


def test_bounded_analysis_execution_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_bounded_analysis_execution_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_bounded_analysis_execution_approval",
        "soccernet_bounded_analysis_scope_repair",
        "soccernet_bounded_analysis_approval_blocker_summary",
    ]
