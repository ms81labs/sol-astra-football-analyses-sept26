from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_accepted_retention_guardrail_audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _arm(
    name: str,
    *,
    accepted_frames: int,
    controlled_frames: int,
    accepted_retention: float,
    controlled_retention: float,
    edge_improvement: float,
    passed: bool = False,
    blockers: list[str] | None = None,
) -> dict:
    return {
        "armName": name,
        "sourceSummaries": {
            "trimed-5min.mp4": {
                "medianAcceptedRetentionRatio": accepted_retention,
                "medianControlledRetentionRatio": controlled_retention,
                "medianBallTrackEdgeFrameShare": 0.2,
                "sourceViable": True,
                "sourceFailureSignal": "low_accepted_ball_ratio",
            }
        },
        "proofRuns": [
            {
                "sourceClipId": "trimed-5min.mp4",
                "acceptedBallFrames": accepted_frames,
                "controlledPossessionFrames": controlled_frames,
            }
        ],
        "outcome": {
            "failingSourceEdgeShareImprovement": edge_improvement,
            "passedPromotionGate": passed,
            "promotionBlockers": blockers or [],
            "configOutcome": "source_robustness_strong" if passed else "source_robustness_weak",
        },
    }


def test_guardrail_audit_selects_global_gap_when_best_arm_below_retention_guardrail(tmp_path: Path) -> None:
    output_root = tmp_path / "accepted_retention_guardrail_audit_v1"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    microfix_root = tmp_path / "microfix"

    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                _arm(
                    "baseline_current",
                    accepted_frames=101,
                    controlled_frames=98,
                    accepted_retention=1.0,
                    controlled_retention=1.0,
                    edge_improvement=-0.812,
                    blockers=["edge_share_improvement_insufficient"],
                ),
                _arm(
                    "promoted_v6_baseline",
                    accepted_frames=11,
                    controlled_frames=11,
                    accepted_retention=0.109,
                    controlled_retention=0.112,
                    edge_improvement=0.448,
                    blockers=["accepted_retention_below_guardrail", "controlled_retention_below_guardrail"],
                ),
                _arm(
                    "promoted_v6_plus_best_thin",
                    accepted_frames=10,
                    controlled_frames=13,
                    accepted_retention=0.099,
                    controlled_retention=0.133,
                    edge_improvement=0.712,
                    blockers=["accepted_retention_below_guardrail", "controlled_retention_below_guardrail"],
                ),
            ]
        },
    )
    _write_json(
        validation_root / "validation_summary.json",
        {
            "winningArmName": "promoted_v6_plus_best_thin",
            "winningPassedPromotionGate": False,
            "winningPromotionBlockers": [
                "accepted_retention_below_guardrail",
                "controlled_retention_below_guardrail",
            ],
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.099,
            "controlledRetentionRatio": 0.133,
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
        },
    )
    _write_json(
        microfix_root / "residual_segment_selection_microfix_summary.json",
        {"residualAcceptedFrameCount": 4, "residualSelectedFrameCount": 4},
    )

    payload = (
        run_promoted_v6_accepted_retention_guardrail_audit
        .run_promoted_v6_accepted_retention_guardrail_audit(
            output_root=output_root,
            validation_root=validation_root,
            retention_delta_root=retention_root,
            microfix_root=microfix_root,
        )
    )

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "accepted_controlled_retention_guardrail_gap"
    assert summary["bestRetentionArmName"] == "promoted_v6_baseline"
    assert summary["acceptedFramesRequiredForGuardrail"] == 61
    assert summary["acceptedFramesShortOfGuardrail"] == 50
    assert summary["nextCorrectiveFamily"] == "global_accepted_gap_audit"
    assert summary["rankingFinding"]["present"] is True
    assert (output_root / "arm_retention_guardrail_matrix.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_guardrail_audit_selects_runtime_default_validation_when_promotion_gate_clears(tmp_path: Path) -> None:
    output_root = tmp_path / "accepted_retention_guardrail_audit_v1"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    microfix_root = tmp_path / "microfix"

    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                _arm(
                    "baseline_current",
                    accepted_frames=100,
                    controlled_frames=100,
                    accepted_retention=1.0,
                    controlled_retention=1.0,
                    edge_improvement=-0.8,
                ),
                _arm(
                    "promoted_v6_baseline",
                    accepted_frames=62,
                    controlled_frames=65,
                    accepted_retention=0.62,
                    controlled_retention=0.65,
                    edge_improvement=0.4,
                    passed=True,
                ),
            ]
        },
    )
    _write_json(
        validation_root / "validation_summary.json",
        {"winningArmName": "promoted_v6_baseline", "winningPassedPromotionGate": True},
    )
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.62})
    _write_json(microfix_root / "residual_segment_selection_microfix_summary.json", {})

    payload = (
        run_promoted_v6_accepted_retention_guardrail_audit
        .run_promoted_v6_accepted_retention_guardrail_audit(
            output_root=output_root,
            validation_root=validation_root,
            retention_delta_root=retention_root,
            microfix_root=microfix_root,
        )
    )

    summary = payload["summary"]
    assert summary["dominantBlockerClass"] == "promotion_gate_cleared"
    assert summary["nextCorrectiveFamily"] == "validate_promoted_touchline_runtime_default"
    assert summary["runtimeDefaultChanged"] is False
