from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_LANE_ROOT = DEFAULT_SUITE_ROOT / "v7_training_data_lane_v1"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "touchline_detector_candidate_v7_training_data_refresh_v1"
DEFAULT_MIN_REVIEWED_POSITIVE_FRAMES = 20


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _frame_key(row: dict[str, Any]) -> tuple[str, int | str]:
    source_clip_id = str(row.get("sourceClipId") or row.get("source") or "unknown")
    frame_index = row.get("frameIndex")
    if isinstance(frame_index, int):
        return source_clip_id, frame_index
    try:
        return source_clip_id, int(str(frame_index))
    except (TypeError, ValueError):
        return source_clip_id, str(frame_index)


def _bbox_centroid(bbox: dict[str, Any] | None) -> dict[str, float] | None:
    if not bbox:
        return None
    try:
        x1 = float(bbox["x1"])
        y1 = float(bbox["y1"])
        x2 = float(bbox["x2"])
        y2 = float(bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"x": round((x1 + x2) / 2.0, 3), "y": round((y1 + y2) / 2.0, 3)}


def _split_for_index(index: int) -> str:
    return "validation" if index % 5 == 4 else "train"


def _normalize_positive(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    bbox = row.get("reviewedBBox") if isinstance(row.get("reviewedBBox"), dict) else row.get("seedBBox")
    bbox = dict(bbox) if isinstance(bbox, dict) else None
    return {
        "exampleId": f"v7-positive-{row.get('sourceClipId', 'unknown')}-{row.get('frameIndex')}",
        "frameIndex": row.get("frameIndex"),
        "sourceClipId": row.get("sourceClipId"),
        "timestampSeconds": row.get("timestampSeconds"),
        "bbox": bbox,
        "bboxCentroid": _bbox_centroid(bbox),
        "label": "ball",
        "truthUse": "reviewed_positive_training_seed",
        "reviewDecision": row.get("reviewDecision"),
        "reviewItemId": row.get("reviewItemId"),
        "candidateFrameId": row.get("candidateFrameId"),
        "windowId": row.get("windowId"),
        "lineage": row.get("lineage") if isinstance(row.get("lineage"), dict) else {},
        "split": _split_for_index(index),
    }


def _normalize_negative(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    bbox = row.get("reviewedBBox") if isinstance(row.get("reviewedBBox"), dict) else row.get("seedBBox")
    bbox = dict(bbox) if isinstance(bbox, dict) else None
    return {
        "exampleId": f"v7-negative-{row.get('sourceClipId', 'unknown')}-{row.get('frameIndex')}-{index}",
        "frameIndex": row.get("frameIndex"),
        "sourceClipId": row.get("sourceClipId"),
        "timestampSeconds": row.get("timestampSeconds"),
        "bbox": bbox,
        "bboxCentroid": _bbox_centroid(bbox),
        "label": "not_ball_refuted_seed",
        "truthUse": "negative_only_refuted_seed",
        "reviewDecision": row.get("reviewDecision"),
        "reviewItemId": row.get("reviewItemId"),
        "candidateFrameId": row.get("candidateFrameId"),
        "refutationUse": "negative_only_do_not_use_as_positive",
        "split": _split_for_index(index),
    }


def _normalize_review_candidate(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    return {
        "reviewItemId": f"v7-denominator-review-{row.get('sourceClipId', 'unknown')}-{row.get('frameIndex')}",
        "frameIndex": row.get("frameIndex"),
        "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
        "reviewDecision": "pending_review",
        "truthUse": "pending_denominator_review",
        "priority": index + 1,
        "gapClass": row.get("gapClass"),
        "classification": row.get("classification"),
        "reviewTruthClass": row.get("reviewTruthClass"),
        "baselineAccepted": row.get("baselineAccepted"),
        "promotedAccepted": row.get("promotedAccepted"),
    }


def _dedupe_by_frame(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, int | str], dict[str, Any]] = {}
    for row in rows:
        deduped.setdefault(_frame_key(row), row)
    return [deduped[key] for key in sorted(deduped, key=lambda item: (item[0], str(item[1])))]


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Touchline Detector Candidate V7 Training Data Refresh",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- refutedNegativeFrameCount: {summary.get('refutedNegativeFrameCount')}",
            f"- pendingReviewFrameCount: {summary.get('pendingReviewFrameCount')}",
            f"- hardMiningCandidateCount: {summary.get('hardMiningCandidateCount')}",
            f"- trainingReady: {summary.get('trainingReady')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def _select_next_family(
    *,
    training_ready: bool,
    pending_review_count: int,
    reviewed_positive_count: int,
    min_reviewed_positive_frames: int,
) -> str:
    if training_ready:
        return "touchline_detector_candidate_v7_training_prep"
    if pending_review_count > 0:
        return "manual_review_denominator_expansion"
    if reviewed_positive_count < min_reviewed_positive_frames:
        return "manual_review_positive_expansion"
    return "v7_training_data_blocker_summary"


def run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
    *,
    lane_root: Path = DEFAULT_LANE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    min_reviewed_positive_frames: int = DEFAULT_MIN_REVIEWED_POSITIVE_FRAMES,
) -> dict[str, Any]:
    lane_root = Path(lane_root)
    output_root = Path(output_root)
    lane_manifest = _load_json_dict(lane_root / "v7_training_data_manifest.json")
    lane_summary = _load_json_dict(lane_root / "v7_training_data_lane_summary.json")

    reviewed_positive_rows = _dedupe_by_frame(_list_dicts(lane_manifest.get("reviewedPositiveFrames")))
    refuted_negative_rows = _dedupe_by_frame(_list_dicts(lane_manifest.get("refutedNegativeFrames")))
    unreviewed_rows = _dedupe_by_frame(_list_dicts(lane_manifest.get("unreviewedDenominatorFrames")))
    hard_mining_rows = _dedupe_by_frame(_list_dicts(lane_manifest.get("hardMiningCandidateFrames")))

    positive_keys = {_frame_key(row) for row in reviewed_positive_rows}
    negative_keys = {_frame_key(row) for row in refuted_negative_rows}
    refuted_reused_as_positive = bool(positive_keys & negative_keys)

    positive_examples = [
        _normalize_positive(row, index=index)
        for index, row in enumerate(reviewed_positive_rows)
        if _frame_key(row) not in negative_keys
    ]
    negative_examples = [
        _normalize_negative(row, index=index)
        for index, row in enumerate(refuted_negative_rows)
    ]
    review_queue = [
        _normalize_review_candidate(row, index=index)
        for index, row in enumerate(unreviewed_rows)
        if _frame_key(row) not in positive_keys and _frame_key(row) not in negative_keys
    ]
    hard_mining_manifest = {
        "hardMiningCandidateCount": len(hard_mining_rows),
        "candidateFrames": [
            {
                **_normalize_review_candidate(row, index=index),
                "truthUse": "hard_mining_candidate",
            }
            for index, row in enumerate(hard_mining_rows)
            if _frame_key(row) not in negative_keys
        ],
    }

    weak_evidence_reasons: list[str] = []
    if len(positive_examples) < min_reviewed_positive_frames:
        weak_evidence_reasons.append("reviewed_positive_count_below_minimum")
    if review_queue:
        weak_evidence_reasons.append("unreviewed_denominator_frames_pending")
    if refuted_reused_as_positive:
        weak_evidence_reasons.append("refuted_seed_positive_overlap")

    training_ready = not weak_evidence_reasons
    next_family = _select_next_family(
        training_ready=training_ready,
        pending_review_count=len(review_queue),
        reviewed_positive_count=len(positive_examples),
        min_reviewed_positive_frames=min_reviewed_positive_frames,
    )
    generated_at = _utc_now_iso()
    dataset_manifest = {
        "generatedAt": generated_at,
        "batchName": "touchline_detector_candidate_v7_training_data_refresh",
        "positiveTruthPolicy": "reviewed_positive_only",
        "negativeTruthPolicy": "refuted_seed_negative_only",
        "pendingTruthPolicy": "unreviewed_denominator_frames_require_review",
        "positiveExampleCount": len(positive_examples),
        "positiveExamples": positive_examples,
        "negativeExampleCount": len(negative_examples),
        "negativeExamples": negative_examples,
        "pendingReviewFrameCount": len(review_queue),
        "pendingReviewFrames": review_queue,
        "refutedSeedsReusedAsPositiveEvidence": refuted_reused_as_positive,
    }
    quality_gate = {
        "generatedAt": generated_at,
        "trainingReady": training_ready,
        "minReviewedPositiveFrames": min_reviewed_positive_frames,
        "reviewedPositiveFrameCount": len(positive_examples),
        "refutedNegativeFrameCount": len(negative_examples),
        "pendingReviewFrameCount": len(review_queue),
        "hardMiningCandidateCount": hard_mining_manifest["hardMiningCandidateCount"],
        "weakEvidenceReasons": weak_evidence_reasons,
        "nextCorrectiveFamily": next_family,
    }
    source_manifest_delta = {
        "generatedAt": generated_at,
        "mutationPolicy": "proposal_only_do_not_mutate_frozen_manifest",
        "proposedDatasetId": "touchline_detector_candidate_v7_training_data_refresh_v1",
        "sourceClipIds": sorted(
            {
                str(row.get("sourceClipId") or "trimed-5min.mp4")
                for row in [*reviewed_positive_rows, *refuted_negative_rows, *unreviewed_rows]
            }
        ),
        "positiveFrameCount": len(positive_examples),
        "negativeFrameCount": len(negative_examples),
        "pendingReviewFrameCount": len(review_queue),
        "hardMiningCandidateCount": hard_mining_manifest["hardMiningCandidateCount"],
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": "touchline_detector_candidate_v7_training_data_refresh",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "v7_dataset_manifest_refresh",
        "batchStatus": "succeeded" if training_ready else "packaged_not_train_ready",
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "reviewedPositiveFrameCount": len(positive_examples),
        "refutedNegativeFrameCount": len(negative_examples),
        "pendingReviewFrameCount": len(review_queue),
        "hardMiningCandidateCount": hard_mining_manifest["hardMiningCandidateCount"],
        "trainingReady": training_ready,
        "weakEvidenceReasons": weak_evidence_reasons,
        "upstreamEffectiveAcceptedRetentionRatio": lane_summary.get("upstreamEffectiveAcceptedRetentionRatio"),
        "refutedSeedsReusedAsPositiveEvidence": refuted_reused_as_positive,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
    }
    decision = {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "trainingReady": training_ready,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "rationale": (
            "The v7 dataset manifest is prepared from reviewed positives and refuted negatives. "
            "Training is blocked until the quality gate has enough reviewed positives and no pending denominator review."
            if not training_ready
            else "The v7 dataset manifest clears the local quality gate and can move to training prep."
        ),
    }
    batch_outcome = {
        **summary,
        "datasetManifest": dataset_manifest,
        "qualityGate": quality_gate,
        "hardMiningManifest": hard_mining_manifest,
        "sourceManifestDelta": source_manifest_delta,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "touchline_detector_candidate_v7_training_data_refresh_summary.json", summary)
    _write_json(output_root / "v7_dataset_manifest.json", dataset_manifest)
    _write_json(output_root / "v7_labeling_queue.json", {"generatedAt": generated_at, "reviewItems": review_queue})
    _write_json(output_root / "v7_hard_mining_manifest.json", hard_mining_manifest)
    _write_json(output_root / "v7_training_quality_gate.json", quality_gate)
    _write_json(output_root / "source_manifest_delta.json", source_manifest_delta)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "datasetManifest": dataset_manifest,
        "qualityGate": quality_gate,
        "hardMiningManifest": hard_mining_manifest,
        "sourceManifestDelta": source_manifest_delta,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the touchline detector v7 training data refresh artifacts.")
    parser.add_argument("--lane-root", type=Path, default=DEFAULT_LANE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--min-reviewed-positive-frames", type=int, default=DEFAULT_MIN_REVIEWED_POSITIVE_FRAMES)
    args = parser.parse_args()
    payload = run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh(
        lane_root=args.lane_root,
        output_root=args.output_root,
        min_reviewed_positive_frames=args.min_reviewed_positive_frames,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
