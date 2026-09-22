from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_optional as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_1_tiny_overfit_sanity_train_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_training_config_or_export_debug_v1"

BLOCKER_LABEL_INGESTION = "v7_1_yolo_trainer_label_ingestion_failure"
BLOCKER_TRAIN_BATCH_LABELS = "v7_1_train_batch_labels_missing"
BLOCKER_WRONG_CHECKPOINT = "v7_1_wrong_checkpoint_for_inference"
BLOCKER_RESULTS_NOT_LEARNING = "v7_1_results_csv_loss_not_learning"
BLOCKER_SINGLE_IMAGE = "v7_1_single_image_overfit_failure"
BLOCKER_DATASET_BALANCE = "v7_1_tiny_dataset_balance_or_hparam_failure"
BLOCKER_MISSING = "v7_1_tiny_train_missing_artifacts"

NEXT_LABEL_PATH_FIX = "v7_1_data_yaml_label_path_fix"
NEXT_TINY_RETRY = "v7_1_tiny_overfit_retry_with_verified_config"
NEXT_MODEL_HPARAM = "v7_1_model_task_or_training_hparam_fix"
NEXT_MANUAL = "manual_review_required"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_data_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload: dict[str, Any] = {"names": {}}
    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, value = raw_line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if current_key == "nc":
                try:
                    payload[current_key] = int(value)
                except ValueError:
                    payload[current_key] = value
            elif current_key == "names" and value:
                payload[current_key] = value
            elif current_key != "names":
                payload[current_key] = value
        elif current_key == "names" and ":" in raw_line:
            key, value = raw_line.strip().split(":", 1)
            payload.setdefault("names", {})[key.strip()] = value.strip()
    return payload


def _label_files(dataset_root: Path, split: str) -> list[Path]:
    return sorted((dataset_root / "labels" / split).glob("*.txt"))


def _image_files(dataset_root: Path, split: str) -> list[Path]:
    return sorted((dataset_root / "images" / split).glob("*.jpg"))


def _label_rows(label_path: Path) -> list[list[str]]:
    text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
    if not text:
        return []
    return [line.split() for line in text.splitlines() if line.strip()]


def _dataset_loader_audit(dataset_root: Path) -> dict[str, Any]:
    data_yaml = _read_data_yaml(dataset_root / "data.yaml")
    train_images = _image_files(dataset_root, "train")
    train_labels = _label_files(dataset_root, "train")
    class_ids: set[int] = set()
    positive_label_images = 0
    background_images = 0
    label_row_count = 0
    malformed = []
    label_by_stem = {path.stem: path for path in train_labels}
    for image_path in train_images:
        rows = _label_rows(label_by_stem.get(image_path.stem, Path()))
        if rows:
            positive_label_images += 1
        else:
            background_images += 1
        label_row_count += len(rows)
        for row in rows:
            if len(row) != 5:
                malformed.append({"labelPath": str(label_by_stem.get(image_path.stem)), "row": row})
                continue
            try:
                class_ids.add(int(float(row[0])))
            except ValueError:
                malformed.append({"labelPath": str(label_by_stem.get(image_path.stem)), "row": row})
    return {
        "generatedAt": _utc_now_iso(),
        "datasetRoot": str(dataset_root),
        "dataYamlPath": str(dataset_root / "data.yaml"),
        "tinyTrainImageCount": len(train_images),
        "tinyTrainPositiveImageCount": positive_label_images,
        "tinyTrainBackgroundImageCount": background_images,
        "trainerObservedPositiveLabelImageCount": positive_label_images,
        "trainerObservedBackgroundImageCount": background_images,
        "trainerObservedLabelRowCount": label_row_count,
        "trainerObservedClassIdSet": sorted(class_ids),
        "trainerObservedNames": data_yaml.get("names") or {},
        "trainerObservedNc": data_yaml.get("nc"),
        "malformedLabelRowCount": len(malformed),
        "malformedLabelRows": malformed[:20],
    }


def _loss_values(rows: list[dict[str, str]], key: str) -> list[float]:
    return [_safe_float(row.get(key), 0.0) for row in rows if row.get(key) not in (None, "")]


def _results_csv_audit(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"generatedAt": _utc_now_iso(), "resultsCsvPath": str(path), "resultsCsvExists": False}
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    box = _loss_values(rows, "train/box_loss")
    cls = _loss_values(rows, "train/cls_loss")
    dfl = _loss_values(rows, "train/dfl_loss")
    def first(values: list[float]) -> float | None:
        return values[0] if values else None
    def last(values: list[float]) -> float | None:
        return values[-1] if values else None
    return {
        "generatedAt": _utc_now_iso(),
        "resultsCsvPath": str(path),
        "resultsCsvExists": True,
        "epochCount": len(rows),
        "firstEpochBoxLoss": first(box),
        "lastEpochBoxLoss": last(box),
        "firstEpochClsLoss": first(cls),
        "lastEpochClsLoss": last(cls),
        "firstEpochDflLoss": first(dfl),
        "lastEpochDflLoss": last(dfl),
        "boxLossNonZero": any(value > 0 for value in box),
        "boxLossDecreased": bool(len(box) >= 2 and box[-1] < box[0]),
        "clsLossNonZero": any(value > 0 for value in cls),
        "dflLossNonZero": any(value > 0 for value in dfl),
    }


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_hash_audit(training_result: dict[str, Any]) -> dict[str, Any]:
    best_local_legacy = training_result.get("bestWeightsLocalPath")
    best_local_actual = training_result.get("bestWeightsPathLocal")
    last_local_actual = training_result.get("lastWeightsPathLocal")
    remote_best = Path(str(training_result.get("bestWeightsPath") or ""))
    best_actual_path = Path(str(best_local_actual or ""))
    last_actual_path = Path(str(last_local_actual or ""))
    return {
        "generatedAt": _utc_now_iso(),
        "bestWeightsPath": training_result.get("bestWeightsPath"),
        "bestWeightsPathLocal": best_local_actual,
        "lastWeightsPathLocal": last_local_actual,
        "tinyScriptLegacyBestWeightsLocalPathPresent": bool(best_local_legacy),
        "bestWeightsPathLocalExists": best_actual_path.exists(),
        "lastWeightsPathLocalExists": last_actual_path.exists(),
        "remoteBestWeightsPathExistsLocally": remote_best.exists(),
        "bestWeightsPathLocalSizeBytes": best_actual_path.stat().st_size if best_actual_path.exists() else 0,
        "bestWeightsPathLocalSha256": _sha256(best_actual_path),
        "lastWeightsPathLocalSha256": _sha256(last_actual_path),
        "wrongCheckpointContractLikely": bool(best_actual_path.exists() and not best_local_legacy and not remote_best.exists()),
    }


def _cache_audit(dataset_root: Path) -> dict[str, Any]:
    caches = sorted(dataset_root.glob("*.cache")) + sorted((dataset_root / "labels").glob("*.cache"))
    return {
        "generatedAt": _utc_now_iso(),
        "cacheFileCount": len(caches),
        "cacheFiles": [str(path) for path in caches],
        "staleCacheSuspected": False,
    }


def _classify(
    *,
    loader: dict[str, Any],
    results: dict[str, Any],
    checkpoint: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if loader.get("trainerObservedLabelRowCount", 0) <= 0:
        return (
            BLOCKER_LABEL_INGESTION,
            NEXT_LABEL_PATH_FIX,
            True,
            "The tiny dataset has no positive label rows from the trainer-facing layout; repair the data.yaml/image-label path contract before retrying.",
        )
    if loader.get("trainerObservedPositiveLabelImageCount", 0) <= 0:
        return (
            BLOCKER_TRAIN_BATCH_LABELS,
            NEXT_LABEL_PATH_FIX,
            True,
            "The trainer-facing batch has no positive label images; repair the training dataset layout.",
        )
    if checkpoint.get("wrongCheckpointContractLikely"):
        return (
            BLOCKER_WRONG_CHECKPOINT,
            NEXT_TINY_RETRY,
            True,
            "Training produced local weights, but the tiny inference path looked for the wrong local-weight key and likely evaluated no trained checkpoint.",
        )
    if not results.get("boxLossNonZero"):
        return (
            BLOCKER_RESULTS_NOT_LEARNING,
            NEXT_MODEL_HPARAM,
            True,
            "Training completed but box loss is absent or zero, so labels may not be participating in optimization.",
        )
    if results.get("boxLossNonZero") and not results.get("boxLossDecreased"):
        return (
            BLOCKER_SINGLE_IMAGE,
            NEXT_MODEL_HPARAM,
            True,
            "Labels appear loaded but loss did not improve; isolate with a one-image overfit or model/config debug.",
        )
    return (
        BLOCKER_DATASET_BALANCE,
        NEXT_TINY_RETRY,
        True,
        "Label loading and loss behavior look plausible; retry tiny overfit with the verified checkpoint/inference contract before bounded retrain.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Training Config Or Export Debug",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Trainer observed label rows: `{summary.get('trainerObservedLabelRowCount')}`",
            f"- Box loss nonzero: `{summary.get('boxLossNonZero')}`",
            f"- Box loss decreased: `{summary.get('boxLossDecreased')}`",
            f"- Inference checkpoint contract mismatch: `{summary.get('wrongCheckpointContractLikely')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_training_config_or_export_debug(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    input_batch_name: str = DEFAULT_INPUT_BATCH_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "tiny_train_label_loading_debug",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    input_root = candidate_root / input_batch_name
    output_root = candidate_root / output_dir_name
    dataset_root = input_root / "tiny_dataset"
    training_result = _load_json(input_root / "training_run_summary.json")
    previous_audit = _load_json(input_root / "v7_1_tiny_overfit_sanity_train_audit.json")
    loader = _dataset_loader_audit(dataset_root)
    results = _results_csv_audit(input_root / "train_run" / "results.csv")
    checkpoint = _checkpoint_hash_audit(training_result)
    cache = _cache_audit(dataset_root)
    primary_blocker, next_family, goal_achieved, english = _classify(
        loader=loader,
        results=results,
        checkpoint=checkpoint,
    )
    summary = {
        "batchName": "v7_1_training_config_or_export_debug",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "tinyOverfitPreviousBlocker": previous_audit.get("primaryBlocker"),
        "trainerObservedLabelRowCount": loader.get("trainerObservedLabelRowCount"),
        "trainerObservedPositiveLabelImageCount": loader.get("trainerObservedPositiveLabelImageCount"),
        "trainerObservedBackgroundImageCount": loader.get("trainerObservedBackgroundImageCount"),
        "trainerObservedClassIdSet": loader.get("trainerObservedClassIdSet"),
        "trainerObservedNames": loader.get("trainerObservedNames"),
        "trainerObservedNc": loader.get("trainerObservedNc"),
        "boxLossNonZero": results.get("boxLossNonZero"),
        "boxLossDecreased": results.get("boxLossDecreased"),
        "wrongCheckpointContractLikely": checkpoint.get("wrongCheckpointContractLikely"),
        "inferenceUsedTrainedWeights": not checkpoint.get("wrongCheckpointContractLikely"),
        "singleImageOverfitCompleted": False,
        "singleImageLocalizationHit": None,
        "primaryBlocker": primary_blocker,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_family,
        "englishDecision": english,
    }
    snapshot = {
        "generatedAt": _utc_now_iso(),
        "inputRoot": str(input_root),
        "datasetRoot": str(dataset_root),
        "previousTinyAudit": previous_audit,
        "trainingResultKeys": sorted(training_result.keys()),
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "label_rows_loaded", "observed": loader.get("trainerObservedLabelRowCount", 0) > 0, "blocker": BLOCKER_LABEL_INGESTION},
            {"condition": "local_checkpoint_contract_valid", "observed": not checkpoint.get("wrongCheckpointContractLikely"), "blocker": BLOCKER_WRONG_CHECKPOINT},
            {"condition": "box_loss_nonzero", "observed": bool(results.get("boxLossNonZero")), "blocker": BLOCKER_RESULTS_NOT_LEARNING},
            {"condition": "box_loss_decreased", "observed": bool(results.get("boxLossDecreased")), "blocker": BLOCKER_SINGLE_IMAGE},
            {"condition": "debug_diagnosis_complete", "observed": goal_achieved, "nextFamily": next_family},
        ],
    }
    outcome = {
        "summary": summary,
        "inputAuditedExportSnapshot": snapshot,
        "tinyTrainDatasetDebugAudit": loader,
        "yoloDatasetLoaderAudit": loader,
        "yoloCacheAudit": cache,
        "resultsCsvAudit": results,
        "checkpointHashAudit": checkpoint,
    }
    _write_json(output_root / "input_audited_export_snapshot.json", snapshot)
    _write_json(output_root / "tiny_train_dataset_debug_audit.json", loader)
    _write_json(output_root / "yolo_dataset_loader_audit.json", loader)
    _write_json(output_root / "yolo_cache_audit.json", cache)
    _write_json(output_root / "training_args_resolved.json", training_result.get("trainKwargs") or {})
    (output_root / "training_log_excerpt.txt").write_text(str(training_result.get("errorMessage") or ""), encoding="utf-8")
    _write_json(output_root / "results_csv_audit.json", results)
    _write_json(output_root / "checkpoint_hash_audit.json", checkpoint)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="tiny_train_label_loading_debug")
    args = parser.parse_args()
    payload = run_v7_1_training_config_or_export_debug(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
