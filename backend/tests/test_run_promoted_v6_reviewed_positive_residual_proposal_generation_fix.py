from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_residual_proposal_generation_fix


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _positive_seed(frame_id: int) -> dict:
    return {
        "frameIndex": frame_id,
        "sourceClipId": "trimed-5min.mp4",
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "review-window",
        "reviewedBBox": {"x1": frame_id, "y1": 2, "x2": frame_id + 10, "y2": 12},
    }


def test_residual_proposal_generation_fix_classifies_residual_frames_and_selects_profile(tmp_path: Path) -> None:
    seed_root = tmp_path / "manual_review_expansion_resolution_v1"
    acceptance_root = tmp_path / "reviewed_positive_acceptance_fix_v1"
    crop_root = tmp_path / "reviewed_positive_crop_geometry_scale_fix_v1"
    audit_root = tmp_path / "reviewed_positive_crop_reinference_audit_v1"
    diagnostics_root = tmp_path / "proof_runtime_frame_diagnostics_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"
    output_root = tmp_path / "reviewed_positive_residual_proposal_generation_fix_v1"

    frames = [240, 245, 250, 255, 260, 265, 270]
    _write_json(
        seed_root / "expanded_reviewed_truth_seed.json",
        {
            "reviewedPositiveSeedCount": len(frames),
            "reviewedPositiveSeedRows": [_positive_seed(frame_id) for frame_id in frames],
            "reviewedNegativeSeedCount": 74,
            "reviewedNegativeSeedRows": [{"frameIndex": 1000}],
        },
    )
    _write_json(
        acceptance_root / "reviewed_positive_acceptance_matrix.json",
        {
            "reviewedPositiveAcceptedFrameCount": 5,
            "selectedReviewedPositiveFrames": [
                {"frameIndex": frame_id, "accepted": True}
                for frame_id in [250, 255, 260, 265, 270]
            ],
        },
    )
    _write_json(
        crop_root / "reviewed_positive_crop_geometry_scale_coverage.json",
        {
            "reviewedPositiveFrames": [
                {
                    "frameIndex": 240,
                    "rawDetected": False,
                    "candidateGenerated": False,
                    "collapsed": False,
                    "selected": False,
                    "accepted": False,
                    "diagnosticClass": "reviewed_positive_no_raw_detect",
                    "auditDiagnosticClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                    "auditReinferenceDetected": True,
                },
                {
                    "frameIndex": 245,
                    "rawDetected": False,
                    "candidateGenerated": False,
                    "collapsed": False,
                    "selected": False,
                    "accepted": False,
                    "diagnosticClass": "reviewed_positive_no_raw_detect",
                    "auditDiagnosticClass": "reviewed_positive_model_zero_detect_all_scales",
                    "auditReinferenceDetected": False,
                },
            ],
        },
    )
    _write_json(
        audit_root / "reviewed_positive_crop_reinference_matrix.json",
        {
            "reviewedPositiveCropRows": [
                {
                    "frameIndex": 240,
                    "diagnosticClass": "reviewed_positive_crop_geometry_scale_rescue_available",
                    "reinferenceDetected": True,
                    "bestAttempt": {"contextRatio": 1.0, "imgsz": 1600, "cropWindow": [1, 2, 3, 4]},
                },
                {
                    "frameIndex": 245,
                    "diagnosticClass": "reviewed_positive_model_zero_detect_all_scales",
                    "reinferenceDetected": False,
                    "bestAttempt": {},
                },
            ]
        },
    )
    _write_json(
        diagnostics_root / "reviewed_positive_runtime_frame_diagnostics.json",
        {
            "reviewedPositiveFrameDiagnostics": [
                {"frameIndex": 240, "diagnosticClass": "reviewed_positive_no_promoted_proposal"},
                {"frameIndex": 245, "diagnosticClass": "reviewed_positive_no_promoted_proposal"},
            ]
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {"profiles": [{"name": "proposal_windows_075", "proposalFrameDiagnostics": []}]},
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
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )

    payload = (
        run_promoted_v6_reviewed_positive_residual_proposal_generation_fix
        .run_promoted_v6_reviewed_positive_residual_proposal_generation_fix(
            output_root=output_root,
            reviewed_truth_root=seed_root,
            acceptance_root=acceptance_root,
            crop_geometry_root=crop_root,
            crop_audit_root=audit_root,
            frame_diagnostics_root=diagnostics_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
            suite_root=suite_root,
        )
    )

    summary = payload["summary"]
    assert summary["reviewedPositiveFrameCount"] == 7
    assert summary["reviewedPositiveAcceptedFrameCount"] == 5
    assert summary["residualReviewedPositiveFrameCount"] == 2
    assert summary["dominantBlockerClass"] == "residual_window_generated_zero_raw_detect"
    assert summary["nextCorrectiveFamily"] == "residual_audit_best_crop_profile"
    assert summary["rejectedBootstrapSeedPositiveEvidenceCount"] == 0

    matrix = json.loads((output_root / "residual_reviewed_positive_frame_matrix.json").read_text())
    residual_rows = [row for row in matrix["reviewedPositiveFrames"] if row["isResidual"]]
    assert [row["frameIndex"] for row in residual_rows] == [240, 245]
    assert residual_rows[0]["auditRescueAvailable"] is True
    assert residual_rows[0]["bestAuditAttempt"] == {
        "contextRatio": 1.0,
        "cropWindow": [1, 2, 3, 4],
        "imgsz": 1600,
    }
    assert residual_rows[1]["auditModelZeroDetect"] is True
    assert (output_root / "residual_profile_candidate_plan.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_residual_proposal_generation_fix_keeps_rejected_seeds_negative_only(tmp_path: Path) -> None:
    seed_root = tmp_path / "manual_review_expansion_resolution_v1"
    acceptance_root = tmp_path / "reviewed_positive_acceptance_fix_v1"
    crop_root = tmp_path / "reviewed_positive_crop_geometry_scale_fix_v1"
    audit_root = tmp_path / "reviewed_positive_crop_reinference_audit_v1"
    diagnostics_root = tmp_path / "proof_runtime_frame_diagnostics_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"
    output_root = tmp_path / "reviewed_positive_residual_proposal_generation_fix_v1"

    _write_json(
        seed_root / "expanded_reviewed_truth_seed.json",
        {
            "reviewedPositiveSeedCount": 1,
            "reviewedPositiveSeedRows": [_positive_seed(240)],
            "reviewedNegativeSeedCount": 2,
            "reviewedNegativeSeedRows": [
                {"frameIndex": 240, "reviewDecision": "reject_seed"},
                {"frameIndex": 245, "reviewDecision": "reject_seed"},
            ],
        },
    )
    _write_json(acceptance_root / "reviewed_positive_acceptance_matrix.json", {})
    _write_json(crop_root / "reviewed_positive_crop_geometry_scale_coverage.json", {"reviewedPositiveFrames": []})
    _write_json(audit_root / "reviewed_positive_crop_reinference_matrix.json", {"reviewedPositiveCropRows": []})
    _write_json(diagnostics_root / "reviewed_positive_runtime_frame_diagnostics.json", {"reviewedPositiveFrameDiagnostics": []})
    _write_json(proof_root / "recovery_profile_matrix.json", {"profiles": []})
    _write_json(retention_root / "retention_delta_summary.json", {})
    _write_json(suite_root / "suite_summary.json", {})

    payload = (
        run_promoted_v6_reviewed_positive_residual_proposal_generation_fix
        .run_promoted_v6_reviewed_positive_residual_proposal_generation_fix(
            output_root=output_root,
            reviewed_truth_root=seed_root,
            acceptance_root=acceptance_root,
            crop_geometry_root=crop_root,
            crop_audit_root=audit_root,
            frame_diagnostics_root=diagnostics_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
            suite_root=suite_root,
        )
    )

    summary = payload["summary"]
    assert summary["reviewedPositiveFrameCount"] == 1
    assert summary["rejectedBootstrapSeedCount"] == 2
    assert summary["rejectedBootstrapSeedPositiveEvidenceCount"] == 0
