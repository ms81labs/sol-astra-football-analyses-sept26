from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_acceptance_report_product_backlog as backlog


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_route_binding(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_acceptance_report_route_binding_v1"
    _write_json(
        root / "acceptance_report_route_binding_summary.json",
        {
            "batchName": "video_to_analysis_acceptance_report_route_binding",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "acceptanceReportRouteReady": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "apiRoutePath": "/api/video-to-analysis/acceptance-report",
            "htmlRoutePath": "/video-to-analysis/acceptance-report",
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_acceptance_report_product_backlog",
        },
    )
    _write_json(
        root / "acceptance_report_view_model.json",
        {
            "schemaVersion": "video_to_analysis_acceptance_report_view_model_v1",
            "acceptanceResult": "passed",
            "scoreboard": [{"label": "Acceptance cases passed", "value": "5 / 5"}],
            "guardrails": {"trainingReady": False, "promotionReady": False, "runtimeDefaultMutationReady": False},
        },
    )
    _write_json(
        root / "acceptance_report_route_contract.json",
        {
            "apiRoutePath": "/api/video-to-analysis/acceptance-report",
            "htmlRoutePath": "/video-to-analysis/acceptance-report",
            "acceptanceReportRouteReady": True,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
        },
    )


def test_acceptance_report_product_backlog_selects_release_candidate_closeout(tmp_path: Path) -> None:
    _seed_route_binding(tmp_path)

    payload = backlog.run_video_to_analysis_acceptance_report_product_backlog(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_acceptance_report_product_backlog_v1"
    backlog_payload = json.loads((output_root / "acceptance_report_product_backlog.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["acceptanceReportProductBacklogReady"] is True
    assert payload["acceptanceCaseCount"] == 5
    assert payload["acceptancePassedCaseCount"] == 5
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_candidate_closeout"
    assert backlog_payload["priorityOrder"][0] == "release_candidate_closeout"
    assert len(backlog_payload["backlogItems"]) >= 3


def test_acceptance_report_product_backlog_blocks_without_route_binding(tmp_path: Path) -> None:
    payload = backlog.run_video_to_analysis_acceptance_report_product_backlog(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_acceptance_report_route_binding_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_acceptance_report_route_binding"
