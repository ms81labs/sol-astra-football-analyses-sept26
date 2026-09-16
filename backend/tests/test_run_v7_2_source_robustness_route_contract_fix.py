from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_source_robustness_route_contract_fix as route_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_route_truth(
    tmp_path: Path,
    *,
    suite_next: str = "promoted_v7_2_source_robustness_validation",
    route_mismatch: bool = False,
    default_blocker: str | None = "v7_2_default_path_performance_blocker",
    default_next: str = "v7_2_default_path_edge_share_reduction",
) -> None:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "suite_summary.json",
        {
            "sourceRobustnessRecommendedNextLever": suite_next,
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessDominantFailureSignal": "high_ball_track_edge_frame_share",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    _write_json(
        suite_root
        / "promoted_v7_2_source_robustness_validation_v1"
        / "promoted_v7_2_source_robustness_validation_summary.json",
        {
            "controlledPromotionValid": True,
            "runtimeDefaultMutationReady": False,
            "runtimeDefaultMutationExecuted": False,
            "runtimeDefaultMutationBlockers": ["failing_source_not_viable"],
            "sourceRobustnessRecommendedNextLever": suite_next,
            "sourceRobustnessRouteMismatchDetected": route_mismatch,
            "nextRecommendedNextLever": "v7_2_source_robustness_default_blocker_analysis",
        },
    )
    _write_json(
        suite_root
        / "v7_2_source_robustness_default_blocker_analysis_v1"
        / "default_blocker_analysis_summary.json",
        {
            "controlledPromotionValid": True,
            "primaryBlocker": default_blocker,
            "realDefaultPerformanceFailureProven": default_blocker == "v7_2_default_path_performance_blocker",
            "runtimeDefaultMutationReady": default_blocker is None,
            "runtimeDefaultMutationExecuted": False,
            "runtimeDefaultMutationBlockers": [] if default_blocker is None else ["failing_source_not_viable"],
            "nextRecommendedNextLever": default_next,
        },
    )


def test_route_contract_fix_passes_when_suite_no_longer_routes_to_stale_evaluation(tmp_path: Path) -> None:
    _write_route_truth(tmp_path)

    payload = route_fix.run_v7_2_source_robustness_route_contract_fix(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["routeContractFixed"] is True
    assert payload["sourceRobustnessRouteMismatchDetected"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_edge_share_reduction"
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_route_contract_fix_blocks_when_suite_still_routes_to_evaluation(tmp_path: Path) -> None:
    _write_route_truth(
        tmp_path,
        suite_next="evaluate_touchline_detector_candidate",
        route_mismatch=True,
        default_blocker="v7_2_source_robustness_route_contract_stale",
        default_next="v7_2_source_robustness_route_contract_fix",
    )

    payload = route_fix.run_v7_2_source_robustness_route_contract_fix(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_2_source_robustness_route_contract_stale"
    assert payload["routeContractFixed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_2_source_robustness_route_contract_fix"


def test_route_contract_fix_blocks_when_default_blocker_analysis_still_names_route_stale(
    tmp_path: Path,
) -> None:
    _write_route_truth(
        tmp_path,
        suite_next="promoted_v7_2_source_robustness_validation",
        route_mismatch=False,
        default_blocker="v7_2_source_robustness_route_contract_stale",
        default_next="v7_2_source_robustness_route_contract_fix",
    )

    payload = route_fix.run_v7_2_source_robustness_route_contract_fix(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_2_source_robustness_route_contract_stale"
    assert payload["routeContractFixed"] is False
    assert payload["defaultBlockerAfterRouteFix"] == "v7_2_source_robustness_route_contract_stale"
    assert payload["nextRecommendedNextLever"] == "v7_2_source_robustness_route_contract_fix"


def test_route_contract_fix_attempt_plan_has_three_failsafe_attempts(tmp_path: Path) -> None:
    _write_route_truth(tmp_path)

    payload = route_fix.run_v7_2_source_robustness_route_contract_fix(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "source_robustness_route_contract_refresh",
        "source_robustness_default_gate_contract_repair",
        "source_robustness_route_contract_blocker_summary",
    ]
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
