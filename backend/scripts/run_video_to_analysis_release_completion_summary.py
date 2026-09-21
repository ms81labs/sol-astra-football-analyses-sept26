from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_CLOSEOUT_DIR_NAME = "video_to_analysis_promoted_runtime_release_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_release_completion_summary_v1"

BLOCKER_CLOSEOUT_MISSING = "video_to_analysis_promoted_runtime_release_closeout_missing"
NEXT_RELEASE_CLOSEOUT = "video_to_analysis_promoted_runtime_release_closeout"
NEXT_POST_RELEASE_MONITORING = "video_to_analysis_promoted_runtime_post_release_monitoring_plan"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "release_completion_summary",
                "successCriteria": [
                    "promoted runtime release closeout passed",
                    "write final release completion manifest",
                    "route next to promoted-runtime post-release monitoring",
                ],
                "failureAdaptation": "If release closeout is missing, route back to release closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_completion_evidence_repair",
                "successCriteria": ["repair only completion evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_completion_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop after blocker summary; do not force monitoring plan.",
            },
        ],
    }


def _closeout_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("promotedRuntimeReleaseClosed") is True
        and summary.get("promotedRuntimeOperatorAcceptancePassed") is True
        and summary.get("routeSmokePassedCount") == 5
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("promotedRuntimeReleaseClosed") is True
    )


def run_video_to_analysis_release_completion_summary(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    closeout_root = root / DEFAULT_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(closeout_root / "promoted_runtime_release_closeout_summary.json")
    release_manifest = load_json(closeout_root / "promoted_runtime_release_manifest.json")
    ready = _closeout_ready(closeout_summary, release_manifest)

    if ready:
        primary_blocker = None
        next_lever = NEXT_POST_RELEASE_MONITORING
        goal = True
        english = "Video-to-analysis promoted runtime release is complete. Plan promoted-runtime post-release monitoring next."
    else:
        primary_blocker = BLOCKER_CLOSEOUT_MISSING
        next_lever = NEXT_RELEASE_CLOSEOUT
        goal = False
        english = "Promoted runtime release closeout is missing or unsafe; close release before completion summary."

    completion_manifest = {
        "schemaVersion": "video_to_analysis_release_completion_manifest_v1",
        "generatedAt": utc_now_iso(),
        "videoToAnalysisPromotedRuntimeReleaseComplete": goal,
        "releasedRuntimeVersion": "v7.2" if goal else None,
        "releasedRuntimeName": "touchline_detector_candidate_v7" if goal else None,
        "nextOperatingMode": "post_release_monitoring" if goal else "release_closeout_required",
        "releaseEvidence": {
            "closeoutSummaryPath": str(closeout_root / "promoted_runtime_release_closeout_summary.json"),
            "releaseManifestPath": str(closeout_root / "promoted_runtime_release_manifest.json"),
        },
    }
    summary = {
        "batchName": "video_to_analysis_release_completion_summary",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "videoToAnalysisPromotedRuntimeReleaseComplete": goal,
        "releasedRuntimeVersion": "v7.2" if goal else None,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_completion_summary.json",
        summary=summary,
        artifacts={
            "release_completion_manifest.json": completion_manifest,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Release Completion Summary",
    )


def main() -> None:
    main_for("Write video-to-analysis release completion summary.", run_video_to_analysis_release_completion_summary)


if __name__ == "__main__":
    main()
