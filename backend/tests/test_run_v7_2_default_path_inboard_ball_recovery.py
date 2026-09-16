from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_default_path_inboard_ball_recovery as recovery


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_edge_requirement(tmp_path: Path, *, deficits: list[int]) -> None:
    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_2_default_path_edge_share_reduction_v1"
    )
    _write_json(
        output_root / "edge_share_reduction_summary.json",
        {
            "batchName": "v7_2_default_path_edge_share_reduction",
            "goalAchieved": True,
            "primaryBlocker": "v7_2_default_path_inboard_ball_recovery_required",
            "nextRecommendedNextLever": "v7_2_default_path_inboard_ball_recovery",
            "minimumAdditionalInboardFramesNeededForNearViable": max(deficits) if deficits else 0,
            "runtimeDefaultMutationExecuted": False,
            "trainingExecuted": False,
        },
    )
    _write_json(
        output_root / "inboard_recovery_requirement.json",
        {
            "batchName": "v7_2_default_path_edge_share_reduction",
            "inboardRecoveryRequired": True,
            "nextRecommendedNextLever": "v7_2_default_path_inboard_ball_recovery",
            "sliceRequirements": [
                {
                    "matchId": f"match-{index}",
                    "acceptedFrameCount": 100,
                    "acceptedNonEdgeFrameCount": 18,
                    "nearViableAdditionalInboardFramesNeeded": deficit,
                    "viableAdditionalInboardFramesNeeded": deficit + 2,
                }
                for index, deficit in enumerate(deficits)
            ],
        },
    )


def _write_match_truth(tmp_path: Path, match_id: str, accepted_frames: list[int]) -> None:
    _write_json(
        tmp_path / "matches" / match_id / "ball_truth_layers.json",
        {
            "acceptedBall": {
                "rows": [
                    {
                        "Frame_ID": frame_id,
                        "Entity_Type": "ball",
                        "X": 2.0,
                        "Y": 96.0,
                        "Conf": 0.8,
                    }
                    for frame_id in accepted_frames
                ]
            },
            "probeObservedBall": {"filteredRows": [], "rawRows": []},
        },
    )


def _write_pipeline_audits(
    tmp_path: Path,
    *,
    candidate_frames: list[int],
    top_left_share: float = 0.0,
) -> None:
    output_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "v7_2_full_pipeline_non_promotion_eval_v1"
    )
    _write_json(
        output_root / "v7_2_full_pipeline_non_promotion_summary.json",
        {
            "batchName": "v7_2_full_pipeline_non_promotion_eval",
            "goalAchieved": True,
            "checkpointContractPassed": True,
            "inferenceUsedTrainedWeights": True,
            "missingArtifactCount": 0,
            "projectionAuditPassed": True,
            "projectionErrorCount": 0,
            "sourceFrameLocalizationHitRate": 1.0,
            "observedBallAcceptanceRate": 1.0,
            "oldTopLeftArtifactFalsePositiveFrameRate": 0.0,
            "heldoutCanaryFalsePositiveFrameRate": 0.0,
            "sampledFrameDetectionRate": 0.0,
            "topLeftArtifactShare": top_left_share,
            "giantBoxShare": 0.0,
            "runtimeDefaultMutationAllowed": False,
            "trainingExecuted": False,
            "promotionReady": False,
        },
    )
    _write_json(
        output_root / "reviewed_positive_pipeline_audit.json",
        {
            "frameRows": [
                {
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": frame_id,
                    "candidateCropCoversGtBall": True,
                    "cropDetectorLocalized": True,
                    "sourceFrameLocalized": True,
                    "acceptedAsObservedBall": True,
                    "sourceFrameBbox": {
                        "x1": 1800.0,
                        "y1": 900.0,
                        "x2": 1820.0,
                        "y2": 920.0,
                    },
                    "cropRows": [{"confidence": 0.9}],
                }
                for frame_id in candidate_frames
            ]
        },
    )


def test_inboard_recovery_profile_clears_default_path_blocker(tmp_path: Path) -> None:
    _write_edge_requirement(tmp_path, deficits=[3, 3])
    _write_match_truth(tmp_path, "match-0", accepted_frames=[0])
    _write_match_truth(tmp_path, "match-1", accepted_frames=[0, 5])
    _write_pipeline_audits(tmp_path, candidate_frames=[10, 15, 20, 25])

    payload = recovery.run_v7_2_default_path_inboard_ball_recovery(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["inboardRecoveryProfileReady"] is True
    assert payload["allSliceNearViableDeficitsCovered"] is True
    assert payload["allSliceProjectedNearViableEdgeShareClearsGate"] is True
    assert payload["runtimeDefaultMutationReady"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_change_validation"
    assert payload["attemptPlanFamilies"] == [
        "default_path_inboard_candidate_source_audit",
        "v7_2_controlled_inboard_recovery_profile",
        "inboard_recovery_blocker_summary",
    ]


def test_inboard_candidate_coverage_gap_preserves_runtime_default_guardrail(tmp_path: Path) -> None:
    _write_edge_requirement(tmp_path, deficits=[3])
    _write_match_truth(tmp_path, "match-0", accepted_frames=[0])
    _write_pipeline_audits(tmp_path, candidate_frames=[10, 15])

    payload = recovery.run_v7_2_default_path_inboard_ball_recovery(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_default_path_inboard_candidate_coverage_gap"
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_inboard_candidate_mining"
    assert payload["runtimeDefaultMutationReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_inboard_guardrail_regression_blocks_profile(tmp_path: Path) -> None:
    _write_edge_requirement(tmp_path, deficits=[1])
    _write_match_truth(tmp_path, "match-0", accepted_frames=[0])
    _write_pipeline_audits(tmp_path, candidate_frames=[10, 15], top_left_share=0.25)

    payload = recovery.run_v7_2_default_path_inboard_ball_recovery(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_default_path_inboard_recovery_guardrail_blocked"
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_inboard_guardrail_repair"
    assert payload["runtimeDefaultMutationReady"] is False


def test_writes_required_inboard_recovery_artifacts(tmp_path: Path) -> None:
    _write_edge_requirement(tmp_path, deficits=[1])
    _write_match_truth(tmp_path, "match-0", accepted_frames=[0])
    _write_pipeline_audits(tmp_path, candidate_frames=[10, 15])

    recovery.run_v7_2_default_path_inboard_ball_recovery(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_2_default_path_inboard_ball_recovery_v1"
    )
    for name in [
        "inboard_ball_recovery_summary.json",
        "candidate_source_audit.json",
        "controlled_recovery_profile_audit.json",
        "guardrail_audit.json",
        "source_robustness_regeneration_contract.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ]:
        assert (output_root / name).exists()
