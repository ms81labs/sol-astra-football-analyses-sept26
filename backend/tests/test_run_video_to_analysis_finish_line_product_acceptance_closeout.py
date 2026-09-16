from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_product_acceptance_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_product_execution(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "product_video_to_analysis_finish_line_execution_v1"
    _write_json(
        root / "product_video_to_analysis_finish_line_execution_summary.json",
        {
            "batchName": "product_video_to_analysis_finish_line_execution",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineProductExecutionPassed": True,
            "boundedRouteSmokePassed": True,
            "bundleConsistencyPassed": True,
            "detectorEvaluationExecuted": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "normalMatchStorageMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_product_acceptance_closeout",
        },
    )
    _write_json(
        root / "finish_line_product_acceptance_truth.json",
        {
            "finishLineProductExecutionPassed": True,
            "boundedRouteSmokePassed": True,
            "bundleConsistencyPassed": True,
            "normalMatchStorageMutationExecuted": False,
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )


def test_product_acceptance_closeout_routes_to_user_acceptance_trial(tmp_path: Path) -> None:
    _seed_product_execution(tmp_path)

    payload = closeout.run_video_to_analysis_finish_line_product_acceptance_closeout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_product_acceptance_closeout_v1"
    capability = json.loads((output_root / "finish_line_product_acceptance_capability_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["finishLineProductAcceptanceClosed"] is True
    assert payload["productRouteAndBundleSmokePassed"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_user_acceptance_trial"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert capability["productUserAcceptanceTrialReady"] is True


def test_product_acceptance_closeout_blocks_without_execution(tmp_path: Path) -> None:
    payload = closeout.run_video_to_analysis_finish_line_product_acceptance_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "product_video_to_analysis_finish_line_execution_missing"
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_finish_line_execution"
