from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_negative_semantics_review as negative_review


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_review_bundle(tmp_path: Path) -> Path:
    storage_root = tmp_path
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    suite_root = storage_root / "benchmark_suites/frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "touchline_detector_candidate_v7_training_prep_v1/v7_training_manifest.json",
        {
            "positiveExampleCount": 1,
            "negativeExampleCount": 2,
            "positiveExamples": [
                {
                    "exampleId": "positive-10",
                    "frameIndex": 10,
                    "bbox": {"x1": 40.0, "y1": 40.0, "x2": 60.0, "y2": 60.0},
                    "truthUse": "reviewed_positive_training_seed",
                }
            ],
            "negativeExamples": [
                {
                    "exampleId": "negative-20",
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "candidateFrameId": "candidate-20",
                    "reviewItemId": "review-20",
                    "truthUse": "negative_only_refuted_seed",
                    "reviewDecision": "reject_seed",
                    "bbox": None,
                    "split": "train",
                },
                {
                    "exampleId": "negative-25",
                    "frameIndex": 25,
                    "sourceClipId": "trimed-5min.mp4",
                    "candidateFrameId": "candidate-25",
                    "reviewItemId": "review-25",
                    "truthUse": "negative_only_refuted_seed",
                    "reviewDecision": "reject_seed",
                    "bbox": None,
                    "split": "validation",
                },
            ],
        },
    )
    _write_json(
        candidate_root / "v7_training_data_quality_refresh_v1/v7_training_data_quality_summary.json",
        {
            "dominantBlockerClass": "v7_negative_semantics_unsafe",
            "unsafeFullFrameNegativeCount": 2,
            "hardNegativeCandidateCount": 3,
            "nextCorrectiveFamily": "v7_negative_semantics_review",
        },
    )
    _write_json(
        candidate_root / "v7_training_data_quality_refresh_v1/negative_semantics_audit.json",
        {
            "negativeExampleCount": 2,
            "fullFrameEmptyLabelNegativeCount": 2,
            "unsafeFullFrameNegativeCount": 2,
            "negativeSemanticsSafeForFullFrameTraining": False,
            "unsafeRows": [
                {
                    "exampleId": "negative-20",
                    "frameIndex": 20,
                    "reason": "empty_full_frame_negative_visible_ball_unknown",
                },
                {
                    "exampleId": "negative-25",
                    "frameIndex": 25,
                    "reason": "empty_full_frame_negative_visible_ball_unknown",
                },
            ],
        },
    )
    _write_json(
        candidate_root / "v7_training_data_quality_refresh_v1/hard_negative_mining_plan.json",
        {
            "dedupedTopLeftArtifactCandidateCount": 3,
            "sampledHardNegativeCandidates": [
                {
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 200.0, 230.0],
                    "truthUse": "hard_negative_top_left_artifact_candidate",
                },
                {
                    "frameIndex": 25,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 201.0, 231.0],
                    "truthUse": "hard_negative_top_left_artifact_candidate",
                },
                {
                    "frameIndex": 50,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 199.0, 229.0],
                    "truthUse": "hard_negative_top_left_artifact_candidate",
                },
            ],
        },
    )
    return candidate_root


def test_negative_semantics_review_packages_unsafe_full_frame_negatives(tmp_path: Path) -> None:
    candidate_root = _write_review_bundle(tmp_path)

    payload = negative_review.run_v7_negative_semantics_review(storage_root=tmp_path)

    output_root = candidate_root / "v7_negative_semantics_review_v1"
    summary = _load_json(output_root / "v7_negative_semantics_review_summary.json")
    review_manifest = _load_json(output_root / "full_frame_negative_review_manifest.json")
    crop_plan = _load_json(output_root / "negative_crop_conversion_plan.json")
    hard_negative_manifest = _load_json(output_root / "top_left_artifact_hard_negative_manifest.json")
    delta = _load_json(output_root / "v7_1_training_manifest_delta.json")

    assert payload["dominantBlockerClass"] == "v7_full_frame_negative_visible_ball_review_required"
    assert summary["unsafeFullFrameNegativeCount"] == 2
    assert summary["pendingVisibleBallReviewCount"] == 2
    assert summary["topLeftArtifactHardNegativeCandidateCount"] == 3
    assert summary["nextCorrectiveFamily"] == "v7_negative_crop_conversion_plan"
    assert len(review_manifest["reviewItems"]) == 2
    assert {row["decision"] for row in review_manifest["reviewItems"]} == {"pending_review"}
    assert all(row["reviewTask"] == "confirm_no_visible_ball_in_full_frame" for row in review_manifest["reviewItems"])
    assert crop_plan["fullFrameNegativesExcludedUntilReviewed"] == 2
    assert crop_plan["proposedTopLeftArtifactCropCount"] == 3
    assert hard_negative_manifest["candidateCount"] == 3
    assert delta["removeUnsafeFullFrameNegativesFromV7_1"] == 2
    assert delta["addTopLeftArtifactHardNegativeCrops"] == 3


def test_negative_semantics_review_selects_manifest_prep_when_negatives_are_safe(tmp_path: Path) -> None:
    candidate_root = _write_review_bundle(tmp_path)
    _write_json(
        candidate_root / "v7_training_data_quality_refresh_v1/negative_semantics_audit.json",
        {
            "negativeExampleCount": 2,
            "fullFrameEmptyLabelNegativeCount": 2,
            "unsafeFullFrameNegativeCount": 0,
            "negativeSemanticsSafeForFullFrameTraining": True,
            "unsafeRows": [],
        },
    )

    payload = negative_review.run_v7_negative_semantics_review(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_negative_semantics_review_clear"
    assert payload["nextCorrectiveFamily"] == "v7_1_training_manifest_prep"
