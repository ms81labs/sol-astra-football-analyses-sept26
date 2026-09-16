from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_touchline_detector_candidate_v7_training_prep


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _positive(frame: int, *, lineage: dict | None = None) -> dict:
    return {
        "bbox": {"x1": 10.0, "y1": 20.0, "x2": 20.0, "y2": 30.0},
        "candidateFrameId": f"candidate-positive-{frame}",
        "exampleId": f"old-positive-{frame}",
        "frameIndex": frame,
        "label": "ball",
        "lineage": lineage or {},
        "reviewDecision": "adjust_bbox",
        "reviewItemId": f"positive-{frame}",
        "sourceClipId": "trimed-5min.mp4",
        "timestampSeconds": frame / 25,
        "truthUse": "reviewed_positive_training_seed",
    }


def _negative(frame: int) -> dict:
    return {
        "candidateFrameId": f"candidate-negative-{frame}",
        "exampleId": f"old-negative-{frame}",
        "frameIndex": frame,
        "label": "not_ball_refuted_seed",
        "reviewDecision": "reject_seed",
        "reviewItemId": f"negative-{frame}",
        "sourceClipId": "trimed-5min.mp4",
        "truthUse": "negative_only_refuted_seed",
    }


def _pending(frame: int) -> dict:
    return {
        "frameIndex": frame,
        "reviewDecision": "pending_review",
        "reviewItemId": f"pending-{frame}",
        "sourceClipId": "trimed-5min.mp4",
        "truthUse": "pending_denominator_review",
    }


def _denominator_positive(frame: int) -> dict:
    return {
        "candidateFrameId": f"denominator-review-frame-{frame}",
        "frameIndex": frame,
        "lineage": {
            "acceptedGapFrameManifestPath": "accepted_gap_frame_manifest.json",
            "baselineDenominatorReviewSummaryPath": "baseline_denominator_review_summary.json",
            "labelingQueuePath": "v7_labeling_queue.json",
            "sourceClipId": "trimed-5min.mp4",
            "v7DatasetManifestPath": "v7_dataset_manifest.json",
        },
        "reviewDecision": "adjust_bbox",
        "reviewItemId": f"denominator-positive-{frame}",
        "reviewedBBox": {"x1": 30.0, "y1": 40.0, "x2": 42.0, "y2": 52.0},
        "sourceClipId": "trimed-5min.mp4",
        "timestampSeconds": frame / 25,
        "truthUse": "reviewed_positive_denominator_seed",
    }


def _denominator_negative(frame: int) -> dict:
    return {
        "candidateFrameId": f"denominator-review-frame-{frame}",
        "frameIndex": frame,
        "reviewDecision": "reject_seed",
        "reviewItemId": f"denominator-negative-{frame}",
        "sourceClipId": "trimed-5min.mp4",
        "truthUse": "reviewed_negative_denominator_refutation",
    }


def _write_inputs(
    tmp_path: Path,
    *,
    old_positives: list[dict],
    old_negatives: list[dict],
    pending: list[dict],
    denominator_positives: list[dict],
    denominator_negatives: list[dict],
) -> tuple[Path, Path, Path]:
    dataset_path = tmp_path / "v7_data_refresh" / "v7_dataset_manifest.json"
    denominator_seed_path = tmp_path / "denominator_resolution" / "reviewed_denominator_truth_seed.json"
    output_root = tmp_path / "v7_training_prep"
    _write_json(
        dataset_path,
        {
            "positiveExamples": old_positives,
            "negativeExamples": old_negatives,
            "pendingReviewFrames": pending,
        },
    )
    _write_json(
        denominator_seed_path,
        {
            "reviewedPositiveSeedRows": denominator_positives,
            "reviewedNegativeSeedRows": denominator_negatives,
            "reviewedPositiveSeedCount": len(denominator_positives),
            "reviewedNegativeSeedCount": len(denominator_negatives),
            "truthStatus": "review_resolved",
        },
    )
    return dataset_path, denominator_seed_path, output_root


def test_v7_training_prep_merges_reviewed_denominator_truth_and_clears_quality_gate(
    tmp_path: Path,
) -> None:
    dataset_path, denominator_seed_path, output_root = _write_inputs(
        tmp_path,
        old_positives=[_positive(frame) for frame in range(100, 117)],
        old_negatives=[_negative(frame) for frame in range(200, 274)],
        pending=[_pending(frame) for frame in range(300, 323)],
        denominator_positives=[_denominator_positive(frame) for frame in range(300, 319)],
        denominator_negatives=[_denominator_negative(frame) for frame in range(319, 323)],
    )

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_prep
        .run_promoted_v6_touchline_detector_candidate_v7_training_prep(
            dataset_manifest_path=dataset_path,
            denominator_truth_seed_path=denominator_seed_path,
            output_root=output_root,
            min_positive_examples=20,
            min_negative_examples=20,
        )
    )

    summary = payload["summary"]
    assert summary["trainingPrepReady"] is True
    assert summary["positiveExampleCount"] == 36
    assert summary["negativeExampleCount"] == 78
    assert summary["remainingPendingReviewCount"] == 0
    assert summary["refutedSeedsReusedAsPositiveEvidence"] is False
    assert summary["nextCorrectiveFamily"] == "touchline_detector_candidate_v7_training"
    assert summary["runtimeDefaultChanged"] is False
    assert summary["sourceManifestMutated"] is False

    manifest = payload["trainingManifest"]
    assert {row["frameIndex"] for row in manifest["positiveExamples"]} >= set(range(300, 319))
    assert {row["frameIndex"] for row in manifest["negativeExamples"]} >= set(range(319, 323))
    assert all(row["truthUse"] != "pending_denominator_review" for row in manifest["positiveExamples"])
    assert (output_root / "v7_training_manifest.json").exists()
    assert (output_root / "v7_training_quality_gate.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_v7_training_prep_keeps_refuted_overlap_out_of_positive_examples(tmp_path: Path) -> None:
    dataset_path, denominator_seed_path, output_root = _write_inputs(
        tmp_path,
        old_positives=[_positive(100), _positive(200)],
        old_negatives=[_negative(200), _negative(201)],
        pending=[],
        denominator_positives=[],
        denominator_negatives=[],
    )

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_prep
        .run_promoted_v6_touchline_detector_candidate_v7_training_prep(
            dataset_manifest_path=dataset_path,
            denominator_truth_seed_path=denominator_seed_path,
            output_root=output_root,
            min_positive_examples=1,
            min_negative_examples=1,
        )
    )

    manifest = payload["trainingManifest"]
    assert {row["frameIndex"] for row in manifest["positiveExamples"]} == {100}
    assert payload["summary"]["refutedSeedsReusedAsPositiveEvidence"] is True
    assert payload["summary"]["trainingPrepReady"] is True
    assert "refuted_positive_overlap_removed" in payload["summary"]["qualityWarnings"]
    assert payload["summary"]["weakEvidenceReasons"] == []


def test_v7_training_prep_blocks_when_positive_boxes_are_missing(tmp_path: Path) -> None:
    bad_positive = _positive(100)
    bad_positive["bbox"] = None
    dataset_path, denominator_seed_path, output_root = _write_inputs(
        tmp_path,
        old_positives=[bad_positive],
        old_negatives=[_negative(200)],
        pending=[],
        denominator_positives=[],
        denominator_negatives=[],
    )

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_prep
        .run_promoted_v6_touchline_detector_candidate_v7_training_prep(
            dataset_manifest_path=dataset_path,
            denominator_truth_seed_path=denominator_seed_path,
            output_root=output_root,
            min_positive_examples=1,
            min_negative_examples=1,
        )
    )

    assert payload["summary"]["trainingPrepReady"] is False
    assert "positive_bbox_missing" in payload["summary"]["weakEvidenceReasons"]
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_positive_expansion"


def test_v7_training_prep_blocks_when_denominator_review_is_still_pending(tmp_path: Path) -> None:
    dataset_path, denominator_seed_path, output_root = _write_inputs(
        tmp_path,
        old_positives=[_positive(frame) for frame in range(100, 125)],
        old_negatives=[_negative(frame) for frame in range(200, 225)],
        pending=[_pending(300)],
        denominator_positives=[],
        denominator_negatives=[],
    )

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_prep
        .run_promoted_v6_touchline_detector_candidate_v7_training_prep(
            dataset_manifest_path=dataset_path,
            denominator_truth_seed_path=denominator_seed_path,
            output_root=output_root,
            min_positive_examples=20,
            min_negative_examples=20,
        )
    )

    assert payload["summary"]["trainingPrepReady"] is False
    assert payload["summary"]["remainingPendingReviewCount"] == 1
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_denominator_expansion"
