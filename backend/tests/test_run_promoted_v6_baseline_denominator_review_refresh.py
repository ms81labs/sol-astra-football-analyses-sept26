from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_baseline_denominator_review_refresh


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _frame(frame_id: int, *, gap_class: str, review_class: str, promoted_accepted: bool = False) -> dict:
    return {
        "frameIndex": frame_id,
        "gapClass": gap_class,
        "reviewTruthClass": review_class,
        "baselineAccepted": True,
        "promotedAccepted": promoted_accepted,
        "missingFromPromotedAccepted": not promoted_accepted,
    }


def test_denominator_refresh_classifies_refuted_reviewed_overlap_and_unreviewed_frames(tmp_path: Path) -> None:
    output_root = tmp_path / "baseline_denominator_review_refresh_v1"
    global_gap_root = tmp_path / "global_gap"
    reachable_root = tmp_path / "reachable"
    refuted_path = tmp_path / "refuted.json"
    reviewed_path = tmp_path / "reviewed.json"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    guardrail_root = tmp_path / "guardrail"

    _write_json(
        global_gap_root / "accepted_gap_frame_manifest.json",
        {
            "frames": [
                _frame(10, gap_class="baseline_accepted_already_accepted_in_promoted", review_class="reviewed_positive", promoted_accepted=True),
                _frame(20, gap_class="baseline_accepted_no_promoted_proposal", review_class="refuted_bootstrap_seed"),
                _frame(30, gap_class="baseline_accepted_no_promoted_proposal", review_class="reviewed_positive"),
                _frame(40, gap_class="baseline_accepted_no_promoted_proposal", review_class="unreviewed"),
                _frame(50, gap_class="baseline_accepted_no_promoted_proposal", review_class="reviewed_positive_with_refuted_seed_context"),
            ]
        },
    )
    _write_json(global_gap_root / "accepted_gap_class_taxonomy.json", {"gapClassCounts": {}})
    _write_json(reachable_root / "global_reachable_acceptance_summary.json", {"acceptedFrameCount": 1})
    _write_json(refuted_path, {"rejectedSeeds": [{"frameIndex": 20}, {"frameIndex": 50}]})
    _write_json(reviewed_path, {"reviewedPositiveSeedRows": [{"frameIndex": 10}, {"frameIndex": 30}, {"frameIndex": 50}]})
    _write_json(validation_root / "arm_matrix.json", {"arms": []})
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.2})
    _write_json(
        guardrail_root / "accepted_retention_guardrail_summary.json",
        {"acceptedRetentionGuardrail": 0.6, "controlledRetentionGuardrail": 0.6},
    )

    payload = (
        run_promoted_v6_baseline_denominator_review_refresh
        .run_promoted_v6_baseline_denominator_review_refresh(
            output_root=output_root,
            global_gap_root=global_gap_root,
            reachable_root=reachable_root,
            refuted_seed_path=refuted_path,
            reviewed_truth_path=reviewed_path,
            validation_root=validation_root,
            retention_delta_root=retention_root,
            guardrail_root=guardrail_root,
        )
    )

    summary = payload["summary"]
    assert summary["baselineDenominatorFrameCount"] == 5
    assert summary["promotedAcceptedOverlapCount"] == 1
    assert summary["refutedDenominatorFrameCount"] == 2
    assert summary["reviewedPositiveSupportedFrameCount"] == 2
    assert summary["unreviewedDenominatorFrameCount"] == 1
    assert summary["classificationCounts"] == {
        "promoted_accepted_overlap": 1,
        "refuted_bootstrap_seed_denominator_contaminant": 2,
        "reviewed_positive_supported_denominator_frame": 1,
        "unreviewed_denominator_frame": 1,
    }
    assert summary["refutedSeedsReusedAsPositiveEvidence"] is False
    assert (output_root / "effective_retention_denominator_delta.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_denominator_refresh_selects_refuted_filter_when_refuted_frames_dominate(tmp_path: Path) -> None:
    output_root = tmp_path / "baseline_denominator_review_refresh_v1"
    global_gap_root = tmp_path / "global_gap"
    reachable_root = tmp_path / "reachable"
    refuted_path = tmp_path / "refuted.json"
    reviewed_path = tmp_path / "reviewed.json"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    guardrail_root = tmp_path / "guardrail"

    frames = [
        _frame(1, gap_class="baseline_accepted_already_accepted_in_promoted", review_class="reviewed_positive", promoted_accepted=True),
        _frame(2, gap_class="baseline_accepted_no_promoted_proposal", review_class="refuted_bootstrap_seed"),
        _frame(3, gap_class="baseline_accepted_no_promoted_proposal", review_class="refuted_bootstrap_seed"),
        _frame(4, gap_class="baseline_accepted_no_promoted_proposal", review_class="unreviewed"),
    ]
    _write_json(global_gap_root / "accepted_gap_frame_manifest.json", {"frames": frames})
    _write_json(global_gap_root / "accepted_gap_class_taxonomy.json", {})
    _write_json(reachable_root / "global_reachable_acceptance_summary.json", {})
    _write_json(refuted_path, {"rejectedSeeds": [{"frameIndex": 2}, {"frameIndex": 3}]})
    _write_json(reviewed_path, {"reviewedPositiveSeedRows": [{"frameIndex": 1}]})
    _write_json(validation_root / "arm_matrix.json", {})
    _write_json(retention_root / "retention_delta_summary.json", {})
    _write_json(guardrail_root / "accepted_retention_guardrail_summary.json", {"acceptedRetentionGuardrail": 0.6})

    payload = (
        run_promoted_v6_baseline_denominator_review_refresh
        .run_promoted_v6_baseline_denominator_review_refresh(
            output_root=output_root,
            global_gap_root=global_gap_root,
            reachable_root=reachable_root,
            refuted_seed_path=refuted_path,
            reviewed_truth_path=reviewed_path,
            validation_root=validation_root,
            retention_delta_root=retention_root,
            guardrail_root=guardrail_root,
        )
    )

    assert payload["summary"]["nextCorrectiveFamily"] == "refuted_denominator_filter_plan"


def test_denominator_refresh_selects_v7_when_filtering_remains_far_below_guardrail(tmp_path: Path) -> None:
    output_root = tmp_path / "baseline_denominator_review_refresh_v1"
    global_gap_root = tmp_path / "global_gap"
    reachable_root = tmp_path / "reachable"
    refuted_path = tmp_path / "refuted.json"
    reviewed_path = tmp_path / "reviewed.json"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    guardrail_root = tmp_path / "guardrail"

    frames = [
        _frame(frame_id, gap_class="baseline_accepted_already_accepted_in_promoted", review_class="reviewed_positive", promoted_accepted=True)
        for frame_id in [1, 2]
    ] + [
        _frame(frame_id, gap_class="baseline_accepted_no_promoted_proposal", review_class="unreviewed")
        for frame_id in range(3, 13)
    ]
    _write_json(global_gap_root / "accepted_gap_frame_manifest.json", {"frames": frames})
    _write_json(global_gap_root / "accepted_gap_class_taxonomy.json", {})
    _write_json(reachable_root / "global_reachable_acceptance_summary.json", {})
    _write_json(refuted_path, {"rejectedSeeds": []})
    _write_json(reviewed_path, {"reviewedPositiveSeedRows": [{"frameIndex": 1}, {"frameIndex": 2}]})
    _write_json(validation_root / "arm_matrix.json", {})
    _write_json(retention_root / "retention_delta_summary.json", {})
    _write_json(guardrail_root / "accepted_retention_guardrail_summary.json", {"acceptedRetentionGuardrail": 0.6})

    payload = (
        run_promoted_v6_baseline_denominator_review_refresh
        .run_promoted_v6_baseline_denominator_review_refresh(
            output_root=output_root,
            global_gap_root=global_gap_root,
            reachable_root=reachable_root,
            refuted_seed_path=refuted_path,
            reviewed_truth_path=reviewed_path,
            validation_root=validation_root,
            retention_delta_root=retention_root,
            guardrail_root=guardrail_root,
        )
    )

    summary = payload["summary"]
    assert summary["effectiveAcceptedRetentionRatioAfterRefutedFilter"] == 0.167
    assert summary["nextCorrectiveFamily"] == "v7_training_data_lane"
