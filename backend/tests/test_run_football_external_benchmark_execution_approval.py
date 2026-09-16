from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_smoke_inputs(tmp_path: Path, *, smoke_ready: bool = True) -> Path:
    root = _candidate_root(tmp_path)
    smoke_root = root / "football_external_benchmark_harness_smoke_v1"
    _write_json(
        smoke_root / "external_benchmark_smoke_summary.json",
        {
            "batchName": "football_external_benchmark_harness_smoke",
            "goalAchieved": smoke_ready,
            "roadmapAdvanceAllowed": smoke_ready,
            "primaryBlocker": None if smoke_ready else "football_external_benchmark_harness_schema_gap",
            "externalBenchmarkHarnessSmokePassed": smoke_ready,
            "externalBenchmarkExecutionApprovalReady": smoke_ready,
            "externalBenchmarkExecutionReady": False,
            "externalSourceCount": 2 if smoke_ready else 0,
            "smokeCaseCount": 2 if smoke_ready else 0,
            "allSourceArtifactsPresent": smoke_ready,
            "schemaSmokePassed": smoke_ready,
            "metricFamilyCoveragePassed": smoke_ready,
            "stageGateSmokePassed": smoke_ready,
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )
    _write_json(
        smoke_root / "benchmark_smoke_case_manifest.json",
        {
            "schemaVersion": "football_external_benchmark_smoke_case_manifest_v1",
            "smokeCaseCount": 2 if smoke_ready else 0,
            "smokeCases": [
                {
                    "sourceId": "soccernet",
                    "caseId": "soccernet_generated_truth_smoke",
                    "artifactPaths": ["soccernet-summary.json"],
                    "expectedMetricFamilies": ["analysis_product_surface", "event_semantics"],
                    "detectorEvaluationExecuted": False,
                    "trainingUseAllowed": False,
                    "videoDownloadAllowed": False,
                },
                {
                    "sourceId": "soccertrack",
                    "caseId": "soccertrack_generated_truth_smoke",
                    "artifactPaths": ["soccertrack-summary.json"],
                    "expectedMetricFamilies": ["analysis_product_surface", "event_semantics"],
                    "detectorEvaluationExecuted": False,
                    "trainingUseAllowed": False,
                    "videoDownloadAllowed": False,
                },
            ]
            if smoke_ready
            else [],
        },
    )
    _write_json(
        smoke_root / "stage_gate_smoke_audit.json",
        {
            "schemaVersion": "football_external_benchmark_stage_gate_smoke_audit_v1",
            "stageGateSmokePassed": smoke_ready,
            "missingRequiredStageCoverage": [],
        },
    )
    return root


def test_execution_approval_writes_bounded_contract(tmp_path: Path) -> None:
    root = _write_smoke_inputs(tmp_path)

    payload = approval.run_football_external_benchmark_execution_approval(storage_root=tmp_path)

    output_root = root / "football_external_benchmark_execution_approval_v1"
    contract = json.loads((output_root / "external_benchmark_execution_approval_contract.json").read_text(encoding="utf-8"))
    scope = json.loads((output_root / "execution_scope_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["externalBenchmarkExecutionApproved"] is True
    assert payload["externalBenchmarkExecutionReady"] is False
    assert payload["approvedSmokeCaseCount"] == 2
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_bounded_execution_smoke"
    assert contract["approvedExecutionMode"] == "generated_truth_bounded_smoke"
    assert contract["detectorBenchmarkAllowed"] is False
    assert contract["normalMatchStorageMutationAllowed"] is False
    assert scope["approvedSourceIds"] == ["soccernet", "soccertrack"]


def test_execution_approval_blocks_without_harness_smoke(tmp_path: Path) -> None:
    _write_smoke_inputs(tmp_path, smoke_ready=False)

    payload = approval.run_football_external_benchmark_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_harness_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_harness_smoke"


def test_execution_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_smoke_inputs(tmp_path)

    payload = approval.run_football_external_benchmark_execution_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_execution_approval",
        "external_benchmark_execution_scope_repair",
        "external_benchmark_execution_approval_blocker_summary",
    ]
