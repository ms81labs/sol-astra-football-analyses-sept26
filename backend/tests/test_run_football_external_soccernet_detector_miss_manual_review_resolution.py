from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_detector_miss_manual_review_resolution as resolution


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_root(storage_root: Path) -> Path:
    return storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"


def _row(index: int, *, status: str = "pending_review", bbox: dict[str, float] | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "reviewItemId": f"soccernet-miss-review-{index:04d}",
        "candidateKind": "soccernet_event_window_detector_miss_review",
        "eventLabel": "SHOT" if index % 2 == 0 else "PASS",
        "eventPositionMs": 1000 + index * 1000,
        "gameTime": f"1 - 00:{index:02d}",
        "frameIndex": 25 + index,
        "sourceClipId": "224p.mp4",
        "splitGroupId": f"soccernet-event-window-bucket-{index % 4:04d}",
        "fullFrameImagePath": f"/tmp/full-{index}.jpg",
        "cropImagePath": f"/tmp/crop-{index}.jpg",
        "cropBoundsXyxy": [0.0, 0.0, 398.0, 224.0],
        "reviewStatus": status,
        "sourceFrameBbox": bbox,
        "trainingEligibility": "pending_review",
    }
    if status == "reviewed_real_detector_miss_positive":
        row.update(
            {
                "sourceFrameBbox": bbox or {"x1": 100.0, "y1": 80.0, "x2": 112.0, "y2": 92.0},
                "visibilityClass": "clear",
                "contextTags": ["small_ball", "in_play"],
                "trainingEligibility": "eligible_real_detector_miss_positive",
                "reviewNotes": "",
            }
        )
    elif status != "pending_review":
        row["rejectionReason"] = "not_a_detector_miss"
    return row


def _seed_queue(storage_root: Path, rows: list[dict[str, object]]) -> Path:
    root = _candidate_root(storage_root)
    queue_root = root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1"
    for index, row in enumerate(rows):
        full = Path(str(row["fullFrameImagePath"]))
        crop = Path(str(row["cropImagePath"]))
        full.parent.mkdir(parents=True, exist_ok=True)
        crop.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b"full-image")
        crop.write_bytes(b"crop-image")
        row["fullFrameImagePath"] = str(full)
        row["cropImagePath"] = str(crop)
        row.setdefault("reviewItemId", f"soccernet-miss-review-{index:04d}")
    _write_json(
        queue_root / "detector_miss_capture_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "reviewQueueReady": True,
            "reviewItemCount": len(rows),
            "pendingReviewItemCount": len(rows),
            "missingEvidenceImageCount": 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "v7_3TrainingDataReady": False,
        },
    )
    _write_json(queue_root / "soccernet_detector_miss_review_overlay.json", {"reviewItems": rows})
    return root


def test_resolution_blocks_while_detector_miss_review_is_pending(tmp_path: Path) -> None:
    _seed_queue(tmp_path, [_row(index) for index in range(6)])

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    assert payload["goalAchieved"] is False
    assert payload["roadmapAdvanceAllowed"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_detector_miss_manual_review_still_pending"
    assert payload["reviewCandidateCount"] == 6
    assert payload["pendingReviewItemCount"] == 6
    assert payload["v7_3TrainingDataReady"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_manual_review_resolution"


def test_resolution_unlocks_v73_manifest_when_reviewed_real_miss_boxes_exist(tmp_path: Path) -> None:
    rows = [_row(index, status="reviewed_real_detector_miss_positive") for index in range(3)]
    rows.extend(_row(index + 3, status="reviewed_detector_hit_or_not_miss") for index in range(5))
    _seed_queue(tmp_path, rows)

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    output_root = _candidate_root(tmp_path) / "football_external_soccernet_detector_miss_manual_review_resolution_v1"
    truth = json.loads((output_root / "reviewed_real_detector_miss_truth_additions.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["reviewedRealDetectorMissPositiveCount"] == 3
    assert payload["realDetectorMissCount"] == 3
    assert payload["detectorTrainingNeededFromEvidence"] is True
    assert payload["v7_3TrainingDataReady"] is True
    assert payload["nextRecommendedNextLever"] == "v7_3_training_manifest_prep_from_soccernet_real_misses"
    assert truth["reviewedRealDetectorMissPositiveCount"] == 3
    assert len(truth["rows"]) == 3


def test_resolution_completes_no_training_needed_when_review_finds_no_real_misses(tmp_path: Path) -> None:
    rows = [_row(index, status="reviewed_detector_hit_or_not_miss") for index in range(4)]
    rows.extend(_row(index + 4, status="reviewed_not_ball_or_out_of_play") for index in range(3))
    _seed_queue(tmp_path, rows)

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["reviewedRealDetectorMissPositiveCount"] == 0
    assert payload["detectorTrainingNeededFromEvidence"] is False
    assert payload["v7_3TrainingDataReady"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_no_detector_training_needed_closeout"


def test_resolution_rejects_invalid_real_miss_bbox(tmp_path: Path) -> None:
    rows = [_row(0, status="reviewed_real_detector_miss_positive", bbox={"x1": 20.0, "y1": 10.0, "x2": 150.0, "y2": 30.0})]
    _seed_queue(tmp_path, rows)

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_detector_miss_invalid_bbox"
    assert payload["invalidBBoxCount"] == 1
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_detector_miss_manual_review_resolution"


def test_resolution_rejects_accepted_miss_without_existing_evidence(tmp_path: Path) -> None:
    rows = [_row(0, status="reviewed_real_detector_miss_positive")]
    root = _seed_queue(tmp_path, rows)
    overlay_path = root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1" / "soccernet_detector_miss_review_overlay.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    Path(overlay["reviewItems"][0]["fullFrameImagePath"]).unlink()
    overlay_path.write_text(json.dumps(overlay, indent=2), encoding="utf-8")

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_detector_miss_evidence_missing"
    assert payload["missingEvidenceImageCount"] == 1


def test_resolution_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _seed_queue(tmp_path, [_row(0)])

    payload = resolution.run_football_external_soccernet_detector_miss_manual_review_resolution(
        storage_root=tmp_path
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_detector_miss_review_resolution_gate",
        "soccernet_detector_miss_review_schema_repair",
        "soccernet_detector_miss_resolution_blocker_summary",
    ]
