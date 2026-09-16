from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_runtime_registry_product_path_binding as binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_historical_registry_fixture(tmp_path: Path, *, mutated: bool = True) -> Path:
    weights_path = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "v7_2_bounded_retrain_v1" / "train_run" / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True)
    weights_path.write_bytes(b"weights")
    registry_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    _write_json(
        registry_path,
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
            "runtimeUse": "default_runtime",
            "runtimeDefaultMutationExecuted": mutated,
            "runtimeDefaultProfileName": "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1",
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "activeFailingSourceNotViableBlockerPresent": False,
            "runtimeContract": {
                "primaryDetectorModelPath": "yolov10n.pt",
                "auxiliaryBallModelPath": str(weights_path),
                "auxiliaryBallModelProfile": "ball_probe_only_v7_2_crop_256",
                "detectorInputSize": 256,
            },
        },
    )
    return registry_path


def test_runtime_registry_product_path_binding_passes_with_active_historical_registry(tmp_path: Path) -> None:
    _write_historical_registry_fixture(tmp_path)

    payload = binding.run_v7_2_runtime_registry_product_path_binding(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_2_runtime_registry_product_path_binding_v1"
    )
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["localProductPathRegistryBindingPassed"] is True
    assert payload["runpodAuxiliaryRuntimePayloadPassed"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "canonical_match_bundle_export_v1"
    assert (output_root / "runtime_registry_product_binding_summary.json").exists()
    assert (output_root / "local_product_path_binding_audit.json").exists()
    assert (output_root / "runpod_payload_contract_audit.json").exists()
    assert (output_root / "decision_matrix.json").exists()
    assert (output_root / "batch_outcome_analysis.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_runtime_registry_product_path_binding_fails_closed_without_mutated_registry(tmp_path: Path) -> None:
    _write_historical_registry_fixture(tmp_path, mutated=False)

    payload = binding.run_v7_2_runtime_registry_product_path_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_2_product_path_runtime_registry_not_active"
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_registry_contract_fix"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False


def test_runtime_registry_product_path_binding_attempt_plan_has_three_failsafes(tmp_path: Path) -> None:
    _write_historical_registry_fixture(tmp_path)

    payload = binding.run_v7_2_runtime_registry_product_path_binding(storage_root=tmp_path)

    assert [item["attemptApproachFamily"] for item in payload["attemptPlan"]] == [
        "product_path_runtime_registry_binding",
        "runpod_auxiliary_runtime_payload_repair",
        "runtime_registry_product_binding_blocker_summary",
    ]
