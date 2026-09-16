from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_1_export_label_overlay_audit as overlay_audit


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_frame(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((900, 1200, 3), dtype=np.uint8)
    image[:, :] = (42, 130, 58)
    cv2.circle(image, (390, 696), 8, (235, 235, 235), -1)
    cv2.imwrite(str(path), image)
    return path


def _bbox_for(index: int) -> dict[str, float]:
    x1 = 381.0 + (index % 10) * 2.0
    y1 = 688.0 + (index % 3) * 3.0
    return {"x1": x1, "y1": y1, "x2": x1 + 16.0, "y2": y1 + 16.0}


def _positive_crop(
    *,
    index: int,
    crop_size: int,
    source_frame_image_path: Path,
    bad_bbox: bool = False,
) -> dict[str, object]:
    frame = 240 + index * 70
    bbox = _bbox_for(index)
    cx = (bbox["x1"] + bbox["x2"]) / 2.0
    cy = (bbox["y1"] + bbox["y2"]) / 2.0
    crop_x1 = cx - crop_size / 2.0
    crop_y1 = cy - crop_size / 2.0
    crop_frame_bbox = {
        "x1": bbox["x1"] - crop_x1,
        "y1": bbox["y1"] - crop_y1,
        "x2": bbox["x2"] - crop_x1,
        "y2": bbox["y2"] - crop_y1,
    }
    if bad_bbox:
        crop_frame_bbox["x2"] = crop_size + 20.0
    return {
        "exampleId": f"positive-{frame}-{crop_size}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame,
        "label": "ball",
        "truthUse": "reviewed_positive_training_seed",
        "exportUse": "yolo_positive_crop_with_ball_label",
        "cropKind": "ball_centered_positive_crop",
        "cropSizePx": crop_size,
        "cropBounds": [crop_x1, crop_y1, crop_x1 + crop_size, crop_y1 + crop_size],
        "sourceFrameBbox": bbox,
        "cropFrameBbox": crop_frame_bbox,
        "splitGroupId": f"positive-group-{index // 5}",
        "split": "validation" if index >= 25 else "train",
        "sourceFrameImagePath": str(source_frame_image_path),
    }


def _negative_crop(
    *,
    index: int,
    source_frame_image_path: Path,
    canary: bool = False,
    example_id: str | None = None,
) -> dict[str, object]:
    frame = index * 25
    return {
        "exampleId": example_id or f"negative-{index}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame,
        "label": "no_ball",
        "truthUse": "local_hard_negative_crop_only",
        "exportUse": "yolo_empty_label_crop",
        "cropKind": "top_left_artifact_false_positive_crop",
        "sourceFalsePositiveBbox": [0.0, 0.0, 198.0, 233.0],
        "cropBbox": [0.0, 0.0, 198.0, 233.0],
        "ballFreeStatus": "deterministic_artifact_region_ball_free",
        "splitGroupId": f"negative-group-{index // 20}",
        "split": "canary" if canary else ("validation" if index >= 160 else "train"),
        "sourceFrameImagePath": str(source_frame_image_path),
    }


def _write_manifest_bundle(
    tmp_path: Path,
    *,
    bad_positive_bbox: bool = False,
    canary_leak: bool = False,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    input_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    source_image = _source_frame(tmp_path / "frames" / "frame.jpg")
    positives = [
        _positive_crop(
            index=source_index,
            crop_size=crop_size,
            source_frame_image_path=source_image,
            bad_bbox=bad_positive_bbox and source_index == 0 and crop_size == 192,
        )
        for source_index in range(30)
        for crop_size in (192, 256, 384)
    ]
    negatives = [_negative_crop(index=index, source_frame_image_path=source_image) for index in range(180)]
    canary_id = "negative-0" if canary_leak else None
    canaries = [
        _negative_crop(index=180 + index, source_frame_image_path=source_image, canary=True, example_id=canary_id if index == 0 else None)
        for index in range(20)
    ]
    _write_json(
        input_root / "v7_1_local_crop_training_manifest.json",
        {
            "batchName": "v7_1_crop_manifest_consistency_refresh",
            "trainingCandidateName": "touchline_detector_candidate_v7_1",
            "positiveCropExampleCount": len(positives),
            "localHardNegativeCropCount": len(negatives),
            "heldoutHardNegativeCanaryCount": len(canaries),
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
            "refutedSeedsReusedAsPositiveEvidence": False,
            "runtimeDefaultMutationAllowed": False,
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "manifestReadyForExportAudit": True,
            "positiveCropExamples": positives,
            "negativeCropExamples": negatives,
            "heldoutHardNegativeCanary": canaries,
        },
    )
    return candidate_root


def test_export_label_overlay_audit_writes_preview_labels_and_contact_sheets(tmp_path: Path) -> None:
    candidate_root = _write_manifest_bundle(tmp_path)

    payload = overlay_audit.run_v7_1_export_label_overlay_audit(storage_root=tmp_path)

    output_root = candidate_root / "v7_1_export_label_overlay_audit_v1"
    preview_root = output_root / "v7_1_export_preview"
    summary = _load_json(output_root / "v7_1_label_overlay_audit.json")
    transform_audit = _load_json(output_root / "v7_1_crop_label_transform_audit.json")
    consistency_audit = _load_json(output_root / "v7_1_export_manifest_consistency_audit.json")

    assert payload["primaryBlocker"] is None
    assert payload["readinessClass"] == "v7_1_export_overlay_audit_ready"
    assert payload["nextRecommendedNextLever"] == "v7_1_tiny_overfit_sanity_train"
    assert summary["positiveCropExampleCount"] == 90
    assert summary["positiveLabelFilesWithExactlyOneBall"] == 90
    assert summary["negativeLabelFilesEmpty"] == 180
    assert summary["heldoutCanaryLabelFilesEmpty"] == 20
    assert summary["trainingReady"] is False
    assert transform_audit["positiveLabelRoundTripMaxErrorPx"] <= 1.0
    assert consistency_audit["splitLeakageCount"] == 0
    assert consistency_audit["canaryLeakageCount"] == 0
    assert (preview_root / "data.yaml").exists()
    first_label = next((preview_root / "labels" / "train").glob("positive-*.txt"))
    fields = first_label.read_text(encoding="utf-8").strip().split()
    assert fields[0] == "0"
    assert all(0.0 <= float(value) <= 1.0 for value in fields[1:])
    first_negative_label = next((preview_root / "labels" / "train").glob("negative-*.txt"))
    assert first_negative_label.read_text(encoding="utf-8") == ""
    assert (output_root / "v7_1_overlay_contact_sheet_positive.jpg").exists()
    assert (output_root / "v7_1_overlay_contact_sheet_negative.jpg").exists()
    assert (output_root / "v7_1_overlay_contact_sheet_canary.jpg").exists()


def test_export_label_overlay_audit_blocks_bad_positive_bbox_roundtrip(tmp_path: Path) -> None:
    _write_manifest_bundle(tmp_path, bad_positive_bbox=True)

    payload = overlay_audit.run_v7_1_export_label_overlay_audit(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_export_bbox_roundtrip_error"
    assert payload["exportOverlayAuditPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_crop_transform_fix"


def test_export_label_overlay_audit_blocks_canary_leakage(tmp_path: Path) -> None:
    _write_manifest_bundle(tmp_path, canary_leak=True)

    payload = overlay_audit.run_v7_1_export_label_overlay_audit(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_export_canary_leakage"
    assert payload["exportOverlayAuditPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_crop_manifest_consistency_refresh"
