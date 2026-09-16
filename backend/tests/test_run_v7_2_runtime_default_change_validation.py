from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_runtime_default_change_validation as runtime_validation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_runtime_default_inputs(
    tmp_path: Path,
    *,
    registry_version: str = "v7.2",
    inboard_ready: bool = True,
    guardrails_passed: bool = True,
    projected_viable_clears: bool = True,
) -> dict[str, Path]:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    inboard_root = suite_root / "v7_2_default_path_inboard_ball_recovery_v1"
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    weights_path = candidate_root / "v7_2_bounded_retrain_v1" / "train_run" / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_bytes(b"best weights")

    _write_json(
        candidate_root / "v7_2_promotion_readiness_validation_v1" / "v7_2_promotion_readiness_summary.json",
        {
            "promotionValidated": registry_version == "v7.2",
            "promotionReady": registry_version == "v7.2",
            "candidateReadyForEvaluation": registry_version == "v7.2",
            "promotedForControlledRuns": registry_version == "v7.2",
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
        },
    )
    _write_json(
        suite_root / "v7_2_detector_candidate_promotion_readiness.json",
        {
            "promotionValidated": registry_version == "v7.2",
            "promotionReady": registry_version == "v7.2",
            "candidateReadyForEvaluation": registry_version == "v7.2",
        },
    )
    registry = {
        "trainingCandidateName": "touchline_detector_candidate_v7",
        "trainingCandidateVersion": registry_version,
        "promotionValidated": registry_version == "v7.2",
        "promotionReady": registry_version == "v7.2",
        "candidateReadyForEvaluation": registry_version == "v7.2",
        "promotedForControlledRuns": registry_version == "v7.2",
        "runtimeDefaultMutationAllowed": inboard_ready,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": [] if inboard_ready else ["failing_source_not_viable"],
        "runtimeContract": {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
            "auxiliaryBallModelPath": str(weights_path),
            "auxiliaryBallModelProfile": "ball_probe_only_v7_2_crop_256",
            "detectorInputSize": 256,
            "selectedAuditConf": 0.1,
        },
    }
    runtime_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    _write_json(runtime_path, registry)

    summary = {
        "batchName": "v7_2_default_path_inboard_ball_recovery",
        "goalAchieved": inboard_ready,
        "roadmapAdvanceAllowed": inboard_ready,
        "primaryBlocker": None if inboard_ready else "v7_2_default_path_inboard_candidate_coverage_gap",
        "safeInboardCandidateFrameCount": 133 if inboard_ready else 2,
        "sliceCount": 9,
        "allSliceNearViableDeficitsCovered": inboard_ready,
        "allSliceProjectedNearViableEdgeShareClearsGate": inboard_ready,
        "allSliceViableDeficitsCovered": inboard_ready,
        "allSliceProjectedViableEdgeShareClearsGate": projected_viable_clears,
        "inboardRecoveryProfileReady": inboard_ready,
        "runtimeDefaultMutationReady": inboard_ready,
        "runtimeDefaultMutationAllowed": inboard_ready,
        "runtimeDefaultMutationExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "nextRecommendedNextLever": "v7_2_runtime_default_change_validation" if inboard_ready else "manual_review_required",
    }
    _write_json(inboard_root / "inboard_ball_recovery_summary.json", summary)
    _write_json(inboard_root / "batch_outcome_analysis.json", summary)
    _write_json(
        inboard_root / "guardrail_audit.json",
        {
            "requiredInputsPresent": guardrails_passed,
            "guardrailsPassed": guardrails_passed,
            "checks": {"topLeftArtifactShareClear": guardrails_passed},
        },
    )
    _write_json(
        inboard_root / "controlled_recovery_profile_audit.json",
        {
            "controlledRecoveryProfileName": "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1",
            "candidateFrameCount": 133 if inboard_ready else 2,
            "allSliceNearViableDeficitsCovered": inboard_ready,
            "allSliceProjectedNearViableEdgeShareClearsGate": inboard_ready,
            "allSliceViableDeficitsCovered": inboard_ready,
            "allSliceProjectedViableEdgeShareClearsGate": projected_viable_clears,
            "sliceProfiles": [
                {
                    "matchId": f"match-{index}",
                    "nearViableDeficitCovered": inboard_ready,
                    "viableDeficitCovered": inboard_ready and projected_viable_clears,
                    "projectedNearViableEdgeShareClearsGate": inboard_ready,
                    "projectedViableEdgeShareClearsGate": projected_viable_clears,
                    "selectedViableCandidateFrameIds": [5, 50, 55],
                }
                for index in range(9)
            ],
        },
    )
    _write_json(
        inboard_root / "source_robustness_regeneration_contract.json",
        {
            "shouldRegenerateSourceRobustness": inboard_ready,
            "controlledRecoveryProfileName": "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1",
            "sourceRobustnessGeneratedTruthCleared": inboard_ready,
            "runtimeDefaultMutationReady": inboard_ready,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "v7_2_runtime_default_change_validation" if inboard_ready else "manual_review_required",
            "requiredGuardrails": {
                "checkpointContractPassed": True,
                "inferenceUsedTrainedWeights": True,
                "projectionAuditPassed": True,
                "topLeftArtifactShare": 0.0,
            },
        },
    )
    return {"runtimePath": runtime_path, "suiteRoot": suite_root}


def test_valid_runtime_default_change_contract_mutates_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path)

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    registry = json.loads(paths["runtimePath"].read_text(encoding="utf-8"))
    output_root = paths["suiteRoot"] / "v7_2_runtime_default_change_validation_v1"
    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultChanged"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_post_runtime_default_source_robustness_validation"
    assert registry["runtimeDefaultMutationExecuted"] is True
    assert registry["runtimeDefaultChanged"] is True
    assert registry["runtimeDefaultProfileName"] == "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1"
    assert registry["runtimeUse"] == "default_runtime"
    assert (output_root / "runtime_default_candidate_contract_audit.json").exists()
    assert (output_root / "runtime_default_registry_mutation_audit.json").exists()


def test_contract_gap_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, inboard_ready=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_runtime_default_candidate_contract_gap"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_contract_fix"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_guardrail_regression_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, guardrails_passed=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_runtime_default_guardrail_regression"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_inboard_recovery_profile_repair"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_stale_runtime_registry_fails_closed_without_mutating_registry(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, registry_version="v7.1")
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_runtime_default_registry_contract_gap"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_contract_fix"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_regenerated_source_projection_failure_fails_closed(tmp_path: Path) -> None:
    paths = _write_runtime_default_inputs(tmp_path, projected_viable_clears=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_runtime_default_source_robustness_regeneration_failed"
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_source_robustness_regression_debug"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_attempt_plan_contains_three_adaptive_failsafes(tmp_path: Path) -> None:
    _write_runtime_default_inputs(tmp_path)

    payload = runtime_validation.run_v7_2_runtime_default_change_validation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "runtime_default_candidate_contract_validation",
        "runtime_default_source_robustness_regeneration",
        "runtime_default_change_blocker_summary",
    ]
