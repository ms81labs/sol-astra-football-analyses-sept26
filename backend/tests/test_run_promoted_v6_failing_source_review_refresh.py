from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_failing_source_review_refresh as review_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ball_row(frame_id: int, *, x: float = 40.0, y: float = 40.0) -> dict[str, object]:
    return {
        "Frame_ID": frame_id,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": x,
        "Y": y,
        "Conf": 0.8,
    }


def test_missing_accepted_frames_and_contiguous_windows_are_deterministic() -> None:
    baseline_truth = {
        "acceptedBall": {"rows": [_ball_row(0), _ball_row(5), _ball_row(10), _ball_row(25)]}
    }
    promoted_truth = {
        "acceptedBall": {"rows": [_ball_row(10)]}
    }

    missing_frames = review_refresh._missing_accepted_frames(
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
    )
    windows = review_refresh._group_contiguous_frames(missing_frames, sample_interval=5)

    assert missing_frames == [0, 5, 25]
    assert windows == [
        {"startFrame": 0, "endFrame": 5, "frameIds": [0, 5], "frameCount": 2},
        {"startFrame": 25, "endFrame": 25, "frameIds": [25], "frameCount": 1},
    ]


def test_review_taxonomy_assigns_expected_buckets_from_synthetic_evidence() -> None:
    baseline_truth = {
        "sampleInterval": 5,
        "acceptedBall": {
            "rows": [
                _ball_row(0, x=2.0),
                _ball_row(5, x=3.0),
                _ball_row(20, x=45.0),
                _ball_row(25, x=46.0),
                _ball_row(50, x=48.0),
            ]
        },
    }
    promoted_truth = {
        "sampleInterval": 5,
        "acceptedBall": {"rows": [_ball_row(60)]},
        "observedBall": {"rows": [_ball_row(20)]},
        "probeObservedBall": {"rows": []},
        "sourceConditionedAcquisitionDiagnostics": {
            "edgeStuckCandidateRejectionCounts": {"candidate_viability_regressed": 2},
            "zeroTouchlineCandidateReasonCounts": {},
        },
    }
    promoted_selected_cluster_delta = {
        "before": {"acceptedBallFrames": 5, "controlledPossessionFrames": 0},
        "after": {"acceptedBallFrames": 5, "controlledPossessionFrames": 1},
    }
    baseline_selected_cluster_delta = {
        "after": {"acceptedBallFrames": 100, "controlledPossessionFrames": 80},
    }
    recovery_profile_matrix = {
        "profiles": [
            {
                "name": "proposal_windows_075",
                "proposalCandidateFrames": 4,
                "selectedFrames": 0,
                "proposalDirectSeedRawHitFilteredOutFrames": 2,
            }
        ]
    }

    taxonomy = review_refresh.build_missing_accepted_signal_taxonomy(
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
        baseline_selected_cluster_delta=baseline_selected_cluster_delta,
        promoted_selected_cluster_delta=promoted_selected_cluster_delta,
        promoted_proof_summary={},
        recovery_profile_matrix=recovery_profile_matrix,
        retention_delta_summary={"acceptedRetentionRatio": 0.05},
    )

    by_start = {window["startFrame"]: window for window in taxonomy["windows"]}
    assert by_start[0]["taxonomyBucket"] == "edge_cleanup_removed_baseline_edge_signal"
    assert by_start[20]["taxonomyBucket"] == "proposal_signal_present_but_not_selected"
    assert by_start[50]["taxonomyBucket"] == "support_or_viability_filter_loss"
    assert taxonomy["dominantBlockerClass"] == "edge_cleanup_removed_baseline_edge_signal"
    assert taxonomy["nextFixFamily"] == "edge_cleanup_truth_refresh"


def test_run_review_refresh_writes_all_expected_artifacts(tmp_path: Path) -> None:
    baseline_root = tmp_path / "pod_cycles" / "baseline"
    promoted_root = tmp_path / "pod_cycles" / "promoted"
    analysis_root = tmp_path / "benchmark_suites" / "suite" / "review_refresh"
    retention_root = tmp_path / "benchmark_suites" / "suite" / "retention"

    _write_json(
        baseline_root / "ball_truth_layers.json",
        {
            "sampleInterval": 5,
            "acceptedBall": {"rows": [_ball_row(0, x=2.0), _ball_row(5, x=3.0)]},
        },
    )
    _write_json(
        promoted_root / "ball_truth_layers.json",
        {
            "sampleInterval": 5,
            "acceptedBall": {"rows": []},
            "observedBall": {"rows": []},
            "probeObservedBall": {"rows": []},
        },
    )
    _write_json(baseline_root / "selected_cluster_delta.json", {"after": {"acceptedBallFrames": 2}})
    _write_json(
        promoted_root / "selected_cluster_delta.json",
        {"before": {"acceptedBallFrames": 0}, "after": {"acceptedBallFrames": 0}},
    )
    _write_json(promoted_root / "proof_summary.json", {"acceptedBallFrames": 0})
    _write_json(promoted_root / "recovery_profile_matrix.json", {"profiles": []})
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
            "acceptedRetentionRatio": 0.069,
            "controlledRetentionRatio": 0.102,
        },
    )

    payload = review_refresh.run_promoted_v6_failing_source_review_refresh(
        analysis_root=analysis_root,
        baseline_proof_root=baseline_root,
        promoted_proof_root=promoted_root,
        retention_delta_root=retention_root,
    )

    assert payload["goalAchieved"] is True
    assert payload["dominantBlockerClass"] == "edge_cleanup_removed_baseline_edge_signal"
    for filename in (
        "review_refresh_summary.json",
        "missing_accepted_signal_taxonomy.json",
        "frame_window_taxonomy.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (analysis_root / filename).exists()
