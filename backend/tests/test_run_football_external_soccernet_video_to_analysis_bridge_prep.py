from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_video_to_analysis_bridge_prep as bridge


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, product_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    product_root = candidate_root / "football_external_soccernet_video_product_path_smoke_v1"
    video_path = candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"
    frame_path = candidate_root / "football_external_soccernet_video_frame_probe_v1/sampled_frames/frame_000000.jpg"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42payload")
    frame_path.write_bytes(b"fake-jpeg")
    _write_json(
        product_root / "video_product_path_smoke_summary.json",
        {
            "goalAchieved": product_ready,
            "primaryBlocker": None if product_ready else "football_external_soccernet_video_product_bundle_gap",
            "externalVideoProductPathReady": product_ready,
            "frameCount": 146893,
            "fps": 25.0,
            "width": 398,
            "height": 224,
            "sampledFrameCount": 1 if product_ready else 0,
            "fullAnalysisReady": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        product_root / "external_video_product_bundle.json",
        {
            "schemaVersion": "soccernet_external_video_product_bundle_v1",
            "video": {"path": str(video_path), "exists": True, "width": 398, "height": 224, "fps": 25.0, "frameCount": 146893},
            "sampledFrames": [{"frameIndex": 0, "path": str(frame_path), "exists": True, "width": 398, "height": 224}],
            "readiness": {
                "externalVideoProductPathReady": product_ready,
                "frameSamplingReady": product_ready,
                "fullAnalysisReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    return candidate_root


def test_video_to_analysis_bridge_prep_writes_non_executing_contract(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = bridge.run_football_external_soccernet_video_to_analysis_bridge_prep(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
    contract = json.loads((output_root / "analysis_bridge_contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "external_video_ingestion_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisBridgePrepReady"] is True
    assert payload["analysisExecutionApproved"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_analysis_dry_run_approval"
    assert contract["analysisExecutionApproved"] is False
    assert manifest["video"]["exists"] is True
    assert manifest["sampledFrameCount"] == 1


def test_video_to_analysis_bridge_prep_blocks_without_product_path(tmp_path: Path) -> None:
    _write_inputs(tmp_path, product_ready=False)

    payload = bridge.run_football_external_soccernet_video_to_analysis_bridge_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_product_path_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_product_path_smoke"


def test_video_to_analysis_bridge_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = bridge.run_football_external_soccernet_video_to_analysis_bridge_prep(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_video_to_analysis_bridge_contract",
        "soccernet_video_to_analysis_bridge_contract_repair",
        "soccernet_video_to_analysis_bridge_blocker_summary",
    ]
