from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_v7_1_positive_diversity_manual_review_resolution as resolution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _item(index: int, *, status: str, source: str = "temporal_neighbor", group: str | None = None) -> dict[str, object]:
    bbox = {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0}
    row: dict[str, object] = {
        "candidateId": f"candidate-{index}",
        "reviewStatus": status,
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 1000 + index * 10,
        "source": source,
        "sourceFrameBbox": bbox,
        "visibilityClass": "clear",
        "contextTags": ["small_ball"],
        "reviewNotes": "",
        "splitGroupId": group or f"group-{index % 9}",
        "reviewFrameImagePath": f"/tmp/review-frame-{index}.jpg",
    }
    if status == "reviewed_positive_ball":
        row["trainingEligibility"] = "eligible_positive_truth"
    elif status != "pending_review":
        row["rejectionReason"] = "not_visible_ball"
    return row


def _write_bundle(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    expansion_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    manifest_root = root / "v7_1_crop_manifest_consistency_refresh_v1"
    _write_json(expansion_root / "reviewed_label_overlay.json", {"reviewItems": items})
    _write_json(
        expansion_root / "v7_1_positive_diversity_manual_review_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 30,
            "reviewQueueCandidateCount": len(items),
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    _write_json(
        manifest_root / "v7_1_local_crop_training_manifest.json",
        {
            "reviewedPositiveSourceCount": 30,
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def _write_v2_bundle(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    mining_root = root / "v7_1_positive_candidate_mining_expansion_v1"
    _write_json(mining_root / "corrected_label_overlay.json", {"reviewItems": items})
    _write_json(
        mining_root / "v7_1_positive_candidate_mining_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 34,
            "totalCandidateReviewCount": len(items),
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def _write_v2_bundle_with_known_miss_carryforward(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = _write_v2_bundle(tmp_path, items)
    mining_root = root / "v7_1_positive_candidate_mining_expansion_v1"
    _write_json(
        mining_root / "v7_1_positive_candidate_mining_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 34,
            "totalCandidateReviewCount": len(items),
            "knownCropValidationMissesCarriedForward": 9,
            "knownFullPipelineMissesCarriedForward": 2,
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def _resolved_items(*, positive_count: int = 94, total: int = 149, groups: int = 9) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index in range(total):
        if index < positive_count:
            source = "v7_1_crop_probe_precision_guardrail_audit" if index < 9 else "temporal_neighbor"
            if 9 <= index < 11:
                source = "v7_1_full_pipeline_non_promotion_eval"
            items.append(_item(index, status="reviewed_positive_ball", source=source, group=f"group-{index % groups}"))
        elif index < positive_count + 28:
            items.append(_item(index, status="reviewed_not_ball"))
        elif index < positive_count + 40:
            items.append(_item(index, status="review_deferred_unclear"))
        else:
            items.append(_item(index, status="duplicate_or_near_duplicate"))
    return items


def test_resolution_stays_pending_when_review_items_are_unresolved(tmp_path: Path) -> None:
    _write_bundle(tmp_path, [_item(index, status="pending_review") for index in range(149)])

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_manual_review_still_pending"
    assert payload["pendingReviewItemCount"] == 149
    assert payload["goalAchieved"] is False
    assert payload["roadmapAdvanceAllowed"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_resolution"


def test_resolution_advances_to_v72_when_review_thresholds_pass(tmp_path: Path) -> None:
    _write_bundle(tmp_path, _resolved_items(positive_count=94, groups=9))

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["pendingReviewItemCount"] == 0
    assert payload["newReviewedPositiveSourceCount"] == 94
    assert payload["totalReviewedPositiveSourceCount"] == 124
    assert payload["distinctPositiveSplitGroupCount"] == 9
    assert payload["knownCropValidationMissesReviewed"] == 9
    assert payload["knownFullPipelineMissesReviewed"] == 2
    assert payload["nextRecommendedNextLever"] == "v7_2_training_manifest_prep"


def test_resolution_blocks_low_yield_after_completed_review(tmp_path: Path) -> None:
    _write_bundle(tmp_path, _resolved_items(positive_count=62, groups=8))

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_review_yield_insufficient"
    assert payload["pendingReviewItemCount"] == 0
    assert payload["totalReviewedPositiveSourceCount"] == 92
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_candidate_mining_expansion"


def test_resolution_rejects_invalid_accepted_bbox(tmp_path: Path) -> None:
    items = _resolved_items(positive_count=94, groups=9)
    items[0]["sourceFrameBbox"] = {"x1": 100.0, "y1": 120.0, "x2": 300.0, "y2": 136.0}
    _write_bundle(tmp_path, items)

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_invalid_bbox"
    assert payload["invalidBBoxCount"] == 1
    assert payload["nextRecommendedNextLever"] == "manual_review_required"


def test_resolution_rejects_accepted_positive_without_review_evidence_image(tmp_path: Path) -> None:
    items = _resolved_items(positive_count=94, groups=9)
    items[0].pop("reviewFrameImagePath", None)
    items[0].pop("reviewCropImagePath", None)
    _write_bundle(tmp_path, items)

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_label_quality_gap"
    assert payload["labelQualityGapCount"] == 1
    assert payload["nextRecommendedNextLever"] == "manual_review_required"


def test_resolution_counts_unique_source_positive_frames_not_crop_variants(tmp_path: Path) -> None:
    duplicate_items = []
    for index in range(3):
        row = _item(index, status="reviewed_positive_ball", source="v7_1_crop_probe_precision_guardrail_audit", group="group-0")
        row["candidateId"] = f"same-frame-crop-{index}"
        row["frameIndex"] = 240
        duplicate_items.append(row)
    duplicate_items.extend(_item(index + 3, status="reviewed_not_ball") for index in range(20))
    _write_bundle(tmp_path, duplicate_items)

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(storage_root=tmp_path)

    assert payload["newReviewedPositiveSourceCount"] == 1
    assert payload["totalReviewedPositiveSourceCount"] == 31


def test_v2_resolution_reads_corrected_overlay_and_advances_when_thresholds_pass(tmp_path: Path) -> None:
    _write_v2_bundle(tmp_path, _resolved_items(positive_count=86, total=342, groups=8))

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(
        storage_root=tmp_path,
        output_dir_name="v7_1_positive_diversity_manual_review_resolution_v2",
        overlay_dir_name="v7_1_positive_candidate_mining_expansion_v1",
        overlay_file_name="corrected_label_overlay.json",
        summary_file_name="v7_1_positive_candidate_mining_expansion_summary.json",
        batch_name="v7_1_positive_diversity_manual_review_resolution_v2",
        next_self="v7_1_positive_diversity_manual_review_resolution_v2",
        next_mining="v7_1_positive_candidate_mining_expansion_v2",
        min_new_reviewed_positives=86,
    )

    assert payload["batchName"] == "v7_1_positive_diversity_manual_review_resolution_v2"
    assert payload["reviewCandidateCount"] == 342
    assert payload["previousReviewedPositiveSourceCount"] == 34
    assert payload["newReviewedPositiveSourceCount"] == 86
    assert payload["totalReviewedPositiveSourceCount"] == 120
    assert payload["primaryBlocker"] is None
    assert payload["nextRecommendedNextLever"] == "v7_2_training_manifest_prep"
    assert (root := tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "v7_1_positive_diversity_manual_review_resolution_v2").exists()
    assert (root / "v7_1_positive_diversity_manual_review_resolution_summary.json").exists()


def test_v2_resolution_counts_known_misses_carried_forward_from_mining_summary(tmp_path: Path) -> None:
    items = _resolved_items(positive_count=86, total=342, groups=8)
    for item in items:
        item["source"] = "corrected_bbox_positive_review"
    _write_v2_bundle_with_known_miss_carryforward(tmp_path, items)

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(
        storage_root=tmp_path,
        output_dir_name="v7_1_positive_diversity_manual_review_resolution_v2",
        overlay_dir_name="v7_1_positive_candidate_mining_expansion_v1",
        overlay_file_name="corrected_label_overlay.json",
        summary_file_name="v7_1_positive_candidate_mining_expansion_summary.json",
        batch_name="v7_1_positive_diversity_manual_review_resolution_v2",
        next_self="v7_1_positive_diversity_manual_review_resolution_v2",
        next_mining="v7_1_positive_candidate_mining_expansion_v2",
        min_new_reviewed_positives=86,
    )

    assert payload["knownCropValidationMissesReviewed"] == 9
    assert payload["knownFullPipelineMissesReviewed"] == 2
    assert payload["primaryBlocker"] is None
    assert payload["nextRecommendedNextLever"] == "v7_2_training_manifest_prep"


def test_v2_resolution_stays_pending_on_unresolved_corrected_overlay(tmp_path: Path) -> None:
    _write_v2_bundle(tmp_path, [_item(index, status="pending_review") for index in range(342)])

    payload = resolution.run_v7_1_positive_diversity_manual_review_resolution(
        storage_root=tmp_path,
        output_dir_name="v7_1_positive_diversity_manual_review_resolution_v2",
        overlay_dir_name="v7_1_positive_candidate_mining_expansion_v1",
        overlay_file_name="corrected_label_overlay.json",
        summary_file_name="v7_1_positive_candidate_mining_expansion_summary.json",
        batch_name="v7_1_positive_diversity_manual_review_resolution_v2",
        next_self="v7_1_positive_diversity_manual_review_resolution_v2",
        next_mining="v7_1_positive_candidate_mining_expansion_v2",
        min_new_reviewed_positives=86,
    )

    assert payload["primaryBlocker"] == "v7_1_positive_diversity_manual_review_still_pending"
    assert payload["pendingReviewItemCount"] == 342
    assert payload["roadmapAdvanceAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_resolution_v2"


def test_v2_cli_shortcut_uses_corrected_overlay_defaults() -> None:
    parser = resolution.build_arg_parser()

    args = parser.parse_args(["--v2"])
    options = resolution.resolve_cli_options(args)

    assert options["output_dir_name"] == "v7_1_positive_diversity_manual_review_resolution_v2"
    assert options["overlay_dir_name"] == "v7_1_positive_candidate_mining_expansion_v1"
    assert options["overlay_file_name"] == "corrected_label_overlay.json"
    assert options["summary_file_name"] == "v7_1_positive_candidate_mining_expansion_summary.json"
    assert options["batch_name"] == "v7_1_positive_diversity_manual_review_resolution_v2"
    assert options["next_self"] == "v7_1_positive_diversity_manual_review_resolution_v2"
    assert options["next_mining"] == "v7_1_positive_candidate_mining_expansion_v2"
    assert options["min_new_reviewed_positives"] == 86


def test_v2_cli_shortcut_rejects_conflicting_path_overrides() -> None:
    parser = resolution.build_arg_parser()

    args = parser.parse_args(["--v2", "--overlay-file-name", "custom_overlay.json"])

    with pytest.raises(SystemExit):
        resolution.resolve_cli_options(args)
