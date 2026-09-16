from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_full_analysis_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, closeout_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    closeout_root = candidate_root / "football_external_soccernet_bounded_analysis_lane_closeout_v1"
    product_root = candidate_root / "football_external_soccernet_video_product_path_smoke_v1"
    video_path = candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42payload")
    _write_json(
        closeout_root / "bounded_analysis_lane_closeout_summary.json",
        {
            "goalAchieved": closeout_ready,
            "primaryBlocker": None if closeout_ready else "football_external_soccernet_bounded_analysis_closeout_gap",
            "boundedAnalysisLaneClosed": closeout_ready,
            "reportedFrameCount": 300 if closeout_ready else 0,
            "fullAnalysisExecutionApprovalReady": closeout_ready,
            "fullAnalysisExecutionApproved": False,
            "fullAnalysisExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        closeout_root / "full_analysis_execution_approval_contract_prep.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_execution_approval_prep_v1",
            "fullAnalysisExecutionApprovalReady": closeout_ready,
            "fullAnalysisExecutionApproved": False,
            "fullAnalysisExecutionExecuted": False,
            "recommendedScope": {
                "inputVideo": "extracted_224p_soccernet_member",
                "requiresSeparateApproval": True,
                "trainingAllowed": False,
                "promotionAllowed": False,
                "runtimeDefaultMutationAllowed": False,
            },
        },
    )
    _write_json(
        product_root / "external_video_product_bundle.json",
        {
            "schemaVersion": "soccernet_external_video_product_bundle_v1",
            "video": {
                "path": str(video_path),
                "exists": True,
                "width": 398,
                "height": 224,
                "fps": 25.0,
                "frameCount": 146893,
            },
            "readiness": {
                "externalVideoProductPathReady": closeout_ready,
                "fullAnalysisReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    return candidate_root


def test_full_analysis_execution_approval_writes_non_executed_contract(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_full_analysis_execution_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_full_analysis_execution_approval_v1"
    contract = json.loads((output_root / "full_analysis_execution_contract.json").read_text(encoding="utf-8"))
    scope = json.loads((output_root / "full_analysis_scope_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["fullAnalysisExecutionApproved"] is True
    assert payload["fullAnalysisExecutionExecuted"] is False
    assert payload["approvedFrameCount"] == 146893
    assert payload["selectedVideoPath"].endswith("224p.mp4")
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_execution"
    assert contract["fullAnalysisExecutionApproved"] is True
    assert contract["fullAnalysisExecutionExecuted"] is False
    assert contract["video720pMemberDownloadAllowed"] is False
    assert scope["fullFrameCountApproval"] == 146893
    assert scope["resolution"] == {"width": 398, "height": 224}


def test_full_analysis_execution_approval_blocks_without_bounded_closeout(tmp_path: Path) -> None:
    _write_inputs(tmp_path, closeout_ready=False)

    payload = approval.run_football_external_soccernet_full_analysis_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_bounded_analysis_lane_closeout_missing"
    assert payload["fullAnalysisExecutionApproved"] is False
    assert payload["fullAnalysisExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_lane_closeout"


def test_full_analysis_execution_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = approval.run_football_external_soccernet_full_analysis_execution_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_full_analysis_execution_approval",
        "soccernet_full_analysis_scope_repair",
        "soccernet_full_analysis_approval_blocker_summary",
    ]
