from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from backend.app.main import create_app
import backend.scripts.run_video_to_analysis_promotion_review_design as design
import backend.scripts.run_video_to_analysis_promotion_review_execution as execution
import backend.scripts.run_video_to_analysis_promotion_review_report_binding as report_binding
import backend.scripts.run_video_to_analysis_promotion_review_report_route_binding as route_binding
import backend.scripts.run_video_to_analysis_promotion_review_closeout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"


def _seed_current_promotion_truth(storage_root: Path) -> None:
    candidate_root = _candidate_root(storage_root)
    _write_json(
        candidate_root / "video_to_analysis_next_roadmap_direction_snapshot_v1" / "next_roadmap_direction_snapshot_summary.json",
        {
            "batchName": "video_to_analysis_next_roadmap_direction_snapshot",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "nextRoadmapDirectionSnapshotReady": True,
            "selectedNextFamily": "video_to_analysis_promotion_review_design",
            "detectorEvaluationExecuted": False,
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationExecuted": False,
            "candidateReadyForEvaluation": False,
            "nextRecommendedNextLever": "video_to_analysis_promotion_review_design",
        },
    )
    _write_json(
        candidate_root / "v7_2_promotion_readiness_validation_v1" / "v7_2_promotion_readiness_summary.json",
        {
            "batchName": "v7_2_promotion_readiness_validation",
            "goalAchieved": True,
            "primaryBlocker": None,
            "promotionValidated": True,
            "promotionReady": True,
            "candidateReadyForEvaluation": True,
            "promotedForControlledRuns": True,
            "controlledRuntimeRegistryUpdated": True,
            "runtimeDefaultMutationExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "gateHighlights": {
                "boundedValPositiveLocalizationHitRate": 0.971014,
                "sourceFrameLocalizationHitRate": 1.0,
                "precisionGuardrailPassed": True,
            },
            "runtimeContract": {
                "trainingCandidateName": "touchline_detector_candidate_v7",
                "trainingCandidateVersion": "v7.2",
                "runtimeUse": "controlled_internal_candidate_runs",
            },
        },
    )
    _write_json(
        _suite_root(storage_root) / "v7_2_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json",
        {
            "batchName": "v7_2_runtime_default_rollout_closeout",
            "goalAchieved": True,
            "primaryBlocker": None,
            "runtimeDefaultRolloutClosed": True,
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
            "historicalSuiteBlockerArchived": True,
            "sourceRobustnessOutcome": "source_robustness_viable_by_validated_inboard_recovery",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
        },
    )
    _write_json(
        storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "trainingCandidateVersion": "v7.2",
            "runtimeUse": "default_runtime",
            "promotionValidated": True,
            "promotionReady": True,
            "candidateReadyForEvaluation": True,
            "promotedForControlledRuns": True,
            "runtimeDefaultChanged": True,
            "runtimeDefaultMutationExecuted": True,
            "postRuntimeDefaultSourceRobustnessValidated": True,
            "activeFailingSourceNotViableBlockerPresent": False,
        },
    )


def _seed_design(storage_root: Path) -> None:
    _seed_current_promotion_truth(storage_root)
    design.run_video_to_analysis_promotion_review_design(storage_root=storage_root)


def _seed_execution(storage_root: Path) -> None:
    _seed_design(storage_root)
    execution.run_video_to_analysis_promotion_review_execution(storage_root=storage_root)


def _seed_report_binding(storage_root: Path) -> None:
    _seed_execution(storage_root)
    report_binding.run_video_to_analysis_promotion_review_report_binding(storage_root=storage_root)


def _seed_route_binding(storage_root: Path) -> None:
    _seed_report_binding(storage_root)
    route_binding.run_video_to_analysis_promotion_review_report_route_binding(storage_root=storage_root)


def test_promotion_review_design_uses_current_snapshot_without_mutating(tmp_path: Path) -> None:
    _seed_current_promotion_truth(tmp_path)

    payload = design.run_video_to_analysis_promotion_review_design(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["promotionReviewDesignReady"] is True
    assert payload["runtimeDefaultAlreadyMutatedBeforeReview"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_execution"


def test_promotion_review_execution_verifies_existing_promotion_and_rollout(tmp_path: Path) -> None:
    _seed_design(tmp_path)

    payload = execution.run_video_to_analysis_promotion_review_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["promotionReviewExecuted"] is True
    assert payload["promotionReviewPassed"] is True
    assert payload["registryMatchesV7_2DefaultRuntime"] is True
    assert payload["postRuntimeDefaultSourceRobustnessValidated"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_report_binding"


def test_promotion_review_report_binding_writes_view_model_and_contract(tmp_path: Path) -> None:
    _seed_execution(tmp_path)

    payload = report_binding.run_video_to_analysis_promotion_review_report_binding(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_promotion_review_report_binding_v1"
    view_model = json.loads((output_root / "promotion_review_report_view_model.json").read_text(encoding="utf-8"))
    route_contract = json.loads((output_root / "promotion_review_report_route_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["promotionReviewReportReady"] is True
    assert view_model["schemaVersion"] == "video_to_analysis_promotion_review_report_view_model_v1"
    assert view_model["promotionReviewPassed"] is True
    assert route_contract["apiRoutePath"] == "/api/video-to-analysis/promotion-review"
    assert route_contract["htmlRoutePath"] == "/video-to-analysis/promotion-review"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_report_route_binding"


def test_promotion_review_report_route_binding_serves_api_and_html(tmp_path: Path) -> None:
    _seed_report_binding(tmp_path)

    payload = route_binding.run_video_to_analysis_promotion_review_report_route_binding(storage_root=tmp_path)

    async def _fetch() -> tuple[dict[str, object], str]:
        app = create_app(storage_root=tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
            api_response = await client.get("/api/video-to-analysis/promotion-review")
            html_response = await client.get("/video-to-analysis/promotion-review")
        assert api_response.status_code == 200
        assert html_response.status_code == 200
        return api_response.json(), html_response.text

    api_payload, html = asyncio.run(_fetch())

    assert payload["goalAchieved"] is True
    assert payload["promotionReviewReportRouteReady"] is True
    assert api_payload["schemaVersion"] == "video_to_analysis_promotion_review_report_view_model_v1"
    assert "Promotion Review" in html
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promotion_review_closeout"


def test_promotion_review_closeout_selects_operator_acceptance_trial(tmp_path: Path) -> None:
    _seed_route_binding(tmp_path)

    payload = closeout.run_video_to_analysis_promotion_review_closeout(storage_root=tmp_path)

    assert payload["goalAchieved"] is True
    assert payload["promotionReviewClosed"] is True
    assert payload["promotionReviewPassed"] is True
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_promoted_runtime_operator_acceptance_trial"
