from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_crop_manifest_consistency_refresh as crop_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_crop_consistency_bundle(
    tmp_path: Path,
    *,
    bad_positive_bbox: bool = False,
    leak_split: bool = False,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    prep_root = candidate_root / "v7_1_training_manifest_prep_v1"
    conversion_root = candidate_root / "v7_negative_crop_conversion_plan_v1"
    positive_examples = []
    for index in range(30):
        frame = 100000 + index * 70
        bbox = (
            {"x1": 100.0, "y1": 100.0, "x2": 100.0, "y2": 110.0}
            if bad_positive_bbox and index == 0
            else {"x1": 380.0 + index, "y1": 680.0, "x2": 396.0 + index, "y2": 696.0}
        )
        positive_examples.append(
            {
                "exampleId": f"positive-{frame}",
                "frameIndex": frame,
                "sourceClipId": "trimed-5min.mp4",
                "bbox": bbox,
                "truthUse": "reviewed_positive_training_seed",
                "split": "train" if index < 20 or leak_split else "validation",
            }
        )
    negative_examples = [
        {
            "exampleId": f"negative-{index}",
            "frameIndex": index * 300,
            "sourceClipId": "trimed-5min.mp4",
            "cropWindow": [0.0, 0.0, 200.0, 230.0],
            "truthUse": "local_hard_negative_top_left_artifact",
            "sourceFullFrameNegativeExported": False,
            "split": "train" if index < 160 or leak_split else "validation",
        }
        for index in range(200)
    ]
    if leak_split:
        negative_examples[0]["frameIndex"] = 100000
        negative_examples[0]["split"] = "validation"
    _write_json(
        prep_root / "v7_1_training_manifest.json",
        {
            "positiveExampleCount": len(positive_examples),
            "negativeExampleCount": len(negative_examples),
            "positiveExamples": positive_examples,
            "negativeExamples": negative_examples,
            "positiveTruthPolicy": "reviewed_positive_ball_bboxes_only",
            "negativeTruthPolicy": "local_crop_hard_negatives_only",
        },
    )
    _write_json(
        prep_root / "v7_1_manifest_quality_gate.json",
        {
            "trainingPrepReady": True,
            "unsafeFullFrameNegativeCount": 0,
            "refutedSeedPositiveLabelCount": 0,
        },
    )
    _write_json(
        conversion_root / "local_hard_negative_crop_manifest.json",
        {
            "cropCount": len(negative_examples),
            "crops": negative_examples,
        },
    )
    return candidate_root


def test_crop_manifest_consistency_builds_positive_crop_variants_and_caps_negatives(tmp_path: Path) -> None:
    candidate_root = _write_crop_consistency_bundle(tmp_path)

    payload = crop_refresh.run_v7_1_crop_manifest_consistency_refresh(storage_root=tmp_path)

    output_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    summary = _load_json(output_root / "v7_1_crop_manifest_consistency_summary.json")
    manifest = _load_json(output_root / "v7_1_local_crop_training_manifest.json")
    transform_audit = _load_json(output_root / "v7_1_positive_crop_transform_audit.json")
    negative_audit = _load_json(output_root / "v7_1_negative_crop_safety_audit.json")
    split_audit = _load_json(output_root / "v7_1_split_leakage_audit.json")
    overlay = _load_json(output_root / "v7_1_export_label_overlay_manifest.json")

    assert payload["dominantBlockerClass"] == "v7_1_crop_manifest_consistency_ready"
    assert summary["nextCorrectiveFamily"] == "v7_1_export_label_overlay_audit"
    assert summary["positiveCropExampleCount"] == 90
    assert summary["localHardNegativeCropCount"] == 180
    assert summary["heldoutHardNegativeCanaryCount"] == 20
    assert summary["unsafeFullFrameNegativeExportCount"] == 0
    assert summary["fullFrameEmptyLabelNegativeExportCount"] == 0
    assert summary["manifestReadyForExportAudit"] is True
    assert summary["promotionReady"] is False
    assert summary["candidateReadyForEvaluation"] is False
    assert len(manifest["positiveCropExamples"]) == 90
    assert len(manifest["negativeCropExamples"]) == 180
    assert len(manifest["heldoutHardNegativeCanary"]) == 20
    assert all(example["exportUse"] == "yolo_positive_crop_with_ball_label" for example in manifest["positiveCropExamples"])
    assert all(example["exportUse"] == "yolo_empty_label_crop" for example in manifest["negativeCropExamples"])
    assert all(example["ballFreeStatus"] == "deterministic_artifact_region_ball_free" for example in manifest["negativeCropExamples"])
    assert transform_audit["invalidPositiveCropCount"] == 0
    assert negative_audit["unsafeFullFrameNegativeExportCount"] == 0
    assert negative_audit["unreviewedNegativeCropCount"] == 0
    assert split_audit["splitLeakageCount"] == 0
    assert overlay["positiveOverlaySampleCount"] == 20
    assert overlay["negativeOverlaySampleCount"] == 20


def test_crop_manifest_consistency_blocks_invalid_positive_crop_transform(tmp_path: Path) -> None:
    _write_crop_consistency_bundle(tmp_path, bad_positive_bbox=True)

    payload = crop_refresh.run_v7_1_crop_manifest_consistency_refresh(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_1_manifest_positive_crop_transform_gap"
    assert payload["manifestReadyForExportAudit"] is False
    assert payload["nextCorrectiveFamily"] == "v7_1_positive_crop_transform_fix"


def test_crop_manifest_consistency_detects_split_leakage(tmp_path: Path) -> None:
    _write_crop_consistency_bundle(tmp_path, leak_split=True)

    payload = crop_refresh.run_v7_1_crop_manifest_consistency_refresh(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_1_manifest_split_leakage"
    assert payload["manifestReadyForExportAudit"] is False
    assert payload["nextCorrectiveFamily"] == "v7_1_split_policy_refresh"


def test_crop_manifest_consistency_repairs_split_leakage_by_group(tmp_path: Path) -> None:
    candidate_root = _write_crop_consistency_bundle(tmp_path, leak_split=True)

    payload = crop_refresh.run_v7_1_crop_manifest_consistency_refresh(
        storage_root=tmp_path,
        attempt_number=2,
        attempt_approach_family="crop_transform_quality_repair",
        repair_split_leakage=True,
    )

    output_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    split_audit = _load_json(output_root / "v7_1_split_leakage_audit.json")

    assert payload["dominantBlockerClass"] == "v7_1_crop_manifest_consistency_ready"
    assert payload["manifestReadyForExportAudit"] is True
    assert payload["nextCorrectiveFamily"] == "v7_1_export_label_overlay_audit"
    assert payload["attemptNumber"] == 2
    assert split_audit["splitLeakageCount"] == 0
    assert split_audit["splitPolicyRepairApplied"] is True
