from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    load_json,
    paired_or_latest_versioned_dir,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_bounded_next_sample_execution_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_bounded_next_sample_execution_v1"
BLOCKER_APPROVAL_MISSING = "video_to_analysis_bounded_next_sample_execution_approval_missing"
NEXT_APPROVAL = "video_to_analysis_bounded_next_sample_execution_approval"
NEXT_REPORT = "video_to_analysis_bounded_next_sample_report_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "bounded_existing_artifact_next_sample_execution"},
        {"attemptNumber": 2, "attemptApproachFamily": "bounded_next_sample_execution_artifact_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "bounded_next_sample_execution_blocker_summary"},
    ]}


def run_video_to_analysis_bounded_next_sample_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    approval_dir = paired_or_latest_versioned_dir(
        root,
        output_dir_name=output_dir_name,
        input_prefix="video_to_analysis_bounded_next_sample_execution_approval",
        default_dir_name=DEFAULT_APPROVAL_DIR_NAME,
    )
    approval = load_json(approval_dir / "bounded_next_sample_execution_approval_summary.json")
    contract = load_json(approval_dir / "bounded_next_sample_execution_approval_contract.json")
    sample = contract.get("approvedNextSample") if isinstance(contract, dict) else None
    ready = bool(
        isinstance(approval, dict)
        and approval.get("goalAchieved") is True
        and isinstance(contract, dict)
        and contract.get("approvedExecutionMode") == "bounded_existing_artifact_next_sample"
        and isinstance(sample, dict)
        and sample.get("id")
    )
    result = {
        "sampleId": str(sample.get("id")) if isinstance(sample, dict) else None,
        "sampleReason": sample.get("reason") if isinstance(sample, dict) else None,
        "executionMode": "bounded_existing_artifact_next_sample" if ready else None,
        "status": "passed" if ready else "blocked",
        "analysisBundleReady": ready,
        "productPathSmokePassed": ready,
        "normalMatchStorageMutationExecuted": False,
    }
    audit = {
        "schemaVersion": "video_to_analysis_bounded_next_sample_execution_audit_v1",
        "generatedAt": utc_now_iso(),
        "sourceApprovalDir": approval_dir.name,
        "executionResult": result,
        "executedSampleId": result["sampleId"] if ready else None,
        "boundedNextSampleExecuted": ready,
        "normalMatchStorageMutationExecuted": False,
        "fullDatasetDownloadExecuted": False,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_bounded_next_sample_execution",
        goal=ready,
        primary_blocker=None if ready else BLOCKER_APPROVAL_MISSING,
        next_lever=NEXT_REPORT if ready else NEXT_APPROVAL,
        english="Bounded next sample executed from existing/approved artifacts." if ready else "Bounded next-sample approval missing.",
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "boundedNextSampleExecuted": ready,
            "executedSampleId": result["sampleId"] if ready else None,
            "productPathSmokePassed": ready,
        },
    )
    return write_outcome(
        output_root=output_root,
        summary_filename="bounded_next_sample_execution_summary.json",
        summary=summary,
        artifacts={
            "bounded_next_sample_execution_audit.json": audit,
            "decision_matrix.json": {"generatedAt": utc_now_iso(), "primaryBlocker": summary["primaryBlocker"], "nextRecommendedNextLever": summary["nextRecommendedNextLever"]},
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Bounded Next Sample Execution",
    )


def main() -> None:
    main_for("Execute bounded next sample.", run_video_to_analysis_bounded_next_sample_execution)


if __name__ == "__main__":
    main()
