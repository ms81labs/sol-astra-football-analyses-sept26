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

DEFAULT_SNAPSHOT_DIR_NAME = "video_to_analysis_next_roadmap_direction_snapshot_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promotion_review_design_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"

BLOCKER_SNAPSHOT_MISSING = "video_to_analysis_promotion_review_snapshot_missing"
NEXT_SNAPSHOT = "video_to_analysis_next_roadmap_direction_snapshot"
NEXT_EXECUTION = "video_to_analysis_promotion_review_execution"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promotion_review_design",
                "successCriteria": [
                    "read current roadmap snapshot",
                    "design a non-mutating review of existing v7.2 promotion and default-runtime truth",
                ],
                "failureAdaptation": "If the roadmap snapshot is missing, route back to the snapshot batch.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promotion_review_design_contract_repair",
                "successCriteria": ["repair only design schema or evidence references"],
                "failureAdaptation": "If the design remains unsafe, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promotion_review_design_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to snapshot, contract repair, or promotion review execution.",
            },
        ],
    }


def _snapshot_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("nextRoadmapDirectionSnapshotReady") is True
        and summary.get("selectedNextFamily") == "video_to_analysis_promotion_review_design"
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def run_video_to_analysis_promotion_review_design(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)
    snapshot_summary = load_json(root / DEFAULT_SNAPSHOT_DIR_NAME / "next_roadmap_direction_snapshot_summary.json")
    readiness_summary = load_json(root / "v7_2_promotion_readiness_validation_v1" / "v7_2_promotion_readiness_summary.json")
    rollout_summary = load_json(
        _suite_root(storage_root) / "v7_2_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json"
    )
    runtime_registry = load_json(storage_root / "runtime" / "promoted_touchline_detector_candidate.json")
    ready = _snapshot_ready(snapshot_summary)

    if ready:
        primary_blocker = None
        next_lever = NEXT_EXECUTION
        goal = True
        english = "Promotion review design is ready. Execute a non-mutating evidence review next."
    else:
        primary_blocker = BLOCKER_SNAPSHOT_MISSING
        next_lever = NEXT_SNAPSHOT
        goal = False
        english = "Roadmap snapshot does not authorize promotion review design yet."

    runtime_default_already_mutated = bool(
        isinstance(runtime_registry, dict)
        and runtime_registry.get("runtimeDefaultMutationExecuted") is True
        and runtime_registry.get("runtimeUse") == "default_runtime"
    )
    review_design = {
        "schemaVersion": "video_to_analysis_promotion_review_design_v1",
        "generatedAt": utc_now_iso(),
        "promotionReviewDesignReady": goal,
        "reviewMode": "non_mutating_existing_evidence_review",
        "requiredEvidence": {
            "roadmapSnapshot": str(root / DEFAULT_SNAPSHOT_DIR_NAME / "next_roadmap_direction_snapshot_summary.json"),
            "promotionReadiness": str(root / "v7_2_promotion_readiness_validation_v1" / "v7_2_promotion_readiness_summary.json"),
            "runtimeRegistry": str(storage_root / "runtime" / "promoted_touchline_detector_candidate.json"),
            "runtimeDefaultRolloutCloseout": str(
                _suite_root(storage_root) / "v7_2_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json"
            ),
        },
        "reviewQuestions": [
            "Does promoted runtime registry point at v7.2 default runtime?",
            "Did v7.2 promotion readiness pass?",
            "Did post-runtime-default source robustness pass?",
            "Is the old failing_source_not_viable blocker dead in active runtime truth?",
        ],
        "readinessSnapshotPresent": isinstance(readiness_summary, dict),
        "rolloutCloseoutSnapshotPresent": isinstance(rollout_summary, dict),
        "runtimeDefaultAlreadyMutatedBeforeReview": runtime_default_already_mutated,
        "mutationPolicy": {
            "trainingExecutedByThisBatch": False,
            "promotionMutationExecutedByThisBatch": False,
            "runtimeDefaultMutationExecutedByThisBatch": False,
        },
    }
    summary = {
        "batchName": "video_to_analysis_promotion_review_design",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotionReviewDesignReady": goal,
        "runtimeDefaultAlreadyMutatedBeforeReview": runtime_default_already_mutated,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promotion_review_design_summary.json",
        summary=summary,
        artifacts={
            "promotion_review_design.json": review_design,
            "promotion_review_execution_contract.json": {
                "schemaVersion": "video_to_analysis_promotion_review_execution_contract_v1",
                "generatedAt": utc_now_iso(),
                "executionMode": "non_mutating_existing_evidence_review",
                "allowedToMutatePromotion": False,
                "allowedToMutateRuntimeDefault": False,
                "allowedToTrain": False,
            },
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promotion Review Design",
    )


def main() -> None:
    main_for("Design video-to-analysis promotion review.", run_video_to_analysis_promotion_review_design)


if __name__ == "__main__":
    main()
