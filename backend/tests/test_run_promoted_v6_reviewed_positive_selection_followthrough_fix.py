import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_selection_followthrough_fix


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _coverage_payload(*, include_proof_fields: bool = True) -> dict:
    frames = []
    for frame_id in [250, 255, 260, 265, 270]:
        proof_evidence = {"frameIndex": frame_id, "collapsed": True}
        if include_proof_fields:
            proof_evidence.update(
                {
                    "proposalGenerated": True,
                    "rawDetected": True,
                    "selected": False,
                    "accepted": False,
                    "proposalWindowKinds": ["reviewed_positive_audit_context_8"],
                }
            )
        frames.append(
            {
                "frameIndex": frame_id,
                "reviewItemId": f"review-{frame_id}",
                "candidateFrameId": f"manual-review-expansion-{frame_id}",
                "windowId": "trimed-5min.mp4-manual-review-expansion-0240-0320",
                "sourceClipId": "trimed-5min.mp4",
                "reviewedBBox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                "diagnosticClass": "reviewed_positive_collapsed_not_selected",
                "rawDetected": True,
                "candidateGenerated": True,
                "collapsed": True,
                "selected": False,
                "accepted": False,
                "proofEvidence": proof_evidence,
            }
        )
    return {
        "reviewedPositiveFrameCount": 17,
        "reviewedPositiveProposalEvidenceFrameCount": 5,
        "reviewedPositiveCollapsedFrameCount": 5,
        "reviewedPositiveSelectedFrameCount": 0,
        "reviewedPositiveAcceptedFrameCount": 0,
        "reviewedPositiveFrames": frames,
        "refutedSeeds": [{"frameIndex": 245, "decision": "reject_seed"}],
    }


def _write_common_inputs(tmp_path: Path, *, include_proof_fields: bool = True) -> dict[str, Path]:
    crop_root = tmp_path / "reviewed_positive_crop_geometry_scale_fix_v1"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"
    output_root = tmp_path / "reviewed_positive_selection_followthrough_fix_v1"

    _write_json(crop_root / "reviewed_positive_crop_geometry_scale_coverage.json", _coverage_payload(include_proof_fields=include_proof_fields))
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "proposal_windows_075",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalCollapsedFrames": 5,
                    "selectedFrames": 0,
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": frame_id,
                            "proposalGenerated": True,
                            "rawDetected": True,
                            "collapsed": True,
                            "selected": False,
                            "accepted": False,
                            "proposalWindowKinds": ["reviewed_positive_audit_context_8"],
                        }
                        for frame_id in [250, 255, 260, 265, 270]
                    ]
                    if include_proof_fields
                    else [],
                }
            ],
        },
    )
    _write_json(
        proof_root / "proof_summary.json",
        {
            "acceptedBallFrames": 7,
            "bestProposalRawDetectedFrames": 8,
            "bestProposalAfterSeedCollapseFrames": 8,
            "bestProposalSelectedFrames": 0,
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
        "crop_root": crop_root,
        "proof_root": proof_root,
        "retention_root": retention_root,
        "suite_root": suite_root,
        "output_root": output_root,
    }


def _mark_reviewed_positive_frames_selected(roots: dict[str, Path]) -> None:
    matrix_path = roots["proof_root"] / "recovery_profile_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    profile = matrix["profiles"][0]
    profile["selectedFrames"] = 5
    profile["selectedRows"] = [
        {
            "Frame_ID": frame_id,
            "Entity_Type": "ball",
            "ProposalWindowKind": "reviewed_positive_audit_context_8",
        }
        for frame_id in [250, 255, 260, 265, 270]
    ]
    for row in profile["proposalFrameDiagnostics"]:
        row["selected"] = True
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")


def _add_selection_gate_trace(
    roots: dict[str, Path],
    *,
    rejected_by: str | None,
) -> None:
    matrix_path = roots["proof_root"] / "recovery_profile_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    for row in matrix["profiles"][0]["proposalFrameDiagnostics"]:
        trace = {
            "reviewedPositiveLineageMatch": True,
            "syntheticRowRejected": False,
            "repeatedAnchorRejected": False,
            "continuityRejected": False,
            "segmentLengthRejected": False,
            "edgeShareRejected": False,
            "selectedProfileRankingRejected": False,
            "edgeShareForSegment": 0.0,
            "segmentFrameCount": 5,
        }
        if rejected_by is not None:
            trace[rejected_by] = True
        if rejected_by == "edgeShareRejected":
            trace["edgeShareForSegment"] = 1.0
        row["selectionGateTrace"] = trace
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")


def test_reviewed_positive_selection_followthrough_diagnosis_selects_segment_profile(tmp_path):
    roots = _write_common_inputs(tmp_path)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "succeeded"
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveCollapsedFrameCount"] == 5
    assert summary["classifiedCollapsedFrameCount"] == 5
    assert summary["dominantBlockerClass"] == "reviewed_positive_segment_selection_zero"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_selected_segment_profile"
    assert summary["rejectedBootstrapSeedPositiveEvidenceCount"] == 0
    assert summary["runtimeDefaultChanged"] is False
    assert summary["sourceManifestMutationPolicy"] == "not_mutated"

    matrix = json.loads(
        (roots["output_root"] / "reviewed_positive_selection_followthrough_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert [row["frameIndex"] for row in matrix["collapsedReviewedPositiveFrames"]] == [
        250,
        255,
        260,
        265,
        270,
    ]
    assert {row["gapClass"] for row in matrix["collapsedReviewedPositiveFrames"]} == {
        "reviewed_positive_segment_selection_zero"
    }
    assert (roots["output_root"] / "reviewed_positive_selection_gate_taxonomy.json").exists()
    assert (roots["output_root"] / "reviewed_positive_selected_funnel_audit.json").exists()
    assert (roots["output_root"] / "decision_matrix.json").exists()
    assert (roots["output_root"] / "batch_outcome_analysis.md").exists()


def test_reviewed_positive_selection_followthrough_marks_missing_diagnostics(tmp_path):
    roots = _write_common_inputs(tmp_path, include_proof_fields=False)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
        )
    )

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["dominantBlockerClass"] == "reviewed_positive_selection_evidence_gap"
    assert summary["nextCorrectiveFamily"] == "proof_diagnostic_instrumentation_refresh"
    assert summary["weakEvidenceReasons"] == [
        "reviewed_positive_selected_followthrough_rejection_fields_missing"
    ]


def test_reviewed_positive_selection_followthrough_attempt_two_selects_acceptance_fix_when_selected_frames_exist(tmp_path):
    roots = _write_common_inputs(tmp_path)
    _mark_reviewed_positive_frames_selected(roots)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=2,
            attempt_approach_family="reviewed_positive_selected_segment_profile",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "succeeded"
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveSelectedFrameCount"] == 5
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_acceptance_fix"
    assert payload["decisionMatrix"]["rationale"] == (
        "Reviewed-positive rows now reach selected-frame follow-through; move to acceptance diagnostics next."
    )


def test_reviewed_positive_selection_followthrough_attempt_two_advances_to_blocker_when_selection_still_zero(tmp_path):
    roots = _write_common_inputs(tmp_path)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=2,
            attempt_approach_family="reviewed_positive_selected_segment_profile",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "needs_next_attempt"
    assert summary["goalAchieved"] is False
    assert summary["reviewedPositiveSelectedFrameCount"] == 0
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_selection_blocker_summary"
    assert summary["weakEvidenceReasons"] == [
        "reviewed_positive_selected_segment_profile_selected_zero_frames"
    ]


def test_reviewed_positive_edge_share_override_selects_acceptance_fix_when_selected_frames_exist(tmp_path):
    roots = _write_common_inputs(tmp_path)
    _mark_reviewed_positive_frames_selected(roots)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=1,
            attempt_approach_family="reviewed_positive_edge_share_override",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "succeeded"
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveSelectedFrameCount"] == 5
    assert summary["reviewedPositiveAcceptedFrameCount"] == 0
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_acceptance_fix"
    assert payload["decisionMatrix"]["rationale"] == (
        "Reviewed-positive edge-share override moved rows into selected-frame follow-through; "
        "move to acceptance diagnostics next."
    )


def test_reviewed_positive_edge_share_override_advances_to_acceptance_trace_when_selection_still_zero(tmp_path):
    roots = _write_common_inputs(tmp_path)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=1,
            attempt_approach_family="reviewed_positive_edge_share_override",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "needs_next_attempt"
    assert summary["goalAchieved"] is False
    assert summary["reviewedPositiveSelectedFrameCount"] == 0
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_edge_share_plus_acceptance_trace"
    assert summary["weakEvidenceReasons"] == [
        "reviewed_positive_edge_share_override_selected_zero_frames"
    ]


def test_reviewed_positive_selection_blocker_summary_selects_edge_override_from_trace(tmp_path):
    roots = _write_common_inputs(tmp_path)
    _add_selection_gate_trace(roots, rejected_by="edgeShareRejected")

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=3,
            attempt_approach_family="reviewed_positive_selection_blocker_summary",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "exhausted"
    assert summary["goalAchieved"] is False
    assert summary["roadmapAdvanceAllowed"] is True
    assert summary["dominantBlockerClass"] == "reviewed_positive_edge_share_gate_rejection"
    assert summary["dominantBlockerFrameCount"] == 5
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_edge_share_gate_override"
    assert summary["weakEvidenceReasons"] == []

    trace = json.loads((roots["output_root"] / "reviewed_positive_selection_gate_trace.json").read_text())
    assert [row["frameIndex"] for row in trace["frameGateTrace"]] == [250, 255, 260, 265, 270]
    assert {row["dominantGateClass"] for row in trace["frameGateTrace"]} == {
        "reviewed_positive_edge_share_gate_rejection"
    }
    assert (roots["output_root"] / "reviewed_positive_selection_blocker_classification.json").exists()
    assert (roots["output_root"] / "blocker_summary.json").exists()


def test_reviewed_positive_selection_blocker_summary_does_not_guess_when_trace_missing(tmp_path):
    roots = _write_common_inputs(tmp_path)

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=3,
            attempt_approach_family="reviewed_positive_selection_blocker_summary",
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "exhausted"
    assert summary["goalAchieved"] is False
    assert summary["dominantBlockerClass"] == "reviewed_positive_selection_artifact_coverage_gap"
    assert summary["nextCorrectiveFamily"] == "proof_selection_gate_trace_refresh"
    assert summary["weakEvidenceReasons"] == ["reviewed_positive_selection_gate_trace_missing"]


def test_reviewed_positive_selection_blocker_summary_selects_continuity_fix_from_trace(tmp_path):
    roots = _write_common_inputs(tmp_path)
    _add_selection_gate_trace(roots, rejected_by="continuityRejected")

    payload = (
        run_promoted_v6_reviewed_positive_selection_followthrough_fix
        .run_promoted_v6_reviewed_positive_selection_followthrough_fix(
            output_root=roots["output_root"],
            crop_geometry_root=roots["crop_root"],
            promoted_proof_root=roots["proof_root"],
            retention_delta_root=roots["retention_root"],
            suite_root=roots["suite_root"],
            attempt_number=3,
            attempt_approach_family="reviewed_positive_selection_blocker_summary",
        )
    )

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "reviewed_positive_continuity_gate_rejection"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_continuity_followthrough_fix"
