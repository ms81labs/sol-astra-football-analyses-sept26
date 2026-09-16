from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_product_validation_plan as plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _false_guardrails() -> dict[str, bool]:
    return {
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
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


def _seed_soccernet_validation_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    guardrails = _false_guardrails()
    _write_json(
        root
        / "football_external_benchmark_real_report_and_product_binding_v1"
        / "real_report_and_product_binding_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "realReportAndProductBindingReady": True,
            "nextRecommendedNextLever": "video_to_analysis_finish_line_integration_plan",
            **guardrails,
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
            "nextRecommendedNextLever": "football_external_safe_source_adapter_smoke_test",
            **guardrails,
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
            "nextRecommendedNextLever": "football_external_soccernet_full_analysis_product_integration",
            **guardrails,
        },
    )
    _write_json(
        root
        / "football_external_soccernet_video_analysis_dry_run_v1"
        / "video_analysis_dry_run_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "sampledFrameCount": 300,
            **guardrails,
        },
    )
    _write_json(
        root
        / "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"
        / "dry_run_product_bridge_smoke_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "roadmapAdvanceAllowed": True,
            "productBridgeSmokePassed": True,
            "productPayloadFrameCount": 300,
            **guardrails,
        },
    )
    docs = storage_root.parent / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "foot-soccer-deepresearch.md").write_text(
        "SoccerNet calibration tracking ball actions game_state.parquet pitch coordinates",
        encoding="utf-8",
    )


def test_soccernet_bounded_product_validation_plan_reuses_existing_artifacts(tmp_path: Path, monkeypatch) -> None:
    _seed_soccernet_validation_inputs(tmp_path)
    monkeypatch.setattr(plan.shutil, "disk_usage", lambda _path: (20 * 1024**3, 9 * 1024**3, 11 * 1024**3))

    payload = plan.run_football_external_soccernet_bounded_product_validation_plan(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_bounded_product_validation_plan_v1"
    validation_plan = json.loads((output_root / "soccernet_bounded_product_validation_plan.json").read_text(encoding="utf-8"))
    governance = json.loads((output_root / "soccernet_source_governance_audit.json").read_text(encoding="utf-8"))
    inventory = json.loads((output_root / "soccernet_existing_artifact_inventory.json").read_text(encoding="utf-8"))
    storage_budget = json.loads((output_root / "soccernet_storage_budget_audit.json").read_text(encoding="utf-8"))
    gap_matrix = json.loads((output_root / "soccernet_product_gap_matrix.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["existingArtifactReusePlanned"] is True
    assert payload["sourceGovernanceReady"] is True
    assert payload["storageBudgetReady"] is True
    assert payload["productValidationSlices"] >= 3
    assert payload["bulkDownloadPlanned"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_execution_approval"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert validation_plan["productValidationSlices"][0]["sliceId"] == "soccernet_dry_run_product_bridge"
    assert governance["sourceGovernanceReady"] is True
    assert governance["bulkDownloadAllowed"] is False
    assert inventory["existingArtifactReusePlanned"] is True
    assert inventory["readyArtifactCount"] >= 4
    assert storage_budget["storageBudgetReady"] is True
    assert gap_matrix["currentV72RuntimeScopePreserved"] is True


def test_soccernet_bounded_product_validation_plan_blocks_low_disk_budget(tmp_path: Path, monkeypatch) -> None:
    _seed_soccernet_validation_inputs(tmp_path)
    monkeypatch.setattr(plan.shutil, "disk_usage", lambda _path: (20 * 1024**3, 11 * 1024**3, 9 * 1024**3))

    payload = plan.run_football_external_soccernet_bounded_product_validation_plan(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "soccernet_storage_budget_gap"
    assert payload["storageBudgetReady"] is False


def test_soccernet_bounded_product_validation_plan_blocks_without_existing_artifacts(tmp_path: Path) -> None:
    payload = plan.run_football_external_soccernet_bounded_product_validation_plan(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "soccernet_existing_artifact_inventory_gap"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_existing_artifact_inventory_repair"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_soccernet_bounded_product_validation_plan_blocks_guardrail_violation(tmp_path: Path) -> None:
    _seed_soccernet_validation_inputs(tmp_path)
    unsafe = (
        _candidate_root(tmp_path)
        / "football_external_soccernet_full_analysis_lane_closeout_v1"
        / "full_analysis_lane_closeout_summary.json"
    )
    payload = json.loads(unsafe.read_text(encoding="utf-8"))
    payload["dataDownloadExecuted"] = True
    unsafe.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = plan.run_football_external_soccernet_bounded_product_validation_plan(
        storage_root=tmp_path,
        docs_root=tmp_path.parent / "docs",
    )

    assert result["goalAchieved"] is False
    assert result["primaryBlocker"] == "soccernet_source_governance_gap"
    assert result["nextRecommendedNextLever"] == "football_external_soccernet_source_governance_repair"
