from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_training_manifest_prep as prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive(frame: int, *, source: str = "reviewed") -> dict[str, object]:
    return {
        "candidateId": f"{source}-{frame}",
        "reviewStatus": "reviewed_positive_ball",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame,
        "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
        "splitGroupId": f"trimed-5min.mp4-cluster-{frame // 60:04d}",
        "trainingEligibility": "eligible_positive_truth",
        "visibilityClass": "clear",
        "contextTags": ["small_ball"],
    }


def _write_bundle(tmp_path: Path, *, positive_count: int = 130, unsafe_negative: bool = False) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    v1_manifest_root = root / "v7_1_crop_manifest_consistency_refresh_v1"
    v1_resolution_root = root / "v7_1_positive_diversity_manual_review_resolution_v1"
    v1_mining_root = root / "v7_1_positive_candidate_mining_expansion_v1"
    v2_resolution_root = root / "v7_1_positive_diversity_manual_review_resolution_v2"
    _write_json(
        v1_manifest_root / "v7_1_local_crop_training_manifest.json",
        {
            "positiveCropExamples": [
                {
                    "exampleId": f"old-crop-{index}",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": index * 5,
                    "sourceFrameBbox": {"x1": 80.0, "y1": 100.0, "x2": 96.0, "y2": 116.0},
                    "splitGroupId": f"old-group-{index // 4}",
                    "split": "train",
                }
                for index in range(30)
            ],
            "negativeCropExamples": [
                {
                    "exampleId": f"neg-{index}",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": index,
                    "sourceFalsePositiveBbox": [0.0, 0.0, 200.0, 230.0],
                    **(
                        {"sourceFullFrameNegativeExported": True}
                        if unsafe_negative
                        else {
                            "truthUse": "local_hard_negative_crop_only",
                            "exportUse": "yolo_empty_label_crop",
                            "ballFreeStatus": "deterministic_artifact_region_ball_free",
                        }
                    ),
                    "splitGroupId": f"neg-group-{index // 20}",
                    "split": "train",
                }
                for index in range(180)
            ],
            "heldoutHardNegativeCanary": [
                {
                    "exampleId": f"canary-{index}",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": index,
                    "cropWindow": [0.0, 0.0, 200.0, 230.0],
                    "sourceFullFrameNegativeExported": False,
                    "splitGroupId": f"canary-group-{index}",
                    "split": "heldout",
                }
                for index in range(20)
            ],
        },
    )
    _write_json(v1_resolution_root / "reviewed_positive_truth_additions.json", {"rows": [_positive(1000 + index, source="v1") for index in range(4)]})
    _write_json(v1_mining_root / "corrected_label_overlay.json", {"reviewItems": [_positive(2000 + index, source="mining") for index in range(69)]})
    remaining = max(0, positive_count - 30 - 4 - 69)
    _write_json(v2_resolution_root / "reviewed_positive_truth_additions.json", {"rows": [_positive(3000 + index, source="v3") for index in range(remaining)]})
    _write_json(
        v2_resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json",
        {
            "goalAchieved": positive_count >= 120,
            "totalReviewedPositiveSourceCount": positive_count,
            "newReviewedPositiveSourceCount": remaining,
            "distinctPositiveSplitGroupCount": 8,
            "nextRecommendedNextLever": "v7_2_training_manifest_prep",
        },
    )
    return root


def test_v7_2_training_manifest_prep_merges_reviewed_positives_and_preserves_negatives(tmp_path: Path) -> None:
    root = _write_bundle(tmp_path, positive_count=130)

    payload = prep.run_v7_2_training_manifest_prep(storage_root=tmp_path)

    output_root = root / "v7_2_training_manifest_prep_v1"
    manifest = json.loads((output_root / "v7_2_training_manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((output_root / "v7_2_manifest_quality_gate.json").read_text(encoding="utf-8"))

    assert payload["batchName"] == "v7_2_training_manifest_prep"
    assert payload["goalAchieved"] is True
    assert payload["nextRecommendedNextLever"] == "v7_2_export_label_overlay_audit"
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert manifest["trainingCandidateName"] == "touchline_detector_candidate_v7_2"
    assert manifest["reviewedPositiveSourceCount"] == 130
    assert manifest["positiveCropExampleCount"] == 390
    assert manifest["localHardNegativeCropCount"] == 180
    assert manifest["heldoutHardNegativeCanaryCount"] == 20
    assert quality["trainingPrepReady"] is True
    assert all(row["truthUse"] == "reviewed_positive_training_seed" for row in manifest["positiveCropExamples"])
    assert all(row["exportUse"] == "yolo_empty_label_crop" for row in manifest["negativeCropExamples"])


def test_v7_2_training_manifest_prep_blocks_unsafe_negative_leak(tmp_path: Path) -> None:
    _write_bundle(tmp_path, positive_count=130, unsafe_negative=True)

    payload = prep.run_v7_2_training_manifest_prep(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "v7_2_manifest_unsafe_negative_leak"
    assert payload["nextRecommendedNextLever"] == "v7_negative_crop_conversion_plan"
