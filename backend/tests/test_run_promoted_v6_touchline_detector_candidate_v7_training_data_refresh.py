from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _positive(frame: int) -> dict:
    return {
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "timestampSeconds": frame / 25,
        "reviewDecision": "adjust_bbox",
        "reviewedBBox": {"x1": 10.0, "y1": 20.0, "x2": 18.0, "y2": 28.0},
        "reviewItemId": f"positive-{frame}",
        "candidateFrameId": f"candidate-positive-{frame}",
    }


def _negative(frame: int) -> dict:
    return {
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "reject_seed",
        "reviewItemId": f"negative-{frame}",
        "candidateFrameId": f"candidate-negative-{frame}",
        "refutationUse": "negative_only_do_not_use_as_positive",
    }


def _unreviewed(frame: int) -> dict:
    return {
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "classification": "unreviewed_denominator_frame",
        "gapClass": "baseline_accepted_no_promoted_proposal",
        "reviewTruthClass": "unreviewed",
    }


def test_v7_training_data_refresh_writes_dataset_manifest_without_reusing_refuted_seeds(
    tmp_path: Path,
) -> None:
    lane_root = tmp_path / "v7_training_data_lane_v1"
    output_root = tmp_path / "touchline_detector_candidate_v7_training_data_refresh_v1"
    _write_json(
        lane_root / "v7_training_data_manifest.json",
        {
            "reviewedPositiveFrames": [_positive(frame) for frame in [240, 245, 250]],
            "refutedNegativeFrames": [_negative(frame) for frame in [255, 260]],
            "unreviewedDenominatorFrames": [_unreviewed(frame) for frame in [300, 305]],
            "hardMiningCandidateFrames": [_unreviewed(frame) for frame in [300, 305, 310]],
        },
    )
    _write_json(
        lane_root / "v7_training_data_lane_summary.json",
        {
            "reviewedPositiveFrameCount": 3,
            "refutedNegativeFrameCount": 2,
            "unreviewedDenominatorFrameCount": 2,
            "hardMiningCandidateCount": 3,
            "upstreamEffectiveAcceptedRetentionRatio": 0.212,
        },
    )

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh
        .run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
            lane_root=lane_root,
            output_root=output_root,
            min_reviewed_positive_frames=5,
        )
    )

    summary = payload["summary"]
    assert summary["reviewedPositiveFrameCount"] == 3
    assert summary["refutedNegativeFrameCount"] == 2
    assert summary["pendingReviewFrameCount"] == 2
    assert summary["refutedSeedsReusedAsPositiveEvidence"] is False
    assert summary["runtimeDefaultChanged"] is False
    assert summary["sourceManifestMutated"] is False

    dataset = payload["datasetManifest"]
    assert {row["frameIndex"] for row in dataset["positiveExamples"]} == {240, 245, 250}
    assert {row["frameIndex"] for row in dataset["negativeExamples"]} == {255, 260}
    assert all(row["truthUse"] == "negative_only_refuted_seed" for row in dataset["negativeExamples"])
    assert not any(row["frameIndex"] in {255, 260} for row in dataset["positiveExamples"])
    assert (output_root / "v7_dataset_manifest.json").exists()
    assert (output_root / "v7_training_quality_gate.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_v7_training_data_refresh_selects_review_queue_when_positive_evidence_is_sparse(
    tmp_path: Path,
) -> None:
    lane_root = tmp_path / "v7_training_data_lane_v1"
    output_root = tmp_path / "touchline_detector_candidate_v7_training_data_refresh_v1"
    _write_json(
        lane_root / "v7_training_data_manifest.json",
        {
            "reviewedPositiveFrames": [_positive(frame) for frame in [240, 245]],
            "refutedNegativeFrames": [_negative(frame) for frame in [255]],
            "unreviewedDenominatorFrames": [_unreviewed(frame) for frame in [300]],
            "hardMiningCandidateFrames": [],
        },
    )
    _write_json(lane_root / "v7_training_data_lane_summary.json", {})

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh
        .run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
            lane_root=lane_root,
            output_root=output_root,
            min_reviewed_positive_frames=5,
        )
    )

    assert payload["summary"]["trainingReady"] is False
    assert payload["summary"]["batchStatus"] == "packaged_not_train_ready"
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_denominator_expansion"
    assert payload["qualityGate"]["weakEvidenceReasons"] == [
        "reviewed_positive_count_below_minimum",
        "unreviewed_denominator_frames_pending",
    ]


def test_v7_training_data_refresh_selects_training_prep_when_quality_gate_passes(
    tmp_path: Path,
) -> None:
    lane_root = tmp_path / "v7_training_data_lane_v1"
    output_root = tmp_path / "touchline_detector_candidate_v7_training_data_refresh_v1"
    _write_json(
        lane_root / "v7_training_data_manifest.json",
        {
            "reviewedPositiveFrames": [_positive(frame) for frame in range(100, 110)],
            "refutedNegativeFrames": [_negative(frame) for frame in range(200, 210)],
            "unreviewedDenominatorFrames": [],
            "hardMiningCandidateFrames": [],
        },
    )
    _write_json(lane_root / "v7_training_data_lane_summary.json", {})

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh
        .run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
            lane_root=lane_root,
            output_root=output_root,
            min_reviewed_positive_frames=5,
        )
    )

    assert payload["summary"]["trainingReady"] is True
    assert payload["summary"]["nextCorrectiveFamily"] == "touchline_detector_candidate_v7_training_prep"


def test_v7_training_data_refresh_does_not_loop_same_batch_when_positives_remain_sparse(
    tmp_path: Path,
) -> None:
    lane_root = tmp_path / "v7_training_data_lane_v1"
    output_root = tmp_path / "touchline_detector_candidate_v7_training_data_refresh_v1"
    _write_json(
        lane_root / "v7_training_data_manifest.json",
        {
            "reviewedPositiveFrames": [_positive(frame) for frame in [240, 245]],
            "refutedNegativeFrames": [_negative(frame) for frame in [255]],
            "unreviewedDenominatorFrames": [],
            "hardMiningCandidateFrames": [],
        },
    )
    _write_json(lane_root / "v7_training_data_lane_summary.json", {})

    payload = (
        run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh
        .run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
            lane_root=lane_root,
            output_root=output_root,
            min_reviewed_positive_frames=5,
        )
    )

    assert payload["summary"]["trainingReady"] is False
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_positive_expansion"
