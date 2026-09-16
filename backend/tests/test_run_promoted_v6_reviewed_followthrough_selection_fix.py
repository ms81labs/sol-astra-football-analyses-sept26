from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_reviewed_followthrough_selection_fix as reviewed_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"positive-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": f"window-{frame_id // 100}",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "accept_seed",
        "seedBBox": {"x1": 10.0, "y1": 20.0, "x2": 25.0, "y2": 35.0},
        "reviewedBBox": {"x1": 10.0, "y1": 20.0, "x2": 25.0, "y2": 35.0},
        "lineage": {"baseline": "baseline/ball_truth_layers.json", "promoted": "promoted/ball_truth_layers.json"},
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
    positive_frames: list[int],
    negative_frames: list[int],
    funnel_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    output_root = root / "reviewed_followthrough_selection_fix_v1"
    manual_resolution_root = root / "manual_resolution"
    manual_review_root = root / "manual_review"
    followthrough_root = root / "proposal_selection_followthrough_fix_v1"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "frozen_source_manifest.json"

    positives = [_positive_row(frame_id) for frame_id in positive_frames]
    negatives = [_negative_row(frame_id) for frame_id in negative_frames]
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
    overlay_items = [
        {
            "reviewItemId": row["reviewItemId"],
            "candidateFrameId": row["candidateFrameId"],
            "frameIndex": row["frameIndex"],
            "decision": "accept_seed",
            "reviewedBBox": row["reviewedBBox"],
            "seedBBox": row["seedBBox"],
            "aiReviewPass": {"reviewer": "codex_ai_visual_review"},
        }
        for row in positives
    ] + [
        {
            "reviewItemId": row["reviewItemId"],
            "candidateFrameId": row["candidateFrameId"],
            "frameIndex": row["frameIndex"],
            "decision": "reject_seed",
            "reviewedBBox": None,
            "seedBBox": {"x1": 1.0, "y1": 2.0, "x2": 4.0, "y2": 5.0},
            "aiReviewPass": {"reviewer": "codex_ai_visual_review"},
        }
        for row in negatives
    ]
    _write_json(
        manual_review_root / "reviewed_label_overlay.json",
        {
            "reviewItemCount": len(overlay_items),
            "pendingReviewCount": 0,
            "reviewedPositiveCount": len(positives),
            "reviewedNegativeCount": len(negatives),
            "reviewItems": overlay_items,
            "aiReviewSummary": {"reviewer": "codex_ai_visual_review"},
        },
    )
    funnel = {
        "proposalCandidateFrames": 110,
        "proposalRawDetectedFrames": 93,
        "proposalCollapsedFrames": 93,
        "proposalSelectedFrames": 0,
        "proposalSelectedSegmentCount": 0,
        "supportViabilityAcceptedFrames": 0,
        "selectedClusterTruthGateSparse": True,
    }
    funnel.update(funnel_overrides or {})
    _write_json(followthrough_root / "profile_selection_funnel_audit.json", funnel)
    _write_json(
        followthrough_root / "proposal_selection_followthrough_summary.json",
        {
            "batchStatus": "exhausted",
            "dominantBlockerClass": "candidate_rows_collapsed_but_segment_selection_zero",
            "proposalDiagnostics": {
                "proposalCandidateFrames": funnel.get("proposalCandidateFrames"),
                "proposalRawDetectedFrames": funnel.get("proposalRawDetectedFrames"),
                "proposalCollapsedFrames": funnel.get("proposalCollapsedFrames"),
                "selectedFrames": funnel.get("proposalSelectedFrames"),
            },
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
        "manual_resolution_root": manual_resolution_root,
        "manual_review_root": manual_review_root,
        "followthrough_root": followthrough_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_reviewed_followthrough_fix_selects_refuted_refresh_for_sparse_positive_truth(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, positive_frames=[260, 290, 295, 300], negative_frames=list(range(1000, 1074)))

    payload = reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["dominantBlockerClass"] == "reviewed_positive_evidence_too_sparse"
    assert summary["nextCorrectiveFamily"] == "gold_truth_seed_refuted_refresh"
    assert summary["reviewedPositiveSeedCount"] == 4
    assert summary["reviewedNegativeSeedCount"] == 74
    matrix = json.loads((paths["output_root"] / "reviewed_positive_followthrough_matrix.json").read_text())
    assert matrix["bucketCounts"] == {"reviewed_positive_evidence_too_sparse": 4}
    refutation = json.loads((paths["output_root"] / "reviewed_seed_refutation_matrix.json").read_text())
    assert refutation["rejectedSeedCount"] == 74
    assert refutation["rejectedSeedsReusedAsPositiveEvidence"] is False


def test_reviewed_followthrough_fix_names_profile_when_enough_positives_are_collapsed_but_unselected(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, positive_frames=list(range(200, 208)), negative_frames=list(range(1000, 1010)))

    payload = reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "reviewed_positive_collapsed_not_selected"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_followthrough_profile"
    assert summary["reviewedPositiveSeedCount"] == 8


def test_reviewed_followthrough_fix_classifies_not_generated_when_no_proposal_signal(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        positive_frames=list(range(300, 308)),
        negative_frames=[],
        funnel_overrides={
            "proposalCandidateFrames": 0,
            "proposalRawDetectedFrames": 0,
            "proposalCollapsedFrames": 0,
            "proposalSelectedFrames": 0,
        },
    )

    payload = reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    assert payload["summary"]["dominantBlockerClass"] == "reviewed_positive_candidate_not_generated"
    assert payload["summary"]["nextCorrectiveFamily"] == "source_manifest_refresh"


def test_reviewed_followthrough_fix_classifies_selected_not_accepted(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        positive_frames=list(range(400, 408)),
        negative_frames=[],
        funnel_overrides={"proposalSelectedFrames": 6},
    )

    payload = reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    assert payload["summary"]["dominantBlockerClass"] == "reviewed_positive_selected_not_accepted"
    assert payload["summary"]["nextCorrectiveFamily"] == "reviewed_positive_followthrough_profile"


def test_reviewed_followthrough_fix_writes_all_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, positive_frames=[260, 290, 295, 300], negative_frames=list(range(1000, 1074)))

    reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    for filename in (
        "reviewed_followthrough_selection_summary.json",
        "reviewed_positive_followthrough_matrix.json",
        "reviewed_seed_refutation_matrix.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_reviewed_followthrough_fix_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, positive_frames=[260, 290, 295, 300], negative_frames=list(range(1000, 1074)))
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    reviewed_fix.run_promoted_v6_reviewed_followthrough_selection_fix(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
