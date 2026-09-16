from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_source_robustness_default_blocker_analysis as analysis


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_truth(
    tmp_path: Path,
    *,
    controlled_valid: bool = True,
    blockers: list[str] | None = None,
    route_mismatch: bool = True,
    passed_source_gate: bool = False,
) -> None:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    validation_root = suite_root / "promoted_v7_2_source_robustness_validation_v1"
    blockers = ["failing_source_not_viable"] if blockers is None else blockers
    next_lever = "evaluate_touchline_detector_candidate" if route_mismatch else "promoted_v7_2_source_robustness_validation"
    if not blockers and passed_source_gate:
        next_lever = "v7_2_runtime_default_change_validation"

    _write_json(
        validation_root / "promoted_v7_2_source_robustness_validation_summary.json",
        {
            "batchName": "promoted_v7_2_source_robustness_validation",
            "validationCompleted": True,
            "controlledPromotionValid": controlled_valid,
            "runtimeDefaultMutationReady": passed_source_gate and not blockers,
            "runtimeDefaultMutationExecuted": False,
            "runtimeDefaultMutationBlockers": blockers,
            "sourceRobustnessOutcome": "source_robustness_partial" if blockers else "source_robustness_strong",
            "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share" if blockers else None,
            "sourceRobustnessRecommendedNextLever": next_lever,
            "sourceRobustnessRouteMismatchDetected": route_mismatch,
            "nextRecommendedNextLever": "v7_2_source_robustness_default_blocker_analysis",
        },
    )
    _write_json(
        validation_root / "source_robustness_gate_audit.json",
        {
            "promotionAudit": {"promotionTruthValid": controlled_valid},
            "sourceAudit": {
                "routeMismatchDetected": route_mismatch,
                "passedPromotionGate": passed_source_gate,
                "runtimeDefaultMutationReady": passed_source_gate and not blockers,
                "runtimeDefaultMutationBlockers": blockers,
                "sourceRobustnessRecommendedNextLever": next_lever,
                "sourceRobustnessOutcome": "source_robustness_partial" if blockers else "source_robustness_strong",
                "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share" if blockers else None,
            },
        },
    )
    _write_json(
        suite_root / "suite_summary.json",
        {
            "sourceRobustnessRecommendedNextLever": next_lever,
            "sourceRobustnessOutcome": "source_robustness_partial" if blockers else "source_robustness_strong",
            "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share" if blockers else None,
            "sourceRobustnessPromotionBlockers": blockers,
            "passedPromotionGate": passed_source_gate,
        },
    )
    _write_json(
        suite_root / "suite_robustness_diagnosis.json",
        {
            "detectorCandidatePromotionDiagnosis": {
                "trainingCandidateName": "touchline_detector_candidate_v7",
                "promotionValidated": controlled_valid,
                "promotedForControlledRuns": controlled_valid,
                "nextRecommendedNextLever": "promoted_v7_2_source_robustness_validation",
            },
            "sourceRobustnessRecommendedNextLever": next_lever,
            "sourceRobustnessPromotionBlockers": blockers,
        },
    )
    _write_json(
        suite_root / "v7_2_detector_candidate_promotion_readiness.json",
        {
            "promotionValidated": controlled_valid,
            "promotionReady": controlled_valid,
            "candidateReadyForEvaluation": controlled_valid,
            "promotedForControlledRuns": controlled_valid,
        },
    )


def test_route_mismatch_selects_route_contract_fix(tmp_path: Path) -> None:
    _write_truth(tmp_path, route_mismatch=True, blockers=["failing_source_not_viable"])

    payload = analysis.run_v7_2_source_robustness_default_blocker_analysis(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_source_robustness_route_contract_stale"
    assert payload["realDefaultPerformanceFailureProven"] is False
    assert payload["sourceRobustnessRouteMismatchDetected"] is True
    assert payload["nextRecommendedNextLever"] == "v7_2_source_robustness_route_contract_fix"


def test_real_performance_blocker_selects_edge_share_reduction(tmp_path: Path) -> None:
    _write_truth(tmp_path, route_mismatch=False, blockers=["failing_source_not_viable"], passed_source_gate=False)

    payload = analysis.run_v7_2_source_robustness_default_blocker_analysis(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_default_path_performance_blocker"
    assert payload["realDefaultPerformanceFailureProven"] is True
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_edge_share_reduction"


def test_clear_source_gate_selects_runtime_default_change_validation(tmp_path: Path) -> None:
    _write_truth(tmp_path, route_mismatch=False, blockers=[], passed_source_gate=True)

    payload = analysis.run_v7_2_source_robustness_default_blocker_analysis(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["runtimeDefaultMutationReady"] is True
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_change_validation"


def test_missing_controlled_promotion_truth_routes_back_to_promotion_readiness(tmp_path: Path) -> None:
    _write_truth(tmp_path, controlled_valid=False)

    payload = analysis.run_v7_2_source_robustness_default_blocker_analysis(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_controlled_promotion_truth_missing"
    assert payload["nextRecommendedNextLever"] == "v7_2_promotion_readiness_validation"


def test_attempt_plan_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_truth(tmp_path)

    payload = analysis.run_v7_2_source_robustness_default_blocker_analysis(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "default_blocker_truth_delta_analysis",
        "source_robustness_route_contract_repair",
        "default_blocker_summary",
    ]
