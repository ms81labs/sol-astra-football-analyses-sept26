from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_analysis_dry_run_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, bridge_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    bridge_root = candidate_root / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
    video_path = candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"
    frame_path = candidate_root / "football_external_soccernet_video_frame_probe_v1/sampled_frames/frame_000000.jpg"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42payload")
    frame_path.write_bytes(b"fake-jpeg")
    _write_json(
        bridge_root / "video_to_analysis_bridge_prep_summary.json",
        {
            "goalAchieved": bridge_ready,
            "primaryBlocker": None if bridge_ready else "football_external_soccernet_video_to_analysis_bridge_contract_gap",
            "analysisBridgePrepReady": bridge_ready,
            "analysisExecutionApproved": False,
            "analysisExecutionExecuted": False,
            "videoExists": bridge_ready,
            "sampledFrameCount": 1 if bridge_ready else 0,
            "archiveDownloadExecuted": False,
            "video720pMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        bridge_root / "external_video_ingestion_manifest.json",
        {
            "schemaVersion": "soccernet_external_video_ingestion_manifest_v1",
            "video": {"path": str(video_path), "exists": bridge_ready, "width": 398, "height": 224, "fps": 25.0, "frameCount": 146893},
            "sampledFrames": [{"frameIndex": 0, "path": str(frame_path), "exists": True, "width": 398, "height": 224}] if bridge_ready else [],
            "sampledFrameCount": 1 if bridge_ready else 0,
            "analysisExecutionApproved": False,
            "analysisExecutionExecuted": False,
            "safeForDryRunApproval": bridge_ready,
        },
    )
    _write_json(
        bridge_root / "analysis_bridge_contract.json",
        {
            "contractName": "football_external_soccernet_video_analysis_dry_run_approval",
            "videoPath": str(video_path),
            "videoExists": bridge_ready,
            "sampledFrameCount": 1 if bridge_ready else 0,
            "analysisBridgePrepReady": bridge_ready,
            "analysisExecutionApproved": False,
            "analysisExecutionExecuted": False,
            "trainingUseAllowed": False,
            "promotionUseAllowed": False,
            "candidateEvaluationUseAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    return candidate_root


def test_video_analysis_dry_run_approval_writes_bounded_non_executed_contract(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_analysis_dry_run_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_analysis_dry_run_approval_v1"
    contract = json.loads((output_root / "video_analysis_dry_run_contract.json").read_text(encoding="utf-8"))
    scope = json.loads((output_root / "dry_run_scope_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisDryRunApproved"] is True
    assert payload["analysisExecutionApproved"] is True
    assert payload["analysisExecutionExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run"
    assert contract["selectedVideoPath"] == scope["selectedVideoPath"]
    assert contract["maxDryRunFrames"] == 300
    assert contract["fullAnalysisAllowed"] is False
    assert scope["boundedDryRunOnly"] is True


def test_video_analysis_dry_run_approval_blocks_without_bridge_prep(tmp_path: Path) -> None:
    _write_inputs(tmp_path, bridge_ready=False)

    payload = approval.run_football_external_soccernet_video_analysis_dry_run_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_to_analysis_bridge_missing"
    assert payload["analysisDryRunApproved"] is False
    assert payload["analysisExecutionApproved"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_to_analysis_bridge_prep"


def test_video_analysis_dry_run_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_video_analysis_dry_run_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_video_analysis_dry_run_approval",
        "soccernet_video_analysis_dry_run_scope_repair",
        "soccernet_video_analysis_dry_run_approval_blocker_summary",
    ]
