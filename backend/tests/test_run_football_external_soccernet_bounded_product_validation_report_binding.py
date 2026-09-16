from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_product_validation_report_binding as binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_execution_truth(storage_root: Path, *, passed: bool = True) -> None:
    root = _candidate_root(storage_root) / "football_external_soccernet_bounded_product_validation_execution_v1"
    _write_json(
        root / "soccernet_bounded_product_validation_execution_summary.json",
        {
            "batchName": "football_external_soccernet_bounded_product_validation_execution",
            "goalAchieved": passed,
            "primaryBlocker": None if passed else "football_external_soccernet_product_validation_reference_gap",
            "roadmapAdvanceAllowed": passed,
            "productValidationExecutionExecuted": passed,
            "validatedProductSliceCount": 4 if passed else 3,
            "failedProductSliceCount": 0 if passed else 1,
            "bulkDownloadExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_bounded_product_validation_report_binding",
        },
    )
    _write_json(
        root / "product_validation_execution_report.json",
        {
            "schemaVersion": "soccernet_bounded_product_validation_execution_report_v1",
            "boundedProductValidationPassed": passed,
            "validatedProductSliceCount": 4 if passed else 3,
            "failedProductSliceCount": 0 if passed else 1,
            "executionBoundary": {
                "bulkDownloadExecuted": False,
                "videoDownloadExecuted": False,
                "dataDownloadExecuted": False,
                "trainingExecuted": False,
                "promotionMutationExecuted": False,
                "runtimeDefaultMutationExecuted": False,
                "normalMatchStorageMutationExecuted": False,
            },
        },
    )
    _write_json(
        root / "product_validation_slice_audit.json",
        {
            "schemaVersion": "soccernet_bounded_product_validation_slice_audit_v1",
            "validatedProductSliceCount": 4 if passed else 3,
            "failedProductSliceCount": 0 if passed else 1,
            "sliceResults": [
                {"sliceId": "soccernet_dry_run_product_bridge", "passed": True, "evidence": {"payloadFrameCount": 300}},
                {"sliceId": "soccernet_full_analysis_product_lane", "passed": True, "evidence": {"fullAnalysisLaneClosed": True}},
                {"sliceId": "external_benchmark_report_product_binding", "passed": True, "evidence": {"realReportPayloadExists": True}},
                {"sliceId": "research_game_state_gap_probe", "passed": passed, "evidence": {"matchedTerms": ["soccernet"]}},
            ],
        },
    )


def test_report_binding_writes_operator_payload_from_passed_validation(tmp_path: Path) -> None:
    _seed_execution_truth(tmp_path)

    payload = binding.run_football_external_soccernet_bounded_product_validation_report_binding(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_bounded_product_validation_report_binding_v1"
    report_payload = json.loads((output_root / "soccernet_bounded_product_validation_report_payload.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "soccernet_bounded_product_validation_route_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["reportBindingReady"] is True
    assert payload["validatedProductSliceCount"] == 4
    assert payload["failedProductSliceCount"] == 0
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_real_sample_product_pipeline_training_decision"
    assert report_payload["readiness"]["reportBindingReady"] is True
    assert route_contract["apiRoutePath"] == "/api/external/soccernet/bounded-product-validation"
    assert (output_root / "soccernet_bounded_product_validation_report.md").exists()


def test_report_binding_blocks_when_execution_truth_failed(tmp_path: Path) -> None:
    _seed_execution_truth(tmp_path, passed=False)

    payload = binding.run_football_external_soccernet_bounded_product_validation_report_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_bounded_product_validation_execution_gap"
    assert payload["reportBindingReady"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_execution"


def test_report_binding_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _seed_execution_truth(tmp_path)

    payload = binding.run_football_external_soccernet_bounded_product_validation_report_binding(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_product_validation_report_binding",
        "soccernet_product_validation_report_contract_repair",
        "soccernet_product_validation_report_blocker_summary",
    ]
