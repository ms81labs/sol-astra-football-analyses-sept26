from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_gold_truth_seed_refuted_refresh as refuted_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"positive-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "trimed-5min.mp4-proposal-selection-0255-0300",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "accept_seed",
        "seedBBox": {"x1": 10.0, "y1": 20.0, "x2": 25.0, "y2": 35.0},
        "reviewedBBox": {"x1": 10.0, "y1": 20.0, "x2": 25.0, "y2": 35.0},
        "lineage": {
            "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
            "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        },
    }


def _negative_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"negative-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "frameIndex": frame_id,
        "reviewDecision": "reject_seed",
    }


def _write_inputs(
    root: Path,
    *,
    positive_frames: list[int] | None = None,
    negative_frames: list[int] | None = None,
) -> dict[str, Path]:
    positive_frames = positive_frames or [260, 290, 295, 300]
    negative_frames = negative_frames or list(range(1000, 1074))
    output_root = root / "gold_truth_seed_refuted_refresh_v1"
    reviewed_followthrough_root = root / "reviewed_followthrough_selection_fix_v1"
    manual_resolution_root = root / "manual_resolution"
    manual_review_root = root / "manual_review"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "frozen_source_manifest.json"

    positives = [_positive_row(frame_id) for frame_id in positive_frames]
    negatives = [_negative_row(frame_id) for frame_id in negative_frames]
    _write_json(
        reviewed_followthrough_root / "reviewed_followthrough_selection_summary.json",
        {
            "batchStatus": "succeeded",
            "dominantBlockerClass": "reviewed_positive_evidence_too_sparse",
            "nextCorrectiveFamily": "gold_truth_seed_refuted_refresh",
            "reviewedPositiveSeedCount": len(positives),
            "reviewedNegativeSeedCount": len(negatives),
            "reviewedPositiveFrames": positive_frames,
            "weakEvidenceReasons": [
                "reviewed_positive_seed_count_below_detector_fix_floor",
                "bootstrap_seed_surface_mostly_refuted_by_review",
            ],
        },
    )
    _write_json(
        reviewed_followthrough_root / "reviewed_positive_followthrough_matrix.json",
        {
            "reviewedPositiveSeedCount": len(positives),
            "bucketCounts": {"reviewed_positive_evidence_too_sparse": len(positives)},
            "reviewedPositiveFrames": positives,
        },
    )
    _write_json(
        reviewed_followthrough_root / "reviewed_seed_refutation_matrix.json",
        {
            "rejectedSeedCount": len(negatives),
            "rejectedSeedsReusedAsPositiveEvidence": False,
            "rejectedSeedRows": [
                {**row, "refutationUse": "negative_only_do_not_use_as_positive"} for row in negatives
            ],
        },
    )
    _write_json(
        manual_resolution_root / "reviewed_followthrough_truth_seed.json",
        {
            "truthStatus": "review_resolved",
            "reviewedPositiveSeedCount": len(positives),
            "reviewedNegativeSeedCount": len(negatives),
            "reviewedPositiveSeedRows": positives,
            "reviewedNegativeSeedRows": negatives,
        },
    )
    _write_json(
        manual_review_root / "reviewed_label_overlay.json",
        {
            "reviewItemCount": len(positives) + len(negatives),
            "pendingReviewCount": 0,
            "acceptedSeedCount": len(positives),
            "rejectedSeedCount": len(negatives),
            "reviewedPositiveCount": len(positives),
            "reviewedNegativeCount": len(negatives),
            "reviewItems": [
                {
                    "reviewItemId": row["reviewItemId"],
                    "candidateFrameId": row["candidateFrameId"],
                    "frameIndex": row["frameIndex"],
                    "decision": "accept_seed",
                    "reviewedBBox": row["reviewedBBox"],
                    "seedBBox": row["seedBBox"],
                }
                for row in positives
            ]
            + [
                {
                    "reviewItemId": row["reviewItemId"],
                    "candidateFrameId": row["candidateFrameId"],
                    "frameIndex": row["frameIndex"],
                    "decision": "reject_seed",
                    "reviewedBBox": None,
                    "seedBBox": {"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 6.0},
                }
                for row in negatives
            ],
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
            "acceptedRetentionRatio": 0.069,
            "controlledRetentionRatio": 0.102,
        },
    )
    _write_json(
        suite_root / "suite_summary.json",
        {
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    _write_json(runtime_default_path, {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    return {
        "output_root": output_root,
        "reviewed_followthrough_root": reviewed_followthrough_root,
        "manual_resolution_root": manual_resolution_root,
        "manual_review_root": manual_review_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_refuted_refresh_preserves_four_reviewed_positive_frames(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    payload = refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveSeedCount"] == 4
    assert summary["reviewedPositiveFrames"] == [260, 290, 295, 300]
    assert summary["nextCorrectiveFamily"] == "manual_review_expansion"
    positive_manifest = json.loads((paths["output_root"] / "reviewed_positive_truth_manifest.json").read_text())
    assert [row["frameIndex"] for row in positive_manifest["reviewedPositiveSeeds"]] == [260, 290, 295, 300]


def test_refuted_refresh_preserves_rejected_seeds_as_negative_only(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    refutation = json.loads((paths["output_root"] / "rejected_seed_refutation_manifest.json").read_text())
    assert refutation["rejectedSeedCount"] == 74
    assert refutation["rejectedSeedsReusedAsPositiveEvidence"] is False
    assert {row["refutationUse"] for row in refutation["rejectedSeeds"]} == {
        "negative_only_do_not_use_as_positive"
    }


def test_refuted_refresh_writes_all_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    for filename in (
        "gold_truth_seed_refuted_summary.json",
        "reviewed_positive_truth_manifest.json",
        "rejected_seed_refutation_manifest.json",
        "source_manifest_delta.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_refuted_refresh_writes_proposed_source_manifest_delta_only(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    source_manifest_before = paths["source_manifest_path"].read_text()

    refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    delta = json.loads((paths["output_root"] / "source_manifest_delta.json").read_text())
    assert delta["mutationPolicy"] == "not_mutated_delta_only"
    assert delta["positiveFrameIds"] == [260, 290, 295, 300]
    assert delta["rejectedSeedCount"] == 74
    assert paths["source_manifest_path"].read_text() == source_manifest_before


def test_refuted_refresh_selects_micro_validation_when_enough_positive_frames(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, positive_frames=list(range(200, 208)), negative_frames=[1000, 1001])

    payload = refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    assert payload["summary"]["nextCorrectiveFamily"] == "reviewed_positive_micro_validation"
    assert payload["summary"]["reviewedPositiveSeedCount"] == 8


def test_refuted_refresh_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    refuted_refresh.run_promoted_v6_gold_truth_seed_refuted_refresh(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
