from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SOURCE_DIR_NAME = "football_external_benchmark_real_source_path_consolidation_v1"
DEFAULT_PREVIOUS_PLAN_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_v1"
DEFAULT_POOL_EXHAUSTION_DIR_NAME = "video_to_analysis_bounded_next_sample_execution_approval_v4"
DEFAULT_SOURCE_POOL_REPLENISHMENT_APPROVAL_DIR_NAME = "video_to_analysis_source_pool_replenishment_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_refresh_v1"
BLOCKER_INPUTS_MISSING = "video_to_analysis_real_video_scaleout_refresh_inputs_missing"
BLOCKER_POOL_INSUFFICIENT = "video_to_analysis_real_video_scaleout_candidate_pool_insufficient"
NEXT_SOURCE_PATH = "football_external_benchmark_real_source_path_consolidation"
NEXT_APPROVAL = "video_to_analysis_real_video_scaleout_execution_approval"
NEXT_SOURCE_SAMPLING = "video_to_analysis_real_video_scaleout_source_sampling_expansion"
REQUIRED_REFRESH_CASE_COUNT = 5


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "real_video_scaleout_plan_refresh"},
        {"attemptNumber": 2, "attemptApproachFamily": "real_video_scaleout_refresh_scope_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "real_video_scaleout_refresh_blocker_summary"},
    ]}


def _base_case_pool() -> list[dict[str, Any]]:
    return [
        {"id": "soccernet_second_bounded_member", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccernet"},
        {"id": "soccernet_third_bounded_member", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccernet"},
        {"id": "soccertrack_second_materialized_fixture", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccertrack"},
        {"id": "operator_canary_followup_clip", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "operator"},
        {"id": "normal_storage_followup_upload", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "normal_storage"},
        {"id": "soccernet_fourth_bounded_member", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccernet"},
        {"id": "soccernet_fifth_bounded_member", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccernet"},
        {"id": "soccertrack_third_materialized_fixture", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccertrack"},
        {"id": "operator_canary_second_followup_clip", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "operator"},
        {"id": "normal_storage_second_followup_upload", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "normal_storage"},
        {"id": "promoted_runtime_alternate_reference_video", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "promoted_runtime"},
        {"id": "soccernet_sixth_bounded_member", "executionMode": "bounded_existing_or_approved_sample_only", "sourceFamily": "soccernet"},
    ]


def _source_sampling_expansion_cases(root: Path) -> list[dict[str, Any]]:
    expansion_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_source_sampling_expansion",
        "video_to_analysis_real_video_scaleout_source_sampling_expansion_v1",
    )
    summary = load_json(expansion_dir / "real_video_scaleout_source_sampling_expansion_summary.json")
    manifest = load_json(expansion_dir / "expanded_scaleout_candidate_manifest.json")
    if not (
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and isinstance(manifest, dict)
    ):
        return []
    candidates = manifest.get("expandedScaleoutCandidates", [])
    return [row for row in candidates if isinstance(row, dict) and row.get("id")]


def _source_pool_replenishment_approval_cases(root: Path) -> list[dict[str, Any]]:
    approval_dir = latest_versioned_dir(
        root,
        "video_to_analysis_source_pool_replenishment_approval",
        DEFAULT_SOURCE_POOL_REPLENISHMENT_APPROVAL_DIR_NAME,
    )
    summary = load_json(approval_dir / "source_pool_replenishment_approval_summary.json")
    approved_pool = load_json(approval_dir / "approved_bounded_source_pool.json")
    if not (
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("sourcePoolReplenishmentApproved") is True
        and isinstance(approved_pool, dict)
        and approved_pool.get("approvedBoundedScaleoutCaseCount", 0) >= REQUIRED_REFRESH_CASE_COUNT
    ):
        return []
    rows = approved_pool.get("approvedBoundedScaleoutCases", [])
    candidates: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not (isinstance(row, dict) and row.get("id")):
            continue
        candidates.append(
            {
                "id": str(row["id"]),
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": row.get("sourceFamily"),
                "evidenceBasis": row.get("evidenceBasis"),
                "expectedArtifactPaths": row.get("expectedArtifactPaths", []),
                "approvalArtifactPath": row.get("approvalArtifactPath"),
                "sourcePoolApprovalDir": approval_dir.name,
            }
        )
    return candidates


def _case_pool(root: Path) -> list[dict[str, Any]]:
    source_pool_cases = _source_pool_replenishment_approval_cases(root)
    expansion_cases = _source_sampling_expansion_cases(root)
    return [*source_pool_cases, *expansion_cases, *_base_case_pool()]


def _previous_scaleout_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    plan_dirs = [root / DEFAULT_PREVIOUS_PLAN_DIR_NAME]
    plan_dirs.extend(sorted(root.glob("video_to_analysis_real_video_scaleout_plan_refresh_v*")))
    for plan_dir in plan_dirs:
        plan = load_json(plan_dir / "real_video_scaleout_plan.json")
        for row in (plan.get("scaleoutCases", []) if isinstance(plan, dict) else []):
            if isinstance(row, dict) and row.get("id"):
                ids.add(str(row["id"]))
    return ids


def run_video_to_analysis_real_video_scaleout_plan_refresh(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    source_summary = load_json(root / DEFAULT_SOURCE_DIR_NAME / "real_source_path_consolidation_summary.json")
    source_manifest = load_json(root / DEFAULT_SOURCE_DIR_NAME / "real_source_path_consolidation_manifest.json")
    previous_plan = load_json(root / DEFAULT_PREVIOUS_PLAN_DIR_NAME / "real_video_scaleout_plan.json")
    pool_exhaustion_dir = latest_versioned_dir(root, "video_to_analysis_bounded_next_sample_execution_approval", DEFAULT_POOL_EXHAUSTION_DIR_NAME)
    pool_exhaustion = load_json(pool_exhaustion_dir / "bounded_next_sample_execution_approval_summary.json")
    previous_ids = _previous_scaleout_ids(root)
    candidates = [row for row in _case_pool(root) if row["id"] not in previous_ids]
    selected = candidates[:REQUIRED_REFRESH_CASE_COUNT]
    source_pool_approval_dir = (
        str(selected[0].get("sourcePoolApprovalDir"))
        if selected and selected[0].get("sourcePoolApprovalDir")
        else None
    )
    inputs_ready = bool(
        isinstance(source_summary, dict)
        and source_summary.get("goalAchieved") is True
        and isinstance(source_manifest, dict)
        and len(source_manifest.get("sourcePaths", [])) == 2
        and isinstance(previous_plan, dict)
        and previous_plan.get("realVideoScaleoutPlanReady") is True
        and isinstance(pool_exhaustion, dict)
        and pool_exhaustion.get("primaryBlocker") == "video_to_analysis_bounded_next_sample_pool_exhausted"
    )
    enough_fresh_cases = len(selected) == REQUIRED_REFRESH_CASE_COUNT
    ready = inputs_ready and enough_fresh_cases
    primary_blocker = None
    next_lever = NEXT_APPROVAL
    english = "Refreshed real-video scaleout plan is ready after bounded sample pool exhaustion."
    if not inputs_ready:
        primary_blocker = BLOCKER_INPUTS_MISSING
        next_lever = NEXT_SOURCE_PATH
        english = "Scaleout refresh inputs are missing."
    elif not enough_fresh_cases:
        primary_blocker = BLOCKER_POOL_INSUFFICIENT
        next_lever = NEXT_SOURCE_SAMPLING
        english = "Fresh scaleout candidate pool is insufficient; expand source sampling before another bounded scaleout."
    plan = {
        "schemaVersion": "video_to_analysis_real_video_scaleout_plan_refresh_v1",
        "generatedAt": utc_now_iso(),
        "realVideoScaleoutPlanReady": ready,
        "refreshReason": "bounded_next_sample_pool_exhausted",
        "sourcePoolExhaustionDir": pool_exhaustion_dir.name,
        "excludedPreviousScaleoutCaseIds": sorted(previous_ids),
        "scaleoutCases": selected if ready else [],
        "scaleoutCaseCount": len(selected) if ready else 0,
        "availableFreshScaleoutCases": candidates,
        "availableFreshScaleoutCaseCount": len(candidates),
        "requiredFreshScaleoutCaseCount": REQUIRED_REFRESH_CASE_COUNT,
        "fullDatasetDownloadAllowed": False,
        "normalMatchStorageMutationRequiresApproval": True,
        "sourcePoolReplenishmentApprovalDir": source_pool_approval_dir,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_real_video_scaleout_plan_refresh",
        goal=ready,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "realVideoScaleoutPlanRefreshReady": ready,
            "refreshedScaleoutCaseCount": len(selected) if ready else 0,
            "availableFreshScaleoutCaseCount": len(candidates),
            "requiredFreshScaleoutCaseCount": REQUIRED_REFRESH_CASE_COUNT,
            "sourcePoolReplenishmentApprovalDir": source_pool_approval_dir,
        },
    )
    if inputs_ready and not enough_fresh_cases:
        summary["roadmapAdvanceAllowed"] = True
    return write_outcome(
        output_root=output_root,
        summary_filename="real_video_scaleout_plan_refresh_summary.json",
        summary=summary,
        artifacts={
            "real_video_scaleout_plan.json": plan,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Real Video Scaleout Plan Refresh",
    )


def main() -> None:
    main_for("Refresh bounded real-video scaleout plan.", run_video_to_analysis_real_video_scaleout_plan_refresh)


if __name__ == "__main__":
    main()
