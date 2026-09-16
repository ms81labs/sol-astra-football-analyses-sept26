from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_runtime_default_rollout_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_closeout_inputs(
    tmp_path: Path,
    *,
    include_post_validation: bool = True,
    registry_next: str = "v7_3_runtime_default_rollout_closeout",
    post_validated: bool = True,
    unattended_mentions_closeout: bool = True,
) -> dict[str, Path]:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    runtime_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    automation_path = tmp_path / "automation" / "unattended_roadmap_loop_status.json"

    _write_json(
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "v7_3_promotion_readiness_validation_v1"
        / "v7_3_promotion_readiness_summary.json",
        {
            "batchName": "v7_3_promotion_readiness_validation",
            "goalAchieved": True,
            "primaryBlocker": None,
            "promotionValidated": True,
            "promotionReady": True,
            "candidateReadyForEvaluation": True,
        },
    )
    _write_json(
        suite_root / "v7_3_runtime_default_change_validation_v1" / "runtime_default_change_summary.json",
        {
            "batchName": "v7_3_runtime_default_change_validation",
            "goalAchieved": True,
            "primaryBlocker": None,
            "runtimeDefaultChanged": True,
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultMutationBlockers": [],
            "sourceRobustnessDefaultChangeGatePassed": True,
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "nextRecommendedNextLever": "v7_3_post_runtime_default_source_robustness_validation",
        },
    )
    if include_post_validation:
        _write_json(
            suite_root
            / "v7_3_post_runtime_default_source_robustness_validation_v1"
            / "post_runtime_default_source_robustness_summary.json",
            {
                "batchName": "v7_3_post_runtime_default_source_robustness_validation",
                "goalAchieved": post_validated,
                "primaryBlocker": None if post_validated else "post_validation_regression",
                "postRuntimeDefaultSourceRobustnessValidated": post_validated,
                "runtimeDefaultMutationExecuted": True,
                "failingSourceNotViableBlockerPresent": False,
                "legacySuiteBlockerStillPresent": True,
                "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
                "nextRecommendedNextLever": "v7_3_runtime_default_rollout_closeout",
            },
        )
    _write_json(
        suite_root / "suite_summary.json",
        {
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    _write_json(
        runtime_path,
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.3",
            "runtimeUse": "default_runtime",
            "runtimeDefaultChanged": True,
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": post_validated,
            "failingSourceNotViableBlockerPresent": False,
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "nextRecommendedNextLever": registry_next,
        },
    )
    _write_json(
        automation_path,
        {
            "activeBatchName": "v7_3_post_runtime_default_source_robustness_validation",
            "currentStep": "selected v7_3_runtime_default_rollout_closeout"
            if unattended_mentions_closeout
            else "still waiting on post validation",
            "nextExpectedAction": "Run v7_3_runtime_default_rollout_closeout"
            if unattended_mentions_closeout
            else "Run v7_3_post_runtime_default_source_robustness_validation",
        },
    )
    return {"suiteRoot": suite_root, "runtimePath": runtime_path, "automationPath": automation_path}


def test_rollout_closeout_passes_and_marks_registry_completed(tmp_path: Path) -> None:
    paths = _write_closeout_inputs(tmp_path)

    payload = closeout.run_v7_3_runtime_default_rollout_closeout(storage_root=tmp_path)

    registry = json.loads(paths["runtimePath"].read_text(encoding="utf-8"))
    output_root = paths["suiteRoot"] / "v7_3_runtime_default_rollout_closeout_v1"
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeFailingSourceNotViableBlockerPresent"] is False
    assert payload["historicalSuiteBlockerArchived"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_candidate_closeout"
    assert registry["runtimeDefaultRolloutCloseoutCompleted"] is True
    assert registry["nextRecommendedNextLever"] == "video_to_analysis_release_candidate_closeout"
    assert (output_root / "runtime_default_rollout_closeout_summary.json").exists()
    assert (output_root / "rollout_artifact_inventory.json").exists()


def test_missing_post_default_validation_fails_closed(tmp_path: Path) -> None:
    paths = _write_closeout_inputs(tmp_path, include_post_validation=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = closeout.run_v7_3_runtime_default_rollout_closeout(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_rollout_closeout_post_validation_missing"
    assert payload["nextRecommendedNextLever"] == "v7_3_post_runtime_default_source_robustness_validation"
    assert payload["runtimeDefaultRolloutClosed"] is False
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_registry_not_pointing_to_closeout_fails_closed(tmp_path: Path) -> None:
    paths = _write_closeout_inputs(tmp_path, registry_next="v7_3_post_runtime_default_source_robustness_validation")
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = closeout.run_v7_3_runtime_default_rollout_closeout(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_rollout_closeout_registry_contract_drift"
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_contract_repair"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_unattended_status_drift_routes_to_contract_repair(tmp_path: Path) -> None:
    paths = _write_closeout_inputs(tmp_path, unattended_mentions_closeout=False)
    before = paths["runtimePath"].read_text(encoding="utf-8")

    payload = closeout.run_v7_3_runtime_default_rollout_closeout(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_rollout_closeout_unattended_status_drift"
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_contract_repair"
    assert paths["runtimePath"].read_text(encoding="utf-8") == before


def test_attempt_plan_contains_three_adaptive_failsafes(tmp_path: Path) -> None:
    _write_closeout_inputs(tmp_path)

    payload = closeout.run_v7_3_runtime_default_rollout_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "runtime_default_rollout_artifact_closeout",
        "runtime_default_rollout_contract_repair",
        "runtime_default_rollout_blocker_summary",
    ]
