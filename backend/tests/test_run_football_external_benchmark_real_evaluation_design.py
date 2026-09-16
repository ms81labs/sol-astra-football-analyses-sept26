from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_real_evaluation_design as design


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_decision_route(storage_root: Path, *, ready: bool = True, unsafe_flag: bool = False) -> None:
    root = _candidate_root(storage_root) / "football_external_benchmark_product_decision_surface_route_implementation_v1"
    _write_json(
        root / "product_decision_surface_route_implementation_summary.json",
        {
            "batchName": "football_external_benchmark_product_decision_surface_route_implementation",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_benchmark_product_decision_surface_missing",
            "productDecisionRouteReady": ready,
            "externalBenchmarkLaneClosed": ready,
            "externalSourceCount": 2,
            "apiRoutePath": "/api/external/benchmark/decision",
            "htmlRoutePath": "/external/benchmark/decision",
            "recommendedNextDesignLever": "football_external_benchmark_real_evaluation_design",
            "detectorEvaluationExecuted": unsafe_flag,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )


def test_real_evaluation_design_writes_finite_scope_metrics_and_next_five_steps(tmp_path: Path) -> None:
    _write_decision_route(tmp_path)

    payload = design.run_football_external_benchmark_real_evaluation_design(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_real_evaluation_design_v1"
    source_scope = json.loads((output_root / "real_evaluation_source_scope_contract.json").read_text(encoding="utf-8"))
    metric_contract = json.loads((output_root / "real_evaluation_metric_contract.json").read_text(encoding="utf-8"))
    approval_gate = json.loads((output_root / "real_evaluation_approval_gate.json").read_text(encoding="utf-8"))
    cleanup_audit = json.loads((output_root / "code_sweep_cleanup_audit.json").read_text(encoding="utf-8"))
    next_five = json.loads((output_root / "next_five_step_execution_plan.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["realEvaluationDesignReady"] is True
    assert payload["realEvaluationExecutionReady"] is False
    assert payload["externalSourceCount"] == 2
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_dataset_governance_plan"
    assert source_scope["sourceScopeMode"] == "finite_bounded_design"
    assert source_scope["selectedExternalSourceIds"] == ["soccernet", "soccertrack"]
    assert metric_contract["metricFamilies"] == ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"]
    assert approval_gate["executionApproved"] is False
    assert cleanup_audit["cacheCleanupExecuted"] is True
    assert cleanup_audit["backendTestSweepPassed"] is True
    assert [step["nextLever"] for step in next_five["steps"]] == [
        "football_external_benchmark_dataset_governance_plan",
        "football_external_benchmark_real_evaluation_approval",
        "football_external_benchmark_bounded_real_execution",
        "football_external_benchmark_real_report_and_product_binding",
        "video_to_analysis_finish_line_integration_plan",
    ]


def test_real_evaluation_design_blocks_without_decision_route(tmp_path: Path) -> None:
    payload = design.run_football_external_benchmark_real_evaluation_design(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_product_decision_route_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_decision_surface_route_implementation"


def test_real_evaluation_design_blocks_guardrail_violation(tmp_path: Path) -> None:
    _write_decision_route(tmp_path, unsafe_flag=True)

    payload = design.run_football_external_benchmark_real_evaluation_design(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_real_evaluation_design_guardrail_violation"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_decision_surface_route_contract_repair"


def test_real_evaluation_design_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_decision_route(tmp_path)

    payload = design.run_football_external_benchmark_real_evaluation_design(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_real_evaluation_design",
        "external_benchmark_real_evaluation_design_contract_repair",
        "external_benchmark_real_evaluation_design_blocker_summary",
    ]
