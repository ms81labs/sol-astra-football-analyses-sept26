from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_report_smoke as report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_inputs(tmp_path: Path, *, report_ready: bool = True) -> Path:
    root = _candidate_root(tmp_path)
    execution_root = root / "football_external_benchmark_bounded_execution_smoke_v1"
    _write_json(
        execution_root / "external_benchmark_bounded_execution_summary.json",
        {
            "goalAchieved": report_ready,
            "primaryBlocker": None if report_ready else "football_external_benchmark_bounded_execution_contract_gap",
            "boundedBenchmarkExecutionSmokePassed": report_ready,
            "externalBenchmarkReportReady": report_ready,
            "resultRowCount": 2 if report_ready else 0,
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
        execution_root / "benchmark_report_payload.json",
        {
            "schemaVersion": "football_external_benchmark_report_payload_v1",
            "reportReady": report_ready,
            "resultRows": [
                {
                    "sourceId": "soccernet",
                    "eventCount": 1604,
                    "reportedFrameCount": 146893,
                    "segmentCount": 196,
                    "metricFamilies": ["analysis_product_surface", "event_semantics"],
                },
                {
                    "sourceId": "soccertrack",
                    "eventCount": 3142,
                    "reportedFrameCount": 20,
                    "selectedMatchId": "117092",
                    "metricFamilies": ["analysis_product_surface", "event_semantics"],
                },
            ]
            if report_ready
            else [],
            "detectorEvaluationIncluded": False,
            "trainingIncluded": False,
        },
    )
    return root


def test_benchmark_report_smoke_writes_markdown_and_view_model(tmp_path: Path) -> None:
    root = _write_inputs(tmp_path)

    payload = report.run_football_external_benchmark_report_smoke(storage_root=tmp_path)

    output_root = root / "football_external_benchmark_report_smoke_v1"
    markdown = (output_root / "external_benchmark_report.md").read_text(encoding="utf-8")
    view_model = json.loads((output_root / "external_benchmark_report_view_model.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["externalBenchmarkReportSmokePassed"] is True
    assert payload["reportRowCount"] == 2
    assert payload["productUiBindingReady"] is True
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_ui_binding"
    assert "soccernet" in markdown
    assert "soccertrack" in markdown
    assert view_model["sourceCount"] == 2
    assert view_model["reportReady"] is True


def test_benchmark_report_smoke_blocks_without_report_payload(tmp_path: Path) -> None:
    _write_inputs(tmp_path, report_ready=False)

    payload = report.run_football_external_benchmark_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_report_payload_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_bounded_execution_smoke"


def test_benchmark_report_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = report.run_football_external_benchmark_report_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_report_smoke",
        "external_benchmark_report_payload_repair",
        "external_benchmark_report_smoke_blocker_summary",
    ]
