from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_required as _load_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
from backend.scripts.run_v7_2_export_label_overlay_audit import (  # noqa: E402
    _bbox_from_mapping,
    _bounds_from_list,
    _crop_bbox_inside,
    _data_yaml,
    _decode_yolo_label,
    _empty_label,
    _label_from_crop_bbox,
    _label_normalized,
    _make_contact_sheet,
    _safe_int,
    _split_dir,
    _write_json,
    _write_label,
)

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_export_label_overlay_audit_v1"
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"

BLOCKER_POSITIVE_LABEL_MISSING = "v7_3_export_positive_label_missing"
BLOCKER_NEGATIVE_LABEL_NOT_EMPTY = "v7_3_export_negative_label_not_empty"
BLOCKER_CANARY_LEAKAGE = "v7_3_export_canary_leakage"
BLOCKER_SPLIT_LEAKAGE = "v7_3_export_split_leakage_regression"
BLOCKER_YOLO_INVALID = "v7_3_export_yolo_normalization_invalid"
BLOCKER_ROUNDTRIP = "v7_3_export_bbox_roundtrip_error"
BLOCKER_CLASS_ID = "v7_3_export_class_id_mismatch"
BLOCKER_CROP_SIZE = "v7_3_export_crop_size_mismatch"
BLOCKER_OVERLAY_MISSING = "v7_3_export_overlay_review_missing"
BLOCKER_UNSAFE_FULL_FRAME = "v7_3_export_unsafe_full_frame_negative_leak"

READY_CLASS = "v7_3_export_overlay_audit_ready"
NEXT_BOUNDED_RETRAIN = "v7_3_bounded_retrain"
NEXT_MANIFEST_REFRESH = "v7_3_training_manifest_prep_from_soccernet_real_misses"
NEXT_NEGATIVE_REVIEW = "v7_3_negative_crop_review_or_safety_audit"
NEXT_MANUAL_REVIEW = "v7_3_manual_overlay_review"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name




def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "v7_3_physical_export_overlay_audit",
                "successCriteria": [
                    "export audited v7.3 manifest into physical crop images and YOLO label files",
                    "prove mixed v7.2 and SoccerNet source rows share one label coordinate contract",
                    "route to bounded retrain only if all export gates pass",
                ],
                "failureAdaptation": "If physical export fails from geometry, try the padding-aware geometry repair family.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "v7_3_export_geometry_padding_repair",
                "successCriteria": [
                    "preserve crop-local label coordinates while padding source-edge crops",
                    "do not alter labels or training truth",
                    "keep unsafe full-frame negatives excluded",
                ],
                "failureAdaptation": "If repaired export still fails, write blocker truth without training.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "v7_3_export_blocker_summary",
                "successCriteria": ["write one primary blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before training when export truth is incomplete.",
            },
        ],
    }


class _FrameReader:
    def __init__(self, video_path: Path) -> None:
        self.video_path = Path(video_path)
        self._cache: dict[int, np.ndarray] = {}
        self._capture: cv2.VideoCapture | None = None

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def read(self, row: dict[str, Any]) -> np.ndarray | None:
        for key in ("sourceFrameImagePath", "fullFrameImagePath"):
            image_path_value = row.get(key)
            if image_path_value:
                image = cv2.imread(str(Path(str(image_path_value))))
                if image is not None:
                    return image
        frame_index = _safe_int(row.get("frameIndex"), -1)
        if frame_index < 0 or not self.video_path.exists():
            return None
        if frame_index in self._cache:
            return self._cache[frame_index].copy()
        if self._capture is None:
            self._capture = cv2.VideoCapture(str(self.video_path))
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        self._cache[frame_index] = frame.copy()
        return frame


def _crop_image_with_padding(
    frame: np.ndarray,
    bounds: tuple[float, float, float, float],
    *,
    expected_width: int,
    expected_height: int,
) -> tuple[np.ndarray | None, tuple[float, float, float, float], bool, str]:
    frame_height, frame_width = frame.shape[:2]
    crop_x1, crop_y1, crop_x2, crop_y2 = bounds
    crop_width = expected_width if expected_width > 0 else int(round(crop_x2 - crop_x1))
    crop_height = expected_height if expected_height > 0 else int(round(crop_y2 - crop_y1))
    if crop_width <= 0 or crop_height <= 0:
        return None, bounds, False, "invalid_crop_dimensions"

    output = np.zeros((crop_height, crop_width, 3), dtype=frame.dtype)
    src_x1 = max(0, int(np.floor(crop_x1)))
    src_y1 = max(0, int(np.floor(crop_y1)))
    src_x2 = min(frame_width, int(np.ceil(crop_x1 + crop_width)))
    src_y2 = min(frame_height, int(np.ceil(crop_y1 + crop_height)))
    if src_x2 <= src_x1 or src_y2 <= src_y1:
        return None, bounds, False, "crop_has_no_source_intersection"

    dst_x1 = max(0, int(round(src_x1 - crop_x1)))
    dst_y1 = max(0, int(round(src_y1 - crop_y1)))
    copy_width = min(src_x2 - src_x1, crop_width - dst_x1)
    copy_height = min(src_y2 - src_y1, crop_height - dst_y1)
    if copy_width <= 0 or copy_height <= 0:
        return None, bounds, False, "crop_copy_region_empty"
    output[dst_y1 : dst_y1 + copy_height, dst_x1 : dst_x1 + copy_width] = frame[
        src_y1 : src_y1 + copy_height,
        src_x1 : src_x1 + copy_width,
    ]
    padded = src_x1 > crop_x1 or src_y1 > crop_y1 or src_x2 < crop_x1 + crop_width or src_y2 < crop_y1 + crop_height
    normalized_bounds = (crop_x1, crop_y1, crop_x1 + crop_width, crop_y1 + crop_height)
    return output, normalized_bounds, padded, "ok"


def _roundtrip_error(
    *,
    label: tuple[int, float, float, float, float],
    crop_width: int,
    crop_height: int,
    crop_bounds: tuple[float, float, float, float],
    source_bbox: dict[str, float],
) -> float:
    decoded = _decode_yolo_label(label, crop_width=crop_width, crop_height=crop_height)
    source_decoded = {
        "x1": decoded["x1"] + crop_bounds[0],
        "y1": decoded["y1"] + crop_bounds[1],
        "x2": decoded["x2"] + crop_bounds[0],
        "y2": decoded["y2"] + crop_bounds[1],
    }
    return max(abs(source_decoded[key] - source_bbox[key]) for key in ("x1", "y1", "x2", "y2"))


def _split_leakage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, set[str]] = {}
    for row in rows:
        group = str(row.get("splitGroupId") or row.get("exampleId") or "")
        split = _split_dir(row)
        groups.setdefault(group, set()).add(split)
    return [
        {"splitGroupId": group, "splits": sorted(splits)}
        for group, splits in sorted(groups.items())
        if len(splits) > 1
    ]


def _export_positive(
    row: dict[str, Any],
    *,
    reader: _FrameReader,
    preview_root: Path,
) -> dict[str, Any]:
    split = _split_dir(row)
    image_path = preview_root / "images" / split / f"{row.get('exampleId')}.jpg"
    label_path = preview_root / "labels" / split / f"{row.get('exampleId')}.txt"
    frame = reader.read(row)
    source_bbox = _bbox_from_mapping(row.get("sourceFrameBbox"))
    crop_bbox = _bbox_from_mapping(row.get("cropFrameBbox"))
    bounds = _bounds_from_list(row.get("cropBounds"))
    result: dict[str, Any] = {
        "exampleId": row.get("exampleId"),
        "split": split,
        "frameIndex": row.get("frameIndex"),
        "sourceClipId": row.get("sourceClipId"),
        "sourceDataset": row.get("sourceDataset"),
        "imagePath": str(image_path),
        "labelPath": str(label_path),
        "cropFrameBbox": crop_bbox,
        "sourceFrameBbox": source_bbox,
        "imageFileExists": False,
        "labelFileExists": False,
        "labelCount": 0,
        "classId": None,
        "normalized": False,
        "cropLocalBoxInsideBounds": False,
        "roundTripMaxErrorPx": None,
        "cropSizeMismatch": False,
        "cropWasPadded": False,
        "status": "not_exported",
    }
    if frame is None or source_bbox is None or crop_bbox is None or bounds is None:
        result["status"] = "missing_frame_or_bbox"
        return result

    expected_size = _safe_int(row.get("cropSizePx"), 0)
    crop, crop_bounds, padded, crop_status = _crop_image_with_padding(
        frame,
        bounds,
        expected_width=expected_size,
        expected_height=expected_size,
    )
    if crop is None:
        result["status"] = crop_status
        return result
    crop_height, crop_width = crop.shape[:2]
    result["cropWidth"] = crop_width
    result["cropHeight"] = crop_height
    result["cropWasPadded"] = padded
    result["cropSizeMismatch"] = expected_size > 0 and (crop_width != expected_size or crop_height != expected_size)
    label = _label_from_crop_bbox(crop_bbox, crop_width=crop_width, crop_height=crop_height)
    result["cropLocalBoxInsideBounds"] = _crop_bbox_inside(crop_bbox, crop_width=crop_width, crop_height=crop_height)
    result["normalized"] = _label_normalized(label)
    if label is not None:
        result["classId"] = label[0]
        result["yoloLabel"] = [label[0], round(label[1], 8), round(label[2], 8), round(label[3], 8), round(label[4], 8)]
        result["roundTripMaxErrorPx"] = round(
            _roundtrip_error(
                label=label,
                crop_width=crop_width,
                crop_height=crop_height,
                crop_bounds=crop_bounds,
                source_bbox=source_bbox,
            ),
            6,
        )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(image_path), crop)
    if label is not None:
        _write_label(label_path, label)
        result["labelCount"] = 1
    result["imageFileExists"] = image_path.exists()
    result["labelFileExists"] = label_path.exists()
    result["status"] = "exported"
    return result


def _export_negative(
    row: dict[str, Any],
    *,
    reader: _FrameReader,
    preview_root: Path,
    canary: bool = False,
) -> dict[str, Any]:
    split = "canary" if canary else _split_dir(row)
    image_path = preview_root / "images" / split / f"{row.get('exampleId')}.jpg"
    label_path = preview_root / "labels" / split / f"{row.get('exampleId')}.txt"
    bounds = _bounds_from_list(row.get("sourceFalsePositiveBbox") or row.get("cropWindow"))
    frame = reader.read(row)
    result: dict[str, Any] = {
        "exampleId": row.get("exampleId"),
        "split": split,
        "frameIndex": row.get("frameIndex"),
        "sourceClipId": row.get("sourceClipId"),
        "imagePath": str(image_path),
        "labelPath": str(label_path),
        "imageFileExists": False,
        "labelFileExists": False,
        "labelEmpty": False,
        "cropWasPadded": False,
        "status": "not_exported",
    }
    if frame is None or bounds is None:
        result["status"] = "missing_frame_or_crop_bounds"
        return result
    expected_width = int(round(bounds[2] - bounds[0]))
    expected_height = int(round(bounds[3] - bounds[1]))
    crop, _, padded, crop_status = _crop_image_with_padding(
        frame,
        bounds,
        expected_width=expected_width,
        expected_height=expected_height,
    )
    if crop is None:
        result["status"] = crop_status
        return result
    image_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(image_path), crop)
    _empty_label(label_path)
    result["imageFileExists"] = image_path.exists()
    result["labelFileExists"] = label_path.exists()
    result["labelEmpty"] = label_path.read_text(encoding="utf-8") == ""
    result["cropWidth"] = crop.shape[1]
    result["cropHeight"] = crop.shape[0]
    result["cropWasPadded"] = padded
    result["status"] = "exported"
    return result


def _classify(summary: dict[str, Any]) -> tuple[str | None, str | None, bool, str]:
    if summary["unsafeFullFrameNegativeExportCount"] > 0 or summary["fullFrameEmptyLabelNegativeExportCount"] > 0:
        return BLOCKER_UNSAFE_FULL_FRAME, NEXT_MANIFEST_REFRESH, False, "unsafe full-frame negatives leaked into export"
    if summary["positiveLabelFilesWithExactlyOneBall"] != summary["positiveCropExampleCount"]:
        return BLOCKER_POSITIVE_LABEL_MISSING, NEXT_MANIFEST_REFRESH, False, "one or more positive labels are missing or duplicated"
    if summary["negativeLabelFilesEmpty"] != summary["localHardNegativeCropCount"]:
        return BLOCKER_NEGATIVE_LABEL_NOT_EMPTY, NEXT_NEGATIVE_REVIEW, False, "one or more hard-negative labels are not empty"
    if summary["heldoutCanaryLabelFilesEmpty"] != summary["heldoutHardNegativeCanaryCount"]:
        return BLOCKER_NEGATIVE_LABEL_NOT_EMPTY, NEXT_NEGATIVE_REVIEW, False, "one or more canary labels are not empty"
    if summary["canaryLeakageCount"] > 0:
        return BLOCKER_CANARY_LEAKAGE, NEXT_MANIFEST_REFRESH, False, "heldout canary examples leaked into train or validation"
    if summary["splitLeakageCount"] > 0:
        return BLOCKER_SPLIT_LEAKAGE, NEXT_MANIFEST_REFRESH, False, "train/validation split leakage reappeared"
    if summary["labelClassIdSet"] != [0]:
        return BLOCKER_CLASS_ID, NEXT_MANIFEST_REFRESH, False, "exported label class ids are not exactly [0]"
    if not summary["yoloLabelNormalizationValid"]:
        return BLOCKER_YOLO_INVALID, NEXT_MANIFEST_REFRESH, False, "YOLO label normalization is invalid"
    if not summary["positiveCropLocalBoxesInsideBounds"] or summary["positiveLabelRoundTripMaxErrorPx"] > 1.0:
        return BLOCKER_ROUNDTRIP, NEXT_MANIFEST_REFRESH, False, "positive crop label round-trip does not match source reviewed bbox"
    if summary["cropSizeMismatchCount"] > 0:
        return BLOCKER_CROP_SIZE, NEXT_MANIFEST_REFRESH, False, "one or more exported crop images do not match manifest crop size"
    if not summary["overlayContactSheetsReady"]:
        return BLOCKER_OVERLAY_MISSING, NEXT_MANUAL_REVIEW, False, "overlay contact sheets were not generated"
    return None, NEXT_BOUNDED_RETRAIN, True, "v7.3 export and overlay audit passed. Advance to bounded retrain; do not promote."


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Export Label Overlay Audit",
            "",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Readiness class: `{summary.get('readinessClass')}`",
            f"- Positive crop examples: `{summary.get('positiveCropExampleCount')}`",
            f"- Base v7.2 positive crops: `{summary.get('baseV72PositiveCropExampleCount')}`",
            f"- SoccerNet real-miss crops: `{summary.get('realMissPositiveCropExampleCount')}`",
            f"- Local hard-negative crops: `{summary.get('localHardNegativeCropCount')}`",
            f"- Heldout canaries: `{summary.get('heldoutHardNegativeCanaryCount')}`",
            f"- Padded positive crops: `{summary.get('paddedPositiveCropCount')}`",
            f"- Positive label round-trip max error px: `{summary.get('positiveLabelRoundTripMaxErrorPx')}`",
            f"- Export overlay audit passed: `{summary.get('exportOverlayAuditPassed')}`",
            f"- Next lever: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_export_label_overlay_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    input_batch_name: str = DEFAULT_INPUT_BATCH_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    video_path: Path = DEFAULT_VIDEO_PATH,
    attempt_number: int = 1,
    attempt_approach_family: str = "v7_3_physical_export_overlay_audit",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    input_root = candidate_root / input_batch_name
    manifest = _load_json(input_root / "v7_3_training_manifest.json")
    positives = [dict(row) for row in manifest.get("positiveCropExamples") or [] if isinstance(row, dict)]
    negatives = [dict(row) for row in manifest.get("negativeCropExamples") or [] if isinstance(row, dict)]
    canaries = [dict(row) for row in manifest.get("heldoutHardNegativeCanary") or [] if isinstance(row, dict)]
    output_root = reset_output(candidate_root, output_dir_name)
    preview_root = output_root / "v7_3_export_preview"
    preview_root.mkdir(parents=True, exist_ok=True)
    reader = _FrameReader(Path(video_path))
    try:
        positive_rows = [_export_positive(row, reader=reader, preview_root=preview_root) for row in positives]
        negative_rows = [_export_negative(row, reader=reader, preview_root=preview_root, canary=False) for row in negatives]
        canary_rows = [_export_negative(row, reader=reader, preview_root=preview_root, canary=True) for row in canaries]
    finally:
        reader.close()
    (preview_root / "data.yaml").write_text(_data_yaml(preview_root), encoding="utf-8")

    positive_sheet_count = _make_contact_sheet(
        positive_rows,
        output_path=output_root / "v7_3_overlay_contact_sheet_positive.jpg",
        title="positive",
        max_items=len(positive_rows),
    )
    negative_sheet_count = _make_contact_sheet(
        negative_rows,
        output_path=output_root / "v7_3_overlay_contact_sheet_negative.jpg",
        title="negative",
        max_items=60,
    )
    canary_sheet_count = _make_contact_sheet(
        canary_rows,
        output_path=output_root / "v7_3_overlay_contact_sheet_canary.jpg",
        title="canary",
        max_items=20,
    )

    class_ids = sorted({row["classId"] for row in positive_rows if row.get("classId") is not None})
    roundtrip_values = [
        float(row["roundTripMaxErrorPx"])
        for row in positive_rows
        if isinstance(row.get("roundTripMaxErrorPx"), (int, float))
    ]
    train_val_rows = [*positives, *negatives]
    leaks = _split_leakage(train_val_rows)
    train_val_ids = {str(row.get("exampleId")) for row in train_val_rows}
    canary_ids = {str(row.get("exampleId")) for row in canaries}
    canary_leaks = sorted(train_val_ids & canary_ids)
    negative_positive_ratio = round(len(negatives) / max(len(positives), 1), 3)
    attempt_plan = _attempt_plan()
    base_positive_count = _safe_int(manifest.get("baseV72PositiveCropExampleCount"), 0)
    real_miss_count = _safe_int(manifest.get("realMissPositiveCropExampleCount"), 0)
    summary: dict[str, Any] = {
        "batchName": "v7_3_export_label_overlay_audit",
        "attemptNumber": attempt_number,
        "attemptBudget": attempt_plan["attemptBudget"],
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempt_plan["attempts"]],
        "generatedAt": _utc_now_iso(),
        "sourceManifestBatch": "v7_3_training_manifest_prep_from_soccernet_real_misses",
        "positiveCropExampleCount": len(positives),
        "baseV72PositiveCropExampleCount": base_positive_count,
        "realMissPositiveCropExampleCount": real_miss_count,
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(canaries),
        "negativePositiveRatio": negative_positive_ratio,
        "unsafeFullFrameNegativeExportCount": _safe_int(manifest.get("unsafeFullFrameNegativeExportCount"), 0),
        "fullFrameEmptyLabelNegativeExportCount": _safe_int(manifest.get("fullFrameEmptyLabelNegativeExportCount"), 0),
        "positiveImageFilesExist": sum(1 for row in positive_rows if row.get("imageFileExists")),
        "positiveLabelFilesExist": sum(1 for row in positive_rows if row.get("labelFileExists")),
        "positiveLabelFilesWithExactlyOneBall": sum(1 for row in positive_rows if row.get("labelCount") == 1),
        "negativeImageFilesExist": sum(1 for row in negative_rows if row.get("imageFileExists")),
        "negativeLabelFilesExist": sum(1 for row in negative_rows if row.get("labelFileExists")),
        "negativeLabelFilesEmpty": sum(1 for row in negative_rows if row.get("labelEmpty")),
        "heldoutCanaryImageFilesExist": sum(1 for row in canary_rows if row.get("imageFileExists")),
        "heldoutCanaryLabelFilesExist": sum(1 for row in canary_rows if row.get("labelFileExists")),
        "heldoutCanaryLabelFilesEmpty": sum(1 for row in canary_rows if row.get("labelEmpty")),
        "labelClassIdSet": class_ids,
        "yoloLabelNormalizationValid": all(row.get("normalized") for row in positive_rows),
        "positiveCropLocalBoxesInsideBounds": all(row.get("cropLocalBoxInsideBounds") for row in positive_rows),
        "positiveLabelRoundTripMaxErrorPx": max(roundtrip_values) if roundtrip_values else 9999.0,
        "splitLeakageCount": len(leaks),
        "canaryLeakageCount": len(canary_leaks),
        "cropSizeMismatchCount": sum(1 for row in positive_rows if row.get("cropSizeMismatch")),
        "paddedPositiveCropCount": sum(1 for row in positive_rows if row.get("cropWasPadded")),
        "paddedNegativeCropCount": sum(1 for row in [*negative_rows, *canary_rows] if row.get("cropWasPadded")),
        "overlayPositiveRenderedCount": positive_sheet_count,
        "overlayNegativeRenderedCount": negative_sheet_count,
        "overlayCanaryRenderedCount": canary_sheet_count,
        "overlayContactSheetsReady": positive_sheet_count == len(positives) and negative_sheet_count >= min(60, len(negatives)) and canary_sheet_count == len(canaries),
        "manifestReadyForExportAudit": bool(manifest.get("manifestReadyForExportAudit")),
        "trainingReady": False,
        "trainingExecuted": False,
        "candidateReadyForEvaluation": False,
        "promotionReady": False,
        "runtimeDefaultMutationAllowed": False,
    }
    primary_blocker, next_lever, passed, english = _classify(summary)
    summary.update(
        {
            "goalAchieved": passed,
            "roadmapAdvanceAllowed": passed,
            "primaryBlocker": primary_blocker,
            "readinessClass": READY_CLASS if passed else None,
            "exportOverlayAuditPassed": passed,
            "nextRecommendedNextLever": next_lever,
            "englishDecision": english,
        }
    )
    transform_audit = {
        "generatedAt": _utc_now_iso(),
        "positiveLabelRoundTripMaxErrorPx": summary["positiveLabelRoundTripMaxErrorPx"],
        "paddedPositiveCropCount": summary["paddedPositiveCropCount"],
        "positiveCropLocalBoxesInsideBounds": summary["positiveCropLocalBoxesInsideBounds"],
        "labelClassIdSet": class_ids,
        "yoloLabelNormalizationValid": summary["yoloLabelNormalizationValid"],
        "rows": positive_rows,
    }
    consistency_audit = {
        "generatedAt": _utc_now_iso(),
        "splitLeakageCount": len(leaks),
        "splitLeaks": leaks,
        "canaryLeakageCount": len(canary_leaks),
        "canaryLeaks": canary_leaks,
        "negativePositiveRatio": negative_positive_ratio,
        "previewRoot": str(preview_root),
        "positiveRows": positive_rows,
        "negativeRows": negative_rows,
        "canaryRows": canary_rows,
    }
    overlay_manifest = {
        "generatedAt": _utc_now_iso(),
        "reviewPolicy": "programmatic_export_overlay_audit_before_v7_3_training",
        "positiveOverlayCount": positive_sheet_count,
        "negativeOverlayCount": negative_sheet_count,
        "canaryOverlayCount": canary_sheet_count,
        "positiveContactSheetPath": str(output_root / "v7_3_overlay_contact_sheet_positive.jpg"),
        "negativeContactSheetPath": str(output_root / "v7_3_overlay_contact_sheet_negative.jpg"),
        "canaryContactSheetPath": str(output_root / "v7_3_overlay_contact_sheet_canary.jpg"),
        "positiveItems": positive_rows,
        "negativeItems": negative_rows[:60],
        "canaryItems": canary_rows,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "positive_labels_exactly_one_ball", "observed": summary["positiveLabelFilesWithExactlyOneBall"] == len(positives), "blocker": BLOCKER_POSITIVE_LABEL_MISSING},
            {"condition": "negative_labels_empty", "observed": summary["negativeLabelFilesEmpty"] == len(negatives), "blocker": BLOCKER_NEGATIVE_LABEL_NOT_EMPTY},
            {"condition": "canary_labels_empty", "observed": summary["heldoutCanaryLabelFilesEmpty"] == len(canaries), "blocker": BLOCKER_NEGATIVE_LABEL_NOT_EMPTY},
            {"condition": "canary_not_in_train_val", "observed": summary["canaryLeakageCount"] == 0, "blocker": BLOCKER_CANARY_LEAKAGE},
            {"condition": "no_split_leakage", "observed": summary["splitLeakageCount"] == 0, "blocker": BLOCKER_SPLIT_LEAKAGE},
            {"condition": "bbox_roundtrip_valid", "observed": summary["positiveLabelRoundTripMaxErrorPx"] <= 1.0, "blocker": BLOCKER_ROUNDTRIP},
            {"condition": "padding_contract_safe", "observed": summary["cropSizeMismatchCount"] == 0, "blocker": BLOCKER_CROP_SIZE},
            {"condition": "overlay_contact_sheets_ready", "observed": summary["overlayContactSheetsReady"], "blocker": BLOCKER_OVERLAY_MISSING},
            {"condition": "export_overlay_audit_passed", "observed": passed, "nextFamily": next_lever},
        ],
    }
    outcome = {
        "summary": summary,
        "transformAudit": transform_audit,
        "consistencyAudit": consistency_audit,
        "overlayReviewManifest": overlay_manifest,
    }
    _write_json(output_root / "v7_3_label_overlay_audit.json", summary)
    _write_json(output_root / "v7_3_crop_label_transform_audit.json", transform_audit)
    _write_json(output_root / "v7_3_export_manifest_consistency_audit.json", consistency_audit)
    _write_json(output_root / "v7_3_overlay_review_manifest.json", overlay_manifest)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", attempt_plan)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and audit the v7.3 mixed-source crop training preview.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="v7_3_physical_export_overlay_audit")
    args = parser.parse_args()
    payload = run_v7_3_export_label_overlay_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        video_path=args.video_path,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
