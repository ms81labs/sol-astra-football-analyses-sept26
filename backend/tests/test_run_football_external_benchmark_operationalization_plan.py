from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_operationalization_plan as op_plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_closeout(storage_root: Path, *, ready: bool = True, unsafe_flag: bool = False) -> None:
    closeout_root = _candidate_root(storage_root) / "football_external_benchmark_lane_closeout_v1"
    _write_json(
        closeout_root / "external_benchmark_lane_closeout_summary.json",
        {
            "batchName": "football_external_benchmark_lane_closeout",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_benchmark_lane_required_evidence_missing",
            "externalBenchmarkLaneClosed": ready,
            "externalSourceCount": 2,
            "soccernetAnalysisProductLaneClosed": ready,
            "soccertrackLaneClosed": ready,
            "benchmarkProductUiRouteReady": ready,
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": unsafe_flag,
        },
    )
    _write_json(
        closeout_root / "external_benchmark_capability_matrix.json",
        {
            "schemaVersion": "external_benchmark_capability_matrix_v1",
            "externalBenchmarkLaneClosed": ready,
            "externalSourceCount": 2,
            "soccernetAnalysisProductLaneClosed": ready,
            "soccertrackLaneClosed": ready,
            "benchmarkProductUiRouteReady": ready,
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "soccernetReportedFrameCount": 146893,
            "soccertrackReportedEventCount": 3142,
            "soccertrackReportedFrameCount": 20,
            "detectorEvaluationReady": False,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
    )
    _write_json(
        closeout_root / "remaining_gap_analysis.json",
        {
            "schemaVersion": "external_benchmark_remaining_gap_analysis_v1",
            "externalBenchmarkLaneClosed": ready,
            "remainingPrimaryGap": "external_benchmark_operationalization_not_yet_planned" if ready else "external_benchmark_lane_required_evidence_missing",
            "remainingGaps": [
                "turn benchmark harness smoke into an operational product decision path",
                "benchmark reports are generated truth smoke, not detector candidate evaluation",
            ],
            "nextSafeLever": "football_external_benchmark_operationalization_plan",
        },
    )


def test_operationalization_plan_writes_product_contract_and_selects_decision_surface(tmp_path: Path) -> None:
    _write_closeout(tmp_path)

    payload = op_plan.run_football_external_benchmark_operationalization_plan(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_operationalization_plan_v1"
    plan = json.loads((output_root / "benchmark_operationalization_plan.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "product_decision_surface_contract.json").read_text(encoding="utf-8"))
    gates = json.loads((output_root / "stage_gate_transition_plan.json").read_text(encoding="utf-8"))
    risks = json.loads((output_root / "risk_register.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operationalizationPlanReady"] is True
    assert payload["externalSourceCount"] == 2
    assert payload["apiRoutePath"] == "/api/external/benchmark/report"
    assert payload["htmlRoutePath"] == "/external/benchmark/report"
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_decision_surface"
    assert plan["recommendedMilestones"][0]["nextLever"] == "football_external_benchmark_product_decision_surface"
    assert contract["apiRoutePath"] == "/api/external/benchmark/report"
    assert contract["allowsDetectorEvaluationReadiness"] is False
    assert gates["allowedNow"] == ["read_only_product_decision_surface"]
    assert risks["riskCount"] >= 3


def test_operationalization_plan_blocks_without_closed_lane(tmp_path: Path) -> None:
    payload = op_plan.run_football_external_benchmark_operationalization_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_lane_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_lane_closeout"


def test_operationalization_plan_blocks_guardrail_violation(tmp_path: Path) -> None:
    _write_closeout(tmp_path, unsafe_flag=True)

    payload = op_plan.run_football_external_benchmark_operationalization_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_operationalization_guardrail_violation"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_lane_closeout_evidence_repair"


def test_operationalization_plan_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_closeout(tmp_path)

    payload = op_plan.run_football_external_benchmark_operationalization_plan(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_operationalization_plan",
        "external_benchmark_operationalization_contract_repair",
        "external_benchmark_operationalization_blocker_summary",
    ]
