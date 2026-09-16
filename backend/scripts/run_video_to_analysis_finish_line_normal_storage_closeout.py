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
    utc_now_iso,
    write_outcome,
)

DEFAULT_SMOKE_DIR_NAME = "product_video_to_analysis_normal_storage_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_normal_storage_closeout_v1"

BLOCKER_SMOKE_MISSING = "product_video_to_analysis_normal_storage_smoke_missing"
BLOCKER_CLOSEOUT_GAP = "video_to_analysis_finish_line_normal_storage_closeout_gap"
NEXT_SMOKE = "product_video_to_analysis_normal_storage_smoke"
NEXT_CLOSEOUT_REPAIR = "video_to_analysis_finish_line_normal_storage_closeout_repair"
NEXT_OPERATIONAL_READINESS = "video_to_analysis_finish_line_operational_readiness"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "normal_storage_closeout",
                "successCriteria": [
                    "normal-storage product smoke passed after explicit approval",
                    "API upload/export and existing video bundle smoke passed",
                    "no detector evaluation, downloads, training, promotion, candidate readiness, or runtime-default mutation occurred",
                ],
                "failureAdaptation": "If normal-storage smoke truth is missing, route back to controlled normal-storage smoke.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "normal_storage_closeout_evidence_repair",
                "successCriteria": ["repair only closeout evidence inventory"],
                "failureAdaptation": "If closeout evidence remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "normal_storage_closeout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to smoke, closeout repair, or operational readiness.",
            },
        ],
    }


def _smoke_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("normalStorageProductSmokePassed") is True
        and summary.get("apiUploadJobSmokePassed") is True
        and summary.get("existingVideoBundleSmokePassed") is True
        and summary.get("normalMatchStorageMutationExecuted") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("approvalReady") is True
        and audit.get("normalStorageProductSmokePassed") is True
        and audit.get("apiUploadJobSmokePassed") is True
        and audit.get("existingVideoBundleSmokePassed") is True
        and audit.get("normalMatchStorageMutationExecuted") is True
    )


def run_video_to_analysis_finish_line_normal_storage_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    smoke_root = root / DEFAULT_SMOKE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    smoke_summary = load_json(smoke_root / "product_video_to_analysis_normal_storage_smoke_summary.json")
    smoke_audit = load_json(smoke_root / "normal_storage_execution_audit.json")
    ready = _smoke_ready(smoke_summary, smoke_audit)

    capability_matrix = {
        "schemaVersion": "video_to_analysis_finish_line_normal_storage_closeout_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "normalStorageProductSmokePassed": ready,
        "apiUploadJobSmokePassed": bool(smoke_summary and smoke_summary.get("apiUploadJobSmokePassed") is True),
        "existingVideoBundleSmokePassed": bool(smoke_summary and smoke_summary.get("existingVideoBundleSmokePassed") is True),
        "normalMatchStorageMutationExecuted": bool(smoke_summary and smoke_summary.get("normalMatchStorageMutationExecuted") is True),
        "operationalReadinessReady": ready,
        "detectorEvaluationExecuted": False,
        "dataDownloadExecuted": False,
        "videoDownloadExecuted": False,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
    }
    remaining_gap_analysis = {
        "schemaVersion": "video_to_analysis_finish_line_normal_storage_remaining_gap_analysis_v1",
        "generatedAt": utc_now_iso(),
        "remainingTechnicalBlocker": None if ready else (BLOCKER_SMOKE_MISSING if smoke_summary is None else BLOCKER_CLOSEOUT_GAP),
        "nextOperationalAction": "prepare finish-line operational readiness and runbook" if ready else None,
        "nonGoalsStillBlocked": [
            "detector_evaluation",
            "training",
            "promotion",
            "candidate_evaluation_readiness",
            "runtime_default_mutation",
        ],
    }
    if smoke_summary is None:
        primary_blocker = BLOCKER_SMOKE_MISSING
        next_lever = NEXT_SMOKE
        goal = False
        english = "Normal-storage product smoke truth is missing; run controlled normal-storage smoke first."
    elif not ready:
        primary_blocker = BLOCKER_CLOSEOUT_GAP
        next_lever = NEXT_CLOSEOUT_REPAIR
        goal = False
        english = "Normal-storage product smoke evidence is incomplete; repair closeout evidence."
    else:
        primary_blocker = None
        next_lever = NEXT_OPERATIONAL_READINESS
        goal = True
        english = "Normal-storage finish-line execution is closed. Prepare operational readiness next."

    summary = {
        "batchName": "video_to_analysis_finish_line_normal_storage_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "normalStorageCloseoutPassed": goal,
        "normalStorageProductSmokePassed": ready,
        "apiUploadJobSmokePassed": capability_matrix["apiUploadJobSmokePassed"],
        "existingVideoBundleSmokePassed": capability_matrix["existingVideoBundleSmokePassed"],
        "normalMatchStorageMutationExecuted": capability_matrix["normalMatchStorageMutationExecuted"],
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "trainingExecuted": False,
        "trainingAllowed": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "normal_storage_smoke_missing", "selected": primary_blocker == BLOCKER_SMOKE_MISSING, "primaryBlocker": BLOCKER_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_SMOKE},
            {"condition": "normal_storage_closeout_gap", "selected": primary_blocker == BLOCKER_CLOSEOUT_GAP, "primaryBlocker": BLOCKER_CLOSEOUT_GAP, "nextRecommendedNextLever": NEXT_CLOSEOUT_REPAIR},
            {"condition": "normal_storage_closeout_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_OPERATIONAL_READINESS},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_normal_storage_closeout_summary.json",
        summary=summary,
        artifacts={
            "normal_storage_closeout_capability_matrix.json": capability_matrix,
            "normal_storage_remaining_gap_analysis.json": remaining_gap_analysis,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Normal Storage Closeout",
    )


def main() -> None:
    main_for("Close out finish-line normal-storage execution.", run_video_to_analysis_finish_line_normal_storage_closeout)


if __name__ == "__main__":
    main()
