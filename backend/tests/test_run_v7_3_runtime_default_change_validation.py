from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_runtime_default_change_validation as runtime_validation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_runtime_default_inputs(
    tmp_path: Path,
    *,
    registry_version: str = "v7.3",
    readiness_allowed: bool = True,
    source_blockers: list[str] | None = None,
    pipeline_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    weights_path = candidate_root / "v7_3_bounded_retrain_v1" / "train_run" / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_bytes(b"best weights")

    readiness = {
        "batchName": "v7_3_promotion_readiness_validation",
        "goalAchieved": readiness_allowed,
        "primaryBlocker": None if readiness_allowed else "v7_3_promotion_positive_recall_insufficient",
        "promotionValidated": readiness_allowed,
        "promotionReady": readiness_allowed,
        "candidateReadyForEvaluation": readiness_allowed,
        "promotedForControlledRuns": readiness_allowed,
        "controlledRuntimeRegistryUpdated": readiness_allowed,
        "runtimeDefaultMutationAllowed": readiness_allowed,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": [] if readiness_allowed else ["promotion_readiness_not_validated"],
        "trainingCandidateName": "touchline_detector_candidate_v7",
        "trainingCandidateVersion": "v7.3",
        "runtimeContract": {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.3",
            "auxiliaryBallModelPath": str(weights_path),
            "auxiliaryBallModelProfile": "ball_probe_only_v7_3_crop_256",
            "detectorInputSize": 256,
            "selectedAuditConf": 0.1,
        },
    }
    _write_json(
        candidate_root / "v7_3_promotion_readiness_validation_v1" / "v7_3_promotion_readiness_summary.json",
        readiness,
    )
    _write_json(suite_root / "v7_3_detector_candidate_promotion_readiness.json", readiness)

    pipeline = {
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
        "sourceFrameLocalizationHitRate": 0.99,
        "observedBallAcceptanceRate": 0.99,
        "oldTopLeftArtifactFalsePositiveFrameRate": 0.0,
        "heldoutCanaryFalsePositiveFrameRate": 0.0,
        "sampledFrameDetectionRate": 0.0,
        "topLeftArtifactShare": 0.0,
        "giantBoxShare": 0.0,
        "nearConstantLowConfidenceFlood": False,
    }
    pipeline.update(pipeline_overrides or {})
    _write_json(
        candidate_root
        / "v7_3_full_pipeline_non_promotion_eval_v1"
        / "v7_3_full_pipeline_non_promotion_summary.json",
        pipeline,
    )

    blockers = source_blockers if source_blockers is not None else []
    _write_json(
        suite_root
        / "v7_2_post_runtime_default_source_robustness_validation_v1"
        / "post_runtime_default_source_robustness_summary.json",
        {
            "batchName": "v7_2_post_runtime_default_source_robustness_validation",
            "goalAchieved": True,
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "runtimeDefaultMutationBlockers": blockers,
        },
    )

    registry = {
        "trainingCandidateName": "touchline_detector_candidate_v7",
        "trainingCandidateVersion": registry_version,
        "promotionValidated": registry_version == "v7.3",
        "promotionReady": registry_version == "v7.3",
        "candidateReadyForEvaluation": registry_version == "v7.3",
        "promotedForControlledRuns": registry_version == "v7.3",
        "runtimeDefaultMutationAllowed": readiness_allowed,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": [] if readiness_allowed else ["promotion_readiness_not_validated"],
        "runtimeContract": {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": registry_version,
            "auxiliaryBallModelPath": str(weights_path),
            "auxiliaryBallModelProfile": "ball_probe_only_v7_3_crop_256",
            "detectorInputSize": 256,
            "selectedAuditConf": 0.1,
        },
    }
    runtime_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    _write_json(runtime_path, registry)
    return {"runtimePath": runtime_path, "suiteRoot": suite_root, "candidateRoot": candidate_root}


def test_valid_runtime_default_change_contract_mutates_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path)

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    registry = json.loads(paths["runtimePath"].read_text(encoding="utf-8"))
    output_root = paths["suiteRoot"] / "v7_3_runtime_default_change_validation_v1"
    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultChanged"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_post_runtime_default_source_robustness_validation"
    assert registry["trainingCandidateVersion"] == "v7.3"
    assert registry["runtimeDefaultMutationExecuted"] is True
    assert registry["runtimeDefaultChanged"] is True
    assert registry["runtimeUse"] == "default_runtime"
    assert (output_root / "runtime_default_candidate_contract_audit.json").exists()
    assert (output_root / "runtime_default_registry_mutation_audit.json").exists()


def test_promotion_readiness_gap_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, readiness_allowed=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_runtime_default_candidate_contract_gap"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_contract_fix"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_pipeline_regression_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(
        tmp_path,
        pipeline_overrides={
            "oldTopLeftArtifactFalsePositiveFrameRate": 0.2,
            "topLeftArtifactShare": 0.2,
        },
    )
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_runtime_default_guardrail_regression"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_pipeline_guardrail_repair"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_stale_runtime_registry_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, registry_version="v7.2")
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_runtime_default_registry_contract_gap"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_contract_fix"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_source_robustness_blocker_fails_closed(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, source_blockers=["failing_source_not_viable"])
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_runtime_default_source_robustness_regeneration_failed"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_source_robustness_regression_debug"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_attempt_plan_contains_three_adaptive_failsafes(tmp_path: Path) -> None:
    _write_runtime_default_inputs(tmp_path)

    payload = runtime_validation.run_v7_3_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "runtime_default_candidate_contract_validation",
        "runtime_default_source_robustness_regeneration",
        "runtime_default_change_blocker_summary",
    ]
