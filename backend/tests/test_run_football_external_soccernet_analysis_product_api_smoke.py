from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_analysis_product_api_smoke as smoke


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, product_ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    source_root = candidate_root / "football_external_soccernet_full_analysis_product_integration_v1"
    _write_json(
        source_root / "full_analysis_product_integration_summary.json",
        {
            "batchName": "football_external_soccernet_full_analysis_product_integration",
            "goalAchieved": product_ready,
            "primaryBlocker": None if product_ready else "football_external_soccernet_full_analysis_product_contract_gap",
            "roadmapAdvanceAllowed": product_ready,
            "productFullAnalysisReady": product_ready,
            "reportedFrameCount": 146893 if product_ready else 0,
            "segmentCount": 196 if product_ready else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        source_root / "product_full_analysis_payload.json",
        {
            "schemaVersion": "soccernet_external_full_analysis_product_payload_v1",
            "frameCount": 146893,
            "segmentCount": 196,
            "sourceReportPath": str(source_root / "product_full_analysis_report.md"),
            "sourceVideoPath": str(candidate_root / "football_external_soccernet_video_member_extract_v1/extracted_video/game/224p.mp4"),
            "summaryCards": [
                {"label": "Frames analyzed", "value": 146893},
                {"label": "Timeline segments", "value": 196},
                {"label": "Resolution", "value": "398x224"},
                {"label": "Median motion delta", "value": 4.795114},
            ],
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
                "productFullAnalysisReady": product_ready,
                "full224pAnalysisReady": product_ready,
                "videoPlaybackReady": product_ready,
                "trainingReady": False,
                "promotionReady": False,
                "candidateEvaluationReady": False,
                "runtimeDefaultMutationReady": False,
            },
            "limitations": [
                "full extracted 224p member only",
                "not detector evaluation",
                "not ball-localization truth",
            ],
            "remainingGaps": ["ball_localization_truth_not_evaluated"],
        },
    )
    _write_json(
        source_root / "product_ui_copy.json",
        {
            "title": "SoccerNet full 224p analysis",
            "subtitle": "Full extracted SoccerNet video summarized with lightweight frame-signal timelines.",
            "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
            "safeNextAction": "Run product API smoke before any detector evaluation.",
            "productFullAnalysisReady": product_ready,
            "candidateEvaluationReady": False,
        },
    )
    _write_json(
        source_root / "product_integration_contract.json",
        {
            "contractName": "football_external_soccernet_full_analysis_product_integration",
            "productFullAnalysisReady": product_ready,
            "requiresTraining": False,
            "allowsPromotion": False,
            "allowsCandidateEvaluationReadiness": False,
            "allowsRuntimeDefaultMutation": False,
            "mustShowLimitationsBanner": True,
            "nextSmokeRequiredBeforeUserFacingApi": True,
        },
    )
    return candidate_root


def test_analysis_product_api_smoke_writes_response_fixture_and_preserves_safety_flags(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_analysis_product_api_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_analysis_product_api_smoke_v1"
    response_fixture = json.loads((output_root / "analysis_product_api_response_fixture.json").read_text(encoding="utf-8"))
    contract_audit = json.loads((output_root / "analysis_product_api_payload_contract_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productApiSmokePassed"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["segmentCount"] == 196
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_ui_binding"
    assert response_fixture["statusCode"] == 200
    assert response_fixture["body"]["analysis"]["frameCount"] == 146893
    assert response_fixture["body"]["readiness"]["candidateEvaluationReady"] is False
    assert response_fixture["body"]["ui"]["limitationsBanner"]
    assert contract_audit["payloadContractValid"] is True
    assert contract_audit["apiResponseFixtureValid"] is True


def test_analysis_product_api_smoke_blocks_without_product_integration(tmp_path: Path) -> None:
    _write_inputs(tmp_path, product_ready=False)

    payload = smoke.run_football_external_soccernet_analysis_product_api_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_full_analysis_product_integration_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_full_analysis_product_integration"


def test_analysis_product_api_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = smoke.run_football_external_soccernet_analysis_product_api_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_analysis_product_api_smoke",
        "soccernet_analysis_product_api_contract_repair",
        "soccernet_analysis_product_api_blocker_summary",
    ]
