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

DEFAULT_APPROVAL_DIR_NAME = "video_to_analysis_detector_evaluation_reentry_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution_v1"

BLOCKER_APPROVAL_MISSING = "video_to_analysis_detector_evaluation_reentry_approval_missing"
BLOCKER_ARTIFACT_MISSING = "video_to_analysis_detector_evaluation_existing_artifact_missing"
NEXT_APPROVAL = "video_to_analysis_detector_evaluation_reentry_approval"
NEXT_REPORT_BINDING = "video_to_analysis_detector_evaluation_report_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "bounded_existing_artifact_detector_evaluation_execution",
                "successCriteria": [
                    "aggregate v7.2 bounded, guardrail, and pipeline truth",
                    "execute no new training, downloads, promotion, or runtime mutation",
                ],
                "failureAdaptation": "If approval is missing, route back to approval.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "existing_artifact_inventory_repair",
                "successCriteria": ["repair only generated-truth artifact references"],
                "failureAdaptation": "If required v7.2 artifacts remain missing, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "bounded_detector_evaluation_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to approval, inventory repair, or report binding.",
            },
        ],
    }


def _approval_ready(summary: dict[str, Any] | None, scope: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("detectorEvaluationApproved") is True
        and summary.get("approvedExecutionMode") == "bounded_existing_v7_2_artifact_detector_evaluation"
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and isinstance(scope, dict)
        and scope.get("detectorEvaluationApproved") is True
        and scope.get("runtimeDefaultRolloutClosed") is True
        and scope.get("activeRuntimeDefaultVersion") == "v7.3"
    )


def _artifacts(root: Path) -> dict[str, dict[str, Any] | None]:
    return {
        "boundedRetrain": load_json(root / "v7_2_bounded_retrain_v1" / "v7_2_bounded_retrain_summary.json"),
        "cropGuardrail": load_json(
            root / "v7_2_crop_probe_precision_guardrail_audit_v1" / "v7_2_crop_probe_precision_guardrail_summary.json"
        ),
        "fullPipeline": load_json(root / "v7_2_full_pipeline_non_promotion_eval_v1" / "v7_2_full_pipeline_non_promotion_summary.json"),
    }


def _artifacts_ready(artifacts: dict[str, dict[str, Any] | None]) -> bool:
    bounded = artifacts.get("boundedRetrain")
    guardrail = artifacts.get("cropGuardrail")
    pipeline = artifacts.get("fullPipeline")
    return bool(
        isinstance(bounded, dict)
        and bounded.get("goalAchieved") is True
        and bounded.get("primaryBlocker") is None
        and bounded.get("boundedValPositiveLocalizationHitRate") is not None
        and isinstance(guardrail, dict)
        and guardrail.get("goalAchieved") is True
        and guardrail.get("primaryBlocker") is None
        and guardrail.get("precisionGuardrailPassed") is True
        and isinstance(pipeline, dict)
        and pipeline.get("goalAchieved") is True
        and pipeline.get("primaryBlocker") is None
        and pipeline.get("sourceFrameLocalizationHitRate") is not None
    )


def run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    approval_root = root / DEFAULT_APPROVAL_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    approval_summary = load_json(approval_root / "detector_evaluation_reentry_approval_summary.json")
    approved_scope = load_json(approval_root / "approved_detector_evaluation_scope.json")
    approval_ready = _approval_ready(approval_summary, approved_scope)
    artifacts = _artifacts(root)
    artifacts_ready = _artifacts_ready(artifacts)

    if not approval_ready:
        primary_blocker = BLOCKER_APPROVAL_MISSING
        next_lever = NEXT_APPROVAL
        goal = False
        detector_executed = False
        english = "Detector-evaluation approval is missing or unsafe; approve bounded scope before execution."
    elif not artifacts_ready:
        primary_blocker = BLOCKER_ARTIFACT_MISSING
        next_lever = "video_to_analysis_detector_evaluation_existing_artifact_inventory_repair"
        goal = False
        detector_executed = False
        english = "Required existing v7.2 detector artifacts are missing; repair artifact inventory before report binding."
    else:
        primary_blocker = None
        next_lever = NEXT_REPORT_BINDING
        goal = True
        detector_executed = True
        english = "Bounded existing-artifact detector evaluation executed. Bind the detector evaluation report next."

    bounded = artifacts.get("boundedRetrain") if isinstance(artifacts.get("boundedRetrain"), dict) else {}
    guardrail = artifacts.get("cropGuardrail") if isinstance(artifacts.get("cropGuardrail"), dict) else {}
    pipeline = artifacts.get("fullPipeline") if isinstance(artifacts.get("fullPipeline"), dict) else {}
    metric_snapshot = {
        "schemaVersion": "video_to_analysis_detector_evaluation_metric_snapshot_v1",
        "generatedAt": utc_now_iso(),
        "boundedValPositiveLocalizationHitRate": bounded.get("boundedValPositiveLocalizationHitRate"),
        "precisionGuardrailPassed": guardrail.get("precisionGuardrailPassed"),
        "sourceFrameLocalizationHitRate": pipeline.get("sourceFrameLocalizationHitRate"),
        "boundedRetrainNextLever": bounded.get("nextRecommendedNextLever"),
        "guardrailNextLever": guardrail.get("nextRecommendedNextLever"),
        "pipelineNextLever": pipeline.get("nextRecommendedNextLever"),
    }
    inventory = {
        "schemaVersion": "video_to_analysis_detector_evaluation_source_artifact_inventory_v1",
        "generatedAt": utc_now_iso(),
        "artifactsReady": artifacts_ready,
        "sourceArtifacts": {
            name: {"present": isinstance(payload, dict), "goalAchieved": payload.get("goalAchieved") if isinstance(payload, dict) else None}
            for name, payload in artifacts.items()
        },
    }
    false_flags = standard_false_flags()
    false_flags["detectorEvaluationExecuted"] = detector_executed
    false_flags["runtimeDefaultMutationExecuted"] = goal
    summary = {
        "batchName": "video_to_analysis_detector_evaluation_bounded_existing_artifact_execution",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "boundedValPositiveLocalizationHitRate": metric_snapshot["boundedValPositiveLocalizationHitRate"],
        "sourceFrameLocalizationHitRate": metric_snapshot["sourceFrameLocalizationHitRate"],
        "precisionGuardrailPassed": metric_snapshot["precisionGuardrailPassed"],
        **false_flags,
        "runtimeDefaultRolloutClosed": goal,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="detector_evaluation_bounded_existing_artifact_execution_summary.json",
        summary=summary,
        artifacts={
            "detector_evaluation_metric_snapshot.json": metric_snapshot,
            "detector_evaluation_source_artifact_inventory.json": inventory,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": primary_blocker,
                "nextRecommendedNextLever": next_lever,
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Detector Evaluation Bounded Existing Artifact Execution",
    )


def main() -> None:
    main_for(
        "Execute bounded existing-artifact video-to-analysis detector evaluation.",
        run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution,
    )


if __name__ == "__main__":
    main()
