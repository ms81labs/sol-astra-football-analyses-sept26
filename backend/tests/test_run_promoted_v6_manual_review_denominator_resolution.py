from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_manual_review_denominator_resolution


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bbox(frame: int) -> dict[str, float]:
    return {"x1": float(frame), "y1": 10.0, "x2": float(frame + 8), "y2": 18.0}


def _item(frame: int, decision: str) -> dict:
    return {
        "reviewItemId": f"review-{frame}",
        "candidateFrameId": f"candidate-{frame}",
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "decision": decision,
        "seedBBox": _bbox(frame),
        "reviewedBBox": _bbox(frame + 1) if decision == "adjust_bbox" else None,
        "lineage": {
            "labelingQueuePath": "/queue.json",
            "v7DatasetManifestPath": "/manifest.json",
            "baselineDenominatorReviewSummaryPath": "/denominator.json",
            "acceptedGapFrameManifestPath": "/gap.json",
            "sourceClipId": "trimed-5min.mp4",
        },
    }


def test_denominator_resolution_stops_when_pending_items_remain(tmp_path: Path) -> None:
    expansion_root = tmp_path / "manual_review_denominator_expansion_v1"
    output_root = tmp_path / "manual_review_denominator_resolution_v1"
    v7_root = tmp_path / "v7"
    _write_json(expansion_root / "reviewed_label_overlay.json", {"reviewItems": [_item(1, "pending_review")]})
    _write_json(v7_root / "touchline_detector_candidate_v7_training_data_refresh_summary.json", {"reviewedPositiveFrameCount": 17})

    payload = (
        run_promoted_v6_manual_review_denominator_resolution
        .run_promoted_v6_manual_review_denominator_resolution(
            expansion_root=expansion_root,
            output_root=output_root,
            v7_refresh_root=v7_root,
        )
    )

    assert payload["summary"]["batchStatus"] == "manual_review_pending"
    assert payload["summary"]["roadmapAdvanceAllowed"] is False
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_pending"


def test_denominator_resolution_writes_truth_seed_and_selects_training_prep_when_ready(tmp_path: Path) -> None:
    expansion_root = tmp_path / "manual_review_denominator_expansion_v1"
    output_root = tmp_path / "manual_review_denominator_resolution_v1"
    v7_root = tmp_path / "v7"
    items = [_item(1, "accept_seed"), _item(2, "adjust_bbox"), _item(3, "reject_seed")]
    _write_json(expansion_root / "reviewed_label_overlay.json", {"reviewItems": items})
    _write_json(v7_root / "touchline_detector_candidate_v7_training_data_refresh_summary.json", {"reviewedPositiveFrameCount": 18})

    payload = (
        run_promoted_v6_manual_review_denominator_resolution
        .run_promoted_v6_manual_review_denominator_resolution(
            expansion_root=expansion_root,
            output_root=output_root,
            v7_refresh_root=v7_root,
            min_total_positive_frames=20,
        )
    )

    summary = payload["summary"]
    assert summary["batchStatus"] == "review_resolved"
    assert summary["denominatorReviewedPositiveCount"] == 2
    assert summary["denominatorReviewedNegativeCount"] == 1
    assert summary["totalReviewedPositiveFrameCount"] == 20
    assert summary["nextCorrectiveFamily"] == "touchline_detector_candidate_v7_training_prep"
    seed = json.loads((output_root / "reviewed_denominator_truth_seed.json").read_text())
    assert seed["reviewedPositiveSeedCount"] == 2
    assert seed["reviewedNegativeSeedCount"] == 1


def test_denominator_resolution_marks_adjust_without_bbox_invalid(tmp_path: Path) -> None:
    expansion_root = tmp_path / "manual_review_denominator_expansion_v1"
    output_root = tmp_path / "manual_review_denominator_resolution_v1"
    v7_root = tmp_path / "v7"
    item = _item(1, "adjust_bbox")
    item["reviewedBBox"] = None
    _write_json(expansion_root / "reviewed_label_overlay.json", {"reviewItems": [item]})
    _write_json(v7_root / "touchline_detector_candidate_v7_training_data_refresh_summary.json", {"reviewedPositiveFrameCount": 17})

    payload = (
        run_promoted_v6_manual_review_denominator_resolution
        .run_promoted_v6_manual_review_denominator_resolution(
            expansion_root=expansion_root,
            output_root=output_root,
            v7_refresh_root=v7_root,
        )
    )

    assert payload["summary"]["batchStatus"] == "manual_review_invalid"
    assert payload["summary"]["invalidDecisionCount"] == 1
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_denominator_repair"
