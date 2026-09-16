from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_proposal_generation_fix


def test_proposal_generation_fix_summarizes_reviewed_anchor_coverage(tmp_path):
    output_root = tmp_path / "reviewed_positive_proposal_generation_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    output_root.mkdir(parents=True)
    proof_root.mkdir()
    retention_root.mkdir()
    (output_root / "reviewed_positive_anchor_seed.json").write_text(
        json.dumps(
            {
                "reviewedPositiveAnchorRows": [
                    {
                        "reviewItemId": "positive-240",
                        "candidateFrameId": "candidate-240",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "frameIndex": 240,
                        "reviewedBBox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                    },
                    {
                        "reviewItemId": "positive-245",
                        "candidateFrameId": "candidate-245",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "frameIndex": 245,
                        "reviewedBBox": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (proof_root / "recovery_profile_matrix.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "name": "proposal_windows_075",
                        "reviewedPositiveAnchorSeedFrames": 2,
                        "reviewedPositiveAnchorUsedFrames": 2,
                        "reviewedPositiveAnchorWindowFrames": 2,
                        "proposalRawDetectedFrames": 1,
                        "proposalCollapsedFrames": 1,
                        "selectedFrames": 0,
                        "proposalFrameDiagnostics": [
                            {
                                "frameIndex": 245,
                                "proposalGenerated": True,
                                "rawDetected": True,
                                "collapsed": True,
                                "selected": False,
                                "accepted": False,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (proof_root / "proof_summary.json").write_text(
        json.dumps(
            {
                "acceptedBallFrames": 7,
                "bestProposalRawDetectedFrames": 1,
                "bestProposalAfterSeedCollapseFrames": 1,
                "bestProposalSelectedFrames": 0,
            }
        ),
        encoding="utf-8",
    )
    (retention_root / "retention_delta_summary.json").write_text(
        json.dumps(
            {
                "acceptedRetentionRatio": 0.069,
                "controlledRetentionRatio": 0.102,
                "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
            }
        ),
        encoding="utf-8",
    )

    payload = (
        run_promoted_v6_reviewed_positive_proposal_generation_fix
        .run_promoted_v6_reviewed_positive_proposal_generation_fix(
            output_root=output_root,
            proof_root=proof_root,
            retention_delta_root=retention_root,
        )
    )

    summary = payload["reviewedPositiveProposalFixSummary"]
    coverage = payload["reviewedPositiveProposalCoverage"]
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveProposalEvidenceFrameCount"] == 1
    assert summary["dominantBlockerClass"] == "reviewed_positive_anchor_window_zero_detect"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_crop_reinference_audit"
    assert coverage["bucketCounts"] == {
        "reviewed_positive_anchor_window_zero_detect": 1,
        "reviewed_positive_collapsed_not_selected": 1,
    }
    by_frame = {row["frameIndex"]: row for row in coverage["reviewedPositiveFrames"]}
    assert by_frame[240]["windowGenerated"] is True
    assert by_frame[240]["windowSkipped"] is False
    assert by_frame[240]["zeroDetect"] is True
    assert by_frame[240]["candidateGenerated"] is False
    assert by_frame[240]["rejectionReason"] == "reviewed_positive_anchor_window_zero_detect"
    assert by_frame[245]["rawDetected"] is True
    assert by_frame[245]["candidateGenerated"] is True
    assert by_frame[245]["collapsed"] is True
    assert by_frame[245]["selected"] is False
    assert by_frame[245]["accepted"] is False
    assert by_frame[245]["rejectionReason"] == "reviewed_positive_collapsed_not_selected"
    assert (output_root / "reviewed_positive_proposal_coverage.json").exists()
