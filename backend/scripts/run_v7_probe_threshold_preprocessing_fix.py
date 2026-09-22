from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections.abc import Callable
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_EXPORT_BATCH_NAME = "touchline_detector_candidate_v7_training_v1"
DEFAULT_BATCH_NAME = "v7_probe_threshold_preprocessing_fix"
DEFAULT_OUTPUT_DIR_NAME = "v7_probe_threshold_preprocessing_fix_v1"
DEFAULT_CONF_VALUES = [0.001, 0.01, 0.05, 0.1, 0.25]
DEFAULT_IMGSZ_VALUES = [640, 960]
MAX_POSITIVE_IMAGES = 40

BLOCKER_OFFLINE_DETECTIONS = "v7_offline_detections_available"
BLOCKER_WRONG_CLASS = "v7_class_index_mismatch"
BLOCKER_MODEL_QUALITY = "v7_model_quality_failure"
BLOCKER_ARTIFACT_GAP = "v7_threshold_preprocessing_artifact_gap"

NEXT_THRESHOLD_CONTRACT_FIX = "v7_probe_threshold_contract_fix"
NEXT_CLASS_CONTRACT_FIX = "v7_probe_class_index_contract_fix"
NEXT_TRAINING_REFRESH = "v7_training_data_quality_refresh"
NEXT_ARTIFACT_REFRESH = "v7_evaluation_proof_artifact_refresh"

Predictor = Callable[..., dict[str, object]]


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


def _load_json(path: Path, *, required: bool = True) -> dict[str, object]:
    if not path.exists():
        if required:
            raise FileNotFoundError(str(path))
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _resolve_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _nested_path(payload: dict[str, object], *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _export_root(storage_root: Path) -> Path:
    return Path(storage_root) / "training_prep" / DEFAULT_EXPORT_BATCH_NAME / "yolo_export"


def _positive_image_paths(export_root: Path) -> list[Path]:
    image_paths: list[Path] = []
    for split in ("train", "val"):
        labels_root = export_root / "labels" / split
        images_root = export_root / "images" / split
        if not labels_root.exists():
            continue
        for label_path in sorted(labels_root.glob("*.txt")):
            if not label_path.read_text(encoding="utf-8").strip():
                continue
            for suffix in (".jpg", ".jpeg", ".png"):
                image_path = images_root / f"{label_path.stem}{suffix}"
                if image_path.exists():
                    image_paths.append(image_path)
                    break
    return image_paths[:MAX_POSITIVE_IMAGES]


def _model_path(contract: dict[str, object]) -> Path | None:
    return _resolve_path(contract.get("candidateAuxiliaryBallModelPath") or _nested_path(contract, "candidateWeights", "bestWeightsPath"))


def _boxes_from_result(result: object) -> list[dict[str, object]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    confidences = getattr(boxes, "conf", None)
    classes = getattr(boxes, "cls", None)
    if confidences is None or classes is None:
        return []
    try:
        conf_values = confidences.detach().cpu().tolist()
    except AttributeError:
        conf_values = list(confidences)
    try:
        class_values = classes.detach().cpu().tolist()
    except AttributeError:
        class_values = list(classes)
    rows = []
    for conf, class_id in zip(conf_values, class_values, strict=False):
        rows.append({"confidence": _safe_float(conf), "classId": _safe_int(class_id, -1)})
    return rows


def _ultralytics_predict(
    *,
    model_path: Path,
    image_paths: list[Path],
    conf_values: list[float],
    imgsz_values: list[int],
) -> dict[str, object]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    per_image_best: dict[str, dict[str, object]] = {
        str(path): {"imagePath": str(path), "bestConfidence": 0.0, "bestClassId": None, "detected": False}
        for path in image_paths
    }
    grid: list[dict[str, object]] = []
    for imgsz in imgsz_values:
        for conf in conf_values:
            detected_paths: set[str] = set()
            wrong_class_paths: set[str] = set()
            for image_path in image_paths:
                results = model.predict(
                    source=str(image_path),
                    imgsz=int(imgsz),
                    conf=float(conf),
                    verbose=False,
                    device="cpu",
                )
                rows: list[dict[str, object]] = []
                for result in results:
                    rows.extend(_boxes_from_result(result))
                if rows:
                    detected_paths.add(str(image_path))
                if rows and all(_safe_int(row.get("classId"), -1) != 0 for row in rows):
                    wrong_class_paths.add(str(image_path))
                best = max(rows, key=lambda row: _safe_float(row.get("confidence"), 0.0), default=None)
                if best is not None:
                    current = per_image_best[str(image_path)]
                    if _safe_float(best.get("confidence"), 0.0) > _safe_float(current.get("bestConfidence"), 0.0):
                        current["bestConfidence"] = _safe_float(best.get("confidence"), 0.0)
                        current["bestClassId"] = _safe_int(best.get("classId"), -1)
                        current["detected"] = True
                        current["bestConfThreshold"] = float(conf)
                        current["bestImageSize"] = int(imgsz)
            grid.append(
                {
                    "imgsz": int(imgsz),
                    "conf": float(conf),
                    "detectedFrameCount": len(detected_paths),
                    "wrongClassDetectionCount": len(wrong_class_paths),
                }
            )
    detected_count = sum(1 for item in per_image_best.values() if item.get("detected"))
    wrong_class_count = sum(1 for item in per_image_best.values() if item.get("detected") and _safe_int(item.get("bestClassId"), -1) != 0)
    return {
        "modelPath": str(model_path),
        "grid": grid,
        "perImage": list(per_image_best.values()),
        "detectedImageCount": detected_count,
        "wrongClassDetectionCount": wrong_class_count,
    }


def _classify(positive_count: int, matrix: dict[str, object], model_path: Path | None) -> tuple[str, str, list[str]]:
    if model_path is None or not model_path.exists() or positive_count <= 0:
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_ARTIFACT_REFRESH,
            ["The audit lacks an existing v7 model path or positive YOLO export images."],
        )
    detected = _safe_int(matrix.get("detectedImageCount"), 0)
    wrong_class = _safe_int(matrix.get("wrongClassDetectionCount"), 0)
    if detected > 0 and wrong_class >= detected:
        return (
            BLOCKER_WRONG_CLASS,
            NEXT_CLASS_CONTRACT_FIX,
            ["Offline v7 inference detects objects, but the best detections are not class 0."],
        )
    if detected > 0:
        return (
            BLOCKER_OFFLINE_DETECTIONS,
            NEXT_THRESHOLD_CONTRACT_FIX,
            ["Offline v7 inference detects reviewed-positive examples, so proof preprocessing/threshold contract is the likely gate."],
        )
    return (
        BLOCKER_MODEL_QUALITY,
        NEXT_TRAINING_REFRESH,
        ["Offline v7 inference still detects no reviewed-positive/training-positive examples across the audit grid."],
    )


def _markdown_summary(summary: dict[str, object], outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Probe Threshold Preprocessing Fix",
            "",
            f"- Goal achieved: `{outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Positive images audited: `{summary.get('positiveImageCount')}`",
            f"- Offline detected images: `{summary.get('offlineDetectedImageCount')}`",
            "",
            str(outcome.get("englishSummary") or ""),
            "",
            str(outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_probe_threshold_preprocessing_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    conf_values: list[float] | None = None,
    imgsz_values: list[int] | None = None,
    predictor: Predictor | None = None,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    export_root = _export_root(storage_root)
    contract = _load_json(candidate_root / "evaluation_contract.json")
    integration_summary = _load_json(
        candidate_root / "v7_probe_assist_integration_audit_v1" / "v7_probe_assist_integration_summary.json",
        required=False,
    )
    model_path = _model_path(contract)
    image_paths = _positive_image_paths(export_root)
    conf_values = list(conf_values or DEFAULT_CONF_VALUES)
    imgsz_values = list(imgsz_values or DEFAULT_IMGSZ_VALUES)
    if model_path is not None and model_path.exists() and image_paths:
        predictor = predictor or _ultralytics_predict
        matrix = predictor(
            model_path=model_path,
            image_paths=image_paths,
            conf_values=conf_values,
            imgsz_values=imgsz_values,
        )
    else:
        matrix = {
            "modelPath": str(model_path) if model_path else None,
            "grid": [],
            "perImage": [],
            "detectedImageCount": 0,
            "wrongClassDetectionCount": 0,
        }
    dominant, next_family, reasons = _classify(len(image_paths), matrix, model_path)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "attemptNumber": 1,
        "attemptApproachFamily": "offline_threshold_preprocessing_audit",
        "inputBlockerClass": integration_summary.get("dominantBlockerClass"),
        "modelPath": str(model_path) if model_path else None,
        "modelPathExists": bool(model_path and model_path.exists()),
        "positiveImageCount": len(image_paths),
        "confidenceThresholdsAudited": conf_values,
        "imageSizesAudited": imgsz_values,
        "offlineDetectedImageCount": _safe_int(matrix.get("detectedImageCount"), 0),
        "wrongClassDetectionCount": _safe_int(matrix.get("wrongClassDetectionCount"), 0),
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
    }
    taxonomy = {
        "generatedAt": _utc_now_iso(),
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "classificationReasons": reasons,
        "candidateBlockerClasses": [
            BLOCKER_OFFLINE_DETECTIONS,
            BLOCKER_WRONG_CLASS,
            BLOCKER_MODEL_QUALITY,
            BLOCKER_ARTIFACT_GAP,
        ],
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "decisions": [
            {
                "condition": "offline detections exist for class 0",
                "matched": dominant == BLOCKER_OFFLINE_DETECTIONS,
                "nextCorrectiveFamily": NEXT_THRESHOLD_CONTRACT_FIX,
            },
            {
                "condition": "offline detections exist only under wrong class",
                "matched": dominant == BLOCKER_WRONG_CLASS,
                "nextCorrectiveFamily": NEXT_CLASS_CONTRACT_FIX,
            },
            {
                "condition": "offline detections remain zero",
                "matched": dominant == BLOCKER_MODEL_QUALITY,
                "nextCorrectiveFamily": NEXT_TRAINING_REFRESH,
            },
            {
                "condition": "audit artifacts are incomplete",
                "matched": dominant == BLOCKER_ARTIFACT_GAP,
                "nextCorrectiveFamily": NEXT_ARTIFACT_REFRESH,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Audit whether v7 zero probe signal is caused by threshold/preprocessing mismatch or model/data quality.",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": f"V7 threshold/preprocessing audit classified the blocker as {dominant}.",
        "englishDecision": f"Advance to {next_family}; do not promote v7 or mutate runtime defaults.",
    }
    _write_json(output_root / "v7_probe_threshold_preprocessing_summary.json", summary)
    _write_json(output_root / "offline_inference_threshold_matrix.json", dict(matrix))
    _write_json(output_root / "v7_probe_threshold_preprocessing_taxonomy.json", taxonomy)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, outcome),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--conf", type=float, nargs="*", default=DEFAULT_CONF_VALUES)
    parser.add_argument("--imgsz", type=int, nargs="*", default=DEFAULT_IMGSZ_VALUES)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_v7_probe_threshold_preprocessing_fix(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        conf_values=args.conf,
        imgsz_values=args.imgsz,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
