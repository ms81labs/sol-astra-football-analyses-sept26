from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_RECONCILIATION_DIR_NAME = "video_to_analysis_roadmap_state_reconciliation_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_release_acceptance_archive_v1"

BLOCKER_RECONCILIATION_MISSING = "video_to_analysis_release_archive_reconciliation_missing"
NEXT_RECONCILIATION = "video_to_analysis_roadmap_state_reconciliation"
NEXT_STEADY_STATE = "video_to_analysis_steady_state_monitoring_cycle"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "release_acceptance_archive",
                "successCriteria": [
                    "roadmap reconciliation passed",
                    "archive current v7.3 runtime/product/monitoring/detector closeout truth",
                    "write an operator-readable next-step backlog",
                ],
                "failureAdaptation": "If reconciliation is missing, route back to reconciliation.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_acceptance_archive_reference_repair",
                "successCriteria": ["repair only source-truth references and archive metadata"],
                "failureAdaptation": "If archive inputs remain incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_acceptance_archive_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Stop without training, promotion mutation, downloads, or runtime-default mutation.",
            },
        ],
    }


def _reconciliation_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("manualStrategicSentinelResolved") is True
        and summary.get("nextRecommendedNextLever") == "video_to_analysis_release_acceptance_archive"
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
    )


def run_video_to_analysis_release_acceptance_archive(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    reconciliation_root = root / DEFAULT_RECONCILIATION_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    reconciliation_summary = load_json(reconciliation_root / "roadmap_state_reconciliation_summary.json")
    reconciliation_matrix = load_json(reconciliation_root / "roadmap_state_readiness_matrix.json")
    ready = _reconciliation_ready(reconciliation_summary)
    generated_at = utc_now_iso()
    attempts = _attempt_plan()

    if ready:
        primary_blocker = None
        next_lever = NEXT_STEADY_STATE
        goal = True
        english = (
            "Video-to-analysis release acceptance archive is complete: v7.3 is active, product and monitoring "
            "lanes are closed, detector evaluation is report-bound, and bounded growth is optional future work."
        )
    else:
        primary_blocker = BLOCKER_RECONCILIATION_MISSING
        next_lever = NEXT_RECONCILIATION
        goal = False
        english = "Roadmap reconciliation is missing or unsafe; reconcile state before archiving release acceptance."

    release_archive_manifest = {
        "schemaVersion": "video_to_analysis_release_acceptance_archive_manifest_v1",
        "generatedAt": generated_at,
        "releaseAcceptanceArchived": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "primaryOperatorRoutes": [
            "/video-to-analysis/acceptance-report",
            "/video-to-analysis/operator-handoff",
            "/video-to-analysis/post-release-monitoring",
            "/video-to-analysis/detector-evaluation",
        ]
        if goal
        else [],
        "archivedMilestones": {
            "v7_3RuntimeDefaultActive": bool((reconciliation_summary or {}).get("runtimeDefaultV7_3Active")),
            "releaseCandidateClosed": bool((reconciliation_summary or {}).get("releaseCandidateClosed")),
            "productLaneClosed": bool((reconciliation_summary or {}).get("productLaneClosed")),
            "postReleaseMonitoringClosed": bool((reconciliation_summary or {}).get("postReleaseMonitoringClosed")),
            "detectorEvaluationLaneClosed": bool((reconciliation_summary or {}).get("detectorEvaluationLaneClosed")),
            "growthLaneClosedManualChoice": bool((reconciliation_summary or {}).get("growthLaneClosedManualChoice")),
        },
        "sourceReadinessMatrix": reconciliation_matrix or {},
    }
    operator_finish_line = {
        "schemaVersion": "video_to_analysis_operator_finish_line_map_v1",
        "generatedAt": generated_at,
        "status": "current_release_finished" if goal else "blocked",
        "whatWorksNow": [
            "v7.3 is the active runtime default",
            "acceptance report and operator handoff routes are bound",
            "post-release monitoring route is bound and closed",
            "detector evaluation report lane is closed from existing artifacts",
            "bounded growth is intentionally stopped at the manual strategic gate",
        ]
        if goal
        else [],
        "whatIsNotPartOfThisArchive": [
            "bulk dataset download",
            "new training",
            "promotion mutation",
            "automatic bounded scaleout continuation",
        ],
    }
    remaining_backlog = {
        "schemaVersion": "video_to_analysis_remaining_work_backlog_v1",
        "generatedAt": generated_at,
        "nextRecommendedNextLever": next_lever,
        "nextFiveSteps": [
            {
                "order": 1,
                "lever": NEXT_STEADY_STATE,
                "purpose": "Run or schedule a lightweight health check for the finished current release.",
            },
            {
                "order": 2,
                "lever": "football_external_soccernet_broader_validation_choice",
                "purpose": "Choose whether to spend time on broader external validation now that the product lane is stable.",
            },
            {
                "order": 3,
                "lever": "video_to_analysis_upload_to_analysis_walkthrough",
                "purpose": "Polish the product path so an operator can confidently use upload/select video to analysis.",
            },
            {
                "order": 4,
                "lever": "v7_4_training_decision_from_real_misses",
                "purpose": "Train again only when new real miss truth proves it is needed.",
            },
            {
                "order": 5,
                "lever": "video_to_analysis_storage_retention_and_artifact_hygiene",
                "purpose": "Keep generated artifacts and external samples from making the repo hard to operate.",
            },
        ],
    }
    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = goal
    false_flags["runtimeDefaultMutationAllowed"] = False
    summary = {
        "batchName": "video_to_analysis_release_acceptance_archive",
        "generatedAt": generated_at,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "videoToAnalysisReleaseAcceptanceArchived": goal,
        "currentReleaseFinished": goal,
        "manualStrategicSentinelResolved": goal,
        "autoContinueBoundedGrowthRecommended": False,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        **false_flags,
        "runtimeDefaultMutationExecutedByThisBatch": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_release_acceptance_archive_decision_matrix_v1",
        "generatedAt": generated_at,
        "decisions": [
            {
                "condition": "roadmap_reconciliation_missing",
                "selected": primary_blocker == BLOCKER_RECONCILIATION_MISSING,
                "primaryBlocker": BLOCKER_RECONCILIATION_MISSING,
                "nextRecommendedNextLever": NEXT_RECONCILIATION,
            },
            {
                "condition": "release_acceptance_archived",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STEADY_STATE,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_acceptance_archive_summary.json",
        summary=summary,
        artifacts={
            "release_acceptance_archive_manifest.json": release_archive_manifest,
            "operator_finish_line_map.json": operator_finish_line,
            "remaining_work_backlog.json": remaining_backlog,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": attempts,
        },
        markdown_title="Video To Analysis Release Acceptance Archive",
    )


def main() -> None:
    main_for("Archive current video-to-analysis release acceptance state.", run_video_to_analysis_release_acceptance_archive)


if __name__ == "__main__":
    main()
