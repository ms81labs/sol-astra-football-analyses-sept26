from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_positive_diversity_refresh as diversity


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive(frame: int, *, group: str = "g1") -> dict[str, object]:
    return {
        "exampleId": f"pos-{frame}-256",
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
        "cropFrameBbox": {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "cropSizePx": 256,
        "splitGroupId": group,
        "truthUse": "reviewed_positive_training_seed",
    }


def _write_bundle(tmp_path: Path, *, source_count: int = 30, groups: int = 3) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    pipeline_root = candidate_root / "v7_1_full_pipeline_non_promotion_eval_v1"
    guardrail_root = candidate_root / "v7_1_crop_probe_precision_guardrail_audit_v1"
    positive_crops = []
    for source_index in range(source_count):
        frame = 100 + source_index * 5
        group = f"group-{source_index % groups}"
        for size in (192, 256, 384):
            row = _positive(frame, group=group)
            row["exampleId"] = f"pos-{frame}-{size}"
            row["cropSizePx"] = size
            positive_crops.append(row)
    _write_json(
        manifest_root / "v7_1_local_crop_training_manifest.json",
        {
            "reviewedPositiveSourceCount": source_count,
            "positiveCropExamples": positive_crops,
            "negativeCropExamples": [{"exampleId": "neg-1", "exportUse": "yolo_empty_label_crop"}],
            "heldoutHardNegativeCanary": [{"exampleId": "canary-1", "exportUse": "yolo_empty_label_crop"}],
            "fullFrameEmptyLabelNegativeExportCount": 0,
            "unsafeFullFrameNegativeExportCount": 0,
            "refutedSeedsReusedAsPositiveEvidence": False,
        },
    )
    _write_json(
        guardrail_root / "validation_positive_miss_analysis.json",
        {
            "missCount": 9,
            "misses": [
                {
                    "exampleId": f"pos-{100 + index * 5}-256",
                    "missType": "no_prediction",
                    "imagePath": str(tmp_path / f"miss-{index}.jpg"),
                }
                for index in range(9)
            ],
        },
    )
    _write_json(
        pipeline_root / "positive_miss_analysis.json",
        {
            "missCount": 2,
            "misses": [
                {
                    "frameIndex": 100,
                    "sourceClipId": "trimed-5min.mp4",
                    "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
                },
                {
                    "frameIndex": 105,
                    "sourceClipId": "trimed-5min.mp4",
                    "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
                },
            ],
        },
    )
    _write_json(
        pipeline_root / "reviewed_positive_pipeline_audit.json",
        {
            "frameRows": [
                {
                    "frameIndex": 100 + index * 5,
                    "sourceClipId": "trimed-5min.mp4",
                    "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
                    "sourceFrameLocalized": True,
                }
                for index in range(source_count)
            ]
        },
    )
    _write_json(
        pipeline_root / "v7_1_full_pipeline_non_promotion_summary.json",
        {
            "goalAchieved": True,
            "secondaryConcern": "v7_1_validation_positive_recall_limited",
            "sourceFrameLocalizationHitRate": 0.933333,
        },
    )
    return candidate_root


def test_positive_diversity_refresh_writes_review_queue_and_blocks_training_prep_when_count_is_low(tmp_path: Path) -> None:
    candidate_root = _write_bundle(tmp_path)

    payload = diversity.run_v7_1_positive_diversity_refresh(storage_root=tmp_path)

    output_root = candidate_root / "v7_1_positive_diversity_refresh_v1"
    queue = json.loads((output_root / "positive_review_queue.json").read_text(encoding="utf-8"))

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_insufficient_reviewed_count"
    assert payload["previousReviewedPositiveSourceCount"] == 30
    assert payload["newReviewedPositiveSourceCount"] == 0
    assert payload["knownCropValidationMissesIncluded"] == 9
    assert payload["knownFullPipelineMissesIncluded"] == 2
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_expansion"
    assert queue["candidateCount"] >= 11
    assert (output_root / "known_miss_refresh_plan.json").exists()


def test_positive_diversity_refresh_advances_when_reviewed_count_and_groups_are_sufficient(tmp_path: Path) -> None:
    _write_bundle(tmp_path, source_count=120, groups=8)

    payload = diversity.run_v7_1_positive_diversity_refresh(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["totalReviewedPositiveSourceCount"] == 120
    assert payload["distinctPositiveSplitGroupCount"] == 8
    assert payload["nextRecommendedNextLever"] == "v7_2_training_manifest_prep"


def test_positive_diversity_refresh_blocks_split_leakage(tmp_path: Path) -> None:
    candidate_root = _write_bundle(tmp_path, source_count=120, groups=8)
    manifest_path = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1" / "v7_1_local_crop_training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["positiveCropExamples"][0]["split"] = "train"
    manifest["positiveCropExamples"][1]["split"] = "validation"
    manifest["positiveCropExamples"][0]["splitGroupId"] = "leaky-group"
    manifest["positiveCropExamples"][1]["splitGroupId"] = "leaky-group"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = diversity.run_v7_1_positive_diversity_refresh(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_split_leakage"
    assert payload["splitLeakageCount"] == 1
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_split_policy_refresh"
