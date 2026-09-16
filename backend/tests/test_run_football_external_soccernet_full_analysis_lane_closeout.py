from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_full_analysis_lane_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, report_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    report_root = candidate_root / "football_external_soccernet_full_analysis_report_smoke_v1"
    _write_json(
        report_root / "full_analysis_report_smoke_summary.json",
        {
            "goalAchieved": report_ready,
            "primaryBlocker": None if report_ready else "football_external_soccernet_full_analysis_report_gap",
            "fullAnalysisReportReady": report_ready,
            "reportedFrameCount": 146893 if report_ready else 0,
            "segmentCount": 196 if report_ready else 0,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateEvaluationExecuted": False,
        },
    )
    _write_json(
        report_root / "full_analysis_report_payload.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_report_payload_v1",
            "reportedFrameCount": 146893 if report_ready else 0,
            "segmentCount": 196 if report_ready else 0,
            "readiness": {
                "fullAnalysisReportReady": report_ready,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    return candidate_root


def test_full_analysis_lane_closeout_selects_product_integration(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = closeout.run_football_external_soccernet_full_analysis_lane_closeout(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_full_analysis_lane_closeout_v1"
    matrix = json.loads((output_root / "full_analysis_capability_matrix.json").read_text(encoding="utf-8"))
    prep = json.loads((output_root / "full_analysis_product_integration_contract_prep.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["fullAnalysisLaneClosed"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["fullAnalysisProductIntegrationReady"] is True
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["candidateEvaluationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_product_integration"
    assert matrix["coveredCapabilities"]["full224pFrameAnalysis"] is True
    assert prep["fullAnalysisProductIntegrationReady"] is True


def test_full_analysis_lane_closeout_blocks_without_report(tmp_path: Path) -> None:
    _write_inputs(tmp_path, report_ready=False)

    payload = closeout.run_football_external_soccernet_full_analysis_lane_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_full_analysis_report_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_report_smoke"


def test_full_analysis_lane_closeout_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = closeout.run_football_external_soccernet_full_analysis_lane_closeout(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_full_analysis_lane_closeout",
        "soccernet_full_analysis_closeout_repair",
        "soccernet_full_analysis_closeout_blocker_summary",
    ]
