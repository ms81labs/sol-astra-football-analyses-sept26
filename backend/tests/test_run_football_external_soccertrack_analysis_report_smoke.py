from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_analysis_report_smoke as report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_product_route_outputs(tmp_path: Path, *, ready: bool = True, missing_events: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    route_root = candidate_root / "football_external_soccertrack_product_route_smoke_v1"
    _write_json(
        route_root / "soccertrack_product_route_smoke_summary.json",
        {
            "batchName": "football_external_soccertrack_product_route_smoke",
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "route_failed",
            "productRouteSmokePassed": ready,
            "selectedMatchId": "117092" if ready else None,
            "routePath": "/api/external/soccertrack/117092/export/match.json",
            "routeStatusCode": 200 if ready else 404,
            "responseSchemaVersion": "match_bundle_v1" if ready else None,
            "externalBundleEventCount": 0 if missing_events else 2,
            "externalBundleFrameCount": 1 if ready else 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "nextRecommendedNextLever": "football_external_soccertrack_analysis_report_smoke",
        },
    )
    _write_json(
        route_root / "product_route_response_audit.json",
        {
            "schemaVersion": "soccertrack_product_route_response_audit_v1",
            "routeStatusCode": 200 if ready else 404,
            "routePath": "/api/external/soccertrack/117092/export/match.json",
            "body": {
                "schemaVersion": "match_bundle_v1",
                "match": {
                    "id": "soccertrack:117092",
                    "name": "SoccerTrack 117092",
                    "inputMode": "external_soccertrack_fixture",
                },
                "provenance": {
                    "externalDataset": "soccertrack_v2",
                    "externalSourceMatchId": "117092",
                    "runtimeDefaultMutationAllowed": False,
                },
                "analytics": {
                    "summary": {
                        "source": "soccertrack_adapter_smoke",
                        "basEventCount": 0 if missing_events else 2,
                        "gsrHalfCount": 2,
                        "motFrameCount": 20,
                        "motSampledFrameCount": 1,
                    }
                },
                "frames": [{"frameId": 1, "timestamp": 0.04, "ball": {"status": "ALIVE"}}] if ready else [],
                "events": []
                if missing_events
                else [
                    {"id": "evt-1", "type": "PASS", "team": "right", "timestamp": 1.2},
                    {"id": "evt-2", "type": "DRIVE", "team": "left", "timestamp": 2.4},
                ],
            },
        },
    )
    _write_json(
        route_root / "external_route_contract_audit.json",
        {"externalRouteContractPassed": ready and not missing_events},
    )
    return candidate_root


def test_soccertrack_analysis_report_smoke_writes_report_payload_and_markdown(tmp_path: Path) -> None:
    candidate_root = _write_product_route_outputs(tmp_path)

    payload = report.run_football_external_soccertrack_analysis_report_smoke(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_analysis_report_smoke_v1"
    report_payload = json.loads((output_root / "soccertrack_analysis_report_payload.json").read_text(encoding="utf-8"))
    report_md = (output_root / "soccertrack_analysis_report.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["analysisReportSmokePassed"] is True
    assert payload["selectedMatchId"] == "117092"
    assert payload["reportedEventCount"] == 2
    assert payload["reportedFrameCount"] == 1
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_product_ui_binding"
    assert report_payload["schemaVersion"] == "soccertrack_external_analysis_report_payload_v1"
    assert report_payload["readiness"]["analysisReportReady"] is True
    assert report_payload["readiness"]["candidateEvaluationReady"] is False
    assert "SoccerTrack External Fixture Report" in report_md
    assert "PASS" in report_md
    assert "not detector evaluation" in report_md


def test_soccertrack_analysis_report_smoke_blocks_without_product_route_truth(tmp_path: Path) -> None:
    _write_product_route_outputs(tmp_path, ready=False)

    payload = report.run_football_external_soccertrack_analysis_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_product_route_smoke_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_product_route_smoke"


def test_soccertrack_analysis_report_smoke_blocks_report_gap(tmp_path: Path, monkeypatch) -> None:
    _write_product_route_outputs(tmp_path)

    def _failed_render_audit(markdown: str, payload: dict[str, object]) -> dict[str, object]:
        return {
            "schemaVersion": "soccertrack_analysis_report_render_audit_v1",
            "renderedReportBytes": len(markdown),
            "checks": {"requiredTitlePresent": False},
            "reportRenderPassed": False,
        }

    monkeypatch.setattr(report, "_render_audit", _failed_render_audit)

    payload = report.run_football_external_soccertrack_analysis_report_smoke(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_analysis_report_gap"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_analysis_report_payload_repair"


def test_soccertrack_analysis_report_smoke_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_product_route_outputs(tmp_path)

    payload = report.run_football_external_soccertrack_analysis_report_smoke(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_external_analysis_report_smoke",
        "soccertrack_analysis_report_payload_repair",
        "soccertrack_analysis_report_blocker_summary",
    ]
