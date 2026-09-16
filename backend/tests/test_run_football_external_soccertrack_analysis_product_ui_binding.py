from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_analysis_product_ui_binding as binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_report_outputs(tmp_path: Path, *, ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    report_root = candidate_root / "football_external_soccertrack_analysis_report_smoke_v1"
    _write_json(
        report_root / "soccertrack_analysis_report_smoke_summary.json",
        {
            "batchName": "football_external_soccertrack_analysis_report_smoke",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "report_failed",
            "analysisReportSmokePassed": ready,
            "analysisReportReady": ready,
            "productRouteReady": ready,
            "selectedMatchId": "117092" if ready else None,
            "reportedEventCount": 2 if ready else 0,
            "reportedFrameCount": 1 if ready else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "nextRecommendedNextLever": "football_external_soccertrack_analysis_product_ui_binding",
        },
    )
    _write_json(
        report_root / "soccertrack_analysis_report_payload.json",
        {
            "schemaVersion": "soccertrack_external_analysis_report_payload_v1",
            "sourceDataset": "soccertrack_v2",
            "selectedMatchId": "117092",
            "routePath": "/api/external/soccertrack/117092/export/match.json",
            "match": {"id": "soccertrack:117092", "name": "SoccerTrack 117092"},
            "reportedEventCount": 2 if ready else 0,
            "reportedFrameCount": 1 if ready else 0,
            "taskFixtureSummary": {
                "basEventCount": 2 if ready else 0,
                "gsrHalfCount": 2,
                "motFrameCount": 20,
                "motSampledFrameCount": 1,
            },
            "eventTypeBreakdown": [{"value": "PASS", "count": 1}, {"value": "DRIVE", "count": 1}],
            "teamBreakdown": [{"value": "right", "count": 1}, {"value": "left", "count": 1}],
            "ballStatusBreakdown": [{"value": "ALIVE", "count": 1}],
            "readiness": {
                "analysisReportReady": ready,
                "productRouteReady": ready,
                "candidateEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitations": ["not detector evaluation", "does not train or promote a detector"],
        },
    )
    (report_root / "soccertrack_analysis_report.md").write_text(
        "# SoccerTrack External Fixture Report\n\nPASS\n\nnot detector evaluation\n",
        encoding="utf-8",
    )
    return candidate_root


def test_soccertrack_analysis_product_ui_binding_writes_view_model_and_html(tmp_path: Path) -> None:
    candidate_root = _write_report_outputs(tmp_path)

    payload = binding.run_football_external_soccertrack_analysis_product_ui_binding(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_analysis_product_ui_binding_v1"
    view_model = json.loads((output_root / "analysis_product_ui_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "analysis_product_ui_route_contract.json").read_text(encoding="utf-8"))
    html = (output_root / "analysis_product_ui_render_smoke.html").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productUiBindingReady"] is True
    assert payload["selectedMatchId"] == "117092"
    assert payload["reportedEventCount"] == 2
    assert payload["reportedFrameCount"] == 1
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_product_ui_route_implementation"
    assert view_model["hero"]["title"] == "SoccerTrack 117092 external fixture"
    assert view_model["cards"][0]["label"] == "Events"
    assert view_model["readiness"]["candidateEvaluationReady"] is False
    assert route_contract["routePath"] == "/external/soccertrack/117092/analysis"
    assert route_contract["allowsTraining"] is False
    assert "SoccerTrack 117092 external fixture" in html
    assert "not detector evaluation" in html


def test_soccertrack_analysis_product_ui_binding_blocks_without_report(tmp_path: Path) -> None:
    _write_report_outputs(tmp_path, ready=False)

    payload = binding.run_football_external_soccertrack_analysis_product_ui_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_analysis_report_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_report_smoke"


def test_soccertrack_analysis_product_ui_binding_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_report_outputs(tmp_path)

    payload = binding.run_football_external_soccertrack_analysis_product_ui_binding(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_analysis_product_ui_binding",
        "soccertrack_analysis_product_ui_contract_repair",
        "soccertrack_analysis_product_ui_blocker_summary",
    ]
