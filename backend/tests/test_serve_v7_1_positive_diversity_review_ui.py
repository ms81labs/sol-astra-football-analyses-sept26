from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import backend.scripts.serve_v7_1_positive_diversity_review_ui as review_ui


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bbox(seed: int = 100) -> dict[str, float]:
    return {"x1": float(seed), "y1": float(seed + 10), "x2": float(seed + 16), "y2": float(seed + 26)}


def _item(index: int, *, status: str = "pending_review", kind: str = "off_bbox_visible_ball_correction_queue") -> dict[str, object]:
    return {
        "candidateId": f"candidate-{index}",
        "candidateKind": kind,
        "reviewStatus": status,
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": 1000 + index * 5,
        "sourceFrameBbox": _bbox(index + 100),
        "originalSourceFrameBbox": _bbox(index + 100),
        "reviewFrameImagePath": f"/tmp/frame-{index}.jpg",
        "reviewCropImagePath": f"/tmp/crop-{index}.jpg",
        "splitGroupId": f"group-{index % 8}",
        "trainingEligibility": "pending_review",
    }


def _write_review_root(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    mining_root = root / "v7_1_positive_candidate_mining_expansion_v1"
    _write_json(
        mining_root / "corrected_label_overlay.json",
        {
            "batchName": "v7_1_positive_candidate_mining_expansion",
            "reviewItemCount": len(items),
            "pendingReviewCount": sum(item.get("reviewStatus") == "pending_review" for item in items),
            "reviewItems": items,
        },
    )
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


def _write_review_root_with_v2_package(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = _write_review_root(tmp_path, [_item(99, status="reviewed_not_ball")])
    mining_root = root / "v7_1_positive_candidate_mining_expansion_v2"
    _write_json(
        mining_root / "corrected_label_overlay.json",
        {
            "batchName": "v7_1_positive_candidate_mining_expansion_v2",
            "reviewItemCount": len(items),
            "pendingReviewCount": sum(item.get("reviewStatus") == "pending_review" for item in items),
            "reviewItems": items,
        },
    )
    _write_json(
        mining_root / "v7_1_positive_candidate_mining_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 103,
            "totalCandidateReviewCount": len(items),
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def _write_review_root_with_v3_package(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    root = _write_review_root_with_v2_package(tmp_path, [_item(7)])
    mining_root = root / "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1"
    _write_json(
        mining_root / "corrected_label_overlay.json",
        {
            "batchName": "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered",
            "reviewItemCount": len(items),
            "pendingReviewCount": sum(item.get("reviewStatus") == "pending_review" for item in items),
            "reviewItems": items,
        },
    )
    _write_json(
        mining_root / "v7_1_positive_candidate_mining_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 103,
            "totalCandidateReviewCount": len(items),
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def test_load_review_state_reports_corrected_overlay_counts(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(1), _item(2, status="reviewed_not_ball")])

    state = review_ui.load_review_state(candidate_root=candidate_root)

    assert state["summary"]["reviewItemCount"] == 2
    assert state["summary"]["pendingReviewItemCount"] == 1
    assert state["summary"]["reviewedNotBallCount"] == 1
    assert state["reviewItems"][0]["candidateId"] == "candidate-1"
    assert state["reviewItems"][0]["frameImageUrl"] == "/source-image?path=/tmp/frame-1.jpg"


def test_load_review_state_prefers_v2_package_when_present(tmp_path: Path) -> None:
    candidate_root = _write_review_root_with_v2_package(tmp_path, [_item(7), _item(8)])

    state = review_ui.load_review_state(candidate_root=candidate_root)

    assert state["summary"]["reviewItemCount"] == 2
    assert state["summary"]["pendingReviewItemCount"] == 2
    assert state["reviewItems"][0]["candidateId"] == "candidate-7"
    assert "v7_1_positive_candidate_mining_expansion_v2" in state["overlayPath"]


def test_load_review_state_prefers_v3_pitch_filtered_package_when_present(tmp_path: Path) -> None:
    candidate_root = _write_review_root_with_v3_package(tmp_path, [_item(12), _item(13)])

    state = review_ui.load_review_state(candidate_root=candidate_root)

    assert state["summary"]["reviewItemCount"] == 2
    assert state["reviewItems"][0]["candidateId"] == "candidate-12"
    assert "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1" in state["overlayPath"]


def test_update_review_item_accepts_corrected_positive_with_tight_bbox(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(1), _item(2)])

    result = review_ui.update_review_item(
        candidate_root=candidate_root,
        candidate_id="candidate-1",
        review_status="reviewed_positive_ball",
        source_frame_bbox={"x1": 120.0, "y1": 130.0, "x2": 136.0, "y2": 146.0},
        bbox_source="manual_corrected_from_off_bbox_candidate",
        visibility_class="clear",
        context_tags=["small_ball", "near_player_feet"],
        review_notes="corrected nearby ball",
    )

    assert result["summary"]["pendingReviewItemCount"] == 1
    assert result["summary"]["newReviewedPositiveRowCount"] == 1
    overlay = json.loads((candidate_root / "v7_1_positive_candidate_mining_expansion_v1" / "corrected_label_overlay.json").read_text())
    updated = overlay["reviewItems"][0]
    assert updated["reviewStatus"] == "reviewed_positive_ball"
    assert updated["sourceFrameBbox"] == {"x1": 120.0, "y1": 130.0, "x2": 136.0, "y2": 146.0}
    assert updated["trainingEligibility"] == "eligible_positive_truth"
    assert updated["bboxSource"] == "manual_corrected_from_off_bbox_candidate"
    assert updated["originalCandidateBboxWasOffTarget"] is True


def test_update_review_item_rejects_positive_without_valid_bbox(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(1)])

    with pytest.raises(review_ui.ReviewUpdateError, match="positive_requires_valid_source_frame_bbox"):
        review_ui.update_review_item(
            candidate_root=candidate_root,
            candidate_id="candidate-1",
            review_status="reviewed_positive_ball",
            source_frame_bbox={"x1": 1.0, "y1": 2.0, "x2": 1.0, "y2": 3.0},
        )


def test_update_review_item_records_non_positive_reasons(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(1)])

    result = review_ui.update_review_item(
        candidate_root=candidate_root,
        candidate_id="candidate-1",
        review_status="review_deferred_unclear",
        rejection_reason="ball_not_visible_enough_to_box_confidently",
    )

    assert result["summary"]["pendingReviewItemCount"] == 0
    overlay = json.loads((candidate_root / "v7_1_positive_candidate_mining_expansion_v1" / "corrected_label_overlay.json").read_text())
    assert overlay["reviewItems"][0]["rejectionReason"] == "ball_not_visible_enough_to_box_confidently"
    assert overlay["reviewItems"][0]["trainingEligibility"] == "evidence_only_not_positive_training_truth"


def test_run_resolution_gate_invokes_v2_resolver(tmp_path: Path) -> None:
    _write_review_root(tmp_path, [_item(index) for index in range(3)])

    result = review_ui.run_resolution_gate(storage_root=tmp_path)

    assert result["batchName"] == "v7_1_positive_diversity_manual_review_resolution_v2"
    assert result["pendingReviewItemCount"] == 3
    assert result["nextRecommendedNextLever"] == "v7_1_positive_diversity_manual_review_resolution_v2"


def test_v7_review_ui_script_runs_directly_in_dry_run_mode(tmp_path: Path) -> None:
    candidate_root = _write_review_root(tmp_path, [_item(1)])

    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/serve_v7_1_positive_diversity_review_ui.py",
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
    item = _item(1)
    item["reviewFrameImagePath"] = str(tmp_path / "frame &#+%.jpg")
    root = _write_review_root(tmp_path, [item])
    state = review_ui.load_review_state(candidate_root=root)
    assert state["reviewItems"][0]["frameImageUrl"] == f"/source-image?path={tmp_path}/frame%20%26%23%2B%25.jpg"
