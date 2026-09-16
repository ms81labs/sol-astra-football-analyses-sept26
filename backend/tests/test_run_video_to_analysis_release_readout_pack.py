from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_release_readout_pack as readout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_v38_growth_closeout(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root / "video_to_analysis_next_sample_selection_snapshot_v38" / "next_sample_selection_snapshot_summary.json",
        {
            "batchName": "video_to_analysis_next_sample_selection_snapshot",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "candidateSampleCount": 3,
            "candidateSampleIds": [
                "operator_uploaded_local_video_replenishment_candidate_v23",
                "soccernet_bounded_224p_member_replenishment_candidate_v23",
                "existing_normal_storage_video_replenishment_candidate_v23",
            ],
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "generatedTruthDeleteAllowed": False,
            "cleanupMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_bounded_next_sample_execution_approval",
        },
    )


def _seed_external_benchmark_binding(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "football_external_benchmark_real_report_and_product_binding_v1"
        / "real_report_and_product_binding_summary.json",
        {
            "batchName": "football_external_benchmark_real_report_and_product_binding",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "realBenchmarkReportReady": True,
            "productBindingReady": True,
            "detectorEvaluationExecuted": False,
            "dataDownloadExecuted": False,
            "videoDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "candidateEvaluationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_integration_plan",
        },
    )


def _seed_runtime_completion(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "video_to_analysis_promoted_runtime_operational_completion_summary_v1"
        / "promoted_runtime_operational_completion_summary.json",
        {
            "batchName": "video_to_analysis_promoted_runtime_operational_completion_summary",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": None,
            "videoToAnalysisPromotedRuntimeOperationallyComplete": True,
            "releasedRuntimeVersion": "v7.2",
            "steadyStateMonitoringCyclePassed": True,
            "oldFailingSourceNotViableBlockerDead": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "nextRecommendedNextLever": "video_to_analysis_operational_backlog_prioritization",
        },
    )


def test_release_readout_pack_writes_operator_brief_and_next_lane_matrix(tmp_path: Path) -> None:
    _seed_v38_growth_closeout(tmp_path)
    _seed_external_benchmark_binding(tmp_path)
    _seed_runtime_completion(tmp_path)

    payload = readout.run_video_to_analysis_release_readout_pack(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_release_readout_pack_v1"
    manifest = json.loads((output_root / "release_readout_manifest.json").read_text(encoding="utf-8"))
    matrix = json.loads((output_root / "next_strategic_lane_matrix.json").read_text(encoding="utf-8"))
    guardrails = json.loads((output_root / "guardrail_audit.json").read_text(encoding="utf-8"))
    brief = (output_root / "operator_release_brief.md").read_text(encoding="utf-8")

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["releaseReadoutPackReady"] is True
    assert payload["growthLaneCloseoutSnapshot"] == "video_to_analysis_next_sample_selection_snapshot_v38"
    assert payload["externalBenchmarkProductBindingReady"] is True
    assert payload["runtimeOperationallyComplete"] is True
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_next_strategic_lane_selection"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["dataDownloadExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False

    assert manifest["latestSnapshot"] == "video_to_analysis_next_sample_selection_snapshot_v38"
    assert manifest["activeQueueCandidateIds"][1] == "soccernet_bounded_224p_member_replenishment_candidate_v23"
    assert matrix["recommendedLane"] == "external_benchmark_expansion_or_release_readout"
    assert len(matrix["candidateStrategicLanes"]) == 5
    assert guardrails["allMutationGuardrailsPreserved"] is True
    assert "Video-to-analysis release readout" in brief
    assert "v38" in brief


def test_release_readout_pack_blocks_without_v38_snapshot(tmp_path: Path) -> None:
    _seed_external_benchmark_binding(tmp_path)
    _seed_runtime_completion(tmp_path)

    payload = readout.run_video_to_analysis_release_readout_pack(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_release_readout_growth_closeout_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_growth_lane_closeout_readout"
