from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_reviewed_positive_micro_validation as micro_validation


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_row(frame_id: int) -> dict[str, object]:
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"manual-review-expansion-{frame_id}",
        "windowId": "trimed-5min.mp4-manual-review-expansion-0240-0320",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "reviewDecision": "adjust_bbox",
        "reviewedBBox": {
            "x1": float(frame_id),
            "y1": float(frame_id + 1),
            "x2": float(frame_id + 10),
            "y2": float(frame_id + 11),
        },
        "lineage": {
            "manualReviewExpansionRoot": "/review/expansion",
            "promotedProofRoot": "/proof/promoted",
        },
    }


def _write_inputs(
    root: Path,
    *,
    proof_evidence: dict[str, object] | None = None,
    selected_cluster_delta: dict[str, object] | None = None,
) -> dict[str, Path]:
    output_root = root / "reviewed_positive_micro_validation_v1"
    expansion_resolution_root = root / "manual_review_expansion_resolution_v1"
    validation_root = root / "validation"
    proof_root = root / "proof"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "frozen_source_manifest.json"
    positive_rows = [_positive_row(frame_id) for frame_id in range(240, 321, 5)]

    _write_json(
        expansion_resolution_root / "expanded_reviewed_truth_seed.json",
        {
            "truthStatus": "review_resolved",
            "reviewedPositiveSeedCount": len(positive_rows),
            "reviewedNegativeSeedCount": 0,
            "reviewedPositiveSeedRows": positive_rows,
            "reviewedNegativeSeedRows": [],
        },
    )
    _write_json(
        validation_root / "arm_matrix.json",
        {
            "validationBatchName": "promoted_touchline_detector_candidate_robustness_validation_v1",
            "arms": [
                {"armName": "baseline_current", "proofRuns": []},
                {
                    "armName": "promoted_v6_baseline",
                    "runtimeOptions": {
                        "edgeShareRepairProfile": "source_robustness_shadow_profile",
                    },
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "proofSummaryPath": str(proof_root / "proof_summary.json"),
                                "selectedClusterDeltaPath": str(proof_root / "selected_cluster_delta.json"),
                            },
                        }
                    ],
                },
            ],
        },
    )
    _write_json(proof_root / "recovery_profile_matrix.json", proof_evidence or {})
    _write_json(proof_root / "proof_summary.json", {"bestProposalCollapsedFrames": 0, "bestProposalSelectedFrames": 0})
    _write_json(proof_root / "selected_cluster_delta.json", selected_cluster_delta or {"after": {}})
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
        "validation_root": validation_root,
        "proof_root": proof_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_micro_validation_loads_the_17_reviewed_positive_frames(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    summary = payload["summary"]
    assert summary["reviewedPositiveFrameCount"] == 17
    assert summary["reviewedPositiveFrames"] == list(range(240, 321, 5))


def test_micro_validation_classifies_per_frame_proposal_selection_and_acceptance_gaps(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "reviewedPositiveFrameEvidence": [
                {"frameIndex": 240, "proposalGenerated": False},
                {"frameIndex": 245, "rawDetected": True, "collapsed": False},
                {"frameIndex": 250, "collapsed": True, "selected": False},
                {"frameIndex": 255, "selected": True, "accepted": False},
                {"frameIndex": 260, "accepted": True},
            ]
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    matrix_rows = {
        row["frameIndex"]: row["gapClass"]
        for row in payload["reviewedPositiveFrameMatrix"]["reviewedPositiveFrames"]
    }
    assert matrix_rows[240] == "reviewed_positive_no_promoted_proposal"
    assert matrix_rows[245] == "reviewed_positive_raw_detected_not_collapsed"
    assert matrix_rows[250] == "reviewed_positive_collapsed_not_selected"
    assert matrix_rows[255] == "reviewed_positive_selected_not_accepted"
    assert matrix_rows[260] == "reviewed_positive_already_accepted"


def test_micro_validation_selects_selection_followthrough_when_collapsed_candidates_are_unselected(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "proposalCollapsedFrameIds": list(range(240, 321, 5)),
            "proposalSelectedFrameIds": [],
            "acceptedFrameIds": [],
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["dominantBlockerClass"] == "reviewed_positive_collapsed_not_selected"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_selection_followthrough_fix"


def test_micro_validation_selects_instrumentation_refresh_when_per_frame_coverage_is_missing(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalCollapsedFrames": 93,
                    "selectedFrames": 0,
                }
            ]
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "reviewed_positive_artifact_coverage_gap"
    assert summary["nextCorrectiveFamily"] == "proof_diagnostic_instrumentation_refresh"
    audit = payload["proofArtifactCoverageAudit"]
    assert audit["perFrameProofCoverageAvailable"] is False
    assert "reviewed_positive_frame_level_proposal_selection_fields_missing" in audit["missingArtifactFields"]


def test_micro_validation_keeps_uncovered_reviewed_frames_as_coverage_gaps(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "proposalCollapsedFrameIds": [240, 245, 250],
            "proposalSelectedFrameIds": [],
            "acceptedFrameIds": [],
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    rows = payload["reviewedPositiveFrameMatrix"]["reviewedPositiveFrames"]
    by_frame = {row["frameIndex"]: row["gapClass"] for row in rows}
    assert by_frame[240] == "reviewed_positive_collapsed_not_selected"
    assert by_frame[255] == "reviewed_positive_artifact_coverage_gap"
    assert payload["proofArtifactCoverageAudit"]["perFrameProofCoverageAvailable"] is False
    assert payload["summary"]["dominantBlockerClass"] == "reviewed_positive_artifact_coverage_gap"
    assert payload["summary"]["nextCorrectiveFamily"] == "proof_diagnostic_instrumentation_refresh"


def test_micro_validation_parses_dict_shaped_frame_maps(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "proposalCollapsedFramesByFrame": {
                str(frame_id): {"frameIndex": frame_id}
                for frame_id in range(240, 321, 5)
            },
            "proposalSelectedFrameIds": [],
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    assert payload["summary"]["dominantBlockerClass"] == "reviewed_positive_collapsed_not_selected"
    assert payload["proofArtifactCoverageAudit"]["perFrameProofCoverageAvailable"] is True


def test_micro_validation_reads_selected_and_accepted_frames_from_selected_cluster_delta(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        proof_evidence={
            "proposalCollapsedFrameIds": list(range(240, 321, 5)),
        },
        selected_cluster_delta={
            "after": {
                "selectedFrameIds": [240, 245],
                "acceptedFrameIds": [250],
            }
        },
    )

    payload = micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    rows = {
        row["frameIndex"]: row["gapClass"]
        for row in payload["reviewedPositiveFrameMatrix"]["reviewedPositiveFrames"]
    }
    assert rows[240] == "reviewed_positive_selected_not_accepted"
    assert rows[245] == "reviewed_positive_selected_not_accepted"
    assert rows[250] == "reviewed_positive_already_accepted"


def test_micro_validation_writes_all_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    for filename in (
        "reviewed_positive_micro_validation_summary.json",
        "reviewed_positive_frame_matrix.json",
        "reviewed_positive_gap_taxonomy.json",
        "proof_artifact_coverage_audit.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_micro_validation_does_not_mutate_runtime_defaults_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    micro_validation.run_promoted_v6_reviewed_positive_micro_validation(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
