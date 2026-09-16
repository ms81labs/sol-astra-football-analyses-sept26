from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_finish_line_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_finish_line_plan(storage_root: Path) -> None:
    root = _candidate_root(storage_root) / "video_to_analysis_finish_line_integration_plan_v1"
    _write_json(
        root / "finish_line_integration_plan_summary.json",
        {
            "batchName": "video_to_analysis_finish_line_integration_plan",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "finishLineIntegrationPlanReady": True,
            "finishLineExecutionApprovalReady": True,
            "sourceReportReady": True,
            "productGoal": "video_to_auditable_match_analysis_data",
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
            "nextRecommendedNextLever": "video_to_analysis_finish_line_execution_approval",
        },
    )
    _write_json(
        root / "finish_line_execution_readiness.json",
        {
            "executionApprovalReady": True,
            "requiresHumanApprovalBeforeNormalRuntimeMutation": True,
            "requiresNoPromotionBoundary": True,
            "requiresRunPodHygieneCheck": True,
            "recommendedNextLever": "video_to_analysis_finish_line_execution_approval",
        },
    )


def test_finish_line_execution_approval_allows_only_bounded_product_smoke(tmp_path: Path) -> None:
    _seed_finish_line_plan(tmp_path)

    payload = approval.run_video_to_analysis_finish_line_execution_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_finish_line_execution_approval_v1"
    scope = json.loads((output_root / "approved_finish_line_execution_scope.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "approval_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["finishLineExecutionApproved"] is True
    assert payload["approvedExecutionMode"] == "isolated_product_video_to_analysis_smoke"
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["normalMatchStorageMutationApproved"] is False
    assert payload["isolatedBenchmarkStorageMutationApproved"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_smoke"
    assert scope["allowedRunner"] == "backend/scripts/run_product_video_to_analysis_smoke.py"
    assert scope["normalMatchStorageMutationAllowed"] is False
    assert scope["isolatedBenchmarkStorageMutationAllowed"] is True
    assert guardrail["approvalGuardrailPassed"] is True


def test_finish_line_execution_approval_blocks_without_integration_plan(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_finish_line_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_finish_line_integration_plan_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_integration_plan"


def test_finish_line_execution_approval_contains_three_failsafe_attempts(tmp_path: Path) -> None:
    _seed_finish_line_plan(tmp_path)

    payload = approval.run_video_to_analysis_finish_line_execution_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "video_to_analysis_finish_line_execution_approval",
        "video_to_analysis_finish_line_scope_repair",
        "video_to_analysis_finish_line_approval_blocker_summary",
    ]
