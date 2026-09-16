import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_acceptance_fix


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _selected_rows(*, acceptance_trace: dict | None = None) -> list[dict]:
    rows = []
    for frame_id in [250, 255, 260, 265, 270]:
        recovery_profile = {
            "frameIndex": frame_id,
            "proposalGenerated": True,
            "rawDetected": True,
            "collapsed": True,
            "selected": True,
            "accepted": False,
            "proposalWindowKinds": ["reviewed_positive_audit_context_8"],
        }
        if acceptance_trace is not None:
            recovery_profile["acceptanceGateTrace"] = dict(acceptance_trace)
        rows.append(
            {
                "frameIndex": frame_id,
                "reviewItemId": f"review-{frame_id}",
                "candidateFrameId": f"manual-review-expansion-{frame_id}",
                "windowId": "trimed-5min.mp4-manual-review-expansion-0240-0320",
                "sourceClipId": "trimed-5min.mp4",
                "reviewedBBox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                "rawDetected": True,
                "candidateGenerated": True,
                "collapsed": True,
                "selected": True,
                "accepted": False,
                "proposalWindowKinds": ["reviewed_positive_audit_context_8"],
                "gapClass": "reviewed_positive_selection_evidence_gap",
                "proofEvidence": {
                    "coverage": {
                        "proposalGenerated": True,
                        "rawDetected": True,
                        "collapsed": True,
                        "selected": True,
                        "accepted": False,
                    },
                    "recoveryProfile": recovery_profile,
                },
            }
        )
    return rows


def _write_common_inputs(
    tmp_path: Path,
    *,
    acceptance_trace: dict | None = None,
    accepted_frames: list[int] | None = None,
    rejected_positive_count: int = 0,
) -> dict[str, Path]:
    selection_root = tmp_path / "reviewed_positive_selection_followthrough_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"
    output_root = tmp_path / "reviewed_positive_acceptance_fix_v1"
    rows = _selected_rows(acceptance_trace=acceptance_trace)
    accepted_frames = list(accepted_frames or [])

    _write_json(
        selection_root / "reviewed_positive_selection_followthrough_matrix.json",
        {
            "reviewedPositiveFrameCount": 17,
            "collapsedReviewedPositiveFrameCount": 5,
            "classifiedCollapsedFrameCount": 5,
            "rejectedBootstrapSeedPositiveEvidenceCount": rejected_positive_count,
            "collapsedReviewedPositiveFrames": rows,
        },
    )
    _write_json(
        selection_root / "reviewed_positive_selection_followthrough_summary.json",
        {
            "batchStatus": "succeeded",
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "reviewedPositiveFrameCount": 17,
            "reviewedPositiveCollapsedFrameCount": 5,
            "reviewedPositiveSelectedFrameCount": 5,
            "reviewedPositiveAcceptedFrameCount": 0,
            "nextCorrectiveFamily": "reviewed_positive_acceptance_fix",
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": None,
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "selectedFrames": 5,
                    "proposalFrameDiagnostics": [
                        dict(row["proofEvidence"]["recoveryProfile"]) for row in rows
                    ],
                }
            ],
        },
    )
    _write_json(
        proof_root / "proof_summary.json",
        {
            "acceptedBallFrames": len(accepted_frames),
            "acceptedFrameIds": accepted_frames,
        },
    )
    _write_json(
        proof_root / "ball_truth_layers.json",
        {
            "acceptedBall": {
                "rows": [{"Frame_ID": frame_id, "Entity_Type": "ball"} for frame_id in accepted_frames],
                "summary": {"frames": len(accepted_frames)},
            }
        },
    )
    _write_json(proof_root / "selected_cluster_delta.json", {"remainingTruthGateReasons": []})
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.069,
            "controlledRetentionRatio": 0.102,
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
    return {
        "selection_root": selection_root,
        "proof_root": proof_root,
        "retention_root": retention_root,
        "suite_root": suite_root,
        "output_root": output_root,
    }


def test_acceptance_fix_classifies_selected_frames_without_guessing_missing_trace(tmp_path):
    roots = _write_common_inputs(tmp_path)

    payload = run_promoted_v6_reviewed_positive_acceptance_fix.run_promoted_v6_reviewed_positive_acceptance_fix(
        output_root=roots["output_root"],
        selection_followthrough_root=roots["selection_root"],
        promoted_proof_root=roots["proof_root"],
        retention_delta_root=roots["retention_root"],
        suite_root=roots["suite_root"],
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "succeeded"
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveSelectedFrameCount"] == 5
    assert summary["reviewedPositiveAcceptedFrameCount"] == 0
    assert summary["dominantBlockerClass"] == "reviewed_positive_acceptance_artifact_gap"
    assert summary["nextCorrectiveFamily"] == "proof_acceptance_gate_trace_refresh"
    assert summary["weakEvidenceReasons"] == ["reviewed_positive_acceptance_gate_trace_missing"]

    matrix = json.loads(
        (roots["output_root"] / "reviewed_positive_acceptance_matrix.json").read_text()
    )
    assert [row["frameIndex"] for row in matrix["selectedReviewedPositiveFrames"]] == [
        250,
        255,
        260,
        265,
        270,
    ]
    assert {row["gapClass"] for row in matrix["selectedReviewedPositiveFrames"]} == {
        "reviewed_positive_acceptance_artifact_gap"
    }
    assert (roots["output_root"] / "reviewed_positive_acceptance_gate_taxonomy.json").exists()
    assert (roots["output_root"] / "reviewed_positive_accepted_funnel_audit.json").exists()
    assert (roots["output_root"] / "batch_outcome_analysis.md").exists()


def test_acceptance_fix_selects_profile_when_acceptance_gate_trace_is_dominant(tmp_path):
    roots = _write_common_inputs(
        tmp_path,
        acceptance_trace={
            "acceptedTruthLayerMatch": False,
            "acceptanceGateRejected": True,
            "continuityRejected": False,
            "repeatedAnchorRejected": False,
            "viabilityRejected": False,
        },
    )

    payload = run_promoted_v6_reviewed_positive_acceptance_fix.run_promoted_v6_reviewed_positive_acceptance_fix(
        output_root=roots["output_root"],
        selection_followthrough_root=roots["selection_root"],
        promoted_proof_root=roots["proof_root"],
        retention_delta_root=roots["retention_root"],
        suite_root=roots["suite_root"],
    )

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "reviewed_positive_selected_rejected_by_acceptance_gate"
    assert summary["dominantBlockerFrameCount"] == 5
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_acceptance_profile"
    assert summary["weakEvidenceReasons"] == []


def test_acceptance_fix_keeps_rejected_bootstrap_seeds_out_of_positive_counts(tmp_path):
    roots = _write_common_inputs(
        tmp_path,
        acceptance_trace={
            "acceptedTruthLayerMatch": False,
            "acceptanceGateRejected": False,
            "continuityRejected": False,
            "repeatedAnchorRejected": False,
            "viabilityRejected": True,
        },
        rejected_positive_count=74,
    )

    payload = run_promoted_v6_reviewed_positive_acceptance_fix.run_promoted_v6_reviewed_positive_acceptance_fix(
        output_root=roots["output_root"],
        selection_followthrough_root=roots["selection_root"],
        promoted_proof_root=roots["proof_root"],
        retention_delta_root=roots["retention_root"],
        suite_root=roots["suite_root"],
    )

    summary = payload["summary"]
    assert summary["reviewedPositiveSelectedFrameCount"] == 5
    assert summary["rejectedBootstrapSeedPositiveEvidenceCount"] == 74
    assert summary["dominantBlockerClass"] == "reviewed_positive_selected_rejected_by_viability"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_acceptance_profile"


def test_acceptance_fix_recognizes_already_accepted_frames_from_truth_layer(tmp_path):
    roots = _write_common_inputs(tmp_path, accepted_frames=[250, 255, 260, 265, 270])

    payload = run_promoted_v6_reviewed_positive_acceptance_fix.run_promoted_v6_reviewed_positive_acceptance_fix(
        output_root=roots["output_root"],
        selection_followthrough_root=roots["selection_root"],
        promoted_proof_root=roots["proof_root"],
        retention_delta_root=roots["retention_root"],
        suite_root=roots["suite_root"],
    )

    summary = payload["summary"]
    assert summary["reviewedPositiveAcceptedFrameCount"] == 5
    assert summary["dominantBlockerClass"] == "reviewed_positive_already_accepted"
    assert summary["nextCorrectiveFamily"] == "promote_touchline_detector_candidate"
