from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import backend.scripts.serve_football_external_soccernet_detector_miss_review_ui as review_ui


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bbox(seed: int = 50) -> dict[str, float]:
    return {"x1": float(seed), "y1": float(seed + 8), "x2": float(seed + 12), "y2": float(seed + 20)}


def _item(tmp_path: Path, index: int, *, status: str = "pending_review") -> dict[str, object]:
    full = tmp_path / f"soccernet-full-{index}.jpg"
    crop = tmp_path / f"soccernet-crop-{index}.jpg"
    full.write_bytes(b"full-image")
    crop.write_bytes(b"crop-image")
    return {
        "reviewItemId": f"soccernet-miss-review-{index:04d}",
        "candidateKind": "soccernet_event_window_detector_miss_review",
        "reviewStatus": status,
        "eventLabel": "SHOT",
        "eventPositionMs": 1000 + index * 1000,
        "gameTime": f"1 - 00:{index:02d}",
        "sourceClipId": "224p.mp4",
        "frameIndex": 100 + index,
        "splitGroupId": f"soccernet-event-window-bucket-{index % 3:04d}",
        "fullFrameImagePath": str(full),
        "cropImagePath": str(crop),
        "cropBoundsXyxy": [0.0, 0.0, 398.0, 224.0],
        "sourceFrameBbox": None,
        "trainingEligibility": "pending_review",
    }


def _write_review_root(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    queue_root = root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1"
    _write_json(
        queue_root / "detector_miss_capture_summary.json",
        {
            "goalAchieved": True,
            "primaryBlocker": None,
            "reviewQueueReady": True,
            "reviewItemCount": len(items),
            "pendingReviewItemCount": sum(item.get("reviewStatus") == "pending_review" for item in items),
            "missingEvidenceImageCount": 0,
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        queue_root / "soccernet_detector_miss_review_overlay.json",
        {"schemaVersion": "soccernet_detector_miss_review_overlay_v1", "reviewItems": items},
    )
    return root


def test_load_review_state_reports_soccernet_miss_counts_and_image_urls(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(tmp_path, 1), _item(tmp_path, 2, status="reviewed_detector_hit_or_not_miss")])

    state = review_ui.load_review_state(candidate_root=candidate_root)

    assert state["summary"]["reviewItemCount"] == 2
    assert state["summary"]["pendingReviewItemCount"] == 1
    assert state["summary"]["reviewedDetectorHitOrNotMissCount"] == 1
    assert state["reviewItems"][0]["reviewItemId"] == "soccernet-miss-review-0001"
    assert state["reviewItems"][0]["fullFrameImageUrl"] == f"/source-image?path={tmp_path}/soccernet-full-1.jpg"
    assert state["reviewItems"][0]["cropImageUrl"] == f"/source-image?path={tmp_path}/soccernet-crop-1.jpg"


def test_update_review_item_accepts_real_detector_miss_with_bbox(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(tmp_path, 1), _item(tmp_path, 2)])

    result = review_ui.update_review_item(
        candidate_root=candidate_root,
        review_item_id="soccernet-miss-review-0001",
        review_status="reviewed_real_detector_miss_positive",
        source_frame_bbox=_bbox(),
        visibility_class="clear",
        context_tags=["small_ball", "in_play"],
        review_notes="missed in-play ball",
    )

    assert result["summary"]["pendingReviewItemCount"] == 1
    assert result["summary"]["reviewedRealDetectorMissPositiveCount"] == 1
    overlay_path = candidate_root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1" / "soccernet_detector_miss_review_overlay.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    updated = overlay["reviewItems"][0]
    assert updated["reviewStatus"] == "reviewed_real_detector_miss_positive"
    assert updated["sourceFrameBbox"] == _bbox()
    assert updated["trainingEligibility"] == "eligible_real_detector_miss_positive"
    assert updated["bboxSource"] == "manual_reviewed_real_detector_miss"


def test_update_review_item_rejects_non_miss_with_one_click_reason(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(tmp_path, 1)])

    result = review_ui.update_review_item(
        candidate_root=candidate_root,
        review_item_id="soccernet-miss-review-0001",
        review_status="reviewed_not_ball_or_out_of_play",
        rejection_reason="replacement_or_out_of_play_ball",
    )

    assert result["summary"]["pendingReviewItemCount"] == 0
    assert result["summary"]["reviewedNotBallOrOutOfPlayCount"] == 1
    overlay_path = candidate_root / "football_external_soccernet_detector_miss_capture_and_label_queue_v1" / "soccernet_detector_miss_review_overlay.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert overlay["reviewItems"][0]["rejectionReason"] == "replacement_or_out_of_play_ball"
    assert overlay["reviewItems"][0]["trainingEligibility"] == "evidence_only_not_real_detector_miss"


def test_update_review_item_rejects_positive_without_valid_bbox(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(tmp_path, 1)])

    with pytest.raises(review_ui.ReviewUpdateError, match="positive_requires_valid_source_frame_bbox"):
        review_ui.update_review_item(
            candidate_root=candidate_root,
            review_item_id="soccernet-miss-review-0001",
            review_status="reviewed_real_detector_miss_positive",
            source_frame_bbox={"x1": 1.0, "y1": 1.0, "x2": 1.0, "y2": 2.0},
        )


def test_run_resolution_gate_invokes_soccernet_miss_resolver(tmp_path: Path) -> None:
    _write_review_root(tmp_path, [_item(tmp_path, index) for index in range(3)])

    result = review_ui.run_resolution_gate(storage_root=tmp_path)

    assert result["batchName"] == "football_external_soccernet_detector_miss_manual_review_resolution"
    assert result["pendingReviewItemCount"] == 3
    assert result["primaryBlocker"] == "football_external_soccernet_detector_miss_manual_review_still_pending"


def test_soccernet_miss_review_ui_script_runs_directly_in_dry_run_mode(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(tmp_path, 1)])

    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py",
            "--candidate-root",
            str(candidate_root),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["reviewItemCount"] == 1
    assert payload["pendingReviewItemCount"] == 1


def test_image_urls_preserve_reserved_filename_characters(tmp_path: Path) -> None:
    # Break: unescaped &, #, % and + alter the path sent back by the review UI.
    item = _item(tmp_path, 1)
    item["fullFrameImagePath"] = str(tmp_path / "frame &#+%.jpg")
    root = _write_review_root(tmp_path, [item])
    state = review_ui.load_review_state(candidate_root=root)
    assert state["reviewItems"][0]["fullFrameImageUrl"] == f"/source-image?path={tmp_path}/frame%20%26%23%2B%25.jpg"
