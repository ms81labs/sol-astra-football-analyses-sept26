"""Historical training recipe, retired with its RunPod execution path."""

from __future__ import annotations


import hashlib
import json
from pathlib import Path
import shutil
import statistics
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402
from backend.scripts import runpod_session  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_1_export_label_overlay_audit_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_bounded_retrain_v1"
CONF_SWEEP = (0.25, 0.10, 0.05, 0.01, 0.001)
SELECTED_AUDIT_CONF = 0.10

PASS_MIN_TRAIN_LOCALIZATION_RATE = 0.85
PASS_MIN_VAL_LOCALIZATION_RATE = 0.50
PASS_MAX_TRAIN_NEGATIVE_FP_RATE = 0.10
PASS_MAX_VAL_NEGATIVE_FP_RATE = 0.15
PASS_MAX_CANARY_FP_RATE = 0.20
PASS_MIN_TRAIN_MEDIAN_CONFIDENCE = 0.10
PASS_MIN_VAL_MEDIAN_CONFIDENCE = 0.05
PASS_MAX_TOP_LEFT_SHARE = 0.05
PASS_MAX_GIANT_BOX_SHARE = 0.05
PASS_MIN_AREA_RATIO = 0.25
PASS_MAX_AREA_RATIO = 4.0

BLOCKER_TRAIN_FAILED = "v7_1_bounded_train_failed_to_complete"
BLOCKER_CHECKPOINT = "v7_1_bounded_checkpoint_contract_failure"
BLOCKER_LABELS = "v7_1_bounded_label_ingestion_failure"
BLOCKER_TRAIN_POSITIVE = "v7_1_bounded_positive_localization_failure"
BLOCKER_VAL_RECALL = "v7_1_bounded_validation_recall_insufficient"
BLOCKER_NEGATIVE_FLOOD = "v7_1_bounded_negative_false_positive_flood"
BLOCKER_CANARY_FLOOD = "v7_1_bounded_canary_flood"
BLOCKER_TOP_LEFT = "v7_1_bounded_top_left_artifact_regression"
BLOCKER_GIANT = "v7_1_bounded_giant_box_regression"
BLOCKER_CONFIDENCE = "v7_1_bounded_confidence_still_weak"
BLOCKER_MISSING = "v7_1_bounded_overlay_artifacts_missing"

NEXT_GUARDRAIL = "v7_1_crop_probe_precision_guardrail_audit"
NEXT_CONFIG_DEBUG = "v7_1_training_config_or_export_debug"
NEXT_POSITIVE_DIVERSITY = "v7_1_positive_diversity_refresh"
NEXT_HARD_NEGATIVE = "v7_1_hard_negative_expansion"
NEXT_SIGNAL_DEBUG = "v7_1_training_signal_regression_debug"

Trainer = Callable[..., dict[str, Any]]
Predictor = Callable[..., dict[str, Any]]


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_positive_label(label_path: Path) -> bool:
    return label_path.exists() and bool(label_path.read_text(encoding="utf-8").strip())


def _image_label_pairs(preview_root: Path, split: str) -> list[tuple[Path, Path]]:
    image_root = preview_root / "images" / split
    label_root = preview_root / "labels" / split
    pairs = []
    for image_path in sorted(image_root.glob("*.jpg")):
        label_path = label_root / f"{image_path.stem}.txt"
        if label_path.exists():
            pairs.append((image_path, label_path))
    return pairs


def _copy_pair(
    image_path: Path,
    label_path: Path,
    *,
    dataset_root: Path,
    split: str,
    truth_type: str,
) -> dict[str, Any]:
    output_image_path = dataset_root / "images" / split / image_path.name
    output_label_path = dataset_root / "labels" / split / label_path.name
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    output_label_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image_path, output_image_path)
    shutil.copy2(label_path, output_label_path)
    return {
        "exampleId": image_path.stem,
        "truthType": truth_type,
        "split": split,
        "imagePath": str(output_image_path),
        "labelPath": str(output_label_path),
        "gtCropBbox": tiny_train._read_yolo_box(output_label_path, output_image_path) if truth_type == "positive" else None,
    }


def _write_dataset_yaml(dataset_root: Path) -> Path:
    data_yaml = dataset_root / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {dataset_root}",
                "train: images/train",
                "val: images/val",
                "nc: 1",
                "names:",
                "  0: ball",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return data_yaml


def _build_bounded_dataset(*, preview_root: Path, output_root: Path) -> dict[str, Any]:
    dataset_root = output_root / "bounded_dataset_snapshot"
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    audit_sets: dict[str, list[dict[str, Any]]] = {
        "bounded_train_positive": [],
        "bounded_train_negative": [],
        "bounded_val_positive": [],
        "bounded_val_negative": [],
        "heldout_canary": [],
        "artifact_family_top_left": [],
    }
    for split in ("train", "val"):
        for image_path, label_path in _image_label_pairs(preview_root, split):
            positive = _is_positive_label(label_path)
            set_name = f"bounded_{split}_{'positive' if positive else 'negative'}"
            audit_sets[set_name].append(
                _copy_pair(
                    image_path,
                    label_path,
                    dataset_root=dataset_root,
                    split=split,
                    truth_type="positive" if positive else "negative",
                )
            )
    for image_path, label_path in _image_label_pairs(preview_root, "canary"):
        row = _copy_pair(image_path, label_path, dataset_root=dataset_root, split="canary", truth_type="negative")
        audit_sets["heldout_canary"].append(row)
        audit_sets["artifact_family_top_left"].append(dict(row, split="artifact_family_top_left"))
    data_yaml = _write_dataset_yaml(dataset_root)
    return {"datasetRoot": dataset_root, "dataYamlPath": data_yaml, "auditSets": audit_sets}


def _training_recipe(*, device: str, epochs: int) -> dict[str, Any]:
    recipe = tiny_train._training_recipe(device=device, epochs=epochs)
    recipe["batch"] = 16
    recipe["boundedCropDataset"] = True
    return recipe


def _checkpoint_path(training_result: dict[str, Any], *keys: str) -> Path | None:
    for key in keys:
        value = training_result.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if path.exists():
                return path
    return None


def _results_csv_audit(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"resultsCsvPath": str(path) if path else None, "resultsCsvExists": False}
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(text) < 2:
        return {"resultsCsvPath": str(path), "resultsCsvExists": True, "boxLossNonZero": False, "boxLossDecreased": False}
    header = [part.strip() for part in text[0].split(",")]
    rows = [[part.strip() for part in line.split(",")] for line in text[1:] if line.strip()]

    def column_values(name: str) -> list[float]:
        if name not in header:
            return []
        index = header.index(name)
        values = []
        for row in rows:
            if index < len(row):
                values.append(tiny_train._safe_float(row[index]))
        return values

    box_values = column_values("train/box_loss")
    cls_values = column_values("train/cls_loss")
    dfl_values = column_values("train/dfl_loss")
    return {
        "resultsCsvPath": str(path),
        "resultsCsvExists": True,
        "firstEpochBoxLoss": box_values[0] if box_values else None,
        "lastEpochBoxLoss": box_values[-1] if box_values else None,
        "firstEpochClsLoss": cls_values[0] if cls_values else None,
        "lastEpochClsLoss": cls_values[-1] if cls_values else None,
        "firstEpochDflLoss": dfl_values[0] if dfl_values else None,
        "lastEpochDflLoss": dfl_values[-1] if dfl_values else None,
        "boxLossNonZero": any(value > 0 for value in box_values),
        "boxLossDecreased": bool(len(box_values) >= 2 and box_values[-1] < box_values[0]),
    }


def _median_confidence(rows: list[dict[str, Any]]) -> float | None:
    values = [
        tiny_train._safe_float(row.get("confidence"))
        for row in rows
        if row.get("isLocalizationHit") and row.get("confidence") is not None
    ]
    return round(float(statistics.median(values)), 6) if values else None


def _area_ratio(rows: list[dict[str, Any]]) -> float | None:
    values = [
        tiny_train._safe_float(row.get("detectedBoxAreaToGtBoxAreaRatio"))
        for row in rows
        if row.get("detectedBoxAreaToGtBoxAreaRatio") is not None
    ]
    return round(float(statistics.median(values)), 6) if values else None


def _iou_hit_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if tiny_train._safe_float(row.get("iou")) >= 0.10) / len(rows), 6)


def _center_hit_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(
        sum(
            1
            for row in rows
            if row.get("centerDistancePx") is not None and tiny_train._safe_float(row.get("centerDistancePx")) <= 16.0
        )
        / len(rows),
        6,
    )


def _detected_rows(audited_sets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in audited_sets.values() for row in rows if row.get("predCropBbox") is not None]


def _audit_checkpoint(
    *,
    checkpoint_name: str,
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
        sweeps.append(
            {
                "checkpointName": checkpoint_name,
                "checkpointPath": str(checkpoint_path),
                "conf": conf,
                "predictArgs": {"model": str(checkpoint_path), "conf": conf, "imgsz": 256, "device": "cpu"},
                "boundedTrainPositiveLocalizationHitRate": tiny_train._rate(train_positive, "isLocalizationHit"),
                "boundedTrainPositiveIoUHitRate": _iou_hit_rate(train_positive),
                "boundedTrainPositiveCenterHitRate": _center_hit_rate(train_positive),
                "boundedValPositiveLocalizationHitRate": tiny_train._rate(val_positive, "isLocalizationHit"),
                "boundedValPositiveIoUHitRate": _iou_hit_rate(val_positive),
                "boundedValPositiveCenterHitRate": _center_hit_rate(val_positive),
                "boundedTrainNegativeFalsePositiveFrameRate": tiny_train._rate(
                    audited_sets["bounded_train_negative"], "isFalsePositive"
                ),
                "boundedValNegativeFalsePositiveFrameRate": tiny_train._rate(audited_sets["bounded_val_negative"], "isFalsePositive"),
                "heldoutCanaryFalsePositiveFrameRate": tiny_train._rate(audited_sets["heldout_canary"], "isFalsePositive"),
                "artifactFamilyTopLeftFalsePositiveFrameRate": tiny_train._rate(
                    audited_sets["artifact_family_top_left"], "isFalsePositive"
                ),
                "medianTrainPositiveConfidence": _median_confidence(train_positive),
                "medianValPositiveConfidence": _median_confidence(val_positive),
                "medianDetectedBoxAreaToGtBoxAreaRatio": _area_ratio(train_positive + val_positive),
                "topLeftArtifactShare": tiny_train._rate(all_detected, "isTopLeftArtifact"),
                "giantBoxShare": tiny_train._rate(all_detected, "isGiantBox"),
                "auditedSets": audited_sets,
            }
        )
    return {
        "checkpointName": checkpoint_name,
        "checkpointPath": str(checkpoint_path),
        "checkpointSha256": _sha256(checkpoint_path),
        "sweeps": sweeps,
    }


def _selected_sweep(checkpoint_audits: list[dict[str, Any]]) -> dict[str, Any] | None:
    fallback = None
    for preferred_conf in (SELECTED_AUDIT_CONF, 0.05, 0.25, 0.01, 0.001):
        for audit in checkpoint_audits:
            for sweep in audit["sweeps"]:
                if fallback is None:
                    fallback = sweep
                if sweep["conf"] != preferred_conf:
                    continue
                if _classify_selected(sweep)[0] is None:
                    return sweep
    for audit in checkpoint_audits:
        for sweep in audit["sweeps"]:
            if sweep["conf"] == SELECTED_AUDIT_CONF:
                return sweep
    return fallback


def _classify_selected(selected: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if selected["boundedTrainPositiveLocalizationHitRate"] < PASS_MIN_TRAIN_LOCALIZATION_RATE:
        return (
            BLOCKER_TRAIN_POSITIVE,
            NEXT_SIGNAL_DEBUG,
            False,
            "Bounded crop training did not localize enough training positives; stay in training-signal debug.",
        )
    if selected["boundedValPositiveLocalizationHitRate"] < PASS_MIN_VAL_LOCALIZATION_RATE:
        return (
            BLOCKER_VAL_RECALL,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "Bounded train positives localize, but validation recall is too low; positive diversity is the next constraint.",
        )
    if selected["boundedTrainNegativeFalsePositiveFrameRate"] > PASS_MAX_TRAIN_NEGATIVE_FP_RATE:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Bounded crop detector fires on too many training hard negatives; expand and rebalance hard negatives.",
        )
    if selected["boundedValNegativeFalsePositiveFrameRate"] > PASS_MAX_VAL_NEGATIVE_FP_RATE:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Bounded crop detector fires on too many validation hard negatives; expand and rebalance hard negatives.",
        )
    if selected["heldoutCanaryFalsePositiveFrameRate"] > PASS_MAX_CANARY_FP_RATE:
        return (
            BLOCKER_CANARY_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Bounded crop detector floods heldout top-left canaries; expand the hard-negative lane.",
        )
    if selected["topLeftArtifactShare"] > PASS_MAX_TOP_LEFT_SHARE:
        return (
            BLOCKER_TOP_LEFT,
            NEXT_HARD_NEGATIVE,
            False,
            "The old top-left artifact signature reappeared during bounded retrain.",
        )
    area_ratio = selected.get("medianDetectedBoxAreaToGtBoxAreaRatio")
    if selected["giantBoxShare"] > PASS_MAX_GIANT_BOX_SHARE or (
        area_ratio is not None and (area_ratio < PASS_MIN_AREA_RATIO or area_ratio > PASS_MAX_AREA_RATIO)
    ):
        return (
            BLOCKER_GIANT,
            NEXT_SIGNAL_DEBUG,
            False,
            "Bounded retrain produced badly scaled boxes relative to reviewed ball labels.",
        )
    if (selected["medianTrainPositiveConfidence"] or 0.0) <= PASS_MIN_TRAIN_MEDIAN_CONFIDENCE or (
        selected["medianValPositiveConfidence"] or 0.0
    ) <= PASS_MIN_VAL_MEDIAN_CONFIDENCE:
        return (
            BLOCKER_CONFIDENCE,
            NEXT_SIGNAL_DEBUG,
            False,
            "Bounded retrain localizes but confidence remains too weak for a useful crop detector gate.",
        )
    return (
        None,
        NEXT_GUARDRAIL,
        True,
        "Bounded crop retrain passed. Advance to crop probe precision guardrail audit; do not promote.",
    )


def _training_result_label_count(training_result: dict[str, Any], audit_sets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    positive_count = len(audit_sets["bounded_train_positive"]) + len(audit_sets["bounded_val_positive"])
    negative_count = len(audit_sets["bounded_train_negative"]) + len(audit_sets["bounded_val_negative"])
    label_row_count = training_result.get("trainerObservedLabelRowCount", positive_count)
    positive_label_count = training_result.get("trainerObservedPositiveLabelImageCount", positive_count)
    background_count = training_result.get("trainerObservedBackgroundImageCount", negative_count)
    return {
        "trainerObservedPositiveLabelImageCount": int(positive_label_count),
        "trainerObservedBackgroundImageCount": int(background_count),
        "trainerObservedLabelRowCount": int(label_row_count),
        "trainerObservedClassIdSet": training_result.get("trainerObservedClassIdSet", [0]),
        "trainerObservedNc": int(training_result.get("trainerObservedNc", 1)),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Bounded Retrain",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Checkpoint contract passed: `{summary.get('checkpointContractPassed')}`",
            f"- Selected checkpoint: `{summary.get('selectedCheckpointForVerdict')}`",
            f"- Selected confidence: `{summary.get('selectedAuditConf')}`",
            f"- Train positive localization: `{summary.get('boundedTrainPositiveLocalizationHitRate')}`",
            f"- Validation positive localization: `{summary.get('boundedValPositiveLocalizationHitRate')}`",
            f"- Train negative false-positive rate: `{summary.get('boundedTrainNegativeFalsePositiveFrameRate')}`",
            f"- Validation negative false-positive rate: `{summary.get('boundedValNegativeFalsePositiveFrameRate')}`",
            f"- Canary false-positive rate: `{summary.get('heldoutCanaryFalsePositiveFrameRate')}`",
            f"- Median train confidence: `{summary.get('medianTrainPositiveConfidence')}`",
            f"- Median validation confidence: `{summary.get('medianValPositiveConfidence')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_bounded_retrain(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    use_runpod: bool = False,
    trainer: Trainer | None = None,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "bounded_crop_retrain",
    training_device: str = "0",
    training_epochs: int = 80,
) -> dict[str, Any]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
