from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_touchline_detector_candidate_source_robustness_validation as run_promoted_touchline_detector_candidate_source_robustness_validation


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_baseline_guided_rescue_reference_uses_missing_non_edge_baseline_anchors(tmp_path: Path) -> None:
    baseline_truth_path = tmp_path / "baseline_ball_truth_layers.json"
    promoted_truth_path = tmp_path / "promoted_ball_truth_layers.json"
    output_path = tmp_path / "baseline_guided_rescue_reference.json"
    baseline_truth_path.write_text(
        json.dumps(
            {
                "acceptedBall": {
                    "rows": [
                        {
                            "Frame_ID": 10,
                            "X": 40.0,
                            "Y": 40.0,
                            "Source_X1": 100.0,
                            "Source_Y1": 200.0,
                            "Source_X2": 110.0,
                            "Source_Y2": 220.0,
                        },
                        {
                            "Frame_ID": 20,
                            "X": 2.0,
                            "Y": 40.0,
                            "Source_X1": 120.0,
                            "Source_Y1": 200.0,
                            "Source_X2": 130.0,
                            "Source_Y2": 220.0,
                        },
                        {
                            "Frame_ID": 30,
                            "X": 45.0,
                            "Y": 45.0,
                            "Source_X1": 140.0,
                            "Source_Y1": 200.0,
                            "Source_X2": 150.0,
                            "Source_Y2": 220.0,
                        },
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    promoted_truth_path.write_text(
        json.dumps(
            {
                "acceptedBall": {
                    "rows": [
                        {
                            "Frame_ID": 30,
                            "X": 45.0,
                            "Y": 45.0,
                            "Source_X1": 140.0,
                            "Source_Y1": 200.0,
                            "Source_X2": 150.0,
                            "Source_Y2": 220.0,
                        }
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    payload = (
        run_promoted_touchline_detector_candidate_source_robustness_validation._write_baseline_guided_rescue_reference(
            baseline_truth_layers_path=baseline_truth_path,
            promoted_truth_layers_path=promoted_truth_path,
            output_path=output_path,
            source_clip_id="trimed-5min.mp4",
        )
    )

    written_payload = _load_json(output_path)
    assert payload == written_payload
    assert [anchor["frameId"] for anchor in payload["anchors"]] == [10]
    assert payload["anchors"][0]["sourceCenterX"] == 105.0
    assert payload["anchors"][0]["sourceCenterY"] == 210.0
    assert payload["diagnostics"]["baselineAcceptedFrameCount"] == 3
    assert payload["diagnostics"]["promotedAcceptedFrameCount"] == 1
    assert payload["diagnostics"]["missingBaselineFrameCount"] == 2
    assert payload["diagnostics"]["skippedPromotedExistingFrames"] == 1
    assert payload["diagnostics"]["skippedEdgeFrames"] == 1
    assert payload["diagnostics"]["anchorFrameCount"] == 1


def test_build_arm_specs_uses_manifest_baseline_for_baseline_current() -> None:
    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
    )

    assert arm_specs[0]["runtimeOptions"]["primaryModelPath"] == "yolov10n.pt"
    assert arm_specs[1]["runtimeOptions"]["primaryModelPath"] == "yolo11s.pt"
    assert arm_specs[2]["runtimeOptions"]["primaryModelPath"] == "yolo11s.pt"
    assert arm_specs[1]["runtimeOptions"]["auxiliaryBallModelPath"] == "/tmp/promoted.pt"


def test_build_arm_specs_records_continuity_bridge_attempt_profile_without_runtime_default_change() -> None:
    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1"
        ),
    )

    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1"
    )
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1"
    )


def test_build_arm_specs_records_acceptance_support_gating_profile_without_runtime_default_change() -> None:
    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_acceptance_support_gating_v1"
        ),
    )

    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_acceptance_support_gating_v1"
    )
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_acceptance_support_gating_v1"
    )


def test_build_arm_specs_records_proposal_selection_seed_path_without_runtime_default_change() -> None:
    seed_path = (
        "/tmp/promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
        "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None
    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert arm_specs[2]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1"
    )


def test_build_arm_specs_records_reviewed_positive_anchor_seed_path_without_runtime_default_change() -> None:
    anchor_seed_path = (
        "/tmp/reviewed_positive_proposal_generation_fix_v1/"
        "reviewed_positive_anchor_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1"
        ),
        promoted_baseline_reviewed_positive_anchor_seed_path=anchor_seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] == anchor_seed_path
    assert arm_specs[2]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1"
    )


def test_build_arm_specs_records_reviewed_positive_crop_geometry_scale_profile() -> None:
    anchor_seed_path = (
        "/tmp/reviewed_positive_proposal_generation_fix_v1/"
        "reviewed_positive_anchor_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1"
        ),
        promoted_baseline_reviewed_positive_anchor_seed_path=anchor_seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] == anchor_seed_path
    assert arm_specs[2]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1"
    )


def test_build_arm_specs_records_reviewed_positive_selected_segment_profile() -> None:
    anchor_seed_path = (
        "/tmp/reviewed_positive_proposal_generation_fix_v1/"
        "reviewed_positive_anchor_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
        ),
        promoted_baseline_reviewed_positive_anchor_seed_path=anchor_seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] == anchor_seed_path
    assert arm_specs[1]["forceFreshProof"] is True
    assert arm_specs[2]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1"
    )


def test_build_arm_specs_records_reviewed_positive_edge_share_override_profile() -> None:
    anchor_seed_path = (
        "/tmp/reviewed_positive_proposal_generation_fix_v1/"
        "reviewed_positive_anchor_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1"
        ),
        promoted_baseline_reviewed_positive_anchor_seed_path=anchor_seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] == anchor_seed_path
    assert arm_specs[1]["forceFreshProof"] is True
    assert arm_specs[2]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1"
    )


def test_build_arm_specs_records_reviewed_positive_residual_proposal_profile() -> None:
    anchor_seed_path = (
        "/tmp/reviewed_positive_proposal_generation_fix_v1/"
        "reviewed_positive_anchor_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1"
        ),
        promoted_baseline_reviewed_positive_anchor_seed_path=anchor_seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] == anchor_seed_path
    assert arm_specs[1]["forceFreshProof"] is True
    assert arm_specs[2]["runtimeOptions"]["reviewedPositiveAnchorSeedPath"] is None
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1"
    )


def test_build_arm_specs_records_support_viability_profile_without_runtime_default_change() -> None:
    seed_path = (
        "/tmp/promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
        "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[0]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1"
    )
    assert arm_specs[2]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None


def test_support_viability_profiles_require_default_proposal_selection_seed_path() -> None:
    assert (
        "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )
    assert (
        "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v2"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )
    assert (
        "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )


def test_build_arm_specs_records_proposal_crop_geometry_profile_without_runtime_default_change() -> None:
    seed_path = (
        "/tmp/promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
        "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
    )

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    assert arm_specs[0]["runtimeOptions"]["edgeShareRepairProfile"] is None
    assert arm_specs[0]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None
    assert arm_specs[1]["runtimeOptions"]["edgeShareRepairProfile"] == (
        "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1"
    )
    assert arm_specs[1]["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert arm_specs[2]["runtimeOptions"]["edgeShareRepairProfile"] != (
        "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1"
    )
    assert arm_specs[2]["runtimeOptions"]["proposalSelectionTruthSeedPath"] is None
    assert (
        "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )


def test_build_arm_specs_records_expanded_proposal_crop_geometry_profile() -> None:
    seed_path = "/tmp/seed.json"

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    promoted = arm_specs[1]
    assert (
        promoted["runtimeOptions"]["edgeShareRepairProfile"]
        == "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2"
    )
    assert promoted["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert (
        "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )


def test_build_arm_specs_records_followthrough_proposal_crop_geometry_profile() -> None:
    seed_path = "/tmp/seed.json"

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    promoted = arm_specs[1]
    assert (
        promoted["runtimeOptions"]["edgeShareRepairProfile"]
        == "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3"
    )
    assert promoted["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert (
        "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )


def test_build_arm_specs_records_selection_segment_viability_profile() -> None:
    seed_path = "/tmp/seed.json"

    arm_specs = run_promoted_touchline_detector_candidate_source_robustness_validation._build_arm_specs(
        {
            "runtimeContract": {
                "primaryDetectorModelPath": "yolo11s.pt",
                "auxiliaryBallModelPath": "/tmp/promoted.pt",
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            }
        },
        baseline_fingerprint={"detectorModelPath": "yolov10n.pt"},
        promoted_baseline_edge_share_repair_profile=(
            "source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1"
        ),
        promoted_baseline_proposal_selection_truth_seed_path=seed_path,
    )

    promoted = arm_specs[1]
    assert (
        promoted["runtimeOptions"]["edgeShareRepairProfile"]
        == "source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1"
    )
    assert promoted["runtimeOptions"]["proposalSelectionTruthSeedPath"] == seed_path
    assert (
        "source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1"
        in run_promoted_touchline_detector_candidate_source_robustness_validation.PROFILES_REQUIRING_TRUTH_SEED_PATH
    )
