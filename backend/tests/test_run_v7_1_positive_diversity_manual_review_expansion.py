from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_positive_diversity_manual_review_expansion as expansion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate(frame: int, *, candidate_id: str | None = None, source: str = "temporal_neighbor") -> dict[str, object]:
    return {
        "candidateId": candidate_id or f"candidate-{frame}",
        "candidateStatus": "proposed_positive_candidate",
        "source": source,
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame,
        "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
        "recommendedCropVariants": [192, 256, 384],
        "labelPolicy": "requires_human_review_before_training",
    }


def _write_refresh_bundle(tmp_path: Path, *, candidate_count: int = 89) -> Path:
    root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    refresh_root = root / "v7_1_positive_diversity_refresh_v1"
    manifest_root = root / "v7_1_crop_manifest_consistency_refresh_v1"
    candidates = []
    for index in range(candidate_count):
        source = "v7_1_crop_probe_precision_guardrail_audit" if index < 9 else "temporal_neighbor"
        if 9 <= index < 11:
            source = "v7_1_full_pipeline_non_promotion_eval"
        candidates.append(_candidate(240 + index * 5, source=source))
    _write_json(refresh_root / "positive_review_queue.json", {"candidateCount": len(candidates), "candidates": candidates})
    _write_json(
        refresh_root / "v7_1_positive_diversity_refresh_summary.json",
        {
            "previousReviewedPositiveSourceCount": 30,
            "totalReviewedPositiveSourceCount": 30,
            "positiveReviewQueueCandidateCount": candidate_count,
            "knownCropValidationMissesIncluded": 9,
            "knownFullPipelineMissesIncluded": 2,
            "secondaryConcernCarriedForward": "v7_1_validation_positive_recall_limited",
        },
    )
    _write_json(
        manifest_root / "v7_1_local_crop_training_manifest.json",
        {
            "reviewedPositiveSourceCount": 30,
            "positiveCropExamples": [
                {
                    "exampleId": f"existing-{index}-256",
                    "sourceClipId": "trimed-5min.mp4",
                    "frameIndex": 100 + index * 5,
                    "sourceFrameBbox": {"x1": 100.0, "y1": 120.0, "x2": 116.0, "y2": 136.0},
                    "splitGroupId": f"existing-group-{index // 5}",
                    "split": "train",
                    "cropSizePx": 256,
                }
                for index in range(30)
            ],
            "unsafeFullFrameNegativeExportCount": 0,
            "fullFrameEmptyLabelNegativeExportCount": 0,
        },
    )
    return root


def test_manual_review_expansion_mines_surplus_and_stops_pending(tmp_path: Path) -> None:
    root = _write_refresh_bundle(tmp_path, candidate_count=89)

    payload = expansion.run_v7_1_positive_diversity_manual_review_expansion(storage_root=tmp_path)

    output_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    overlay = json.loads((output_root / "reviewed_label_overlay.json").read_text(encoding="utf-8"))

    assert payload["batchStatus"] == "manual_review_pending"
    assert payload["reviewQueueCandidateCount"] >= 140
    assert payload["pendingReviewCount"] == payload["reviewQueueCandidateCount"]
    assert payload["trainingExecuted"] is False
    assert payload["promotionReady"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "manual_review_required"
    assert overlay["pendingReviewCount"] == payload["pendingReviewCount"]
    assert (output_root / "positive_hard_case_overlay_contact_sheet_manifest.json").exists()


def test_manual_review_expansion_resolves_to_v72_when_thresholds_pass(tmp_path: Path) -> None:
    root = _write_refresh_bundle(tmp_path, candidate_count=150)
    output_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    decisions = []
    for index in range(150):
        status = "reviewed_positive_ball" if index < 96 else "reviewed_not_ball"
        source = "v7_1_crop_probe_precision_guardrail_audit" if index < 9 else "temporal_neighbor"
        if 9 <= index < 11:
            source = "v7_1_full_pipeline_non_promotion_eval"
        decisions.append({**_candidate(1000 + index * 10, source=source), "reviewStatus": status})
    _write_json(output_root / "reviewed_label_overlay.json", {"reviewItems": decisions})

    payload = expansion.run_v7_1_positive_diversity_manual_review_expansion(storage_root=tmp_path)

    assert payload["batchStatus"] == "review_resolved"
    assert payload["primaryBlocker"] is None
    assert payload["newReviewedPositiveSourceCount"] == 96
    assert payload["totalReviewedPositiveSourceCount"] == 126
    assert payload["knownCropValidationMissesReviewed"] == 9
    assert payload["knownFullPipelineMissesReviewed"] == 2
    assert payload["nextRecommendedNextLever"] == "v7_2_training_manifest_prep"


def test_manual_review_expansion_blocks_low_review_yield(tmp_path: Path) -> None:
    root = _write_refresh_bundle(tmp_path, candidate_count=140)
    output_root = root / "v7_1_positive_diversity_manual_review_expansion_v1"
    decisions = []
    for index in range(140):
        status = "reviewed_positive_ball" if index < 54 else "reviewed_not_ball"
        source = "v7_1_crop_probe_precision_guardrail_audit" if index < 9 else "temporal_neighbor"
        if 9 <= index < 11:
            source = "v7_1_full_pipeline_non_promotion_eval"
        decisions.append({**_candidate(1000 + index * 10, source=source), "reviewStatus": status})
    _write_json(output_root / "reviewed_label_overlay.json", {"reviewItems": decisions})

    payload = expansion.run_v7_1_positive_diversity_manual_review_expansion(storage_root=tmp_path)

    assert payload["batchStatus"] == "review_resolved"
    assert payload["primaryBlocker"] == "v7_1_positive_diversity_review_yield_insufficient"
    assert payload["totalReviewedPositiveSourceCount"] == 84
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_candidate_mining_expansion"
