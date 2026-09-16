from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_gold_truth_bootstrap as gold_bootstrap


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ball_row(frame_id: int, *, x: float = 36.8, y: float = 96.8) -> dict[str, object]:
    return {
        "Frame_ID": frame_id,
        "Timestamp": frame_id / 25.0,
        "Entity_Type": "ball",
        "Track_ID": -1,
        "X": x,
        "Y": y,
        "Conf": 0.5,
        "Source_X1": 100.0,
        "Source_Y1": 200.0,
        "Source_X2": 112.0,
        "Source_Y2": 214.0,
    }


def _bootstrap_window(window_id: str, start_frame: int, count: int) -> dict[str, object]:
    frame_ids = [start_frame + (index * 5) for index in range(count)]
    return {
        "windowId": window_id,
        "sourceClipId": "trimed-5min.mp4",
        "startFrame": frame_ids[0],
        "endFrame": frame_ids[-1],
        "paddedStartFrame": max(0, frame_ids[0] - 10),
        "paddedEndFrame": frame_ids[-1] + 10,
        "frameCount": count,
        "frameIds": frame_ids,
        "sampleInterval": 5,
        "proofReferences": {
            "baselineCurrent": {
                "proofRoot": "/baseline",
                "ballTruthLayersPath": "/baseline/ball_truth_layers.json",
                "selectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
            },
            "promotedV6Baseline": {
                "proofRoot": "/promoted",
                "ballTruthLayersPath": "/promoted/ball_truth_layers.json",
                "selectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
            },
        },
    }


def _write_bootstrap_inputs(
    root: Path,
    *,
    windows: list[dict[str, object]],
    proposal_candidate_frames: int = 80,
) -> dict[str, Path]:
    plan_path = root / "suite" / "gold_truth_bootstrap_plan.json"
    baseline_root = root / "baseline"
    promoted_root = root / "promoted"
    validation_root = root / "validation"
    retention_root = root / "retention"
    source_manifest_path = root / "source_manifest.json"

    all_frame_ids = [
        frame_id
        for window in windows
        for frame_id in window["frameIds"]
    ]
    _write_json(
        plan_path,
        {
            "analysisBatchName": "promoted_v6_source_manifest_and_gold_truth_refresh_v1",
            "selectedWindowCount": len(windows),
            "selectedMissingAcceptedFrameCount": len(all_frame_ids),
            "bootstrapWindows": windows,
        },
    )
    _write_json(
        baseline_root / "ball_truth_layers.json",
        {"sampleInterval": 5, "acceptedBall": {"rows": [_ball_row(frame_id) for frame_id in all_frame_ids]}},
    )
    _write_json(
        baseline_root / "selected_cluster_delta.json",
        {"after": {"controlledPossessionFrames": len(all_frame_ids), "supportedAcceptedBallFrames": len(all_frame_ids)}},
    )
    _write_json(
        promoted_root / "ball_truth_layers.json",
        {"sampleInterval": 5, "acceptedBall": {"rows": []}, "observedBall": {"rows": []}, "probeObservedBall": {"rawRows": []}},
    )
    _write_json(promoted_root / "selected_cluster_delta.json", {"after": {"acceptedBallFrames": 0}})
    _write_json(
        promoted_root / "recovery_profile_matrix.json",
        {"profiles": [{"name": "proposal_windows_075", "proposalCandidateFrames": proposal_candidate_frames, "selectedFrames": 0}]},
    )
    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                {
                    "armName": "baseline_current",
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "selectedClusterDeltaPath": str(baseline_root / "selected_cluster_delta.json")
                            },
                        }
                    ],
                },
                {
                    "armName": "promoted_v6_baseline",
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "selectedClusterDeltaPath": str(promoted_root / "selected_cluster_delta.json")
                            },
                        }
                    ],
                },
            ]
        },
    )
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.069})
    _write_json(source_manifest_path, {"entries": [{"clipId": "trimed-5min.mp4", "localPath": "/video.mp4"}]})
    return {
        "plan": plan_path,
        "analysis_root": root / "analysis",
        "validation_root": validation_root,
        "retention_root": retention_root,
        "source_manifest": source_manifest_path,
    }


def test_build_candidate_manifest_seeds_baseline_accepted_frames_with_lineage() -> None:
    windows = [_bootstrap_window("w1", 100, 3)]
    baseline_truth = {"acceptedBall": {"rows": [_ball_row(100), _ball_row(105), _ball_row(110)]}}
    promoted_truth = {"acceptedBall": {"rows": []}, "observedBall": {"rows": []}}
    recovery_matrix = {"profiles": [{"name": "proposal_windows_075", "proposalCandidateFrames": 4, "selectedFrames": 0}]}

    manifest = gold_bootstrap.build_candidate_frame_truth_manifest(
        bootstrap_plan={"bootstrapWindows": windows},
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
        baseline_selected_cluster_delta={"after": {"controlledPossessionFrames": 3}},
        recovery_profile_matrix=recovery_matrix,
        proof_references={"baselineCurrent": {"proofRoot": "/baseline"}, "promotedV6Baseline": {"proofRoot": "/promoted"}},
    )

    assert manifest["representedBootstrapWindowCount"] == 1
    assert manifest["representedMissingAcceptedFrameCount"] == 3
    assert manifest["proposalEvidenceScope"] == "recovery_profile_matrix_global"
    assert {frame["acceptedSeedDecision"] for frame in manifest["candidateFrames"]} == {"accept_seed"}
    assert all(frame["lineageComplete"] for frame in manifest["candidateFrames"])


def test_quality_gate_passes_with_five_windows_and_fifty_seeded_frames() -> None:
    candidate_manifest = {
        "representedBootstrapWindowCount": 5,
        "representedMissingAcceptedFrameCount": 50,
        "candidateFrames": [{"lineageComplete": True} for _ in range(50)],
    }
    overlay = {"reviewItemCount": 50, "pendingReviewCount": 0}

    gate = gold_bootstrap.evaluate_bootstrap_quality(
        candidate_manifest=candidate_manifest,
        reviewed_label_overlay=overlay,
    )

    assert gate["goalAchieved"] is True
    assert gate["roadmapAdvanceAllowed"] is True
    assert gate["successfulApproach"] == "A_direct_saved_artifact_seed"
    assert gate["weakEvidenceReasons"] == []


def test_quality_gate_falls_back_to_overlay_when_direct_seed_is_weak() -> None:
    candidate_manifest = {
        "representedBootstrapWindowCount": 2,
        "representedMissingAcceptedFrameCount": 10,
        "candidateFrames": [{"lineageComplete": True} for _ in range(10)],
    }
    overlay = {"reviewItemCount": 55, "pendingReviewCount": 55}

    gate = gold_bootstrap.evaluate_bootstrap_quality(
        candidate_manifest=candidate_manifest,
        reviewed_label_overlay=overlay,
    )

    assert gate["goalAchieved"] is True
    assert gate["successfulApproach"] == "B_review_overlay_fallback"
    assert gate["weakEvidenceReasons"] == []


def test_quality_gate_fails_honestly_when_seed_and_overlay_are_weak() -> None:
    candidate_manifest = {
        "representedBootstrapWindowCount": 1,
        "representedMissingAcceptedFrameCount": 4,
        "candidateFrames": [{"lineageComplete": False} for _ in range(4)],
    }
    overlay = {"reviewItemCount": 4, "pendingReviewCount": 4}

    gate = gold_bootstrap.evaluate_bootstrap_quality(
        candidate_manifest=candidate_manifest,
        reviewed_label_overlay=overlay,
    )

    assert gate["goalAchieved"] is False
    assert gate["roadmapAdvanceAllowed"] is False
    assert gate["successfulApproach"] == "C_evidence_only_blocker"
    assert gate["weakEvidenceReasons"] == [
        "bootstrap_window_count_below_5",
        "represented_missing_accepted_frames_below_50",
        "frame_lineage_incomplete",
        "review_overlay_coverage_below_50",
    ]


def test_next_corrective_family_prefers_proposal_selection_admission_for_strong_seed() -> None:
    recommendation = gold_bootstrap.select_next_corrective_family(
        quality_gate={"goalAchieved": True, "successfulApproach": "A_direct_saved_artifact_seed"},
        candidate_manifest={"proposalEvidenceAvailable": True},
        reviewed_label_overlay={"pendingReviewCount": 0, "reviewedPositiveCount": 50, "reviewedNegativeCount": 0},
    )

    assert recommendation["nextCorrectiveFamily"] == "proposal_selection_admission_fix"


def test_run_gold_truth_bootstrap_writes_artifacts_and_keeps_source_manifest_unchanged(tmp_path: Path) -> None:
    windows = [
        _bootstrap_window("w1", 100, 10),
        _bootstrap_window("w2", 200, 10),
        _bootstrap_window("w3", 300, 10),
        _bootstrap_window("w4", 400, 10),
        _bootstrap_window("w5", 500, 10),
    ]
    paths = _write_bootstrap_inputs(tmp_path, windows=windows)
    original_source_manifest = paths["source_manifest"].read_text(encoding="utf-8")

    payload = gold_bootstrap.run_promoted_v6_gold_truth_bootstrap(
        analysis_root=paths["analysis_root"],
        bootstrap_plan_path=paths["plan"],
        validation_root=paths["validation_root"],
        retention_delta_root=paths["retention_root"],
        source_manifest_path=paths["source_manifest"],
    )

    assert paths["source_manifest"].read_text(encoding="utf-8") == original_source_manifest
    assert payload["summary"]["goalAchieved"] is True
    assert payload["summary"]["successfulApproach"] == "A_direct_saved_artifact_seed"
    assert payload["summary"]["nextCorrectiveFamily"] == "proposal_selection_admission_fix"
    for filename in (
        "gold_truth_bootstrap_summary.json",
        "candidate_frame_truth_manifest.json",
        "accepted_controlled_truth_seed.json",
        "reviewed_label_overlay.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["analysis_root"] / "gold_truth_bootstrap_attempt_v1" / filename).exists()
