"""Historical training recipe, retired with its RunPod execution path."""

from __future__ import annotations


import json
from pathlib import Path
import shutil
import statistics
from typing import Any, Callable

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_1_export_label_overlay_audit_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_tiny_overfit_sanity_train_v1"
DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"

TRAIN_POSITIVE_COUNT = 10
TRAIN_NEGATIVE_COUNT = 20
VAL_POSITIVE_COUNT = 5
VAL_NEGATIVE_COUNT = 10
CANARY_COUNT = 20

PASS_MIN_LOCALIZATION_RATE = 0.90
PASS_MAX_TRAIN_NEGATIVE_FP_RATE = 0.10
PASS_MAX_CANARY_FP_RATE = 0.20
PASS_MIN_MEDIAN_CONFIDENCE = 0.05
PASS_MAX_TOP_LEFT_SHARE = 0.10
PASS_MAX_GIANT_BOX_SHARE = 0.10
PASS_MAX_AREA_RATIO = 10.0

BLOCKER_TRAIN_FAILED = "v7_1_tiny_train_failed_to_complete"
BLOCKER_LOCALIZATION = "v7_1_tiny_train_positive_localization_failure"
BLOCKER_CONFIDENCE = "v7_1_tiny_train_confidence_still_low"
BLOCKER_NEGATIVE_FLOOD = "v7_1_tiny_train_negative_false_positive_flood"
BLOCKER_TOP_LEFT = "v7_1_tiny_train_top_left_artifact_regression"
BLOCKER_GIANT_BOX = "v7_1_tiny_train_giant_box_regression"
BLOCKER_CANARY = "v7_1_tiny_train_canary_flood"
BLOCKER_MISSING = "v7_1_tiny_train_missing_artifacts"

NEXT_BOUNDED_RETRAIN = "v7_1_bounded_retrain"
NEXT_CONFIG_DEBUG = "v7_1_training_config_or_export_debug"
NEXT_HARD_NEGATIVE = "v7_1_hard_negative_balance_refresh"
NEXT_CANARY = "v7_1_canary_hard_negative_expansion"
NEXT_RETRY = "v7_1_tiny_overfit_sanity_train"

Trainer = Callable[..., dict[str, Any]]
Predictor = Callable[..., dict[str, Any]]


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _read_yolo_box(label_path: Path, image_path: Path) -> dict[str, float] | None:
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    fields = text.split()
    if len(fields) != 5 or fields[0] != "0":
        return None
    image = cv2.imread(str(image_path))
    if image is None:
        return None
    height, width = image.shape[:2]
    cx, cy, box_width, box_height = (_safe_float(value) for value in fields[1:])
    center_x = cx * width
    center_y = cy * height
    pixel_width = box_width * width
    pixel_height = box_height * height
    return {
        "x1": center_x - pixel_width / 2.0,
        "y1": center_y - pixel_height / 2.0,
        "x2": center_x + pixel_width / 2.0,
        "y2": center_y + pixel_height / 2.0,
    }


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
    gt_bbox = _read_yolo_box(output_label_path, output_image_path)
    return {
        "exampleId": image_path.stem,
        "truthType": truth_type,
        "split": split,
        "imagePath": str(output_image_path),
        "labelPath": str(output_label_path),
        "gtCropBbox": gt_bbox,
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


def _build_tiny_dataset(*, preview_root: Path, output_root: Path) -> dict[str, Any]:
    dataset_root = output_root / "tiny_dataset"
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    train_pairs = _image_label_pairs(preview_root, "train")
    val_pairs = _image_label_pairs(preview_root, "val")
    canary_pairs = _image_label_pairs(preview_root, "canary")
    train_positives = [(image, label) for image, label in train_pairs if _is_positive_label(label)][:TRAIN_POSITIVE_COUNT]
    train_negatives = [(image, label) for image, label in train_pairs if not _is_positive_label(label)][:TRAIN_NEGATIVE_COUNT]
    val_positives = [(image, label) for image, label in val_pairs if _is_positive_label(label)][:VAL_POSITIVE_COUNT]
    val_negatives = [(image, label) for image, label in val_pairs if not _is_positive_label(label)][:VAL_NEGATIVE_COUNT]
    canaries = [(image, label) for image, label in canary_pairs if not _is_positive_label(label)][:CANARY_COUNT]
    audit_sets = {
        "train_positive": [
            _copy_pair(image, label, dataset_root=dataset_root, split="train", truth_type="positive")
            for image, label in train_positives
        ],
        "train_negative": [
            _copy_pair(image, label, dataset_root=dataset_root, split="train", truth_type="negative")
            for image, label in train_negatives
        ],
        "val_positive": [
            _copy_pair(image, label, dataset_root=dataset_root, split="val", truth_type="positive")
            for image, label in val_positives
        ],
        "val_negative": [
            _copy_pair(image, label, dataset_root=dataset_root, split="val", truth_type="negative")
            for image, label in val_negatives
        ],
        "heldout_canary": [
            _copy_pair(image, label, dataset_root=dataset_root, split="canary", truth_type="negative")
            for image, label in canaries
        ],
    }
    data_yaml = _write_dataset_yaml(dataset_root)
    return {"datasetRoot": dataset_root, "dataYamlPath": data_yaml, "auditSets": audit_sets}


def _training_recipe(*, device: str = "0", epochs: int = 80) -> dict[str, Any]:
    return {
        "baseModelPath": DEFAULT_BASE_MODEL_PATH,
        "imgsz": 256,
        "epochs": int(epochs),
        "batch": 8,
        "device": str(device),
        "workers": 2,
        "seed": 42,
        "patience": int(epochs),
        "augmentationPolicy": {
            "degrees": 0.0,
            "translate": 0.0,
            "scale": 0.0,
            "shear": 0.0,
            "perspective": 0.0,
            "flipud": 0.0,
            "fliplr": 0.0,
            "mosaic": 0.0,
            "mixup": 0.0,
            "copy_paste": 0.0,
        },
    }


def _rewrite_dataset_yaml(dataset_yaml_path: Path, *, remote_dataset_root: str) -> str:
    lines = []
    replaced = False
    for raw_line in dataset_yaml_path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip().startswith("path:"):
            lines.append(f"path: {remote_dataset_root}")
            replaced = True
        else:
            lines.append(raw_line)
    if not replaced:
        lines.insert(0, f"path: {remote_dataset_root}")
    lines.append("")
    return "\n".join(lines)


def _run_runpod_training(
    *,
    dataset_root: Path,
    data_yaml_path: Path,
    output_root: Path,
    training_recipe: dict[str, Any],
) -> dict[str, Any]:
    runpod_session.require_retired_runpod_disabled()


def _resolve_inference_weights_path(training_result: dict[str, Any]) -> tuple[Path, bool]:
    for key in ("bestWeightsLocalPath", "bestWeightsPathLocal", "lastWeightsLocalPath", "lastWeightsPathLocal"):
        value = training_result.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if path.exists():
                return path, True
    return Path(""), False


def _boxes_from_result(result: object) -> list[dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    confidences = getattr(boxes, "conf", None)
    classes = getattr(boxes, "cls", None)
    xyxy = getattr(boxes, "xyxy", None)
    if confidences is None or classes is None or xyxy is None:
        return []
    try:
        conf_values = confidences.detach().cpu().tolist()
    except AttributeError:
        conf_values = list(confidences)
    try:
        class_values = classes.detach().cpu().tolist()
    except AttributeError:
        class_values = list(classes)
    try:
        box_values = xyxy.detach().cpu().tolist()
    except AttributeError:
        box_values = list(xyxy)
    rows = []
    for conf, class_id, bbox in zip(conf_values, class_values, box_values, strict=False):
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        rows.append(
            {
                "confidence": _safe_float(conf),
                "classId": _safe_int(class_id, -1),
                "predCropBbox": [_safe_float(part) for part in bbox],
            }
        )
    return rows


def _predict_with_ultralytics(
    *,
    model_path: Path,
    audit_sets: dict[str, list[dict[str, Any]]],
    conf: float = 0.001,
    imgsz: int = 256,
) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    predictions: dict[str, list[dict[str, Any]]] = {}
    for set_name, rows in audit_sets.items():
        predictions[set_name] = []
        for row in rows:
            image_path = Path(str(row["imagePath"]))
            results = model.predict(source=str(image_path), imgsz=imgsz, conf=conf, verbose=False, device="cpu")
            boxes = []
            for result in results:
                boxes.extend(_boxes_from_result(result))
            best = max(boxes, key=lambda item: _safe_float(item.get("confidence")), default=None)
            predictions[set_name].append(
                {
                    "exampleId": row["exampleId"],
                    "confidence": best.get("confidence") if best else None,
                    "classId": best.get("classId") if best else None,
                    "predCropBbox": best.get("predCropBbox") if best else None,
                }
            )
    return {"predictions": predictions}


def _bbox_area(bbox: dict[str, float] | list[float] | None) -> float:
    if bbox is None:
        return 0.0
    if isinstance(bbox, dict):
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
    else:
        x1, y1, x2, y2 = bbox
    return max(0.0, _safe_float(x2) - _safe_float(x1)) * max(0.0, _safe_float(y2) - _safe_float(y1))


def _iou(gt_bbox: dict[str, float], pred_bbox: list[float]) -> float:
    x1 = max(gt_bbox["x1"], _safe_float(pred_bbox[0]))
    y1 = max(gt_bbox["y1"], _safe_float(pred_bbox[1]))
    x2 = min(gt_bbox["x2"], _safe_float(pred_bbox[2]))
    y2 = min(gt_bbox["y2"], _safe_float(pred_bbox[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = _bbox_area(gt_bbox) + _bbox_area(pred_bbox) - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(gt_bbox: dict[str, float], pred_bbox: list[float]) -> float:
    gt_x = (gt_bbox["x1"] + gt_bbox["x2"]) / 2.0
    gt_y = (gt_bbox["y1"] + gt_bbox["y2"]) / 2.0
    pred_x = (_safe_float(pred_bbox[0]) + _safe_float(pred_bbox[2])) / 2.0
    pred_y = (_safe_float(pred_bbox[1]) + _safe_float(pred_bbox[3])) / 2.0
    return float(((gt_x - pred_x) ** 2 + (gt_y - pred_y) ** 2) ** 0.5)


def _prediction_by_id(predictions: dict[str, Any], set_name: str) -> dict[str, dict[str, Any]]:
    rows = predictions.get("predictions", {}).get(set_name, [])
    return {str(row.get("exampleId")): dict(row) for row in rows if isinstance(row, dict)}


def _audit_set(
    rows: list[dict[str, Any]],
    *,
    predictions: dict[str, Any],
    set_name: str,
) -> list[dict[str, Any]]:
    pred_by_id = _prediction_by_id(predictions, set_name)
    audited = []
    for row in rows:
        pred = pred_by_id.get(str(row["exampleId"]), {})
        pred_bbox = pred.get("predCropBbox") if isinstance(pred.get("predCropBbox"), list) else None
        confidence = pred.get("confidence")
        gt_bbox = row.get("gtCropBbox") if isinstance(row.get("gtCropBbox"), dict) else None
        iou = _iou(gt_bbox, pred_bbox) if gt_bbox and pred_bbox else 0.0
        center_distance = _center_distance(gt_bbox, pred_bbox) if gt_bbox and pred_bbox else None
        is_hit = bool(row["truthType"] == "positive" and pred_bbox and (iou >= 0.10 or (center_distance is not None and center_distance <= 16.0)))
        pred_area = _bbox_area(pred_bbox)
        gt_area = _bbox_area(gt_bbox)
        image = cv2.imread(str(row["imagePath"]))
        image_area = float(image.shape[0] * image.shape[1]) if image is not None else 0.0
        audited.append(
            {
                **row,
                "confidence": confidence,
                "classId": pred.get("classId"),
                "predCropBbox": pred_bbox,
                "iou": round(iou, 6),
                "centerDistancePx": round(center_distance, 6) if center_distance is not None else None,
                "isLocalizationHit": is_hit,
                "isFalsePositive": bool(row["truthType"] == "negative" and pred_bbox is not None),
                "isTopLeftArtifact": bool(pred_bbox and _safe_float(pred_bbox[0]) <= 2.0 and _safe_float(pred_bbox[1]) <= 2.0),
                "isGiantBox": bool(
                    pred_bbox
                    and (
                        (gt_area > 0 and pred_area / gt_area > PASS_MAX_AREA_RATIO)
                        or (gt_area <= 0 and image_area > 0 and pred_area / image_area > 0.40)
                    )
                ),
                "detectedBoxAreaToGtBoxAreaRatio": round(pred_area / gt_area, 6) if gt_area > 0 and pred_bbox else None,
            }
        )
    return audited


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row.get(key)) / len(rows), 6)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 6)


def _draw_contact_sheet(rows: list[dict[str, Any]], *, output_path: Path, max_items: int = 30) -> int:
    selected = rows[:max_items]
    if not selected:
        return 0
    tile = 180
    columns = 5
    sheet = np.zeros((int(np.ceil(len(selected) / columns)) * tile, columns * tile, 3), dtype=np.uint8)
    sheet[:, :] = (20, 20, 20)
    for index, row in enumerate(selected):
        image = cv2.imread(str(row["imagePath"]))
        if image is None:
            continue
        gt_bbox = row.get("gtCropBbox")
        pred_bbox = row.get("predCropBbox")
        if isinstance(gt_bbox, dict):
            cv2.rectangle(
                image,
                (int(round(gt_bbox["x1"])), int(round(gt_bbox["y1"]))),
                (int(round(gt_bbox["x2"])), int(round(gt_bbox["y2"]))),
                (0, 255, 255),
                2,
            )
        if isinstance(pred_bbox, list):
            cv2.rectangle(
                image,
                (int(round(_safe_float(pred_bbox[0]))), int(round(_safe_float(pred_bbox[1])))),
                (int(round(_safe_float(pred_bbox[2]))), int(round(_safe_float(pred_bbox[3])))),
                (0, 0, 255),
                2,
            )
        cv2.rectangle(image, (0, 0), (image.shape[1], 24), (0, 0, 0), -1)
        label = f"{row.get('exampleId')} conf={row.get('confidence')}"
        cv2.putText(image, label[:48], (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        resized = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA)
        sheet[(index // columns) * tile : (index // columns + 1) * tile, (index % columns) * tile : (index % columns + 1) * tile] = resized
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)
    return len(selected)


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not summary["tinyOverfitTrainingCompleted"]:
        return BLOCKER_TRAIN_FAILED, NEXT_RETRY, False, "Tiny training did not complete; do not advance to bounded retrain."
    if summary["missingArtifactCount"] > 0:
        return BLOCKER_MISSING, NEXT_CONFIG_DEBUG, False, "Tiny training or inference artifacts are missing."
    if summary["tinyTrainPositiveLocalizationHitRate"] < PASS_MIN_LOCALIZATION_RATE:
        return BLOCKER_LOCALIZATION, NEXT_CONFIG_DEBUG, False, "The tiny model could not localize the memorized positive crop labels."
    if summary["medianTrainPositiveConfidence"] is None or summary["medianTrainPositiveConfidence"] <= PASS_MIN_MEDIAN_CONFIDENCE:
        return BLOCKER_CONFIDENCE, NEXT_CONFIG_DEBUG, False, "Positive localization exists, but confidence remains near the old low-confidence flood regime."
    if summary["tinyTrainNegativeFalsePositiveFrameRate"] > PASS_MAX_TRAIN_NEGATIVE_FP_RATE:
        return BLOCKER_NEGATIVE_FLOOD, NEXT_HARD_NEGATIVE, False, "The tiny model fires on too many training hard-negative crops."
    if summary["topLeftArtifactShare"] > PASS_MAX_TOP_LEFT_SHARE:
        return BLOCKER_TOP_LEFT, NEXT_HARD_NEGATIVE, False, "The top-left artifact signature reappeared in the tiny sanity run."
    if summary["giantBoxShare"] > PASS_MAX_GIANT_BOX_SHARE or (
        summary["medianDetectedBoxAreaToGtBoxAreaRatio"] is not None
        and summary["medianDetectedBoxAreaToGtBoxAreaRatio"] > PASS_MAX_AREA_RATIO
    ):
        return BLOCKER_GIANT_BOX, NEXT_CONFIG_DEBUG, False, "The model's detections are too large relative to the reviewed ball boxes."
    if summary["tinyHeldoutCanaryFalsePositiveFrameRate"] > PASS_MAX_CANARY_FP_RATE:
        return BLOCKER_CANARY, NEXT_CANARY, False, "The tiny model learned training positives but floods heldout hard-negative canaries."
    return (
        None,
        NEXT_BOUNDED_RETRAIN,
        True,
        "Tiny overfit sanity train passed. Advance to bounded v7.1 retrain; do not promote.",
    )


def _markdown_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Tiny Overfit Sanity Train",
            "",
            f"- Goal achieved: `{payload.get('goalAchieved')}`",
            f"- Primary blocker: `{payload.get('primaryBlocker')}`",
            f"- Train positive localization hit rate: `{payload.get('tinyTrainPositiveLocalizationHitRate')}`",
            f"- Train negative false-positive frame rate: `{payload.get('tinyTrainNegativeFalsePositiveFrameRate')}`",
            f"- Canary false-positive frame rate: `{payload.get('tinyHeldoutCanaryFalsePositiveFrameRate')}`",
            f"- Median train positive confidence: `{payload.get('medianTrainPositiveConfidence')}`",
            f"- Next: `{payload.get('nextRecommendedNextLever')}`",
            "",
            str(payload.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_tiny_overfit_sanity_train(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    use_runpod: bool = False,
    trainer: Trainer | None = None,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "tiny_crop_overfit_train",
    training_device: str = "0",
    training_epochs: int = 80,
) -> dict[str, Any]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
