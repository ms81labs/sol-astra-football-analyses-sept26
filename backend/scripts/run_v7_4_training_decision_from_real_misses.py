from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

DEFAULT_WALKTHROUGH_DIR_NAME = "video_to_analysis_upload_to_analysis_walkthrough_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_4_training_decision_from_real_misses_v1"

BLOCKER_WALKTHROUGH_MISSING = "v7_4_training_decision_upload_walkthrough_missing"
NEXT_WALKTHROUGH = "video_to_analysis_upload_to_analysis_walkthrough"
NEXT_STORAGE_HYGIENE = "video_to_analysis_storage_retention_and_artifact_hygiene"
NEXT_MISS_CAPTURE = "football_external_soccernet_detector_miss_capture_and_label_queue"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "v7_4_training_decision_from_real_misses",
                "successCriteria": [
                    "walkthrough truth exists",
                    "real miss review/training lineage is read",
                    "v7.4 training is allowed only if new unresolved real-miss truth exists",
                ],
                "failureAdaptation": "If no new miss truth exists, defer training and route to storage hygiene.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "v7_4_training_decision_evidence_repair",
                "successCriteria": ["repair only miss-evidence references or thresholds"],
                "failureAdaptation": "Do not create labels or train while repairing decision truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "v7_4_training_decision_blocker_summary",
                "successCriteria": ["write one blocker and one next family"],
                "failureAdaptation": "Route to miss capture, storage hygiene, or walkthrough repair.",
            },
        ],
    }


def _walkthrough_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("uploadToAnalysisWalkthroughReady") is True
    )


def _ok(summary: dict[str, Any] | None) -> bool:
    return bool(isinstance(summary, dict) and summary.get("goalAchieved") is True and summary.get("primaryBlocker") is None)


def run_v7_4_training_decision_from_real_misses(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    walkthrough_summary = load_json(root / DEFAULT_WALKTHROUGH_DIR_NAME / "upload_to_analysis_walkthrough_summary.json")
    miss_resolution = load_json(
        root / "football_external_soccernet_detector_miss_manual_review_resolution_v1" / "detector_miss_manual_review_resolution_summary.json"
    )
    v7_3_manifest = load_json(root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1" / "v7_3_training_manifest_prep_summary.json")
    v7_3_promotion = load_json(root / "v7_3_promotion_readiness_validation_v1" / "v7_3_promotion_readiness_summary.json")
    release_archive = load_json(root / "video_to_analysis_release_acceptance_archive_v1" / "release_acceptance_archive_summary.json")

    walkthrough_ready = _walkthrough_ready(walkthrough_summary)
    miss_resolution_ready = _ok(miss_resolution)
    v7_3_real_miss_training_consumed = _ok(v7_3_manifest) and _ok(v7_3_promotion)
    active_release_finished = _ok(release_archive) and release_archive.get("currentReleaseFinished") is True
    unresolved_new_miss_count = int((miss_resolution or {}).get("unresolvedNewMissCount") or 0)
    new_reviewed_miss_count = int((miss_resolution or {}).get("newReviewedPositiveSourceCount") or 0)
    v7_4_training_needed = bool(walkthrough_ready and unresolved_new_miss_count >= 20 and new_reviewed_miss_count >= 20)

    if not walkthrough_ready:
        goal = False
        primary_blocker = BLOCKER_WALKTHROUGH_MISSING
        next_lever = NEXT_WALKTHROUGH
        english = "Upload-to-analysis walkthrough is missing; package walkthrough before v7.4 training decision."
    elif v7_4_training_needed:
        goal = True
        primary_blocker = None
        next_lever = NEXT_MISS_CAPTURE
        english = "New unresolved real-miss truth is large enough to justify v7.4 data prep; capture and review misses next."
    else:
        goal = True
        primary_blocker = None
        next_lever = NEXT_STORAGE_HYGIENE
        english = "No new real-miss evidence justifies v7.4 training now. Keep training deferred and run storage hygiene next."

    decision = {
        "schemaVersion": "v7_4_training_decision_from_real_misses_v1",
        "generatedAt": utc_now_iso(),
        "walkthroughReady": walkthrough_ready,
        "missResolutionReady": miss_resolution_ready,
        "v7_3RealMissTrainingAlreadyConsumed": v7_3_real_miss_training_consumed,
        "activeReleaseFinished": active_release_finished,
        "unresolvedNewMissCount": unresolved_new_miss_count,
        "newReviewedMissCount": new_reviewed_miss_count,
        "v7_4TrainingNeeded": v7_4_training_needed,
        "trainingDeferred": not v7_4_training_needed and walkthrough_ready,
        "selectedNextLever": next_lever,
    }
    summary = {
        "batchName": "v7_4_training_decision_from_real_misses",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "walkthroughReady": walkthrough_ready,
        "missResolutionReady": miss_resolution_ready,
        "v7_3RealMissTrainingAlreadyConsumed": v7_3_real_miss_training_consumed,
        "activeReleaseFinished": active_release_finished,
        "unresolvedNewMissCount": unresolved_new_miss_count,
        "newReviewedMissCount": new_reviewed_miss_count,
        "v7_4TrainingNeeded": v7_4_training_needed,
        "trainingDeferred": not v7_4_training_needed and walkthrough_ready,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="v7_4_training_decision_from_real_misses_summary.json",
        summary=summary,
        artifacts={
            "v7_4_training_decision.json": decision,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="V7.4 Training Decision From Real Misses",
    )


def main() -> None:
    main_for("Decide whether v7.4 training is justified by real misses.", run_v7_4_training_decision_from_real_misses)


if __name__ == "__main__":
    main()
