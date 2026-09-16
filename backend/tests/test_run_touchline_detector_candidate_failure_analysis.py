from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_touchline_detector_candidate_failure_analysis as run_touchline_detector_candidate_failure_analysis


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_proof_bundle(
    storage_root: Path,
    bundle_name: str,
    *,
    auxiliary_ball_model_name: str,
    accepted_ball_frames: int,
    controlled_possession_frames: int,
    ball_track_viable: bool,
    ball_track_edge_frame_share: float | None,
    raw_probe_frame_ids: list[int],
    filtered_probe_frame_ids: list[int],
    accepted_frame_ids: list[int],
    proposal_profile_rows: list[dict[str, object]],
    supported_accepted_ball_ratio: float = 0.0,
    candidate_edge_share: float = 0.0,
    unsupported_accepted_edge_frames: int = 0,
    unknown_gap_count: int = 0,
    longest_unknown_gap_frames: int = 0,
    event_types: dict[str, int] | None = None,
    truth_gate_reasons: list[str] | None = None,
    include_event_family_count_in_proof_summary: bool = False,
    proposal_direct_seed_pitch_polygon_rejected_frames: int = 0,
) -> Path:
    bundle_root = storage_root / "pod_cycles" / bundle_name
    event_types = dict(event_types or {})
    truth_gate_reasons = list(truth_gate_reasons or [])
    proof_summary = {
        "acceptedBallFrames": accepted_ball_frames,
        "controlledPossessionFrames": controlled_possession_frames,
        "ballTrackViable": ball_track_viable,
        "ballTrackEdgeFrameShare": ball_track_edge_frame_share,
        "supportedAcceptedBallRatio": supported_accepted_ball_ratio,
        "candidateEdgeShare": candidate_edge_share,
        "unsupportedAcceptedEdgeFrames": unsupported_accepted_edge_frames,
        "unknownGapCount": unknown_gap_count,
        "longestUnknownGapFrames": longest_unknown_gap_frames,
        "eventTypes": event_types,
        "truthGateReasons": truth_gate_reasons,
        "bestProposalDirectSeedPitchPolygonRejectedFrames": proposal_direct_seed_pitch_polygon_rejected_frames,
    }
    if include_event_family_count_in_proof_summary:
        proof_summary["eventFamilyCount"] = len(event_types)
    _write_json(
        bundle_root / "proof_summary.json",
        proof_summary,
    )
    _write_json(
        bundle_root / "ball_truth_layers.json",
        {
            "acceptedBall": {
                "rows": [{"Frame_ID": frame_id} for frame_id in accepted_frame_ids],
                "summary": {"frameCount": accepted_ball_frames},
            },
            "probeObservedBall": {
                "rawRows": [{"Frame_ID": frame_id} for frame_id in raw_probe_frame_ids],
                "filteredRows": [{"Frame_ID": frame_id} for frame_id in filtered_probe_frame_ids],
            },
            "directObservationBreakdown": {
                "trackingObservedBallFrames": 0,
                "probeObservedBallFrames": len(filtered_probe_frame_ids),
                "probeOnlyObservedBallFrames": len(filtered_probe_frame_ids),
                "acceptedFromObservedFrames": len(accepted_frame_ids),
                "acceptedFromObservedRatio": 0.0,
            },
            "supportDiagnostics": {
                "supportedAcceptedBallRatio": supported_accepted_ball_ratio,
                "unsupportedAcceptedEdgeFrames": unsupported_accepted_edge_frames,
            },
        },
    )
    _write_json(
        bundle_root / "ball_pipeline_trace.json",
        {
            "detectorModelPath": "/workspace/weights/yolov10n.pt",
            "detectorModelName": "yolov10n.pt",
            "primaryModelPath": "/workspace/weights/yolov10n.pt",
            "primaryModelName": "yolov10n.pt",
            "auxiliaryBallModelPath": f"/workspace/weights/{auxiliary_ball_model_name}",
            "auxiliaryBallModelName": auxiliary_ball_model_name,
            "auxiliaryBallModelProfile": "ball_probe_only_v1",
            "trackingModelPath": "/workspace/weights/yolov10n.pt",
            "trackingDetectorProfile": "coco_tracking_full",
            "probeModelPath": f"/workspace/weights/{auxiliary_ball_model_name}",
            "probeDetectorProfile": "ball_probe_only_v1",
            "recoveryModelPath": f"/workspace/weights/{auxiliary_ball_model_name}",
            "recoveryDetectorProfile": "ball_probe_only_v1",
        },
    )
    _write_json(
        bundle_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "proposal_windows_075",
            "profiles": proposal_profile_rows,
        },
    )
    _write_json(
        bundle_root / "selected_cluster_delta.json",
        {
            "before": {
                "acceptedBallFrames": accepted_ball_frames,
                "controlledPossessionFrames": controlled_possession_frames,
                "supportedAcceptedBallRatio": supported_accepted_ball_ratio,
                "eventFamilyCount": len(event_types),
                "truthGateReasons": truth_gate_reasons,
                "candidateEdgeShare": candidate_edge_share,
                "unsupportedAcceptedEdgeFrames": unsupported_accepted_edge_frames,
                "unknownGapCount": unknown_gap_count,
                "longestUnknownGapFrames": longest_unknown_gap_frames,
                "bestProposalDirectSeedPitchPolygonRejectedFrames": proposal_direct_seed_pitch_polygon_rejected_frames,
            }
        },
    )
    return bundle_root


def _write_evaluation_bundle(
    storage_root: Path,
    *,
    candidate_name: str,
    candidate_bundle_name: str,
    candidate_detector_label: str,
    candidate_bundle_kwargs: dict[str, object],
    baseline_bundle_name: str | None = None,
    baseline_bundle_kwargs: dict[str, object] | None = None,
    screen_winner_label: str = "yolov10n.pt_baseline_full_detector",
    candidate_screen_viable: bool = False,
    candidate_screen_selected_frames: int = 0,
    candidate_screen_edge_share: float = 1.0,
) -> Path:
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    evaluation_root = candidate_root / "evaluation_v1"
    candidate_bundle = _write_proof_bundle(
        storage_root,
        candidate_bundle_name,
        auxiliary_ball_model_name=f"{candidate_name}-best.pt",
        **candidate_bundle_kwargs,
    )

    discarded_bundles: list[dict[str, object]] | None = None
    if baseline_bundle_name is not None and baseline_bundle_kwargs is not None:
        baseline_bundle = _write_proof_bundle(
            storage_root,
            baseline_bundle_name,
            auxiliary_ball_model_name="baseline-best.pt",
            **baseline_bundle_kwargs,
        )
        discarded_bundles = [
            {
                "reason": "discarded_due_to_pre_fix_product_comparator_false_positive",
                "proofKind": "baseline_control",
                "proofSummaryPath": str(baseline_bundle / "proof_summary.json"),
            }
        ]

    _write_json(
        evaluation_root / "screen_matrix.json",
        {
            "screenWinningDetectorLabel": screen_winner_label,
            "cells": [
                {
                    "detectorLabel": "yolov10n.pt_baseline_full_detector",
                    "recommendedProfileName": "baseline_player_window",
                    "screenSucceeded": True,
                    "viable": True,
                    "selectedFrames": 38,
                    "selectedEdgeFrameShare": 0.132,
                },
                {
                    "detectorLabel": candidate_detector_label,
                    "recommendedProfileName": "proposal_windows_075" if candidate_screen_viable else "no_viable_profile",
                    "screenSucceeded": True,
                    "viable": candidate_screen_viable,
                    "selectedFrames": candidate_screen_selected_frames,
                    "selectedEdgeFrameShare": candidate_screen_edge_share,
                },
            ],
        },
    )
    _write_json(
        evaluation_root / "proof_report.json",
        {
            "trainingCandidateName": candidate_name,
            "evaluationBatchName": f"touchline_detector_candidate_evaluation_{candidate_name.rsplit('_', 1)[-1]}",
            "candidateBaselineProofRan": True,
            "candidateBaselineResult": {
                "detectorLabel": candidate_detector_label,
                "summaryPath": str(candidate_bundle / "proof_summary.json"),
                "ballTruthLayersPath": str(candidate_bundle / "ball_truth_layers.json"),
                "acceptedBallFrames": candidate_bundle_kwargs["accepted_ball_frames"],
                "controlledPossessionFrames": candidate_bundle_kwargs["controlled_possession_frames"],
                "ballTrackViable": candidate_bundle_kwargs["ball_track_viable"],
                "ballTrackEdgeFrameShare": candidate_bundle_kwargs["ball_track_edge_frame_share"],
                "productBeatsPlateau": False,
            },
            "baselineControlProofRan": False,
            "baselineControlResult": None,
            "candidateCompoundThinProofRan": False,
            "candidateCompoundThinResult": None,
            "discardedIntermediateProofBundles": discarded_bundles,
        },
    )
    _write_json(
        evaluation_root / "evaluation_summary.json",
        {
            "trainingCandidateName": candidate_name,
            "evaluationBatchName": f"touchline_detector_candidate_evaluation_{candidate_name.rsplit('_', 1)[-1]}",
            "screenCompleted": True,
            "screenWinningDetectorLabel": screen_winner_label,
            "candidateBaselineProofRan": True,
            "candidateBaselineProductBeatsPlateau": False,
            "baselineControlProofRan": False,
            "candidateCompoundThinProofRan": False,
            "readyForPromotion": False,
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            "evaluationPrimaryBlocker": "candidate_baseline_did_not_beat_plateau",
        },
    )
    _write_json(
        evaluation_root / "batch_outcome_analysis.json",
        {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": False,
            "primaryBlocker": "candidate_baseline_did_not_beat_plateau",
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
            "executionBlockersResolved": True,
            "evaluationReachedProductComparison": True,
        },
    )
    return evaluation_root


def _write_previous_failure_analysis_root(storage_root: Path, *, candidate_name: str) -> None:
    failure_root = storage_root / "trained_detector_candidates" / candidate_name / "failure_analysis_v1"
    _write_json(
        failure_root / "failure_analysis_summary.json",
        {
            "trainingCandidateName": candidate_name,
            "failureAnalysisBatchName": "touchline_detector_candidate_failure_analysis_v1",
            "rootCauseClass": "auxiliary_probe_zero_raw_rows",
            "recommendedFixClass": "model_data_quality",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": False,
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
    )
    _write_json(
        failure_root / "batch_outcome_analysis.json",
        {
            "goalAchieved": True,
            "roadmapAdvanceAllowed": False,
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
    )


def _write_v2_and_v3_evaluation_bundles(storage_root: Path) -> None:
    _write_evaluation_bundle(
        storage_root,
        candidate_name="touchline_detector_candidate_v2",
        candidate_bundle_name="touchline-detector-candidate-v2-probe-assist-baseline-20260422223225",
        candidate_detector_label="touchline_detector_candidate_v2_probe_assist",
        candidate_bundle_kwargs={
            "accepted_ball_frames": 0,
            "controlled_possession_frames": 0,
            "ball_track_viable": False,
            "ball_track_edge_frame_share": 1.0,
            "raw_probe_frame_ids": [],
            "filtered_probe_frame_ids": [],
            "accepted_frame_ids": [],
            "proposal_profile_rows": [
                {
                    "name": "baseline_player_window",
                    "selectedFrames": 0,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 0,
                    "proposalDirectSeedDetectedFrames": 0,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
                {
                    "name": "proposal_windows_075",
                    "selectedFrames": 0,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 0,
                    "proposalDirectSeedDetectedFrames": 0,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
            ],
        },
        baseline_bundle_name="yolov10n-pt-baseline-full-detector-baseline-control-20260422224502",
        baseline_bundle_kwargs={
            "accepted_ball_frames": 101,
            "controlled_possession_frames": 0,
            "ball_track_viable": False,
            "ball_track_edge_frame_share": 0.812,
            "raw_probe_frame_ids": list(range(100, 110)),
            "filtered_probe_frame_ids": list(range(100, 105)),
            "accepted_frame_ids": list(range(100, 105)),
            "proposal_profile_rows": [
                {
                    "name": "baseline_player_window",
                    "selectedFrames": 17,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 0,
                    "proposalDirectSeedDetectedFrames": 0,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
                {
                    "name": "proposal_windows_075",
                    "selectedFrames": 20,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 9,
                    "proposalDirectSeedDetectedFrames": 12,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
            ],
        },
    )
    _write_evaluation_bundle(
        storage_root,
        candidate_name="touchline_detector_candidate_v3",
        candidate_bundle_name="touchline-detector-candidate-v3-probe-assist-baseline-20260423045031",
        candidate_detector_label="touchline_detector_candidate_v3_probe_assist",
        candidate_bundle_kwargs={
            "accepted_ball_frames": 0,
            "controlled_possession_frames": 0,
            "ball_track_viable": False,
            "ball_track_edge_frame_share": 0.0,
            "raw_probe_frame_ids": [],
            "filtered_probe_frame_ids": [],
            "accepted_frame_ids": [],
            "proposal_profile_rows": [
                {
                    "name": "baseline_player_window",
                    "selectedFrames": 0,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 0,
                    "proposalDirectSeedDetectedFrames": 0,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
                {
                    "name": "proposal_windows_075",
                    "selectedFrames": 0,
                    "selectedScore": None,
                    "selectedEdgeFrameShare": None,
                    "proposalPlayerRankedDetectedFrames": 0,
                    "proposalDirectSeedDetectedFrames": 0,
                    "proposalDirectSeedRawHitFilteredOutFrames": 0,
                },
            ],
        },
    )
    _write_previous_failure_analysis_root(
        storage_root,
        candidate_name="touchline_detector_candidate_v2",
    )


def test_classify_root_cause_prioritizes_zero_raw_probe_rows_before_product_lift() -> None:
    root_cause = run_touchline_detector_candidate_failure_analysis.classify_failure_root_cause(
        screen_completed=True,
        candidate_screen_succeeded=True,
        candidate_raw_probe_row_count=0,
        candidate_filtered_probe_row_count=0,
        candidate_accepted_ball_frame_count=0,
    )

    assert root_cause == "auxiliary_probe_zero_raw_rows"
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_class_for_root_cause(root_cause)
        == "model_data_quality"
    )


def test_classify_root_cause_distinguishes_filter_and_acceptance_collapse() -> None:
    assert (
        run_touchline_detector_candidate_failure_analysis.classify_failure_root_cause(
            screen_completed=True,
            candidate_screen_succeeded=True,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
        )
        == "auxiliary_probe_rows_filtered_out"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.classify_failure_root_cause(
            screen_completed=True,
            candidate_screen_succeeded=True,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=4,
            candidate_accepted_ball_frame_count=0,
        )
        == "accepted_layer_collapse_after_probe"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.classify_failure_root_cause(
            screen_completed=True,
            candidate_screen_succeeded=True,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=4,
            candidate_accepted_ball_frame_count=3,
        )
        == "insufficient_product_lift"
    )


def test_classify_change_from_previous_candidate_detects_no_observable_improvement() -> None:
    assert (
        run_touchline_detector_candidate_failure_analysis.classify_change_from_previous_candidate(
            candidate_max_proposal_detected_frames=0,
            previous_candidate_max_proposal_detected_frames=0,
            candidate_raw_probe_row_count=0,
            previous_candidate_raw_probe_row_count=0,
            candidate_filtered_probe_row_count=0,
            previous_candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
            previous_candidate_accepted_ball_frame_count=0,
            candidate_controlled_possession_frames=0,
            previous_candidate_controlled_possession_frames=0,
            candidate_ball_track_viable=False,
            previous_candidate_ball_track_viable=False,
        )
        == "no_observable_improvement"
    )


def test_recommended_fix_focus_prioritizes_proposal_then_raw_then_filter_then_acceptance() -> None:
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_focus_for_failure(
            candidate_max_proposal_detected_frames=0,
            candidate_raw_probe_row_count=0,
            candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
        )
        == "proposal_signal_generation"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_focus_for_failure(
            candidate_max_proposal_detected_frames=5,
            candidate_raw_probe_row_count=0,
            candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
        )
        == "raw_probe_materialization"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_focus_for_failure(
            candidate_max_proposal_detected_frames=5,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
        )
        == "probe_filtering_behavior"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_focus_for_failure(
            candidate_max_proposal_detected_frames=5,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=4,
            candidate_accepted_ball_frame_count=0,
        )
        == "accepted_layer_behavior"
    )
    assert (
        run_touchline_detector_candidate_failure_analysis.recommended_fix_focus_for_failure(
            candidate_max_proposal_detected_frames=5,
            candidate_raw_probe_row_count=7,
            candidate_filtered_probe_row_count=4,
            candidate_accepted_ball_frame_count=2,
        )
        == "product_lift_gap"
    )


def test_analyze_summary_surface_drift_detects_required_judge_field_gap() -> None:
    analysis = run_touchline_detector_candidate_failure_analysis.analyze_summary_surface_drift(
        proof_summary={
            "acceptedBallFrames": 0,
            "supportedAcceptedBallRatio": 0.0,
            "controlledPossessionFrames": 0,
            "truthGateReasons": ["Need controlled possession"],
        },
        selected_cluster_summary={
            "acceptedBallFrames": 0,
            "supportedAcceptedBallRatio": 0.0,
            "controlledPossessionFrames": 0,
            "eventFamilyCount": 0,
            "truthGateReasons": ["Need controlled possession"],
        },
        ball_truth_layers={
            "acceptedBall": {"summary": {"frameCount": 0}},
            "supportDiagnostics": {"supportedAcceptedBallRatio": 0.0},
        },
    )

    assert analysis["detected"] is True
    assert "missing_proof_summary_required_field:eventFamilyCount" in analysis["reasons"]


def test_bundle_summary_canonicalizes_missing_event_family_count_from_selected_cluster_delta(tmp_path: Path) -> None:
    bundle_root = _write_proof_bundle(
        tmp_path,
        "touchline-detector-candidate-v5-probe-assist-baseline-20260423150042",
        auxiliary_ball_model_name="touchline_detector_candidate_v5-best.pt",
        accepted_ball_frames=0,
        controlled_possession_frames=0,
        ball_track_viable=False,
        ball_track_edge_frame_share=0.0,
        raw_probe_frame_ids=[],
        filtered_probe_frame_ids=[],
        accepted_frame_ids=[],
        event_types={},
        truth_gate_reasons=["Need controlled possession"],
        proposal_profile_rows=[],
        include_event_family_count_in_proof_summary=False,
    )

    bundle_summary = run_touchline_detector_candidate_failure_analysis._bundle_summary(bundle_root)

    assert bundle_summary["proofSummary"]["eventFamilyCount"] == 0


def test_analyze_calibration_suspicion_requires_upstream_signal_and_pitch_polygon_collapse() -> None:
    suspicious = run_touchline_detector_candidate_failure_analysis.analyze_calibration_suspicion(
        candidate_max_proposal_detected_frames=12,
        candidate_raw_probe_row_count=0,
        candidate_filtered_probe_row_count=0,
        candidate_accepted_ball_frame_count=0,
        candidate_pitch_polygon_rejected_frames=12,
    )
    not_suspicious_without_upstream_signal = (
        run_touchline_detector_candidate_failure_analysis.analyze_calibration_suspicion(
            candidate_max_proposal_detected_frames=0,
            candidate_raw_probe_row_count=0,
            candidate_filtered_probe_row_count=0,
            candidate_accepted_ball_frame_count=0,
            candidate_pitch_polygon_rejected_frames=12,
        )
    )

    assert suspicious["detected"] is True
    assert "pitch_polygon_rejected_after_upstream_proposals" in suspicious["reasons"]
    assert not_suspicious_without_upstream_signal["detected"] is False


def test_run_touchline_detector_candidate_failure_analysis_writes_expected_artifacts_for_v3(
    tmp_path: Path,
) -> None:
    _write_v2_and_v3_evaluation_bundles(tmp_path)

    payload = run_touchline_detector_candidate_failure_analysis.run_touchline_detector_candidate_failure_analysis(
        storage_root=tmp_path,
    )

    analysis_root = (
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v3"
        / "failure_analysis_v1"
    )
    summary = json.loads((analysis_root / "failure_analysis_summary.json").read_text(encoding="utf-8"))
    baseline_delta = json.loads((analysis_root / "candidate_vs_baseline_delta.json").read_text(encoding="utf-8"))
    previous_delta = json.loads(
        (analysis_root / "candidate_vs_previous_candidate_delta.json").read_text(encoding="utf-8")
    )
    profile_delta = json.loads((analysis_root / "profile_matrix_delta.json").read_text(encoding="utf-8"))
    frame_delta = json.loads((analysis_root / "frame_level_probe_delta.json").read_text(encoding="utf-8"))
    batch_outcome = json.loads((analysis_root / "batch_outcome_analysis.json").read_text(encoding="utf-8"))

    assert payload["trainingCandidateName"] == "touchline_detector_candidate_v3"
    assert payload["previousCandidateName"] == "touchline_detector_candidate_v2"
    assert payload["failureAnalysisBatchName"] == "touchline_detector_candidate_failure_analysis_v1"
    assert summary["screenWinningDetectorLabel"] == "yolov10n.pt_baseline_full_detector"
    assert summary["candidateScreenViable"] is False
    assert summary["candidateRawProbeRowCount"] == 0
    assert summary["previousCandidateRawProbeRowCount"] == 0
    assert summary["baselineRawProbeRowCount"] == 10
    assert summary["rootCauseClass"] == "auxiliary_probe_zero_raw_rows"
    assert summary["changeFromPreviousCandidateClass"] == "no_observable_improvement"
    assert summary["recommendedFixClass"] == "model_data_quality"
    assert summary["recommendedFixFocus"] == "proposal_signal_generation"
    assert summary["summarySurfaceDriftDetected"] is False
    assert summary["calibrationSuspicionDetected"] is False
    assert summary["nextImplementationBatchRecommendation"] == "touchline_detector_candidate_v3_proposal_signal_generation_fix_v1"
    assert summary["candidateMaxProposalDetectedFramesAcrossProfiles"] == 0
    assert summary["previousCandidateMaxProposalDetectedFramesAcrossProfiles"] == 0
    assert summary["baselineMaxProposalDetectedFramesAcrossProfiles"] == 21
    assert summary["nextRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert summary["baselineControlDiagnosticEvidenceOnly"] is True
    assert baseline_delta["stageWiseDelta"]["proposalDetectionsAcrossRecoveryProfiles"]["candidateValue"] == 0
    assert baseline_delta["stageWiseDelta"]["rawProbeRows"]["baselineValue"] == 10
    assert baseline_delta["stageWiseDelta"]["acceptedBallFrames"]["baselineValue"] == 5
    assert baseline_delta["probeContributionDelta"]["rawProbeRowDelta"] == -10
    assert previous_delta["changeFromPreviousCandidateClass"] == "no_observable_improvement"
    assert previous_delta["proposalContributionDelta"]["proposalDetectedFrameDelta"] == 0
    assert profile_delta["candidateMaxProposalDetectedFramesAcrossProfiles"] == 0
    assert profile_delta["baselineMaxProposalDetectedFramesAcrossProfiles"] == 21
    assert frame_delta["layers"]["rawProbe"]["candidateFrameIds"] == []
    assert frame_delta["layers"]["rawProbe"]["baselineFrameIds"] == list(range(100, 110))
    assert batch_outcome["goalAchieved"] is True
    assert batch_outcome["roadmapAdvanceAllowed"] is False
    assert batch_outcome["nextRecommendedNextLever"] == "evaluate_touchline_detector_candidate"
    assert batch_outcome["recommendedFixClass"] == "model_data_quality"
    assert batch_outcome["recommendedFixFocus"] == "proposal_signal_generation"
    assert batch_outcome["summarySurfaceDriftDetected"] is False
    assert batch_outcome["calibrationSuspicionDetected"] is False
    assert batch_outcome["nextImplementationBatchRecommendation"] == "touchline_detector_candidate_v3_proposal_signal_generation_fix_v1"
    assert batch_outcome["brainstormFixes"]
    assert (analysis_root / "batch_outcome_analysis.md").exists()


def test_run_touchline_detector_candidate_failure_analysis_fails_clearly_when_evaluation_bundle_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="evaluation_summary.json"):
        run_touchline_detector_candidate_failure_analysis.run_touchline_detector_candidate_failure_analysis(
            storage_root=tmp_path,
            candidate_name="touchline_detector_candidate_v3",
            previous_candidate_name="touchline_detector_candidate_v2",
        )
