from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_manual_review_expansion as manual_review_expansion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bbox(frame_id: int) -> dict[str, float]:
    return {
        "x1": float(frame_id),
        "y1": float(frame_id + 1),
        "x2": float(frame_id + 10),
        "y2": float(frame_id + 11),
    }


def _lineage() -> dict[str, str]:
    return {
        "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
        "baselineSelectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
        "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        "promotedSelectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
    }


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"positive-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "trimed-5min.mp4-reviewed-positive-0260-0300",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "accept_seed",
        "seedBBox": _bbox(frame_id),
        "reviewedBBox": _bbox(frame_id),
        "lineage": _lineage(),
        "truthUse": "provisional_reviewed_positive",
    }


def _rejected_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"negative-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "frameIndex": frame_id,
        "reviewDecision": "reject_seed",
        "seedBBox": _bbox(frame_id),
        "refutationUse": "negative_only_do_not_use_as_positive",
    }


def _write_inputs(root: Path, *, with_video: bool = False) -> dict[str, Path]:
    output_root = root / "manual_review_expansion_v1"
    refuted_root = root / "gold_truth_seed_refuted_refresh_v1"
    prior_review_root = root / "promoted_v6_manual_review_followthrough_v1"
    retention_root = root / "retention"
    suite_root = root / "suite"
    video_path = root / "videos" / "trimed-5min.mp4"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "frozen_source_manifest.json"
    if with_video:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"not-a-real-video")

    positives = [_positive_row(frame_id) for frame_id in [260, 290, 295, 300]]
    rejected_frame_ids = [255, 265, 270] + list(range(1000, 1071))
    rejected = [_rejected_row(frame_id) for frame_id in rejected_frame_ids]
    prior_frames = [
        {
            "reviewItemId": f"prior-{frame_id}",
            "candidateFrameId": f"prior-candidate-{frame_id}",
            "windowId": "trimed-5min.mp4-proposal-selection-0255-0300",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": frame_id,
            "timestampSeconds": round(frame_id / 25.0, 3),
            "fileStem": f"prior-{frame_id}",
            "seedBBox": _bbox(frame_id),
            "imagePath": None,
            "imageExtracted": False,
            "imageExtractionError": "fixture",
        }
        for frame_id in range(240, 321, 5)
    ]
    _write_json(
        refuted_root / "reviewed_positive_truth_manifest.json",
        {
            "truthStatus": "review_resolved",
            "truthPolicy": "reviewed_positive_seed_only",
            "reviewedPositiveSeedCount": len(positives),
            "positiveFrameIds": [260, 290, 295, 300],
            "reviewedPositiveSeeds": positives,
        },
    )
    _write_json(
        refuted_root / "rejected_seed_refutation_manifest.json",
        {
            "truthPolicy": "rejected_seed_refutation_only",
            "rejectedSeedCount": len(rejected),
            "rejectedSeedsReusedAsPositiveEvidence": False,
            "rejectedSeeds": rejected,
        },
    )
    _write_json(
        prior_review_root / "reviewed_label_overlay.json",
        {
            "reviewItemCount": 78,
            "pendingReviewCount": 0,
            "acceptedSeedCount": 4,
            "rejectedSeedCount": 74,
            "reviewItems": positives + rejected,
        },
    )
    _write_json(
        prior_review_root / "review_frame_manifest.json",
        {
            "reviewFrameCount": len(prior_frames),
            "reviewFrames": prior_frames,
            "imageExtractionStatus": "fixture",
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
        "refuted_root": refuted_root,
        "prior_review_root": prior_review_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "video_path": video_path,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_manual_review_expansion_creates_deterministic_review_window(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    payload = manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["batchStatus"] == "manual_review_pending"
    assert summary["expansionFrameIds"] == list(range(240, 321, 5))
    overlay = json.loads((paths["output_root"] / "reviewed_label_overlay.json").read_text())
    assert overlay["reviewItemCount"] == 17
    assert [item["frameIndex"] for item in overlay["reviewItems"]] == list(range(240, 321, 5))


def test_manual_review_expansion_preserves_positive_anchors_and_pending_neighbors(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    overlay = json.loads((paths["output_root"] / "reviewed_label_overlay.json").read_text())
    by_frame = {item["frameIndex"]: item for item in overlay["reviewItems"]}
    assert overlay["acceptedSeedCount"] == 4
    assert overlay["pendingReviewCount"] == 13
    for frame_id in [260, 290, 295, 300]:
        assert by_frame[frame_id]["decision"] == "accept_seed"
        assert by_frame[frame_id]["seedBBox"] == _bbox(frame_id)
        assert by_frame[frame_id]["reviewedBBox"] == _bbox(frame_id)
        assert by_frame[frame_id]["lineageComplete"] is True
    assert by_frame[240]["decision"] == "pending_review"
    assert by_frame[240]["seedBBox"] is None
    assert by_frame[240]["reviewedBBox"] is None


def test_manual_review_expansion_preserves_rejected_seeds_as_refutation_only(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    guard = json.loads((paths["output_root"] / "refutation_guard_manifest.json").read_text())
    assert guard["rejectedSeedCount"] == 74
    assert guard["rejectedSeedsReusedAsPositiveEvidence"] is False
    assert {row["refutationUse"] for row in guard["rejectedSeeds"]} == {
        "negative_only_do_not_use_as_positive"
    }
    overlay = json.loads((paths["output_root"] / "reviewed_label_overlay.json").read_text())
    assert all(item.get("refutedBBox") is not None for item in overlay["reviewItems"] if item["frameIndex"] in {255, 265, 270})
    assert all(item["decision"] != "accept_seed" for item in overlay["reviewItems"] if item["frameIndex"] not in {260, 290, 295, 300})


def test_manual_review_expansion_writes_all_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    for filename in (
        "manual_review_expansion_summary.json",
        "reviewed_positive_window_expansion_manifest.json",
        "reviewed_label_overlay.json",
        "review_frame_manifest.json",
        "refutation_guard_manifest.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_manual_review_expansion_supports_json_only_fallback_without_video(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, with_video=False)

    payload = manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    assert payload["summary"]["successfulApproach"] == "B_nearby_candidate_context_expansion"
    frame_manifest = json.loads((paths["output_root"] / "review_frame_manifest.json").read_text())
    assert frame_manifest["imageExtractionStatus"] == "json_only_no_video"
    assert frame_manifest["reviewFrameCount"] == 17
    assert frame_manifest["extractedImageCount"] == 0


def test_manual_review_expansion_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    manual_review_expansion.run_promoted_v6_manual_review_expansion(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
