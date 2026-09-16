from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

import backend.scripts.run_v7_1_positive_diversity_review_evidence_package as evidence


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_review_evidence_package_adds_images_without_changing_decisions(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    expansion_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    overlay_path = expansion_root / "reviewed_label_overlay.json"
    _write_json(
        overlay_path,
        {
            "reviewItemCount": 2,
            "pendingReviewCount": 2,
            "reviewItems": [
                {
                    "candidateId": "candidate-a",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": 10,
                    "reviewStatus": "pending_review",
                    "sourceFrameBbox": {"x1": 20.0, "y1": 30.0, "x2": 36.0, "y2": 46.0},
                },
                {
                    "candidateId": "candidate-b",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": 20,
                    "reviewStatus": "pending_review",
                    "sourceFrameBbox": {"x1": 40.0, "y1": 50.0, "x2": 58.0, "y2": 68.0},
                },
            ],
        },
    )

    def fake_extract_frame(*, video_path: Path, frame_index: int):
        return Image.new("RGB", (120, 90), (30 + frame_index, 100, 80))

    monkeypatch.setattr(evidence, "_extract_frame_image", fake_extract_frame)

    payload = evidence.run_v7_1_positive_diversity_review_evidence_package(
        storage_root=tmp_path,
        video_path=tmp_path / "videos" / "trimed-5min.mp4",
    )

    updated = json.loads(overlay_path.read_text(encoding="utf-8"))

    assert payload["reviewItemCount"] == 2
    assert payload["frameImageCount"] == 2
    assert payload["cropImageCount"] == 2
    assert payload["reviewDecisionMutationCount"] == 0
    assert updated["pendingReviewCount"] == 2
    assert all(item["reviewStatus"] == "pending_review" for item in updated["reviewItems"])
    assert all(Path(item["reviewFrameImagePath"]).exists() for item in updated["reviewItems"])
    assert all(Path(item["reviewCropImagePath"]).exists() for item in updated["reviewItems"])
    assert (root / "v7_1_positive_diversity_review_evidence_package_v1" / "review_index.html").exists()

