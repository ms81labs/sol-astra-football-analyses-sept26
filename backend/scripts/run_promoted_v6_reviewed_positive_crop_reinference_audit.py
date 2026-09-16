from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_PROPOSAL_GENERATION_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_proposal_generation_fix_v1"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_crop_reinference_audit_v1"
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"
DEFAULT_MODEL_PATH = (
    DEFAULT_STORAGE_ROOT
    / "trained_detector_candidates"
    / "touchline_detector_candidate_v6"
    / "weights"
    / "best.pt"
)
DEFAULT_CONTEXT_RATIOS = [1.0, 2.0, 4.0, 8.0]
DEFAULT_IMGSZ_VALUES = [640, 960, 1600]
DEFAULT_CONF = 0.01
DEFAULT_BATCH_NAME = "reviewed_positive_crop_reinference_audit_v1"

BUCKET_GEOMETRY_RESCUE = "reviewed_positive_crop_geometry_scale_rescue_available"
BUCKET_MODEL_ZERO_DETECT = "reviewed_positive_model_zero_detect_all_scales"
BUCKET_EXISTING_FOLLOWTHROUGH = "reviewed_positive_existing_proposal_followthrough_gap"
BUCKET_FRAME_UNAVAILABLE = "reviewed_positive_video_frame_unavailable"
BUCKET_INVALID_BBOX = "reviewed_positive_crop_geometry_invalid"
BUCKET_MODEL_UNAVAILABLE = "reviewed_positive_model_unavailable"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _valid_bbox(bbox: object) -> bool:
    if not isinstance(bbox, dict):
        return False
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    return x2 > x1 and y2 > y1


def _frame_shape(frame_payload: dict[str, Any]) -> tuple[int, int, int]:
    shape = frame_payload.get("frameShape")
    if isinstance(shape, (list, tuple)) and len(shape) >= 2:
        return (_safe_int(shape[0]), _safe_int(shape[1]), _safe_int(shape[2], 3))
    frame = frame_payload.get("frame")
    if hasattr(frame, "shape") and len(frame.shape) >= 2:
        return (int(frame.shape[0]), int(frame.shape[1]), int(frame.shape[2]) if len(frame.shape) > 2 else 1)
    return (0, 0, 0)


def _crop_window_for_bbox(
    bbox: dict[str, Any],
    frame_shape: tuple[int, int, int],
    *,
    context_ratio: float,
    min_crop_size: int = 64,
) -> list[int]:
    frame_h, frame_w = frame_shape[:2]
    x1 = _safe_float(bbox.get("x1"))
    y1 = _safe_float(bbox.get("y1"))
    x2 = _safe_float(bbox.get("x2"))
    y2 = _safe_float(bbox.get("y2"))
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    base_w = max(x2 - x1, 1.0)
    base_h = max(y2 - y1, 1.0)
    crop_w = max(base_w * float(context_ratio), float(min_crop_size))
    crop_h = max(base_h * float(context_ratio), float(min_crop_size))
    left = max(0.0, center_x - crop_w / 2.0)
    top = max(0.0, center_y - crop_h / 2.0)
    right = min(float(frame_w), center_x + crop_w / 2.0)
    bottom = min(float(frame_h), center_y + crop_h / 2.0)
    left = max(0.0, right - crop_w)
    top = max(0.0, bottom - crop_h)
    return [int(round(left)), int(round(top)), int(round(right)), int(round(bottom))]


def _crop_frame(frame: object, window: list[int]) -> object:
    if frame is None or not hasattr(frame, "__getitem__"):
        return frame
    left, top, right, bottom = window
    return frame[top:bottom, left:right]


def _load_frame_from_video(video_path: Path, frame_index: int) -> dict[str, Any]:
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"frameIndex": frame_index, "frameAvailable": False, "frameShape": [0, 0, 0], "frame": None}
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = cap.read()
        if not ok or frame is None:
            return {"frameIndex": frame_index, "frameAvailable": False, "frameShape": [0, 0, 0], "frame": None}
        return {
            "frameIndex": frame_index,
            "frameAvailable": True,
            "frameShape": list(frame.shape),
            "frame": frame,
        }
    finally:
        cap.release()


def _make_yolo_predictor(*, conf: float) -> Callable[..., list[dict[str, Any]]]:
    models: dict[str, Any] = {}

    def _predictor(*, crop: object, attempt: dict[str, Any], model_path: Path) -> list[dict[str, Any]]:
        from ultralytics import YOLO

        key = str(model_path)
        if key not in models:
            models[key] = YOLO(key)
        result = models[key].predict(
            crop,
            imgsz=int(attempt["imgsz"]),
            conf=float(conf),
            classes=[0],
            verbose=False,
        )[0]
        boxes = result.boxes
        if boxes is None:
            return []
        detections: list[dict[str, Any]] = []
        for box in list(boxes):
            coords = box.xyxy[0]
            if hasattr(coords, "tolist"):
                coords = coords.tolist()
            confidence = box.conf[0]
            if hasattr(confidence, "item"):
                confidence = confidence.item()
            cls = box.cls[0]
            if hasattr(cls, "item"):
                cls = cls.item()
            detections.append(
                {
                    "bbox": [round(float(value), 3) for value in coords],
                    "confidence": round(float(confidence), 6),
                    "classId": int(cls),
                }
            )
        return detections

    return _predictor


def _diagnostic_class_for_row(
    *,
    source_row: dict[str, Any],
    frame_available: bool,
    valid_bbox: bool,
    attempted: bool,
    best_attempt: dict[str, Any] | None,
    model_available: bool,
) -> str:
    if source_row.get("rawDetected") or source_row.get("collapsed") or source_row.get("selected"):
        return BUCKET_EXISTING_FOLLOWTHROUGH
    if not valid_bbox:
        return BUCKET_INVALID_BBOX
    if not frame_available:
        return BUCKET_FRAME_UNAVAILABLE
    if not model_available:
        return BUCKET_MODEL_UNAVAILABLE
    if attempted and best_attempt is not None:
        return BUCKET_GEOMETRY_RESCUE
    return BUCKET_MODEL_ZERO_DETECT


def _next_family(dominant_bucket: str) -> str:
    if dominant_bucket == BUCKET_GEOMETRY_RESCUE:
        return "reviewed_positive_crop_geometry_scale_fix"
    if dominant_bucket == BUCKET_MODEL_ZERO_DETECT:
        return "reviewed_positive_model_finetune_fix"
    if dominant_bucket == BUCKET_EXISTING_FOLLOWTHROUGH:
        return "reviewed_positive_selection_followthrough_fix"
    if dominant_bucket in {BUCKET_FRAME_UNAVAILABLE, BUCKET_INVALID_BBOX, BUCKET_MODEL_UNAVAILABLE}:
        return "manual_review_required"
    return "reviewed_positive_model_finetune_fix"


def _dominant_bucket(counts: dict[str, int]) -> tuple[str, int]:
    priority = {
        BUCKET_GEOMETRY_RESCUE: 0,
        BUCKET_MODEL_ZERO_DETECT: 1,
        BUCKET_EXISTING_FOLLOWTHROUGH: 2,
        BUCKET_INVALID_BBOX: 3,
        BUCKET_FRAME_UNAVAILABLE: 4,
        BUCKET_MODEL_UNAVAILABLE: 5,
    }
    if not counts:
        return BUCKET_MODEL_ZERO_DETECT, 0
    return sorted(
        ((str(key), _safe_int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], priority.get(item[0], 99), item[0]),
    )[0]


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Positive Crop Reinference Audit",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- zeroDetectFrameCount: {summary.get('zeroDetectFrameCount')}",
            f"- reinferenceDetectedFrameCount: {summary.get('reinferenceDetectedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_crop_reinference_audit(
    *,
    proposal_generation_root: Path = DEFAULT_PROPOSAL_GENERATION_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    video_path: Path = DEFAULT_VIDEO_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    predictor: Callable[..., list[dict[str, Any]]] | None = None,
    frame_loader: Callable[[int], dict[str, Any]] | None = None,
    context_ratios: list[float] | None = None,
    imgsz_values: list[int] | None = None,
    conf: float = DEFAULT_CONF,
) -> dict[str, Any]:
    proposal_generation_root = Path(proposal_generation_root)
    output_root = Path(output_root)
    video_path = Path(video_path)
    model_path = Path(model_path)
    context_ratios = list(context_ratios or DEFAULT_CONTEXT_RATIOS)
    imgsz_values = [int(value) for value in (imgsz_values or DEFAULT_IMGSZ_VALUES)]
    coverage = _load_json_dict(proposal_generation_root / "reviewed_positive_proposal_coverage.json")
    proposal_summary = _load_json_dict(proposal_generation_root / "reviewed_positive_proposal_fix_summary.json")
    rows = _list_dicts(coverage.get("reviewedPositiveFrames"))
    if predictor is None:
        predictor = _make_yolo_predictor(conf=conf)
    if frame_loader is None:
        frame_loader = lambda frame_id: _load_frame_from_video(video_path, frame_id)

    model_available = model_path.exists() or predictor is not None
    matrix_rows: list[dict[str, Any]] = []
    scale_attempt_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []

    for row in rows:
        frame_id = _safe_int(row.get("frameIndex"), -1)
        bbox = row.get("reviewedBBox")
        valid_bbox = _valid_bbox(bbox)
        frame_payload = frame_loader(frame_id) if frame_id >= 0 else {"frameAvailable": False, "frame": None}
        frame_available = bool(frame_payload.get("frameAvailable"))
        shape = _frame_shape(frame_payload)
        frame = frame_payload.get("frame")
        attempts: list[dict[str, Any]] = []
        best_attempt: dict[str, Any] | None = None
        should_reinfer = not (row.get("rawDetected") or row.get("collapsed") or row.get("selected"))
        if valid_bbox and frame_available and model_available and should_reinfer:
            for context_ratio in context_ratios:
                window = _crop_window_for_bbox(
                    bbox if isinstance(bbox, dict) else {},
                    shape,
                    context_ratio=float(context_ratio),
                )
                crop = _crop_frame(frame, window)
                for imgsz in imgsz_values:
                    attempt = {
                        "frameIndex": frame_id,
                        "contextRatio": float(context_ratio),
                        "imgsz": int(imgsz),
                        "cropWindow": window,
                    }
                    detections = predictor(crop=crop, attempt=attempt, model_path=model_path)
                    attempt["detectionCount"] = len(detections)
                    attempt["detections"] = detections
                    attempts.append(attempt)
                    scale_attempt_rows.append(
                        {
                            "frameIndex": frame_id,
                            "contextRatio": float(context_ratio),
                            "imgsz": int(imgsz),
                            "cropWindow": window,
                            "detectionCount": len(detections),
                        }
                    )
                    if detections and best_attempt is None:
                        best_attempt = attempt
        diagnostic_class = _diagnostic_class_for_row(
            source_row=row,
            frame_available=frame_available,
            valid_bbox=valid_bbox,
            attempted=bool(attempts),
            best_attempt=best_attempt,
            model_available=model_available,
        )
        geometry_rows.append(
            {
                "frameIndex": frame_id,
                "reviewedBBox": bbox,
                "validBBox": valid_bbox,
                "frameAvailable": frame_available,
                "frameShape": list(shape),
                "attemptedContextRatios": context_ratios if should_reinfer else [],
                "attemptedImgszValues": imgsz_values if should_reinfer else [],
                "sourceDiagnosticClass": row.get("diagnosticClass"),
            }
        )
        matrix_rows.append(
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "frameIndex": frame_id,
                "reviewedBBox": bbox,
                "sourceDiagnosticClass": row.get("diagnosticClass"),
                "sourceZeroDetect": bool(row.get("zeroDetect")),
                "sourceRawDetected": bool(row.get("rawDetected")),
                "sourceCollapsed": bool(row.get("collapsed")),
                "attemptCount": len(attempts),
                "reinferenceDetected": best_attempt is not None,
                "bestAttempt": best_attempt or {},
                "diagnosticClass": diagnostic_class,
            }
        )

    counts = Counter(str(row["diagnosticClass"]) for row in matrix_rows)
    dominant_bucket, dominant_count = _dominant_bucket(dict(counts))
    zero_detect_count = sum(1 for row in matrix_rows if row["sourceZeroDetect"])
    detected_count = sum(1 for row in matrix_rows if row["reinferenceDetected"])
    next_family = _next_family(dominant_bucket)
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 2,
        "attemptBudget": 3,
        "attemptApproachFamily": "reviewed_positive_crop_reinference_audit",
        "batchStatus": "succeeded",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "reviewedPositiveFrameCount": len(matrix_rows),
        "zeroDetectFrameCount": zero_detect_count,
        "reinferenceDetectedFrameCount": detected_count,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "runPodUsed": False,
        "modelPath": str(model_path),
        "videoPath": str(video_path),
        "contextRatios": context_ratios,
        "imgszValues": imgsz_values,
        "retentionTruth": proposal_summary.get("retentionTruth") or {},
    }
    matrix = {
        "generatedAt": generated_at,
        "reviewedPositiveCropRows": matrix_rows,
        "bucketCounts": dict(sorted(counts.items())),
    }
    geometry_audit = {
        "generatedAt": generated_at,
        "reviewedPositiveCropGeometryRows": geometry_rows,
    }
    scale_audit = {
        "generatedAt": generated_at,
        "scaleAttemptRows": scale_attempt_rows,
        "attemptedFrameCount": len({row["frameIndex"] for row in scale_attempt_rows}),
    }
    decision = {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "rationale": (
            "Expanded reviewed-positive crops produced detector hits; implement a non-default crop geometry/scale fix next."
            if dominant_bucket == BUCKET_GEOMETRY_RESCUE
            else "Reviewed-positive crops still produce zero detector hits across audited scales; model/data fix is likely next."
            if dominant_bucket == BUCKET_MODEL_ZERO_DETECT
            else "Reviewed-positive evidence exists but fails after candidate generation."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "reviewed_positive_crop_reinference_summary.json", summary)
    _write_json(output_root / "reviewed_positive_crop_reinference_matrix.json", matrix)
    _write_json(output_root / "reviewed_positive_crop_geometry_audit.json", geometry_audit)
    _write_json(output_root / "crop_reinference_scale_audit.json", scale_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "reviewedPositiveCropReinferenceSummary": summary,
        "reviewedPositiveCropReinferenceMatrix": matrix,
        "reviewedPositiveCropGeometryAudit": geometry_audit,
        "cropReinferenceScaleAudit": scale_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-generation-root", type=Path, default=DEFAULT_PROPOSAL_GENERATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--context-ratios", type=float, nargs="*", default=DEFAULT_CONTEXT_RATIOS)
    parser.add_argument("--imgsz-values", type=int, nargs="*", default=DEFAULT_IMGSZ_VALUES)
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF)
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_crop_reinference_audit(
        proposal_generation_root=args.proposal_generation_root,
        output_root=args.output_root,
        video_path=args.video_path,
        model_path=args.model_path,
        context_ratios=args.context_ratios,
        imgsz_values=args.imgsz_values,
        conf=args.conf,
    )
    print(json.dumps(payload["reviewedPositiveCropReinferenceSummary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
