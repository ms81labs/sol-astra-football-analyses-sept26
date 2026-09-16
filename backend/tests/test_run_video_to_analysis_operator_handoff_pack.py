from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_operator_handoff_pack as handoff


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_release_candidate(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    closeout_root = root / "video_to_analysis_release_candidate_closeout_v1"
    _write_json(
        closeout_root / "release_candidate_closeout_summary.json",
        {
            "batchName": "video_to_analysis_release_candidate_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "videoToAnalysisReleaseCandidateClosed": True,
            "videoToAnalysisProductPathReady": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": True,
            "runtimeDefaultRolloutClosed": True,
            "activeRuntimeDefaultVersion": "v7.3",
            "activeFailingSourceNotViableBlockerPresent": False,
            "nextRecommendedNextLever": "video_to_analysis_operator_handoff_pack",
        },
    )
    _write_json(
        closeout_root / "release_candidate_operator_snapshot.json",
        {
            "schemaVersion": "video_to_analysis_release_candidate_operator_snapshot_v1",
            "status": "release_candidate_closed",
            "primaryRoute": "/video-to-analysis/acceptance-report",
            "apiRoute": "/api/video-to-analysis/acceptance-report",
            "activeRuntimeDefaultVersion": "v7.3",
            "runtimeDefaultRolloutClosed": True,
        },
    )
    _write_json(
        closeout_root / "release_candidate_capability_matrix.json",
        {
            "schemaVersion": "video_to_analysis_release_candidate_capability_matrix_v1",
            "releaseCandidateCapabilities": {
                "acceptanceReportRouteReady": True,
                "broaderRealVideoAcceptancePassed": True,
                "normalStorageProductSmokeCovered": True,
                "csvExportsCovered": True,
                "htmlReportCovered": True,
                "finishLineRouteCovered": True,
                "v7_3RuntimeDefaultRolloutClosed": True,
            },
            "guardrails": {
                "detectorEvaluationReady": False,
                "trainingReady": False,
                "promotionReady": False,
                "runtimeDefaultMutationReady": True,
            },
        },
    )


def test_operator_handoff_pack_writes_quickstart_and_route_contract(tmp_path: Path) -> None:
    _seed_release_candidate(tmp_path)

    payload = handoff.run_video_to_analysis_operator_handoff_pack(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_operator_handoff_pack_v1"
    handoff_pack = json.loads((output_root / "operator_handoff_pack.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "operator_handoff_route_contract.json").read_text(encoding="utf-8"))
    quickstart = (output_root / "operator_quickstart.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operatorHandoffPackReady"] is True
    assert payload["videoToAnalysisProductPathReady"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_handoff_route_binding"
    assert handoff_pack["primaryOperatorRoute"] == "/video-to-analysis/acceptance-report"
    assert handoff_pack["activeRuntimeDefaultVersion"] == "v7.3"
    assert handoff_pack["operatorChecklist"][0]["id"] == "open_acceptance_report"
    assert route_contract["apiRoutePath"] == "/api/video-to-analysis/operator-handoff"
    assert route_contract["htmlRoutePath"] == "/video-to-analysis/operator-handoff"
    assert "Video-to-analysis operator handoff" in quickstart


def test_operator_handoff_pack_blocks_without_release_candidate(tmp_path: Path) -> None:
    payload = handoff.run_video_to_analysis_operator_handoff_pack(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_release_candidate_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_release_candidate_closeout"
