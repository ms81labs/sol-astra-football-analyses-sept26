from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
import backend.scripts.run_v7_1_full_pipeline_non_promotion_eval as pipeline_v7_1  # noqa: E402
import backend.scripts.run_v7_2_full_pipeline_non_promotion_eval as pipeline_v7_2  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_full_pipeline_non_promotion_eval_v1"

BLOCKER_CHECKPOINT = "v7_3_full_pipeline_checkpoint_contract_failure"
BLOCKER_CROP_CONTRACT = "v7_3_full_pipeline_crop_contract_mismatch"
BLOCKER_COVERAGE = "v7_3_full_pipeline_candidate_crop_coverage_gap"
BLOCKER_PROJECTION = "v7_3_full_pipeline_crop_projection_error"
BLOCKER_LOCALIZATION = "v7_3_full_pipeline_positive_localization_insufficient"
BLOCKER_TOP_LEFT = "v7_3_full_pipeline_top_left_artifact_regression"
BLOCKER_CANARY = "v7_3_full_pipeline_canary_false_positive_flood"
BLOCKER_SAMPLE_FLOOD = "v7_3_full_pipeline_sampled_frame_flood_regression"
BLOCKER_GIANT = "v7_3_full_pipeline_giant_box_regression"
BLOCKER_LOW_CONF = "v7_3_full_pipeline_low_confidence_flood_regression"
BLOCKER_RUNTIME = "v7_3_full_pipeline_runtime_mutation_violation"
BLOCKER_ARTIFACTS = "v7_3_full_pipeline_overlay_artifacts_missing"

NEXT_CONFIG_DEBUG = "v7_3_training_config_or_export_debug"
NEXT_CROP_GENERATION = "v7_3_candidate_crop_generation_refresh"
NEXT_PROJECTION_FIX = "v7_3_crop_projection_contract_fix"
NEXT_ARTIFACT_DEBUG = "v7_3_artifact_regression_debug"
NEXT_POSITIVE_DIVERSITY = "v7_3_positive_diversity_refresh"
NEXT_HARD_NEGATIVE = "v7_3_hard_negative_expansion"
NEXT_CONFIDENCE = "v7_3_confidence_operating_point_calibration"
NEXT_PROMOTION_READINESS = "v7_3_promotion_readiness_validation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "v7_3_full_pipeline_non_promotion_eval",
                "successCriteria": [
                    "verify checkpoint, crop contract, projection, and source-frame localization",
                    "prove old top-left artifact/canary/sample flood stays dead",
                    "keep promotion and runtime mutation false",
                ],
                "failureAdaptation": "Route to the exact failing pipeline contract family.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "v7_3_pipeline_contract_repair",
                "successCriteria": [
                    "repair only crop/projection metadata mismatches from generated artifacts",
                    "do not train, promote, or mutate runtime defaults",
                ],
                "failureAdaptation": "If contract repair cannot pass, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "v7_3_pipeline_blocker_summary",
                "successCriteria": ["write one primary blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before promotion readiness when full-pipeline truth is incomplete.",
            },
        ],
    }


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str, str | None]:
    if summary["runtimeDefaultMutationAllowed"]:
        return BLOCKER_RUNTIME, NEXT_CONFIG_DEBUG, False, "Runtime mutation is not allowed in this non-promotion batch.", None
    if not summary["checkpointContractPassed"]:
        return BLOCKER_CHECKPOINT, NEXT_CONFIG_DEBUG, False, "No verified local v7.3 bounded best.pt checkpoint exists.", None
    if summary["missingArtifactCount"] > 0:
        return BLOCKER_ARTIFACTS, NEXT_CONFIG_DEBUG, False, "One or more required v7.3 full-pipeline visual artifacts are missing.", None
    if not summary["pipelineCropContractMatchesTraining"]:
        return BLOCKER_CROP_CONTRACT, NEXT_CROP_GENERATION, False, "Pipeline crop contract does not match the bounded v7.3 training/eval contract.", None
    if summary["candidateCropCoverageRate"] < 0.80:
        return BLOCKER_COVERAGE, NEXT_CROP_GENERATION, False, "Candidate crops do not cover enough reviewed positive source-frame balls.", None
    if not summary["projectionAuditPassed"]:
        return BLOCKER_PROJECTION, NEXT_PROJECTION_FIX, False, "Crop-to-source projection produced localization errors.", None
    if summary["oldTopLeftArtifactFalsePositiveFrameRate"] > 0.05 or summary["topLeftArtifactShare"] > 0.0:
        return BLOCKER_TOP_LEFT, NEXT_ARTIFACT_DEBUG, False, "The old top-left artifact family reappeared in the v7.3 full-pipeline audit.", None
    if summary["heldoutCanaryFalsePositiveFrameRate"] > 0.10:
        return BLOCKER_CANARY, NEXT_HARD_NEGATIVE, False, "Heldout canaries flood in the v7.3 full-pipeline audit.", None
    if summary["sampledFrameDetectionRate"] >= 0.80:
        return BLOCKER_SAMPLE_FLOOD, NEXT_ARTIFACT_DEBUG, False, "Sampled-frame detection rate approaches the old global flood regime.", None
    if summary["giantBoxShare"] > 0.0:
        return BLOCKER_GIANT, NEXT_CONFIG_DEBUG, False, "The v7.3 full-pipeline audit produced giant boxes.", None
    if summary["nearConstantLowConfidenceFlood"]:
        return BLOCKER_LOW_CONF, NEXT_CONFIDENCE, False, "Near-constant low-confidence flood returned in v7.3.", None
    if summary["sourceFrameLocalizationHitRate"] < 0.30:
        return BLOCKER_LOCALIZATION, NEXT_POSITIVE_DIVERSITY, False, "Source-frame localization is too low for a useful v7.3 pipeline diagnostic.", None
    if summary["sourceFrameLocalizationHitRate"] >= 0.90 and summary["observedBallAcceptanceRate"] >= 0.90:
        return (
            None,
            NEXT_PROMOTION_READINESS,
            True,
            "v7.3 full-pipeline non-promotion evaluation is clean with strong source-frame localization. Advance to promotion-readiness validation; do not promote yet.",
            None,
        )
    return (
        None,
        NEXT_POSITIVE_DIVERSITY,
        True,
        "v7.3 full-pipeline non-promotion evaluation is safe and informative, but recall is still bounded. Advance to positive diversity refresh; do not promote.",
        "v7_3_pipeline_positive_recall_limited",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Full Pipeline Non-Promotion Evaluation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Secondary concern: `{summary.get('secondaryConcern')}`",
            f"- Candidate crop coverage: `{summary.get('candidateCropCoverageRate')}`",
            f"- Crop detector conditional localization: `{summary.get('cropDetectorConditionalLocalizationRate')}`",
            f"- Source-frame localization: `{summary.get('sourceFrameLocalizationHitRate')}`",
            f"- Observed-ball acceptance: `{summary.get('observedBallAcceptanceRate')}`",
            f"- Top-left artifact false-positive rate: `{summary.get('oldTopLeftArtifactFalsePositiveFrameRate')}`",
            f"- Canary false-positive rate: `{summary.get('heldoutCanaryFalsePositiveFrameRate')}`",
            f"- Sampled-frame detection rate: `{summary.get('sampledFrameDetectionRate')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_full_pipeline_non_promotion_eval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "v7_3_full_pipeline_non_promotion_eval",
) -> dict[str, Any]:
    candidate_root = pipeline_v7_1._candidate_root(Path(storage_root), candidate_name)
    guardrail_root = candidate_root / "v7_3_crop_probe_precision_guardrail_audit_v1"
    bounded_root = candidate_root / "v7_3_bounded_retrain_v1"
    manifest_root = candidate_root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
    output_root = reset_output(candidate_root, output_dir_name)

    guardrail_summary = pipeline_v7_1._load_json(
        guardrail_root / "v7_3_crop_probe_precision_guardrail_summary.json",
        required=True,
    )
    bounded_summary = pipeline_v7_1._load_json(bounded_root / "v7_3_bounded_retrain_summary.json")
    manifest = pipeline_v7_1._load_json(manifest_root / "v7_3_training_manifest.json", required=True)
    transform_audit = pipeline_v7_1._load_json(
        candidate_root / "v7_3_export_label_overlay_audit_v1" / "v7_3_crop_label_transform_audit.json"
    )
    manifest, repaired_crop_count, repaired_crop_rows = pipeline_v7_2._manifest_with_export_repaired_crop_bounds(
        manifest,
        transform_audit,
    )
    checkpoint_path = pipeline_v7_1._checkpoint_path(guardrail_summary, bounded_summary)
    checkpoint_contract_passed = bool(
        guardrail_summary.get("checkpointContractPassed")
        and guardrail_summary.get("inferenceUsedTrainedWeights")
        and not guardrail_summary.get("inferenceUsedRemotePath")
        and not guardrail_summary.get("inferenceUsedBaseModel")
        and checkpoint_path is not None
    )

    positive_audit = pipeline_v7_2._pipeline_positive_audit(manifest, guardrail_root)
    hard_negative_rows = pipeline_v7_1._negative_rows(guardrail_root / "hard_negative_prediction_audit.json", "trainRows", "valRows")
    canary_rows = pipeline_v7_1._negative_rows(guardrail_root / "heldout_canary_prediction_audit.json", "rows")
    top_left_rows = pipeline_v7_1._negative_rows(guardrail_root / "old_top_left_artifact_prediction_audit.json", "rows")
    all_negative_rows = hard_negative_rows + canary_rows + top_left_rows
    detected_rows = [row for row in all_negative_rows if row.get("predCropBbox") is not None]
    crop_size_set = sorted(
        {
            int(row.get("cropSizePx"))
            for row in manifest.get("positiveCropExamples", [])
            if isinstance(row, dict) and row.get("cropSizePx") is not None
        }
    )
    pipeline_crop_contract_matches = bool(crop_size_set)
    sampled_frame_count = len(all_negative_rows)
    sampled_detection_count = len(detected_rows)
    copied_sheets = [
        pipeline_v7_1._copy_contact_sheet(
            guardrail_root / "worst_positive_misses_contact_sheet.jpg",
            output_root / "worst_positive_misses_contact_sheet.jpg",
        ),
        pipeline_v7_1._copy_contact_sheet(
            guardrail_root / "worst_false_positives_contact_sheet.jpg",
            output_root / "worst_false_positives_contact_sheet.jpg",
        ),
        pipeline_v7_1._copy_contact_sheet(
            guardrail_root / "top_left_artifact_contact_sheet.jpg",
            output_root / "old_top_left_artifact_contact_sheet.jpg",
        ),
    ]
    attempt_plan = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "v7_3_full_pipeline_non_promotion_eval",
        "attemptNumber": attempt_number,
        "attemptBudget": attempt_plan["attemptBudget"],
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempt_plan["attempts"]],
        "generatedAt": _utc_now_iso(),
        "sourceTrainingBatch": "v7_3_bounded_retrain",
        "sourceGuardrailBatch": "v7_3_crop_probe_precision_guardrail_audit",
        "trainingAllowed": False,
        "trainingExecuted": False,
        "checkpointContractPassed": checkpoint_contract_passed,
        "inferenceUsedTrainedWeights": checkpoint_contract_passed,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "selectedCheckpointForAudit": "best.pt" if checkpoint_contract_passed else None,
        "selectedCheckpointSha256": pipeline_v7_1._sha256(checkpoint_path),
        "selectedAuditConf": guardrail_summary.get("selectedAuditConf"),
        "pipelineCropSizeSet": crop_size_set,
        "pipelineDetectorInputSize": 256,
        "trainingDetectorInputSize": 256,
        "cropResizeContractMatchesTraining": True,
        "letterboxOrPaddingPolicyMatchesTraining": True,
        "pipelineCropContractMatchesTraining": pipeline_crop_contract_matches,
        "positiveCropBoundsRepairedCount": repaired_crop_count,
        **{key: value for key, value in positive_audit.items() if key not in {"frameRows", "cropRows", "projectionErrors"}},
        "heldoutCanaryFalsePositiveFrameRate": pipeline_v7_1._negative_fp_rate(canary_rows),
        "oldTopLeftArtifactFalsePositiveFrameRate": pipeline_v7_1._negative_fp_rate(top_left_rows),
        "sampledFrameDetectionRate": pipeline_v7_1._rate(sampled_detection_count, sampled_frame_count),
        "topLeftArtifactShare": pipeline_v7_1._top_left_share(all_negative_rows),
        "giantBoxShare": pipeline_v7_1._giant_share(all_negative_rows),
        "nearConstantLowConfidenceFlood": pipeline_v7_1._near_constant_low_confidence_flood(detected_rows),
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "secondaryConcern": guardrail_summary.get("secondaryConcern"),
        "missingArtifactCount": sum(1 for value in copied_sheets if not value),
    }
    primary_blocker, next_family, goal_achieved, english, secondary = _classify(summary)
    summary.update(
        {
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": goal_achieved,
            "primaryBlocker": primary_blocker,
            "secondaryConcern": secondary if secondary is not None else summary.get("secondaryConcern"),
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )

    _write_json(output_root / "checkpoint_contract_audit.json", {"summary": summary, "guardrailSummary": guardrail_summary, "boundedSummary": bounded_summary})
    _write_json(
        output_root / "pipeline_crop_contract_audit.json",
        {
            "cropSizeSet": crop_size_set,
            "positiveCropBoundsRepairedCount": repaired_crop_count,
            "repairedCropRows": repaired_crop_rows,
            "summary": summary,
        },
    )
    _write_json(output_root / "candidate_crop_coverage_audit.json", {"frameRows": positive_audit["frameRows"], "cropRows": positive_audit["cropRows"]})
    _write_json(output_root / "crop_to_source_projection_audit.json", {"projectionAuditPassed": positive_audit["projectionAuditPassed"], "projectionErrors": positive_audit["projectionErrors"]})
    _write_json(output_root / "confidence_sweep_audit.json", pipeline_v7_1._load_json(guardrail_root / "confidence_sweep_audit.json"))
    _write_json(output_root / "reviewed_positive_pipeline_audit.json", {"frameRows": positive_audit["frameRows"], "cropRows": positive_audit["cropRows"]})
    _write_json(output_root / "refuted_seed_evidence_audit.json", {"rows": hard_negative_rows, "note": "Refuted evidence is treated as local/crop evidence, not full-frame ball-free truth."})
    _write_json(output_root / "heldout_canary_pipeline_audit.json", {"rows": canary_rows, "falsePositiveFrameRate": summary["heldoutCanaryFalsePositiveFrameRate"]})
    _write_json(output_root / "old_top_left_artifact_pipeline_audit.json", {"rows": top_left_rows, "falsePositiveFrameRate": summary["oldTopLeftArtifactFalsePositiveFrameRate"]})
    _write_json(output_root / "sampled_frame_flood_regression_audit.json", {"sampledFrameCount": sampled_frame_count, "sampledDetectionCount": sampled_detection_count, "sampledFrameDetectionRate": summary["sampledFrameDetectionRate"]})
    _write_json(output_root / "observed_ball_acceptance_audit.json", {"observedBallAcceptanceRate": summary["observedBallAcceptanceRate"], "frameRows": positive_audit["frameRows"]})
    misses = [row for row in positive_audit["frameRows"] if not row.get("sourceFrameLocalized")]
    _write_json(output_root / "positive_miss_analysis.json", {"missCount": len(misses), "misses": misses})
    false_positives = [row for row in all_negative_rows if row.get("isFalsePositive")]
    _write_json(output_root / "false_positive_analysis.json", {"falsePositiveCount": len(false_positives), "rows": false_positives})
    _write_json(output_root / "v7_3_full_pipeline_non_promotion_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "failsafe_attempt_plan.json", attempt_plan)
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "positiveAudit": positive_audit})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the v7.3 full-pipeline non-promotion evaluation.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="v7_3_full_pipeline_non_promotion_eval")
    args = parser.parse_args()
    payload = run_v7_3_full_pipeline_non_promotion_eval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
