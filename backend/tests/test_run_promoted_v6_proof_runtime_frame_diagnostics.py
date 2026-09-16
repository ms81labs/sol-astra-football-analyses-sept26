from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_proof_runtime_frame_diagnostics as runtime_diag


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "expanded-window",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_id,
        "reviewDecision": "adjust_bbox",
        "reviewedBBox": {"x1": 1, "y1": 2, "x2": 5, "y2": 7},
    }


def _write_inputs(root: Path, *, proof_matrix: dict[str, object]) -> dict[str, Path]:
    output_root = root / "proof_runtime_frame_diagnostics_v1"
    expansion_resolution_root = root / "manual_review_expansion_resolution_v1"
    proof_root = root / "fresh-proof"
    micro_validation_root = root / "reviewed_positive_micro_validation_v1"
    retention_root = root / "retention"
    suite_root = root / "suite"
    _write_json(
        expansion_resolution_root / "expanded_reviewed_truth_seed.json",
        {
            "truthStatus": "review_resolved",
            "reviewedPositiveSeedRows": [_positive_row(frame_id) for frame_id in range(240, 321, 5)],
        },
    )
    _write_json(
        micro_validation_root / "reviewed_positive_micro_validation_summary.json",
        {
            "dominantBlockerClass": "reviewed_positive_artifact_coverage_gap",
            "nextCorrectiveFamily": "proof_diagnostic_instrumentation_refresh",
        },
    )
    _write_json(proof_root / "recovery_profile_matrix.json", proof_matrix)
    _write_json(proof_root / "proof_summary.json", {})
    _write_json(proof_root / "ball_truth_layers.json", {"acceptedBall": {"rows": []}})
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
        {"sourceRobustnessOutcome": "source_robustness_partial"},
    )
    return {
        "output_root": output_root,
        "expansion_resolution_root": expansion_resolution_root,
        "proof_root": proof_root,
        "micro_validation_root": micro_validation_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
    }


def test_runtime_frame_diagnostics_selects_proposal_generation_when_reviewed_frames_have_no_evidence(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_matrix={
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalRawDetectedFrameIds": [415],
                    "proposalCollapsedFrameIds": [415],
                    "proposalSelectedFrameIds": [415],
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": 415,
                            "proposalGenerated": True,
                            "rawDetected": True,
                            "collapsed": True,
                            "selected": True,
                            "accepted": False,
                        }
                    ],
                }
            ]
        },
    )

    payload = runtime_diag.run_promoted_v6_proof_runtime_frame_diagnostics(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["classifiedReviewedFrameCount"] == 17
    assert summary["dominantBlockerClass"] == "reviewed_positive_no_promoted_proposal"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_proposal_generation_fix"


def test_runtime_frame_diagnostics_keeps_blocker_when_runtime_diagnostics_are_absent(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, proof_matrix={"profiles": [{"name": "proposal_windows_075"}]})

    payload = runtime_diag.run_promoted_v6_proof_runtime_frame_diagnostics(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is False
    assert summary["dominantBlockerClass"] == "proof_runtime_frame_diagnostics_incomplete"
    assert summary["nextCorrectiveFamily"] == "proof_diagnostic_instrumentation_refresh"


def test_runtime_frame_diagnostics_writes_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_matrix={
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalRawDetectedFrameIds": [240],
                    "proposalFrameDiagnostics": [{"frameIndex": 240, "proposalGenerated": True}],
                }
            ]
        },
    )

    runtime_diag.run_promoted_v6_proof_runtime_frame_diagnostics(**paths)

    for filename in (
        "proof_runtime_frame_diagnostics_summary.json",
        "reviewed_positive_runtime_frame_diagnostics.json",
        "proof_runtime_artifact_audit.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()
