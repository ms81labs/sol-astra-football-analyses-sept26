from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_bounded_product_validation_execution_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_validation_plan(storage_root: Path, *, ready: bool = True, bulk_download: bool = False) -> None:
    root = _candidate_root(storage_root) / "football_external_soccernet_bounded_product_validation_plan_v1"
    _write_json(
        root / "soccernet_bounded_product_validation_plan_summary.json",
        {
            "goalAchieved": ready,
            "primaryBlocker": None if ready else "soccernet_existing_artifact_inventory_gap",
            "roadmapAdvanceAllowed": ready,
            "existingArtifactReusePlanned": ready,
            "readyArtifactCount": 5 if ready else 1,
            "sourceGovernanceReady": ready,
            "storageBudgetReady": ready,
            "productValidationSlices": 4 if ready else 0,
            "bulkDownloadPlanned": bulk_download,
            "executionApproved": False,
            "executionApprovalRequired": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_bounded_product_validation_execution_approval",
        },
    )
    _write_json(
        root / "soccernet_bounded_product_validation_plan.json",
        {
            "schemaVersion": "soccernet_bounded_product_validation_plan_v1",
            "sourceMode": "existing_artifact_reuse_only",
            "bulkDownloadPlanned": bulk_download,
            "executionApproved": False,
            "executionApprovalRequiredBefore": "football_external_soccernet_bounded_product_validation_execution_approval",
            "productValidationSlices": [
                {"sliceId": "soccernet_dry_run_product_bridge", "executionRequiresApproval": True},
                {"sliceId": "soccernet_full_analysis_product_lane", "executionRequiresApproval": True},
                {"sliceId": "external_benchmark_report_product_binding", "executionRequiresApproval": True},
                {"sliceId": "research_game_state_gap_probe", "executionRequiresApproval": False},
            ]
            if ready
            else [],
            "expectedExecutionBoundary": {
                "trainingAllowed": False,
                "promotionMutationAllowed": False,
                "runtimeDefaultMutationAllowed": False,
                "bulkDownloadAllowed": False,
                "normalMatchStorageMutationAllowed": False,
            },
        },
    )
    _write_json(
        root / "soccernet_source_governance_audit.json",
        {
            "sourceGovernanceReady": ready,
            "bulkDownloadAllowed": False,
            "bulkDownloadPlanned": bulk_download,
            "additionalVideoDownloadAllowedWithoutApproval": False,
            "additionalDataDownloadAllowedWithoutApproval": False,
            "allInputGuardrailsPreserved": ready,
        },
    )
    _write_json(
        root / "soccernet_storage_budget_audit.json",
        {
            "storageBudgetReady": ready,
            "diskFreeGb": 52.0,
            "minimumFreeGbForBoundedValidationPlan": 10.0,
            "bulkDownloadPlanned": bulk_download,
        },
    )
    _write_json(
        root / "soccernet_existing_artifact_inventory.json",
        {
            "existingArtifactReusePlanned": ready,
            "readyArtifactCount": 5 if ready else 1,
            "requiredReadyArtifactCount": 4,
            "artifactRows": [
                {"artifactId": "external_real_report_product_binding", "ready": True, "guardrailsPreserved": True},
                {"artifactId": "soccernet_analysis_product_lane_closeout", "ready": True, "guardrailsPreserved": True},
                {"artifactId": "soccernet_full_analysis_lane_closeout", "ready": True, "guardrailsPreserved": True},
                {"artifactId": "soccernet_video_analysis_dry_run", "ready": True, "guardrailsPreserved": True},
                {"artifactId": "soccernet_dry_run_product_bridge_smoke", "ready": True, "guardrailsPreserved": True},
            ]
            if ready
            else [],
        },
    )


def test_bounded_product_validation_execution_approval_writes_non_executed_contract(tmp_path: Path) -> None:
    _seed_validation_plan(tmp_path)

    payload = approval.run_football_external_soccernet_bounded_product_validation_execution_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_bounded_product_validation_execution_approval_v1"
    scope = json.loads((output_root / "approved_product_validation_scope.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "product_validation_execution_contract.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "approval_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["productValidationExecutionApproved"] is True
    assert payload["productValidationExecutionExecuted"] is False
    assert payload["approvedProductValidationSliceCount"] == 4
    assert payload["bulkDownloadApproved"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_execution"
    assert scope["sourcePlanBatch"] == "football_external_soccernet_bounded_product_validation_plan"
    assert scope["approvedProductValidationSliceCount"] == 4
    assert contract["productValidationExecutionApproved"] is True
    assert contract["productValidationExecutionExecuted"] is False
    assert guardrail["approvalGuardrailPassed"] is True


def test_bounded_product_validation_execution_approval_blocks_without_ready_plan(tmp_path: Path) -> None:
    _seed_validation_plan(tmp_path, ready=False)

    payload = approval.run_football_external_soccernet_bounded_product_validation_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_product_validation_plan_missing"
    assert payload["productValidationExecutionApproved"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_plan"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False


def test_bounded_product_validation_execution_approval_blocks_bulk_download_plan(tmp_path: Path) -> None:
    _seed_validation_plan(tmp_path, ready=True, bulk_download=True)

    payload = approval.run_football_external_soccernet_bounded_product_validation_execution_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_product_validation_guardrail_violation"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_bounded_product_validation_plan_repair"
