from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
import backend.scripts.run_v7_1_bounded_retrain as bounded  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_1_bounded_retrain_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_crop_probe_precision_guardrail_audit_v1"
CONF_SWEEP = (0.50, 0.25, 0.10, 0.05, 0.01, 0.001)
SELECTED_AUDIT_CONF = 0.10

BLOCKER_CHECKPOINT = "v7_1_crop_probe_checkpoint_contract_failure"
BLOCKER_POSITIVE_REGRESSION = "v7_1_crop_probe_positive_localization_regression"
BLOCKER_VAL_RECALL = "v7_1_crop_probe_validation_recall_insufficient"
BLOCKER_NEGATIVE_FLOOD = "v7_1_crop_probe_hard_negative_false_positive_flood"
BLOCKER_CANARY_FLOOD = "v7_1_crop_probe_canary_false_positive_flood"
BLOCKER_TOP_LEFT = "v7_1_crop_probe_top_left_artifact_regression"
BLOCKER_GIANT = "v7_1_crop_probe_giant_box_regression"
BLOCKER_LOW_CONF = "v7_1_crop_probe_low_confidence_flood_regression"
BLOCKER_ARTIFACTS = "v7_1_crop_probe_overlay_artifacts_missing"
BLOCKER_MISS_ANALYSIS = "v7_1_crop_probe_miss_analysis_missing"

NEXT_PIPELINE = "v7_1_full_pipeline_non_promotion_eval"
NEXT_CONFIG_DEBUG = "v7_1_training_config_or_export_debug"
NEXT_POSITIVE_DIVERSITY = "v7_1_positive_diversity_refresh"
NEXT_ARTIFACT_DEBUG = "v7_1_artifact_regression_debug"
NEXT_CONFIDENCE = "v7_1_confidence_operating_point_calibration"
NEXT_HARD_NEGATIVE = "v7_1_hard_negative_expansion"

Predictor = Callable[..., dict[str, Any]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_path(summary: dict[str, Any], *keys: str) -> Path | None:
    for key in keys:
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if path.exists():
                return path
    return None


def _copy_pair_to_output(row: dict[str, Any], *, output_root: Path, split: str) -> dict[str, Any]:
    image_path = Path(str(row["imagePath"]))
    label_path = Path(str(row["labelPath"]))
    dataset_root = output_root / "audit_dataset_snapshot"
    target_image = dataset_root / "images" / split / image_path.name
    target_label = dataset_root / "labels" / split / label_path.name
    target_image.parent.mkdir(parents=True, exist_ok=True)
    target_label.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image_path, target_image)
    shutil.copy2(label_path, target_label)
    copied = dict(row)
    copied["imagePath"] = str(target_image)
    copied["labelPath"] = str(target_label)
    if copied.get("truthType") == "positive":
        copied["gtCropBbox"] = tiny_train._read_yolo_box(target_label, target_image)
    return copied


def _audit_sets_from_bounded_root(*, bounded_root: Path, output_root: Path) -> dict[str, list[dict[str, Any]]]:
    bounded_dataset = bounded._build_bounded_dataset(preview_root=bounded_root / "bounded_dataset_snapshot", output_root=output_root)
    # _build_bounded_dataset expects preview-style images/labels. If the bounded snapshot already uses
    # that same structure, this gives us a copied read-only audit dataset under this batch.
    return bounded_dataset["auditSets"]


def _audit_sets_from_existing_snapshot(*, bounded_root: Path, output_root: Path) -> dict[str, list[dict[str, Any]]]:
    snapshot = bounded_root / "bounded_dataset_snapshot"
    audit_sets: dict[str, list[dict[str, Any]]] = {
        "bounded_train_positive": [],
        "bounded_train_negative": [],
        "bounded_val_positive": [],
        "bounded_val_negative": [],
        "heldout_canary": [],
        "artifact_family_top_left": [],
    }
    for split in ("train", "val"):
        for image_path, label_path in bounded._image_label_pairs(snapshot, split):
            positive = bounded._is_positive_label(label_path)
            set_name = f"bounded_{split}_{'positive' if positive else 'negative'}"
            row = {
                "exampleId": image_path.stem,
                "truthType": "positive" if positive else "negative",
                "split": split,
                "imagePath": str(image_path),
                "labelPath": str(label_path),
                "gtCropBbox": tiny_train._read_yolo_box(label_path, image_path) if positive else None,
            }
            audit_sets[set_name].append(_copy_pair_to_output(row, output_root=output_root, split=split))
    for image_path, label_path in bounded._image_label_pairs(snapshot, "canary"):
        row = {
            "exampleId": image_path.stem,
            "truthType": "negative",
            "split": "canary",
            "imagePath": str(image_path),
            "labelPath": str(label_path),
            "gtCropBbox": None,
        }
        copied = _copy_pair_to_output(row, output_root=output_root, split="canary")
        audit_sets["heldout_canary"].append(copied)
        audit_sets["artifact_family_top_left"].append(dict(copied, split="artifact_family_top_left"))
    return audit_sets


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 6)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction), 6)


def _center_success_rate(rows: list[dict[str, Any]], threshold: float) -> float:
    if not rows:
        return 0.0
    return round(
        sum(
            1
            for row in rows
            if row.get("centerDistancePx") is not None and tiny_train._safe_float(row.get("centerDistancePx")) <= threshold
        )
        / len(rows),
        6,
    )


def _positive_distance_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    distances = [
        tiny_train._safe_float(row.get("centerDistancePx"))
        for row in rows
        if row.get("centerDistancePx") is not None
    ]
    return {
        "successAt5Px": _center_success_rate(rows, 5.0),
        "successAt10Px": _center_success_rate(rows, 10.0),
        "successAt20Px": _center_success_rate(rows, 20.0),
        "centerDistanceP50": _percentile(distances, 0.50),
        "centerDistanceP90": _percentile(distances, 0.90),
    }


def _negative_slice_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    false_positive_rows = [row for row in rows if row.get("isFalsePositive")]
    confidences = [
        tiny_train._safe_float(row.get("confidence"))
        for row in false_positive_rows
        if row.get("confidence") is not None
    ]
    return {
        "falsePositiveFrameRate": tiny_train._rate(rows, "isFalsePositive"),
        "falsePositiveBoxCount": len(false_positive_rows),
        "maxConfidence": round(max(confidences), 6) if confidences else None,
        "medianFalsePositiveConfidence": round(float(statistics.median(confidences)), 6) if confidences else None,
    }


def _miss_type(row: dict[str, Any]) -> str:
    if row.get("isLocalizationHit"):
        return "localized"
    if row.get("predCropBbox") is None:
        return "no_prediction"
    area_ratio = row.get("detectedBoxAreaToGtBoxAreaRatio")
    if area_ratio is not None and (tiny_train._safe_float(area_ratio) < 0.25 or tiny_train._safe_float(area_ratio) > 4.0):
        return "wrong_scale_box"
    if row.get("centerDistancePx") is not None and tiny_train._safe_float(row.get("centerDistancePx")) <= 32.0:
        return "near_miss_center_distance"
    if row.get("isTopLeftArtifact"):
        return "off_target_artifact"
    return "crop_context_issue"


def _validation_miss_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    misses = []
    for row in rows:
        if row.get("isLocalizationHit"):
            continue
        misses.append(
            {
                "exampleId": row.get("exampleId"),
                "split": row.get("split"),
                "gtCropBbox": row.get("gtCropBbox"),
                "bestPredictionConf": row.get("confidence"),
                "bestPredictionBbox": row.get("predCropBbox"),
                "centerDistancePx": row.get("centerDistancePx"),
                "iou": row.get("iou"),
                "missType": _miss_type(row),
                "imagePath": row.get("imagePath"),
            }
        )
    counts: dict[str, int] = {}
    for miss in misses:
        key = str(miss["missType"])
        counts[key] = counts.get(key, 0) + 1
    return {"missCount": len(misses), "missTypeCounts": counts, "misses": misses}


def _detected_rows(audited_sets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in audited_sets.values() for row in rows if row.get("predCropBbox") is not None]


def _near_constant_low_confidence_flood(rows: list[dict[str, Any]]) -> bool:
    confidences = [
        tiny_train._safe_float(row.get("confidence"))
        for row in rows
        if row.get("confidence") is not None
    ]
    if len(confidences) < 10:
        return False
    return max(confidences) - min(confidences) < 0.002 and statistics.median(confidences) < 0.02


def _audit_checkpoint(
    *,
    checkpoint_path: Path,
    audit_sets: dict[str, list[dict[str, Any]]],
    predictor: Predictor | None,
) -> dict[str, Any]:
    sweeps = []
    for conf in CONF_SWEEP:
        prediction_result = (
            predictor(model_path=checkpoint_path, audit_sets=audit_sets, conf=conf, imgsz=256)
            if predictor is not None
            else tiny_train._predict_with_ultralytics(model_path=checkpoint_path, audit_sets=audit_sets, conf=conf, imgsz=256)
        )
        audited_sets = {
            set_name: tiny_train._audit_set(rows, predictions=prediction_result, set_name=set_name)
            for set_name, rows in audit_sets.items()
        }
        train_positive = audited_sets["bounded_train_positive"]
        val_positive = audited_sets["bounded_val_positive"]
        all_detected = _detected_rows(audited_sets)
        val_stats = _positive_distance_stats(val_positive)
        sweeps.append(
            {
                "checkpointName": "best.pt",
                "checkpointPath": str(checkpoint_path),
                "checkpointSha256": _sha256(checkpoint_path),
                "conf": conf,
                "predictArgs": {"model": str(checkpoint_path), "conf": conf, "imgsz": 256, "device": "cpu"},
                "boundedTrainPositiveLocalizationHitRate": tiny_train._rate(train_positive, "isLocalizationHit"),
                "boundedTrainPositiveIoUHitRate": bounded._iou_hit_rate(train_positive),
                "boundedTrainPositiveCenterHitRate": bounded._center_hit_rate(train_positive),
                "boundedValPositiveLocalizationHitRate": tiny_train._rate(val_positive, "isLocalizationHit"),
                "boundedValPositiveIoUHitRate": bounded._iou_hit_rate(val_positive),
                "boundedValPositiveCenterHitRate": bounded._center_hit_rate(val_positive),
                "valPositiveSuccessAt5Px": val_stats["successAt5Px"],
                "valPositiveSuccessAt10Px": val_stats["successAt10Px"],
                "valPositiveSuccessAt20Px": val_stats["successAt20Px"],
                "valPositiveCenterDistanceP50": val_stats["centerDistanceP50"],
                "valPositiveCenterDistanceP90": val_stats["centerDistanceP90"],
                "boundedTrainHardNegativeFalsePositiveFrameRate": tiny_train._rate(audited_sets["bounded_train_negative"], "isFalsePositive"),
                "boundedValHardNegativeFalsePositiveFrameRate": tiny_train._rate(audited_sets["bounded_val_negative"], "isFalsePositive"),
                "heldoutCanaryFalsePositiveFrameRate": tiny_train._rate(audited_sets["heldout_canary"], "isFalsePositive"),
                "oldTopLeftArtifactFalsePositiveFrameRate": tiny_train._rate(audited_sets["artifact_family_top_left"], "isFalsePositive"),
                "topLeftArtifactShare": tiny_train._rate(all_detected, "isTopLeftArtifact"),
                "giantBoxShare": tiny_train._rate(all_detected, "isGiantBox"),
                "nearConstantLowConfidenceFlood": _near_constant_low_confidence_flood(all_detected),
                "medianTrainPositiveConfidence": bounded._median_confidence(train_positive),
                "medianValPositiveConfidence": bounded._median_confidence(val_positive),
                "medianDetectedBoxAreaToGtBoxAreaRatio": bounded._area_ratio(train_positive + val_positive),
                "auditedSets": audited_sets,
            }
        )
    return {"checkpointName": "best.pt", "checkpointPath": str(checkpoint_path), "checkpointSha256": _sha256(checkpoint_path), "sweeps": sweeps}


def _selected_sweep(checkpoint_audit: dict[str, Any]) -> dict[str, Any] | None:
    for sweep in checkpoint_audit.get("sweeps", []):
        if sweep.get("conf") == SELECTED_AUDIT_CONF:
            return sweep
    return checkpoint_audit.get("sweeps", [None])[0]


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str, str | None]:
    if not summary["checkpointContractPassed"]:
        return (
            BLOCKER_CHECKPOINT,
            NEXT_CONFIG_DEBUG,
            False,
            "No verified local bounded best.pt exists; refusing remote, stale, or base-model inference.",
            None,
        )
    if summary["missingArtifactCount"] > 0:
        return BLOCKER_ARTIFACTS, NEXT_CONFIG_DEBUG, False, "Guardrail visual/audit artifacts are missing.", None
    if summary["boundedTrainPositiveLocalizationHitRate"] < 0.90:
        return (
            BLOCKER_POSITIVE_REGRESSION,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "Bounded crop probe regressed on training positive localization.",
            None,
        )
    if summary["boundedValPositiveLocalizationHitRate"] < 0.50:
        return (
            BLOCKER_VAL_RECALL,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "Bounded crop probe validation recall is below the minimum guardrail.",
            None,
        )
    if summary["oldTopLeftArtifactFalsePositiveFrameRate"] > 0.05 or summary["topLeftArtifactShare"] > 0.0:
        return (
            BLOCKER_TOP_LEFT,
            NEXT_ARTIFACT_DEBUG,
            False,
            "The old top-left artifact family reappeared; do not advance to pipeline evaluation.",
            None,
        )
    if summary["boundedTrainHardNegativeFalsePositiveFrameRate"] > 0.05 or summary["boundedValHardNegativeFalsePositiveFrameRate"] > 0.05:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Bounded crop probe fires on too many hard-negative crops.",
            None,
        )
    if summary["heldoutCanaryFalsePositiveFrameRate"] > 0.10:
        return (
            BLOCKER_CANARY_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Bounded crop probe floods heldout hard-negative canaries.",
            None,
        )
    area_ratio = summary.get("medianDetectedBoxAreaToGtBoxAreaRatio")
    if summary["giantBoxShare"] > 0.0 or (area_ratio is not None and (area_ratio < 0.25 or area_ratio > 4.0)):
        return (
            BLOCKER_GIANT,
            NEXT_CONFIG_DEBUG,
            False,
            "Bounded crop probe produced badly scaled boxes relative to reviewed ball labels.",
            None,
        )
    if summary["nearConstantLowConfidenceFlood"]:
        return (
            BLOCKER_LOW_CONF,
            NEXT_CONFIDENCE,
            False,
            "Near-constant low-confidence flood signature reappeared.",
            None,
        )
    secondary = "v7_1_validation_positive_recall_limited" if summary["boundedValPositiveLocalizationHitRate"] < 0.70 else None
    return (
        None,
        NEXT_PIPELINE,
        True,
        "Bounded crop detector passed precision guardrails with limited validation recall. Advance to full-pipeline non-promotion evaluation; do not promote.",
        secondary,
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Crop Probe Precision Guardrail Audit",
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


def run_v7_1_crop_probe_precision_guardrail_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "bounded_crop_precision_guardrail_audit",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    bounded_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    output_root = reset_output(candidate_root, output_dir_name)
    bounded_summary = _load_json(bounded_root / "v7_1_bounded_retrain_summary.json", required=True)
    checkpoint_path = _checkpoint_path(bounded_summary, "bestWeightsPathLocal", "bestWeightsLocalPath")
    checkpoint_contract_passed = bool(
        bounded_summary.get("checkpointContractPassed")
        and bounded_summary.get("inferenceUsedTrainedWeights")
        and not bounded_summary.get("inferenceUsedRemotePath")
        and not bounded_summary.get("inferenceUsedBaseModel")
        and checkpoint_path is not None
    )
    audit_sets = _audit_sets_from_existing_snapshot(bounded_root=bounded_root, output_root=output_root)
    checkpoint_audit = {"checkpointName": "best.pt", "checkpointPath": str(checkpoint_path) if checkpoint_path else None, "sweeps": []}
    selected: dict[str, Any] | None = None
    if checkpoint_contract_passed and checkpoint_path is not None:
        checkpoint_audit = _audit_checkpoint(checkpoint_path=checkpoint_path, audit_sets=audit_sets, predictor=predictor)
        selected = _selected_sweep(checkpoint_audit)
    audited_sets = (
        selected["auditedSets"]
        if isinstance(selected, dict) and isinstance(selected.get("auditedSets"), dict)
        else {set_name: tiny_train._audit_set(rows, predictions={"predictions": {}}, set_name=set_name) for set_name, rows in audit_sets.items()}
    )
    miss_analysis = _validation_miss_analysis(audited_sets["bounded_val_positive"])
    worst_misses = [row for row in audited_sets["bounded_val_positive"] if not row.get("isLocalizationHit")]
    false_positives = [
        row
        for set_name in ("bounded_train_negative", "bounded_val_negative", "heldout_canary", "artifact_family_top_left")
        for row in audited_sets[set_name]
        if row.get("isFalsePositive")
    ]
    miss_sheet = tiny_train._draw_contact_sheet(worst_misses or audited_sets["bounded_val_positive"], output_path=output_root / "worst_positive_misses_contact_sheet.jpg")
    fp_sheet = tiny_train._draw_contact_sheet(false_positives or audited_sets["bounded_train_negative"][:20], output_path=output_root / "worst_false_positives_contact_sheet.jpg")
    top_left_sheet = tiny_train._draw_contact_sheet(audited_sets["artifact_family_top_left"], output_path=output_root / "top_left_artifact_contact_sheet.jpg")
    missing_artifacts = sum(1 for count in (miss_sheet, fp_sheet, top_left_sheet) if count <= 0)

    selected_metrics = selected or {}
    summary: dict[str, Any] = {
        "batchName": "v7_1_crop_probe_precision_guardrail_audit",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "sourceTrainingBatch": "v7_1_bounded_retrain",
        "trainingAllowed": False,
        "trainingExecuted": False,
        "checkpointContractPassed": checkpoint_contract_passed,
        "inferenceUsedTrainedWeights": checkpoint_contract_passed,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "selectedCheckpointForAudit": "best.pt" if checkpoint_contract_passed else None,
        "selectedCheckpointSha256": _sha256(checkpoint_path),
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
        secondary = secondary or "v7_1_validation_positive_recall_limited"
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
    _write_json(output_root / "hard_negative_prediction_audit.json", {"trainRows": audited_sets["bounded_train_negative"], "valRows": audited_sets["bounded_val_negative"], "stats": {"train": _negative_slice_stats(audited_sets["bounded_train_negative"]), "val": _negative_slice_stats(audited_sets["bounded_val_negative"])}})
    _write_json(output_root / "heldout_canary_prediction_audit.json", {"rows": audited_sets["heldout_canary"], "stats": _negative_slice_stats(audited_sets["heldout_canary"])})
    _write_json(output_root / "old_top_left_artifact_prediction_audit.json", {"rows": audited_sets["artifact_family_top_left"], "stats": _negative_slice_stats(audited_sets["artifact_family_top_left"])})
    _write_json(output_root / "validation_positive_miss_analysis.json", miss_analysis)
    _write_json(output_root / "artifact_family_breakdown.json", {"oldTopLeftArtifact": _negative_slice_stats(audited_sets["artifact_family_top_left"])})
    _write_json(output_root / "v7_1_crop_probe_precision_guardrail_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "checkpointAudit": checkpoint_audit, "validationMissAnalysis": miss_analysis})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="bounded_crop_precision_guardrail_audit")
    args = parser.parse_args()
    payload = run_v7_1_crop_probe_precision_guardrail_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
