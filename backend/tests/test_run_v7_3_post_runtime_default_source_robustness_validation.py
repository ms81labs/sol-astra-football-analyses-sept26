from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_post_runtime_default_source_robustness_validation as post_validation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_post_default_inputs(
    tmp_path: Path,
    *,
    registry_version: str = "v7.3",
    registry_runtime_use: str = "default_runtime",
    runtime_mutated: bool = True,
    source_blockers: list[str] | None = None,
    source_gate_passed: bool = True,
    include_change_summary: bool = True,
) -> dict[str, Path]:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    change_root = suite_root / "v7_3_runtime_default_change_validation_v1"
    blockers = [] if source_blockers is None else source_blockers
    registry_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"

    registry = {
        "trainingCandidateName": "touchline_detector_candidate_v7",
        "trainingCandidateVersion": registry_version,
        "promotionValidated": registry_version == "v7.3",
        "promotionReady": registry_version == "v7.3",
        "candidateReadyForEvaluation": registry_version == "v7.3",
        "promotedForControlledRuns": registry_version == "v7.3",
        "runtimeDefaultChanged": runtime_mutated,
        "runtimeDefaultMutationExecuted": runtime_mutated,
        "runtimeDefaultMutationReady": runtime_mutated,
        "runtimeDefaultMutationAllowed": runtime_mutated,
        "runtimeDefaultMutationBlockers": blockers,
        "runtimeDefaultChangeBlockers": blockers,
        "runtimeUse": registry_runtime_use,
        "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery"
        if source_gate_passed
        else "source_robustness_partial",
        "nextRecommendedNextLever": "v7_3_post_runtime_default_source_robustness_validation",
    }
    _write_json(registry_path, registry)

    if include_change_summary:
        _write_json(
            change_root / "runtime_default_change_summary.json",
            {
                "batchName": "v7_3_runtime_default_change_validation",
                "goalAchieved": runtime_mutated and source_gate_passed and not blockers,
                "primaryBlocker": None if runtime_mutated and source_gate_passed and not blockers else "regression",
                "runtimeDefaultChanged": runtime_mutated,
                "runtimeDefaultMutationExecuted": runtime_mutated,
                "runtimeDefaultMutationBlockers": blockers,
                "sourceRobustnessDefaultChangeGatePassed": source_gate_passed,
                "sourceRobustnessOutcome": registry["sourceRobustnessOutcome"],
                "nextRecommendedNextLever": "v7_3_post_runtime_default_source_robustness_validation",
                "trainingExecuted": False,
                "promotionMutationExecuted": False,
            },
        )
        _write_json(
            change_root / "runtime_default_source_robustness_regeneration_audit.json",
            {
                "sourceRobustnessRegenerationPassed": source_gate_passed and not blockers,
                "runtimeDefaultMutationReady": source_gate_passed and not blockers,
                "runtimeDefaultMutationBlockers": blockers,
                "regeneratedSourceRobustnessOutcome": registry["sourceRobustnessOutcome"],
            },
        )
        _write_json(
            change_root / "runtime_default_registry_mutation_audit.json",
            {
                "runtimeDefaultMutationExecuted": runtime_mutated,
                "registryAfter": registry,
            },
        )

    _write_json(
        suite_root / "suite_summary.json",
        {
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    return {"registryPath": registry_path, "suiteRoot": suite_root}


def test_post_runtime_default_validation_passes_from_active_registry(tmp_path: Path) -> None:
    paths = _write_post_default_inputs(tmp_path)

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    registry = json.loads(paths["registryPath"].read_text(encoding="utf-8"))
    output_root = paths["suiteRoot"] / "v7_3_post_runtime_default_source_robustness_validation_v1"
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["postRuntimeDefaultSourceRobustnessValidated"] is True
    assert payload["failingSourceNotViableBlockerPresent"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_closeout"
    assert registry["postRuntimeDefaultSourceRobustnessValidated"] is True
    assert registry["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_closeout"
    assert (output_root / "active_runtime_default_registry_audit.json").exists()
    assert (output_root / "failing_source_blocker_resurrection_audit.json").exists()


def test_old_suite_summary_blocker_is_historical_not_active(tmp_path: Path) -> None:
    _write_post_default_inputs(tmp_path)

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["legacySuiteBlockerStillPresent"] is True
    assert payload["failingSourceNotViableBlockerPresent"] is False


def test_missing_runtime_default_change_truth_fails_closed(tmp_path: Path) -> None:
    paths = _write_post_default_inputs(tmp_path, include_change_summary=False)
    before = paths["registryPath"].read_text(encoding="utf-8")

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_post_default_source_truth_missing"
    assert payload["postRuntimeDefaultSourceRobustnessValidated"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_post_default_source_robustness_regeneration"
    assert paths["registryPath"].read_text(encoding="utf-8") == before


def test_stale_runtime_registry_fails_closed(tmp_path: Path) -> None:
    paths = _write_post_default_inputs(tmp_path, registry_version="v7.2")
    before = paths["registryPath"].read_text(encoding="utf-8")

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_post_default_registry_contract_gap"
    assert payload["nextRecommendedNextLever"] == "v7_3_post_default_registry_contract_repair"
    assert payload["postRuntimeDefaultSourceRobustnessValidated"] is False
    assert paths["registryPath"].read_text(encoding="utf-8") == before


def test_failing_source_blocker_resurrection_fails_closed(tmp_path: Path) -> None:
    paths = _write_post_default_inputs(tmp_path, source_blockers=["failing_source_not_viable"], source_gate_passed=False)
    before = paths["registryPath"].read_text(encoding="utf-8")

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_post_default_failing_source_not_viable_resurrected"
    assert payload["failingSourceNotViableBlockerPresent"] is True
    assert payload["nextRecommendedNextLever"] == "v7_3_post_default_source_robustness_regression_debug"
    assert paths["registryPath"].read_text(encoding="utf-8") == before


def test_attempt_plan_contains_three_adaptive_failsafes(tmp_path: Path) -> None:
    _write_post_default_inputs(tmp_path)

    payload = post_validation.run_v7_3_post_runtime_default_source_robustness_validation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "post_default_source_robustness_validation",
        "post_default_registry_contract_repair",
        "post_default_blocker_summary",
    ]
