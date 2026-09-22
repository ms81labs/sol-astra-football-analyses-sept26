from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_required as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_negative_crop_conversion_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_training_manifest_prep_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_detector_candidate_v7_training_prep_v1"

BLOCKER_READY = "v7_1_training_manifest_ready"
BLOCKER_UNSAFE_NEGATIVE_LEAK = "v7_1_manifest_unsafe_negative_leak"
BLOCKER_POSITIVE_GAP = "v7_1_manifest_positive_gap"
BLOCKER_NEGATIVE_GAP = "v7_1_manifest_negative_gap"
BLOCKER_ARTIFACT_GAP = "v7_1_manifest_artifact_gap"

NEXT_TRAINING = "touchline_detector_candidate_v7_1_training"
NEXT_CROP_CONVERSION = "v7_negative_crop_conversion_plan"
NEXT_POSITIVE_EXPANSION = "manual_review_positive_expansion"
NEXT_MANUAL_REVIEW = "manual_review_required"






def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _training_manifest_path(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / DEFAULT_TRAINING_PREP_BATCH_NAME
        / "v7_training_manifest.json"
    )


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_for_index(index: int) -> str:
    return "validation" if index % 5 == 4 else "train"


def _bbox_valid(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        return float(value["x2"]) > float(value["x1"]) and float(value["y2"]) > float(value["y1"])
    except (KeyError, TypeError, ValueError):
        return False


def _crop_window(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    window = [_safe_float(part) for part in value]
    if window[2] <= window[0] or window[3] <= window[1]:
        return None
    return [round(part, 3) for part in window]


def _positive_examples(training_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    positives = []
    seen: set[str] = set()
    for index, row in enumerate(training_manifest.get("positiveExamples") or []):
        if not isinstance(row, dict):
            continue
        example_id = str(row.get("exampleId") or f"positive-{index}")
        if example_id in seen or not _bbox_valid(row.get("bbox")):
            continue
        seen.add(example_id)
        normalized = dict(row)
        normalized["exampleId"] = example_id
        normalized["truthUse"] = "reviewed_positive_training_seed"
        normalized.setdefault("split", _split_for_index(index))
        normalized["v7_1Use"] = "positive_ball_label"
        positives.append(normalized)
    return positives


def _crop_negative_examples(crop_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    negatives = []
    seen: set[str] = set()
    for index, row in enumerate(crop_manifest.get("crops") or []):
        if not isinstance(row, dict):
            continue
        window = _crop_window(row.get("cropWindow"))
        if window is None:
            continue
        example_id = str(row.get("exampleId") or f"v7-1-crop-negative-{index}")
        if example_id in seen:
            continue
        seen.add(example_id)
        negatives.append(
            {
                "exampleId": example_id,
                "frameIndex": _safe_int(row.get("frameIndex"), -1),
                "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
                "cropWindow": window,
                "bbox": None,
                "label": "not_ball_local_crop",
                "truthUse": "local_hard_negative_top_left_artifact",
                "labelPolicy": "empty_label_crop_only",
                "sourceFullFrameNegativeExported": False,
                "split": _split_for_index(index),
                "lineage": row.get("lineage") if isinstance(row.get("lineage"), dict) else {},
                "v7_1Use": "negative_empty_crop_label",
            }
        )
    return negatives


def _legacy_negative_examples(training_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]


def _split_counts(positives: list[dict[str, Any]], negatives: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {
        "train": {"positive": 0, "negative": 0},
        "validation": {"positive": 0, "negative": 0},
    }
    for row in positives:
        split = str(row.get("split") or "train")
        counts.setdefault(split, {"positive": 0, "negative": 0})
        counts[split]["positive"] += 1
    for row in negatives:
        split = str(row.get("split") or "train")
        counts.setdefault(split, {"positive": 0, "negative": 0})
        counts[split]["negative"] += 1
    return counts


def _quality_gate(
    *,
    positives: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
    min_positive_examples: int,
    min_negative_examples: int,
) -> dict[str, Any]:
    refuted_positive_count = sum(1 for row in positives if "refuted" in str(row.get("truthUse") or ""))
    unsafe_negative_count = sum(
        1
        for row in negatives
        if row.get("sourceFullFrameNegativeExported") is not False
        or "negative_only_refuted_seed" in str(row.get("truthUse") or "")
    )
    missing_positive_bbox_count = sum(1 for row in positives if not _bbox_valid(row.get("bbox")))
    split_counts = _split_counts(positives, negatives)
    train_positive_count = split_counts.get("train", {}).get("positive", 0)
    validation_positive_count = split_counts.get("validation", {}).get("positive", 0)
    train_negative_count = split_counts.get("train", {}).get("negative", 0)
    validation_negative_count = split_counts.get("validation", {}).get("negative", 0)
    weak_reasons = []
    if len(positives) < min_positive_examples:
        weak_reasons.append("positive_example_count_below_minimum")
    if len(negatives) < min_negative_examples:
        weak_reasons.append("negative_example_count_below_minimum")
    if refuted_positive_count:
        weak_reasons.append("refuted_seed_positive_label_leak")
    if unsafe_negative_count:
        weak_reasons.append("unsafe_full_frame_negative_leak")
    if missing_positive_bbox_count:
        weak_reasons.append("positive_bbox_missing")
    if train_positive_count == 0 or validation_positive_count == 0:
        weak_reasons.append("positive_split_missing_train_or_validation")
    if train_negative_count == 0 or validation_negative_count == 0:
        weak_reasons.append("negative_split_missing_train_or_validation")
    return {
        "generatedAt": _utc_now_iso(),
        "positiveExampleCount": len(positives),
        "negativeExampleCount": len(negatives),
        "minPositiveExamples": min_positive_examples,
        "minNegativeExamples": min_negative_examples,
        "refutedSeedPositiveLabelCount": refuted_positive_count,
        "unsafeFullFrameNegativeCount": unsafe_negative_count,
        "positiveBBoxMissingCount": missing_positive_bbox_count,
        "groupedSplitRequired": True,
        "splitCounts": split_counts,
        "trainingPrepReady": not weak_reasons,
        "weakEvidenceReasons": weak_reasons,
    }


def _classify(quality_gate: dict[str, Any]) -> tuple[str, str]:
    if quality_gate.get("trainingPrepReady") is True:
        return BLOCKER_READY, NEXT_TRAINING
    weak_reasons = set(quality_gate.get("weakEvidenceReasons") or [])
    if "unsafe_full_frame_negative_leak" in weak_reasons or "refuted_seed_positive_label_leak" in weak_reasons:
        return BLOCKER_UNSAFE_NEGATIVE_LEAK, NEXT_CROP_CONVERSION
    if "positive_example_count_below_minimum" in weak_reasons or "positive_bbox_missing" in weak_reasons:
        return BLOCKER_POSITIVE_GAP, NEXT_POSITIVE_EXPANSION
    if "negative_example_count_below_minimum" in weak_reasons:
        return BLOCKER_NEGATIVE_GAP, NEXT_CROP_CONVERSION
    return BLOCKER_ARTIFACT_GAP, NEXT_MANUAL_REVIEW


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Training Manifest Prep",
            "",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- trainingPrepReady: `{summary.get('trainingPrepReady')}`",
            f"- Positive examples: `{summary.get('positiveExampleCount')}`",
            f"- Negative examples: `{summary.get('negativeExampleCount')}`",
            f"- Unsafe full-frame negatives: `{summary.get('unsafeFullFrameNegativeCount')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            "",
        ]
    )


def run_v7_1_training_manifest_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    min_positive_examples: int = 20,
    min_negative_examples: int = 20,
    include_legacy_negatives: bool = False,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    input_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    output_root = candidate_root / output_dir_name
    training_manifest = _load_json(_training_manifest_path(storage_root), required=False)
    conversion_summary = _load_json(input_root / "v7_negative_crop_conversion_summary.json", required=False)
    crop_manifest = _load_json(input_root / "local_hard_negative_crop_manifest.json", required=False)
    excluded_manifest = _load_json(input_root / "excluded_full_frame_negative_manifest.json", required=False)

    positives = _positive_examples(training_manifest)
    negatives = _crop_negative_examples(crop_manifest)
    if include_legacy_negatives:
        negatives.extend(_legacy_negative_examples(training_manifest))
    quality_gate = _quality_gate(
        positives=positives,
        negatives=negatives,
        min_positive_examples=min_positive_examples,
        min_negative_examples=min_negative_examples,
    )
    blocker, next_family = _classify(quality_gate)
    manifest = {
        "batchName": "v7_1_training_manifest_prep",
        "generatedAt": _utc_now_iso(),
        "positiveTruthPolicy": "reviewed_positive_ball_bboxes_only",
        "negativeTruthPolicy": "local_crop_hard_negatives_only",
        "positiveExampleCount": len(positives),
        "negativeExampleCount": len(negatives),
        "positiveExamples": positives,
        "negativeExamples": negatives,
        "excludedUnsafeFullFrameNegativeCount": len(excluded_manifest.get("excluded") or []),
        "groupedSplitRequired": True,
        "splitCounts": quality_gate["splitCounts"],
    }
    summary = {
        "batchName": "v7_1_training_manifest_prep",
        "attemptNumber": 1,
        "attemptApproachFamily": "v7_1_manifest_assembly",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": candidate_name,
        "dominantBlockerClass": blocker,
        "nextCorrectiveFamily": next_family,
        "goalAchieved": blocker != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": quality_gate["trainingPrepReady"],
        "trainingPrepReady": quality_gate["trainingPrepReady"],
        "positiveExampleCount": len(positives),
        "negativeExampleCount": len(negatives),
        "unsafeFullFrameNegativeCount": quality_gate["unsafeFullFrameNegativeCount"],
        "refutedSeedPositiveLabelCount": quality_gate["refutedSeedPositiveLabelCount"],
        "positiveBBoxMissingCount": quality_gate["positiveBBoxMissingCount"],
        "excludedUnsafeFullFrameNegativeCount": len(excluded_manifest.get("excluded") or []),
        "inputDominantBlockerClass": conversion_summary.get("dominantBlockerClass"),
        "runtimeDefaultMutationAllowed": False,
        "weakEvidenceReasons": quality_gate["weakEvidenceReasons"],
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "manifest_quality_gate_passed",
                "observed": quality_gate["trainingPrepReady"],
                "selected": blocker == BLOCKER_READY,
                "nextFamily": NEXT_TRAINING,
            },
            {
                "condition": "unsafe_negative_or_refuted_positive_leak",
                "observed": quality_gate["unsafeFullFrameNegativeCount"] > 0
                or quality_gate["refutedSeedPositiveLabelCount"] > 0,
                "selected": blocker == BLOCKER_UNSAFE_NEGATIVE_LEAK,
                "nextFamily": NEXT_CROP_CONVERSION,
            },
        ],
    }
    outcome = {
        "summary": summary,
        "qualityGate": quality_gate,
        "trainingManifest": manifest,
    }

    _write_json(output_root / "v7_1_training_manifest_prep_summary.json", summary)
    _write_json(output_root / "v7_1_training_manifest.json", manifest)
    _write_json(output_root / "v7_1_manifest_quality_gate.json", quality_gate)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--include-legacy-negatives", action="store_true")
    args = parser.parse_args()
    payload = run_v7_1_training_manifest_prep(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        include_legacy_negatives=args.include_legacy_negatives,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
