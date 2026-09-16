from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_full_analysis_product_integration as integration


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, closeout_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    closeout_root = candidate_root / "football_external_soccernet_full_analysis_lane_closeout_v1"
    report_root = candidate_root / "football_external_soccernet_full_analysis_report_smoke_v1"
    execution_root = candidate_root / "football_external_soccernet_full_analysis_execution_v1"
    _write_json(
        closeout_root / "full_analysis_lane_closeout_summary.json",
        {
            "batchName": "football_external_soccernet_full_analysis_lane_closeout",
            "goalAchieved": closeout_goal,
            "primaryBlocker": None if closeout_goal else "football_external_soccernet_full_analysis_closeout_gap",
            "fullAnalysisLaneClosed": closeout_goal,
            "fullAnalysisProductIntegrationReady": closeout_goal,
            "reportedFrameCount": 146893 if closeout_goal else 0,
            "segmentCount": 196 if closeout_goal else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        closeout_root / "full_analysis_product_integration_contract_prep.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_product_integration_prep_v1",
            "sourceBatch": "football_external_soccernet_full_analysis_lane_closeout",
            "fullAnalysisProductIntegrationReady": closeout_goal,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "candidateEvaluationReadinessAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        closeout_root / "remaining_gap_analysis.json",
        {
            "remainingGaps": [
                "ball_localization_truth_not_evaluated",
                "detector_evaluation_not_requested",
                "720p_member_not_downloaded_or_processed",
            ],
        },
    )
    _write_json(
        report_root / "full_analysis_report_payload.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_report_payload_v1",
            "reportedFrameCount": 146893,
            "segmentCount": 196,
            "aggregateFrameSignals": {
                "width": 398,
                "height": 224,
                "fps": 25.0,
                "meanBrightnessP50": 105.457578,
                "greenDominantPixelRatioP50": 0.729956,
                "motionDeltaP50": 4.795114,
                "unreadableFrameCount": 0,
            },
            "readiness": {
                "fullAnalysisReportReady": True,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitations": ["full extracted 224p member only"],
        },
    )
    (report_root / "full_analysis_report.md").parent.mkdir(parents=True, exist_ok=True)
    (report_root / "full_analysis_report.md").write_text("# SoccerNet Full 224p Analysis Report\n", encoding="utf-8")
    _write_json(
        execution_root / "full_analysis_product_payload.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_product_payload_v1",
            "frameCount": 146893,
            "segmentCount": 196,
            "videoPath": str(candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"),
            "readiness": {
                "fullAnalysisExecutionReady": True,
                "fullAnalysisReportReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
        },
    )
    return candidate_root


def test_full_analysis_product_integration_writes_safe_payload(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = integration.run_football_external_soccernet_full_analysis_product_integration(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_full_analysis_product_integration_v1"
    product_payload = json.loads((output_root / "product_full_analysis_payload.json").read_text(encoding="utf-8"))
    copy = json.loads((output_root / "product_ui_copy.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "product_integration_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productFullAnalysisReady"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["segmentCount"] == 196
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_api_smoke"
    assert product_payload["readiness"]["productFullAnalysisReady"] is True
    assert product_payload["readiness"]["candidateEvaluationReady"] is False
    assert product_payload["summaryCards"][0]["value"] == 146893
    assert "not detector evaluation" in copy["limitationsBanner"]
    assert contract["allowsCandidateEvaluationReadiness"] is False


def test_full_analysis_product_integration_blocks_without_closeout(tmp_path: Path) -> None:
    _write_inputs(tmp_path, closeout_goal=False)

    payload = integration.run_football_external_soccernet_full_analysis_product_integration(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_full_analysis_lane_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_lane_closeout"


def test_full_analysis_product_integration_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = integration.run_football_external_soccernet_full_analysis_product_integration(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_full_analysis_product_payload",
        "soccernet_full_analysis_product_contract_repair",
        "soccernet_full_analysis_product_blocker_summary",
    ]
