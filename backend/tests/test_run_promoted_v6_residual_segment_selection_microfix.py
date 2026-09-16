from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_residual_segment_selection_microfix


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_residual_segment_selection_microfix_classifies_segment_length_gate(tmp_path: Path) -> None:
    output_root = tmp_path / "residual_segment_selection_microfix_v1"
    residual_root = tmp_path / "reviewed_positive_residual_proposal_generation_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"

    _write_json(
        residual_root / "residual_reviewed_positive_frame_matrix.json",
        {
            "reviewedPositiveFrames": [
                {
                    "frameIndex": frame_id,
                    "isResidual": True,
                    "gapClass": "residual_collapsed_not_selected",
                    "reviewedBBox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
                for frame_id in [305, 310, 315, 320]
            ]
        },
    )
    _write_json(
        residual_root / "residual_proposal_generation_summary.json",
        {
            "reviewedPositiveAcceptedFrameCount": 10,
            "residualReviewedPositiveFrameCount": 7,
            "dominantBlockerClass": "residual_collapsed_not_selected",
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": frame_id,
                            "proposalGenerated": True,
                            "rawDetected": True,
                            "collapsed": True,
                            "selected": False,
                            "accepted": False,
                            "selectionGateTrace": {
                                "segmentLengthRejected": True,
                                "segmentFrameCount": 4,
                                "continuityRejected": False,
                                "repeatedAnchorRejected": False,
                                "edgeShareRejected": False,
                                "reviewedPositiveLineageMatch": True,
                                "syntheticRowRejected": False,
                            },
                        }
                        for frame_id in [305, 310, 315, 320]
                    ],
                }
            ]
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.099,
            "controlledRetentionRatio": 0.133,
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
        },
    )
    _write_json(suite_root / "suite_summary.json", {"sourceRobustnessPromotionBlockers": ["failing_source_not_viable"]})

    payload = (
        run_promoted_v6_residual_segment_selection_microfix
        .run_promoted_v6_residual_segment_selection_microfix(
            output_root=output_root,
            residual_root=residual_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
            suite_root=suite_root,
        )
    )

    summary = payload["summary"]
    assert summary["collapsedNotSelectedFrameIds"] == [305, 310, 315, 320]
    assert summary["dominantBlockerClass"] == "residual_segment_length_rejected"
    assert summary["nextCorrectiveFamily"] == "residual_selected_segment_microprofile"
    assert summary["reviewedPositiveAcceptedFrameCount"] == 10
    assert (output_root / "residual_frame_gate_trace.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_residual_segment_selection_microfix_selects_runtime_default_validation_when_gate_clears(tmp_path: Path) -> None:
    output_root = tmp_path / "residual_segment_selection_microfix_v1"
    residual_root = tmp_path / "reviewed_positive_residual_proposal_generation_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"

    _write_json(
        residual_root / "residual_reviewed_positive_frame_matrix.json",
        {
            "reviewedPositiveFrames": [
                {"frameIndex": frame_id, "isResidual": True, "gapClass": "residual_collapsed_not_selected"}
                for frame_id in [305, 310, 315, 320]
            ]
        },
    )
    _write_json(residual_root / "residual_proposal_generation_summary.json", {"reviewedPositiveAcceptedFrameCount": 10})
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": frame_id,
                            "collapsed": True,
                            "selected": True,
                            "accepted": True,
                            "selectionGateTrace": {"segmentLengthRejected": False, "segmentFrameCount": 4},
                            "acceptanceGateTrace": {"acceptedByReviewedPositiveProfile": True},
                        }
                        for frame_id in [305, 310, 315, 320]
                    ],
                }
            ]
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.108,
            "controlledRetentionRatio": 0.14,
            "primaryRetentionBlockerClass": "cleared",
        },
    )
    _write_json(suite_root / "suite_summary.json", {"passedPromotionGate": True, "sourceRobustnessPromotionBlockers": []})

    payload = (
        run_promoted_v6_residual_segment_selection_microfix
        .run_promoted_v6_residual_segment_selection_microfix(
            output_root=output_root,
            residual_root=residual_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
            suite_root=suite_root,
            attempt_number=2,
            attempt_approach_family="residual_selected_segment_microprofile",
        )
    )

    summary = payload["summary"]
    assert summary["residualSelectedFrameCount"] == 4
    assert summary["residualAcceptedFrameCount"] == 4
    assert summary["nextCorrectiveFamily"] == "validate_promoted_touchline_runtime_default"


def test_residual_segment_selection_microfix_selects_guardrail_audit_when_lift_does_not_clear_gate(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "residual_segment_selection_microfix_v1"
    residual_root = tmp_path / "reviewed_positive_residual_proposal_generation_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"

    _write_json(
        residual_root / "residual_reviewed_positive_frame_matrix.json",
        {
            "reviewedPositiveFrames": [
                {"frameIndex": frame_id, "isResidual": True, "gapClass": "residual_collapsed_not_selected"}
                for frame_id in [305, 310, 315, 320]
            ]
        },
    )
    _write_json(residual_root / "residual_proposal_generation_summary.json", {"reviewedPositiveAcceptedFrameCount": 10})
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": frame_id,
                            "collapsed": True,
                            "selected": True,
                            "accepted": True,
                            "selectionGateTrace": {"segmentLengthRejected": False, "segmentFrameCount": 4},
                        }
                        for frame_id in [305, 310, 315, 320]
                    ],
                }
            ]
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.099,
            "controlledRetentionRatio": 0.133,
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
        },
    )
    _write_json(
        suite_root / "suite_summary.json",
        {
            "passedPromotionGate": False,
            "sourceRobustnessPromotionBlockers": [
                "accepted_retention_below_guardrail",
                "controlled_retention_below_guardrail",
            ],
        },
    )

    payload = (
        run_promoted_v6_residual_segment_selection_microfix
        .run_promoted_v6_residual_segment_selection_microfix(
            output_root=output_root,
            residual_root=residual_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
            suite_root=suite_root,
            attempt_number=2,
            attempt_approach_family="residual_selected_segment_microprofile",
        )
    )

    summary = payload["summary"]
    assert summary["residualAcceptedFrameCount"] == 4
    assert summary["nextCorrectiveFamily"] == "accepted_retention_guardrail_audit"
