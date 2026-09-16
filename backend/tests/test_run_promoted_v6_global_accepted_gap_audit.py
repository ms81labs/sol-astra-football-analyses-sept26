from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_global_accepted_gap_audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _truth_layers(frames: list[int]) -> dict:
    return {
        "acceptedBall": {
            "rows": [
                {
                    "Frame_ID": frame,
                    "Timestamp": frame / 25,
                    "X": float(frame),
                    "Y": 90.0,
                    "Conf": 0.5,
                    "Source_X1": 1,
                    "Source_Y1": 2,
                    "Source_X2": 3,
                    "Source_Y2": 4,
                }
                for frame in frames
            ]
        }
    }


def test_global_accepted_gap_audit_classifies_missing_baseline_frames(tmp_path: Path) -> None:
    output_root = tmp_path / "global_accepted_gap_audit_v1"
    baseline_root = tmp_path / "baseline"
    promoted_root = tmp_path / "promoted"
    guardrail_root = tmp_path / "guardrail"
    retention_root = tmp_path / "retention"
    reviewed_truth_path = tmp_path / "reviewed.json"
    refuted_seed_path = tmp_path / "refuted.json"

    _write_json(baseline_root / "ball_truth_layers.json", _truth_layers([10, 20, 30, 40, 50, 60]))
    _write_json(promoted_root / "ball_truth_layers.json", _truth_layers([60, 70]))
    _write_json(baseline_root / "proof_summary.json", {"acceptedBallFrames": 6})
    _write_json(
        promoted_root / "proof_summary.json",
        {
            "acceptedBallFrames": 2,
            "bestProposalRawDetectedFrames": 3,
            "bestProposalAfterSeedCollapseFrames": 2,
            "bestProposalSelectedFrames": 1,
        },
    )
    _write_json(
        promoted_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "proposal_windows_075",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalRawDetectedFrameIds": [20, 30, 40],
                    "proposalCollapsedFrameIds": [30, 40],
                    "proposalSelectedFrameIds": [40],
                    "proposalFrameDiagnostics": [
                        {"frameIndex": 10, "proposalGenerated": True, "rawDetected": False},
                        {"frameIndex": 20, "proposalGenerated": True, "rawDetected": True, "collapsed": False},
                        {"frameIndex": 30, "proposalGenerated": True, "rawDetected": True, "collapsed": True},
                        {
                            "frameIndex": 40,
                            "proposalGenerated": True,
                            "rawDetected": True,
                            "collapsed": True,
                            "selected": True,
                            "accepted": False,
                        },
                    ],
                }
            ],
        },
    )
    _write_json(
        guardrail_root / "accepted_retention_guardrail_summary.json",
        {"bestRetentionArmName": "promoted_v6_baseline", "acceptedFramesShortOfGuardrail": 4},
    )
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.1})
    _write_json(
        reviewed_truth_path,
        {"reviewedPositiveSeedRows": [{"frameIndex": 30}, {"frameIndex": 40}]},
    )
    _write_json(refuted_seed_path, {"rejectedSeeds": [{"frameIndex": 20}]})

    payload = run_promoted_v6_global_accepted_gap_audit.run_promoted_v6_global_accepted_gap_audit(
        output_root=output_root,
        baseline_proof_root=baseline_root,
        promoted_proof_root=promoted_root,
        guardrail_root=guardrail_root,
        retention_delta_root=retention_root,
        reviewed_truth_path=reviewed_truth_path,
        refuted_seed_path=refuted_seed_path,
    )

    summary = payload["summary"]
    assert summary["baselineAcceptedFrameCount"] == 6
    assert summary["promotedAcceptedFrameCount"] == 2
    assert summary["overlappingAcceptedFrameCount"] == 1
    assert summary["missingBaselineAcceptedFrameCount"] == 5
    assert summary["gapClassCounts"] == {
        "baseline_accepted_collapsed_not_selected": 1,
        "baseline_accepted_no_promoted_proposal": 1,
        "baseline_accepted_raw_detected_not_collapsed": 1,
        "baseline_accepted_selected_not_accepted": 1,
        "baseline_accepted_window_generated_zero_raw_detect": 1,
    }
    assert summary["reachableFrameIds"] == [30, 40]
    assert (output_root / "accepted_gap_frame_manifest.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_global_accepted_gap_audit_selects_denominator_review_when_refuted_frames_dominate(tmp_path: Path) -> None:
    output_root = tmp_path / "global_accepted_gap_audit_v1"
    baseline_root = tmp_path / "baseline"
    promoted_root = tmp_path / "promoted"
    guardrail_root = tmp_path / "guardrail"
    retention_root = tmp_path / "retention"
    reviewed_truth_path = tmp_path / "reviewed.json"
    refuted_seed_path = tmp_path / "refuted.json"

    _write_json(baseline_root / "ball_truth_layers.json", _truth_layers([1, 2, 3, 4]))
    _write_json(promoted_root / "ball_truth_layers.json", _truth_layers([]))
    _write_json(baseline_root / "proof_summary.json", {"acceptedBallFrames": 4})
    _write_json(promoted_root / "proof_summary.json", {"acceptedBallFrames": 0})
    _write_json(
        promoted_root / "recovery_profile_matrix.json",
        {"selectedProfileName": "proposal_windows_075", "profiles": [{"name": "proposal_windows_075"}]},
    )
    _write_json(guardrail_root / "accepted_retention_guardrail_summary.json", {})
    _write_json(retention_root / "retention_delta_summary.json", {})
    _write_json(reviewed_truth_path, {"reviewedPositiveSeedRows": []})
    _write_json(refuted_seed_path, {"rejectedSeeds": [{"frameIndex": 1}, {"frameIndex": 2}, {"frameIndex": 3}]})

    payload = run_promoted_v6_global_accepted_gap_audit.run_promoted_v6_global_accepted_gap_audit(
        output_root=output_root,
        baseline_proof_root=baseline_root,
        promoted_proof_root=promoted_root,
        guardrail_root=guardrail_root,
        retention_delta_root=retention_root,
        reviewed_truth_path=reviewed_truth_path,
        refuted_seed_path=refuted_seed_path,
    )

    summary = payload["summary"]
    assert summary["dominantGapClass"] == "baseline_accepted_no_promoted_proposal"
    assert summary["refutedOnlyMissingFrameCount"] == 3
    assert summary["nextCorrectiveFamily"] == "baseline_denominator_review_refresh"
