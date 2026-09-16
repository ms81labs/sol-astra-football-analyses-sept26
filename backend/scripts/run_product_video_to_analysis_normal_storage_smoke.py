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
from backend.scripts.run_product_video_to_analysis_smoke import run_product_video_to_analysis_smoke  # noqa: E402

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_finish_line_normal_storage_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "product_video_to_analysis_normal_storage_smoke_v1"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_finish_line_normal_storage_execution_approval_missing"
BLOCKER_PRODUCT_SMOKE_FAILED = "product_video_to_analysis_normal_storage_smoke_failed"
NEXT_APPROVAL = "video_to_analysis_finish_line_normal_storage_execution_approval"
NEXT_PRODUCT_REPAIR = "product_video_to_analysis_smoke_repair"
NEXT_CLOSEOUT = "video_to_analysis_finish_line_normal_storage_closeout"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "controlled_normal_storage_product_smoke",
                "successCriteria": [
                    "normal product API upload/export smoke passes",
                    "existing video bundle smoke passes when ready video evidence exists",
                    "detector evaluation, downloads, training, promotion, candidate readiness, and runtime-default mutation remain blocked",
                ],
                "failureAdaptation": "If approval truth is missing, route back to normal-storage execution approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "normal_storage_product_smoke_repair",
                "successCriteria": ["repair only product smoke route/export plumbing"],
                "failureAdaptation": "If product smoke remains failing, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "normal_storage_product_smoke_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to approval, product smoke repair, or normal-storage closeout.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("normalStorageExecutionApproved") is True
        and summary.get("approvedExecutionMode") == "controlled_product_video_to_analysis_normal_storage_smoke"
        and summary.get("normalMatchStorageMutationApproved") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(scope, dict)
        and scope.get("normalStorageExecutionApproved") is True
        and scope.get("normalMatchStorageMutationAllowed") is True
        and scope.get("allowedRunner") == "backend/scripts/run_product_video_to_analysis_smoke.py"
        and scope.get("trainingAllowed") is False
        and scope.get("promotionAllowed") is False
        and scope.get("runtimeDefaultMutationAllowed") is False
    )


def _blocked_flags(*, normal_storage_mutated: bool) -> dict[str, bool]:
    return {
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "normalMatchStorageMutationExecuted": normal_storage_mutated,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "trainingExecuted": False,
        "trainingAllowed": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def run_product_video_to_analysis_normal_storage_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    approval_summary = load_json(approval_root / "finish_line_normal_storage_execution_approval_summary.json")
    approval_scope = load_json(approval_root / "approved_normal_storage_execution_scope.json")
    ready = _approval_ready(approval_summary, approval_scope)

    nested_summary: dict[str, Any] | None = None
    if ready:
        nested_summary = run_product_video_to_analysis_smoke(storage_root=Path(storage_root))

    product_smoke_passed = bool(
        isinstance(nested_summary, dict)
        and nested_summary.get("goalAchieved") is True
        and nested_summary.get("primaryBlocker") is None
        and nested_summary.get("apiUploadJobSmokePassed") is True
        and nested_summary.get("existingVideoBundleSmokePassed") is True
    )

    if not ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        goal = False
        english = "Normal-storage execution approval is missing or unsafe; approve before running the normal-storage smoke."
        normal_storage_mutated = False
    elif not product_smoke_passed:
        primary_blocker = BLOCKER_PRODUCT_SMOKE_FAILED
        next_lever = NEXT_PRODUCT_REPAIR
        goal = False
        english = "Controlled normal-storage product smoke failed; repair product smoke route/export plumbing."
        normal_storage_mutated = True
    else:
        primary_blocker = None
        next_lever = NEXT_CLOSEOUT
        goal = True
        english = "Controlled normal-storage product smoke passed. Close out normal-storage finish-line execution next."
        normal_storage_mutated = True

    execution_audit = {
        "schemaVersion": "product_video_to_analysis_normal_storage_execution_audit_v1",
        "generatedAt": utc_now_iso(),
        "approvalReady": ready,
        "normalStorageProductSmokePassed": product_smoke_passed,
        "apiUploadJobSmokePassed": bool(nested_summary and nested_summary.get("apiUploadJobSmokePassed") is True),
        "existingVideoBundleSmokePassed": bool(nested_summary and nested_summary.get("existingVideoBundleSmokePassed") is True),
        "normalMatchStorageMutationExecuted": normal_storage_mutated,
        "nestedOutputRoot": str(Path(storage_root) / "benchmark_suites" / "frozen-viable-baseline-slice-suite" / "product_video_to_analysis_smoke_v1") if nested_summary else None,
    }
    summary = {
        "batchName": "product_video_to_analysis_normal_storage_smoke",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "normalStorageProductSmokePassed": goal,
        "apiUploadJobSmokePassed": execution_audit["apiUploadJobSmokePassed"],
        "existingVideoBundleSmokePassed": execution_audit["existingVideoBundleSmokePassed"],
        **_blocked_flags(normal_storage_mutated=normal_storage_mutated),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "normal_storage_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "product_smoke_failed", "selected": primary_blocker == BLOCKER_PRODUCT_SMOKE_FAILED, "primaryBlocker": BLOCKER_PRODUCT_SMOKE_FAILED, "nextRecommendedNextLever": NEXT_PRODUCT_REPAIR},
            {"condition": "normal_storage_smoke_passed", "selected": goal, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_CLOSEOUT},
        ],
    }
    artifacts: dict[str, dict[str, Any]] = {
        "normal_storage_execution_audit.json": execution_audit,
        "decision_matrix.json": decision_matrix,
        "failsafe_attempt_plan.json": _attempt_plan(),
    }
    if isinstance(nested_summary, dict):
        artifacts["normal_storage_product_smoke_summary.json"] = nested_summary
    return write_outcome(
        output_root=output_root,
        summary_filename="product_video_to_analysis_normal_storage_smoke_summary.json",
        summary=summary,
        artifacts=artifacts,
        markdown_title="Product Video To Analysis Normal Storage Smoke",
    )


def main() -> None:
    main_for("Run controlled normal-storage product video-to-analysis smoke.", run_product_video_to_analysis_normal_storage_smoke)


if __name__ == "__main__":
    main()
