from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_analysis_report_smoke as report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, execution_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    execution_root = candidate_root / "football_external_soccernet_bounded_analysis_execution_v1"
    _write_json(
        execution_root / "bounded_analysis_execution_summary.json",
        {
            "goalAchieved": execution_ready,
            "primaryBlocker": None if execution_ready else "football_external_soccernet_bounded_analysis_execution_failed",
            "boundedAnalysisExecutionExecuted": execution_ready,
            "requestedFrameCount": 300 if execution_ready else 0,
            "analyzedFrameCount": 300 if execution_ready else 0,
            "missingFrameCount": 0,
            "unreadableFrameCount": 0,
            "fullAnalysisExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        execution_root / "bounded_analysis_product_payload.json",
        {
            "schemaVersion": "soccernet_external_bounded_analysis_product_payload_v1",
            "frameCount": 300 if execution_ready else 0,
            "aggregateFrameSignals": {
                "requestedFrameCount": 300 if execution_ready else 0,
                "analyzedFrameCount": 300 if execution_ready else 0,
                "missingFrameCount": 0,
                "unreadableFrameCount": 0,
                "meanBrightnessP50": 77.5,
                "greenDominantPixelRatioP50": 0.82,
                "edgeDensityP50": 0.12,
            },
            "readiness": {
                "boundedAnalysisExecutionReady": execution_ready,
                "boundedReportReady": execution_ready,
                "fullAnalysisReady": False,
                "trainingReady": False,
                "promotionReady": False,
            },
        },
    )
    return candidate_root


def test_bounded_analysis_report_smoke_writes_markdown_and_product_payload(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = report.run_football_external_soccernet_bounded_analysis_report_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_bounded_analysis_report_smoke_v1"
    report_payload = json.loads((output_root / "bounded_analysis_report_payload.json").read_text(encoding="utf-8"))
    report_md = (output_root / "bounded_analysis_report.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["boundedAnalysisReportReady"] is True
    assert payload["reportedFrameCount"] == 300
    assert payload["fullAnalysisReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_lane_closeout"
    assert report_payload["schemaVersion"] == "soccernet_external_bounded_analysis_report_payload_v1"
    assert "300" in report_md
    assert "Full analysis ready: `False`" in report_md


def test_bounded_analysis_report_smoke_blocks_without_execution(tmp_path: Path) -> None:
    _write_inputs(tmp_path, execution_ready=False)

    payload = report.run_football_external_soccernet_bounded_analysis_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_bounded_analysis_execution_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_analysis_execution"


def test_bounded_analysis_report_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = report.run_football_external_soccernet_bounded_analysis_report_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_bounded_analysis_report_smoke",
        "soccernet_bounded_analysis_report_payload_repair",
        "soccernet_bounded_analysis_report_blocker_summary",
    ]
