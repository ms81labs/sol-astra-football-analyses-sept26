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

DEFAULT_DESIGN_DIR_NAME = "video_to_analysis_promotion_review_design_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_promotion_review_execution_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"

BLOCKER_DESIGN_MISSING = "video_to_analysis_promotion_review_design_missing"
BLOCKER_EVIDENCE_GAP = "video_to_analysis_promotion_review_evidence_gap"
NEXT_DESIGN = "video_to_analysis_promotion_review_design"
NEXT_EVIDENCE_REPAIR = "video_to_analysis_promotion_review_evidence_repair"
NEXT_REPORT_BINDING = "video_to_analysis_promotion_review_report_binding"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "promotion_review_execution",
                "successCriteria": ["verify existing promotion readiness and runtime rollout evidence without mutation"],
                "failureAdaptation": "If design truth is missing, route back to promotion review design.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "promotion_review_evidence_repair",
                "successCriteria": ["repair only generated-truth evidence references"],
                "failureAdaptation": "If evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "promotion_review_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to design, evidence repair, or report binding.",
            },
        ],
    }


def _design_ready(summary: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("promotionReviewDesignReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("executionMode") == "non_mutating_existing_evidence_review"
        and contract.get("allowedToMutatePromotion") is False
        and contract.get("allowedToMutateRuntimeDefault") is False
    )


def run_video_to_analysis_promotion_review_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    root = candidate_root(storage_root, candidate_name)
    output_root = reset_output(root, output_dir_name)
    design_root = root / DEFAULT_DESIGN_DIR_NAME
    design_summary = load_json(design_root / "promotion_review_design_summary.json")
    execution_contract = load_json(design_root / "promotion_review_execution_contract.json")
    readiness = load_json(root / "v7_2_promotion_readiness_validation_v1" / "v7_2_promotion_readiness_summary.json")
    rollout = load_json(
        _suite_root(storage_root) / "v7_2_runtime_default_rollout_closeout_v1" / "runtime_default_rollout_closeout_summary.json"
    )
    registry = load_json(storage_root / "runtime" / "promoted_touchline_detector_candidate.json")
    design_ready = _design_ready(design_summary, execution_contract)

    registry_matches = bool(
        isinstance(registry, dict)
        and registry.get("trainingCandidateName") == "touchline_detector_candidate_v7"
        and registry.get("trainingCandidateVersion") == "v7.2"
        and registry.get("runtimeUse") == "default_runtime"
        and registry.get("promotionValidated") is True
        and registry.get("candidateReadyForEvaluation") is True
        and registry.get("runtimeDefaultMutationExecuted") is True
    )
    readiness_passed = bool(
        isinstance(readiness, dict)
        and readiness.get("goalAchieved") is True
        and readiness.get("promotionValidated") is True
        and readiness.get("promotionReady") is True
        and readiness.get("candidateReadyForEvaluation") is True
    )
    rollout_passed = bool(
        isinstance(rollout, dict)
        and rollout.get("goalAchieved") is True
        and rollout.get("runtimeDefaultRolloutClosed") is True
        and rollout.get("postRuntimeDefaultSourceRobustnessValidated") is True
        and rollout.get("activeFailingSourceNotViableBlockerPresent") is False
    )
    review_passed = bool(design_ready and registry_matches and readiness_passed and rollout_passed)

    if not design_ready:
        primary_blocker = BLOCKER_DESIGN_MISSING
        next_lever = NEXT_DESIGN
        goal = False
        english = "Promotion review design is missing or unsafe; design review before execution."
    elif not review_passed:
        primary_blocker = BLOCKER_EVIDENCE_GAP
        next_lever = NEXT_EVIDENCE_REPAIR
        goal = False
        english = "Promotion review evidence is incomplete or inconsistent; repair evidence references before report binding."
    else:
        primary_blocker = None
        next_lever = NEXT_REPORT_BINDING
        goal = True
        english = "Promotion review passed from existing v7.2 promotion and runtime rollout evidence. Bind the report next."

    audit = {
        "schemaVersion": "video_to_analysis_promotion_review_execution_audit_v1",
        "generatedAt": utc_now_iso(),
        "registryMatchesV7_2DefaultRuntime": registry_matches,
        "promotionReadinessPassed": readiness_passed,
        "runtimeDefaultRolloutClosed": rollout_passed,
        "postRuntimeDefaultSourceRobustnessValidated": bool(isinstance(rollout, dict) and rollout.get("postRuntimeDefaultSourceRobustnessValidated") is True),
        "activeFailingSourceNotViableBlockerPresent": rollout.get("activeFailingSourceNotViableBlockerPresent") if isinstance(rollout, dict) else None,
        "reviewMutations": {
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    }
    summary = {
        "batchName": "video_to_analysis_promotion_review_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "promotionReviewExecuted": design_ready,
        "promotionReviewPassed": review_passed,
        "registryMatchesV7_2DefaultRuntime": registry_matches,
        "postRuntimeDefaultSourceRobustnessValidated": audit["postRuntimeDefaultSourceRobustnessValidated"],
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="promotion_review_execution_summary.json",
        summary=summary,
        artifacts={
            "promotion_review_execution_audit.json": audit,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Promotion Review Execution",
    )


def main() -> None:
    main_for("Execute video-to-analysis promotion review.", run_video_to_analysis_promotion_review_execution)


if __name__ == "__main__":
    main()
