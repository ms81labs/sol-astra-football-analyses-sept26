from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_completion_summary as completion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_operational_readiness(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_operational_readiness_v1"
    _write_json(
        root / "finish_line_operational_readiness_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_operational_readiness",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "operationalReadinessPassed": True,
            "normalStorageProductSmokePassed": True,
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
            "nextRecommendedNextLever": "video_to_analysis_finish_line_completion_summary",
        },
    )
    _write_json(
        root / "operational_readiness_audit.json",
        {
            "normalStorageCloseoutReady": True,
            "routeInventoryWritten": True,
            "operatorRunbookWritten": True,
            "operationalReadinessPassed": True,
        },
    )


def test_completion_summary_marks_finish_line_milestone_complete(tmp_path: Path) -> None:
    _seed_operational_readiness(tmp_path)

    payload = completion.run_video_to_analysis_finish_line_completion_summary(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_completion_summary_v1"
    roadmap = json.loads((output_root / "finish_line_next_steps_roadmap.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["finishLineMilestoneComplete"] is True
    assert payload["videoToAnalysisProductPathReady"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_product_hardening_backlog"
    assert roadmap["recommendedNextLever"] == "video_to_analysis_product_hardening_backlog"


def test_completion_summary_blocks_without_operational_readiness(tmp_path: Path) -> None:
    payload = completion.run_video_to_analysis_finish_line_completion_summary(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_operational_readiness_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_operational_readiness"
