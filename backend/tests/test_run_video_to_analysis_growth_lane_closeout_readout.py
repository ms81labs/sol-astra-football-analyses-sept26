from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_growth_lane_closeout_readout as closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _false_flags() -> dict[str, bool]:
    return {
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
    }


def _seed_v57_growth_truth(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root / "video_to_analysis_next_sample_selection_snapshot_v57" / "next_sample_selection_snapshot_summary.json",
        {
            "batchName": "video_to_analysis_next_sample_selection_snapshot",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "candidateSampleCount": 3,
            "candidateSampleIds": [
                "operator_uploaded_local_video_replenishment_candidate_v28",
                "soccernet_bounded_224p_member_replenishment_candidate_v28",
                "existing_normal_storage_video_replenishment_candidate_v28",
            ],
            "nextRecommendedNextLever": "video_to_analysis_bounded_next_sample_execution_approval",
            **_false_flags(),
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_bounded_execution_v57"
        / "real_video_scaleout_bounded_execution_summary.json",
        {
            "batchName": "video_to_analysis_real_video_scaleout_bounded_execution",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "scaleoutPassedCaseCount": 5,
            "nextRecommendedNextLever": "video_to_analysis_real_video_scaleout_report_route_binding",
            **_false_flags(),
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_report_route_binding_v57"
        / "real_video_scaleout_report_route_binding_summary.json",
        {
            "batchName": "video_to_analysis_real_video_scaleout_report_route_binding",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "apiRouteStatusCode": 200,
            "htmlRouteStatusCode": 200,
            "nextRecommendedNextLever": "video_to_analysis_real_video_scaleout_lane_closeout",
            **_false_flags(),
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_lane_closeout_v57"
        / "real_video_scaleout_lane_closeout_summary.json",
        {
            "batchName": "video_to_analysis_real_video_scaleout_lane_closeout",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "realVideoScaleoutLaneClosed": True,
            "nextRecommendedNextLever": "video_to_analysis_next_sample_selection_snapshot",
            **_false_flags(),
        },
    )


def _seed_consumed_v57_queue_and_recovered_plan(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "video_to_analysis_bounded_next_sample_execution_approval_v252"
        / "bounded_next_sample_execution_approval_summary.json",
        {
            "batchName": "video_to_analysis_bounded_next_sample_execution_approval",
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted",
            "remainingCandidateSampleCount": 0,
            "sourceSnapshotDir": "video_to_analysis_next_sample_selection_snapshot_v57",
            "nextRecommendedNextLever": "video_to_analysis_real_video_scaleout_plan_refresh",
            **_false_flags(),
        },
    )
    _write_json(
        root / "video_to_analysis_real_video_scaleout_plan_refresh_v123" / "real_video_scaleout_plan_refresh_summary.json",
        {
            "batchName": "video_to_analysis_real_video_scaleout_plan_refresh",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "availableFreshScaleoutCaseCount": 7,
            "requiredFreshScaleoutCaseCount": 5,
            "refreshedScaleoutCaseCount": 5,
            "sourcePoolReplenishmentApprovalDir": "video_to_analysis_source_pool_replenishment_approval_v35",
            "nextRecommendedNextLever": "video_to_analysis_real_video_scaleout_execution_approval",
            **_false_flags(),
        },
    )


def test_growth_lane_closeout_closes_at_latest_snapshot_without_auto_continuation(tmp_path: Path) -> None:
    _seed_v57_growth_truth(tmp_path)

    payload = closeout.run_video_to_analysis_growth_lane_closeout_readout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_growth_lane_closeout_readout_v1"
    manifest = json.loads((output_root / "growth_lane_closeout_readout_manifest.json").read_text(encoding="utf-8"))
    guardrails = json.loads((output_root / "growth_lane_closeout_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["growthLaneCloseoutReady"] is True
    assert payload["growthLaneClosedAtSnapshotDir"] == "video_to_analysis_next_sample_selection_snapshot_v57"
    assert payload["growthLaneClosedAtVersion"] == 57
    assert payload["activeQueueCandidateCount"] == 3
    assert payload["activeQueueConsumed"] is False
    assert payload["optionalFutureScaleoutPlanReady"] is False
    assert payload["autoContinueBoundedGrowthRecommended"] is False
    assert payload["manualStrategicChoiceRequired"] is True
    assert payload["nextRecommendedNextLever"] == "manual_strategic_lane_selection_required"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["dataDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False

    assert manifest["growthLaneClosedAtVersion"] == 57
    assert manifest["autoContinueBoundedGrowthRecommended"] is False
    assert manifest["activeQueueRemainsValidForOptionalFutureGrowth"] is True
    assert manifest["activeQueueConsumed"] is False
    assert guardrails["allMutationGuardrailsPreserved"] is True


def test_growth_lane_closeout_tracks_consumed_queue_and_recovered_optional_plan(tmp_path: Path) -> None:
    _seed_v57_growth_truth(tmp_path)
    _seed_consumed_v57_queue_and_recovered_plan(tmp_path)

    payload = closeout.run_video_to_analysis_growth_lane_closeout_readout(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_growth_lane_closeout_readout_v1"
    manifest = json.loads((output_root / "growth_lane_closeout_readout_manifest.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["growthLaneCloseoutReady"] is True
    assert payload["activeQueueConsumed"] is True
    assert payload["latestConsumedQueueApprovalDir"] == "video_to_analysis_bounded_next_sample_execution_approval_v252"
    assert payload["optionalFutureScaleoutPlanReady"] is True
    assert payload["optionalFutureScaleoutPlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v123"
    assert payload["autoContinueBoundedGrowthRecommended"] is False
    assert payload["nextRecommendedNextLever"] == "manual_strategic_lane_selection_required"

    assert manifest["activeQueueConsumed"] is True
    assert manifest["activeQueueRemainsValidForOptionalFutureGrowth"] is False
    assert manifest["optionalFutureScaleoutPlanReady"] is True


def test_growth_lane_closeout_blocks_without_matching_scaleout_evidence(tmp_path: Path) -> None:
    root = _candidate_root(tmp_path)
    _write_json(
        root / "video_to_analysis_next_sample_selection_snapshot_v57" / "next_sample_selection_snapshot_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "candidateSampleCount": 3,
            "candidateSampleIds": ["one", "two", "three"],
            **_false_flags(),
        },
    )

    payload = closeout.run_video_to_analysis_growth_lane_closeout_readout(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_growth_lane_closeout_scaleout_evidence_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_lane_closeout"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
