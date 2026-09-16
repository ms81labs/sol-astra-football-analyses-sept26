from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_product_hardening_backlog as backlog


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_completion_summary(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_completion_summary_v1"
    _write_json(
        root / "finish_line_completion_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_completion_summary",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineMilestoneComplete": True,
            "videoToAnalysisProductPathReady": True,
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
            "nextRecommendedNextLever": "video_to_analysis_product_hardening_backlog",
        },
    )
    _write_json(
        root / "finish_line_next_steps_roadmap.json",
        {
            "recommendedNextLever": "video_to_analysis_product_hardening_backlog",
            "candidateNextSteps": [
                "polish finish-line route UI copy and empty states",
                "add product-facing upload-to-analysis walkthrough",
                "prepare a broader real-video acceptance suite",
                "keep detector training/promotion lanes separate from product path hardening",
            ],
        },
    )


def test_product_hardening_backlog_selects_route_polish(tmp_path: Path) -> None:
    _seed_completion_summary(tmp_path)

    payload = backlog.run_video_to_analysis_product_hardening_backlog(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_product_hardening_backlog_v1"
    backlog_payload = json.loads((output_root / "product_hardening_backlog.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productHardeningBacklogReady"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_route_polish"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert backlog_payload["priorityOrder"][0] == "finish_line_route_polish"
    assert backlog_payload["backlogItems"][0]["nextLever"] == "video_to_analysis_finish_line_route_polish"


def test_product_hardening_backlog_blocks_without_completion_summary(tmp_path: Path) -> None:
    payload = backlog.run_video_to_analysis_product_hardening_backlog(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_completion_summary_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_completion_summary"
