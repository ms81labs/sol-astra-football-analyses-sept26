from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_touchline_detector_candidate_retention_delta_analysis as retention_delta_analysis


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _proof_metrics(
    *,
    accepted_ball_frames: int,
    controlled_possession_frames: int,
    supported_ratio: float,
    unsupported_edge_frames: int,
    edge_share: float,
    viable: bool,
    event_family_count: int,
    truth_gate_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "acceptedBallFrames": accepted_ball_frames,
        "controlledPossessionFrames": controlled_possession_frames,
        "supportedAcceptedBallRatio": supported_ratio,
        "unsupportedAcceptedEdgeFrames": unsupported_edge_frames,
        "ballTrackEdgeFrameShare": edge_share,
        "ballTrackViable": viable,
        "eventFamilyCount": event_family_count,
        "truthGateReasons": truth_gate_reasons or [],
    }


def _write_selected_cluster_bundle(
    bundle_root: Path,
    *,
    before_metrics: dict[str, object],
    after_metrics: dict[str, object],
) -> Path:
    bundle_root.mkdir(parents=True, exist_ok=True)
    selected_cluster_delta_path = bundle_root / "selected_cluster_delta.json"
    _write_json(
        selected_cluster_delta_path,
        {
            "savedMatchId": bundle_root.name,
            "selectedClusterId": 0,
            "before": before_metrics,
            "after": after_metrics,
            "improvedFields": ["controlledPossessionFrames", "eventFamilyCount"],
            "remainingTruthGateReasons": list(after_metrics.get("truthGateReasons") or []),
        },
    )
    _write_json(bundle_root / "proof_summary.json", before_metrics)
    return selected_cluster_delta_path


def _write_validation_inputs(
    tmp_path: Path,
    *,
    promoted_before: dict[str, object],
    promoted_after: dict[str, object],
    promoted_final_source_summary: dict[str, object],
) -> tuple[Path, Path]:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    validation_root = suite_root / "promoted_touchline_detector_candidate_robustness_validation_v1"
    evaluation_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v6" / "evaluation_v1"
    validation_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)

    baseline_before = _proof_metrics(
        accepted_ball_frames=101,
        controlled_possession_frames=0,
        supported_ratio=0.97,
        unsupported_edge_frames=1,
        edge_share=0.812,
        viable=False,
        event_family_count=2,
        truth_gate_reasons=["accepted_sparse", "controlled_sparse"],
    )
    baseline_after = _proof_metrics(
        accepted_ball_frames=101,
        controlled_possession_frames=98,
        supported_ratio=0.97,
        unsupported_edge_frames=1,
        edge_share=0.812,
        viable=False,
        event_family_count=5,
        truth_gate_reasons=["accepted_sparse", "controlled_sparse"],
    )
    thin_before = dict(promoted_before)
    thin_after = dict(promoted_after)

    baseline_delta_path = _write_selected_cluster_bundle(
        tmp_path / "pod_cycles" / "baseline-control",
        before_metrics=baseline_before,
        after_metrics=baseline_after,
    )
    promoted_delta_path = _write_selected_cluster_bundle(
        tmp_path / "pod_cycles" / "promoted-baseline",
        before_metrics=promoted_before,
        after_metrics=promoted_after,
    )
    thin_delta_path = _write_selected_cluster_bundle(
        tmp_path / "pod_cycles" / "promoted-thin",
        before_metrics=thin_before,
        after_metrics=thin_after,
    )

    arm_matrix = {
        "generatedAt": "2026-04-24T00:00:00+00:00",
        "validationBatchName": "promoted_touchline_detector_candidate_robustness_validation_v1",
        "trainingCandidateName": "touchline_detector_candidate_v6",
        "runtimeContract": {},
        "arms": [
            {
                "armName": "baseline_current",
                "sourceSummaries": {
                    "trimed-5min.mp4": {
                        "medianAcceptedRetentionRatio": 1.0,
                        "medianControlledRetentionRatio": 1.0,
                        "medianSupportedAcceptedBallRatio": 0.97,
                        "medianUnsupportedAcceptedEdgeFrames": 1.0,
                        "medianBallTrackEdgeFrameShare": 0.812,
                        "sourceViable": False,
                        "sourceFailureSignal": "high_ball_track_edge_frame_share",
                    }
                },
                "proofRuns": [
                    {
                        "sourceClipId": "trimed-5min.mp4",
                        "reusedEvidence": {
                            "selectedClusterDeltaPath": str(baseline_delta_path),
                        },
                    }
                ],
            },
            {
                "armName": "promoted_v6_baseline",
                "sourceSummaries": {
                    "trimed-5min.mp4": promoted_final_source_summary,
                },
                "proofRuns": [
                    {
                        "sourceClipId": "trimed-5min.mp4",
                        "reusedEvidence": {
                            "selectedClusterDeltaPath": str(promoted_delta_path),
                        },
                    }
                ],
            },
            {
                "armName": "promoted_v6_plus_best_thin",
                "sourceSummaries": {
                    "trimed-5min.mp4": promoted_final_source_summary,
                },
                "proofRuns": [
                    {
                        "sourceClipId": "trimed-5min.mp4",
                        "reusedEvidence": {
                            "selectedClusterDeltaPath": str(thin_delta_path),
                        },
                    }
                ],
            },
        ],
    }
    _write_json(validation_root / "arm_matrix.json", arm_matrix)
    _write_json(
        validation_root / "validation_summary.json",
        {
            "validationBatchName": "promoted_touchline_detector_candidate_robustness_validation_v1",
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "winningArmName": "promoted_v6_baseline",
            "winningPromotionBlockers": [
                "accepted_retention_below_guardrail",
                "controlled_retention_below_guardrail",
            ],
            "winningFailingSourceEdgeShareImprovement": 0.712,
        },
    )
    _write_json(
        evaluation_root / "evaluation_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v6",
        },
    )
    return validation_root, evaluation_root


def test_retention_delta_analysis_classifies_accepted_signal_retention_collapse(tmp_path: Path) -> None:
    validation_root, evaluation_root = _write_validation_inputs(
        tmp_path,
        promoted_before=_proof_metrics(
            accepted_ball_frames=10,
            controlled_possession_frames=0,
            supported_ratio=1.0,
            unsupported_edge_frames=0,
            edge_share=0.1,
            viable=True,
            event_family_count=1,
            truth_gate_reasons=["accepted_sparse", "controlled_sparse"],
        ),
        promoted_after=_proof_metrics(
            accepted_ball_frames=10,
            controlled_possession_frames=13,
            supported_ratio=1.0,
            unsupported_edge_frames=0,
            edge_share=0.1,
            viable=True,
            event_family_count=2,
            truth_gate_reasons=["accepted_sparse", "controlled_sparse"],
        ),
        promoted_final_source_summary={
            "medianAcceptedRetentionRatio": 0.099,
            "medianControlledRetentionRatio": 0.133,
            "medianSupportedAcceptedBallRatio": 1.0,
            "medianUnsupportedAcceptedEdgeFrames": 0.0,
            "medianBallTrackEdgeFrameShare": 0.1,
            "sourceViable": True,
            "sourceFailureSignal": "low_accepted_ball_ratio",
        },
    )

    payload = retention_delta_analysis.run_promoted_touchline_detector_candidate_retention_delta_analysis(
        storage_root=tmp_path,
        validation_root=validation_root,
        analysis_root=tmp_path / "analysis",
        evaluation_root=evaluation_root,
    )

    summary = _load_json(tmp_path / "analysis" / "retention_delta_summary.json")
    stage_delta = _load_json(tmp_path / "analysis" / "failing_source_stage_delta.json")

    assert payload["primaryRetentionBlockerClass"] == "accepted_signal_retention_collapse"
    assert payload["nextImplementationBatchRecommendation"] == (
        "touchline_detector_candidate_v6_accepted_signal_retention_fix_v1"
    )
    assert summary["selectedClusterStepImplicated"] is False
    assert stage_delta["arms"][1]["selectedClusterBefore"]["acceptedRetentionRatio"] == 0.099
    assert (tmp_path / "analysis" / "selected_cluster_follow_through_delta.json").exists()
    assert (tmp_path / "analysis" / "decision_matrix.json").exists()


def test_retention_delta_analysis_classifies_selected_cluster_follow_through_collapse(tmp_path: Path) -> None:
    validation_root, evaluation_root = _write_validation_inputs(
        tmp_path,
        promoted_before=_proof_metrics(
            accepted_ball_frames=80,
            controlled_possession_frames=0,
            supported_ratio=0.95,
            unsupported_edge_frames=0,
            edge_share=0.15,
            viable=True,
            event_family_count=2,
            truth_gate_reasons=["controlled_sparse"],
        ),
        promoted_after=_proof_metrics(
            accepted_ball_frames=80,
            controlled_possession_frames=20,
            supported_ratio=0.95,
            unsupported_edge_frames=0,
            edge_share=0.15,
            viable=True,
            event_family_count=2,
            truth_gate_reasons=["controlled_sparse"],
        ),
        promoted_final_source_summary={
            "medianAcceptedRetentionRatio": 0.792,
            "medianControlledRetentionRatio": 0.204,
            "medianSupportedAcceptedBallRatio": 0.95,
            "medianUnsupportedAcceptedEdgeFrames": 0.0,
            "medianBallTrackEdgeFrameShare": 0.15,
            "sourceViable": True,
            "sourceFailureSignal": "low_controlled_possession_ratio",
        },
    )

    payload = retention_delta_analysis.run_promoted_touchline_detector_candidate_retention_delta_analysis(
        storage_root=tmp_path,
        validation_root=validation_root,
        analysis_root=tmp_path / "analysis",
        evaluation_root=evaluation_root,
    )

    decision_matrix = _load_json(tmp_path / "analysis" / "decision_matrix.json")

    assert payload["primaryRetentionBlockerClass"] == "selected_cluster_follow_through_collapse"
    assert payload["nextImplementationBatchRecommendation"] == (
        "touchline_detector_candidate_v6_selected_cluster_follow_through_fix_v1"
    )
    assert decision_matrix["resolvedDecision"]["selectedClusterStepImplicated"] is True
