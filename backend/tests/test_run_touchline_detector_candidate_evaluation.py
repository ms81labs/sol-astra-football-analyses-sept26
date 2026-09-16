from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_touchline_detector_candidate_evaluation as run_touchline_detector_candidate_evaluation


def _write_trained_candidate_root(
    tmp_path: Path,
    *,
    candidate_name: str,
    training_batch_name: str,
    batch_outcome_roadmap_advance_allowed: bool = True,
    training_quality_gate_passed: bool | None = None,
) -> Path:
    artifact_root = tmp_path / "trained_detector_candidates" / candidate_name
    weights_dir = artifact_root / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    (weights_dir / "best.pt").write_bytes(b"best")
    (weights_dir / "last.pt").write_bytes(b"last")
    (artifact_root / "training_run_summary.json").write_text(
        json.dumps(
            {
                "trainingBatchName": training_batch_name,
                "trainingCandidateName": candidate_name,
                "artifactRoot": str(artifact_root),
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "trainingPrimaryBlocker": None,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "baseModelPath": "yolov10n.pt",
                "bestWeightsPath": str(weights_dir / "best.pt"),
                "lastWeightsPath": str(weights_dir / "last.pt"),
                "heldOutSplitAssessment": None,
                "trainingQualityGatePassed": training_quality_gate_passed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_root / "training_config.json").write_text(
        json.dumps(
            {
                "trainingBatchName": training_batch_name,
                "trainingCandidateName": candidate_name,
                "trainingRecipe": {
                    "baseModelPath": "yolov10n.pt",
                    "epochs": 12,
                    "imgsz": 640,
                    "batch": 8,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_root / "evaluation_contract.json").write_text(
        json.dumps(
            {
                "trainingCandidateName": candidate_name,
                "trainingBatchName": training_batch_name,
                "candidateReadyForEvaluation": True,
                "localScreenTargetClipPath": str(tmp_path / "videos" / "trimed-5min.mp4"),
                "remoteProofComparisonBaseline": {
                    "acceptedBallFrames": 101,
                    "controlledPossessionFrames": 98,
                    "ballTrackViable": False,
                    "ballTrackEdgeFrameShare": 0.812,
                },
                "activeFrozenBaseline": {
                    "detectorModelPath": "yolov10n.pt",
                    "primaryMode": "anchored_player_ranked_context_960",
                    "cleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
                },
                "candidateWeights": {
                    "bestWeightsPath": str(weights_dir / "best.pt"),
                    "lastWeightsPath": str(weights_dir / "last.pt"),
                },
                "auxiliaryBallModelProfile": "ball_probe_only_v1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (artifact_root / "batch_outcome_analysis.json").write_text(
        json.dumps(
            {
                "batchGoal": "Train one refreshed detector candidate and make it evaluation-ready.",
                "goalAchieved": True,
                "roadmapAdvanceAllowed": batch_outcome_roadmap_advance_allowed,
                "englishSummary": "The training batch produced a usable candidate artifact.",
                "englishDecision": "The roadmap may advance to evaluation.",
                "primaryBlocker": None,
                "trainingCompleted": True,
                "weightsReady": True,
                "evaluationContractReady": True,
                "readyForDetectorEvaluation": True,
                "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                "brainstormFixes": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if training_quality_gate_passed is not None:
        quality_gate_root = artifact_root / "training_quality_gate_v1"
        quality_gate_root.mkdir(parents=True, exist_ok=True)
        (quality_gate_root / "quality_gate_summary.json").write_text(
            json.dumps(
                {
                    "trainingCandidateName": candidate_name,
                    "trainingQualityGatePassed": training_quality_gate_passed,
                    "trainingQualityGatePrimaryBlocker": (
                        None if training_quality_gate_passed else "validation_split_has_no_positive_labels"
                    ),
                    "validationImageCount": 4,
                    "validationPositiveLabelImageCount": 2 if training_quality_gate_passed else 0,
                    "validationEmptyLabelImageCount": 2 if training_quality_gate_passed else 4,
                    "validationInformative": training_quality_gate_passed,
                    "maxValidationPrecision": 0.8 if training_quality_gate_passed else 0.0,
                    "maxValidationRecall": 0.7 if training_quality_gate_passed else 0.0,
                    "maxValidationMap50": 0.75 if training_quality_gate_passed else 0.0,
                    "localPositiveSanityImageCount": 8,
                    "localPositiveSanityDetectedImageCount": 8 if training_quality_gate_passed else 0,
                    "readyForDetectorEvaluation": training_quality_gate_passed,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return artifact_root


def test_resolve_active_candidate_name_prefers_gate_cleared_v5_even_when_training_batch_cannot_advance_roadmap(
    tmp_path: Path,
) -> None:
    _write_trained_candidate_root(
        tmp_path,
        candidate_name="touchline_detector_candidate_v3",
        training_batch_name="touchline_detector_candidate_model_data_quality_fix_v1",
        batch_outcome_roadmap_advance_allowed=False,
        training_quality_gate_passed=False,
    )
    _write_trained_candidate_root(
        tmp_path,
        candidate_name="touchline_detector_candidate_v5",
        training_batch_name="touchline_validation_gate_remediation_v1",
        batch_outcome_roadmap_advance_allowed=False,
        training_quality_gate_passed=True,
    )

    resolved = run_touchline_detector_candidate_evaluation._resolve_active_candidate_name(tmp_path)

    assert resolved == "touchline_detector_candidate_v5"

def test_resolve_active_candidate_name_excludes_blocked_v4_gate_candidate(
    tmp_path: Path,
) -> None:
    _write_trained_candidate_root(
        tmp_path,
        candidate_name="touchline_detector_candidate_v4",
        training_batch_name="touchline_proposal_signal_generation_fix_v1",
        batch_outcome_roadmap_advance_allowed=False,
        training_quality_gate_passed=False,
    )
    _write_trained_candidate_root(
        tmp_path,
        candidate_name="touchline_detector_candidate_v5",
        training_batch_name="touchline_validation_gate_remediation_v1",
        batch_outcome_roadmap_advance_allowed=False,
        training_quality_gate_passed=True,
    )

    resolved = run_touchline_detector_candidate_evaluation._resolve_active_candidate_name(tmp_path)

    assert resolved == "touchline_detector_candidate_v5"
