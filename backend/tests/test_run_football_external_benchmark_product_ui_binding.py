from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_product_ui_binding as binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _write_inputs(tmp_path: Path, *, report_ready: bool = True) -> Path:
    root = _candidate_root(tmp_path)
    report_root = root / "football_external_benchmark_report_smoke_v1"
    _write_json(
        report_root / "external_benchmark_report_smoke_summary.json",
        {
            "goalAchieved": report_ready,
            "primaryBlocker": None if report_ready else "football_external_benchmark_report_payload_missing",
            "externalBenchmarkReportSmokePassed": report_ready,
            "productUiBindingReady": report_ready,
            "reportRowCount": 2 if report_ready else 0,
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
        report_root / "external_benchmark_report_view_model.json",
        {
            "schemaVersion": "football_external_benchmark_report_view_model_v1",
            "title": "External Football Benchmark Smoke",
            "reportReady": report_ready,
            "sourceCount": 2 if report_ready else 0,
            "sources": [
                {"sourceId": "soccernet", "eventCount": 1604, "reportedFrameCount": 146893, "segmentCount": 196},
                {"sourceId": "soccertrack", "eventCount": 3142, "reportedFrameCount": 20, "segmentCount": 0},
            ]
            if report_ready
            else [],
            "detectorEvaluationIncluded": False,
            "trainingIncluded": False,
            "mutationIncluded": False,
        },
    )
    (report_root / "external_benchmark_report.md").write_text(
        "# External Football Benchmark Smoke\n\nsoccernet\nsoccertrack\nnot a detector benchmark\n",
        encoding="utf-8",
    )
    return root


def test_benchmark_product_ui_binding_writes_view_model_route_and_html(tmp_path: Path) -> None:
    root = _write_inputs(tmp_path)

    payload = binding.run_football_external_benchmark_product_ui_binding(storage_root=tmp_path)

    output_root = root / "football_external_benchmark_product_ui_binding_v1"
    view_model = json.loads((output_root / "external_benchmark_product_ui_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "external_benchmark_product_ui_route_contract.json").read_text(encoding="utf-8"))
    html = (output_root / "external_benchmark_product_ui_render_smoke.html").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productUiBindingReady"] is True
    assert payload["productRouteImplementationReady"] is True
    assert payload["sourceCount"] == 2
    assert payload["detectorEvaluationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_product_ui_route_implementation"
    assert view_model["hero"]["title"] == "External Benchmark"
    assert view_model["cards"][0]["label"] == "Sources"
    assert view_model["readiness"]["candidateEvaluationReady"] is False
    assert route_contract["apiRoutePath"] == "/api/external/benchmark/report"
    assert route_contract["htmlRoutePath"] == "/external/benchmark/report"
    assert route_contract["allowsRuntimeDefaultMutation"] is False
    assert "External Benchmark" in html
    assert "soccernet" in html
    assert "soccertrack" in html


def test_benchmark_product_ui_binding_blocks_without_report_smoke(tmp_path: Path) -> None:
    _write_inputs(tmp_path, report_ready=False)

    payload = binding.run_football_external_benchmark_product_ui_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_report_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_report_smoke"


def test_benchmark_product_ui_binding_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = binding.run_football_external_benchmark_product_ui_binding(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "external_benchmark_product_ui_binding",
        "external_benchmark_product_ui_contract_repair",
        "external_benchmark_product_ui_binding_blocker_summary",
    ]
