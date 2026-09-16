from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_benchmark_dataset_governance_plan as governance
import backend.scripts.run_football_external_benchmark_real_evaluation_approval as approval
import backend.scripts.run_football_external_benchmark_bounded_real_execution as bounded
import backend.scripts.run_football_external_benchmark_real_report_and_product_binding as report
import backend.scripts.run_video_to_analysis_finish_line_integration_plan as finish_line


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_real_evaluation_design(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    design_root = root / "football_external_benchmark_real_evaluation_design_v1"
    _write_json(
        design_root / "real_evaluation_design_summary.json",
        {
            "batchName": "football_external_benchmark_real_evaluation_design",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "realEvaluationDesignReady": True,
            "realEvaluationExecutionReady": False,
            "externalSourceCount": 2,
            "selectedExternalSourceIds": ["soccernet", "soccertrack"],
            "detectorEvaluationExecuted": False,
            "dataDownloadExecuted": False,
            "videoDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "promotionReady": False,
            "candidateEvaluationExecuted": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "football_external_benchmark_dataset_governance_plan",
        },
    )
    _write_json(
        design_root / "real_evaluation_source_scope_contract.json",
        {
            "sourceScopeMode": "finite_bounded_design",
            "selectedExternalSourceIds": ["soccernet", "soccertrack"],
            "executionApproved": False,
            "fullDatasetDownloadApproved": False,
            "videoDownloadApproved": False,
            "normalMatchStorageMutationApproved": False,
        },
    )
    _write_json(
        design_root / "real_evaluation_metric_contract.json",
        {
            "metricFamilies": ["source_coverage", "ball_localization", "event_alignment", "pipeline_stability"],
            "promotionMetricReady": False,
            "candidateEvaluationReady": False,
        },
    )
    _write_json(
        design_root / "storage_budget_estimate.json",
        {
            "currentRepoFootprintObserved": "17G",
            "governanceRequiredBeforeMoreDownloads": True,
        },
    )
    _write_json(
        root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_execution_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "processedFrameCount": 146893,
            "segmentCount": 196,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_product_payload.json",
        {
            "sourceId": "soccernet",
            "reportedFrameCount": 146893,
            "segmentCount": 196,
            "eventCount": 1604,
        },
    )
    _write_json(
        root / "football_external_soccertrack_lane_closeout_v1" / "soccertrack_lane_closeout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "selectedMatchId": 117092,
            "downloadedFixtureFileCount": 11,
            "reportedEventCount": 3142,
            "reportedFrameCount": 20,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )


def test_real_evaluation_chain_ships_next_five_batches(tmp_path: Path) -> None:
    _seed_real_evaluation_design(tmp_path)

    governance_payload = governance.run_football_external_benchmark_dataset_governance_plan(storage_root=tmp_path)
    approval_payload = approval.run_football_external_benchmark_real_evaluation_approval(storage_root=tmp_path)
    bounded_payload = bounded.run_football_external_benchmark_bounded_real_execution(storage_root=tmp_path)
    report_payload = report.run_football_external_benchmark_real_report_and_product_binding(storage_root=tmp_path)
    finish_payload = finish_line.run_video_to_analysis_finish_line_integration_plan(storage_root=tmp_path)

    assert governance_payload["goalAchieved"] is True
    assert governance_payload["nextRecommendedNextLever"] == "football_external_benchmark_real_evaluation_approval"
    assert approval_payload["realEvaluationExecutionApproved"] is True
    assert approval_payload["nextRecommendedNextLever"] == "football_external_benchmark_bounded_real_execution"
    assert bounded_payload["boundedRealEvaluationExecuted"] is True
    assert bounded_payload["realEvaluationResultRowCount"] == 2
    assert bounded_payload["detectorEvaluationExecuted"] is False
    assert report_payload["realReportProductBindingReady"] is True
    assert finish_payload["finishLineIntegrationPlanReady"] is True
    assert finish_payload["nextRecommendedNextLever"] == "video_to_analysis_finish_line_execution_approval"
    assert finish_payload["trainingExecuted"] is False
    assert finish_payload["promotionReady"] is False
    assert finish_payload["runtimeDefaultMutationExecuted"] is False


def test_dataset_governance_blocks_without_real_evaluation_design(tmp_path: Path) -> None:
    payload = governance.run_football_external_benchmark_dataset_governance_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_real_evaluation_design_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_real_evaluation_design"


def test_bounded_real_execution_blocks_without_approval(tmp_path: Path) -> None:
    payload = bounded.run_football_external_benchmark_bounded_real_execution(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_benchmark_real_evaluation_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_benchmark_real_evaluation_approval"
