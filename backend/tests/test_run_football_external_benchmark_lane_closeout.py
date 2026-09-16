from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_summary(storage_root: Path, dirname: str, filename: str, payload: dict[str, object]) -> None:
    _write_json(_candidate_root(storage_root) / dirname / filename, payload)


def _write_lane_inputs(tmp_path: Path, *, missing_route: bool = False, soccertrack_closed: bool = True) -> None:
    base_payload = {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": None,
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "normalMatchStorageMutationExecuted": False,
        "videoDownloadExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
    }
    _write_summary(
        tmp_path,
        "football_external_soccernet_analysis_product_lane_closeout_v1",
        "analysis_product_lane_closeout_summary.json",
        {
            **base_payload,
            "batchName": "football_external_soccernet_analysis_product_lane_closeout",
            "analysisProductLaneClosed": True,
            "reportedFrameCount": 146893,
            "segmentCount": 196,
        },
    )
    _write_summary(
        tmp_path,
        "football_external_soccertrack_lane_closeout_v1",
        "soccertrack_lane_closeout_summary.json",
        {
            **base_payload,
            "batchName": "football_external_soccertrack_lane_closeout",
            "goalAchieved": soccertrack_closed,
            "primaryBlocker": None if soccertrack_closed else "soccertrack_not_closed",
            "soccertrackLaneClosed": soccertrack_closed,
            "selectedMatchId": "117092",
            "downloadedFixtureFileCount": 11,
            "reportedEventCount": 3142,
            "reportedFrameCount": 20,
        },
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_harness_prep_v1",
        "external_benchmark_harness_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_harness_prep", "externalSourceCount": 2, "benchmarkHarnessPrepReady": True},
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_harness_smoke_v1",
        "external_benchmark_smoke_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_harness_smoke", "externalBenchmarkHarnessSmokePassed": True, "smokeCaseCount": 2},
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_execution_approval_v1",
        "external_benchmark_execution_approval_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_execution_approval", "externalBenchmarkExecutionApproved": True, "approvedSmokeCaseCount": 2},
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_bounded_execution_smoke_v1",
        "external_benchmark_bounded_execution_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_bounded_execution_smoke", "boundedBenchmarkExecutionSmokePassed": True, "resultRowCount": 2},
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_report_smoke_v1",
        "external_benchmark_report_smoke_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_report_smoke", "externalBenchmarkReportSmokePassed": True, "reportRowCount": 2},
    )
    _write_summary(
        tmp_path,
        "football_external_benchmark_product_ui_binding_v1",
        "external_benchmark_product_ui_binding_summary.json",
        {**base_payload, "batchName": "football_external_benchmark_product_ui_binding", "productUiBindingReady": True, "productRouteImplementationReady": True, "sourceCount": 2},
    )
    if not missing_route:
        _write_summary(
            tmp_path,
            "football_external_benchmark_product_ui_route_implementation_v1",
            "external_benchmark_product_ui_route_implementation_summary.json",
            {
                **base_payload,
                "batchName": "football_external_benchmark_product_ui_route_implementation",
                "productUiRouteReady": True,
                "sourceCount": 2,
                "apiRoutePath": "/api/external/benchmark/report",
                "htmlRoutePath": "/external/benchmark/report",
            },
        )


def test_benchmark_lane_closeout_summarizes_closed_external_benchmark_lane(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path)

    payload = closeout.run_football_external_benchmark_lane_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_benchmark_lane_closeout_v1"
    capability = json.loads((output_root / "external_benchmark_capability_matrix.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_root / "external_benchmark_evidence_index.json").read_text(encoding="utf-8"))
    gaps = json.loads((output_root / "remaining_gap_analysis.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["externalBenchmarkLaneClosed"] is True
    assert payload["externalSourceCount"] == 2
    assert payload["benchmarkProductUiRouteReady"] is True
    assert payload["apiRoutePath"] == "/api/external/benchmark/report"
    assert payload["htmlRoutePath"] == "/external/benchmark/report"
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_operationalization_plan"
    assert capability["soccernetAnalysisProductLaneClosed"] is True
    assert capability["soccertrackLaneClosed"] is True
    assert capability["benchmarkProductUiRouteReady"] is True
    assert capability["trainingReady"] is False
    assert len(evidence["requiredEvidence"]) == 9
    assert gaps["remainingPrimaryGap"] == "external_benchmark_operationalization_not_yet_planned"


def test_benchmark_lane_closeout_blocks_when_required_evidence_missing(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path, missing_route=True)

    payload = closeout.run_football_external_benchmark_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_lane_required_evidence_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_ui_route_implementation"


def test_benchmark_lane_closeout_blocks_when_source_lane_not_closed(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path, soccertrack_closed=False)

    payload = closeout.run_football_external_benchmark_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_source_lane_not_closed"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_lane_closeout"


def test_benchmark_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_lane_inputs(tmp_path)

    payload = closeout.run_football_external_benchmark_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_lane_closeout",
        "external_benchmark_closeout_evidence_repair",
        "external_benchmark_closeout_blocker_summary",
    ]
