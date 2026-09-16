from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_candidate_proposal_generation_fix as candidate_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_row(frame_id: int) -> dict[str, object]:
    return {
        "candidateFrameId": f"seed-{frame_id}",
        "windowId": "w1",
        "frameId": frame_id,
        "decision": "accept_seed",
        "seedSource": "baseline_current_accepted_ball",
        "row": {"Frame_ID": frame_id, "X": 45.0, "Y": 45.0},
        "lineage": {
            "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
            "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        },
    }


def _candidate_frame(frame_id: int, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidateFrameId": f"seed-{frame_id}",
        "windowId": "w1",
        "sourceClipId": "trimed-5min.mp4",
        "frameId": frame_id,
        "proposalEvidenceAvailable": True,
        "promotedSignalSources": ["promoted_recovery_profile_proposal"],
        "lineageComplete": True,
    }
    payload.update(overrides)
    return payload


def _write_inputs(
    root: Path,
    *,
    frame_ids: list[int],
    candidate_overrides: dict[int, dict[str, object]] | None = None,
    proof_summary_overrides: dict[str, object] | None = None,
    recovery_profile_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    analysis_root = root / "analysis"
    support_blocker_root = root / "support_viability_admission_fix"
    gold_root = root / "gold_truth"
    validation_root = root / "validation"
    retention_root = root / "retention"
    suite_root = root / "suite"
    proof_root = root / "proof"

    _write_json(
        support_blocker_root / "blocker_summary.json",
        {
            "batchStatus": "exhausted",
            "nextCorrectiveFamily": "candidate_proposal_generation_fix",
            "attemptBudget": 3,
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
    overrides_by_frame = candidate_overrides or {}
    _write_json(
        gold_root / "candidate_frame_truth_manifest.json",
        {
            "candidateFrameCount": len(frame_ids),
            "representedBootstrapWindowCount": 5 if len(frame_ids) >= 5 else 1,
            "representedMissingAcceptedFrameCount": len(frame_ids),
            "candidateFrames": [
                _candidate_frame(frame_id, **overrides_by_frame.get(frame_id, {}))
                for frame_id in frame_ids
            ],
        },
    )
    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                {
                    "armName": "promoted_v6_baseline",
                    "runtimeOptions": {
                        "edgeShareRepairProfile": (
                            "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3"
                        ),
                        "proposalSelectionTruthSeedPath": str(
                            gold_root / "accepted_controlled_truth_seed.json"
                        ),
                    },
                }
            ]
        },
    )
    proof_summary = {
        "acceptedBallFrames": 0,
        "bestProposalCandidateFrames": 0,
        "bestProposalSelectedFrames": 0,
        "bestProposalDirectSeedContextWindowFrames": 0,
        "bestProposalDirectSeedZeroDetectFrames": 0,
        "bestProposalDirectSeedDetectedFrames": 0,
        "bestProposalDirectSeedPitchPolygonRejectedFrames": 0,
        "bestProposalDirectSeedCropEdgeRejectedFrames": 0,
        "bestProposalDirectSeedCropCenterYRejectedFrames": 0,
        "bestProposalDirectSeedScale1600RawDetectionFrames": 0,
        "bestProposalDirectSeedScale960RawDetectionFrames": 0,
        "bestProposalDirectSeedScale1920RawDetectionFrames": 0,
    }
    proof_summary.update(proof_summary_overrides or {})
    _write_json(proof_root / "proof_summary.json", proof_summary)
    _write_json(
        proof_root / "ball_truth_layers.json",
        {
            "acceptedBall": {"rows": []},
            "probeObservedBall": {"rawRows": []},
            "sourceConditionedAcquisitionDiagnostics": {
                "profileName": "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3",
                "supportViabilityAdmissionFixTruthSeedFrames": 0,
            },
        },
    )
    recovery_profile = {
        "selectedProfileName": None,
        "profiles": [
            {
                "name": "proposal_windows_075",
                "proposalCandidateFrames": 0,
                "selectedFrames": 0,
                "proposalDirectSeedContextWindowFrames": 0,
                "proposalDirectSeedZeroDetectFrames": 0,
                "proposalDirectSeedPitchPolygonRejectedFrames": 0,
            }
        ],
    }
    recovery_profile["profiles"][0].update(recovery_profile_overrides or {})
    _write_json(proof_root / "recovery_profile_matrix.json", recovery_profile)
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
    return {
        "analysis_root": analysis_root,
        "support_blocker_root": support_blocker_root,
        "gold_truth_root": gold_root,
        "validation_root": validation_root,
        "retention_root": retention_root,
        "suite_root": suite_root,
        "promoted_proof_root": proof_root,
    }


def test_candidate_proposal_generation_fix_classifies_per_frame_evidence(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        frame_ids=[100, 105, 110, 115, 120, 125],
        candidate_overrides={
            100: {"proposalAttempted": False, "proposalEvidenceAvailable": False},
            105: {"directSeedDetected": True, "pitchPolygonRejected": True},
            110: {"directSeedDetected": True, "cropGeometryRejected": True},
            115: {"nonDefaultScaleDetected": True, "directSeedDetected": False},
            120: {"proposalCandidateGenerated": True, "selectedInPromoted": False},
            125: {"proposalCandidateGenerated": True, "selectedInPromoted": True, "acceptedInPromoted": False},
        },
    )

    matrix = candidate_fix.build_seed_frame_proposal_generation_matrix(
        seed_payload=json.loads((paths["gold_truth_root"] / "accepted_controlled_truth_seed.json").read_text()),
        candidate_manifest=json.loads((paths["gold_truth_root"] / "candidate_frame_truth_manifest.json").read_text()),
        proof_summary={},
        ball_truth_layers={},
        recovery_profile_matrix={},
    )

    classes = [frame["gapClass"] for frame in matrix["frames"]]
    assert classes == [
        "no_proposal_attempt_for_seed_frame",
        "direct_seed_detected_but_pitch_polygon_rejected",
        "direct_seed_detected_but_crop_geometry_rejected",
        "multiscale_seed_detected_only_at_nondefault_scale",
        "proposal_candidate_generated_but_not_selected",
        "proposal_candidate_selected_but_not_accepted",
    ]


def test_candidate_proposal_generation_fix_uses_aggregate_proof_fallback(tmp_path: Path) -> None:
    frame_ids = list(range(200, 210))
    paths = _write_inputs(
        tmp_path,
        frame_ids=frame_ids,
        proof_summary_overrides={
            "bestProposalDirectSeedContextWindowFrames": 4,
            "bestProposalDirectSeedZeroDetectFrames": 4,
            "bestProposalCandidateFrames": 4,
            "bestProposalSelectedFrames": 0,
        },
    )

    payload = candidate_fix.run_promoted_v6_candidate_proposal_generation_fix(
        analysis_root=paths["analysis_root"],
        support_blocker_root=paths["support_blocker_root"],
        gold_truth_root=paths["gold_truth_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
        promoted_proof_root=paths["promoted_proof_root"],
    )

    counts = payload["gapTaxonomy"]["gapClassCounts"]
    assert counts["no_proposal_attempt_for_seed_frame"] == 6
    assert counts["probe_model_no_raw_detection"] == 4
    assert payload["summary"]["dominantBlockerClass"] == "no_proposal_attempt_for_seed_frame"
    assert payload["summary"]["nextCorrectiveFamily"] == "proposal_crop_geometry_fix"


def test_candidate_proposal_generation_fix_writes_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        frame_ids=list(range(300, 360)),
        proof_summary_overrides={
            "bestProposalDirectSeedContextWindowFrames": 60,
            "bestProposalDirectSeedZeroDetectFrames": 60,
        },
    )

    payload = candidate_fix.run_promoted_v6_candidate_proposal_generation_fix(
        analysis_root=paths["analysis_root"],
        support_blocker_root=paths["support_blocker_root"],
        gold_truth_root=paths["gold_truth_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
        promoted_proof_root=paths["promoted_proof_root"],
    )

    assert payload["summary"]["goalAchieved"] is True
    assert payload["summary"]["dominantBlockerClass"] == "probe_model_no_raw_detection"
    assert payload["summary"]["nextCorrectiveFamily"] == "probe_model_generation_fix"
    for filename in (
        "candidate_proposal_generation_summary.json",
        "seed_frame_proposal_generation_matrix.json",
        "proposal_generation_gap_taxonomy.json",
        "seed_crop_failure_audit.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["analysis_root"] / filename).exists()


def test_candidate_proposal_generation_fix_marks_weak_evidence_honestly(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=[400, 405])

    payload = candidate_fix.run_promoted_v6_candidate_proposal_generation_fix(
        analysis_root=paths["analysis_root"],
        support_blocker_root=paths["support_blocker_root"],
        gold_truth_root=paths["gold_truth_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
        promoted_proof_root=paths["promoted_proof_root"],
    )

    assert payload["summary"]["goalAchieved"] is False
    assert payload["summary"]["dominantBlockerClass"] == "weak_or_insufficient_generation_evidence"
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_required"
    assert payload["summary"]["weakEvidenceReasons"] == [
        "classified_seed_frame_count_below_5",
        "no_dominant_generation_gap_above_half",
    ]
