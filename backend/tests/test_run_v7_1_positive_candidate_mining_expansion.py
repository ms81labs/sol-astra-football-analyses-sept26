from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_1_positive_candidate_mining_expansion as mining


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _item(index: int, *, status: str, reason: str = "visible_ball_or_possible_ball_requires_tight_bbox_correction_before_training") -> dict[str, object]:
    return {
        "candidateId": f"candidate-{index}",
        "reviewStatus": status,
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 1000 + index * 5,
        "source": "positive_diversity_surplus_temporal_mining",
        "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
        "splitGroupId": f"group-{index % 10}",
        "rejectionReason": reason,
        "reviewFrameImagePath": f"/tmp/frame-{index}.jpg",
        "reviewCropImagePath": f"/tmp/crop-{index}.jpg",
    }


def _write_bundle(tmp_path: Path, *, unclear_count: int = 102) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    expansion_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    resolution_root = root / "v7_1_positive_diversity_manual_review_resolution_v1"
    items = [_item(index, status="review_deferred_unclear") for index in range(unclear_count)]
    items.extend(_item(unclear_count + index, status="reviewed_not_ball", reason="proposed_bbox_does_not_cover_visible_ball") for index in range(12))
    _write_json(expansion_root / "reviewed_label_overlay.json", {"reviewItems": items})
    _write_json(
        resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json",
        {
            "previousReviewedPositiveSourceCount": 30,
            "newReviewedPositiveSourceCount": 4,
            "totalReviewedPositiveSourceCount": 34,
            "reviewDeferredUnclearCount": unclear_count,
            "primaryBlocker": "v7_1_positive_diversity_review_yield_insufficient",
        },
    )
    return root


def _write_v2_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    resolution_root = root / "v7_1_positive_diversity_manual_review_resolution_v2"
    rows = []
    for index, frame_index in enumerate([10, 40, 520, 1040]):
        rows.append(
            {
                "candidateId": f"accepted-{index}",
                "reviewStatus": "reviewed_positive_ball",
                "sourceClipId": "trimed-5min.mp4",
                "frameIndex": frame_index,
                "sourceFrameBbox": {"x1": 20.0, "y1": 20.0, "x2": 36.0, "y2": 36.0},
                "splitGroupId": f"existing-{frame_index // 500}",
                "reviewFrameImagePath": f"/tmp/existing-{index}.jpg",
            }
        )
    _write_json(resolution_root / "reviewed_positive_truth_additions.json", {"rows": rows})
    _write_json(
        resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json",
        {
            "totalReviewedPositiveSourceCount": 103,
            "newReviewedPositiveSourceCount": 69,
            "primaryBlocker": "v7_1_positive_diversity_review_yield_insufficient",
            "nextRecommendedNextLever": "v7_1_positive_candidate_mining_expansion_v2",
        },
    )
    return root


def _write_video(path: Path, *, frames: int = 40, width: int = 96, height: int = 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (width, height))
    for index in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 0] = (index * 7) % 255
        frame[:, :, 1] = np.linspace(0, 255, width, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_candidate_mining_expansion_builds_correction_and_review_package(tmp_path: Path) -> None:
    root = _write_bundle(tmp_path)

    payload = mining.run_v7_1_positive_candidate_mining_expansion(storage_root=tmp_path)

    output_root = root / "v7_1_positive_candidate_mining_expansion_v1"
    overlay = json.loads((output_root / "corrected_label_overlay.json").read_text(encoding="utf-8"))

    assert payload["previousReviewedPositiveSourceCount"] == 34
    assert payload["previousDeferredUnclearCount"] == 102
    assert payload["salvageCorrectionQueueCount"] == 102
    assert payload["newMinedCandidateCount"] >= 200
    assert payload["totalCandidateReviewCount"] >= 300
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_expansion_v2"
    assert overlay["pendingReviewCount"] == payload["totalCandidateReviewCount"]
    assert all(item["reviewStatus"] == "pending_review" for item in overlay["reviewItems"])
    assert (output_root / "correction_review_index.html").exists()


def test_candidate_mining_expansion_blocks_when_salvage_pool_is_too_small(tmp_path: Path) -> None:
    _write_bundle(tmp_path, unclear_count=3)

    payload = mining.run_v7_1_positive_candidate_mining_expansion(storage_root=tmp_path, new_candidate_target=20)

    assert payload["primaryBlocker"] == "v7_1_positive_candidate_correction_queue_missing"
    assert payload["nextRecommendedNextLever"] == "v7_1_source_sampling_expansion"


def test_v2_candidate_mining_excludes_rows_without_extracted_review_images(tmp_path: Path) -> None:
    root = _write_v2_bundle(tmp_path)
    video_path = tmp_path / "video.mp4"
    _write_video(video_path, frames=48)

    payload = mining.run_v7_1_positive_candidate_mining_expansion(
        storage_root=tmp_path,
        output_dir_name="v7_1_positive_candidate_mining_expansion_v2",
        resolution_dir_name="v7_1_positive_diversity_manual_review_resolution_v2",
        new_candidate_target=24,
        video_path=video_path,
        frame_bucket_size=10,
    )

    output_root = root / "v7_1_positive_candidate_mining_expansion_v2"
    overlay = json.loads((output_root / "corrected_label_overlay.json").read_text(encoding="utf-8"))
    review_items = overlay["reviewItems"]

    assert payload["batchName"] == "v7_1_positive_candidate_mining_expansion_v2"
    assert payload["totalCandidateReviewCount"] == 24
    assert payload["reviewRowsExcludedMissingEvidenceCount"] == 0
    assert payload["distinctCandidateSplitGroupCount"] >= 3
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_expansion_v2"
    assert review_items
    assert all(item.get("reviewFrameImagePath") and Path(item["reviewFrameImagePath"]).exists() for item in review_items)
    assert all(item.get("reviewCropImagePath") and Path(item["reviewCropImagePath"]).exists() for item in review_items)
    assert all(item["reviewStatus"] == "pending_review" for item in review_items)
