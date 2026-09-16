from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_crop_geometry_scale_fix


def test_crop_geometry_scale_fix_summarizes_audit_to_proof_lift(tmp_path: Path):
    output_root = tmp_path / "reviewed_positive_crop_geometry_scale_fix_v1"
    audit_root = tmp_path / "reviewed_positive_crop_reinference_audit_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    audit_root.mkdir(parents=True)
    proof_root.mkdir()
    retention_root.mkdir()
    (audit_root / "reviewed_positive_crop_reinference_matrix.json").write_text(
        json.dumps(
            {
                "reviewedPositiveCropRows": [
                    {
                        "frameIndex": 240,
                        "reviewItemId": "positive-240",
                        "candidateFrameId": "candidate-240",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                        "diagnosticClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                        "reinferenceDetected": True,
                    },
                    {
                        "frameIndex": 245,
                        "reviewItemId": "positive-245",
                        "candidateFrameId": "candidate-245",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                        "diagnosticClass": "reviewed_positive_model_zero_detect_all_scales",
                        "reinferenceDetected": False,
                    },
                    {
                        "frameIndex": 265,
                        "reviewItemId": "positive-265",
                        "candidateFrameId": "candidate-265",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "reviewedBBox": {"x1": 9, "y1": 10, "x2": 11, "y2": 12},
                        "diagnosticClass": "reviewed_positive_existing_proposal_followthrough_gap",
                        "reinferenceDetected": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (audit_root / "reviewed_positive_crop_reinference_summary.json").write_text(
        json.dumps(
            {
                "reviewedPositiveFrameCount": 3,
                "zeroDetectFrameCount": 2,
                "reinferenceDetectedFrameCount": 1,
                "dominantBlockerClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                "nextCorrectiveFamily": "reviewed_positive_crop_geometry_scale_fix",
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
                        "reviewedPositiveAnchorSeedFrames": 3,
                        "reviewedPositiveAnchorUsedFrames": 3,
                        "reviewedPositiveAnchorWindowFrames": 9,
                        "reviewedPositiveAuditContextWindowFrames": 9,
                        "proposalRawDetectedFrames": 2,
                        "proposalCollapsedFrames": 1,
                        "selectedFrames": 0,
                        "proposalFrameDiagnostics": [
                            {
                                "frameIndex": 240,
                                "proposalGenerated": True,
                                "rawDetected": True,
                                "collapsed": True,
                                "selected": False,
                                "accepted": False,
                                "proposalWindowKinds": ["reviewed_positive_audit_context_4"],
                            },
                            {
                                "frameIndex": 245,
                                "proposalGenerated": True,
                                "rawDetected": True,
                                "collapsed": False,
                                "selected": False,
                                "accepted": False,
                                "proposalWindowKinds": ["reviewed_positive_audit_context_8"],
                            },
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
                "bestProposalRawDetectedFrames": 2,
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
        run_promoted_v6_reviewed_positive_crop_geometry_scale_fix
        .run_promoted_v6_reviewed_positive_crop_geometry_scale_fix(
            output_root=output_root,
            audit_root=audit_root,
            proof_root=proof_root,
            retention_delta_root=retention_root,
        )
    )

    summary = payload["reviewedPositiveCropGeometryScaleFixSummary"]
    coverage = payload["reviewedPositiveCropGeometryScaleCoverage"]
    assert summary["goalAchieved"] is True
    assert summary["auditRescuableFrameCount"] == 1
    assert summary["auditRescuableProofEvidenceFrameCount"] == 1
    assert summary["reviewedPositiveProposalEvidenceFrameCount"] == 2
    assert summary["reviewedPositiveCollapsedFrameCount"] == 1
    assert summary["dominantBlockerClass"] == "reviewed_positive_raw_detected_not_collapsed"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_selection_followthrough_fix"
    assert coverage["bucketCounts"] == {
        "reviewed_positive_collapsed_not_selected": 1,
        "reviewed_positive_no_raw_detect": 1,
        "reviewed_positive_raw_detected_not_collapsed": 1,
    }
    assert (output_root / "reviewed_positive_crop_geometry_scale_fix_summary.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()
