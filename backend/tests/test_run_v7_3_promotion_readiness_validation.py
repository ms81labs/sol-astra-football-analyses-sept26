from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_promotion_readiness_validation as promotion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_v7_3_truth(
    tmp_path: Path,
    *,
    source_blockers: list[str] | None = None,
    pipeline_overrides: dict[str, object] | None = None,
    guardrail_overrides: dict[str, object] | None = None,
    bounded_overrides: dict[str, object] | None = None,
    export_overrides: dict[str, object] | None = None,
    include_pipeline: bool = True,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    weights_path = candidate_root / "v7_3_bounded_retrain_v1" / "train_run" / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_bytes(b"v7.3 best weights")

    export_summary = {
        "batchName": "v7_3_export_label_overlay_audit",
        "goalAchieved": True,
        "primaryBlocker": None,
        "positiveCropExampleCount": 414,
        "positiveLabelFilesWithExactlyOneBall": 414,
        "localHardNegativeCropCount": 180,
        "heldoutHardNegativeCanaryCount": 20,
        "splitLeakageCount": 0,
        "canaryLeakageCount": 0,
        "unsafeFullFrameNegativeExportCount": 0,
        "positiveLabelRoundTripMaxErrorPx": 0.5,
        "exportOverlayAuditPassed": True,
    }
    export_summary.update(export_overrides or {})
    _write_json(candidate_root / "v7_3_export_label_overlay_audit_v1" / "v7_3_label_overlay_audit.json", export_summary)

    bounded_summary = {
        "batchName": "v7_3_bounded_retrain",
        "goalAchieved": True,
        "primaryBlocker": None,
        "trainingCompleted": True,
        "checkpointContractPassed": True,
        "inferenceUsedTrainedWeights": True,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "bestWeightsPathLocal": str(weights_path),
        "bestWeightsPathLocalExists": True,
        "bestWeightsPathLocalSha256": "abc123",
        "selectedCheckpointForVerdict": "best.pt",
        "selectedAuditConf": 0.1,
        "boundedTrainPositiveLocalizationHitRate": 0.98,
        "boundedValPositiveLocalizationHitRate": 0.97,
        "boundedValNegativeFalsePositiveFrameRate": 0.0,
        "heldoutCanaryFalsePositiveFrameRate": 0.0,
        "medianValPositiveConfidence": 0.81,
        "topLeftArtifactShare": 0.0,
        "giantBoxShare": 0.0,
        "nearConstantLowConfidenceFlood": False,
    }
    bounded_summary.update(bounded_overrides or {})
    _write_json(candidate_root / "v7_3_bounded_retrain_v1" / "v7_3_bounded_retrain_summary.json", bounded_summary)

    guardrail_summary = {
        "batchName": "v7_3_crop_probe_precision_guardrail_audit",
        "goalAchieved": True,
        "primaryBlocker": None,
        "precisionGuardrailPassed": True,
        "checkpointContractPassed": True,
        "inferenceUsedTrainedWeights": True,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "selectedCheckpointForAudit": "best.pt",
        "selectedCheckpointSha256": "abc123",
        "selectedAuditConf": 0.1,
        "boundedValPositiveLocalizationHitRate": 0.97,
        "oldTopLeftArtifactFalsePositiveFrameRate": 0.0,
        "heldoutCanaryFalsePositiveFrameRate": 0.0,
        "nearConstantLowConfidenceFlood": False,
        "topLeftArtifactShare": 0.0,
        "giantBoxShare": 0.0,
    }
    guardrail_summary.update(guardrail_overrides or {})
    _write_json(
        candidate_root
        / "v7_3_crop_probe_precision_guardrail_audit_v1"
        / "v7_3_crop_probe_precision_guardrail_summary.json",
        guardrail_summary,
    )

    if include_pipeline:
        pipeline_summary = {
            "batchName": "v7_3_full_pipeline_non_promotion_eval",
            "goalAchieved": True,
            "primaryBlocker": None,
            "checkpointContractPassed": True,
            "inferenceUsedTrainedWeights": True,
            "inferenceUsedRemotePath": False,
            "inferenceUsedBaseModel": False,
            "pipelineCropContractMatchesTraining": True,
            "projectionAuditPassed": True,
            "candidateCropCoverageRate": 1.0,
            "sourceFrameLocalizationHitRate": 1.0,
            "observedBallAcceptanceRate": 1.0,
            "oldTopLeftArtifactFalsePositiveFrameRate": 0.0,
            "heldoutCanaryFalsePositiveFrameRate": 0.0,
            "sampledFrameDetectionRate": 0.0,
            "topLeftArtifactShare": 0.0,
            "giantBoxShare": 0.0,
            "nearConstantLowConfidenceFlood": False,
            "selectedAuditConf": 0.1,
            "selectedCheckpointForAudit": "best.pt",
            "selectedCheckpointSha256": "abc123",
            "positiveReviewedFrameCount": 138,
            "positiveFramesWithSourceFrameLocalizedBall": 138,
            "positiveFramesAcceptedAsObservedBall": 138,
        }
        pipeline_summary.update(pipeline_overrides or {})
        _write_json(
            candidate_root
            / "v7_3_full_pipeline_non_promotion_eval_v1"
            / "v7_3_full_pipeline_non_promotion_summary.json",
            pipeline_summary,
        )

    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "suite_summary.json",
        {
            "suiteVerdict": "baseline_not_robust",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": source_blockers
            if source_blockers is not None
            else ["failing_source_not_viable"],
        },
    )
    return candidate_root


def _write_current_source_robustness_evidence(tmp_path: Path, blockers: list[str] | None = None) -> None:
    _write_json(
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_2_post_runtime_default_source_robustness_validation_v1"
        / "post_runtime_default_source_robustness_summary.json",
        {
            "batchName": "v7_2_post_runtime_default_source_robustness_validation",
            "goalAchieved": True,
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "runtimeDefaultMutationBlockers": blockers if blockers is not None else [],
        },
    )


def test_clean_v7_3_truth_validates_controlled_promotion_and_registry(tmp_path: Path) -> None:
    candidate_root = _build_v7_3_truth(tmp_path)

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    output_root = candidate_root / "v7_3_promotion_readiness_validation_v1"
    runtime_registry = json.loads(
        (tmp_path / "runtime" / "promoted_touchline_detector_candidate.json").read_text(encoding="utf-8")
    )
    suite_readiness = json.loads(
        (
            tmp_path
            / "benchmark_suites"
            / "frozen-viable-baseline-slice-suite"
            / "v7_3_detector_candidate_promotion_readiness.json"
        ).read_text(encoding="utf-8")
    )

    assert payload["promotionValidated"] is True
    assert payload["promotionReady"] is True
    assert payload["candidateReadyForEvaluation"] is True
    assert payload["promotedForControlledRuns"] is True
    assert payload["controlledRuntimeRegistryUpdated"] is True
    assert payload["runtimeDefaultMutationEvaluated"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["runtimeDefaultMutationBlockers"] == ["failing_source_not_viable"]
    assert payload["nextRecommendedNextLever"] == "promoted_v7_3_source_robustness_validation"
    assert runtime_registry["trainingCandidateVersion"] == "v7.3"
    assert runtime_registry["trainingCandidateName"] == "touchline_detector_candidate_v7"
    assert runtime_registry["promotionValidated"] is True
    assert runtime_registry["runtimeDefaultMutationExecuted"] is False
    assert suite_readiness["promotionReady"] is True
    assert (output_root / "promotion_gate_audit.json").exists()
    assert (output_root / "candidate_evaluation_readiness_contract.json").exists()


def test_runtime_default_mutation_can_be_allowed_without_executing_it(tmp_path: Path) -> None:
    _build_v7_3_truth(tmp_path, source_blockers=[])

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["promotionValidated"] is True
    assert payload["runtimeDefaultMutationAllowed"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_change_validation"


def test_current_source_robustness_evidence_overrides_stale_suite_blocker(tmp_path: Path) -> None:
    _build_v7_3_truth(tmp_path, source_blockers=["failing_source_not_viable"])
    _write_current_source_robustness_evidence(tmp_path, blockers=[])

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["promotionValidated"] is True
    assert payload["runtimeDefaultMutationAllowed"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["runtimeDefaultMutationBlockers"] == []
    assert payload["sourceRobustnessEvidencePath"].endswith(
        "v7_2_post_runtime_default_source_robustness_validation_v1/post_runtime_default_source_robustness_summary.json"
    )
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_change_validation"


def test_missing_full_pipeline_truth_fails_closed(tmp_path: Path) -> None:
    _build_v7_3_truth(tmp_path, include_pipeline=False)

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["promotionValidated"] is False
    assert payload["primaryBlocker"] == "v7_3_promotion_readiness_missing_upstream_truth"
    assert payload["controlledRuntimeRegistryUpdated"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_full_pipeline_non_promotion_eval"
    assert not (tmp_path / "runtime" / "promoted_touchline_detector_candidate.json").exists()


def test_full_pipeline_flood_regression_routes_runtime_integration_fix(tmp_path: Path) -> None:
    _build_v7_3_truth(
        tmp_path,
        pipeline_overrides={
            "oldTopLeftArtifactFalsePositiveFrameRate": 0.2,
            "topLeftArtifactShare": 0.2,
        },
    )

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["promotionValidated"] is False
    assert payload["primaryBlocker"] == "v7_3_promotion_full_pipeline_flood_regression"
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_integration_fix"


def test_positive_recall_failure_routes_positive_diversity_refresh(tmp_path: Path) -> None:
    _build_v7_3_truth(
        tmp_path,
        pipeline_overrides={
            "sourceFrameLocalizationHitRate": 0.45,
            "observedBallAcceptanceRate": 0.45,
        },
    )

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["promotionValidated"] is False
    assert payload["primaryBlocker"] == "v7_3_promotion_positive_recall_insufficient"
    assert payload["nextRecommendedNextLever"] == "v7_3_positive_diversity_refresh"


def test_attempt_plan_contains_three_adaptive_failsafes(tmp_path: Path) -> None:
    _build_v7_3_truth(tmp_path)

    payload = promotion.run_v7_3_promotion_readiness_validation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "controlled_candidate_promotion_readiness_validation",
        "promotion_readiness_contract_repair",
        "promotion_readiness_blocker_summary",
    ]
