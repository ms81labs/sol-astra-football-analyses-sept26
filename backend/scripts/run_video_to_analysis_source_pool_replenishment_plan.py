from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SCALEOUT_APPROVAL_DIR_NAME = "video_to_analysis_real_video_scaleout_execution_approval_v1"
DEFAULT_SOURCE_SAMPLING_DIR_NAME = "video_to_analysis_real_video_scaleout_source_sampling_expansion_v13"
DEFAULT_PLAN_REFRESH_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_refresh_v27"
DEFAULT_DASHBOARD_DIR_NAME = "video_to_analysis_operator_dashboard_polish_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_source_pool_replenishment_plan_v1"

BLOCKER_INPUTS_MISSING = "video_to_analysis_source_pool_replenishment_inputs_missing"
BLOCKER_SOURCE_ACCESS_MISSING = "video_to_analysis_source_pool_access_metadata_missing"
BLOCKER_INSUFFICIENT_EXISTING_SOURCES = "video_to_analysis_source_pool_replenishment_insufficient_existing_sources"
BLOCKER_STORAGE_BUDGET_NOT_READY = "video_to_analysis_source_pool_storage_budget_not_ready"

NEXT_SCALEOUT_APPROVAL = "video_to_analysis_real_video_scaleout_execution_approval"
NEXT_DATASET_ACCESS_REVIEW = "football_external_dataset_access_review"
NEXT_MANUAL_SELECTION = "manual_source_selection_required"
NEXT_STORAGE_CLEANUP_MAP = "video_to_analysis_source_and_artifact_cleanup_map"
NEXT_REPLENISHMENT_APPROVAL = "video_to_analysis_source_pool_replenishment_approval"

REQUIRED_FRESH_SOURCE_CANDIDATE_COUNT = 5


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "source_pool_replenishment_plan",
                "successCriteria": [
                    "planned fresh source candidates >= 5",
                    "source family count >= 2",
                    "source access guardrail contract ready",
                    "storage budget preflight ready",
                ],
                "failureAdaptation": "If evidence or metadata is missing, repair only planning metadata; do not download or execute samples.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "source_family_inventory_repair",
                "successCriteria": [
                    "inspect existing generated artifacts",
                    "inspect existing source-path manifests",
                    "add missing metadata-only candidate rows",
                ],
                "failureAdaptation": "If the pool still cannot reach five candidates, write a blocker summary.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "source_pool_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; no download, archive extraction, detector evaluation, training, or runtime mutation.",
            },
        ],
    }


def _rel(path: Path, storage_root: Path) -> str:
    return path.relative_to(storage_root).as_posix()


def _artifact_rows(storage_root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        path = storage_root / relative_path
        rows.append(
            {
                "relativePath": relative_path,
                "exists": path.exists(),
                "sizeBytes": path.stat().st_size if path.exists() and path.is_file() else 0,
            }
        )
    return rows


def _missing_evidence_paths(rows: list[dict[str, Any]]) -> list[str]:
    paths: set[str] = set()
    for row in rows:
        for artifact in row.get("evidenceArtifacts", []):
            if isinstance(artifact, dict) and artifact.get("exists") is not True:
                paths.add(str(artifact.get("relativePath")))
    return sorted(paths)


def _existing_normal_storage_match_paths(storage_root: Path) -> list[str]:
    matches_root = storage_root / "matches"
    if not matches_root.exists():
        return []
    for match_dir in sorted(path for path in matches_root.iterdir() if path.is_dir()):
        required_paths = [match_dir / "frames.json", match_dir / "events.json", match_dir / "analytics.json"]
        if all(path.exists() for path in required_paths):
            return [_rel(path, storage_root) for path in required_paths]
    return []


def _candidate(
    *,
    storage_root: Path,
    candidate_source_id: str,
    source_family: str,
    source_label: str,
    evidence_basis: str,
    expected_artifact_paths: list[str],
    download_approval_required: bool,
    risk_notes: list[str],
) -> dict[str, Any]:
    evidence_artifacts = _artifact_rows(storage_root, expected_artifact_paths)
    return {
        "candidateSourceId": candidate_source_id,
        "sourceFamily": source_family,
        "sourceLabel": source_label,
        "evidenceBasis": evidence_basis,
        "boundedExecutionMode": "bounded_existing_or_approved_sample_only",
        "downloadRequired": False,
        "downloadApprovalRequired": download_approval_required,
        "storageBudgetClass": "small_bounded_sample",
        "expectedArtifactPaths": expected_artifact_paths,
        "evidenceArtifacts": evidence_artifacts,
        "missingEvidencePaths": [
            artifact["relativePath"] for artifact in evidence_artifacts if artifact["exists"] is not True
        ],
        "riskNotes": risk_notes,
        "trainingEligible": False,
        "runtimeMutationEligible": False,
        "promotionMutationEligible": False,
        "scaleoutExecutionApproved": False,
        "requiresReplenishmentApproval": True,
    }


def _tranche_suffix(output_dir_name: str) -> str:
    try:
        version = int(output_dir_name.rsplit("_v", 1)[1])
    except (IndexError, ValueError):
        return ""
    return "" if version <= 1 else f"_v{version}"


def _planned_candidates(storage_root: Path, root: Path, *, output_dir_name: str) -> list[dict[str, Any]]:
    normal_storage_paths = _existing_normal_storage_match_paths(storage_root)
    suffix = _tranche_suffix(output_dir_name)
    return [
        _candidate(
            storage_root=storage_root,
            candidate_source_id=f"operator_uploaded_local_video_replenishment_candidate{suffix}",
            source_family="operator_upload",
            source_label=f"operator uploaded local video{suffix}",
            evidence_basis="existing_artifact",
            expected_artifact_paths=[
                _rel(
                    root
                    / "product_video_to_analysis_normal_storage_smoke_v1"
                    / "normal_storage_execution_audit.json",
                    storage_root,
                ),
                _rel(root / DEFAULT_DASHBOARD_DIR_NAME / "operator_dashboard_view_model.json", storage_root),
            ],
            download_approval_required=False,
            risk_notes=[
                "Reuse only existing operator-upload/local-product evidence until a replenishment approval chooses a concrete sample.",
            ],
        ),
        _candidate(
            storage_root=storage_root,
            candidate_source_id=f"existing_normal_storage_video_replenishment_candidate{suffix}",
            source_family="normal_storage",
            source_label=f"existing normal storage completed match{suffix}",
            evidence_basis="existing_artifact",
            expected_artifact_paths=normal_storage_paths,
            download_approval_required=False,
            risk_notes=[
                "Use only an already-materialized normal storage match; do not create a new match in this planning batch.",
            ],
        ),
        _candidate(
            storage_root=storage_root,
            candidate_source_id=f"soccernet_bounded_224p_member_replenishment_candidate{suffix}",
            source_family="soccernet",
            source_label=f"SoccerNet bounded video member{suffix}",
            evidence_basis="existing_artifact",
            expected_artifact_paths=[
                _rel(
                    root
                    / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
                    / "external_video_ingestion_manifest.json",
                    storage_root,
                ),
                _rel(
                    root
                    / "football_external_soccernet_video_to_analysis_bridge_prep_v1"
                    / "analysis_bridge_contract.json",
                    storage_root,
                ),
            ],
            download_approval_required=True,
            risk_notes=[
                "SoccerNet access remains NDA/research-gated; no full dataset or new member download is approved here.",
            ],
        ),
        _candidate(
            storage_root=storage_root,
            candidate_source_id=f"soccertrack_117092_materialized_fixture_replenishment_candidate{suffix}",
            source_family="soccertrack",
            source_label=f"SoccerTrack bounded fixture/sample{suffix}",
            evidence_basis="existing_artifact",
            expected_artifact_paths=[
                _rel(
                    root
                    / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
                    / "soccertrack_external_match_bundle.json",
                    storage_root,
                ),
                _rel(
                    root
                    / "football_external_soccertrack_match_bundle_bridge_smoke_v1"
                    / "match_bundle_bridge_contract_audit.json",
                    storage_root,
                ),
            ],
            download_approval_required=True,
            risk_notes=[
                "Use only the already-materialized bounded fixture; no Google Drive bulk download is approved here.",
            ],
        ),
        _candidate(
            storage_root=storage_root,
            candidate_source_id=f"promoted_runtime_v7_2_reference_replenishment_candidate{suffix}",
            source_family="promoted_runtime_reference",
            source_label=f"promoted runtime reference video{suffix}",
            evidence_basis="existing_artifact",
            expected_artifact_paths=[
                _rel(
                    root
                    / "video_to_analysis_promoted_runtime_operational_completion_summary_v1"
                    / "promoted_runtime_operational_completion_summary.json",
                    storage_root,
                ),
                "runtime/promoted_touchline_detector_candidate.json",
            ],
            download_approval_required=False,
            risk_notes=[
                "Reference the promoted v7.2 runtime only; do not mutate runtime defaults or promote a new detector.",
            ],
        ),
    ]


def _current_blocker_inputs_ready(
    *,
    status: dict[str, Any] | None,
    approval_summary: dict[str, Any] | None,
    sampling_summary: dict[str, Any] | None,
    refresh_summary: dict[str, Any] | None,
    refresh_plan: dict[str, Any] | None,
    dashboard_view_model: dict[str, Any] | None,
    research_note_exists: bool,
) -> bool:
    status = status if isinstance(status, dict) else {}
    current_state_matches = bool(
        (
            status.get("activeBatchName") == "video_to_analysis_real_video_scaleout_execution_approval"
            and status.get("primaryBlocker") == "video_to_analysis_real_video_scaleout_plan_insufficient"
        )
        or (
            status.get("activeBatchName") == "video_to_analysis_real_video_scaleout_source_sampling_expansion"
            and status.get("primaryBlocker") == "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted"
        )
        or status.get("nextRecommendedNextLever") in {
            "video_to_analysis_next_roadmap_direction_snapshot",
            "video_to_analysis_source_pool_replenishment_plan",
        }
    )
    generated_exhaustion_matches = bool(
        isinstance(sampling_summary, dict)
        and sampling_summary.get("generatedSourceSamplingPoolExhausted") is True
        and isinstance(refresh_summary, dict)
        and refresh_summary.get("primaryBlocker") == "video_to_analysis_real_video_scaleout_candidate_pool_insufficient"
        and isinstance(refresh_plan, dict)
        and int(refresh_plan.get("availableFreshScaleoutCaseCount", 0)) < int(refresh_plan.get("requiredFreshScaleoutCaseCount", REQUIRED_FRESH_SOURCE_CANDIDATE_COUNT))
        and isinstance(dashboard_view_model, dict)
        and research_note_exists
    )
    return bool((current_state_matches or generated_exhaustion_matches) and generated_exhaustion_matches)


def _gap_analysis(
    *,
    refresh_plan: dict[str, Any] | None,
    approval_summary: dict[str, Any] | None,
    sampling_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    refresh_plan = refresh_plan if isinstance(refresh_plan, dict) else {}
    available_count = int(refresh_plan.get("availableFreshScaleoutCaseCount", 0))
    required_count = int(refresh_plan.get("requiredFreshScaleoutCaseCount", REQUIRED_FRESH_SOURCE_CANDIDATE_COUNT))
    return {
        "schemaVersion": "video_to_analysis_source_pool_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "currentBlocker": (approval_summary or {}).get("primaryBlocker") if isinstance(approval_summary, dict) else None,
        "sourceSamplingPoolExhausted": bool(
            isinstance(sampling_summary, dict)
            and sampling_summary.get("generatedSourceSamplingPoolExhausted") is True
        ),
        "availableFreshSourceCandidateCount": available_count,
        "requiredFreshSourceCandidateCount": required_count,
        "freshCandidateGapCount": max(0, required_count - available_count),
        "priorAvailableFreshScaleoutCases": refresh_plan.get("availableFreshScaleoutCases", []),
        "scaleoutCaseCount": int(refresh_plan.get("scaleoutCaseCount", 0) or 0),
    }


def _family_inventory(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    families = sorted({str(row["sourceFamily"]) for row in candidates})
    family_rows: list[dict[str, Any]] = []
    for family in families:
        family_candidates = [row for row in candidates if row["sourceFamily"] == family]
        missing = sorted(
            {
                path
                for row in family_candidates
                for path in row.get("missingEvidencePaths", [])
            }
        )
        family_rows.append(
            {
                "sourceFamily": family,
                "plannedCandidateCount": len(family_candidates),
                "missingEvidenceCount": len(missing),
                "missingEvidencePaths": missing,
                "familyInventoryReady": not missing,
                "downloadExecutionApproved": False,
                "trainingEligible": False,
                "runtimeMutationEligible": False,
            }
        )
    return {
        "schemaVersion": "video_to_analysis_candidate_source_family_inventory_v1",
        "generatedAt": utc_now_iso(),
        "sourceFamilies": family_rows,
        "sourceFamilyCount": len(family_rows),
        "plannedFreshSourceCandidateCount": len(candidates),
        "candidateSourceFamilyInventoryReady": all(row["familyInventoryReady"] for row in family_rows),
    }


def _guardrail_contract(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "candidateSourceId": row["candidateSourceId"],
            "sourceFamily": row["sourceFamily"],
            "downloadRequired": row["downloadRequired"],
            "downloadApprovalRequired": row["downloadApprovalRequired"],
            "trainingEligible": row["trainingEligible"],
            "runtimeMutationEligible": row["runtimeMutationEligible"],
            "scaleoutExecutionApproved": row["scaleoutExecutionApproved"],
        }
        for row in candidates
    ]
    ready = all(
        row["downloadRequired"] is False
        and row["trainingEligible"] is False
        and row["runtimeMutationEligible"] is False
        and row["scaleoutExecutionApproved"] is False
        for row in rows
    )
    return {
        "schemaVersion": "video_to_analysis_source_access_guardrail_contract_v1",
        "generatedAt": utc_now_iso(),
        "sourceAccessGuardrailReady": ready,
        "boundedExecutionMode": "bounded_existing_or_approved_sample_only",
        "downloadExecutionApproved": False,
        "downloadExecutionExecuted": False,
        "fullDatasetDownloadApproved": False,
        "archiveExtractionApproved": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "candidateGuardrails": rows,
    }


def _storage_preflight(candidates: list[dict[str, Any]], missing_evidence_paths: list[str]) -> dict[str, Any]:
    unique_artifacts: dict[str, dict[str, Any]] = {}
    for row in candidates:
        for artifact in row.get("evidenceArtifacts", []):
            if isinstance(artifact, dict):
                unique_artifacts[str(artifact["relativePath"])] = artifact
    total_existing_bytes = sum(int(row["sizeBytes"]) for row in unique_artifacts.values())
    return {
        "schemaVersion": "video_to_analysis_storage_budget_preflight_plan_v1",
        "generatedAt": utc_now_iso(),
        "storageBudgetPreflightReady": not missing_evidence_paths,
        "storageBudgetPolicyPassed": not missing_evidence_paths,
        "storageBudgetClass": "small_bounded_sample",
        "plannedAdditionalDownloadBytes": 0,
        "plannedAdditionalStorageMutationBytes": 0,
        "existingEvidenceArtifactCount": len(unique_artifacts),
        "existingEvidenceBytes": total_existing_bytes,
        "missingEvidenceCount": len(missing_evidence_paths),
        "missingEvidencePaths": missing_evidence_paths,
        "cleanupExecutionRequired": False,
        "cleanupMutationExecuted": False,
    }


def _decision_matrix(
    *,
    inputs_ready: bool,
    missing_evidence_count: int,
    enough_candidates: bool,
    storage_budget_passed: bool,
    primary_blocker: str | None,
    next_lever: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_source_pool_replenishment_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "decisions": [
            {
                "condition": "current_exhausted_scaleout_pool_truth_missing",
                "selected": not inputs_ready,
                "primaryBlocker": BLOCKER_INPUTS_MISSING,
                "nextRecommendedNextLever": NEXT_SCALEOUT_APPROVAL,
            },
            {
                "condition": "source_access_metadata_missing",
                "selected": inputs_ready and missing_evidence_count > 0,
                "primaryBlocker": BLOCKER_SOURCE_ACCESS_MISSING,
                "nextRecommendedNextLever": NEXT_DATASET_ACCESS_REVIEW,
            },
            {
                "condition": "not_enough_planned_candidates",
                "selected": inputs_ready and missing_evidence_count == 0 and not enough_candidates,
                "primaryBlocker": BLOCKER_INSUFFICIENT_EXISTING_SOURCES,
                "nextRecommendedNextLever": NEXT_MANUAL_SELECTION,
            },
            {
                "condition": "storage_budget_not_ready",
                "selected": inputs_ready and missing_evidence_count == 0 and enough_candidates and not storage_budget_passed,
                "primaryBlocker": BLOCKER_STORAGE_BUDGET_NOT_READY,
                "nextRecommendedNextLever": NEXT_STORAGE_CLEANUP_MAP,
            },
            {
                "condition": "source_pool_replenishment_plan_ready",
                "selected": inputs_ready and missing_evidence_count == 0 and enough_candidates and storage_budget_passed,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_REPLENISHMENT_APPROVAL,
            },
        ],
    }


def run_video_to_analysis_source_pool_replenishment_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)

    status = load_json(storage_root / "automation" / "unattended_roadmap_loop_status.json")
    approval_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_execution_approval",
        DEFAULT_SCALEOUT_APPROVAL_DIR_NAME,
    )
    sampling_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_source_sampling_expansion",
        DEFAULT_SOURCE_SAMPLING_DIR_NAME,
    )
    refresh_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_plan_refresh",
        DEFAULT_PLAN_REFRESH_DIR_NAME,
    )
    approval_summary = load_json(
        approval_dir / "real_video_scaleout_execution_approval_summary.json"
    )
    sampling_summary = load_json(
        sampling_dir / "real_video_scaleout_source_sampling_expansion_summary.json"
    )
    refresh_summary = load_json(
        refresh_dir / "real_video_scaleout_plan_refresh_summary.json"
    )
    refresh_plan = load_json(refresh_dir / "real_video_scaleout_plan.json")
    dashboard_view_model = load_json(root / DEFAULT_DASHBOARD_DIR_NAME / "operator_dashboard_view_model.json")
    research_note_path = REPO_ROOT / "docs" / "foot-soccer-deepresearch.md"

    candidates = _planned_candidates(storage_root, root, output_dir_name=output_dir_name)
    missing_evidence_paths = _missing_evidence_paths(candidates)
    family_inventory = _family_inventory(candidates)
    guardrail_contract = _guardrail_contract(candidates)
    storage_preflight = _storage_preflight(candidates, missing_evidence_paths)
    gap_analysis = _gap_analysis(
        refresh_plan=refresh_plan,
        approval_summary=approval_summary,
        sampling_summary=sampling_summary,
    )

    inputs_ready = _current_blocker_inputs_ready(
        status=status,
        approval_summary=approval_summary,
        sampling_summary=sampling_summary,
        refresh_summary=refresh_summary,
        refresh_plan=refresh_plan,
        dashboard_view_model=dashboard_view_model,
        research_note_exists=research_note_path.exists(),
    )
    source_family_count = int(family_inventory["sourceFamilyCount"])
    enough_candidates = len(candidates) >= REQUIRED_FRESH_SOURCE_CANDIDATE_COUNT and source_family_count >= 2
    storage_budget_passed = bool(storage_preflight["storageBudgetPolicyPassed"])

    if not inputs_ready:
        goal = False
        primary_blocker = BLOCKER_INPUTS_MISSING
        next_lever = NEXT_SCALEOUT_APPROVAL
        english = "Source-pool replenishment inputs are missing or do not match the exhausted scaleout-pool blocker."
    elif missing_evidence_paths:
        goal = False
        primary_blocker = BLOCKER_SOURCE_ACCESS_MISSING
        next_lever = NEXT_DATASET_ACCESS_REVIEW
        english = "Source-pool replenishment plan is blocked because required source evidence or access metadata is missing."
    elif not enough_candidates:
        goal = False
        primary_blocker = BLOCKER_INSUFFICIENT_EXISTING_SOURCES
        next_lever = NEXT_MANUAL_SELECTION
        english = "Source-pool replenishment plan could not produce enough bounded candidate rows."
    elif not storage_budget_passed:
        goal = False
        primary_blocker = BLOCKER_STORAGE_BUDGET_NOT_READY
        next_lever = NEXT_STORAGE_CLEANUP_MAP
        english = "Source-pool replenishment plan is blocked because storage budget preflight is not ready."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_REPLENISHMENT_APPROVAL
        english = "Source-pool replenishment plan is ready; approve the bounded source pool before any scaleout execution."

    bounded_plan = {
        "schemaVersion": "video_to_analysis_bounded_sample_replenishment_plan_v1",
        "generatedAt": utc_now_iso(),
        "plannedFreshSourceCandidates": candidates,
        "plannedFreshSourceCandidateCount": len(candidates),
        "sourceFamilyCount": source_family_count,
        "missingEvidenceCount": len(missing_evidence_paths),
        "missingEvidencePaths": missing_evidence_paths,
        "downloadExecutionApproved": False,
        "downloadExecutionExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "scaleoutExecutionApproved": False,
        "nextApprovalFamily": NEXT_REPLENISHMENT_APPROVAL,
    }

    summary = guarded_summary(
        batch_name="video_to_analysis_source_pool_replenishment_plan",
        goal=goal,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "sourcePoolReplenishmentPlanReady": goal,
            "plannedFreshSourceCandidateCount": len(candidates),
            "requiredFreshSourceCandidateCount": REQUIRED_FRESH_SOURCE_CANDIDATE_COUNT,
            "sourceFamilyCount": source_family_count,
            "missingEvidenceCount": len(missing_evidence_paths),
            "storageBudgetPolicyPassed": storage_budget_passed,
            "storageBudgetPreflightReady": bool(storage_preflight["storageBudgetPreflightReady"]),
            "sourceAccessGuardrailReady": bool(guardrail_contract["sourceAccessGuardrailReady"]),
            "downloadExecutionApproved": False,
            "downloadExecutionExecuted": False,
            "sourcePlanDir": refresh_dir.name,
            "sourceSamplingDir": sampling_dir.name,
        },
    )
    summary.update(standard_false_flags())

    decision_matrix = _decision_matrix(
        inputs_ready=inputs_ready,
        missing_evidence_count=len(missing_evidence_paths),
        enough_candidates=enough_candidates,
        storage_budget_passed=storage_budget_passed,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
    )

    return write_outcome(
        output_root=output_root,
        summary_filename="source_pool_replenishment_summary.json",
        summary=summary,
        artifacts={
            "source_pool_gap_analysis.json": gap_analysis,
            "candidate_source_family_inventory.json": family_inventory,
            "bounded_sample_replenishment_plan.json": bounded_plan,
            "source_access_guardrail_contract.json": guardrail_contract,
            "storage_budget_preflight_plan.json": storage_preflight,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Source Pool Replenishment Plan",
    )


def main() -> None:
    main_for("Write video-to-analysis source-pool replenishment plan.", run_video_to_analysis_source_pool_replenishment_plan)


if __name__ == "__main__":
    main()
