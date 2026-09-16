from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_support_viability_truth_fix as support_fix


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
        "acceptedSeedDecision": "accept_seed",
        "lineageComplete": True,
        "lineage": {
            "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
            "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        },
    }
    payload.update(overrides)
    return payload


def _write_inputs(
    root: Path,
    *,
    frame_count: int = 60,
    arm_seed_path: str | None = None,
    candidate_overrides: dict[int, dict[str, object]] | None = None,
) -> dict[str, Path]:
    proposal_root = root / "proposal_selection_admission_fix"
    gold_root = root / "gold_truth"
    validation_root = root / "validation"
    retention_root = root / "retention"
    suite_root = root / "suite"
    seed_path = gold_root / "accepted_controlled_truth_seed.json"

    frame_ids = list(range(100, 100 + frame_count))
    _write_json(
        proposal_root / "blocker_summary.json",
        {
            "batchStatus": "exhausted",
            "nextCorrectiveFamily": "support_viability_truth_fix",
            "attempts": [
                {"attemptNumber": 3, "approachFamily": "segment_level_seed_continuity", "result": "failed"}
            ],
        },
    )
    _write_json(
        seed_path,
        {
            "acceptedSeedRowCount": len(frame_ids),
            "acceptedBallSeedRows": [_seed_row(frame_id) for frame_id in frame_ids],
            "controlledPossessionCandidateRows": [],
        },
    )
    overrides_by_frame = candidate_overrides or {}
    _write_json(
        gold_root / "candidate_frame_truth_manifest.json",
        {
            "candidateFrameCount": len(frame_ids),
            "representedBootstrapWindowCount": 5 if frame_count >= 50 else 1,
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
                            "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v3"
                        ),
                        "proposalSelectionTruthSeedPath": arm_seed_path or str(seed_path),
                    },
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {"proofSummaryPath": "/proof/proof_summary.json"},
                        }
                    ],
                }
            ]
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
        {"suiteVerdict": "baseline_not_robust", "activeLane": "promote_touchline_detector_candidate"},
    )
    return {
        "analysis_root": root / "analysis",
        "proposal_root": proposal_root,
        "gold_root": gold_root,
        "validation_root": validation_root,
        "retention_root": retention_root,
        "suite_root": suite_root,
        "seed_path": seed_path,
    }


def test_support_viability_truth_fix_classifies_seed_frames_deterministically(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_count=60)

    payload = support_fix.run_promoted_v6_support_viability_truth_fix(
        analysis_root=paths["analysis_root"],
        proposal_blocker_root=paths["proposal_root"],
        gold_truth_root=paths["gold_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
    )

    assert payload["summary"]["goalAchieved"] is True
    assert payload["summary"]["dominantBlockerClass"] == "support_viability_evidence_gap"
    assert payload["summary"]["nextCorrectiveFamily"] == "support_viability_admission_fix"
    assert payload["summary"]["classifiedSeedFrameCount"] == 60
    assert payload["proofRuntimeSeedPathAudit"]["auditStatus"] == "passed"
    assert payload["gapTaxonomy"]["dominantGapClass"] == "support_viability_evidence_gap"
    assert len(payload["seedFrameSupportViabilityMatrix"]["frames"]) == 60
    for filename in (
        "support_viability_truth_summary.json",
        "seed_frame_support_viability_matrix.json",
        "support_viability_gap_taxonomy.json",
        "proof_runtime_seed_path_audit.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["analysis_root"] / filename).exists()


def test_support_viability_truth_fix_detects_stale_proof_runtime_seed_path(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_count=60, arm_seed_path="/stale/accepted_controlled_truth_seed.json")

    payload = support_fix.run_promoted_v6_support_viability_truth_fix(
        analysis_root=paths["analysis_root"],
        proposal_blocker_root=paths["proposal_root"],
        gold_truth_root=paths["gold_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
    )

    assert payload["summary"]["goalAchieved"] is True
    assert payload["summary"]["dominantBlockerClass"] == "proof_runtime_seed_path_mismatch"
    assert payload["summary"]["nextCorrectiveFamily"] == "proof_runtime_plumbing_fix"
    assert payload["proofRuntimeSeedPathAudit"]["auditStatus"] == "failed"


def test_support_viability_truth_fix_marks_weak_evidence_honestly(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_count=2)

    payload = support_fix.run_promoted_v6_support_viability_truth_fix(
        analysis_root=paths["analysis_root"],
        proposal_blocker_root=paths["proposal_root"],
        gold_truth_root=paths["gold_root"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        suite_root=paths["suite_root"],
    )

    assert payload["summary"]["goalAchieved"] is False
    assert payload["summary"]["dominantBlockerClass"] == "weak_or_insufficient_evidence"
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_required"
    assert payload["summary"]["weakEvidenceReasons"] == [
        "classified_seed_frame_count_below_50",
        "represented_bootstrap_window_count_below_5",
    ]
