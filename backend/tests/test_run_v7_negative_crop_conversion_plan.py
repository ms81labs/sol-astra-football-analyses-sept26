from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_negative_crop_conversion_plan as crop_plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_crop_bundle(tmp_path: Path) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    suite_root = tmp_path / "benchmark_suites/frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "touchline_detector_candidate_v7_training_prep_v1/v7_training_manifest.json",
        {
            "positiveExamples": [
                {
                    "exampleId": "positive-10",
                    "frameIndex": 10,
                    "sourceClipId": "trimed-5min.mp4",
                    "bbox": {"x1": 40, "y1": 40, "x2": 60, "y2": 60},
                    "truthUse": "reviewed_positive_training_seed",
                }
            ],
            "negativeExamples": [
                {
                    "exampleId": "negative-20",
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "truthUse": "negative_only_refuted_seed",
                },
                {
                    "exampleId": "negative-25",
                    "frameIndex": 25,
                    "sourceClipId": "trimed-5min.mp4",
                    "truthUse": "negative_only_refuted_seed",
                },
            ],
        },
    )
    review_root = candidate_root / "v7_negative_semantics_review_v1"
    _write_json(
        review_root / "v7_negative_semantics_review_summary.json",
        {
            "dominantBlockerClass": "v7_full_frame_negative_visible_ball_review_required",
            "unsafeFullFrameNegativeCount": 2,
            "topLeftArtifactHardNegativeCandidateCount": 2,
            "nextCorrectiveFamily": "v7_negative_crop_conversion_plan",
        },
    )
    _write_json(
        review_root / "full_frame_negative_review_manifest.json",
        {
            "reviewItems": [
                {"exampleId": "negative-20", "frameIndex": 20, "decision": "pending_review"},
                {"exampleId": "negative-25", "frameIndex": 25, "decision": "pending_review"},
            ]
        },
    )
    _write_json(
        review_root / "top_left_artifact_hard_negative_manifest.json",
        {
            "candidateCount": 2,
            "candidates": [
                {
                    "hardNegativeId": "top-left-artifact-0000",
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 200.0, 230.0],
                    "truthUse": "local_hard_negative_top_left_artifact",
                },
                {
                    "hardNegativeId": "top-left-artifact-0001",
                    "frameIndex": 25,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 201.0, 231.0],
                    "truthUse": "local_hard_negative_top_left_artifact",
                },
            ],
        },
    )
    return candidate_root


def test_crop_conversion_plan_excludes_full_frame_negatives_and_adds_local_crops(tmp_path: Path) -> None:
    candidate_root = _write_crop_bundle(tmp_path)

    payload = crop_plan.run_v7_negative_crop_conversion_plan(storage_root=tmp_path)

    output_root = candidate_root / "v7_negative_crop_conversion_plan_v1"
    summary = _load_json(output_root / "v7_negative_crop_conversion_summary.json")
    manifest_delta = _load_json(output_root / "v7_1_training_manifest_delta.json")
    crop_manifest = _load_json(output_root / "local_hard_negative_crop_manifest.json")

    assert payload["dominantBlockerClass"] == "v7_negative_crop_conversion_ready"
    assert summary["unsafeFullFrameNegativeExcludedCount"] == 2
    assert summary["localHardNegativeCropCount"] == 2
    assert summary["nextCorrectiveFamily"] == "v7_1_training_manifest_prep"
    assert manifest_delta["positiveExamplesPreserved"] == 1
    assert manifest_delta["unsafeFullFrameNegativesExcluded"] == 2
    assert manifest_delta["localHardNegativeCropsAdded"] == 2
    assert manifest_delta["containsUnsafeFullFrameEmptyNegatives"] is False
    assert len(crop_manifest["crops"]) == 2
    assert all(crop["truthUse"] == "local_hard_negative_top_left_artifact" for crop in crop_manifest["crops"])
    assert all(crop["sourceFullFrameNegativeExported"] is False for crop in crop_manifest["crops"])


def test_crop_conversion_plan_blocks_when_no_crop_candidates_exist(tmp_path: Path) -> None:
    candidate_root = _write_crop_bundle(tmp_path)
    _write_json(
        candidate_root / "v7_negative_semantics_review_v1/top_left_artifact_hard_negative_manifest.json",
        {"candidateCount": 0, "candidates": []},
    )

    payload = crop_plan.run_v7_negative_crop_conversion_plan(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_negative_crop_conversion_no_safe_crops"
    assert payload["nextCorrectiveFamily"] == "v7_negative_visible_ball_review"
