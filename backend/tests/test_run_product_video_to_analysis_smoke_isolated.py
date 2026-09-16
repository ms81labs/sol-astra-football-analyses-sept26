from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_product_video_to_analysis_smoke_isolated as isolated


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_execution_approval(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_execution_approval_v1"
    _write_json(
        root / "finish_line_execution_approval_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_execution_approval",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineExecutionApproved": True,
            "finishLineExecutionReady": True,
            "approvedExecutionMode": "isolated_product_video_to_analysis_smoke",
            "normalMatchStorageMutationApproved": False,
            "isolatedBenchmarkStorageMutationApproved": True,
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
            "nextRecommendedNextLever": "product_video_to_analysis_smoke",
        },
    )
    _write_json(
        root / "approved_finish_line_execution_scope.json",
        {
            "finishLineExecutionApproved": True,
            "approvedExecutionMode": "isolated_product_video_to_analysis_smoke",
            "allowedRunner": "backend/scripts/run_product_video_to_analysis_smoke.py",
            "normalMatchStorageMutationAllowed": False,
            "isolatedBenchmarkStorageMutationAllowed": True,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )


def test_isolated_product_video_to_analysis_smoke_runs_under_isolated_storage(tmp_path: Path) -> None:
    _seed_execution_approval(tmp_path)

    payload = isolated.run_product_video_to_analysis_smoke_isolated(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "product_video_to_analysis_smoke_isolated_v1"
    nested_summary = Path(payload["isolatedSmokeSummaryPath"])
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productVideoToAnalysisSmokePassed"] is True
    assert payload["apiUploadJobSmokePassed"] is True
    assert payload["existingVideoBundleSmokePassed"] is True
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["isolatedBenchmarkStorageMutationExecuted"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_closeout"
    assert (output_root / "isolated_storage_audit.json").exists()
    assert nested_summary.exists()
    assert str(nested_summary).startswith(str(output_root / "isolated_storage_root"))


def test_isolated_product_video_to_analysis_smoke_blocks_without_approval(tmp_path: Path) -> None:
    payload = isolated.run_product_video_to_analysis_smoke_isolated(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "product_video_to_analysis_smoke_finish_line_approval_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_execution_approval"


def test_isolated_product_video_to_analysis_smoke_attempts_are_adaptive(tmp_path: Path) -> None:
    _seed_execution_approval(tmp_path)

    payload = isolated.run_product_video_to_analysis_smoke_isolated(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "isolated_product_video_to_analysis_smoke",
        "isolated_product_video_to_analysis_storage_repair",
        "isolated_product_video_to_analysis_blocker_summary",
    ]
