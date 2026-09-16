from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_DATASET_MANIFEST_PATH = (
    DEFAULT_SUITE_ROOT
    / "touchline_detector_candidate_v7_training_data_refresh_v1"
    / "v7_dataset_manifest.json"
)
DEFAULT_DENOMINATOR_TRUTH_SEED_PATH = (
    DEFAULT_SUITE_ROOT
    / "manual_review_denominator_resolution_v1"
    / "reviewed_denominator_truth_seed.json"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "touchline_detector_candidate_v7_training_prep_v1"
DEFAULT_MIN_POSITIVE_EXAMPLES = 20
DEFAULT_MIN_NEGATIVE_EXAMPLES = 20
DEFAULT_TARGET_SOURCE_CLIP_ID = "trimed-5min.mp4"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _int_frame(value: object) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _source_clip_id(row: dict[str, Any]) -> str:
    value = row.get("sourceClipId") or row.get("source") or DEFAULT_TARGET_SOURCE_CLIP_ID
    return str(value)


def _frame_key(row: dict[str, Any]) -> tuple[str, int | str]:
    frame = _int_frame(row.get("frameIndex"))
    return _source_clip_id(row), frame if frame is not None else str(row.get("frameIndex"))


def _bbox_from_row(row: dict[str, Any]) -> dict[str, float] | None:
    for key in ("reviewedBBox", "bbox", "seedBBox"):
        value = row.get(key)
        if not isinstance(value, dict):
            continue
        try:
            x1 = float(value["x1"])
            y1 = float(value["y1"])
            x2 = float(value["x2"])
            y2 = float(value["y2"])
        except (KeyError, TypeError, ValueError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    return None


def _bbox_centroid(bbox: dict[str, float] | None) -> dict[str, float] | None:
    if bbox is None:
        return None
    return {
        "x": round((bbox["x1"] + bbox["x2"]) / 2.0, 3),
        "y": round((bbox["y1"] + bbox["y2"]) / 2.0, 3),
    }


def _split_for_index(index: int) -> str:
    return "validation" if index % 5 == 4 else "train"


def _dedupe_by_frame(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int | str], dict[str, Any]] = {}
    for row in rows:
        by_key.setdefault(_frame_key(row), row)
    return [by_key[key] for key in sorted(by_key, key=lambda item: (item[0], str(item[1])))]


def _has_lineage(row: dict[str, Any]) -> bool:
    lineage = row.get("lineage")
    return isinstance(lineage, dict) and bool(lineage)


def _normalize_positive(row: dict[str, Any], *, index: int, source: str) -> dict[str, Any]:
    bbox = _bbox_from_row(row)
    frame = _int_frame(row.get("frameIndex"))
    source_clip_id = _source_clip_id(row)
    return {
        "exampleId": f"v7-training-positive-{source_clip_id}-{frame}",
        "frameIndex": frame,
        "sourceClipId": source_clip_id,
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
        "lineageComplete": _has_lineage(row),
        "trainingPrepSource": source,
        "split": _split_for_index(index),
    }


def _normalize_negative(row: dict[str, Any], *, index: int, source: str) -> dict[str, Any]:
    bbox = _bbox_from_row(row)
    frame = _int_frame(row.get("frameIndex"))
    source_clip_id = _source_clip_id(row)
    return {
        "exampleId": f"v7-training-negative-{source_clip_id}-{frame}-{index}",
        "frameIndex": frame,
        "sourceClipId": source_clip_id,
        "timestampSeconds": row.get("timestampSeconds"),
        "bbox": bbox,
        "bboxCentroid": _bbox_centroid(bbox),
        "label": "not_ball_refuted_seed",
        "truthUse": "negative_only_refuted_seed",
        "reviewDecision": row.get("reviewDecision"),
        "reviewItemId": row.get("reviewItemId"),
        "candidateFrameId": row.get("candidateFrameId"),
        "refutationUse": "negative_only_do_not_use_as_positive",
        "trainingPrepSource": source,
        "split": _split_for_index(index),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Touchline Detector Candidate V7 Training Prep",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- trainingPrepReady: {summary.get('trainingPrepReady')}",
            f"- positiveExampleCount: {summary.get('positiveExampleCount')}",
            f"- negativeExampleCount: {summary.get('negativeExampleCount')}",
            f"- remainingPendingReviewCount: {summary.get('remainingPendingReviewCount')}",
            f"- positiveLineageCompleteCount: {summary.get('positiveLineageCompleteCount')}",
            f"- weakEvidenceReasons: {summary.get('weakEvidenceReasons')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def _select_next_family(
    *,
    training_ready: bool,
    remaining_pending_count: int,
    positive_count: int,
    min_positive_examples: int,
    positive_bbox_missing_count: int,
) -> str:
    if training_ready:
        return "touchline_detector_candidate_v7_training"
    if remaining_pending_count > 0:
        return "manual_review_denominator_expansion"
    if positive_count < min_positive_examples or positive_bbox_missing_count > 0:
        return "manual_review_positive_expansion"
    return "touchline_detector_candidate_v7_training_prep_blocker_summary"


def run_promoted_v6_touchline_detector_candidate_v7_training_prep(
    *,
    dataset_manifest_path: Path = DEFAULT_DATASET_MANIFEST_PATH,
    denominator_truth_seed_path: Path = DEFAULT_DENOMINATOR_TRUTH_SEED_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    min_positive_examples: int = DEFAULT_MIN_POSITIVE_EXAMPLES,
    min_negative_examples: int = DEFAULT_MIN_NEGATIVE_EXAMPLES,
) -> dict[str, Any]:
    dataset_manifest_path = Path(dataset_manifest_path)
    denominator_truth_seed_path = Path(denominator_truth_seed_path)
    output_root = Path(output_root)
    dataset = _load_json_dict(dataset_manifest_path)
    denominator_seed = _load_json_dict(denominator_truth_seed_path)

    prior_positive_rows = _dedupe_by_frame(_list_dicts(dataset.get("positiveExamples")))
    prior_negative_rows = _dedupe_by_frame(_list_dicts(dataset.get("negativeExamples")))
    pending_rows = _dedupe_by_frame(_list_dicts(dataset.get("pendingReviewFrames")))
    denominator_positive_rows = _dedupe_by_frame(_list_dicts(denominator_seed.get("reviewedPositiveSeedRows")))
    denominator_negative_rows = _dedupe_by_frame(_list_dicts(denominator_seed.get("reviewedNegativeSeedRows")))

    denominator_reviewed_keys = {
        _frame_key(row)
        for row in [*denominator_positive_rows, *denominator_negative_rows]
    }
    remaining_pending_rows = [
        row for row in pending_rows if _frame_key(row) not in denominator_reviewed_keys
    ]

    all_negative_source_rows = _dedupe_by_frame([*prior_negative_rows, *denominator_negative_rows])
    negative_keys = {_frame_key(row) for row in all_negative_source_rows}
    all_positive_source_rows = _dedupe_by_frame([*prior_positive_rows, *denominator_positive_rows])
    positive_overlap_keys = {_frame_key(row) for row in all_positive_source_rows} & negative_keys
    positive_source_rows = [
        row for row in all_positive_source_rows if _frame_key(row) not in negative_keys
    ]

    positive_examples = [
        _normalize_positive(
            row,
            index=index,
            source=(
                "manual_review_denominator_resolution"
                if _frame_key(row) in {_frame_key(item) for item in denominator_positive_rows}
                else "v7_training_data_refresh"
            ),
        )
        for index, row in enumerate(positive_source_rows)
    ]
    negative_examples = [
        _normalize_negative(
            row,
            index=index,
            source=(
                "manual_review_denominator_resolution"
                if _frame_key(row) in {_frame_key(item) for item in denominator_negative_rows}
                else "v7_training_data_refresh"
            ),
        )
        for index, row in enumerate(all_negative_source_rows)
    ]

    positive_bbox_missing_count = sum(1 for row in positive_examples if row.get("bbox") is None)
    negative_frame_missing_count = sum(1 for row in negative_examples if row.get("frameIndex") is None)
    positive_lineage_complete_count = sum(1 for row in positive_examples if row.get("lineageComplete"))

    weak_evidence_reasons: list[str] = []
    if len(positive_examples) < min_positive_examples:
        weak_evidence_reasons.append("reviewed_positive_count_below_minimum")
    if len(negative_examples) < min_negative_examples:
        weak_evidence_reasons.append("negative_count_below_minimum")
    if remaining_pending_rows:
        weak_evidence_reasons.append("unresolved_pending_denominator_review")
    if positive_bbox_missing_count:
        weak_evidence_reasons.append("positive_bbox_missing")
    if negative_frame_missing_count:
        weak_evidence_reasons.append("negative_frame_index_missing")

    # Older reviewed-positive seeds intentionally have partial lineage. Track that risk, but do
    # not block training prep after the explicit denominator resolution gate has cleared.
    lineage_warning_count = len(positive_examples) - positive_lineage_complete_count
    quality_warnings: list[str] = []
    if positive_overlap_keys:
        quality_warnings.append("refuted_positive_overlap_removed")
    if lineage_warning_count:
        quality_warnings.append("positive_lineage_partial_for_legacy_reviewed_frames")

    training_ready = not weak_evidence_reasons
    next_family = _select_next_family(
        training_ready=training_ready,
        remaining_pending_count=len(remaining_pending_rows),
        positive_count=len(positive_examples),
        min_positive_examples=min_positive_examples,
        positive_bbox_missing_count=positive_bbox_missing_count,
    )
    generated_at = _utc_now_iso()
    split_counts: dict[str, dict[str, int]] = {
        "train": {"positive": 0, "negative": 0},
        "validation": {"positive": 0, "negative": 0},
    }
    for row in positive_examples:
        split_counts[str(row.get("split", "train"))]["positive"] += 1
    for row in negative_examples:
        split_counts[str(row.get("split", "train"))]["negative"] += 1

    training_manifest = {
        "batchName": "touchline_detector_candidate_v7_training_prep",
        "generatedAt": generated_at,
        "positiveTruthPolicy": "reviewed_positive_only",
        "negativeTruthPolicy": "refuted_and_reviewed_negative_only",
        "refutedSeedsReusedAsPositiveEvidence": bool(positive_overlap_keys),
        "positiveExampleCount": len(positive_examples),
        "positiveExamples": positive_examples,
        "negativeExampleCount": len(negative_examples),
        "negativeExamples": negative_examples,
        "remainingPendingReviewCount": len(remaining_pending_rows),
        "remainingPendingReviewFrames": remaining_pending_rows,
        "splitCounts": split_counts,
    }
    quality_gate = {
        "generatedAt": generated_at,
        "trainingPrepReady": training_ready,
        "minPositiveExamples": min_positive_examples,
        "minNegativeExamples": min_negative_examples,
        "positiveExampleCount": len(positive_examples),
        "negativeExampleCount": len(negative_examples),
        "remainingPendingReviewCount": len(remaining_pending_rows),
        "positiveBBoxMissingCount": positive_bbox_missing_count,
        "negativeFrameMissingCount": negative_frame_missing_count,
        "positiveLineageCompleteCount": positive_lineage_complete_count,
        "positiveLineageWarningCount": lineage_warning_count,
        "refutedPositiveOverlapCount": len(positive_overlap_keys),
        "weakEvidenceReasons": weak_evidence_reasons,
        "qualityWarnings": quality_warnings,
        "nextCorrectiveFamily": next_family,
    }
    split_summary = {
        "generatedAt": generated_at,
        "splitCounts": split_counts,
        "trainPositiveCount": split_counts["train"]["positive"],
        "validationPositiveCount": split_counts["validation"]["positive"],
        "trainNegativeCount": split_counts["train"]["negative"],
        "validationNegativeCount": split_counts["validation"]["negative"],
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": "touchline_detector_candidate_v7_training_prep_v1",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "v7_training_manifest_assembly",
        "batchStatus": "training_prep_ready" if training_ready else "training_prep_blocked",
        "goalAchieved": training_ready,
        "roadmapAdvanceAllowed": training_ready,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "positiveExampleCount": len(positive_examples),
        "negativeExampleCount": len(negative_examples),
        "priorPositiveExampleCount": len(prior_positive_rows),
        "denominatorPositiveExampleCount": len(denominator_positive_rows),
        "priorNegativeExampleCount": len(prior_negative_rows),
        "denominatorNegativeExampleCount": len(denominator_negative_rows),
        "remainingPendingReviewCount": len(remaining_pending_rows),
        "positiveBBoxMissingCount": positive_bbox_missing_count,
        "positiveLineageCompleteCount": positive_lineage_complete_count,
        "positiveLineageWarningCount": lineage_warning_count,
        "refutedSeedsReusedAsPositiveEvidence": bool(positive_overlap_keys),
        "refutedPositiveOverlapCount": len(positive_overlap_keys),
        "trainingPrepReady": training_ready,
        "weakEvidenceReasons": weak_evidence_reasons,
        "qualityWarnings": quality_warnings,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
    }
    decision = {
        "generatedAt": generated_at,
        "goalAchieved": training_ready,
        "roadmapAdvanceAllowed": training_ready,
        "trainingPrepReady": training_ready,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "rationale": (
            "The v7 training-prep manifest clears the local quality gate and can advance to the training batch."
            if training_ready
            else "The v7 training-prep manifest is blocked by unresolved quality-gate evidence."
        ),
    }
    batch_outcome = {
        **summary,
        "trainingManifest": training_manifest,
        "qualityGate": quality_gate,
        "splitSummary": split_summary,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "touchline_detector_candidate_v7_training_prep_summary.json", summary)
    _write_json(output_root / "v7_training_manifest.json", training_manifest)
    _write_json(output_root / "v7_training_quality_gate.json", quality_gate)
    _write_json(output_root / "v7_training_split_summary.json", split_summary)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "trainingManifest": training_manifest,
        "qualityGate": quality_gate,
        "splitSummary": split_summary,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble and quality-gate touchline detector v7 training prep.")
    parser.add_argument("--dataset-manifest-path", type=Path, default=DEFAULT_DATASET_MANIFEST_PATH)
    parser.add_argument("--denominator-truth-seed-path", type=Path, default=DEFAULT_DENOMINATOR_TRUTH_SEED_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--min-positive-examples", type=int, default=DEFAULT_MIN_POSITIVE_EXAMPLES)
    parser.add_argument("--min-negative-examples", type=int, default=DEFAULT_MIN_NEGATIVE_EXAMPLES)
    args = parser.parse_args()
    payload = run_promoted_v6_touchline_detector_candidate_v7_training_prep(
        dataset_manifest_path=args.dataset_manifest_path,
        denominator_truth_seed_path=args.denominator_truth_seed_path,
        output_root=args.output_root,
        min_positive_examples=args.min_positive_examples,
        min_negative_examples=args.min_negative_examples,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
