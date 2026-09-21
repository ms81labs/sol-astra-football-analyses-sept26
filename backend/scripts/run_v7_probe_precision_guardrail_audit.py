from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import statistics
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_BATCH_NAME = "v7_probe_precision_guardrail_audit"
DEFAULT_OUTPUT_DIR_NAME = "v7_probe_precision_guardrail_audit_v1"
DEFAULT_TRAINING_EXPORT_BATCH_NAME = "touchline_detector_candidate_v7_training_v1"
LOW_CONF_PROFILE = "ball_probe_only_v1_low_conf_001"

BLOCKER_THRESHOLD_AVAILABLE = "v7_threshold_precision_contract_available"
BLOCKER_GEOMETRY_AVAILABLE = "v7_bbox_geometry_precision_contract_available"
BLOCKER_LOW_CONF_FLOOD = "v7_low_conf_global_false_positive_flood"
BLOCKER_TOP_LEFT_ARTIFACT_FLOOD = "v7_low_conf_top_left_artifact_flood"
BLOCKER_FRAME_HIT_NOT_LOCALIZATION = "v7_positive_frame_hit_not_localization_hit"
BLOCKER_SIGNAL_GONE = "v7_probe_threshold_contract_signal_missing"
BLOCKER_ARTIFACT_GAP = "v7_probe_precision_artifact_gap"

NEXT_THRESHOLD_CONTRACT = "v7_probe_threshold_sweep_contract"
NEXT_GEOMETRY_CONTRACT = "v7_probe_bbox_geometry_contract_fix"
NEXT_TRAINING_REFRESH = "v7_training_data_quality_refresh"
NEXT_CONTRACT_REFRESH = "v7_probe_threshold_contract_fix"
NEXT_ARTIFACT_REFRESH = "v7_evaluation_proof_artifact_refresh"

CONFIDENCE_THRESHOLDS = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
GEOMETRY_AREA_THRESHOLDS = [1000.0, 2500.0, 5000.0, 10000.0, 20000.0]


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
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


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _export_manifest_path(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "training_prep"
        / DEFAULT_TRAINING_EXPORT_BATCH_NAME
        / "yolo_export"
        / "split_manifest.json"
    )


def _training_manifest_path(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "touchline_detector_candidate_v7_training_prep_v1"
        / "v7_training_manifest.json"
    )


def _source_box_area(row: dict[str, object]) -> float:
    width = max(_safe_float(row.get("Source_X2")) - _safe_float(row.get("Source_X1")), 0.0)
    height = max(_safe_float(row.get("Source_Y2")) - _safe_float(row.get("Source_Y1")), 0.0)
    return width * height


def _row_source_box(row: dict[str, object]) -> tuple[float, float, float, float] | None:
    try:
        return (
            float(row["Source_X1"]),
            float(row["Source_Y1"]),
            float(row["Source_X2"]),
            float(row["Source_Y2"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _manifest_bbox(row: dict[str, object]) -> tuple[float, float, float, float] | None:
    bbox = row.get("bbox")
    if not isinstance(bbox, dict):
        return None
    try:
        return (
            float(bbox["x1"]),
            float(bbox["y1"]),
            float(bbox["x2"]),
            float(bbox["y2"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _box_area(box: tuple[float, float, float, float]) -> float:
    return max(float(box[2]) - float(box[0]), 0.0) * max(float(box[3]) - float(box[1]), 0.0)


def _box_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0


def _box_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1 = max(float(a[0]), float(b[0]))
    iy1 = max(float(a[1]), float(b[1]))
    ix2 = min(float(a[2]), float(b[2]))
    iy2 = min(float(a[3]), float(b[3]))
    intersection = max(ix2 - ix1, 0.0) * max(iy2 - iy1, 0.0)
    union = _box_area(a) + _box_area(b) - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay = _box_center(a)
    bx, by = _box_center(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _frame_id(row: dict[str, object]) -> int | None:
    try:
        return int(row.get("Frame_ID"))
    except (TypeError, ValueError):
        return None


def _load_training_frame_sets(split_manifest: dict[str, object]) -> tuple[set[int], set[int]]:
    positives: set[int] = set()
    negatives: set[int] = set()
    for row in split_manifest.get("exportedExamples") or []:
        if not isinstance(row, dict):
            continue
        frame = _safe_int(row.get("frameIndex"), -1)
        if frame < 0:
            continue
        if bool(row.get("positiveLabelWritten")):
            positives.add(frame)
        else:
            negatives.add(frame)
    return positives, negatives


def _load_positive_bboxes(training_manifest: dict[str, object]) -> dict[int, tuple[float, float, float, float]]:
    positive_bboxes: dict[int, tuple[float, float, float, float]] = {}
    for row in training_manifest.get("positiveExamples") or []:
        if not isinstance(row, dict):
            continue
        frame = _safe_int(row.get("frameIndex"), -1)
        bbox = _manifest_bbox(row)
        if frame >= 0 and bbox is not None:
            positive_bboxes[frame] = bbox
    return positive_bboxes


def _latest_candidate_pod_cycle(storage_root: Path, contract_summary: dict[str, object]) -> Path | None:
    proof_source = _resolve_path(contract_summary.get("proofSource"))
    if proof_source and proof_source.exists():
        return proof_source
    pod_root = Path(storage_root) / "pod_cycles"
    if not pod_root.exists():
        return None
    candidates = [
        path
        for path in pod_root.glob("touchline-detector-candidate-v7-probe-assist-baseline-*")
        if (path / "ball_truth_layers.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "ball_truth_layers.json").stat().st_mtime)


def _probe_rows_from_truth_layers(truth_layers: dict[str, object]) -> list[dict[str, object]]:
    probe_layer = truth_layers.get("probeObservedBall")
    if isinstance(probe_layer, dict):
        rows = probe_layer.get("rawRows") or probe_layer.get("filteredRows")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    accepted_layer = truth_layers.get("acceptedBall")
    if isinstance(accepted_layer, dict) and isinstance(accepted_layer.get("rows"), list):
        return [dict(row) for row in accepted_layer["rows"] if isinstance(row, dict)]
    return []


def _rows_by_frame(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    best_by_frame: dict[int, dict[str, object]] = {}
    for row in rows:
        frame = _frame_id(row)
        if frame is None:
            continue
        current = best_by_frame.get(frame)
        if current is None or _safe_float(row.get("Conf")) > _safe_float(current.get("Conf")):
            best_by_frame[frame] = row
    return best_by_frame


def _threshold_sweep(
    rows_by_frame: dict[int, dict[str, object]],
    positive_frames: set[int],
    negative_frames: set[int],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    matrix: list[dict[str, object]] = []
    best: dict[str, object] | None = None
    for threshold in CONFIDENCE_THRESHOLDS:
        hit_frames = {
            frame
            for frame, row in rows_by_frame.items()
            if _safe_float(row.get("Conf")) >= float(threshold)
        }
        positive_hits = len(positive_frames & hit_frames)
        negative_hits = len(negative_frames & hit_frames)
        positive_rate = positive_hits / max(len(positive_frames), 1)
        negative_rate = negative_hits / max(len(negative_frames), 1)
        row = {
            "confidenceThreshold": threshold,
            "hitFrameCount": len(hit_frames),
            "positiveHitCount": positive_hits,
            "negativeHitCount": negative_hits,
            "positiveHitRate": round(positive_rate, 3),
            "negativeHitRate": round(negative_rate, 3),
            "precisionSafe": positive_rate >= 0.5 and negative_rate <= 0.25,
        }
        matrix.append(row)
        if row["precisionSafe"] and (
            best is None
            or (
                float(row["positiveHitRate"]),
                -float(row["negativeHitRate"]),
                float(row["confidenceThreshold"]),
            )
            > (
                float(best["positiveHitRate"]),
                -float(best["negativeHitRate"]),
                float(best["confidenceThreshold"]),
            )
        ):
            best = row
    return matrix, best


def _geometry_sweep(
    rows_by_frame: dict[int, dict[str, object]],
    positive_frames: set[int],
    negative_frames: set[int],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    matrix: list[dict[str, object]] = []
    best: dict[str, object] | None = None
    for area_threshold in GEOMETRY_AREA_THRESHOLDS:
        hit_frames = {
            frame
            for frame, row in rows_by_frame.items()
            if _source_box_area(row) <= float(area_threshold)
        }
        positive_hits = len(positive_frames & hit_frames)
        negative_hits = len(negative_frames & hit_frames)
        positive_rate = positive_hits / max(len(positive_frames), 1)
        negative_rate = negative_hits / max(len(negative_frames), 1)
        row = {
            "maxSourceBoxArea": area_threshold,
            "hitFrameCount": len(hit_frames),
            "positiveHitCount": positive_hits,
            "negativeHitCount": negative_hits,
            "positiveHitRate": round(positive_rate, 3),
            "negativeHitRate": round(negative_rate, 3),
            "precisionSafe": positive_rate >= 0.5 and negative_rate <= 0.25,
        }
        matrix.append(row)
        if row["precisionSafe"] and (
            best is None
            or (
                float(row["positiveHitRate"]),
                -float(row["negativeHitRate"]),
                -float(row["maxSourceBoxArea"]),
            )
            > (
                float(best["positiveHitRate"]),
                -float(best["negativeHitRate"]),
                -float(best["maxSourceBoxArea"]),
            )
        ):
            best = row
    return matrix, best


def _frame_matrix(
    rows_by_frame: dict[int, dict[str, object]],
    positive_frames: set[int],
    negative_frames: set[int],
) -> list[dict[str, object]]:
    frames = sorted(set(rows_by_frame) | positive_frames | negative_frames)
    matrix = []
    for frame in frames:
        row = rows_by_frame.get(frame, {})
        matrix.append(
            {
                "frameIndex": frame,
                "isReviewedPositiveTrainingFrame": frame in positive_frames,
                "isReviewedNegativeTrainingFrame": frame in negative_frames,
                "probeHit": frame in rows_by_frame,
                "confidence": _safe_float(row.get("Conf"), 0.0) if row else None,
                "sourceBoxArea": round(_source_box_area(row), 3) if row else None,
            }
        )
    return matrix


def _localization_audit(
    rows_by_frame: dict[int, dict[str, object]],
    positive_bboxes: dict[int, tuple[float, float, float, float]],
    *,
    center_threshold_px: float = 32.0,
    iou_threshold: float = 0.1,
) -> dict[str, object]:
    rows = []
    center_hit_count = 0
    iou_hit_count = 0
    localization_hit_count = 0
    center_distances: list[float] = []
    area_ratios: list[float] = []
    for frame, gt_box in sorted(positive_bboxes.items()):
        probe_row = rows_by_frame.get(frame)
        detected_box = _row_source_box(probe_row) if probe_row else None
        center_distance = None
        iou = None
        area_ratio = None
        center_hit = False
        iou_hit = False
        if detected_box is not None:
            center_distance = _center_distance(detected_box, gt_box)
            iou = _box_iou(detected_box, gt_box)
            gt_area = _box_area(gt_box)
            area_ratio = _box_area(detected_box) / gt_area if gt_area > 0 else None
            center_distances.append(float(center_distance))
            if area_ratio is not None:
                area_ratios.append(float(area_ratio))
            center_hit = float(center_distance) <= float(center_threshold_px)
            iou_hit = float(iou) >= float(iou_threshold)
        localization_hit = center_hit or iou_hit
        center_hit_count += int(center_hit)
        iou_hit_count += int(iou_hit)
        localization_hit_count += int(localization_hit)
        rows.append(
            {
                "frameIndex": frame,
                "frameHit": probe_row is not None,
                "centerDistancePx": round(float(center_distance), 3) if center_distance is not None else None,
                "iou": round(float(iou), 6) if iou is not None else None,
                "detectedBoxAreaToGtBoxAreaRatio": round(float(area_ratio), 3) if area_ratio is not None else None,
                "centerDistanceHit": center_hit,
                "iouHit": iou_hit,
                "localizationHit": localization_hit,
            }
        )
    total = max(len(positive_bboxes), 1)
    return {
        "generatedAt": _utc_now_iso(),
        "positiveReviewedBBoxCount": len(positive_bboxes),
        "positiveFrameHitCount": sum(1 for frame in positive_bboxes if frame in rows_by_frame),
        "positiveFrameHitRate": round(
            sum(1 for frame in positive_bboxes if frame in rows_by_frame) / total,
            3,
        ),
        "positiveCenterDistanceHitCount": center_hit_count,
        "positiveCenterDistanceHitRate": round(center_hit_count / total, 3),
        "positiveIoUHitCount": iou_hit_count,
        "positiveIoUHitRate": round(iou_hit_count / total, 3),
        "positiveLocalizationHitCount": localization_hit_count,
        "positiveLocalizationHitRate": round(localization_hit_count / total, 3),
        "medianCenterDistanceToReviewedBBox": round(_median(center_distances), 3),
        "medianDetectedBoxAreaToGtBoxAreaRatio": round(_median(area_ratios), 3),
        "centerDistanceThresholdPx": center_threshold_px,
        "iouThreshold": iou_threshold,
        "frames": rows,
    }


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _classify(
    *,
    raw_row_count: int,
    positive_hit_rate: float,
    negative_hit_rate: float,
    frame_hit_rate: float,
    best_threshold: dict[str, object] | None,
    best_geometry: dict[str, object] | None,
    has_required_artifacts: bool,
    positive_localization_hit_rate: float,
    top_left_box_share: float,
    large_box_share: float,
    near_constant_confidence_share: float,
) -> tuple[str, str, list[str]]:
    if not has_required_artifacts:
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_ARTIFACT_REFRESH,
            ["The audit lacks proof rows or v7 training split truth."],
        )
    if raw_row_count <= 0:
        return (
            BLOCKER_SIGNAL_GONE,
            NEXT_CONTRACT_REFRESH,
            ["The low-confidence proof contract no longer exposes raw probe rows."],
        )
    if best_threshold is not None:
        return (
            BLOCKER_THRESHOLD_AVAILABLE,
            NEXT_THRESHOLD_CONTRACT,
            ["A confidence threshold preserves reviewed-positive hits while suppressing reviewed-negative hits."],
        )
    if best_geometry is not None:
        return (
            BLOCKER_GEOMETRY_AVAILABLE,
            NEXT_GEOMETRY_CONTRACT,
            ["Source-box geometry can preserve reviewed-positive hits while suppressing reviewed-negative hits."],
        )
    if positive_hit_rate > 0 and positive_localization_hit_rate <= 0.0 and top_left_box_share >= 0.8:
        return (
            BLOCKER_TOP_LEFT_ARTIFACT_FLOOD,
            NEXT_TRAINING_REFRESH,
            ["Frame-level positive hits are all non-localizing top-left/large-box probe artifacts."],
        )
    if positive_hit_rate > 0 and positive_localization_hit_rate <= 0.0:
        return (
            BLOCKER_FRAME_HIT_NOT_LOCALIZATION,
            NEXT_TRAINING_REFRESH,
            ["Positive frame hits do not overlap reviewed ball boxes by IoU or center-distance."],
        )
    if frame_hit_rate >= 0.8 or negative_hit_rate >= 0.5:
        return (
            BLOCKER_LOW_CONF_FLOOD,
            NEXT_TRAINING_REFRESH,
            ["The low-confidence v7 proof hits most sampled frames or too many reviewed negatives with no safe threshold/geometry split."],
        )
    return (
        BLOCKER_ARTIFACT_GAP,
        NEXT_ARTIFACT_REFRESH,
        ["Probe rows exist, but the audit cannot find a deterministic precision-safe contract or dominant flood pattern."],
    )


def _markdown_summary(summary: dict[str, object], outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Probe Precision Guardrail Audit",
            "",
            f"- Goal achieved: `{outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Raw probe row count: `{summary.get('rawProbeRowCount')}`",
            f"- Frame hit rate: `{summary.get('frameHitRate')}`",
            f"- Positive hit rate: `{summary.get('positiveFrameHitRate')}`",
            f"- Positive localization hit rate: `{summary.get('positiveLocalizationHitRate')}`",
            f"- Negative hit rate: `{summary.get('negativeFrameHitRate')}`",
            "",
            str(outcome.get("englishSummary") or ""),
            "",
            str(outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_probe_precision_guardrail_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    contract_summary = _load_json(
        candidate_root / "v7_probe_threshold_contract_fix_v1" / "threshold_contract_summary.json",
        required=False,
    )
    split_manifest = _load_json(_export_manifest_path(storage_root), required=False)
    training_manifest = _load_json(_training_manifest_path(storage_root), required=False)
    proof_root = _latest_candidate_pod_cycle(storage_root, contract_summary)
    truth_layers = _load_json(proof_root / "ball_truth_layers.json", required=False) if proof_root else {}
    proof_summary = _load_json(proof_root / "proof_summary.json", required=False) if proof_root else {}
    trace = _load_json(proof_root / "ball_pipeline_trace.json", required=False) if proof_root else {}
    probe_rows = _probe_rows_from_truth_layers(truth_layers)
    rows_by_frame = _rows_by_frame(probe_rows)
    positive_frames, negative_frames = _load_training_frame_sets(split_manifest)
    positive_bboxes = _load_positive_bboxes(training_manifest)
    frame_count = _safe_int(proof_summary.get("frameCount"), len(rows_by_frame))
    hit_frames = set(rows_by_frame)
    positive_hit_rate = len(positive_frames & hit_frames) / max(len(positive_frames), 1)
    negative_hit_rate = len(negative_frames & hit_frames) / max(len(negative_frames), 1)
    frame_hit_rate = len(hit_frames) / max(frame_count, 1)
    threshold_matrix, best_threshold = _threshold_sweep(rows_by_frame, positive_frames, negative_frames)
    geometry_matrix, best_geometry = _geometry_sweep(rows_by_frame, positive_frames, negative_frames)
    confidences = [_safe_float(row.get("Conf")) for row in probe_rows]
    source_areas = [_source_box_area(row) for row in probe_rows]
    localization_audit = _localization_audit(rows_by_frame, positive_bboxes)
    top_left_box_share = (
        sum(
            1
            for row in probe_rows
            if _safe_float(row.get("Source_X1")) <= 1.0 and _safe_float(row.get("Source_Y1")) <= 1.0
        )
        / max(len(probe_rows), 1)
    )
    gt_areas = [_box_area(box) for box in positive_bboxes.values()]
    median_gt_area = _median(gt_areas)
    large_box_share = (
        sum(1 for area in source_areas if median_gt_area > 0 and area >= median_gt_area * 20.0)
        / max(len(source_areas), 1)
    )
    median_confidence = _median(confidences)
    near_constant_confidence_share = (
        sum(1 for conf in confidences if abs(float(conf) - float(median_confidence)) <= 0.001)
        / max(len(confidences), 1)
    )
    supported_ratio = _safe_float(proof_summary.get("supportedAcceptedBallRatio"), 0.0)
    unsupported_accepted_share = 1.0 - supported_ratio if probe_rows else 0.0
    has_required_artifacts = bool(probe_rows) and bool(positive_frames or negative_frames)
    dominant, next_family, reasons = _classify(
        raw_row_count=len(probe_rows),
        positive_hit_rate=positive_hit_rate,
        negative_hit_rate=negative_hit_rate,
        frame_hit_rate=frame_hit_rate,
        best_threshold=best_threshold,
        best_geometry=best_geometry,
        has_required_artifacts=has_required_artifacts,
        positive_localization_hit_rate=_safe_float(localization_audit.get("positiveLocalizationHitRate"), 0.0),
        top_left_box_share=top_left_box_share,
        large_box_share=large_box_share,
        near_constant_confidence_share=near_constant_confidence_share,
    )
    frame_matrix = _frame_matrix(rows_by_frame, positive_frames, negative_frames)
    geometry_audit = {
        "generatedAt": _utc_now_iso(),
        "medianSourceBoxArea": round(_median(source_areas), 3),
        "minSourceBoxArea": round(min(source_areas), 3) if source_areas else 0.0,
        "maxSourceBoxArea": round(max(source_areas), 3) if source_areas else 0.0,
        "geometrySweep": geometry_matrix,
        "bestGeometryContract": best_geometry,
    }
    threshold_sweep = {
        "generatedAt": _utc_now_iso(),
        "medianConfidence": round(_median(confidences), 6),
        "minConfidence": round(min(confidences), 6) if confidences else 0.0,
        "maxConfidence": round(max(confidences), 6) if confidences else 0.0,
        "thresholdSweep": threshold_matrix,
        "bestThresholdContract": best_threshold,
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "attemptNumber": 1,
        "attemptApproachFamily": "low_conf_precision_guardrail_audit",
        "inputBatchName": contract_summary.get("batchName"),
        "proofSource": str(proof_root) if proof_root else None,
        "auxiliaryBallModelProfile": trace.get("auxiliaryBallModelProfile") or trace.get("probeDetectorProfile") or LOW_CONF_PROFILE,
        "rawProbeRowCount": len(probe_rows),
        "hitFrameCount": len(hit_frames),
        "proofFrameCount": frame_count,
        "frameHitRate": round(frame_hit_rate, 3),
        "positiveTrainingFrameCount": len(positive_frames),
        "negativeTrainingFrameCount": len(negative_frames),
        "positiveFrameHitCount": len(positive_frames & hit_frames),
        "negativeFrameHitCount": len(negative_frames & hit_frames),
        "positiveFrameHitRate": round(positive_hit_rate, 3),
        "negativeFrameHitRate": round(negative_hit_rate, 3),
        "medianConfidence": threshold_sweep["medianConfidence"],
        "medianSourceBoxArea": geometry_audit["medianSourceBoxArea"],
        "positiveLocalizationHitRate": localization_audit["positiveLocalizationHitRate"],
        "positiveCenterDistanceHitRate": localization_audit["positiveCenterDistanceHitRate"],
        "positiveIoUHitRate": localization_audit["positiveIoUHitRate"],
        "medianCenterDistanceToReviewedBBox": localization_audit["medianCenterDistanceToReviewedBBox"],
        "medianDetectedBoxAreaToGtBoxAreaRatio": localization_audit["medianDetectedBoxAreaToGtBoxAreaRatio"],
        "topLeftBoxShare": round(top_left_box_share, 3),
        "largeBoxShare": round(large_box_share, 3),
        "nearConstantConfidenceShare": round(near_constant_confidence_share, 3),
        "unsupportedAcceptedShare": round(unsupported_accepted_share, 3),
        "recommendedConfidenceThreshold": (
            best_threshold.get("confidenceThreshold") if isinstance(best_threshold, dict) else None
        ),
        "recommendedMaxSourceBoxArea": (
            best_geometry.get("maxSourceBoxArea") if isinstance(best_geometry, dict) else None
        ),
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "classificationReasons": reasons,
        "decisions": [
            {
                "condition": "confidence threshold separates reviewed positives from reviewed negatives",
                "matched": dominant == BLOCKER_THRESHOLD_AVAILABLE,
                "nextCorrectiveFamily": NEXT_THRESHOLD_CONTRACT,
            },
            {
                "condition": "bbox geometry separates reviewed positives from reviewed negatives",
                "matched": dominant == BLOCKER_GEOMETRY_AVAILABLE,
                "nextCorrectiveFamily": NEXT_GEOMETRY_CONTRACT,
            },
            {
                "condition": "low-confidence probe floods most frames or reviewed negatives",
                "matched": dominant in {BLOCKER_LOW_CONF_FLOOD, BLOCKER_TOP_LEFT_ARTIFACT_FLOOD},
                "nextCorrectiveFamily": NEXT_TRAINING_REFRESH,
            },
            {
                "condition": "low-confidence proof signal missing",
                "matched": dominant == BLOCKER_SIGNAL_GONE,
                "nextCorrectiveFamily": NEXT_CONTRACT_REFRESH,
            },
            {
                "condition": "required audit artifacts missing",
                "matched": dominant == BLOCKER_ARTIFACT_GAP,
                "nextCorrectiveFamily": NEXT_ARTIFACT_REFRESH,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Audit whether the low-confidence v7 probe signal can be precision-bounded before any promotion path.",
        "goalAchieved": dominant != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": f"V7 precision guardrail audit classified the low-confidence proof as {dominant}.",
        "englishDecision": f"Advance to {next_family}; do not promote v7 or mutate runtime defaults.",
    }
    _write_json(output_root / "precision_guardrail_summary.json", summary)
    _write_json(output_root / "positive_localization_audit.json", localization_audit)
    _write_json(output_root / "v7_probe_precision_frame_matrix.json", {"frames": frame_matrix})
    _write_json(output_root / "threshold_precision_sweep.json", threshold_sweep)
    _write_json(output_root / "v7_probe_geometry_guardrail_audit.json", geometry_audit)
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_v7_probe_precision_guardrail_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
