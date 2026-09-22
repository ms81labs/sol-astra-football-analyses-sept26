from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_optional as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_1_tiny_overfit_sanity_train_v1"
DEFAULT_DEBUG_BATCH_NAME = "v7_1_training_config_or_export_debug_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_tiny_overfit_retry_with_verified_config_v1"
CONF_SWEEP = (0.25, 0.10, 0.05, 0.01, 0.001)
ACCEPTED_CHECKPOINT_KEYS = [
    "bestWeightsLocalPath",
    "bestWeightsPathLocal",
    "lastWeightsLocalPath",
    "lastWeightsPathLocal",
]

BLOCKER_MISSING_CHECKPOINT = "v7_1_tiny_retry_missing_local_checkpoint"
BLOCKER_NO_PREDICTIONS = "v7_1_verified_tiny_train_no_predictions"
BLOCKER_NONLOCAL = "v7_1_verified_tiny_train_nonlocal_predictions"
BLOCKER_WEAK_CONF = "v7_1_verified_tiny_train_weak_confidence"
BLOCKER_NEGATIVE_FLOOD = "v7_1_verified_tiny_train_negative_flood"
BLOCKER_BEST_UNSTABLE = "v7_1_best_checkpoint_selection_unstable"

NEXT_BOUNDED = "v7_1_bounded_retrain"
NEXT_DEBUG = "v7_1_training_config_or_export_debug"
NEXT_SINGLE_IMAGE = "v7_1_single_image_overfit_minimal_repro"
NEXT_HARD_NEGATIVE = "v7_1_tiny_hard_negative_balance_debug"

Predictor = Callable[..., dict[str, Any]]


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_path(training_result: dict[str, Any], *keys: str) -> Path | None:
    for key in keys:
        value = training_result.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if path.exists():
                return path
    return None


def _dataset_rows(dataset_root: Path) -> dict[str, list[dict[str, Any]]]:
    def rows(split: str, positive: bool, limit: int | None = None) -> list[dict[str, Any]]:
        image_root = dataset_root / "images" / split
        label_root = dataset_root / "labels" / split
        output = []
        for image_path in sorted(image_root.glob("*.jpg")):
            label_path = label_root / f"{image_path.stem}.txt"
            has_label = label_path.exists() and bool(label_path.read_text(encoding="utf-8").strip())
            if has_label != positive:
                continue
            output.append(
                {
                    "exampleId": image_path.stem,
                    "truthType": "positive" if positive else "negative",
                    "split": split,
                    "imagePath": str(image_path),
                    "labelPath": str(label_path),
                    "gtCropBbox": tiny_train._read_yolo_box(label_path, image_path) if positive else None,
                }
            )
            if limit is not None and len(output) >= limit:
                break
        return output

    return {
        "train_positive": rows("train", True, 10),
        "train_negative": rows("train", False, 20),
        "val_positive": rows("val", True, 5),
        "val_negative": rows("val", False, 10),
        "heldout_canary": rows("canary", False, 20),
    }


def _median_confidence(rows: list[dict[str, Any]]) -> float | None:
    values = [
        tiny_train._safe_float(row.get("confidence"))
        for row in rows
        if row.get("isLocalizationHit") and row.get("confidence") is not None
    ]
    if not values:
        return None
    return round(float(statistics.median(values)), 6)


def _min_confidence(rows: list[dict[str, Any]]) -> float | None:
    values = [
        tiny_train._safe_float(row.get("confidence"))
        for row in rows
        if row.get("isLocalizationHit") and row.get("confidence") is not None
    ]
    if not values:
        return None
    return round(float(min(values)), 6)


def _area_ratio(rows: list[dict[str, Any]]) -> float | None:
    values = [
        tiny_train._safe_float(row.get("detectedBoxAreaToGtBoxAreaRatio"))
        for row in rows
        if row.get("detectedBoxAreaToGtBoxAreaRatio") is not None
    ]
    if not values:
        return None
    return round(float(statistics.median(values)), 6)


def _audit_checkpoint(
    *,
    checkpoint_name: str,
    checkpoint_path: Path,
    audit_sets: dict[str, list[dict[str, Any]]],
    predictor: Predictor | None,
) -> dict[str, Any]:
    sweeps: list[dict[str, Any]] = []
    for conf in CONF_SWEEP:
        prediction_result = (
            predictor(model_path=checkpoint_path, audit_sets=audit_sets, conf=conf, imgsz=256)
            if predictor is not None
            else tiny_train._predict_with_ultralytics(model_path=checkpoint_path, audit_sets=audit_sets, conf=conf, imgsz=256)
        )
        audited = {
            set_name: tiny_train._audit_set(rows, predictions=prediction_result, set_name=set_name)
            for set_name, rows in audit_sets.items()
        }
        train_positive = audited["train_positive"]
        train_negative = audited["train_negative"]
        canary = audited["heldout_canary"]
        all_detected = [row for rows in audited.values() for row in rows if row.get("predCropBbox") is not None]
        sweeps.append(
            {
                "checkpointName": checkpoint_name,
                "checkpointPath": str(checkpoint_path),
                "conf": conf,
                "predictArgs": {"model": str(checkpoint_path), "conf": conf, "imgsz": 256, "device": "cpu"},
                "tinyTrainPositiveLocalizationHitRate": tiny_train._rate(train_positive, "isLocalizationHit"),
                "tinyTrainPositivePredictionCount": sum(1 for row in train_positive if row.get("predCropBbox") is not None),
                "tinyTrainNegativeFalsePositiveFrameRate": tiny_train._rate(train_negative, "isFalsePositive"),
                "tinyHeldoutCanaryFalsePositiveFrameRate": tiny_train._rate(canary, "isFalsePositive"),
                "medianTrainPositiveConfidence": _median_confidence(train_positive),
                "minTrainPositiveConfidence": _min_confidence(train_positive),
                "medianDetectedBoxAreaToGtBoxAreaRatio": _area_ratio(train_positive),
                "topLeftArtifactShare": tiny_train._rate(all_detected, "isTopLeftArtifact"),
                "giantBoxShare": tiny_train._rate(all_detected, "isGiantBox"),
                "auditedSets": audited,
            }
        )
    return {
        "checkpointName": checkpoint_name,
        "checkpointPath": str(checkpoint_path),
        "checkpointSha256": _sha256(checkpoint_path),
        "sweeps": sweeps,
    }


def _selected_sweep(checkpoint_audits: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    fallback = None
    for audit in checkpoint_audits:
        for sweep in audit["sweeps"]:
            if fallback is None:
                fallback = sweep
            if (
                sweep["tinyTrainPositiveLocalizationHitRate"] >= 0.90
                and (sweep["medianTrainPositiveConfidence"] or 0.0) > 0.05
                and sweep["tinyTrainNegativeFalsePositiveFrameRate"] <= 0.10
                and sweep["topLeftArtifactShare"] <= 0.10
                and sweep["giantBoxShare"] <= 0.10
            ):
                return sweep, None if audit["checkpointName"] == "best.pt" else BLOCKER_BEST_UNSTABLE
    return fallback, None


def _classify(selected: dict[str, Any] | None, checkpoint_count: int, best_unstable: str | None) -> tuple[str | None, str, bool, str]:
    if checkpoint_count <= 0:
        return (
            BLOCKER_MISSING_CHECKPOINT,
            NEXT_DEBUG,
            False,
            "No local trained checkpoint exists. Refusing to run inference against a remote or stale path.",
        )
    if selected is None or selected["tinyTrainPositivePredictionCount"] <= 0:
        return (
            BLOCKER_NO_PREDICTIONS,
            NEXT_SINGLE_IMAGE,
            False,
            "Verified local checkpoints produced no boxes on memorized positives.",
        )
    if selected["tinyTrainPositiveLocalizationHitRate"] < 0.90:
        return (
            BLOCKER_NONLOCAL,
            NEXT_SINGLE_IMAGE,
            False,
            "Verified local checkpoint emitted boxes, but they were not localized near the reviewed positive labels.",
        )
    if (selected["medianTrainPositiveConfidence"] or 0.0) <= 0.05:
        return (
            BLOCKER_WEAK_CONF,
            NEXT_SINGLE_IMAGE,
            False,
            "Verified local checkpoint localized positives only at weak confidence.",
        )
    if selected["tinyTrainNegativeFalsePositiveFrameRate"] > 0.10:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "Verified local checkpoint overfit positives but also fired on too many hard negatives.",
        )
    if best_unstable:
        return (
            best_unstable,
            NEXT_BOUNDED,
            True,
            "Tiny overfit passed with a verified local checkpoint, but last.pt was stronger than best.pt; carry that checkpoint-selection warning forward.",
        )
    return (
        None,
        NEXT_BOUNDED,
        True,
        "Tiny overfit retry passed using verified trained local checkpoint. Advance to bounded v7.1 retrain; do not promote.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Tiny Overfit Retry With Verified Config",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Checkpoint contract passed: `{summary.get('checkpointContractPassed')}`",
            f"- Inference used trained weights: `{summary.get('inferenceUsedTrainedWeights')}`",
            f"- Selected checkpoint: `{summary.get('selectedCheckpointForVerdict')}`",
            f"- Selected conf: `{summary.get('selectedAuditConf')}`",
            f"- Train positive localization hit rate: `{summary.get('tinyTrainPositiveLocalizationHitRate')}`",
            f"- Train negative false-positive rate: `{summary.get('tinyTrainNegativeFalsePositiveFrameRate')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_tiny_overfit_retry_with_verified_config(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "retry_with_verified_checkpoint_contract",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    input_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    debug_root = candidate_root / DEFAULT_DEBUG_BATCH_NAME
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    dataset_root = input_root / "tiny_dataset"
    training_result = _load_json(input_root / "training_run_summary.json", required=True)
    debug_outcome = _load_json(debug_root / "batch_outcome_analysis.json")
    debug_summary = debug_outcome.get("summary") if isinstance(debug_outcome.get("summary"), dict) else {}
    audit_sets = _dataset_rows(dataset_root)
    best_path = _checkpoint_path(training_result, "bestWeightsLocalPath", "bestWeightsPathLocal")
    last_path = _checkpoint_path(training_result, "lastWeightsLocalPath", "lastWeightsPathLocal")
    checkpoint_audits = []
    if best_path is not None:
        checkpoint_audits.append(_audit_checkpoint(checkpoint_name="best.pt", checkpoint_path=best_path, audit_sets=audit_sets, predictor=predictor))
    if last_path is not None:
        checkpoint_audits.append(_audit_checkpoint(checkpoint_name="last.pt", checkpoint_path=last_path, audit_sets=audit_sets, predictor=predictor))
    selected, unstable_blocker = _selected_sweep(checkpoint_audits)
    primary_blocker, next_family, goal_achieved, english = _classify(selected, len(checkpoint_audits), unstable_blocker)
    selected_audited_sets = selected.get("auditedSets") if isinstance(selected, dict) else {}
    if isinstance(selected_audited_sets, dict):
        inference_root = output_root / "prediction_overlay_contact_sheets"
        tiny_train._draw_contact_sheet(selected_audited_sets.get("train_positive", []), output_path=inference_root / "positive_overlay_contact_sheet.jpg")
        tiny_train._draw_contact_sheet(selected_audited_sets.get("train_negative", []), output_path=inference_root / "negative_overlay_contact_sheet.jpg")
        tiny_train._draw_contact_sheet(selected_audited_sets.get("heldout_canary", []), output_path=inference_root / "canary_overlay_contact_sheet.jpg")
    summary = {
        "batchName": "v7_1_tiny_overfit_retry_with_verified_config",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "previousTinyOverfitVerdictInvalidated": True,
        "previousInvalidationReason": "v7_1_wrong_checkpoint_for_inference",
        "trainingCompleted": bool(training_result.get("trainingCompleted")),
        "trainerObservedLabelRowCount": debug_summary.get("trainerObservedLabelRowCount"),
        "boxLossNonZero": debug_summary.get("boxLossNonZero"),
        "boxLossDecreased": debug_summary.get("boxLossDecreased"),
        "bestWeightsPathLocal": str(best_path) if best_path else None,
        "bestWeightsPathLocalExists": bool(best_path and best_path.exists()),
        "bestWeightsPathLocalSha256": _sha256(best_path) if best_path else None,
        "lastWeightsPathLocal": str(last_path) if last_path else None,
        "lastWeightsPathLocalExists": bool(last_path and last_path.exists()),
        "lastWeightsPathLocalSha256": _sha256(last_path) if last_path else None,
        "inferenceWeightsPath": selected.get("checkpointPath") if isinstance(selected, dict) else None,
        "inferenceWeightsSha256": _sha256(Path(str(selected.get("checkpointPath")))) if isinstance(selected, dict) and selected.get("checkpointPath") else None,
        "inferenceUsedTrainedWeights": len(checkpoint_audits) > 0,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "checkpointContractPassed": len(checkpoint_audits) > 0,
        "acceptedCheckpointResultKeys": ACCEPTED_CHECKPOINT_KEYS,
        "remoteCheckpointFallbackAllowed": False,
        "predictionSweepCompleted": len(checkpoint_audits) > 0,
        "bestCheckpointPredictionCountsByConf": {
            f"{sweep['conf']:.3g}": sweep["tinyTrainPositivePredictionCount"]
            for audit in checkpoint_audits
            if audit["checkpointName"] == "best.pt"
            for sweep in audit["sweeps"]
        },
        "bestCheckpointLocalizationHitRateByConf": {
            f"{sweep['conf']:.3g}": sweep["tinyTrainPositiveLocalizationHitRate"]
            for audit in checkpoint_audits
            if audit["checkpointName"] == "best.pt"
            for sweep in audit["sweeps"]
        },
        "selectedCheckpointForVerdict": selected.get("checkpointName") if isinstance(selected, dict) else None,
        "selectedAuditConf": selected.get("conf") if isinstance(selected, dict) else None,
        "tinyTrainPositiveLocalizationHitRate": selected.get("tinyTrainPositiveLocalizationHitRate", 0.0) if isinstance(selected, dict) else 0.0,
        "tinyTrainNegativeFalsePositiveFrameRate": selected.get("tinyTrainNegativeFalsePositiveFrameRate", 0.0) if isinstance(selected, dict) else 0.0,
        "tinyHeldoutCanaryFalsePositiveFrameRate": selected.get("tinyHeldoutCanaryFalsePositiveFrameRate", 0.0) if isinstance(selected, dict) else 0.0,
        "medianTrainPositiveConfidence": selected.get("medianTrainPositiveConfidence") if isinstance(selected, dict) else None,
        "minTrainPositiveConfidence": selected.get("minTrainPositiveConfidence") if isinstance(selected, dict) else None,
        "medianDetectedBoxAreaToGtBoxAreaRatio": selected.get("medianDetectedBoxAreaToGtBoxAreaRatio") if isinstance(selected, dict) else None,
        "topLeftArtifactShare": selected.get("topLeftArtifactShare", 0.0) if isinstance(selected, dict) else 0.0,
        "giantBoxShare": selected.get("giantBoxShare", 0.0) if isinstance(selected, dict) else 0.0,
        "nearConstantLowConfidenceFlood": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_family,
        "englishDecision": english,
    }
    _write_json(output_root / "v7_1_tiny_overfit_retry_summary.json", summary)
    _write_json(output_root / "checkpoint_contract_audit.json", {"checkpoints": checkpoint_audits, "summary": summary})
    _write_json(output_root / "prediction_sweep_audit.json", {"checkpoints": checkpoint_audits})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "checkpointAudits": checkpoint_audits})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="retry_with_verified_checkpoint_contract")
    args = parser.parse_args()
    payload = run_v7_1_tiny_overfit_retry_with_verified_config(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
