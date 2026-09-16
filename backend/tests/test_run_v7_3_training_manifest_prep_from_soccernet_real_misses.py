from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_training_manifest_prep_from_soccernet_real_misses as prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _base_positive(index: int) -> dict[str, object]:
    return {
        "exampleId": f"v7-2-positive-{index}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 1000 + index,
        "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
        "cropFrameBbox": {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "cropBounds": [0.0, 0.0, 256.0, 256.0],
        "cropSizePx": 256,
        "truthUse": "reviewed_positive_training_seed",
        "exportUse": "yolo_positive_crop_with_ball_label",
        "splitGroupId": f"base-positive-group-{index // 3}",
        "split": "train" if index % 5 else "validation",
    }


def _negative(index: int, *, heldout: bool = False) -> dict[str, object]:
    return {
        "exampleId": f"{'canary' if heldout else 'neg'}-{index}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 2000 + index,
        "label": "no_ball",
        "truthUse": "local_hard_negative_crop_only",
        "exportUse": "yolo_empty_label_crop",
        "ballFreeStatus": "deterministic_artifact_region_ball_free",
        "cropWindow": [0.0, 0.0, 198.0, 233.0],
        "sourceFullFrameNegativeExported": False,
        "splitGroupId": f"{'canary' if heldout else 'neg'}-group-{index // 10}",
        "split": "heldout" if heldout else ("train" if index % 5 else "validation"),
    }


def _miss(index: int) -> dict[str, object]:
    return {
        "reviewItemId": f"soccernet-miss-review-{index:04d}",
        "reviewStatus": "reviewed_real_detector_miss_positive",
        "sourceClipId": "224p.mp4",
        "frameIndex": 500 + index * 30,
        "eventLabel": "SHOT" if index % 2 else "PASS",
        "eventPositionMs": 1000 + index * 1000,
        "gameTime": f"1 - 00:{index:02d}",
        "fullFrameImagePath": f"/tmp/soccernet-full-{index}.jpg",
        "cropImagePath": f"/tmp/soccernet-crop-{index}.jpg",
        "sourceFrameBbox": {"x1": 120.0, "y1": 80.0, "x2": 132.0, "y2": 92.0},
        "cropBoundsXyxy": [0.0, 0.0, 398.0, 224.0],
        "splitGroupId": f"soccernet-event-window-bucket-{index // 5:04d}",
        "trainingEligibility": "eligible_real_detector_miss_positive",
        "visibilityClass": "clear",
        "contextTags": ["small_ball", "in_play"],
    }


def _write_bundle(
    tmp_path: Path,
    *,
    miss_count: int = 65,
    base_positive_count: int = 414,
    negative_count: int = 180,
    canary_count: int = 20,
    invalid_miss_bbox: bool = False,
) -> Path:
    root = _candidate_root(tmp_path)
    v72_root = root / "v7_2_training_manifest_prep_v1"
    miss_root = root / "football_external_soccernet_detector_miss_manual_review_resolution_v1"
    misses = [_miss(index) for index in range(miss_count)]
    if invalid_miss_bbox and misses:
        misses[0]["sourceFrameBbox"] = {"x1": 20.0, "y1": 20.0, "x2": 200.0, "y2": 22.0}
    _write_json(
        v72_root / "v7_2_training_manifest.json",
        {
            "batchName": "v7_2_training_manifest_prep",
            "manifestReadyForExportAudit": True,
            "positiveCropExamples": [_base_positive(index) for index in range(base_positive_count)],
            "negativeCropExamples": [_negative(index) for index in range(negative_count)],
            "heldoutHardNegativeCanary": [_negative(index, heldout=True) for index in range(canary_count)],
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    _write_json(
        v72_root / "v7_2_training_manifest_prep_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "manifestReadyForExportAudit": True,
            "positiveCropExampleCount": base_positive_count,
            "localHardNegativeCropCount": negative_count,
            "heldoutHardNegativeCanaryCount": canary_count,
            "trainingExecuted": False,
        },
    )
    _write_json(
        miss_root / "detector_miss_manual_review_resolution_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "pendingReviewItemCount": 0,
            "reviewedRealDetectorMissPositiveCount": miss_count,
            "realDetectorMissCount": miss_count,
            "detectorTrainingNeededFromEvidence": miss_count > 0,
            "v7_3TrainingDataReady": miss_count > 0,
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        miss_root / "reviewed_real_detector_miss_truth_additions.json",
        {
            "reviewedRealDetectorMissPositiveCount": miss_count,
            "rows": misses,
        },
    )
    return root


def test_v73_manifest_prep_adds_real_miss_positive_crops_to_v72_baseline(tmp_path: Path) -> None:
    root = _write_bundle(tmp_path, miss_count=65)

    payload = prep.run_v7_3_training_manifest_prep_from_soccernet_real_misses(storage_root=tmp_path)

    output_root = root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
    manifest = json.loads((output_root / "v7_3_training_manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((output_root / "v7_3_manifest_quality_gate.json").read_text(encoding="utf-8"))

    assert payload["batchName"] == "v7_3_training_manifest_prep_from_soccernet_real_misses"
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["nextRecommendedNextLever"] == "v7_3_export_label_overlay_audit"
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert manifest["trainingCandidateName"] == "touchline_detector_candidate_v7_3"
    assert manifest["baseV72PositiveCropExampleCount"] == 414
    assert manifest["realMissReviewedPositiveSourceCount"] == 65
    assert manifest["realMissPositiveCropExampleCount"] == 195
    assert manifest["positiveCropExampleCount"] == 609
    assert manifest["localHardNegativeCropCount"] == 180
    assert manifest["heldoutHardNegativeCanaryCount"] == 20
    assert manifest["manifestReadyForExportAudit"] is True
    assert quality["trainingPrepReady"] is True
    real_miss_rows = [row for row in manifest["positiveCropExamples"] if row["truthUse"] == "reviewed_soccernet_real_detector_miss_positive"]
    assert len(real_miss_rows) == 195
    assert all(row["exportUse"] == "yolo_positive_crop_with_ball_label" for row in real_miss_rows)
    assert all(row["sourceDataset"] == "soccernet" for row in real_miss_rows)


def test_v73_manifest_prep_blocks_without_reviewed_real_misses(tmp_path: Path) -> None:
    _write_bundle(tmp_path, miss_count=0)

    payload = prep.run_v7_3_training_manifest_prep_from_soccernet_real_misses(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_3_manifest_no_reviewed_real_detector_misses"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_capture_and_label_queue"
    assert payload["trainingExecuted"] is False


def test_v73_manifest_prep_blocks_invalid_real_miss_bbox(tmp_path: Path) -> None:
    _write_bundle(tmp_path, miss_count=65, invalid_miss_bbox=True)

    payload = prep.run_v7_3_training_manifest_prep_from_soccernet_real_misses(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_3_manifest_real_miss_bbox_quality_gap"
    assert payload["invalidRealMissSourceCount"] > 0
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_manual_review_resolution"


def test_v73_manifest_prep_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_bundle(tmp_path, miss_count=65)

    payload = prep.run_v7_3_training_manifest_prep_from_soccernet_real_misses(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "v7_3_real_miss_manifest_prep",
        "v7_3_manifest_geometry_repair",
        "v7_3_manifest_blocker_summary",
    ]
