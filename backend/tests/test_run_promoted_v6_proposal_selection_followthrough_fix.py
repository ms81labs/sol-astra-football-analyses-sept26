from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_proposal_selection_followthrough_fix as followthrough_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_row(frame_id: int) -> dict[str, object]:
    return {
        "candidateFrameId": f"seed-{frame_id}",
        "windowId": "w1",
        "frameId": frame_id,
        "row": {"Frame_ID": frame_id, "X": 45.0, "Y": 45.0},
        "lineage": {"baseline": "baseline/ball_truth_layers.json", "promoted": "promoted/ball_truth_layers.json"},
    }


def _write_inputs(
    root: Path,
    *,
    frame_ids: list[int],
    profile_overrides: dict[str, object] | None = None,
    proof_overrides: dict[str, object] | None = None,
    selected_delta_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    analysis_root = root / "analysis"
    crop_blocker_root = root / "proposal_crop_geometry_fix"
    gold_root = root / "gold_truth"
    validation_root = root / "validation"
    retention_root = root / "retention"
    suite_root = root / "suite"
    proof_root = root / "proof"

    _write_json(
        crop_blocker_root / "blocker_summary.json",
        {
            "batchStatus": "exhausted",
            "nextCorrectiveFamily": "proposal_selection_followthrough_fix",
            "dominantBlockerClass": "proposal_selection_followthrough_gap",
            "proposalDiagnostics": {
                "proposalCandidateFrames": 110,
                "proposalRawDetectedFrames": 93,
                "proposalCollapsedFrames": 93,
                "selectedFrames": 0,
            },
        },
    )
    _write_json(
        gold_root / "accepted_controlled_truth_seed.json",
        {
            "acceptedSeedRowCount": len(frame_ids),
            "acceptedBallSeedRows": [_seed_row(frame_id) for frame_id in frame_ids],
            "controlledPossessionCandidateRows": [],
            "truthStatus": "bootstrap_seed_not_manual_gold",
        },
    )
    _write_json(
        gold_root / "candidate_frame_truth_manifest.json",
        {
            "candidateFrameCount": len(frame_ids),
            "representedBootstrapWindowCount": 5 if len(frame_ids) >= 5 else 1,
            "representedMissingAcceptedFrameCount": len(frame_ids),
            "candidateFrames": [
                {
                    "candidateFrameId": f"seed-{frame_id}",
                    "frameId": frame_id,
                    "windowId": "w1",
                    "lineageComplete": True,
                }
                for frame_id in frame_ids
            ],
        },
    )
    _write_json(
        validation_root / "batch_outcome_analysis.json",
        {
            "winningPassedPromotionGate": False,
            "winningPromotionBlockers": [
                "accepted_retention_below_guardrail",
                "controlled_retention_below_guardrail",
            ],
            "runtimeDefaultChanged": False,
        },
    )
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
            "sourceRobustnessRecommendedNextLever": "promote_touchline_detector_candidate",
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    proof_summary = {
        "acceptedBallFrames": 7,
        "bestProposalCandidateFrames": 110,
        "bestProposalRawDetectedFrames": 93,
        "bestProposalAfterSeedCollapseFrames": 93,
        "bestProposalAfterFalseBallSuppressionFrames": 93,
        "bestProposalSelectedFrames": 0,
        "collapsedCandidateFrames": 0,
    }
    proof_summary.update(proof_overrides or {})
    _write_json(proof_root / "proof_summary.json", proof_summary)
    selected_delta = {
        "selectedClusterId": 0,
        "remainingTruthGateReasons": [
            "Accepted ball layer is still too sparse for truthful 5-10 minute analysis",
            "Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis",
        ],
    }
    selected_delta.update(selected_delta_overrides or {})
    _write_json(proof_root / "selected_cluster_delta.json", selected_delta)
    profile = {
        "name": "proposal_windows_075",
        "proposalCandidateFrames": 110,
        "proposalWindowCount": 440,
        "proposalRawDetectedFrames": 93,
        "proposalAfterSeedCollapseFrames": 93,
        "proposalAfterFalseBallSuppressionFrames": 93,
        "proposalCollapsedFrames": 93,
        "candidateFrames": 93,
        "selectedFrames": 0,
        "selectedSegmentCount": 0,
        "viable": False,
        "proposalSupportViabilityAdmissionFixAcceptedFrames": 0,
        "proposalSupportViabilityAdmissionFixRejectedCounts": {},
    }
    profile.update(profile_overrides or {})
    _write_json(proof_root / "recovery_profile_matrix.json", {"selectedProfileName": None, "profiles": [profile]})

    return {
        "analysis_root": analysis_root,
        "crop_blocker_root": crop_blocker_root,
        "gold_truth_root": gold_root,
        "validation_root": validation_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "promoted_proof_root": proof_root,
    }


def test_followthrough_fix_classifies_collapsed_candidates_with_zero_selected_frames(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=list(range(100, 178)))

    payload = followthrough_fix.run_promoted_v6_proposal_selection_followthrough_fix(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["dominantBlockerClass"] == "candidate_rows_collapsed_but_segment_selection_zero"
    assert summary["nextCorrectiveFamily"] == "selection_segment_viability_fix"
    assert summary["classifiedSeedFrameCount"] == 78
    assert summary["proposalDiagnostics"]["proposalRawDetectedFrames"] == 93
    assert summary["proposalDiagnostics"]["selectedFrames"] == 0


def test_followthrough_fix_detects_profile_ranking_discard(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        frame_ids=list(range(200, 260)),
        profile_overrides={"selectedFrames": 12, "selectedSegmentCount": 2, "viable": True},
    )
    _write_json(
        paths["promoted_proof_root"] / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "baseline_player_window",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalCandidateFrames": 110,
                    "proposalCollapsedFrames": 93,
                    "selectedFrames": 12,
                    "selectedSegmentCount": 2,
                    "viable": True,
                },
                {
                    "name": "baseline_player_window",
                    "proposalCandidateFrames": 0,
                    "proposalCollapsedFrames": 0,
                    "selectedFrames": 0,
                    "selectedSegmentCount": 0,
                    "viable": False,
                },
            ],
        },
    )

    payload = followthrough_fix.run_promoted_v6_proposal_selection_followthrough_fix(**paths)

    assert payload["summary"]["dominantBlockerClass"] == "profile_ranking_discarded_candidate_profile"
    assert payload["summary"]["nextCorrectiveFamily"] == "selected_profile_ranking_fix"


def test_followthrough_fix_writes_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=list(range(300, 378)))

    payload = followthrough_fix.run_promoted_v6_proposal_selection_followthrough_fix(**paths)

    assert payload["summary"]["goalAchieved"] is True
    for filename in (
        "proposal_selection_followthrough_summary.json",
        "proposal_selection_followthrough_matrix.json",
        "selected_frame_gap_taxonomy.json",
        "profile_selection_funnel_audit.json",
        "manual_review_followthrough_overlay.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["analysis_root"] / filename).exists()


def test_followthrough_fix_marks_weak_evidence_honestly(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        frame_ids=[400, 405],
        profile_overrides={
            "proposalCandidateFrames": 0,
            "proposalRawDetectedFrames": 0,
            "proposalCollapsedFrames": 0,
            "candidateFrames": 0,
            "selectedFrames": 0,
        },
        proof_overrides={
            "bestProposalCandidateFrames": 0,
            "bestProposalRawDetectedFrames": 0,
            "bestProposalSelectedFrames": 0,
        },
    )
    _write_json(
        paths["crop_blocker_root"] / "blocker_summary.json",
        {
            "batchStatus": "exhausted",
            "nextCorrectiveFamily": "proposal_selection_followthrough_fix",
            "dominantBlockerClass": "proposal_selection_followthrough_gap",
            "proposalDiagnostics": {
                "proposalCandidateFrames": 0,
                "proposalRawDetectedFrames": 0,
                "proposalCollapsedFrames": 0,
                "selectedFrames": 0,
            },
        },
    )

    payload = followthrough_fix.run_promoted_v6_proposal_selection_followthrough_fix(**paths)

    assert payload["summary"]["goalAchieved"] is False
    assert payload["summary"]["dominantBlockerClass"] == "weak_or_insufficient_followthrough_evidence"
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_required"


def test_followthrough_fix_attempt_three_writes_exhausted_blocker_summary(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=list(range(500, 578)))

    payload = followthrough_fix.run_promoted_v6_proposal_selection_followthrough_fix(
        **paths,
        attempt_number=3,
        attempt_approach_family="profile_ranking_or_manual_review_fallback",
    )

    summary = payload["summary"]
    assert summary["goalAchieved"] is False
    assert summary["batchStatus"] == "exhausted"
    assert summary["dominantBlockerClass"] == "candidate_rows_collapsed_but_segment_selection_zero"
    assert summary["nextCorrectiveFamily"] == "manual_review_required"
    assert "no_selected_frames_available_for_profile_ranking_fix" in summary["weakEvidenceReasons"]
    assert (paths["analysis_root"] / "blocker_summary.json").exists()
    overlay = json.loads((paths["analysis_root"] / "manual_review_followthrough_overlay.json").read_text())
    assert overlay["reviewItemCount"] == 78
