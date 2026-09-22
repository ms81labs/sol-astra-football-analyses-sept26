from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_required as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


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

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_2_training_manifest_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_export_label_overlay_audit_v1"
DEFAULT_VIDEO_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"

BLOCKER_POSITIVE_LABEL_MISSING = "v7_2_export_positive_label_missing"
BLOCKER_NEGATIVE_LABEL_NOT_EMPTY = "v7_2_export_negative_label_not_empty"
BLOCKER_CANARY_LEAKAGE = "v7_2_export_canary_leakage"
BLOCKER_SPLIT_LEAKAGE = "v7_2_export_split_leakage_regression"
BLOCKER_YOLO_INVALID = "v7_2_export_yolo_normalization_invalid"
BLOCKER_ROUNDTRIP = "v7_2_export_bbox_roundtrip_error"
BLOCKER_CLASS_ID = "v7_2_export_class_id_mismatch"
BLOCKER_CROP_SIZE = "v7_2_export_crop_size_mismatch"
BLOCKER_OVERLAY_MISSING = "v7_2_export_overlay_review_missing"
BLOCKER_UNSAFE_FULL_FRAME = "v7_2_export_unsafe_full_frame_negative_leak"

READY_CLASS = "v7_2_export_overlay_audit_ready"
NEXT_TINY_OVERFIT = "v7_2_bounded_retrain"
NEXT_POSITIVE_FIX = "v7_2_training_manifest_prep"
NEXT_MANIFEST_REFRESH = "v7_2_training_manifest_prep"
NEXT_NEGATIVE_REVIEW = "v7_2_negative_crop_review_or_safety_audit"
NEXT_MANUAL_REVIEW = "v7_2_manual_overlay_review"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






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


def _bbox_from_mapping(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        x1 = float(value["x1"])
        y1 = float(value["y1"])
        x2 = float(value["x2"])
        y2 = float(value["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _bounds_from_list(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    bounds = tuple(_safe_float(part) for part in value)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    return bounds


def _split_dir(row: dict[str, Any]) -> str:
    split = str(row.get("split") or "train").lower()
    return "val" if split in {"val", "validation"} else "train"


def _empty_label(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _write_label(path: Path, label: tuple[int, float, float, float, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    class_id, cx, cy, width, height = label
    path.write_text(f"{class_id} {cx:.8f} {cy:.8f} {width:.8f} {height:.8f}\n", encoding="utf-8")


def _label_from_crop_bbox(
    crop_bbox: dict[str, float],
    *,
    crop_width: int,
    crop_height: int,
) -> tuple[int, float, float, float, float] | None:
    width = crop_bbox["x2"] - crop_bbox["x1"]
    height = crop_bbox["y2"] - crop_bbox["y1"]
    if crop_width <= 0 or crop_height <= 0 or width <= 0 or height <= 0:
        return None
    cx = (crop_bbox["x1"] + crop_bbox["x2"]) / 2.0 / crop_width
    cy = (crop_bbox["y1"] + crop_bbox["y2"]) / 2.0 / crop_height
    return (0, cx, cy, width / crop_width, height / crop_height)


def _decode_yolo_label(label: tuple[int, float, float, float, float], *, crop_width: int, crop_height: int) -> dict[str, float]:
    _, cx, cy, width, height = label
    box_width = width * crop_width
    box_height = height * crop_height
    center_x = cx * crop_width
    center_y = cy * crop_height
    return {
        "x1": center_x - box_width / 2.0,
        "y1": center_y - box_height / 2.0,
        "x2": center_x + box_width / 2.0,
        "y2": center_y + box_height / 2.0,
    }


def _label_normalized(label: tuple[int, float, float, float, float] | None) -> bool:
    if label is None:
        return False
    class_id, cx, cy, width, height = label
    return class_id == 0 and all(0.0 <= value <= 1.0 for value in (cx, cy, width, height)) and width > 0 and height > 0


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
        image_path_value = row.get("sourceFrameImagePath")
        if image_path_value:
            image_path = Path(str(image_path_value))
            image = cv2.imread(str(image_path))
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


def _crop_image(frame: np.ndarray, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray | None, tuple[int, int, int, int], str]:
    height, width = frame.shape[:2]
    x1 = int(round(bounds[0]))
    y1 = int(round(bounds[1]))
    x2 = int(round(bounds[2]))
    y2 = int(round(bounds[3]))
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height or x2 <= x1 or y2 <= y1:
        return None, (x1, y1, x2, y2), "crop_bounds_outside_source_frame"
    return frame[y1:y2, x1:x2].copy(), (x1, y1, x2, y2), "ok"


def _repair_crop_bounds(
    frame: np.ndarray,
    bounds: tuple[float, float, float, float],
    *,
    expected_size: int,
) -> tuple[tuple[float, float, float, float], bool]:
    if expected_size <= 0:
        return bounds, False
    frame_height, frame_width = frame.shape[:2]
    if expected_size > frame_width or expected_size > frame_height:
        return bounds, False
    x1, y1, x2, y2 = bounds
    if int(round(x1)) >= 0 and int(round(y1)) >= 0 and int(round(x2)) <= frame_width and int(round(y2)) <= frame_height:
        return bounds, False
    repaired_x1 = min(max(x1, 0.0), float(frame_width - expected_size))
    repaired_y1 = min(max(y1, 0.0), float(frame_height - expected_size))
    return (repaired_x1, repaired_y1, repaired_x1 + expected_size, repaired_y1 + expected_size), True


def _crop_bbox_inside(crop_bbox: dict[str, float] | None, *, crop_width: int, crop_height: int) -> bool:
    if crop_bbox is None:
        return False
    return (
        crop_bbox["x1"] >= 0
        and crop_bbox["y1"] >= 0
        and crop_bbox["x2"] <= crop_width
        and crop_bbox["y2"] <= crop_height
        and crop_bbox["x2"] > crop_bbox["x1"]
        and crop_bbox["y2"] > crop_bbox["y1"]
    )


def _roundtrip_error(
    *,
    label: tuple[int, float, float, float, float],
    crop_width: int,
    crop_height: int,
    crop_bounds_int: tuple[int, int, int, int],
    source_bbox: dict[str, float],
) -> float:
    decoded = _decode_yolo_label(label, crop_width=crop_width, crop_height=crop_height)
    source_decoded = {
        "x1": decoded["x1"] + crop_bounds_int[0],
        "y1": decoded["y1"] + crop_bounds_int[1],
        "x2": decoded["x2"] + crop_bounds_int[0],
        "y2": decoded["y2"] + crop_bounds_int[1],
    }
    return max(abs(source_decoded[key] - source_bbox[key]) for key in ("x1", "y1", "x2", "y2"))


def _draw_label(image: np.ndarray, text: str, *, color: tuple[int, int, int]) -> np.ndarray:
    output = image.copy()
    cv2.rectangle(output, (0, 0), (output.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(output, text[:55], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
    return output


def _make_contact_sheet(
    items: list[dict[str, Any]],
    *,
    output_path: Path,
    title: str,
    max_items: int,
    tile_size: int = 180,
) -> int:
    selected = [item for item in items if item.get("imagePath")][:max_items]
    if not selected:
        return 0
    columns = 5
    rows = int(np.ceil(len(selected) / columns))
    sheet = np.zeros((rows * tile_size, columns * tile_size, 3), dtype=np.uint8)
    sheet[:, :] = (24, 24, 24)
    for index, item in enumerate(selected):
        image = cv2.imread(str(item["imagePath"]))
        if image is None:
            continue
        if item.get("cropFrameBbox"):
            bbox = item["cropFrameBbox"]
            cv2.rectangle(
                image,
                (int(round(bbox["x1"])), int(round(bbox["y1"]))),
                (int(round(bbox["x2"])), int(round(bbox["y2"]))),
                (0, 255, 255),
                2,
            )
        image = _draw_label(image, f"{title} {item.get('exampleId')} {item.get('split')}", color=(255, 255, 255))
        resized = cv2.resize(image, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
        row = index // columns
        column = index % columns
        sheet[row * tile_size : (row + 1) * tile_size, column * tile_size : (column + 1) * tile_size] = resized
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)
    return len(selected)


def _data_yaml(preview_root: Path) -> str:
    return "\n".join(
        [
            f"path: {preview_root}",
            "train: images/train",
            "val: images/val",
            "nc: 1",
            "names:",
            "  0: ball",
            "",
        ]
    )


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


def _classify(summary: dict[str, Any]) -> tuple[str | None, str | None, bool, str]:
    if summary["unsafeFullFrameNegativeExportCount"] > 0 or summary["fullFrameEmptyLabelNegativeExportCount"] > 0:
        return BLOCKER_UNSAFE_FULL_FRAME, NEXT_NEGATIVE_REVIEW, False, "unsafe full-frame negatives leaked into export"
    if summary["positiveLabelFilesWithExactlyOneBall"] != summary["positiveCropExampleCount"]:
        return BLOCKER_POSITIVE_LABEL_MISSING, NEXT_POSITIVE_FIX, False, "one or more positive labels are missing or duplicated"
    if summary["negativeLabelFilesEmpty"] != summary["localHardNegativeCropCount"]:
        return BLOCKER_NEGATIVE_LABEL_NOT_EMPTY, NEXT_NEGATIVE_REVIEW, False, "one or more hard-negative labels are not empty"
    if summary["heldoutCanaryLabelFilesEmpty"] != summary["heldoutHardNegativeCanaryCount"]:
        return BLOCKER_NEGATIVE_LABEL_NOT_EMPTY, NEXT_NEGATIVE_REVIEW, False, "one or more canary labels are not empty"
    if summary["canaryLeakageCount"] > 0:
        return BLOCKER_CANARY_LEAKAGE, NEXT_MANIFEST_REFRESH, False, "heldout canary examples leaked into train or validation"
    if summary["splitLeakageCount"] > 0:
        return BLOCKER_SPLIT_LEAKAGE, NEXT_MANIFEST_REFRESH, False, "train/validation split leakage reappeared"
    if summary["labelClassIdSet"] != [0]:
        return BLOCKER_CLASS_ID, NEXT_POSITIVE_FIX, False, "exported label class ids are not exactly [0]"
    if not summary["yoloLabelNormalizationValid"]:
        return BLOCKER_YOLO_INVALID, NEXT_POSITIVE_FIX, False, "YOLO label normalization is invalid"
    if not summary["positiveCropLocalBoxesInsideBounds"] or summary["positiveLabelRoundTripMaxErrorPx"] > 1.0:
        return BLOCKER_ROUNDTRIP, NEXT_POSITIVE_FIX, False, "positive crop label round-trip does not match source reviewed bbox"
    if summary["cropSizeMismatchCount"] > 0:
        return BLOCKER_CROP_SIZE, NEXT_POSITIVE_FIX, False, "one or more exported crop images do not match manifest crop size"
    if not summary["overlayContactSheetsReady"]:
        return BLOCKER_OVERLAY_MISSING, NEXT_MANUAL_REVIEW, False, "overlay contact sheets were not generated"
    return None, NEXT_TINY_OVERFIT, True, "Export and overlay audit passed. Advance to bounded v7.2 retrain; do not promote."


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Export Label Overlay Audit",
            "",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Readiness class: `{summary.get('readinessClass')}`",
            f"- Positive crop examples: `{summary.get('positiveCropExampleCount')}`",
            f"- Local hard-negative crops: `{summary.get('localHardNegativeCropCount')}`",
            f"- Heldout canaries: `{summary.get('heldoutHardNegativeCanaryCount')}`",
            f"- Positive label round-trip max error px: `{summary.get('positiveLabelRoundTripMaxErrorPx')}`",
            f"- Export overlay audit passed: `{summary.get('exportOverlayAuditPassed')}`",
            f"- Next lever: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


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
        "cropBoundsRepaired": False,
        "status": "not_exported",
    }
    if frame is None or source_bbox is None or crop_bbox is None or bounds is None:
        result["status"] = "missing_frame_or_bbox"
        return result
    expected_size = _safe_int(row.get("cropSizePx"), 0)
    adjusted_bounds, bounds_repaired = _repair_crop_bounds(frame, bounds, expected_size=expected_size)
    result["cropBoundsRepaired"] = bounds_repaired
    crop, crop_bounds_int, crop_status = _crop_image(frame, adjusted_bounds)
    if crop is None:
        result["status"] = crop_status
        return result
    crop_height, crop_width = crop.shape[:2]
    if bounds_repaired and source_bbox is not None:
        crop_bbox = {
            "x1": source_bbox["x1"] - crop_bounds_int[0],
            "y1": source_bbox["y1"] - crop_bounds_int[1],
            "x2": source_bbox["x2"] - crop_bounds_int[0],
            "y2": source_bbox["y2"] - crop_bounds_int[1],
        }
        result["cropFrameBbox"] = crop_bbox
    result["cropWidth"] = crop_width
    result["cropHeight"] = crop_height
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
                crop_bounds_int=crop_bounds_int,
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
        "status": "not_exported",
    }
    if frame is None or bounds is None:
        result["status"] = "missing_frame_or_crop_bounds"
        return result
    crop, _, crop_status = _crop_image(frame, bounds)
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
    result["status"] = "exported"
    return result


def run_v7_2_export_label_overlay_audit(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    input_batch_name: str = DEFAULT_INPUT_BATCH_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    video_path: Path = DEFAULT_VIDEO_PATH,
    attempt_number: int = 1,
    attempt_approach_family: str = "export_label_overlay_audit",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    input_root = candidate_root / input_batch_name
    manifest = _load_json(input_root / "v7_2_training_manifest.json")
    positives = [dict(row) for row in manifest.get("positiveCropExamples") or [] if isinstance(row, dict)]
    negatives = [dict(row) for row in manifest.get("negativeCropExamples") or [] if isinstance(row, dict)]
    canaries = [dict(row) for row in manifest.get("heldoutHardNegativeCanary") or [] if isinstance(row, dict)]
    output_root = reset_output(candidate_root, output_dir_name)
    preview_root = output_root / "v7_2_export_preview"
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
        output_path=output_root / "v7_2_overlay_contact_sheet_positive.jpg",
        title="positive",
        max_items=len(positive_rows),
    )
    negative_sheet_count = _make_contact_sheet(
        negative_rows,
        output_path=output_root / "v7_2_overlay_contact_sheet_negative.jpg",
        title="negative",
        max_items=60,
    )
    canary_sheet_count = _make_contact_sheet(
        canary_rows,
        output_path=output_root / "v7_2_overlay_contact_sheet_canary.jpg",
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
    summary: dict[str, Any] = {
        "batchName": "v7_2_export_label_overlay_audit",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "positiveCropExampleCount": len(positives),
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
        "positiveCropBoundsRepairedCount": sum(1 for row in positive_rows if row.get("cropBoundsRepaired")),
        "overlayPositiveRenderedCount": positive_sheet_count,
        "overlayNegativeRenderedCount": negative_sheet_count,
        "overlayCanaryRenderedCount": canary_sheet_count,
        "overlayContactSheetsReady": positive_sheet_count == len(positives) and negative_sheet_count >= min(60, len(negatives)) and canary_sheet_count == len(canaries),
        "manifestReadyForExportAudit": bool(manifest.get("manifestReadyForExportAudit")),
        "trainingReady": False,
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
        "positiveCropBoundsRepairedCount": summary["positiveCropBoundsRepairedCount"],
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
        "reviewPolicy": "programmatic_export_overlay_audit_before_training",
        "positiveOverlayCount": positive_sheet_count,
        "negativeOverlayCount": negative_sheet_count,
        "canaryOverlayCount": canary_sheet_count,
        "positiveContactSheetPath": str(output_root / "v7_2_overlay_contact_sheet_positive.jpg"),
        "negativeContactSheetPath": str(output_root / "v7_2_overlay_contact_sheet_negative.jpg"),
        "canaryContactSheetPath": str(output_root / "v7_2_overlay_contact_sheet_canary.jpg"),
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
    _write_json(output_root / "v7_2_label_overlay_audit.json", summary)
    _write_json(output_root / "v7_2_crop_label_transform_audit.json", transform_audit)
    _write_json(output_root / "v7_2_export_manifest_consistency_audit.json", consistency_audit)
    _write_json(output_root / "v7_2_overlay_review_manifest.json", overlay_manifest)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="export_label_overlay_audit")
    args = parser.parse_args()
    payload = run_v7_2_export_label_overlay_audit(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        video_path=args.video_path,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
