from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_product_validation_execution as execution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _false_flags() -> dict[str, bool]:
    return {
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "detectorEvaluationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "trainingExecuted": False,
        "trainingAllowed": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _seed_execution_inputs(storage_root: Path, *, approved: bool = True) -> None:
    root = _candidate_root(storage_root)
    flags = _false_flags()
    approval_root = root / "football_external_soccernet_bounded_product_validation_execution_approval_v1"
    _write_json(
        approval_root / "soccernet_bounded_product_validation_execution_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_product_validation_scope_gap",
            "roadmapAdvanceAllowed": approved,
            "productValidationExecutionApproved": approved,
            "productValidationExecutionExecuted": False,
            "approvedProductValidationSliceCount": 4 if approved else 0,
            "executionMode": "bounded_existing_artifact_product_validation" if approved else None,
            "bulkDownloadApproved": False,
            "videoDownloadApproved": False,
            "dataDownloadApproved": False,
            "normalMatchStorageMutationApproved": False,
            "trainingApproved": False,
            "promotionApproved": False,
            "runtimeDefaultMutationApproved": False,
            **flags,
        },
    )
    _write_json(
        approval_root / "approved_product_validation_scope.json",
        {
            "productValidationExecutionApproved": approved,
            "productValidationExecutionExecuted": False,
            "approvedProductValidationSliceCount": 4 if approved else 0,
            "approvedProductValidationSlices": [
                {"sliceId": "soccernet_dry_run_product_bridge"},
                {"sliceId": "soccernet_full_analysis_product_lane"},
                {"sliceId": "external_benchmark_report_product_binding"},
                {"sliceId": "research_game_state_gap_probe"},
            ]
            if approved
            else [],
            "bulkDownloadApproved": False,
            "trainingApproved": False,
            "promotionApproved": False,
            "runtimeDefaultMutationApproved": False,
        },
    )
    _write_json(
        approval_root / "product_validation_execution_contract.json",
        {
            "productValidationExecutionApproved": approved,
            "productValidationExecutionExecuted": False,
            "allowedOperations": ["read_existing_soccernet_product_artifacts"] if approved else [],
            "disallowedOperations": ["bulk_soccernet_download", "training", "promotion", "runtime_default_mutation"],
        },
    )
    _write_json(
        root
        / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
        / "dry_run_product_bridge_smoke_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "productBridgeSmokePassed": True,
            "productPayloadFrameCount": 300,
            "missingSampledFrameCount": 0,
            "fullAnalysisReady": False,
            "fullAnalysisExecuted": False,
            **flags,
        },
    )
    _write_json(
        root
        / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
        / "dry_run_product_bridge_payload.json",
        {
            "schemaVersion": "soccernet_external_video_dry_run_product_bridge_v1",
            "frameCount": 300,
            "frames": [{"frameIndex": index} for index in range(300)],
            "readiness": {
                "productBridgeSmokePassed": True,
                "fullAnalysisReady": False,
                "trainingReady": False,
                "promotionReady": False,
            },
        },
    )
    _write_json(
        root
        / "football_external_soccernet_full_analysis_lane_closeout_v1"
        / "full_analysis_lane_closeout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "fullAnalysisLaneClosed": True,
            **flags,
        },
    )
    _write_json(
        root
        / "football_external_soccernet_analysis_product_lane_closeout_v1"
        / "analysis_product_lane_closeout_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "analysisProductLaneClosed": True,
            **flags,
        },
    )
    _write_json(
        root
        / "football_external_benchmark_real_report_and_product_binding_v1"
        / "real_report_and_product_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "realReportProductBindingReady": True,
            "realReportReady": True,
            **flags,
        },
    )
    _write_json(
        root
        / "football_external_benchmark_real_report_and_product_binding_v1"
        / "real_report_payload.json",
        {"schemaVersion": "external_benchmark_real_report_payload_v1", "sourceCount": 2},
    )
    docs = storage_root.parent / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "foot-soccer-deepresearch.md").write_text(
        "SoccerNet calibration tracking ball actions game_state.parquet metric pitch coordinates",
        encoding="utf-8",
    )


def test_bounded_product_validation_execution_validates_four_approved_slices(tmp_path: Path) -> None:
    _seed_execution_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_bounded_product_validation_execution(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_bounded_product_validation_execution_v1"
    slice_audit = json.loads((output_root / "product_validation_slice_audit.json").read_text(encoding="utf-8"))
    report = json.loads((output_root / "product_validation_execution_report.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productValidationExecutionExecuted"] is True
    assert payload["validatedProductSliceCount"] == 4
    assert payload["failedProductSliceCount"] == 0
    assert payload["bulkDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_report_binding"
    assert [row["sliceId"] for row in slice_audit["sliceResults"]] == [
        "soccernet_dry_run_product_bridge",
        "soccernet_full_analysis_product_lane",
        "external_benchmark_report_product_binding",
        "research_game_state_gap_probe",
    ]
    assert all(row["passed"] is True for row in slice_audit["sliceResults"])
    assert report["boundedProductValidationPassed"] is True


def test_bounded_product_validation_execution_blocks_without_approval(tmp_path: Path) -> None:
    _seed_execution_inputs(tmp_path, approved=False)

    payload = execution.run_football_external_soccernet_bounded_product_validation_execution(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_product_validation_execution_not_approved"
    assert payload["productValidationExecutionExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_execution_approval"


def test_bounded_product_validation_execution_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _seed_execution_inputs(tmp_path)

    payload = execution.run_football_external_soccernet_bounded_product_validation_execution(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_bounded_product_validation_execution",
        "soccernet_product_validation_reference_repair",
        "soccernet_product_validation_execution_blocker_summary",
    ]
