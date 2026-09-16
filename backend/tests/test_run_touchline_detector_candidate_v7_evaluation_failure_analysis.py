from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_touchline_detector_candidate_v7_evaluation_failure_analysis as v7_failure


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_v7_failure_bundle(tmp_path: Path, *, raw_probe_frames: int = 0) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    evaluation_root = candidate_root / "evaluation_v1"
    proof_root = tmp_path / "pod_cycles" / "v7-proof"
    prep_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "touchline_detector_candidate_v7_training_prep_v1"
    )
    _write_json(
        evaluation_root / "evaluation_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "evaluationBatchName": "touchline_detector_candidate_evaluation_v7",
            "screenCompleted": True,
            "screenWinningDetectorLabel": "yolov10n.pt_baseline_full_detector",
            "candidateBaselineProductBeatsPlateau": False,
            "evaluationPrimaryBlocker": "candidate_baseline_did_not_beat_plateau",
            "readyForPromotion": False,
            "candidateBaselineProofSummaryPath": str(proof_root / "proof_summary.json"),
        },
    )
    _write_json(
        evaluation_root / "screen_matrix.json",
        {
            "screenWinningDetectorLabel": "yolov10n.pt_baseline_full_detector",
            "cells": [
                {
                    "detectorLabel": "yolov10n.pt_baseline_full_detector",
                    "recommendedProfileName": "baseline_player_window",
                    "viable": True,
                    "selectedFrames": 38,
                    "selectedScore": 100.0,
                    "candidateSummary": {"candidateRows": 512, "uniqueFrames": 399},
                    "selectedSummary": {"frames": 38},
                },
                {
                    "detectorLabel": "touchline_detector_candidate_v7_probe_assist",
                    "recommendedProfileName": "no_viable_profile",
                    "viable": False,
                    "selectedFrames": 0,
                    "selectedScore": 0.0,
                    "candidateSummary": {},
                    "selectedSummary": {},
                    "auxiliaryBallModelPath": "/tmp/best.pt",
                },
            ],
        },
    )
    _write_json(
        evaluation_root / "proof_report.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v7",
            "candidateBaselineProofRan": True,
            "candidateBaselineResult": {
                "acceptedBallFrames": 0,
                "controlledPossessionFrames": 0,
                "ballTrackViable": False,
                "ballTrackEdgeFrameShare": 0.0,
                "productBeatsPlateau": False,
                "summaryPath": str(proof_root / "proof_summary.json"),
                "selectedClusterDeltaPath": str(proof_root / "selected_cluster_delta.json"),
                "ballTruthLayersPath": str(proof_root / "ball_truth_layers.json"),
            },
        },
    )
    _write_json(
        proof_root / "proof_summary.json",
        {
            "acceptedBallFrames": 0,
            "controlledPossessionFrames": 0,
            "ballTrackViable": False,
            "ballTrackEdgeFrameShare": 0.0,
            "rawProbeObservedBallFrames": raw_probe_frames,
            "probeObservedBallFrames": raw_probe_frames,
            "filteredProbeObservedBallFrames": 0,
            "suppressedProbeObservedBallFrames": 0,
            "bestProposalRawDetectedFrames": 0,
            "bestProposalCandidateFrames": 0,
            "bestProposalSelectedFrames": 0,
            "truthGateReasons": ["Need controlled possession frames/frameCount >= 20%"],
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "profiles": [
                {
                    "name": "baseline_player_window",
                    "viable": False,
                    "candidateFrames": 0,
                    "selectedFrames": 0,
                    "proposalRawDetectedFrames": 0,
                    "proposalCandidateFrames": 0,
                    "proposalCollapsedFrames": 0,
                    "proposalSelectedFrameIds": [],
                }
            ]
        },
    )
    _write_json(proof_root / "selected_cluster_delta.json", {"before": {}, "after": {}})
    _write_json(proof_root / "ball_truth_layers.json", {"acceptedBall": []})
    _write_json(
        prep_root / "v7_training_manifest.json",
        {
            "positiveExampleCount": 30,
            "negativeExampleCount": 78,
            "positiveExamples": [{"frameIndex": 240, "bbox": {"x1": 1, "y1": 1, "x2": 2, "y2": 2}}],
            "negativeExamples": [{"frameIndex": 260, "truthUse": "negative_only_refuted_seed"}],
            "remainingPendingReviewCount": 0,
        },
    )
    return candidate_root


def test_v7_evaluation_failure_analysis_classifies_zero_probe_signal(
    tmp_path: Path,
) -> None:
    _write_v7_failure_bundle(tmp_path)

    payload = v7_failure.run_touchline_detector_candidate_v7_evaluation_failure_analysis(
        storage_root=tmp_path,
    )

    output_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "evaluation_failure_analysis_v1"
    )
    summary = _load_json(output_root / "v7_evaluation_failure_summary.json")
    taxonomy = _load_json(output_root / "v7_probe_failure_taxonomy.json")
    screen_delta = _load_json(output_root / "v7_screen_probe_delta.json")
    manifest_alignment = _load_json(output_root / "v7_training_manifest_alignment.json")
    batch_outcome = _load_json(output_root / "batch_outcome_analysis.json")

    assert payload["dominantBlockerClass"] == "v7_auxiliary_probe_zero_raw_signal"
    assert summary["candidateScreenViable"] is False
    assert summary["candidateRawProbeObservedBallFrames"] == 0
    assert summary["nextCorrectiveFamily"] == "v7_probe_assist_integration_audit"
    assert taxonomy["dominantBlockerClass"] == "v7_auxiliary_probe_zero_raw_signal"
    assert screen_delta["baselineSelectedFrames"] == 38
    assert screen_delta["candidateSelectedFrames"] == 0
    assert manifest_alignment["positiveExampleCount"] == 30
    assert manifest_alignment["negativeExampleCount"] == 78
    assert batch_outcome["goalAchieved"] is True
    assert batch_outcome["roadmapAdvanceAllowed"] is False
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_v7_evaluation_failure_analysis_selects_proposal_window_fix_when_raw_probe_exists(
    tmp_path: Path,
) -> None:
    _write_v7_failure_bundle(tmp_path, raw_probe_frames=12)

    payload = v7_failure.run_touchline_detector_candidate_v7_evaluation_failure_analysis(
        storage_root=tmp_path,
    )

    assert payload["dominantBlockerClass"] == "v7_raw_probe_not_materialized_into_proposals"
    assert payload["nextCorrectiveFamily"] == "v7_probe_proposal_window_integration_fix"


def test_v7_evaluation_failure_analysis_fails_clearly_without_evaluation_summary(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="evaluation_summary.json"):
        v7_failure.run_touchline_detector_candidate_v7_evaluation_failure_analysis(
            storage_root=tmp_path,
        )
