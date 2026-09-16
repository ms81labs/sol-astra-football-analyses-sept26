from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_football_external_soccernet_detector_miss_capture_and_label_queue as miss_queue


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_tiny_video(path: Path, *, frame_count: int = 40) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (160, 90))
    assert writer.isOpened()
    for idx in range(frame_count):
        frame = np.full((90, 160, 3), 24 + idx, dtype=np.uint8)
        cv2.putText(frame, str(idx), (8, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        writer.write(frame)
    writer.release()


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _seed_inputs(
    storage_root: Path,
    *,
    decision_ready: bool = True,
    sample_ready: bool = True,
    label_ready: bool = True,
    annotation_count: int = 12,
) -> Path:
    root = _candidate_root(storage_root)
    if decision_ready:
        _write_json(
            root
            / "football_external_soccernet_real_sample_product_pipeline_training_decision_v1"
            / "soccernet_real_sample_product_pipeline_training_decision_summary.json",
            {
                "goalAchieved": True,
                "primaryBlocker": None,
                "controlledRealSampleMaterialized": True,
                "actualProductPipelinePassed": True,
                "detectorTrainingNeededFromEvidence": False,
                "v7_3TrainingDataReady": False,
                "trainingExecuted": False,
                "promotionMutationExecuted": False,
                "runtimeDefaultMutationExecuted": False,
                "nextRecommendedNextLever": "football_external_soccernet_detector_miss_capture_and_label_queue",
            },
        )
    video_path = (
        root
        / "football_external_soccernet_video_member_extract_v1"
        / "extracted_video"
        / "test_game"
        / "224p.mp4"
    )
    if sample_ready:
        _write_tiny_video(video_path)
    _write_json(
        root / "football_external_soccernet_video_member_extract_v1" / "extracted_video_member_inventory.json",
        {
            "archiveDownloadExecuted": False,
            "extractedVideoFileCount": 1 if sample_ready else 0,
            "extractedVideoFiles": [
                {
                    "memberPath": "test_game/224p.mp4",
                    "relativePath": "extracted_video/test_game/224p.mp4",
                    "sizeBytes": video_path.stat().st_size if video_path.exists() else 0,
                    "mp4FtypPresent": True,
                }
            ]
            if sample_ready
            else [],
        },
    )
    if label_ready:
        annotations = []
        labels = ["SHOT", "CROSS", "HIGH PASS", "HEADER", "PASS", "DRIVE"]
        for idx in range(annotation_count):
            annotations.append(
                {
                    "gameTime": f"1 - 00:{idx:02d}",
                    "label": labels[idx % len(labels)],
                    "position": str(500 + idx * 250),
                    "team": "home" if idx % 2 == 0 else "away",
                    "visibility": "visible",
                }
            )
        _write_json(
            root
            / "football_external_soccernet_zip_label_member_extract_v1"
            / "extracted_labels"
            / "test_game"
            / "Labels-ball.json",
            {"annotations": annotations},
        )
    _write_json(
        root / "football_external_soccernet_full_analysis_execution_v1" / "full_analysis_execution_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "fullAnalysisExecutionExecuted": True,
            "processedFrameCount": 40,
            "reportedFrameCount": 40,
            "unreadableFrameCount": 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    return root


def test_miss_capture_queue_generates_pending_event_rows_with_evidence(tmp_path: Path) -> None:
    root = _seed_inputs(tmp_path)

    payload = miss_queue.run_football_external_soccernet_detector_miss_capture_and_label_queue(
        storage_root=tmp_path,
        target_review_item_count=8,
    )

    output_root = root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1"
    queue = json.loads((output_root / "soccernet_event_window_review_queue.json").read_text(encoding="utf-8"))
    overlay = json.loads((output_root / "soccernet_detector_miss_review_overlay.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["reviewQueueReady"] is True
    assert payload["reviewItemCount"] == 8
    assert payload["missingEvidenceImageCount"] == 0
    assert payload["pendingReviewItemCount"] == 8
    assert payload["reviewedRealDetectorMissPositiveCount"] == 0
    assert payload["v7_3TrainingDataReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_manual_review_resolution"

    rows = queue["reviewItems"]
    assert len(rows) == 8
    assert len(overlay["reviewItems"]) == 8
    for row in rows:
        assert row["reviewStatus"] == "pending_review"
        assert row["candidateKind"] == "soccernet_event_window_detector_miss_review"
        assert row["trainingEligibility"] == "pending_review"
        assert Path(row["fullFrameImagePath"]).exists()
        assert Path(row["cropImagePath"]).exists()
        assert row["sourceFrameBbox"] is None


def test_miss_capture_queue_blocks_without_training_decision(tmp_path: Path) -> None:
    _seed_inputs(tmp_path, decision_ready=False)

    payload = miss_queue.run_football_external_soccernet_detector_miss_capture_and_label_queue(
        storage_root=tmp_path,
        target_review_item_count=4,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_real_sample_training_decision_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_real_sample_product_pipeline_training_decision"
    assert payload["trainingExecuted"] is False


def test_miss_capture_queue_blocks_without_sample_or_labels(tmp_path: Path) -> None:
    _seed_inputs(tmp_path, sample_ready=False, label_ready=False)

    payload = miss_queue.run_football_external_soccernet_detector_miss_capture_and_label_queue(
        storage_root=tmp_path,
        target_review_item_count=4,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_real_sample_materialization_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_real_sample_download_execution"


def test_miss_capture_queue_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _seed_inputs(tmp_path)

    payload = miss_queue.run_football_external_soccernet_detector_miss_capture_and_label_queue(
        storage_root=tmp_path,
        target_review_item_count=2,
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_event_window_miss_capture_queue",
        "soccernet_event_queue_sampling_repair",
        "soccernet_miss_capture_blocker_summary",
    ]
