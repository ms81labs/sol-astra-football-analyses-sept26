from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_source_pool_replenishment_approval as approval
import backend.scripts.run_video_to_analysis_source_pool_replenishment_plan as replenishment
import backend.scripts.run_video_to_analysis_real_video_scaleout_plan_refresh as plan_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_ready_inputs(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        storage_root / "automation" / "unattended_roadmap_loop_status.json",
        {
            "activeBatchName": "video_to_analysis_real_video_scaleout_execution_approval",
            "itemStatus": "blocked_on_source_sampling_pool_exhausted_after_operational_completion",
            "primaryBlocker": "video_to_analysis_real_video_scaleout_plan_insufficient",
            "nextRecommendedNextLever": "video_to_analysis_next_roadmap_direction_snapshot",
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_execution_approval_v1"
        / "real_video_scaleout_execution_approval_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_plan_insufficient",
            "sourcePlanDir": "video_to_analysis_real_video_scaleout_plan_refresh_v27",
            "sourceSamplingDir": "video_to_analysis_real_video_scaleout_source_sampling_expansion_v13",
            "sourceSamplingPoolExhausted": True,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v13"
        / "real_video_scaleout_source_sampling_expansion_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "generatedSourceSamplingPoolExhausted": True,
            "expandedScaleoutCandidateCount": 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_plan_refresh_v27"
        / "real_video_scaleout_plan_refresh_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_candidate_pool_insufficient",
            "availableFreshScaleoutCaseCount": 3,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 0,
        },
    )
    _write_json(
        root / "video_to_analysis_real_video_scaleout_plan_refresh_v27" / "real_video_scaleout_plan.json",
        {
            "realVideoScaleoutPlanReady": False,
            "availableFreshScaleoutCaseCount": 3,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 0,
            "scaleoutCases": [],
            "availableFreshScaleoutCases": [
                {
                    "id": "soccernet_thirtieth_bounded_member",
                    "sourceFamily": "soccernet",
                    "executionMode": "bounded_existing_or_approved_sample_only",
                },
                {
                    "id": "promoted_runtime_alternate_reference_video",
                    "sourceFamily": "promoted_runtime",
                    "executionMode": "bounded_existing_or_approved_sample_only",
                },
                {
                    "id": "soccernet_sixth_bounded_member",
                    "sourceFamily": "soccernet",
                    "executionMode": "bounded_existing_or_approved_sample_only",
                },
            ],
        },
    )
    _write_json(
        root / "video_to_analysis_operator_dashboard_polish_v1" / "operator_dashboard_view_model.json",
        {"schemaVersion": "video_to_analysis_operator_dashboard_view_model_v1"},
    )
    _write_json(
        root
        / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
        / "external_video_ingestion_manifest.json",
        {
            "schemaVersion": "soccernet_external_video_ingestion_manifest_v1",
            "video": {"exists": True, "path": "bounded/soccernet/224p.mp4"},
            "analysisExecutionApproved": False,
            "analysisExecutionExecuted": False,
        },
    )
    _write_json(
        root
        / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
        / "analysis_bridge_contract.json",
        {
            "analysisBridgePrepReady": True,
            "videoExists": True,
            "requiresSeparateDryRunApproval": True,
            "trainingUseAllowed": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        root
        / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
        / "soccertrack_external_match_bundle.json",
        {"schemaVersion": "match_bundle_v1", "match": {"id": "soccertrack:117092"}},
    )
    _write_json(
        root
        / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
        / "match_bundle_bridge_contract_audit.json",
        {"bundleContractPassed": True},
    )
    _write_json(
        root / "product_video_to_analysis_normal_storage_smoke_v1" / "normal_storage_execution_audit.json",
        {
            "normalStorageProductSmokePassed": True,
            "existingVideoBundleSmokePassed": True,
            "apiUploadJobSmokePassed": True,
        },
    )
    _write_json(
        root
        / "video_to_analysis_promoted_runtime_operational_completion_summary_v1"
        / "promoted_runtime_operational_completion_summary.json",
        {
            "goalAchieved": True,
            "videoToAnalysisPromotedRuntimeOperationallyComplete": True,
            "releasedRuntimeVersion": "v7.2",
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
        {"candidateName": "touchline_detector_candidate_v7", "version": "v7.2"},
    )
    _write_json(
        storage_root / "matches" / "existing-ready-match" / "frames.json",
        {"frames": [{"frame": 1}]},
    )
    _write_json(
        storage_root / "matches" / "existing-ready-match" / "events.json",
        {"events": []},
    )
    _write_json(
        storage_root / "matches" / "existing-ready-match" / "analytics.json",
        {"summary": {"source": "normal_storage"}},
    )


def _seed_plan_refresh_prerequisites(storage_root: Path) -> None:
    root = _candidate_root(storage_root)
    _write_json(
        root
        / "football_external_benchmark_real_source_path_consolidation_v1"
        / "real_source_path_consolidation_summary.json",
        {"goalAchieved": True},
    )
    _write_json(
        root
        / "football_external_benchmark_real_source_path_consolidation_v1"
        / "real_source_path_consolidation_manifest.json",
        {"sourcePaths": [{"sourceId": "soccernet"}, {"sourceId": "soccertrack"}]},
    )
    _write_json(
        root / "video_to_analysis_real_video_scaleout_plan_v1" / "real_video_scaleout_plan.json",
        {
            "realVideoScaleoutPlanReady": True,
            "scaleoutCases": [
                {"id": "operator_selected_canary_video"},
                {"id": "soccernet_bounded_224p_member"},
                {"id": "soccertrack_materialized_fixture"},
                {"id": "normal_storage_recent_upload"},
                {"id": "promoted_runtime_reference_video"},
            ],
        },
    )
    _write_json(
        root
        / "video_to_analysis_bounded_next_sample_execution_approval_v60"
        / "bounded_next_sample_execution_approval_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_bounded_next_sample_pool_exhausted",
        },
    )


def test_source_pool_replenishment_plan_writes_guarded_candidate_pool(tmp_path: Path) -> None:
    _seed_ready_inputs(tmp_path)

    payload = replenishment.run_video_to_analysis_source_pool_replenishment_plan(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_source_pool_replenishment_plan_v1"
    summary = json.loads((output_root / "source_pool_replenishment_summary.json").read_text(encoding="utf-8"))
    gap_analysis = json.loads((output_root / "source_pool_gap_analysis.json").read_text(encoding="utf-8"))
    inventory = json.loads((output_root / "candidate_source_family_inventory.json").read_text(encoding="utf-8"))
    bounded_plan = json.loads((output_root / "bounded_sample_replenishment_plan.json").read_text(encoding="utf-8"))
    guardrail_contract = json.loads((output_root / "source_access_guardrail_contract.json").read_text(encoding="utf-8"))
    storage_preflight = json.loads((output_root / "storage_budget_preflight_plan.json").read_text(encoding="utf-8"))

    assert payload == summary
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["plannedFreshSourceCandidateCount"] >= 5
    assert payload["sourceFamilyCount"] >= 5
    assert payload["missingEvidenceCount"] == 0
    assert payload["storageBudgetPolicyPassed"] is True
    assert payload["downloadExecutionApproved"] is False
    assert payload["downloadExecutionExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_pool_replenishment_approval"

    assert gap_analysis["sourceSamplingPoolExhausted"] is True
    assert gap_analysis["requiredFreshSourceCandidateCount"] == 5
    assert gap_analysis["availableFreshSourceCandidateCount"] == 3
    assert gap_analysis["freshCandidateGapCount"] == 2
    assert inventory["sourceFamilyCount"] >= 5
    assert guardrail_contract["sourceAccessGuardrailReady"] is True
    assert guardrail_contract["downloadExecutionApproved"] is False
    assert storage_preflight["storageBudgetPreflightReady"] is True
    assert storage_preflight["storageBudgetPolicyPassed"] is True

    planned_rows = bounded_plan["plannedFreshSourceCandidates"]
    families = {row["sourceFamily"] for row in planned_rows}
    assert {
        "operator_upload",
        "normal_storage",
        "soccernet",
        "soccertrack",
        "promoted_runtime_reference",
    }.issubset(families)
    for row in planned_rows:
        assert row["boundedExecutionMode"] == "bounded_existing_or_approved_sample_only"
        assert row["downloadRequired"] is False
        assert row["trainingEligible"] is False
        assert row["runtimeMutationEligible"] is False
        assert row["scaleoutExecutionApproved"] is False
        assert row["expectedArtifactPaths"]


def test_source_pool_replenishment_plan_blocks_when_required_evidence_is_missing(tmp_path: Path) -> None:
    _seed_ready_inputs(tmp_path)
    (
        _candidate_root(tmp_path)
        / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
        / "analysis_bridge_contract.json"
    ).unlink()

    payload = replenishment.run_video_to_analysis_source_pool_replenishment_plan(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_source_pool_access_metadata_missing"
    assert payload["missingEvidenceCount"] == 1
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"
    assert payload["downloadExecutionApproved"] is False
    assert payload["downloadExecutionExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False


def test_source_pool_replenishment_plan_can_emit_fresh_tranche_after_sampling_exhaustion(tmp_path: Path) -> None:
    _seed_ready_inputs(tmp_path)
    _write_json(
        tmp_path / "automation" / "unattended_roadmap_loop_status.json",
        {
            "activeBatchName": "video_to_analysis_real_video_scaleout_source_sampling_expansion",
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "nextRecommendedNextLever": "video_to_analysis_next_roadmap_direction_snapshot",
        },
    )
    root = _candidate_root(tmp_path)
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_plan_refresh_v29"
        / "real_video_scaleout_plan_refresh_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_candidate_pool_insufficient",
            "availableFreshScaleoutCaseCount": 2,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 0,
        },
    )
    _write_json(
        root / "video_to_analysis_real_video_scaleout_plan_refresh_v29" / "real_video_scaleout_plan.json",
        {
            "realVideoScaleoutPlanReady": False,
            "availableFreshScaleoutCaseCount": 2,
            "requiredFreshScaleoutCaseCount": 5,
            "scaleoutCaseCount": 0,
            "scaleoutCases": [],
            "availableFreshScaleoutCases": [
                {"id": "promoted_runtime_alternate_reference_video"},
                {"id": "soccernet_sixth_bounded_member"},
            ],
        },
    )
    _write_json(
        root
        / "video_to_analysis_real_video_scaleout_source_sampling_expansion_v14"
        / "real_video_scaleout_source_sampling_expansion_summary.json",
        {
            "goalAchieved": False,
            "primaryBlocker": "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted",
            "generatedSourceSamplingPoolExhausted": True,
            "expandedScaleoutCandidateCount": 0,
        },
    )

    payload = replenishment.run_video_to_analysis_source_pool_replenishment_plan(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_source_pool_replenishment_plan_v2",
    )

    output_root = _candidate_root(tmp_path) / "video_to_analysis_source_pool_replenishment_plan_v2"
    bounded_plan = json.loads((output_root / "bounded_sample_replenishment_plan.json").read_text(encoding="utf-8"))
    candidate_ids = {row["candidateSourceId"] for row in bounded_plan["plannedFreshSourceCandidates"]}

    assert payload["goalAchieved"] is True
    assert payload["sourcePlanDir"] == "video_to_analysis_real_video_scaleout_plan_refresh_v29"
    assert payload["sourceSamplingDir"] == "video_to_analysis_real_video_scaleout_source_sampling_expansion_v14"
    assert all(candidate_id.endswith("_v2") for candidate_id in candidate_ids)
    assert "operator_uploaded_local_video_replenishment_candidate_v2" in candidate_ids
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_pool_replenishment_approval"


def test_source_pool_replenishment_approval_approves_bounded_pool_from_plan(tmp_path: Path) -> None:
    _seed_ready_inputs(tmp_path)
    replenishment.run_video_to_analysis_source_pool_replenishment_plan(storage_root=tmp_path)

    payload = approval.run_video_to_analysis_source_pool_replenishment_approval(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_source_pool_replenishment_approval_v1"
    summary = json.loads((output_root / "source_pool_replenishment_approval_summary.json").read_text(encoding="utf-8"))
    contract = json.loads((output_root / "source_pool_replenishment_approval_contract.json").read_text(encoding="utf-8"))
    approved_pool = json.loads((output_root / "approved_bounded_source_pool.json").read_text(encoding="utf-8"))
    guardrail_audit = json.loads((output_root / "source_pool_approval_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload == summary
    assert payload["goalAchieved"] is True
    assert payload["sourcePoolReplenishmentApproved"] is True
    assert payload["freshSourceCandidateCount"] == 5
    assert payload["approvedBoundedScaleoutCaseCount"] == 5
    assert payload["missingEvidenceCount"] == 0
    assert payload["storageBudgetPolicyPassed"] is True
    assert payload["downloadExecutionApproved"] is False
    assert payload["downloadExecutionExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_real_video_scaleout_plan_refresh"

    assert contract["sourcePoolReplenishmentApproved"] is True
    assert contract["approvedExecutionMode"] == "bounded_existing_or_approved_sample_only"
    assert contract["downloadExecutionApproved"] is False
    assert contract["trainingApproved"] is False
    assert guardrail_audit["approvalGuardrailPassed"] is True
    assert approved_pool["approvedBoundedScaleoutCaseCount"] == 5
    for row in approved_pool["approvedBoundedScaleoutCases"]:
        assert row["executionMode"] == "bounded_existing_or_approved_sample_only"
        assert row["downloadRequired"] is False
        assert row["trainingEligible"] is False
        assert row["runtimeMutationEligible"] is False
        assert row["approvalArtifactPath"].endswith("source_pool_replenishment_approval_contract.json")
        assert row["expectedArtifactPaths"]


def test_source_pool_replenishment_approval_blocks_without_plan(tmp_path: Path) -> None:
    payload = approval.run_video_to_analysis_source_pool_replenishment_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_source_pool_replenishment_plan_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_source_pool_replenishment_plan"
    assert payload["downloadExecutionApproved"] is False
    assert payload["downloadExecutionExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["normalMatchStorageMutationExecuted"] is False


def test_scaleout_plan_refresh_uses_approved_replenishment_pool(tmp_path: Path) -> None:
    _seed_ready_inputs(tmp_path)
    _seed_plan_refresh_prerequisites(tmp_path)
    replenishment.run_video_to_analysis_source_pool_replenishment_plan(storage_root=tmp_path)
    approval.run_video_to_analysis_source_pool_replenishment_approval(storage_root=tmp_path)

    payload = plan_refresh.run_video_to_analysis_real_video_scaleout_plan_refresh(
        storage_root=tmp_path,
        output_dir_name="video_to_analysis_real_video_scaleout_plan_refresh_v28",
    )

    output_root = _candidate_root(tmp_path) / "video_to_analysis_real_video_scaleout_plan_refresh_v28"
    refreshed_plan = json.loads((output_root / "real_video_scaleout_plan.json").read_text(encoding="utf-8"))
    refreshed_ids = {row["id"] for row in refreshed_plan["scaleoutCases"]}

    assert payload["goalAchieved"] is True
    assert payload["refreshedScaleoutCaseCount"] == 5
    assert payload["sourcePoolReplenishmentApprovalDir"] == "video_to_analysis_source_pool_replenishment_approval_v1"
    assert refreshed_ids == {
        "operator_uploaded_local_video_replenishment_candidate",
        "existing_normal_storage_video_replenishment_candidate",
        "soccernet_bounded_224p_member_replenishment_candidate",
        "soccertrack_117092_materialized_fixture_replenishment_candidate",
        "promoted_runtime_v7_2_reference_replenishment_candidate",
    }
    assert all(
        row["sourcePoolApprovalDir"] == "video_to_analysis_source_pool_replenishment_approval_v1"
        for row in refreshed_plan["scaleoutCases"]
    )
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert payload["dataDownloadExecuted"] is False
