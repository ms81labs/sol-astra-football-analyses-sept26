from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_global_reachable_acceptance_probe


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_global_reachable_probe_selects_profile_for_ranking_rejected_frames(tmp_path: Path) -> None:
    output_root = tmp_path / "global_reachable_acceptance_probe_v1"
    gap_root = tmp_path / "gap"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"

    _write_json(
        gap_root / "accepted_gap_frame_manifest.json",
        {
            "frames": [
                {"frameIndex": frame_id, "gapClass": "baseline_accepted_collapsed_not_selected"}
                for frame_id in [255, 260]
            ]
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "proposal_windows_075",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalFrameDiagnostics": [
                        {
                            "frameIndex": frame_id,
                            "proposalGenerated": True,
                            "rawDetected": True,
                            "collapsed": True,
                            "selected": False,
                            "accepted": False,
                            "selectionGateTrace": {
                                "selectedProfileRankingRejected": True,
                                "continuityRejected": False,
                                "edgeShareRejected": False,
                                "repeatedAnchorRejected": False,
                                "segmentLengthRejected": False,
                            },
                        }
                        for frame_id in [255, 260]
                    ],
                }
            ],
        },
    )
    _write_json(proof_root / "ball_truth_layers.json", {"acceptedBall": {"rows": []}})
    _write_json(proof_root / "proof_summary.json", {"acceptedBallFrames": 0})
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.099})

    payload = (
        run_promoted_v6_global_reachable_acceptance_probe
        .run_promoted_v6_global_reachable_acceptance_probe(
            output_root=output_root,
            global_gap_root=gap_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
        )
    )

    summary = payload["summary"]
    assert summary["reachableFrameIds"] == [255, 260]
    assert summary["dominantBlockerClass"] == "global_reachable_selected_profile_ranking_rejected"
    assert summary["nextCorrectiveFamily"] == "global_reachable_selection_profile"
    assert summary["profileCandidate"] == (
        "source_robustness_shadow_promoted_v6_global_reachable_acceptance_probe_v1"
    )
    assert (output_root / "global_reachable_frame_gate_trace.json").exists()


def test_global_reachable_probe_selects_delta_refresh_when_frames_are_accepted(tmp_path: Path) -> None:
    output_root = tmp_path / "global_reachable_acceptance_probe_v1"
    gap_root = tmp_path / "gap"
    proof_root = tmp_path / "proof"
    retention_root = tmp_path / "retention"

    _write_json(
        gap_root / "accepted_gap_frame_manifest.json",
        {"frames": [{"frameIndex": 255, "gapClass": "baseline_accepted_already_accepted_in_promoted"}]},
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": "proposal_windows_075",
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalFrameDiagnostics": [
                        {"frameIndex": 255, "selected": True, "accepted": True}
                    ],
                }
            ],
        },
    )
    _write_json(proof_root / "ball_truth_layers.json", {"acceptedBall": {"rows": [{"Frame_ID": 255}]}})
    _write_json(proof_root / "proof_summary.json", {"acceptedBallFrames": 1})
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.11})

    payload = (
        run_promoted_v6_global_reachable_acceptance_probe
        .run_promoted_v6_global_reachable_acceptance_probe(
            output_root=output_root,
            global_gap_root=gap_root,
            promoted_proof_root=proof_root,
            retention_delta_root=retention_root,
        )
    )

    summary = payload["summary"]
    assert summary["acceptedFrameCount"] == 1
    assert summary["nextCorrectiveFamily"] == "accepted_retention_delta_refresh"
