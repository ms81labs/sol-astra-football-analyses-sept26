from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_full_analysis_report_smoke as report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, execution_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    execution_root = candidate_root / "football_external_soccernet_full_analysis_execution_v1"
    _write_json(
        execution_root / "full_analysis_execution_summary.json",
        {
            "goalAchieved": execution_ready,
            "primaryBlocker": None if execution_ready else "football_external_soccernet_full_analysis_frame_count_mismatch",
            "fullAnalysisExecutionExecuted": execution_ready,
            "approvedFrameCount": 146893 if execution_ready else 0,
            "processedFrameCount": 146893 if execution_ready else 0,
            "unreadableFrameCount": 0,
            "segmentCount": 196 if execution_ready else 0,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        execution_root / "full_analysis_product_payload.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_product_payload_v1",
            "frameCount": 146893 if execution_ready else 0,
            "segmentCount": 196 if execution_ready else 0,
            "aggregateFrameSignals": {
                "approvedFrameCount": 146893 if execution_ready else 0,
                "processedFrameCount": 146893 if execution_ready else 0,
                "unreadableFrameCount": 0,
                "segmentCount": 196 if execution_ready else 0,
                "meanBrightnessP50": 105.45,
                "greenDominantPixelRatioP50": 0.73,
                "motionDeltaP50": 4.79,
            },
            "readiness": {
                "fullAnalysisExecutionReady": execution_ready,
                "fullAnalysisReportReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
            },
        },
    )
    return candidate_root


def test_full_analysis_report_smoke_writes_report_artifacts(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = report.run_football_external_soccernet_full_analysis_report_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_full_analysis_report_smoke_v1"
    report_payload = json.loads((output_root / "full_analysis_report_payload.json").read_text(encoding="utf-8"))
    report_md = (output_root / "full_analysis_report.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["fullAnalysisReportReady"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_lane_closeout"
    assert report_payload["schemaVersion"] == "soccernet_external_full_analysis_report_payload_v1"
    assert "146893" in report_md


def test_full_analysis_report_smoke_blocks_without_execution(tmp_path: Path) -> None:
    _write_inputs(tmp_path, execution_ready=False)

    payload = report.run_football_external_soccernet_full_analysis_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_full_analysis_execution_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_execution"


def test_full_analysis_report_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = report.run_football_external_soccernet_full_analysis_report_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_full_analysis_report_smoke",
        "soccernet_full_analysis_report_payload_repair",
        "soccernet_full_analysis_report_blocker_summary",
    ]
