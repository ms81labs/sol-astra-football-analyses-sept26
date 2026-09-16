from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_3_export_label_overlay_audit as audit


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_image(path: Path, *, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = (30, 110, 30)
    cv2.circle(image, (width // 2, height // 2), 6, (255, 255, 255), -1)
    cv2.imwrite(str(path), image)


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _positive(index: int, image_path: Path, *, source_dataset: str = "local", split: str = "train") -> dict[str, object]:
    return {
        "exampleId": f"positive-{index}",
        "sourceClipId": "trimed-5min.mp4" if source_dataset == "local" else "224p.mp4",
        "frameIndex": 100 + index,
        "sourceFrameImagePath": str(image_path) if source_dataset == "local" else None,
        "fullFrameImagePath": str(image_path) if source_dataset == "soccernet" else None,
        "sourceDataset": source_dataset,
        "label": "ball",
        "truthUse": "reviewed_positive_training_seed"
        if source_dataset == "local"
        else "reviewed_soccernet_real_detector_miss_positive",
        "exportUse": "yolo_positive_crop_with_ball_label",
        "cropKind": "test_positive_crop",
        "cropSizePx": 256,
        "cropBounds": [50.0, -10.0, 306.0, 246.0] if source_dataset == "soccernet" else [0.0, 0.0, 256.0, 256.0],
        "sourceFrameBbox": {"x1": 170.0, "y1": 100.0, "x2": 184.0, "y2": 114.0}
        if source_dataset == "soccernet"
        else {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "cropFrameBbox": {"x1": 120.0, "y1": 110.0, "x2": 134.0, "y2": 124.0}
        if source_dataset == "soccernet"
        else {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "splitGroupId": f"{source_dataset}-group-{index}",
        "split": split,
    }


def _negative(index: int, image_path: Path, *, heldout: bool = False) -> dict[str, object]:
    return {
        "exampleId": f"{'canary' if heldout else 'negative'}-{index}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 500 + index,
        "sourceFrameImagePath": str(image_path),
        "label": "no_ball",
        "truthUse": "local_hard_negative_crop_only",
        "exportUse": "yolo_empty_label_crop",
        "ballFreeStatus": "deterministic_artifact_region_ball_free",
        "cropWindow": [0.0, 0.0, 128.0, 128.0],
        "sourceFullFrameNegativeExported": False,
        "splitGroupId": f"{'canary' if heldout else 'negative'}-group-{index}",
        "split": "heldout" if heldout else ("validation" if index % 2 else "train"),
    }


def _write_manifest(
    tmp_path: Path,
    *,
    unsafe_negative_count: int = 0,
    split_leak: bool = False,
) -> Path:
    root = _candidate_root(tmp_path)
    input_root = root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
    local_frame = tmp_path / "frames" / "local.jpg"
    soccer_frame = tmp_path / "frames" / "soccernet.jpg"
    _write_image(local_frame, width=320, height=320)
    _write_image(soccer_frame, width=398, height=224)
    positives = [
        _positive(0, local_frame, source_dataset="local", split="train"),
        _positive(1, soccer_frame, source_dataset="soccernet", split="validation"),
    ]
    if split_leak:
        positives[1]["splitGroupId"] = positives[0]["splitGroupId"]
    _write_json(
        input_root / "v7_3_training_manifest.json",
        {
            "batchName": "v7_3_training_manifest_prep_from_soccernet_real_misses",
            "manifestReadyForExportAudit": True,
            "baseV72PositiveCropExampleCount": 1,
            "realMissPositiveCropExampleCount": 1,
            "positiveCropExampleCount": len(positives),
            "localHardNegativeCropCount": 2,
            "heldoutHardNegativeCanaryCount": 1,
            "unsafeFullFrameNegativeExportCount": unsafe_negative_count,
            "fullFrameEmptyLabelNegativeExportCount": 0,
            "positiveCropExamples": positives,
            "negativeCropExamples": [_negative(0, local_frame), _negative(1, local_frame)],
            "heldoutHardNegativeCanary": [_negative(0, local_frame, heldout=True)],
        },
    )
    return root


def test_v73_export_audit_writes_physical_preview_from_mixed_source_manifest(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path)

    payload = audit.run_v7_3_export_label_overlay_audit(storage_root=tmp_path)

    output_root = root / "v7_3_export_label_overlay_audit_v1"
    preview_root = output_root / "v7_3_export_preview"
    transform = json.loads((output_root / "v7_3_crop_label_transform_audit.json").read_text(encoding="utf-8"))

    assert payload["batchName"] == "v7_3_export_label_overlay_audit"
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["nextRecommendedNextLever"] == "v7_3_bounded_retrain"
    assert payload["positiveCropExampleCount"] == 2
    assert payload["baseV72PositiveCropExampleCount"] == 1
    assert payload["realMissPositiveCropExampleCount"] == 1
    assert payload["positiveLabelFilesWithExactlyOneBall"] == 2
    assert payload["negativeLabelFilesEmpty"] == 2
    assert payload["heldoutCanaryLabelFilesEmpty"] == 1
    assert payload["paddedPositiveCropCount"] == 1
    assert payload["cropSizeMismatchCount"] == 0
    assert payload["positiveLabelRoundTripMaxErrorPx"] <= 1.0
    assert payload["trainingReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert (preview_root / "data.yaml").exists()
    soccer_export = preview_root / "images" / "val" / "positive-1.jpg"
    assert soccer_export.exists()
    image = cv2.imread(str(soccer_export))
    assert image is not None
    assert image.shape[:2] == (256, 256)
    assert transform["paddedPositiveCropCount"] == 1


def test_v73_export_audit_blocks_unsafe_full_frame_negative_leak(tmp_path: Path) -> None:
    _write_manifest(tmp_path, unsafe_negative_count=1)

    payload = audit.run_v7_3_export_label_overlay_audit(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_3_export_unsafe_full_frame_negative_leak"
    assert payload["nextRecommendedNextLever"] == "v7_3_training_manifest_prep_from_soccernet_real_misses"
    assert payload["trainingExecuted"] is False


def test_v73_export_audit_blocks_split_leakage(tmp_path: Path) -> None:
    _write_manifest(tmp_path, split_leak=True)

    payload = audit.run_v7_3_export_label_overlay_audit(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_3_export_split_leakage_regression"
    assert payload["nextRecommendedNextLever"] == "v7_3_training_manifest_prep_from_soccernet_real_misses"


def test_v73_export_audit_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    payload = audit.run_v7_3_export_label_overlay_audit(storage_root=tmp_path)

    assert payload["attemptBudget"] == 3
    assert payload["attemptPlanFamilies"] == [
        "v7_3_physical_export_overlay_audit",
        "v7_3_export_geometry_padding_repair",
        "v7_3_export_blocker_summary",
    ]
