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

DEFAULT_SMOKE_DIR_NAME = "product_video_to_analysis_smoke_isolated_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_finish_line_closeout_v1"

BLOCKER_SMOKE_MISSING = "video_to_analysis_finish_line_product_smoke_missing"
NEXT_PRODUCT_SMOKE = "product_video_to_analysis_smoke"
NEXT_PRODUCT_BINDING = "video_to_analysis_finish_line_product_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": "video_to_analysis_finish_line_closeout", "successCriteria": ["summarize isolated product smoke evidence"], "failureAdaptation": "If smoke is missing, route back to product smoke."},
            {"attemptNumber": 2, "attemptApproachFamily": "video_to_analysis_finish_line_closeout_contract_repair", "successCriteria": ["repair closeout evidence mapping only"], "failureAdaptation": "If evidence remains incomplete, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": "video_to_analysis_finish_line_closeout_blocker_summary", "successCriteria": ["write blocker truth"], "failureAdaptation": "Route to product smoke, closeout repair, or product binding."},
        ],
    }


def _smoke_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productVideoToAnalysisSmokePassed") is True
        and summary.get("apiUploadJobSmokePassed") is True
        and summary.get("existingVideoBundleSmokePassed") is True
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("isolatedBenchmarkStorageMutationExecuted") is True
        and isinstance(audit, dict)
        and audit.get("normalStorageRootUsedForSmoke") is False
    )


def run_video_to_analysis_finish_line_closeout(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    smoke_root = root / DEFAULT_SMOKE_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    smoke_summary = load_json(smoke_root / "product_video_to_analysis_smoke_summary.json")
    isolated_audit = load_json(smoke_root / "isolated_storage_audit.json")
    ready = _smoke_ready(smoke_summary, isolated_audit)
    primary_blocker = None if ready else BLOCKER_SMOKE_MISSING
    next_lever = NEXT_PRODUCT_BINDING if ready else NEXT_PRODUCT_SMOKE
    evidence_inventory = {
        "schemaVersion": "video_to_analysis_finish_line_evidence_inventory_v1",
        "generatedAt": utc_now_iso(),
        "productSmokeSummaryPath": str(smoke_root / "product_video_to_analysis_smoke_summary.json"),
        "isolatedStorageAuditPath": str(smoke_root / "isolated_storage_audit.json"),
        "nestedSmokeSummaryPath": (isolated_audit or {}).get("nestedSmokeSummaryPath"),
        "evidenceComplete": ready,
    }
    capability_matrix = {
        "schemaVersion": "video_to_analysis_finish_line_capability_matrix_v1",
        "generatedAt": utc_now_iso(),
        "capabilities": [
            {"capabilityId": "api_upload_to_exports", "status": "passed" if ready else "blocked"},
            {"capabilityId": "ready_video_bundle_export", "status": "passed" if ready else "blocked"},
            {"capabilityId": "normal_storage_preserved", "status": "passed" if ready else "blocked"},
            {"capabilityId": "product_surface_binding", "status": "next" if ready else "blocked"},
        ],
    }
    summary = {
        "batchName": "video_to_analysis_finish_line_closeout",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "finishLineClosed": ready,
        "productVideoToAnalysisSmokePassed": bool((smoke_summary or {}).get("productVideoToAnalysisSmokePassed")),
        "apiUploadJobSmokePassed": bool((smoke_summary or {}).get("apiUploadJobSmokePassed")),
        "existingVideoBundleSmokePassed": bool((smoke_summary or {}).get("existingVideoBundleSmokePassed")),
        "normalMatchStorageMutationExecuted": False,
        "isolatedBenchmarkStorageMutationExecuted": bool((smoke_summary or {}).get("isolatedBenchmarkStorageMutationExecuted")),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": "Finish-line smoke evidence is closed. Bind it to a product-facing finish-line surface next." if ready else "Isolated product video-to-analysis smoke evidence is missing; rerun the smoke first.",
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "product_smoke_missing", "selected": primary_blocker == BLOCKER_SMOKE_MISSING, "primaryBlocker": BLOCKER_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_SMOKE},
            {"condition": "finish_line_closeout_ready", "selected": ready, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_BINDING},
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="finish_line_closeout_summary.json",
        summary=summary,
        artifacts={
            "finish_line_evidence_inventory.json": evidence_inventory,
            "finish_line_capability_matrix.json": capability_matrix,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Finish Line Closeout",
    )


def main() -> None:
    main_for("Close out isolated product video-to-analysis smoke evidence.", run_video_to_analysis_finish_line_closeout)


if __name__ == "__main__":
    main()
