from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_manual_review_denominator_expansion


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _review_item(frame: int) -> dict:
    return {
        "reviewItemId": f"v7-denominator-review-trimed-5min.mp4-{frame}",
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "reviewDecision": "pending_review",
        "truthUse": "pending_denominator_review",
        "gapClass": "baseline_accepted_no_promoted_proposal",
        "classification": "unreviewed_denominator_frame",
        "baselineAccepted": True,
        "promotedAccepted": False,
    }


def test_denominator_expansion_builds_pending_review_overlay_and_manifests(tmp_path: Path) -> None:
    queue_path = tmp_path / "v7" / "v7_labeling_queue.json"
    gap_path = tmp_path / "gap" / "accepted_gap_frame_manifest.json"
    output_root = tmp_path / "manual_review_denominator_expansion_v1"
    _write_json(queue_path, {"reviewItems": [_review_item(frame) for frame in [0, 340, 345]]})
    _write_json(
        gap_path,
        {
            "frames": [
                {
                    "frameIndex": frame,
                    "baselineRow": {"sourceBBox": {"x1": 1, "y1": 2, "x2": 9, "y2": 10}},
                }
                for frame in [0, 340, 345]
            ]
        },
    )

    payload = (
        run_promoted_v6_manual_review_denominator_expansion
        .run_promoted_v6_manual_review_denominator_expansion(
            labeling_queue_path=queue_path,
            output_root=output_root,
            accepted_gap_manifest_path=gap_path,
            video_path=tmp_path / "missing.mp4",
        )
    )

    summary = payload["summary"]
    assert summary["reviewItemCount"] == 3
    assert summary["pendingReviewCount"] == 3
    assert summary["lineageCompleteCount"] == 3
    assert summary["validSeedBBoxCount"] == 3
    assert summary["imageExtractionStatus"] == "json_only_no_video"
    assert summary["nextCorrectiveFamily"] == "manual_review_denominator_resolution"

    overlay = payload["reviewedLabelOverlay"]
    assert all(item["decision"] == "pending_review" for item in overlay["reviewItems"])
    assert all(item["seedBBox"] == {"x1": 1.0, "y1": 2.0, "x2": 9.0, "y2": 10.0} for item in overlay["reviewItems"])
    assert all(item["truthUse"] == "pending_denominator_review" for item in overlay["reviewItems"])
    assert (output_root / "reviewed_label_overlay.json").exists()
    assert (output_root / "review_frame_manifest.json").exists()
    assert (output_root / "review_bundle_manifest.json").exists()


def test_denominator_expansion_marks_weak_evidence_when_queue_is_empty(tmp_path: Path) -> None:
    queue_path = tmp_path / "v7" / "v7_labeling_queue.json"
    gap_path = tmp_path / "gap" / "accepted_gap_frame_manifest.json"
    output_root = tmp_path / "manual_review_denominator_expansion_v1"
    _write_json(queue_path, {"reviewItems": []})
    _write_json(gap_path, {"frames": []})

    payload = (
        run_promoted_v6_manual_review_denominator_expansion
        .run_promoted_v6_manual_review_denominator_expansion(
            labeling_queue_path=queue_path,
            output_root=output_root,
            accepted_gap_manifest_path=gap_path,
            video_path=tmp_path / "missing.mp4",
        )
    )

    assert payload["summary"]["goalAchieved"] is False
    assert payload["summary"]["nextCorrectiveFamily"] == "manual_review_lineage_refresh"
    assert payload["summary"]["weakEvidenceReasons"] == ["no_pending_denominator_review_items"]
