from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_release_candidate_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_product_backlog(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    backlog_root = root / "video_to_analysis_acceptance_report_product_backlog_v1"
    _write_json(
        backlog_root / "acceptance_report_product_backlog_summary.json",
        {
            "batchName": "video_to_analysis_acceptance_report_product_backlog",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "acceptanceReportProductBacklogReady": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "priorityBacklogItem": "release_candidate_closeout",
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
            "nextRecommendedNextLever": "video_to_analysis_release_candidate_closeout",
        },
    )
    _write_json(
        backlog_root / "acceptance_report_product_backlog.json",
        {
            "priorityOrder": ["release_candidate_closeout"],
            "backlogItems": [{"id": "release_candidate_closeout", "nextLever": "video_to_analysis_release_candidate_closeout"}],
        },
    )
    route_root = root / "video_to_analysis_acceptance_report_route_binding_v1"
    _write_json(
        route_root / "acceptance_report_route_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "acceptanceReportRouteReady": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "apiRoutePath": "/api/video-to-analysis/acceptance-report",
            "htmlRoutePath": "/video-to-analysis/acceptance-report",
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
        },
    )
    rollout_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite" / "v7_3_runtime_default_rollout_closeout_v1"
    _write_json(
        rollout_root / "runtime_default_rollout_closeout_summary.json",
        {
            "batchName": "v7_3_runtime_default_rollout_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "runtimeDefaultRolloutClosed": True,
            "runtimeDefaultChanged": True,
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
            "historicalSuiteBlockerArchived": True,
            "nextRecommendedNextLever": "video_to_analysis_release_candidate_closeout",
        },
    )


def test_release_candidate_closeout_marks_product_path_ready(tmp_path: Path) -> None:
    _seed_product_backlog(tmp_path)

    payload = closeout.run_video_to_analysis_release_candidate_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_release_candidate_closeout_v1"
    matrix = json.loads((output_root / "release_candidate_capability_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoToAnalysisReleaseCandidateClosed"] is True
    assert payload["videoToAnalysisProductPathReady"] is True
    assert payload["acceptanceCaseCount"] == 5
    assert payload["acceptancePassedCaseCount"] == 5
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is True
    assert payload["runtimeDefaultRolloutClosed"] is True
    assert payload["activeRuntimeDefaultVersion"] == "v7.3"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_operator_handoff_pack"
    assert matrix["releaseCandidateCapabilities"]["acceptanceReportRouteReady"] is True
    assert matrix["releaseCandidateCapabilities"]["broaderRealVideoAcceptancePassed"] is True
    assert matrix["releaseCandidateCapabilities"]["v7_3RuntimeDefaultRolloutClosed"] is True


def test_release_candidate_closeout_blocks_without_product_backlog(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_release_candidate_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_acceptance_report_product_backlog_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_acceptance_report_product_backlog"


def test_release_candidate_closeout_blocks_without_v7_3_runtime_default_rollout(tmp_path: Path) -> None:
    _seed_product_backlog(tmp_path)
    rollout_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_3_runtime_default_rollout_closeout_v1"
        / "runtime_default_rollout_closeout_summary.json"
    )
    rollout_root.unlink()

    payload = closeout.run_video_to_analysis_release_candidate_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_v7_3_runtime_default_rollout_missing"
    assert payload["nextRecommendedNextLever"] == "v7_3_runtime_default_rollout_closeout"
