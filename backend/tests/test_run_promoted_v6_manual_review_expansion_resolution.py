from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_manual_review_expansion_resolution as expansion_resolution


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


def _lineage() -> dict[str, str]:
    return {
        "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
        "baselineSelectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
        "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        "promotedSelectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
    }


def _review_item(frame_id: int, decision: str) -> dict[str, object]:
    reviewed_bbox = _bbox(frame_id) if decision == "adjust_bbox" else None
    seed_bbox = _bbox(frame_id) if decision == "accept_seed" else None
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": "trimed-5min.mp4-manual-review-expansion-0240-0320",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "decision": decision,
        "seedBBox": seed_bbox,
        "reviewedBBox": reviewed_bbox,
        "lineage": _lineage() if decision == "accept_seed" else {},
        "lineageComplete": True,
    }


def _write_inputs(root: Path, *, pending: bool = False, invalid_adjust: bool = False) -> dict[str, Path]:
    output_root = root / "manual_review_expansion_resolution_v1"
    expansion_root = root / "manual_review_expansion_v1"
    retention_root = root / "retention"
    suite_root = root / "suite"
    runtime_default_path = root / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = root / "frozen_source_manifest.json"
    frame_ids = list(range(240, 321, 5))
    positive_anchors = {260, 290, 295, 300}
    review_items = []
    for frame_id in frame_ids:
        if frame_id in positive_anchors:
            review_items.append(_review_item(frame_id, "accept_seed"))
        elif pending:
            review_items.append(_review_item(frame_id, "pending_review"))
        else:
            item = _review_item(frame_id, "adjust_bbox")
            if invalid_adjust and frame_id == 240:
                item["reviewedBBox"] = None
            review_items.append(item)
    _write_json(
        expansion_root / "reviewed_label_overlay.json",
        {
            "batchName": "manual_review_expansion_v1",
            "reviewItemCount": len(review_items),
            "pendingReviewCount": sum(item["decision"] == "pending_review" for item in review_items),
            "acceptedSeedCount": sum(item["decision"] == "accept_seed" for item in review_items),
            "adjustedBBoxCount": sum(item["decision"] == "adjust_bbox" for item in review_items),
            "reviewedPositiveCount": sum(item["decision"] in {"accept_seed", "adjust_bbox"} for item in review_items),
            "reviewedNegativeCount": 0,
            "reviewItems": review_items,
        },
    )
    _write_json(
        expansion_root / "review_frame_manifest.json",
        {
            "reviewFrameCount": len(review_items),
            "extractedImageCount": len(review_items),
            "imageExtractionStatus": "images_extracted",
            "reviewFrames": [
                {
                    "reviewItemId": item["reviewItemId"],
                    "frameIndex": item["frameIndex"],
                    "imageExtracted": True,
                }
                for item in review_items
            ],
        },
    )
    _write_json(
        expansion_root / "refutation_guard_manifest.json",
        {
            "rejectedSeedCount": 74,
            "rejectedSeedsReusedAsPositiveEvidence": False,
            "rejectedSeeds": [],
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
            "sourceRobustnessPromotionBlockers": ["failing_source_not_viable"],
        },
    )
    _write_json(runtime_default_path, {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    return {
        "output_root": output_root,
        "expansion_root": expansion_root,
        "retention_delta_root": retention_root,
        "suite_root": suite_root,
        "runtime_default_path": runtime_default_path,
        "source_manifest_path": source_manifest_path,
    }


def test_expansion_resolution_stops_when_pending_items_remain(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, pending=True)

    payload = expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    summary = payload["summary"]
    assert summary["batchStatus"] == "manual_review_pending"
    assert summary["goalAchieved"] is False
    assert summary["pendingReviewCount"] == 13
    assert summary["nextCorrectiveFamily"] == "manual_review_pending"
    assert (paths["output_root"] / "review_resolution_blocker_summary.json").exists()


def test_expansion_resolution_writes_reviewed_truth_seed_and_micro_validation_next(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    payload = expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    summary = payload["summary"]
    assert summary["batchStatus"] == "review_resolved"
    assert summary["goalAchieved"] is True
    assert summary["reviewedPositiveCount"] == 17
    assert summary["pendingReviewCount"] == 0
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_micro_validation"
    seed = json.loads((paths["output_root"] / "expanded_reviewed_truth_seed.json").read_text())
    assert seed["reviewedPositiveSeedCount"] == 17
    assert [row["frameIndex"] for row in seed["reviewedPositiveSeedRows"]] == list(range(240, 321, 5))


def test_expansion_resolution_does_not_trust_lineage_complete_flag_without_lineage(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    overlay_path = paths["expansion_root"] / "reviewed_label_overlay.json"
    overlay = json.loads(overlay_path.read_text())
    for item in overlay["reviewItems"]:
        if item["decision"] == "adjust_bbox":
            item["lineageComplete"] = True
            item["lineage"] = {}
    overlay_path.write_text(json.dumps(overlay, indent=2), encoding="utf-8")

    payload = expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    summary = payload["summary"]
    assert summary["lineageCompleteCount"] == 4
    matrix = json.loads((paths["output_root"] / "review_decision_matrix.json").read_text())
    adjusted_rows = [
        row for row in matrix["reviewDecisions"] if row["decision"] == "adjust_bbox"
    ]
    assert adjusted_rows
    assert {row["lineageComplete"] for row in adjusted_rows} == {False}


def test_expansion_resolution_rejects_adjust_bbox_without_reviewed_box(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, invalid_adjust=True)

    payload = expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    summary = payload["summary"]
    assert summary["batchStatus"] == "manual_review_invalid"
    assert summary["invalidDecisionCount"] == 1
    assert summary["nextCorrectiveFamily"] == "manual_review_required"


def test_expansion_resolution_writes_all_expected_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    for filename in (
        "manual_review_expansion_resolution_summary.json",
        "review_decision_matrix.json",
        "expanded_reviewed_truth_seed.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (paths["output_root"] / filename).exists()


def test_expansion_resolution_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    expansion_resolution.run_promoted_v6_manual_review_expansion_resolution(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
