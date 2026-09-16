from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_analysis_product_ui_binding as binding


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_inputs(tmp_path: Path, *, api_smoke_passed: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    source_root = candidate_root / "football_external_soccernet_analysis_product_api_smoke_v1"
    _write_json(
        source_root / "analysis_product_api_smoke_summary.json",
        {
            "batchName": "football_external_soccernet_analysis_product_api_smoke",
            "goalAchieved": api_smoke_passed,
            "primaryBlocker": None if api_smoke_passed else "football_external_soccernet_analysis_product_api_contract_gap",
            "roadmapAdvanceAllowed": api_smoke_passed,
            "productApiSmokePassed": api_smoke_passed,
            "reportedFrameCount": 146893 if api_smoke_passed else 0,
            "segmentCount": 196 if api_smoke_passed else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        source_root / "analysis_product_api_payload_contract_audit.json",
        {
            "schemaVersion": "soccernet_full_analysis_product_api_contract_audit_v1",
            "payloadContractValid": api_smoke_passed,
            "apiResponseFixtureValid": api_smoke_passed,
            "frameCount": 146893 if api_smoke_passed else 0,
            "segmentCount": 196 if api_smoke_passed else 0,
            "candidateEvaluationReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
    )
    _write_json(
        source_root / "analysis_product_api_response_fixture.json",
        {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": {
                "schemaVersion": "soccernet_full_analysis_api_response_v1",
                "analysis": {
                    "frameCount": 146893,
                    "segmentCount": 196,
                    "sourceReportPath": str(source_root / "full_analysis_report.md"),
                    "sourceVideoPath": str(candidate_root / "video/224p.mp4"),
                    "summaryCards": [
                        {"label": "Frames analyzed", "value": 146893},
                        {"label": "Timeline segments", "value": 196},
                        {"label": "Resolution", "value": "398x224"},
                        {"label": "Median motion delta", "value": 4.795114},
                    ],
                    "aggregateFrameSignals": {
                        "meanBrightnessP50": 105.457578,
                        "greenDominantPixelRatioP50": 0.729956,
                        "motionDeltaP50": 4.795114,
                        "unreadableFrameCount": 0,
                    },
                },
                "readiness": {
                    "productFullAnalysisReady": api_smoke_passed,
                    "candidateEvaluationReady": False,
                    "trainingReady": False,
                    "promotionReady": False,
                    "runtimeDefaultMutationReady": False,
                },
                "ui": {
                    "title": "SoccerNet full 224p analysis",
                    "subtitle": "Full extracted SoccerNet video summarized with lightweight frame-signal timelines.",
                    "limitationsBanner": "This is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
                    "safeNextAction": "Bind this payload into product UI before detector evaluation.",
                },
                "limitations": ["not detector evaluation", "not ball-localization truth"],
                "remainingGaps": ["ball_localization_truth_not_evaluated"],
            },
        },
    )
    return candidate_root


def test_analysis_product_ui_binding_writes_view_model_and_html_smoke(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = binding.run_football_external_soccernet_analysis_product_ui_binding(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_analysis_product_ui_binding_v1"
    view_model = json.loads((output_root / "analysis_product_ui_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "analysis_product_ui_route_contract.json").read_text(encoding="utf-8"))
    html = (output_root / "analysis_product_ui_render_smoke.html").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productUiBindingReady"] is True
    assert payload["reportedFrameCount"] == 146893
    assert payload["segmentCount"] == 196
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_ui_route_implementation"
    assert view_model["hero"]["title"] == "SoccerNet full 224p analysis"
    assert view_model["cards"][0]["label"] == "Frames analyzed"
    assert view_model["readiness"]["candidateEvaluationReady"] is False
    assert view_model["limitationsBanner"]
    assert route_contract["routePath"] == "/external/soccernet/full-analysis"
    assert route_contract["allowsCandidateEvaluationReadiness"] is False
    assert "SoccerNet full 224p analysis" in html
    assert "Frames analyzed" in html
    assert "not detector evaluation" in html


def test_analysis_product_ui_binding_blocks_without_api_smoke(tmp_path: Path) -> None:
    _write_inputs(tmp_path, api_smoke_passed=False)

    payload = binding.run_football_external_soccernet_analysis_product_ui_binding(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_analysis_product_api_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_analysis_product_api_smoke"


def test_analysis_product_ui_binding_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = binding.run_football_external_soccernet_analysis_product_ui_binding(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_analysis_product_ui_binding",
        "soccernet_analysis_product_ui_contract_repair",
        "soccernet_analysis_product_ui_blocker_summary",
    ]
