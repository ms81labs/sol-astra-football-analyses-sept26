from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v7_2_source_robustness_validation as validation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_truth(
    tmp_path: Path,
    *,
    registry_version: str = "v7.2",
    blockers: list[str] | None = None,
    passed_source_gate: bool = False,
    promotion_ready: bool = True,
) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    readiness_root = candidate_root / "v7_2_promotion_readiness_validation_v1"
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    registry_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    blockers = ["failing_source_not_viable"] if blockers is None else blockers

    readiness_summary = {
        "batchName": "v7_2_promotion_readiness_validation",
        "goalAchieved": promotion_ready,
        "primaryBlocker": None if promotion_ready else "blocked",
        "promotionValidated": promotion_ready,
        "promotionReady": promotion_ready,
        "candidateReadyForEvaluation": promotion_ready,
        "promotedForControlledRuns": promotion_ready,
        "runtimeDefaultMutationAllowed": not blockers and passed_source_gate,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": blockers,
        "nextRecommendedNextLever": "promoted_v7_2_source_robustness_validation",
    }
    _write_json(readiness_root / "v7_2_promotion_readiness_summary.json", readiness_summary)
    _write_json(suite_root / "v7_2_detector_candidate_promotion_readiness.json", readiness_summary)
    _write_json(
        registry_path,
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": registry_version,
            "promotionValidated": promotion_ready,
            "promotionReady": promotion_ready,
            "candidateReadyForEvaluation": promotion_ready,
            "promotedForControlledRuns": promotion_ready,
            "runtimeDefaultMutationAllowed": not blockers and passed_source_gate,
            "runtimeDefaultMutationExecuted": False,
            "runtimeDefaultMutationBlockers": blockers,
            "runtimeContract": {
                "primaryDetectorModelPath": "yolov10n.pt",
                "auxiliaryBallModelPath": str(candidate_root / "v7_2_bounded_retrain_v1/train_run/weights/best.pt"),
                "auxiliaryBallModelProfile": "ball_probe_only_v7_2_crop_256",
                "detectorInputSize": 256,
            },
        },
    )
    _write_json(
        suite_root / "suite_summary.json",
        {
            "suiteVerdict": "baseline_not_robust" if blockers else "source_robustness_clear",
            "sourceRobustnessOutcome": "source_robustness_partial" if blockers else "source_robustness_strong",
            "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share" if blockers else None,
            "sourceRobustnessRecommendedNextLever": "evaluate_touchline_detector_candidate"
            if blockers
            else "v7_2_runtime_default_change_validation",
            "sourceRobustnessPromotionBlockers": blockers,
            "passedPromotionGate": passed_source_gate,
            "promotionBlockers": blockers,
        },
    )


def test_source_robustness_blocker_routes_default_blocker_analysis(tmp_path: Path) -> None:
    _write_truth(tmp_path, blockers=["failing_source_not_viable"], passed_source_gate=False)

    payload = validation.run_promoted_v7_2_source_robustness_validation(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "promoted_v7_2_source_robustness_validation_v1"
    )
    summary = json.loads(
        (output_root / "promoted_v7_2_source_robustness_validation_summary.json").read_text(encoding="utf-8")
    )

    assert payload["validationCompleted"] is True
    assert payload["runtimeDefaultMutationReady"] is False
    assert payload["primaryBlocker"] == "v7_2_source_robustness_default_mutation_blocked"
    assert payload["runtimeDefaultMutationBlockers"] == ["failing_source_not_viable"]
    assert payload["nextRecommendedNextLever"] == "v7_2_source_robustness_default_blocker_analysis"
    assert summary["controlledPromotionValid"] is True
    assert (output_root / "runtime_default_blocker_audit.json").exists()


def test_clean_source_robustness_routes_runtime_default_change_validation(tmp_path: Path) -> None:
    _write_truth(tmp_path, blockers=[], passed_source_gate=True)

    payload = validation.run_promoted_v7_2_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["runtimeDefaultMutationReady"] is True
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_change_validation"


def test_stale_registry_routes_contract_fix(tmp_path: Path) -> None:
    _write_truth(tmp_path, registry_version="v7.1")

    payload = validation.run_promoted_v7_2_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_runtime_registry_contract_gap"
    assert payload["controlledPromotionValid"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_registry_contract_fix"


def test_failed_promotion_readiness_routes_manual_review(tmp_path: Path) -> None:
    _write_truth(tmp_path, promotion_ready=False)

    payload = validation.run_promoted_v7_2_source_robustness_validation(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_promotion_readiness_truth_missing"
    assert payload["nextRecommendedNextLever"] == "manual_review_required"


def test_attempt_plan_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_truth(tmp_path)

    payload = validation.run_promoted_v7_2_source_robustness_validation(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "promoted_v7_2_controlled_source_robustness_validation",
        "v7_2_source_robustness_route_repair",
        "v7_2_runtime_default_blocker_summary",
    ]
