from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
import backend.scripts.run_v7_1_crop_probe_precision_guardrail_audit as guardrail_v7_1  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_2_bounded_retrain_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_crop_probe_precision_guardrail_audit_v1"
SELECTED_AUDIT_CONF = 0.10

BLOCKER_CHECKPOINT = "v7_2_crop_probe_checkpoint_contract_failure"
BLOCKER_POSITIVE_REGRESSION = "v7_2_crop_probe_positive_localization_regression"
BLOCKER_VAL_RECALL = "v7_2_crop_probe_validation_recall_insufficient"
BLOCKER_NEGATIVE_FLOOD = "v7_2_crop_probe_hard_negative_false_positive_flood"
BLOCKER_CANARY_FLOOD = "v7_2_crop_probe_canary_false_positive_flood"
BLOCKER_TOP_LEFT = "v7_2_crop_probe_top_left_artifact_regression"
BLOCKER_GIANT = "v7_2_crop_probe_giant_box_regression"
BLOCKER_LOW_CONF = "v7_2_crop_probe_low_confidence_flood_regression"
BLOCKER_ARTIFACTS = "v7_2_crop_probe_overlay_artifacts_missing"

NEXT_PIPELINE = "v7_2_full_pipeline_non_promotion_eval"
NEXT_CONFIG_DEBUG = "v7_2_training_config_or_export_debug"
NEXT_POSITIVE_DIVERSITY = "v7_2_positive_diversity_refresh"
NEXT_ARTIFACT_DEBUG = "v7_2_artifact_regression_debug"
NEXT_CONFIDENCE = "v7_2_confidence_operating_point_calibration"
NEXT_HARD_NEGATIVE = "v7_2_hard_negative_expansion"

Predictor = Callable[..., dict[str, Any]]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str, str | None]:
    if not summary["checkpointContractPassed"]:
        return (
            BLOCKER_CHECKPOINT,
            NEXT_CONFIG_DEBUG,
            False,
            "No verified local v7.2 bounded best.pt exists; refusing remote, stale, or base-model inference.",
            None,
        )
    if summary["missingArtifactCount"] > 0:
        return BLOCKER_ARTIFACTS, NEXT_CONFIG_DEBUG, False, "Guardrail visual/audit artifacts are missing.", None
    if summary["boundedTrainPositiveLocalizationHitRate"] < 0.90:
        return (
            BLOCKER_POSITIVE_REGRESSION,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "v7.2 crop probe regressed on training positive localization.",
            None,
        )
    if summary["boundedValPositiveLocalizationHitRate"] < 0.50:
        return (
            BLOCKER_VAL_RECALL,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "v7.2 crop probe validation recall is below the minimum guardrail.",
            None,
        )
    if summary["oldTopLeftArtifactFalsePositiveFrameRate"] > 0.05 or summary["topLeftArtifactShare"] > 0.0:
        return (
            BLOCKER_TOP_LEFT,
            NEXT_ARTIFACT_DEBUG,
            False,
            "The old top-left artifact family reappeared in the v7.2 guardrail audit.",
            None,
        )
    if summary["boundedTrainHardNegativeFalsePositiveFrameRate"] > 0.05 or summary["boundedValHardNegativeFalsePositiveFrameRate"] > 0.05:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "v7.2 crop probe fires on too many hard-negative crops.",
            None,
        )
    if summary["heldoutCanaryFalsePositiveFrameRate"] > 0.10:
        return (
            BLOCKER_CANARY_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "v7.2 crop probe floods heldout hard-negative canaries.",
            None,
        )
    area_ratio = summary.get("medianDetectedBoxAreaToGtBoxAreaRatio")
    if summary["giantBoxShare"] > 0.0 or (area_ratio is not None and (area_ratio < 0.25 or area_ratio > 4.0)):
        return (
            BLOCKER_GIANT,
            NEXT_CONFIG_DEBUG,
            False,
            "v7.2 crop probe produced badly scaled boxes relative to reviewed ball labels.",
            None,
        )
    if summary["nearConstantLowConfidenceFlood"]:
        return (
            BLOCKER_LOW_CONF,
            NEXT_CONFIDENCE,
            False,
            "Near-constant low-confidence flood signature reappeared in v7.2.",
            None,
        )
    secondary = "v7_2_validation_positive_recall_limited" if summary["boundedValPositiveLocalizationHitRate"] < 0.70 else None
    return (
        None,
        NEXT_PIPELINE,
        True,
        "v7.2 bounded crop detector passed precision guardrails. Advance to full-pipeline non-promotion evaluation; do not promote.",
        secondary,
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Crop Probe Precision Guardrail Audit",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Secondary concern: `{summary.get('secondaryConcern')}`",
            f"- Checkpoint contract passed: `{summary.get('checkpointContractPassed')}`",
            f"- Selected checkpoint: `{summary.get('selectedCheckpointForAudit')}`",
            f"- Selected confidence: `{summary.get('selectedAuditConf')}`",
            f"- Train positive localization: `{summary.get('boundedTrainPositiveLocalizationHitRate')}`",
            f"- Validation positive localization: `{summary.get('boundedValPositiveLocalizationHitRate')}`",
            f"- Train hard-negative false-positive rate: `{summary.get('boundedTrainHardNegativeFalsePositiveFrameRate')}`",
            f"- Validation hard-negative false-positive rate: `{summary.get('boundedValHardNegativeFalsePositiveFrameRate')}`",
            f"- Canary false-positive rate: `{summary.get('heldoutCanaryFalsePositiveFrameRate')}`",
            f"- Old top-left artifact false-positive rate: `{summary.get('oldTopLeftArtifactFalsePositiveFrameRate')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_2_crop_probe_precision_guardrail_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "bounded_crop_precision_guardrail_audit",
) -> dict[str, Any]:
    candidate_root = guardrail_v7_1._candidate_root(Path(storage_root), candidate_name)
    bounded_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    output_root = reset_output(candidate_root, output_dir_name)

    bounded_summary = guardrail_v7_1._load_json(bounded_root / "v7_2_bounded_retrain_summary.json", required=True)
    checkpoint_path = guardrail_v7_1._checkpoint_path(bounded_summary, "bestWeightsPathLocal", "bestWeightsLocalPath")
    checkpoint_contract_passed = bool(
        bounded_summary.get("checkpointContractPassed")
        and bounded_summary.get("inferenceUsedTrainedWeights")
        and not bounded_summary.get("inferenceUsedRemotePath")
        and not bounded_summary.get("inferenceUsedBaseModel")
        and checkpoint_path is not None
    )
    audit_sets = guardrail_v7_1._audit_sets_from_existing_snapshot(bounded_root=bounded_root, output_root=output_root)
    checkpoint_audit = {
        "checkpointName": "best.pt",
        "checkpointPath": str(checkpoint_path) if checkpoint_path else None,
        "sweeps": [],
    }
    selected: dict[str, Any] | None = None
    if checkpoint_contract_passed and checkpoint_path is not None:
        checkpoint_audit = guardrail_v7_1._audit_checkpoint(
            checkpoint_path=checkpoint_path,
            audit_sets=audit_sets,
            predictor=predictor,
        )
        selected = guardrail_v7_1._selected_sweep(checkpoint_audit)
    audited_sets = (
        selected["auditedSets"]
        if isinstance(selected, dict) and isinstance(selected.get("auditedSets"), dict)
        else {
            set_name: tiny_train._audit_set(rows, predictions={"predictions": {}}, set_name=set_name)
            for set_name, rows in audit_sets.items()
        }
    )

    miss_analysis = guardrail_v7_1._validation_miss_analysis(audited_sets["bounded_val_positive"])
    worst_misses = [row for row in audited_sets["bounded_val_positive"] if not row.get("isLocalizationHit")]
    false_positives = [
        row
        for set_name in ("bounded_train_negative", "bounded_val_negative", "heldout_canary", "artifact_family_top_left")
        for row in audited_sets[set_name]
        if row.get("isFalsePositive")
    ]
    miss_sheet = tiny_train._draw_contact_sheet(
        worst_misses or audited_sets["bounded_val_positive"],
        output_path=output_root / "worst_positive_misses_contact_sheet.jpg",
    )
    fp_sheet = tiny_train._draw_contact_sheet(
        false_positives or audited_sets["bounded_train_negative"][:20],
        output_path=output_root / "worst_false_positives_contact_sheet.jpg",
    )
    top_left_sheet = tiny_train._draw_contact_sheet(
        audited_sets["artifact_family_top_left"],
        output_path=output_root / "top_left_artifact_contact_sheet.jpg",
    )
    missing_artifacts = sum(1 for count in (miss_sheet, fp_sheet, top_left_sheet) if count <= 0)

    selected_metrics = selected or {}
    summary: dict[str, Any] = {
        "batchName": "v7_2_crop_probe_precision_guardrail_audit",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "sourceTrainingBatch": "v7_2_bounded_retrain",
        "trainingAllowed": False,
        "trainingExecuted": False,
        "checkpointContractPassed": checkpoint_contract_passed,
        "inferenceUsedTrainedWeights": checkpoint_contract_passed,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "selectedCheckpointForAudit": "best.pt" if checkpoint_contract_passed else None,
        "selectedCheckpointSha256": guardrail_v7_1._sha256(checkpoint_path),
        "selectedAuditConf": selected_metrics.get("conf") if selected else None,
        "boundedTrainPositiveLocalizationHitRate": selected_metrics.get("boundedTrainPositiveLocalizationHitRate", 0.0),
        "boundedTrainPositiveIoUHitRate": selected_metrics.get("boundedTrainPositiveIoUHitRate", 0.0),
        "boundedTrainPositiveCenterHitRate": selected_metrics.get("boundedTrainPositiveCenterHitRate", 0.0),
        "boundedValPositiveLocalizationHitRate": selected_metrics.get("boundedValPositiveLocalizationHitRate", 0.0),
        "boundedValPositiveIoUHitRate": selected_metrics.get("boundedValPositiveIoUHitRate", 0.0),
        "boundedValPositiveCenterHitRate": selected_metrics.get("boundedValPositiveCenterHitRate", 0.0),
        "boundedTrainHardNegativeFalsePositiveFrameRate": selected_metrics.get("boundedTrainHardNegativeFalsePositiveFrameRate", 0.0),
        "boundedValHardNegativeFalsePositiveFrameRate": selected_metrics.get("boundedValHardNegativeFalsePositiveFrameRate", 0.0),
        "heldoutCanaryFalsePositiveFrameRate": selected_metrics.get("heldoutCanaryFalsePositiveFrameRate", 0.0),
        "oldTopLeftArtifactFalsePositiveFrameRate": selected_metrics.get("oldTopLeftArtifactFalsePositiveFrameRate", 0.0),
        "valPositiveSuccessAt5Px": selected_metrics.get("valPositiveSuccessAt5Px", 0.0),
        "valPositiveSuccessAt10Px": selected_metrics.get("valPositiveSuccessAt10Px", 0.0),
        "valPositiveSuccessAt20Px": selected_metrics.get("valPositiveSuccessAt20Px", 0.0),
        "valPositiveCenterDistanceP50": selected_metrics.get("valPositiveCenterDistanceP50"),
        "valPositiveCenterDistanceP90": selected_metrics.get("valPositiveCenterDistanceP90"),
        "topLeftArtifactShare": selected_metrics.get("topLeftArtifactShare", 0.0),
        "giantBoxShare": selected_metrics.get("giantBoxShare", 0.0),
        "nearConstantLowConfidenceFlood": selected_metrics.get("nearConstantLowConfidenceFlood", False),
        "medianTrainPositiveConfidence": selected_metrics.get("medianTrainPositiveConfidence"),
        "medianValPositiveConfidence": selected_metrics.get("medianValPositiveConfidence"),
        "medianDetectedBoxAreaToGtBoxAreaRatio": selected_metrics.get("medianDetectedBoxAreaToGtBoxAreaRatio"),
        "precisionGuardrailPassed": False,
        "recallGuardrailStrength": None,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "missingArtifactCount": missing_artifacts,
    }
    primary_blocker, next_family, goal_achieved, english, secondary = _classify(summary)
    if primary_blocker is None and miss_analysis["missCount"] > 0 and summary["boundedValPositiveLocalizationHitRate"] < 0.70:
        secondary = secondary or "v7_2_validation_positive_recall_limited"
    summary.update(
        {
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": goal_achieved,
            "primaryBlocker": primary_blocker,
            "secondaryConcern": secondary,
            "precisionGuardrailPassed": goal_achieved,
            "recallGuardrailStrength": "minimum_pass_validation_recall_limited" if secondary else ("strong_pass" if goal_achieved else "failed"),
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )

    _write_json(output_root / "checkpoint_contract_audit.json", {"summary": summary, "sourceBoundedSummary": bounded_summary})
    _write_json(output_root / "confidence_sweep_audit.json", checkpoint_audit)
    _write_json(output_root / "train_positive_prediction_audit.json", {"rows": audited_sets["bounded_train_positive"]})
    _write_json(output_root / "val_positive_prediction_audit.json", {"rows": audited_sets["bounded_val_positive"]})
    _write_json(
        output_root / "hard_negative_prediction_audit.json",
        {
            "trainRows": audited_sets["bounded_train_negative"],
            "valRows": audited_sets["bounded_val_negative"],
            "stats": {
                "train": guardrail_v7_1._negative_slice_stats(audited_sets["bounded_train_negative"]),
                "val": guardrail_v7_1._negative_slice_stats(audited_sets["bounded_val_negative"]),
            },
        },
    )
    _write_json(
        output_root / "heldout_canary_prediction_audit.json",
        {"rows": audited_sets["heldout_canary"], "stats": guardrail_v7_1._negative_slice_stats(audited_sets["heldout_canary"])},
    )
    _write_json(
        output_root / "old_top_left_artifact_prediction_audit.json",
        {
            "rows": audited_sets["artifact_family_top_left"],
            "stats": guardrail_v7_1._negative_slice_stats(audited_sets["artifact_family_top_left"]),
        },
    )
    _write_json(output_root / "validation_positive_miss_analysis.json", miss_analysis)
    _write_json(
        output_root / "artifact_family_breakdown.json",
        {"oldTopLeftArtifact": guardrail_v7_1._negative_slice_stats(audited_sets["artifact_family_top_left"])},
    )
    _write_json(output_root / "v7_2_crop_probe_precision_guardrail_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {"summary": summary, "checkpointAudit": checkpoint_audit, "validationMissAnalysis": miss_analysis},
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="bounded_crop_precision_guardrail_audit")
    args = parser.parse_args()
    payload = run_v7_2_crop_probe_precision_guardrail_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
