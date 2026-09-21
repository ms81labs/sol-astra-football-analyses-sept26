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
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_SOURCE_DIR_NAME = "football_external_benchmark_real_source_path_consolidation_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_v1"
BLOCKER_SOURCE_PATH_MISSING = "video_to_analysis_real_video_scaleout_source_path_missing"
NEXT_SOURCE_PATH = "football_external_benchmark_real_source_path_consolidation"
NEXT_RECURRING = "video_to_analysis_steady_state_monitoring_recurring_schedule"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "real_video_scaleout_plan"},
            {"attemptNumber": 2, "attemptApproachFamily": "scaleout_scope_repair"},
            {"attemptNumber": 3, "attemptApproachFamily": "scaleout_blocker_summary"},
        ],
    }


def _source_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("sourcePathConsolidationReady") is True
        and isinstance(manifest, dict)
        and len(manifest.get("sourcePaths", [])) == 2
    )


def run_video_to_analysis_real_video_scaleout_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    source_root = root / DEFAULT_SOURCE_DIR_NAME
    source_summary = load_json(source_root / "real_source_path_consolidation_summary.json")
    source_manifest = load_json(source_root / "real_source_path_consolidation_manifest.json")
    ready = _source_ready(source_summary, source_manifest)
    scaleout_cases = [
        {"id": "promoted_runtime_reference_video", "executionMode": "bounded_existing_or_approved_sample_only"},
        {"id": "soccernet_bounded_224p_member", "executionMode": "bounded_existing_or_approved_sample_only"},
        {"id": "soccertrack_materialized_fixture", "executionMode": "bounded_existing_or_approved_sample_only"},
        {"id": "normal_storage_recent_upload", "executionMode": "bounded_existing_or_approved_sample_only"},
        {"id": "operator_selected_canary_video", "executionMode": "bounded_existing_or_approved_sample_only"},
    ]
    plan = {
        "schemaVersion": "video_to_analysis_real_video_scaleout_plan_v1",
        "generatedAt": utc_now_iso(),
        "scaleoutCases": scaleout_cases,
        "scaleoutCaseCount": len(scaleout_cases),
        "fullDatasetDownloadAllowed": False,
        "normalMatchStorageMutationRequiresApproval": True,
        "realVideoScaleoutPlanReady": ready,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_real_video_scaleout_plan",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_SOURCE_PATH_MISSING,
        next_lever=NEXT_RECURRING if ready else NEXT_SOURCE_PATH,
        english=(
            "Real-video scaleout plan is ready for bounded approval."
            if ready
            else "Real-source path consolidation is missing; consolidate source paths first."
        ),
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={"realVideoScaleoutPlanReady": ready, "scaleoutCaseCount": len(scaleout_cases) if ready else 0},
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="real_video_scaleout_plan_summary.json",
        summary=summary,
        artifacts={
            "real_video_scaleout_plan.json": plan,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Real Video Scaleout Plan",
    )


def main() -> None:
    main_for("Plan bounded video-to-analysis real-video scaleout.", run_video_to_analysis_real_video_scaleout_plan)


if __name__ == "__main__":
    main()
