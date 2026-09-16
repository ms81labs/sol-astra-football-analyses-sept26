from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_manual_review_resolution_batch as resolution_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bbox(frame_id: int) -> dict[str, float]:
    return {
        "x1": float(frame_id),
        "y1": float(frame_id + 1),
        "x2": float(frame_id + 10),
        "y2": float(frame_id + 11),
    }


def _review_item(frame_id: int, *, decision: str = "pending_review", reviewed_bbox: object = None) -> dict[str, object]:
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": f"window-{frame_id // 10}",
        "curationUnitId": f"window-{frame_id // 10}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "seedBBox": _bbox(frame_id),
        "decision": decision,
        "reviewedBBox": reviewed_bbox,
        "lineageComplete": True,
        "lineage": {
            "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
            "baselineSelectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
            "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
            "promotedSelectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
        },
        "notes": "review item",
        "fileStem": f"trimed-5min.mp4__f{frame_id:06d}__candidate-{frame_id}",
    }


def _write_inputs(
    root: Path,
    review_items: list[dict[str, object]],
) -> dict[str, Path]:
    output_root = root / "resolution"
    review_root = root / "manual_review"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_root = root / "runtime"
    source_manifest_path = root / "frozen_source_manifest.json"

    pending = sum(item.get("decision") == "pending_review" for item in review_items)
    positive = sum(item.get("decision") in {"accept_seed", "adjust_bbox"} for item in review_items)
    negative = sum(item.get("decision") in {"reject_seed", "confirm_hard_negative"} for item in review_items)
    _write_json(
        review_root / "reviewed_label_overlay.json",
        {
            "batchName": "promoted_v6_manual_review_followthrough_v1",
            "reviewItemCount": len(review_items),
            "pendingReviewCount": pending,
            "reviewedPositiveCount": positive,
            "reviewedNegativeCount": negative,
            "reviewItems": review_items,
        },
    )
    _write_json(
        review_root / "review_frame_manifest.json",
        {
            "reviewFrameCount": len(review_items),
            "extractedImageCount": len(review_items),
            "imageExtractionStatus": "images_extracted",
            "reviewFrames": [
                {
                    "reviewItemId": item["reviewItemId"],
                    "candidateFrameId": item["candidateFrameId"],
                    "frameIndex": item["frameIndex"],
                    "imageExtracted": True,
                }
                for item in review_items
            ],
        },
    )
    _write_json(
        review_root / "review_bundle_manifest.json",
        {
            "reviewedLabelOverlayPath": str(review_root / "reviewed_label_overlay.json"),
            "reviewFrameManifestPath": str(review_root / "review_frame_manifest.json"),
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
    _write_json(runtime_root / "promoted_touchline_detector_candidate.json", {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    return {
        "output_root": output_root,
        "manual_review_root": review_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_root / "promoted_touchline_detector_candidate.json",
        "source_manifest_path": source_manifest_path,
    }


def test_resolution_batch_keeps_current_all_pending_overlay_pending(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, [_review_item(frame_id) for frame_id in range(100, 178)])

    payload = resolution_batch.run_promoted_v6_manual_review_resolution_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is False
    assert summary["batchStatus"] == "manual_review_pending"
    assert summary["reviewItemCount"] == 78
    assert summary["pendingReviewCount"] == 78
    assert summary["invalidDecisionCount"] == 0
    assert summary["nextCorrectiveFamily"] == "manual_review_pending"
    blocker = json.loads((paths["output_root"] / "review_resolution_blocker_summary.json").read_text())
    assert blocker["pendingReviewCount"] == 78


def test_resolution_batch_counts_mixed_valid_decisions_and_writes_truth_seed(tmp_path: Path) -> None:
    items = [
        _review_item(10, decision="accept_seed"),
        _review_item(20, decision="adjust_bbox", reviewed_bbox={"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 6.0}),
        _review_item(30, decision="reject_seed"),
        _review_item(40, decision="confirm_hard_negative"),
    ]
    paths = _write_inputs(tmp_path, items)

    payload = resolution_batch.run_promoted_v6_manual_review_resolution_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["batchStatus"] == "review_resolved"
    assert summary["acceptedSeedCount"] == 1
    assert summary["adjustedBBoxCount"] == 1
    assert summary["reviewedNegativeCount"] == 2
    assert summary["nextCorrectiveFamily"] == "reviewed_followthrough_selection_fix"
    seed = json.loads((paths["output_root"] / "reviewed_followthrough_truth_seed.json").read_text())
    assert seed["reviewedPositiveSeedCount"] == 2
    assert [row["reviewDecision"] for row in seed["reviewedPositiveSeedRows"]] == ["accept_seed", "adjust_bbox"]
    assert seed["reviewedPositiveSeedRows"][1]["reviewedBBox"] == {"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 6.0}


def test_resolution_batch_rejects_adjust_bbox_without_reviewed_box(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, [_review_item(50, decision="adjust_bbox")])

    payload = resolution_batch.run_promoted_v6_manual_review_resolution_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is False
    assert summary["batchStatus"] == "manual_review_invalid"
    assert summary["invalidDecisionCount"] == 1
    assert summary["nextCorrectiveFamily"] == "manual_review_required"
    repair = json.loads((paths["output_root"] / "review_resolution_blocker_summary.json").read_text())
    assert repair["repairGuidanceByReviewItemId"]["review-50"][0] == "add_valid_reviewed_bbox_for_adjust_bbox"


def test_resolution_batch_all_negative_selects_refuted_refresh(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        [
            _review_item(60, decision="reject_seed"),
            _review_item(70, decision="confirm_hard_negative"),
        ],
    )

    payload = resolution_batch.run_promoted_v6_manual_review_resolution_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["acceptedSeedCount"] == 0
    assert summary["reviewedNegativeCount"] == 2
    assert summary["nextCorrectiveFamily"] == "gold_truth_seed_refuted_refresh"


def test_resolution_batch_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, [_review_item(80, decision="accept_seed")])
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    resolution_batch.run_promoted_v6_manual_review_resolution_batch(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
