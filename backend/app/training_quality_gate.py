from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

import yaml


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_dataset_yaml(dataset_yaml_path: Path) -> dict[str, object]:
    parsed = yaml.safe_load(dataset_yaml_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("dataset YAML must contain a mapping")
    return parsed


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_split_dir(dataset_yaml_path: Path, dataset_root: Path, raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return dataset_root / candidate


def _label_path_for_image(image_path: Path, *, images_dir: Path, labels_dir: Path) -> Path:
    relative = image_path.relative_to(images_dir)
    return labels_dir / relative.with_suffix(".txt")


def _split_image_and_label_counts(
    *,
    images_dir: Path,
    labels_dir: Path,
) -> tuple[list[Path], int, int]:
    image_paths = sorted(
        path
        for path in images_dir.glob("**/*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    positive_label_count = 0
    empty_label_count = 0
    for image_path in image_paths:
        label_path = _label_path_for_image(image_path, images_dir=images_dir, labels_dir=labels_dir)
        label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
        if label_text:
            positive_label_count += 1
        else:
            empty_label_count += 1
    return image_paths, positive_label_count, empty_label_count


def _positive_label_image_paths(
    *,
    train_images_dir: Path,
    train_labels_dir: Path,
    val_images_dir: Path,
    val_labels_dir: Path,
) -> list[Path]:
    positive_images: list[Path] = []
    for images_dir, labels_dir in (
        (train_images_dir, train_labels_dir),
        (val_images_dir, val_labels_dir),
    ):
        for image_path in sorted(
            path
            for path in images_dir.glob("**/*")
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ):
            label_path = _label_path_for_image(image_path, images_dir=images_dir, labels_dir=labels_dir)
            label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
            if label_text:
                positive_images.append(image_path)
    return positive_images


def _positive_label_image_paths_for_split(
    *,
    images_dir: Path,
    labels_dir: Path,
) -> list[Path]:
    positive_images: list[Path] = []
    for image_path in sorted(
        path
        for path in images_dir.glob("**/*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ):
        label_path = _label_path_for_image(image_path, images_dir=images_dir, labels_dir=labels_dir)
        label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
        if label_text:
            positive_images.append(image_path)
    return positive_images


def _load_proposal_window_alignment_report(dataset_yaml_path: Path) -> dict[str, object]:
    batch_root = dataset_yaml_path.parent.parent
    return _load_json(batch_root / "proposal_window_alignment_report.json")


def _default_model_factory(model_path: str):
    from ultralytics import YOLO

    return YOLO(model_path)


def _detected_box_count(prediction: object) -> int:
    boxes = getattr(prediction, "boxes", None)
    if boxes is None:
        return 0
    try:
        return int(len(boxes))
    except TypeError:
        return 0


def _run_local_positive_sanity(
    *,
    best_weights_path: Path | None,
    positive_image_paths: list[Path],
    model_factory: Callable[[str], object] | None,
) -> tuple[int, int]:
    if not positive_image_paths:
        return 0, 0
    if best_weights_path is None or not best_weights_path.exists():
        return len(positive_image_paths), 0
    model = (model_factory or _default_model_factory)(str(best_weights_path))
    detected_count = 0
    for image_path in positive_image_paths:
        try:
            predictions = model.predict(
                source=str(image_path),
                conf=0.01,
                verbose=False,
                imgsz=640,
                device="cpu",
            )
        except Exception:
            predictions = []
        if any(_detected_box_count(prediction) > 0 for prediction in predictions or []):
            detected_count += 1
    return len(positive_image_paths), detected_count


def _validation_metric_summary(
    results_csv_path: Path | None,
    *,
    best_epoch: int | None = None,
) -> dict[str, object]:
    if results_csv_path is None or not results_csv_path.exists():
        return {
            "epoch": None,
            "precision": 0.0,
            "recall": 0.0,
            "map50": 0.0,
            "map50_95": 0.0,
            "fitness": 0.0,
            "allZero": True,
            "diagnostics": {"maxPrecision": 0.0, "maxRecall": 0.0, "maxMap50": 0.0, "maxMap50_95": 0.0},
        }
    with results_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        metric_rows = [{str(key).strip(): value for key, value in row.items()} for row in reader]
    if not metric_rows:
        return _validation_metric_summary(None)
    max_precision = max(_safe_float(row.get("metrics/precision(B)"), 0.0) for row in metric_rows)
    max_recall = max(_safe_float(row.get("metrics/recall(B)"), 0.0) for row in metric_rows)
    max_map50 = max(_safe_float(row.get("metrics/mAP50(B)"), 0.0) for row in metric_rows)
    max_map50_95 = max(_safe_float(row.get("metrics/mAP50-95(B)"), 0.0) for row in metric_rows)
    def fitness(row: dict[str, object]) -> float:
        explicit = str(row.get("fitness") or "").strip()
        if explicit:
            return _safe_float(explicit, float("-inf"))
        return 0.1 * _safe_float(row.get("metrics/mAP50(B)")) + 0.9 * _safe_float(
            row.get("metrics/mAP50-95(B)")
        )

    checkpoint = next(
        (row for row in metric_rows if best_epoch is not None and int(_safe_float(row.get("epoch"))) == best_epoch),
        None,
    )
    if checkpoint is None:
        checkpoint = max(metric_rows, key=fitness)
    precision = _safe_float(checkpoint.get("metrics/precision(B)"), 0.0)
    recall = _safe_float(checkpoint.get("metrics/recall(B)"), 0.0)
    map50 = _safe_float(checkpoint.get("metrics/mAP50(B)"), 0.0)
    map50_95 = _safe_float(checkpoint.get("metrics/mAP50-95(B)"), 0.0)
    return {
        "epoch": int(_safe_float(checkpoint.get("epoch"), 0.0)),
        "precision": precision,
        "recall": recall,
        "map50": map50,
        "map50_95": map50_95,
        "fitness": fitness(checkpoint),
        "allZero": max(precision, recall, map50, map50_95) <= 0.0,
        "diagnostics": {
            "maxPrecision": max_precision,
            "maxRecall": max_recall,
            "maxMap50": max_map50,
            "maxMap50_95": max_map50_95,
        },
    }


def _training_quality_gate_primary_blocker(
    *,
    validation_image_count: int,
    validation_positive_label_image_count: int,
    all_validation_metrics_zero: bool,
    proposal_window_sanity_required: bool,
    proposal_window_validation_positive_image_count: int,
    proposal_window_sanity_detected_image_count: int,
    local_positive_sanity_detected_image_count: int,
    train_val_overlap_count: int = 0,
    provenance_hashes_present: bool = True,
) -> str | None:
    if train_val_overlap_count:
        return "train_val_image_overlap"
    if validation_image_count <= 0:
        return "validation_split_empty"
    if validation_positive_label_image_count <= 0:
        return "validation_split_has_no_positive_labels"
    if all_validation_metrics_zero:
        return "zero_validation_metrics"
    if proposal_window_sanity_required and proposal_window_validation_positive_image_count <= 0:
        return "proposal_window_validation_has_no_positive_labels"
    if proposal_window_sanity_required and proposal_window_sanity_detected_image_count <= 0:
        return "proposal_window_sanity_zero_detections"
    if local_positive_sanity_detected_image_count <= 0:
        return "local_positive_sanity_zero_detections"
    if not provenance_hashes_present:
        return "provenance_hash_missing"
    return None


def _batch_outcome_analysis(summary: dict[str, object]) -> dict[str, object]:
    gate_passed = bool(summary.get("trainingQualityGatePassed"))
    primary_blocker = summary.get("trainingQualityGatePrimaryBlocker")
    if gate_passed:
        english_summary = (
            "The training-quality gate passed, so this candidate has an informative validation split and at least some local positive-detection signal."
        )
        english_decision = (
            "This gate achieved its goal. The candidate may be considered evaluation-ready from a training-quality perspective, but the roadmap still stays in Phase 3 until bounded evaluation wins."
        )
        fixes: list[str] = []
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "The training-quality gate failed. This candidate should not be treated as evaluation-ready until the validation or local-sanity blocker is fixed."
        )
        english_decision = (
            f"The gate did not achieve its goal, so bounded detector evaluation must stay blocked while we fix the current blocker: {blocker_text}."
        )
        fixes = [
            "Repair the validation split so it contains positive labels and remains leakage-safe at the curation-unit level.",
            "Keep the roadmap pinned on evaluate_touchline_detector_candidate until the training-quality gate passes.",
        ]
        if primary_blocker == "local_positive_sanity_zero_detections":
            fixes.insert(
                0,
                "Inspect a small set of positive crops locally and verify the trained detector produces at least some raw detections before spending GPU evaluation time.",
            )
        if primary_blocker == "proposal_window_validation_has_no_positive_labels":
            fixes.insert(
                0,
                "Repair the runtime-aligned proposal-window validation slice so it still contains positive images before bounded evaluation.",
            )
        if primary_blocker == "proposal_window_sanity_zero_detections":
            fixes.insert(
                0,
                "Inspect the runtime-aligned proposal-window validation images and verify the detector produces at least some live-window detections before bounded evaluation.",
            )
    return {
        "batchGoal": "Verify that the trained detector artifact has an informative validation split and non-zero local positive-detection sanity signal before bounded evaluation.",
        "goalAchieved": gate_passed,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingQualityGatePassed": gate_passed,
        "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        "brainstormFixes": fixes,
    }


def run_training_quality_gate(
    *,
    candidate_root: Path,
    dataset_yaml_path: Path,
    model_factory: Callable[[str], object] | None = None,
) -> dict[str, object]:
    candidate_root = Path(candidate_root)
    dataset_yaml_path = Path(dataset_yaml_path)
    training_summary_path = candidate_root / "training_run_summary.json"
    training_summary = {}
    if training_summary_path.exists():
        try:
            loaded = json.loads(training_summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            training_summary = loaded

    parsed_dataset = _parse_dataset_yaml(dataset_yaml_path)
    dataset_root = Path(str(parsed_dataset.get("path") or dataset_yaml_path.parent))
    if not dataset_root.is_absolute():
        dataset_root = (dataset_yaml_path.parent / dataset_root).resolve()
    train_images_dir = _resolve_split_dir(dataset_yaml_path, dataset_root, str(parsed_dataset.get("train", "images/train")))
    val_images_dir = _resolve_split_dir(dataset_yaml_path, dataset_root, str(parsed_dataset.get("val", "images/val")))
    train_labels_dir = Path(str(train_images_dir).replace("/images/", "/labels/"))
    val_labels_dir = Path(str(val_images_dir).replace("/images/", "/labels/"))

    train_image_paths, _train_positive_count, _train_empty_count = _split_image_and_label_counts(
        images_dir=train_images_dir,
        labels_dir=train_labels_dir,
    )
    val_image_paths, validation_positive_label_image_count, validation_empty_label_image_count = (
        _split_image_and_label_counts(
            images_dir=val_images_dir,
            labels_dir=val_labels_dir,
        )
    )
    validation_image_count = len(val_image_paths)
    validation_informative = validation_image_count > 0 and validation_positive_label_image_count > 0
    train_hashes = {_sha256(path) for path in train_image_paths}
    val_hashes = {_sha256(path) for path in val_image_paths}
    train_val_overlap = sorted((train_hashes & val_hashes) - {None})

    def candidate_path(value: object, default: Path | None = None) -> Path | None:
        if value is None:
            return default
        path = Path(str(value))
        return path if path.is_absolute() else candidate_root / path

    best_weights_path = candidate_path(training_summary.get("bestWeightsPath"), candidate_root / "weights" / "best.pt")
    results_csv_path = candidate_path(training_summary.get("resultsCsvPath"), candidate_root / "results.csv")
    dataset_manifest_path = candidate_path(training_summary.get("datasetManifestPath"))
    training_config_path = candidate_path(training_summary.get("trainingConfigPath"))
    raw_best_epoch = training_summary.get("bestEpoch")
    checkpoint_metrics = _validation_metric_summary(
        results_csv_path,
        best_epoch=int(raw_best_epoch) if isinstance(raw_best_epoch, (int, float)) else None,
    )
    provenance_hashes = {
        "datasetConfigSha256": _sha256(dataset_yaml_path),
        "datasetManifestSha256": _sha256(dataset_manifest_path),
        "trainingConfigSha256": _sha256(training_config_path),
        "bestWeightsSha256": _sha256(best_weights_path),
    }

    positive_image_paths = _positive_label_image_paths(
        train_images_dir=train_images_dir,
        train_labels_dir=train_labels_dir,
        val_images_dir=val_images_dir,
        val_labels_dir=val_labels_dir,
    )
    local_positive_sanity_image_count, local_positive_sanity_detected_image_count = _run_local_positive_sanity(
        best_weights_path=best_weights_path,
        positive_image_paths=positive_image_paths,
        model_factory=model_factory,
    )

    proposal_window_alignment_report = _load_proposal_window_alignment_report(dataset_yaml_path)
    proposal_window_sanity_required = (
        str(proposal_window_alignment_report.get("windowFamily") or "").strip() == "proposal_windows_075"
    )
    val_positive_image_paths = _positive_label_image_paths_for_split(
        images_dir=val_images_dir,
        labels_dir=val_labels_dir,
    )
    if proposal_window_sanity_required:
        (
            proposal_window_positive_image_count,
            proposal_window_sanity_detected_image_count,
        ) = _run_local_positive_sanity(
            best_weights_path=best_weights_path,
            positive_image_paths=val_positive_image_paths,
            model_factory=model_factory,
        )
        proposal_window_sanity_detection_rate = (
            round(
                proposal_window_sanity_detected_image_count / proposal_window_positive_image_count,
                8,
            )
            if proposal_window_positive_image_count > 0
            else 0.0
        )
        proposal_window_sanity_window_kind_counts = dict(
            proposal_window_alignment_report.get("validationPositiveWindowKindCounts")
            or proposal_window_alignment_report.get("positiveWindowKindCounts")
            or {}
        )
    else:
        proposal_window_positive_image_count = 0
        proposal_window_sanity_detected_image_count = 0
        proposal_window_sanity_detection_rate = 0.0
        proposal_window_sanity_window_kind_counts = {}

    primary_blocker = _training_quality_gate_primary_blocker(
        validation_image_count=validation_image_count,
        validation_positive_label_image_count=validation_positive_label_image_count,
        all_validation_metrics_zero=bool(checkpoint_metrics["allZero"]),
        proposal_window_sanity_required=proposal_window_sanity_required,
        proposal_window_validation_positive_image_count=proposal_window_positive_image_count,
        proposal_window_sanity_detected_image_count=proposal_window_sanity_detected_image_count,
        local_positive_sanity_detected_image_count=local_positive_sanity_detected_image_count,
        train_val_overlap_count=len(train_val_overlap),
        provenance_hashes_present=all(provenance_hashes.values()),
    )
    training_quality_gate_passed = primary_blocker is None
    summary = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": training_summary.get("trainingCandidateName") or candidate_root.name,
        "candidateRoot": str(candidate_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "validationImageCount": validation_image_count,
        "validationPositiveLabelImageCount": validation_positive_label_image_count,
        "validationEmptyLabelImageCount": validation_empty_label_image_count,
        "validationInformative": validation_informative,
        "checkpointEpoch": checkpoint_metrics["epoch"],
        "checkpointFitness": round(float(checkpoint_metrics["fitness"]), 8),
        "checkpointValidationMetrics": {
            key: round(float(checkpoint_metrics[key]), 8)
            for key in ("precision", "recall", "map50", "map50_95")
        },
        "trainingProgressDiagnostics": {
            key: round(float(value), 8)
            for key, value in dict(checkpoint_metrics["diagnostics"]).items()
        },
        "maxValidationPrecision": round(float(checkpoint_metrics["precision"]), 8),
        "maxValidationRecall": round(float(checkpoint_metrics["recall"]), 8),
        "maxValidationMap50": round(float(checkpoint_metrics["map50"]), 8),
        "trainValOverlapCount": len(train_val_overlap),
        "trainValOverlapSha256": train_val_overlap,
        **provenance_hashes,
        "localPositiveSanityImageCount": local_positive_sanity_image_count,
        "localPositiveSanityDetectedImageCount": local_positive_sanity_detected_image_count,
        "proposalWindowValidationImageCount": validation_image_count if proposal_window_sanity_required else 0,
        "proposalWindowValidationPositiveImageCount": proposal_window_positive_image_count,
        "proposalWindowSanityDetectedImageCount": proposal_window_sanity_detected_image_count,
        "proposalWindowSanityDetectionRate": proposal_window_sanity_detection_rate,
        "proposalWindowSanityWindowKindCounts": proposal_window_sanity_window_kind_counts,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "trainingQualityGatePrimaryBlocker": primary_blocker,
        "readyForDetectorEvaluation": training_quality_gate_passed,
    }

    gate_root = candidate_root / "training_quality_gate_v1"
    batch_outcome_analysis = _batch_outcome_analysis(summary)
    _write_json(gate_root / "quality_gate_summary.json", summary)
    _write_json(gate_root / "batch_outcome_analysis.json", batch_outcome_analysis)
    return summary
