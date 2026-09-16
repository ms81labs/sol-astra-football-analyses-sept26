from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_product_decision_surface as decision_surface


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_operationalization(storage_root: Path, *, ready: bool = True, unsafe_flag: bool = False) -> None:
    root = _candidate_root(storage_root) / "football_external_benchmark_operationalization_plan_v1"
    _write_json(
        root / "external_benchmark_operationalization_summary.json",
        {
            "batchName": "football_external_benchmark_operationalization_plan",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_benchmark_lane_closeout_missing",
            "operationalizationPlanReady": ready,
            "productDecisionSurfaceReady": ready,
            "externalBenchmarkLaneClosed": ready,
            "externalSourceCount": 2,
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": unsafe_flag,
        },
    )
    _write_json(
        root / "benchmark_operationalization_plan.json",
        {
            "schemaVersion": "external_benchmark_operationalization_plan_v1",
            "externalSourceCount": 2,
            "availableReadOnlyRoutes": [
                {"routeKind": "benchmark_report_api", "path": "/api/external/benchmark/report"},
                {"routeKind": "benchmark_report_html", "path": "/external/benchmark/report"},
                {"routeKind": "soccernet_analysis_product", "path": "/external/soccernet/full-analysis"},
                {"routeKind": "soccertrack_analysis_product", "path": "/external/soccertrack/117092/analysis"},
            ],
            "recommendedMilestones": [
                {"order": 1, "nextLever": "football_external_benchmark_product_decision_surface", "purpose": "Expose a read-only product decision surface."},
                {"order": 2, "nextLever": "football_external_benchmark_real_evaluation_design", "purpose": "Design a real detector benchmark."},
                {"order": 3, "nextLever": "football_external_benchmark_dataset_governance_plan", "purpose": "Define download and storage governance."},
            ],
            "sourceCoverage": {
                "soccernetReportedFrameCount": 146893,
                "soccertrackReportedEventCount": 3142,
                "soccertrackReportedFrameCount": 20,
            },
        },
    )
    _write_json(
        root / "product_decision_surface_contract.json",
        {
            "schemaVersion": "external_benchmark_product_decision_surface_contract_v1",
            "productDecisionSurfaceReady": ready,
            "apiRoutePath": "/api/external/benchmark/report",
            "htmlRoutePath": "/external/benchmark/report",
            "requiredCopy": [
                "This benchmark surface is generated-truth smoke, not detector evaluation.",
                "No model promotion or runtime default mutation is implied.",
            ],
            "allowsDetectorEvaluationReadiness": False,
            "allowsCandidateEvaluationReadiness": False,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "allowsDataDownload": False,
            "allowsVideoDownload": False,
            "allowsNormalMatchStorageMutation": False,
        },
    )
    _write_json(
        root / "stage_gate_transition_plan.json",
        {
            "schemaVersion": "external_benchmark_stage_gate_transition_plan_v1",
            "allowedNow": ["read_only_product_decision_surface"],
            "blockedUntilExplicitApproval": [
                "real_detector_benchmark_execution",
                "source_video_download",
                "normal_match_storage_ingestion",
                "candidate_evaluation_readiness",
                "promotion",
                "runtime_default_mutation",
            ],
        },
    )
    _write_json(
        root / "risk_register.json",
        {
            "schemaVersion": "external_benchmark_operationalization_risk_register_v1",
            "riskCount": 2,
            "risks": [
                {"riskId": "benchmark_smoke_overclaim", "severity": "high", "mitigation": "Keep readiness false."},
                {"riskId": "unbounded_external_download", "severity": "high", "mitigation": "Require governance."},
            ],
        },
    )


def test_product_decision_surface_writes_route_ready_view_model_and_recommendations(tmp_path: Path) -> None:
    _write_operationalization(tmp_path)

    payload = decision_surface.run_football_external_benchmark_product_decision_surface(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_product_decision_surface_v1"
    view_model = json.loads((output_root / "product_decision_surface_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "product_decision_surface_route_contract.json").read_text(encoding="utf-8"))
    recommendations = json.loads((output_root / "benchmark_decision_recommendation_matrix.json").read_text(encoding="utf-8"))
    guardrails = json.loads((output_root / "guardrail_status_audit.json").read_text(encoding="utf-8"))
    html = (output_root / "product_decision_surface_render_smoke.html").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productDecisionSurfaceReady"] is True
    assert payload["productDecisionRouteImplementationReady"] is True
    assert payload["externalSourceCount"] == 2
    assert payload["apiRoutePath"] == "/api/external/benchmark/decision"
    assert payload["htmlRoutePath"] == "/external/benchmark/decision"
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_decision_surface_route_implementation"
    assert view_model["schemaVersion"] == "external_benchmark_product_decision_surface_view_model_v1"
    assert view_model["hero"]["title"] == "External Benchmark Decision Surface"
    assert route_contract["apiRoutePath"] == "/api/external/benchmark/decision"
    assert route_contract["allowsTraining"] is False
    assert recommendations["recommendedNextLever"] == "football_external_benchmark_real_evaluation_design"
    assert guardrails["allGuardrailsPassed"] is True
    assert "External Benchmark Decision Surface" in html
    assert "not detector evaluation" in html


def test_product_decision_surface_blocks_without_operationalization_truth(tmp_path: Path) -> None:
    payload = decision_surface.run_football_external_benchmark_product_decision_surface(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_operationalization_plan_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_operationalization_plan"


def test_product_decision_surface_blocks_guardrail_violation(tmp_path: Path) -> None:
    _write_operationalization(tmp_path, unsafe_flag=True)

    payload = decision_surface.run_football_external_benchmark_product_decision_surface(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_product_decision_surface_guardrail_violation"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_operationalization_contract_repair"


def test_product_decision_surface_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_operationalization(tmp_path)

    payload = decision_surface.run_football_external_benchmark_product_decision_surface(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_product_decision_surface",
        "external_benchmark_product_decision_surface_contract_repair",
        "external_benchmark_product_decision_surface_blocker_summary",
    ]
