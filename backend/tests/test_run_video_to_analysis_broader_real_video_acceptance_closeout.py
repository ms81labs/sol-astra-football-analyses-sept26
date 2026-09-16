from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_broader_real_video_acceptance_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_execution(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_broader_real_video_acceptance_execution_v1"
    _write_json(
        root / "broader_real_video_acceptance_execution_summary.json",
        {
            "batchName": "video_to_analysis_broader_real_video_acceptance_execution",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "broaderRealVideoAcceptanceExecuted": True,
            "acceptanceCaseCount": 5,
            "acceptancePassedCaseCount": 5,
            "normalMatchStorageMutationExecuted": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_broader_real_video_acceptance_closeout",
        },
    )
    _write_json(root / "acceptance_case_results.json", {"cases": [{"passed": True} for _ in range(5)]})


def test_broader_real_video_acceptance_closeout_routes_to_report(tmp_path: Path) -> None:
    _seed_execution(tmp_path)

    payload = closeout.run_video_to_analysis_broader_real_video_acceptance_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_broader_real_video_acceptance_closeout_v1"
    report = json.loads((output_root / "broader_real_video_acceptance_report.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["broaderRealVideoAcceptanceClosed"] is True
    assert payload["acceptancePassedCaseCount"] == 5
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_acceptance_report_route_binding"
    assert report["acceptanceResult"] == "passed"


def test_broader_real_video_acceptance_closeout_blocks_without_execution(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_broader_real_video_acceptance_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_broader_real_video_acceptance_execution_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_broader_real_video_acceptance_execution"
