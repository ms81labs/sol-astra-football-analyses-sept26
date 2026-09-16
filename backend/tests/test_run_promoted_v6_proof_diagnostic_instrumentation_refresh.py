from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_proof_diagnostic_instrumentation_refresh as proof_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "review-window",
        "frameIndex": frame_id,
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "adjust_bbox",
        "reviewedBBox": {"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 7.0},
        "lineage": {"promotedBallTruthLayersPath": "/proof/ball_truth_layers.json"},
    }


def _write_inputs(
    root: Path,
    *,
    recovery_profile_matrix: dict[str, object] | None = None,
) -> dict[str, Path]:
    output_root = root / "proof_diagnostic_instrumentation_refresh_v1"
    expansion_resolution_root = root / "manual_review_expansion_resolution_v1"
    micro_validation_root = root / "reviewed_positive_micro_validation_v1"
    validation_root = root / "validation"
    proof_root = root / "proof"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "source_manifest.json"

    positives = [_positive_row(frame_id) for frame_id in range(240, 321, 5)]
    _write_json(
        expansion_resolution_root / "expanded_reviewed_truth_seed.json",
        {
            "truthStatus": "review_resolved",
            "reviewedPositiveSeedCount": len(positives),
            "reviewedPositiveSeedRows": positives,
            "reviewedNegativeSeedCount": 0,
            "reviewedNegativeSeedRows": [],
        },
    )
    _write_json(
        micro_validation_root / "reviewed_positive_micro_validation_summary.json",
        {
            "batchStatus": "succeeded",
            "dominantBlockerClass": "reviewed_positive_artifact_coverage_gap",
            "nextCorrectiveFamily": "proof_diagnostic_instrumentation_refresh",
        },
    )
    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                {
                    "armName": "promoted_v6_baseline",
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "proofSummaryPath": str(proof_root / "proof_summary.json"),
                                "selectedClusterDeltaPath": str(proof_root / "selected_cluster_delta.json"),
                            },
                        }
                    ],
                }
            ]
        },
    )
    _write_json(proof_root / "recovery_profile_matrix.json", recovery_profile_matrix or {})
    _write_json(proof_root / "proof_summary.json", {"bestProposalRawDetectedFrames": 93})
    _write_json(proof_root / "selected_cluster_delta.json", {"after": {}})
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
        {
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    _write_json(runtime_default_path, {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    return {
        "output_root": output_root,
        "expansion_resolution_root": expansion_resolution_root,
        "micro_validation_root": micro_validation_root,
        "validation_root": validation_root,
        "proof_root": proof_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_proof_diagnostic_refresh_selects_runtime_diagnostics_when_current_proof_has_no_frame_evidence(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)

    payload = proof_refresh.run_promoted_v6_proof_diagnostic_instrumentation_refresh(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["dominantBlockerClass"] == "reviewed_positive_frame_diagnostics_missing"
    assert summary["nextCorrectiveFamily"] == "proof_runtime_frame_diagnostics"
    assert summary["reviewedPositiveFrameCount"] == 17
    assert summary["coveredReviewedFrameCount"] == 0


def test_proof_diagnostic_refresh_selects_selection_followthrough_when_all_reviewed_frames_are_collapsed(
    tmp_path: Path,
) -> None:
    frames = list(range(240, 321, 5))
    paths = _write_inputs(
        tmp_path,
        recovery_profile_matrix={
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalRawDetectedFrameIds": frames,
                    "proposalCollapsedFrameIds": frames,
                    "proposalSelectedFrameIds": [],
                }
            ]
        },
    )

    payload = proof_refresh.run_promoted_v6_proof_diagnostic_instrumentation_refresh(**paths)

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "reviewed_positive_collapsed_not_selected"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_selection_followthrough_fix"
    assert summary["coveredReviewedFrameCount"] == 17


def test_proof_diagnostic_refresh_writes_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    proof_refresh.run_promoted_v6_proof_diagnostic_instrumentation_refresh(**paths)

    for filename in (
        "proof_diagnostic_instrumentation_summary.json",
        "reviewed_positive_frame_diagnostics.json",
        "proof_artifact_bridge_audit.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_proof_diagnostic_refresh_does_not_mutate_runtime_defaults_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    runtime_before = paths["runtime_default_path"].read_text()
    manifest_before = paths["source_manifest_path"].read_text()

    proof_refresh.run_promoted_v6_proof_diagnostic_instrumentation_refresh(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == manifest_before
