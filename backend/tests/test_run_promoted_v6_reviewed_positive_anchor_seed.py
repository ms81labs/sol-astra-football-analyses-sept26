from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_anchor_seed


def _write_expanded_truth_seed(path: Path) -> None:
    positives = [
        {
            "reviewItemId": "positive-240",
            "candidateFrameId": "manual-review-expansion-240",
            "windowId": "window-240-320",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 240,
            "timestampSeconds": 9.6,
            "reviewDecision": "adjust_bbox",
            "reviewedBBox": {"x1": 381.0, "y1": 688.0, "x2": 397.0, "y2": 704.0},
            "lineage": {"reviewOverlayPath": "/tmp/reviewed_label_overlay.json"},
        },
        {
            "reviewItemId": "positive-245",
            "candidateFrameId": "manual-review-expansion-245",
            "windowId": "window-240-320",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 245,
            "timestampSeconds": 9.8,
            "reviewDecision": "accept_seed",
            "reviewedBBox": {"x1": 390.0, "y1": 684.0, "x2": 406.0, "y2": 701.0},
            "lineage": {"reviewOverlayPath": "/tmp/reviewed_label_overlay.json"},
        },
    ]
    negatives = [
        {
            "reviewItemId": "negative-250",
            "candidateFrameId": "manual-review-expansion-250",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 250,
            "reviewDecision": "reject_seed",
            "reviewedBBox": {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0},
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "reviewedPositiveSeedCount": len(positives),
                "reviewedPositiveSeedRows": positives,
                "reviewedNegativeSeedCount": len(negatives),
                "reviewedNegativeSeedRows": negatives,
            }
        ),
        encoding="utf-8",
    )


def test_anchor_seed_generation_uses_only_reviewed_positive_boxes(tmp_path):
    expansion_root = tmp_path / "manual_review_expansion_resolution_v1"
    output_root = tmp_path / "reviewed_positive_proposal_generation_fix_v1"
    _write_expanded_truth_seed(expansion_root / "expanded_reviewed_truth_seed.json")

    payload = run_promoted_v6_reviewed_positive_anchor_seed.run_promoted_v6_reviewed_positive_anchor_seed(
        expansion_resolution_root=expansion_root,
        output_root=output_root,
    )

    summary = payload["reviewedPositiveAnchorSeedSummary"]
    seed = payload["reviewedPositiveAnchorSeed"]
    assert summary["reviewedPositiveAnchorFrameCount"] == 2
    assert summary["refutedSeedCount"] == 1
    assert [row["frameIndex"] for row in seed["reviewedPositiveAnchorRows"]] == [240, 245]
    assert [row["sourceCenter"] for row in seed["reviewedPositiveAnchorRows"]] == [
        {"x": 389.0, "y": 696.0},
        {"x": 398.0, "y": 692.5},
    ]
    assert all(row["truthUse"] == "reviewed_positive_proposal_anchor" for row in seed["reviewedPositiveAnchorRows"])
    assert all(row["reviewItemId"] != "negative-250" for row in seed["reviewedPositiveAnchorRows"])
    assert (output_root / "reviewed_positive_anchor_seed.json").exists()
    assert (output_root / "reviewed_positive_anchor_seed_summary.json").exists()
