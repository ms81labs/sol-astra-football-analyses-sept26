from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_bounded_execution_smoke as execution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_inputs(tmp_path: Path, *, approval_ready: bool = True) -> Path:
    root = _candidate_root(tmp_path)
    approval_root = root / "football_external_benchmark_execution_approval_v1"
    smoke_root = root / "football_external_benchmark_harness_smoke_v1"
    soccernet_analysis = root / "football_external_soccernet_analysis_product_lane_closeout_v1" / "analysis_product_lane_closeout_summary.json"
    soccernet_events = root / "football_external_soccernet_event_lane_closeout_v1" / "soccernet_event_lane_closeout_summary.json"
    soccertrack = root / "football_external_soccertrack_lane_closeout_v1" / "soccertrack_lane_closeout_summary.json"

    _write_json(
        approval_root / "external_benchmark_execution_approval_summary.json",
        {
            "goalAchieved": approval_ready,
            "primaryBlocker": None if approval_ready else "football_external_benchmark_execution_scope_gap",
            "externalBenchmarkExecutionApproved": approval_ready,
            "approvedExecutionMode": "generated_truth_bounded_smoke",
            "approvedSmokeCaseCount": 2 if approval_ready else 0,
            "approvedSourceIds": ["soccernet", "soccertrack"] if approval_ready else [],
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
        approval_root / "external_benchmark_execution_approval_contract.json",
        {
            "schemaVersion": "football_external_benchmark_execution_approval_contract_v1",
            "externalBenchmarkExecutionApproved": approval_ready,
            "approvedExecutionMode": "generated_truth_bounded_smoke",
            "approvedSourceIds": ["soccernet", "soccertrack"] if approval_ready else [],
            "approvedSmokeCaseCount": 2 if approval_ready else 0,
            "detectorBenchmarkAllowed": False,
            "datasetDownloadAllowed": False,
            "videoDownloadAllowed": False,
            "normalMatchStorageMutationAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        smoke_root / "benchmark_smoke_case_manifest.json",
        {
            "schemaVersion": "football_external_benchmark_smoke_case_manifest_v1",
            "smokeCaseCount": 2,
            "smokeCases": [
                {
                    "sourceId": "soccernet",
                    "caseId": "soccernet_generated_truth_smoke",
                    "artifactPaths": [str(soccernet_analysis), str(soccernet_events)],
                    "expectedMetricFamilies": ["analysis_product_surface", "event_semantics"],
                },
                {
                    "sourceId": "soccertrack",
                    "caseId": "soccertrack_generated_truth_smoke",
                    "artifactPaths": [str(soccertrack)],
                    "expectedMetricFamilies": ["analysis_product_surface", "event_semantics"],
                },
            ],
        },
    )
    _write_json(
        soccernet_analysis,
        {
            "batchName": "football_external_soccernet_analysis_product_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "reportedFrameCount": 146893,
            "segmentCount": 196,
        },
    )
    _write_json(
        soccernet_events,
        {
            "batchName": "football_external_soccernet_event_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "eventCount": 1604,
            "distinctEventTypeCount": 12,
        },
    )
    _write_json(
        soccertrack,
        {
            "batchName": "football_external_soccertrack_lane_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "selectedMatchId": "117092",
            "downloadedFixtureFileCount": 11,
            "reportedEventCount": 3142,
            "reportedFrameCount": 20,
        },
    )
    return root


def test_bounded_execution_smoke_writes_cross_source_results(tmp_path: Path) -> None:
    root = _write_inputs(tmp_path)

    payload = execution.run_football_external_benchmark_bounded_execution_smoke(storage_root=tmp_path)

    output_root = root / "football_external_benchmark_bounded_execution_smoke_v1"
    results = json.loads((output_root / "bounded_execution_result_table.json").read_text(encoding="utf-8"))
    report = json.loads((output_root / "benchmark_report_payload.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["boundedBenchmarkExecutionSmokePassed"] is True
    assert payload["resultRowCount"] == 2
    assert payload["externalBenchmarkReportReady"] is True
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_report_smoke"
    assert [row["sourceId"] for row in results["rows"]] == ["soccernet", "soccertrack"]
    assert results["rows"][0]["eventCount"] == 1604
    assert results["rows"][1]["eventCount"] == 3142
    assert report["reportReady"] is True


def test_bounded_execution_smoke_blocks_without_execution_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approval_ready=False)

    payload = execution.run_football_external_benchmark_bounded_execution_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_execution_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_execution_approval"


def test_bounded_execution_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = execution.run_football_external_benchmark_bounded_execution_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_bounded_execution_smoke",
        "external_benchmark_bounded_execution_contract_repair",
        "external_benchmark_bounded_execution_blocker_summary",
    ]
