from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered as v3


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_video(path: Path, *, frames: int = 80, width: int = 128, height: int = 72) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (width, height))
    for index in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 1] = 80 + (index % 80)
        frame[:, :, 2] = np.linspace(0, 255, width, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _candidate(index: int, *, frame_index: int, bbox: dict[str, float] | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "candidateId": f"v2-candidate-{index}",
        "candidateKind": "new_temporal_group_source_sampling_candidate",
        "reviewStatus": "pending_review",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_index,
        "splitGroupId": f"old-group-{index % 4}",
        "trainingEligibility": "pending_review",
    }
    if bbox is not None:
        row["sourceFrameBbox"] = bbox
    return row


def _write_bundle(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    v2_root = root / "v7_1_positive_candidate_mining_expansion_v2"
    resolution_root = root / "v7_1_positive_diversity_manual_review_resolution_v2"
    video_path = tmp_path / "trimed-5min.mp4"
    _write_video(video_path)
    items = [
        _candidate(0, frame_index=10, bbox=None),
        _candidate(1, frame_index=20, bbox={"x1": 2.0, "y1": 1.0, "x2": 18.0, "y2": 17.0}),
    ]
    _write_json(v2_root / "corrected_label_overlay.json", {"reviewItems": items})
    _write_json(
        v2_root / "v7_1_positive_candidate_mining_expansion_summary.json",
        {
            "previousReviewedPositiveSourceCount": 103,
            "totalCandidateReviewCount": len(items),
            "knownCropValidationMissesCarriedForward": 9,
            "knownFullPipelineMissesCarriedForward": 2,
            "trainingExecuted": False,
            "promotionReady": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        resolution_root / "reviewed_positive_truth_additions.json",
        {
            "rows": [
                {
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": 10,
                    "sourceFrameBbox": {"x1": 20.0, "y1": 20.0, "x2": 36.0, "y2": 36.0},
                }
            ]
        },
    )
    _write_json(
        resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json",
        {
            "totalReviewedPositiveSourceCount": 103,
            "newReviewedPositiveSourceCount": 69,
            "knownCropValidationMissesReviewed": 9,
            "knownFullPipelineMissesReviewed": 2,
            "primaryBlocker": "v7_1_positive_diversity_review_yield_insufficient",
        },
    )
    return root, video_path


def test_pitch_filtered_v3_writes_reviewable_rows_and_filters_replacement_risk(tmp_path: Path) -> None:
    root, video_path = _write_bundle(tmp_path)

    payload = v3.run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered(
        storage_root=tmp_path,
        video_path=video_path,
        candidate_target=24,
        frame_bucket_size=10,
    )

    output_root = root / "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1"
    overlay = json.loads((output_root / "pitch_filtered_corrected_label_overlay.json").read_text(encoding="utf-8"))
    replacement = json.loads((output_root / "replacement_ball_filter_audit.json").read_text(encoding="utf-8"))
    rows = overlay["reviewItems"]

    assert payload["batchName"] == "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered"
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["knownCropValidationMissesCarriedForward"] == 9
    assert payload["knownFullPipelineMissesCarriedForward"] == 2
    assert payload["reviewRowsExcludedMissingEvidenceCount"] == 0
    assert payload["replacementBallEvidenceOnlyCount"] == 0
    assert payload["totalCandidateReviewCount"] >= 24
    assert payload["distinctCandidateSplitGroupCount"] >= 4
    assert rows
    assert all(row["reviewStatus"] == "pending_review" for row in rows)
    assert all(row["trainingEligibility"] == "pending_review" for row in rows)
    assert all(row.get("pitchRegionClass") for row in rows)
    assert all(row.get("playabilityClass") == "reviewable_in_play_candidate" for row in rows)
    assert all(row.get("replacementBallRisk") in {"low", "medium"} for row in rows)
    assert all(Path(row["reviewFrameImagePath"]).exists() for row in rows)
    assert all(Path(row["reviewCropImagePath"]).exists() for row in rows)
    assert replacement["replacementBallEvidenceOnlyCount"] == 0


def test_pitch_filter_marks_edge_boxes_as_evidence_only() -> None:
    reviewable, evidence_only = v3._annotate_pitch_fields(
        [
            {
                "candidateId": "side-replacement",
                "reviewStatus": "pending_review",
                "sourceFrameBbox": {"x1": 2.0, "y1": 1.0, "x2": 18.0, "y2": 17.0},
                "trainingEligibility": "pending_review",
            },
            {
                "candidateId": "center-candidate",
                "reviewStatus": "pending_review",
                "sourceFrameBbox": {"x1": 2000.0, "y1": 500.0, "x2": 2016.0, "y2": 516.0},
                "trainingEligibility": "pending_review",
            },
        ]
    )

    assert [row["candidateId"] for row in evidence_only] == ["side-replacement"]
    assert evidence_only[0]["trainingEligibility"] == "evidence_only_not_positive_training_truth"
    assert reviewable[0]["candidateId"] == "center-candidate"
    assert reviewable[0]["playabilityClass"] == "reviewable_in_play_candidate"
