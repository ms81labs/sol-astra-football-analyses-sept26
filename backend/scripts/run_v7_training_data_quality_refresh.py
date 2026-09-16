from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_BATCH_NAME = "v7_training_data_quality_refresh"
DEFAULT_OUTPUT_DIR_NAME = "v7_training_data_quality_refresh_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_detector_candidate_v7_training_prep_v1"
DEFAULT_TRAINING_EXPORT_BATCH_NAME = "touchline_detector_candidate_v7_training_v1"

BLOCKER_EXPORT_MALFORMED = "v7_yolo_export_label_malformed"
BLOCKER_NEGATIVE_SEMANTICS_UNSAFE = "v7_negative_semantics_unsafe"
BLOCKER_LOCALIZATION_ZERO = "v7_positive_frame_hit_not_localization_hit"
BLOCKER_ARTIFACT_GAP = "v7_training_data_quality_artifact_gap"

NEXT_EXPORT_FIX = "v7_yolo_export_contract_fix"
NEXT_NEGATIVE_REVIEW = "v7_negative_semantics_review"
NEXT_V7_1_PREP = "v7_1_training_manifest_prep"
NEXT_MANUAL_REVIEW = "manual_review_required"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path, *, required: bool = True) -> dict[str, object]:
    if not path.exists():
        if required:
            raise FileNotFoundError(str(path))
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _resolve_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _training_manifest_path(storage_root: Path) -> Path:
    return _suite_root(storage_root) / DEFAULT_TRAINING_PREP_BATCH_NAME / "v7_training_manifest.json"


def _split_manifest_path(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "training_prep"
        / DEFAULT_TRAINING_EXPORT_BATCH_NAME
        / "yolo_export"
        / "split_manifest.json"
    )


def _manifest_examples_by_id(training_manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    examples = {}
    for row in list(training_manifest.get("positiveExamples") or []) + list(training_manifest.get("negativeExamples") or []):
        if isinstance(row, dict) and row.get("exampleId") is not None:
            examples[str(row.get("exampleId"))] = row
    return examples


def _bbox_to_yolo_values(
    bbox: dict[str, object],
    *,
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float] | None:
    try:
        x1 = max(min(float(bbox["x1"]), float(image_width)), 0.0)
        y1 = max(min(float(bbox["y1"]), float(image_height)), 0.0)
        x2 = max(min(float(bbox["x2"]), float(image_width)), 0.0)
        y2 = max(min(float(bbox["y2"]), float(image_height)), 0.0)
    except (KeyError, TypeError, ValueError):
        return None
    width = max(x2 - x1, 0.0)
    height = max(y2 - y1, 0.0)
    if width <= 0 or height <= 0 or image_width <= 0 or image_height <= 0:
        return None
    return (
        ((x1 + x2) / 2.0) / float(image_width),
        ((y1 + y2) / 2.0) / float(image_height),
        width / float(image_width),
        height / float(image_height),
    )


def _image_size(path: Path) -> tuple[int, int] | None:
    image = cv2.imread(str(path))
    if image is None:
        return None
    height, width = image.shape[:2]
    return int(width), int(height)


def _parse_label_line(label_text: str) -> tuple[int, float, float, float, float] | None:
    parts = label_text.strip().split()
    if len(parts) != 5:
        return None
    try:
        class_id = int(parts[0])
        values = tuple(float(part) for part in parts[1:])
    except ValueError:
        return None
    if any(value < 0.0 or value > 1.0 for value in values):
        return None
    return (class_id, *values)


def _audit_yolo_export(
    *,
    training_manifest: dict[str, object],
    split_manifest: dict[str, object],
) -> dict[str, object]:
    examples_by_id = _manifest_examples_by_id(training_manifest)
    rows = []
    malformed = 0
    mismatch = 0
    refuted_positive_labels = 0
    positive_count = 0
    negative_count = 0
    for exported in split_manifest.get("exportedExamples") or []:
        if not isinstance(exported, dict):
            continue
        example_id = str(exported.get("exampleId") or "")
        manifest_row = examples_by_id.get(example_id, {})
        label_path = _resolve_path(exported.get("labelPath"))
        image_path = _resolve_path(exported.get("imagePath"))
        label_text = label_path.read_text(encoding="utf-8").strip() if label_path and label_path.exists() else ""
        positive_label_written = bool(exported.get("positiveLabelWritten"))
        if positive_label_written:
            positive_count += 1
        else:
            negative_count += 1
        parsed = _parse_label_line(label_text) if label_text else None
        reason = "ok"
        if positive_label_written:
            if parsed is None or parsed[0] != 0:
                malformed += 1
                reason = "malformed_positive_label"
            elif "refuted" in str(exported.get("truthUse") or manifest_row.get("truthUse") or ""):
                refuted_positive_labels += 1
                reason = "refuted_positive_label"
            else:
                bbox = manifest_row.get("bbox")
                size = _image_size(image_path) if image_path else None
                if isinstance(bbox, dict) and size is not None:
                    expected = _bbox_to_yolo_values(
                        bbox,
                        image_width=size[0],
                        image_height=size[1],
                    )
                    observed = parsed[1:] if parsed is not None else None
                    if expected is None or observed is None or any(abs(expected[i] - observed[i]) > 0.001 for i in range(4)):
                        mismatch += 1
                        reason = "positive_label_bbox_mismatch"
        elif label_text:
            malformed += 1
            reason = "negative_label_not_empty"
        rows.append(
            {
                "exampleId": example_id,
                "frameIndex": exported.get("frameIndex"),
                "positiveLabelWritten": positive_label_written,
                "truthUse": exported.get("truthUse"),
                "labelReason": reason,
            }
        )
    metadata_overlap = bool(training_manifest.get("refutedSeedsReusedAsPositiveEvidence"))
    return {
        "generatedAt": _utc_now_iso(),
        "positiveExportedLabelCount": positive_count,
        "negativeExportedEmptyLabelCount": negative_count,
        "malformedLabelCount": malformed,
        "bboxMismatchCount": mismatch,
        "refutedSeedPositiveLabelCount": refuted_positive_labels,
        "refutedPositiveOverlapMetadataFlag": metadata_overlap,
        "refutedPositiveOverlapIsMetadataOnly": bool(metadata_overlap and refuted_positive_labels == 0),
        "rows": rows,
    }


def _proof_rows(precision_summary: dict[str, object]) -> list[dict[str, object]]:
    proof_root = _resolve_path(precision_summary.get("proofSource"))
    if proof_root is None:
        return []
    truth_layers = _load_json(proof_root / "ball_truth_layers.json", required=False)
    probe_layer = truth_layers.get("probeObservedBall")
    if isinstance(probe_layer, dict) and isinstance(probe_layer.get("rawRows"), list):
        return [dict(row) for row in probe_layer["rawRows"] if isinstance(row, dict)]
    return []


def _audit_negative_semantics(training_manifest: dict[str, object], split_manifest: dict[str, object]) -> dict[str, object]:
    negative_examples = [row for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]
    empty_full_frame_negatives = [
        row for row in split_manifest.get("exportedExamples") or []
        if isinstance(row, dict) and not bool(row.get("positiveLabelWritten"))
    ]
    unsafe_rows = []
    for row in empty_full_frame_negatives:
        truth_use = str(row.get("truthUse") or "")
        if "refuted_seed" in truth_use or "negative_only" in truth_use:
            unsafe_rows.append(
                {
                    "exampleId": row.get("exampleId"),
                    "frameIndex": row.get("frameIndex"),
                    "reason": "empty_full_frame_negative_visible_ball_unknown",
                }
            )
    return {
        "generatedAt": _utc_now_iso(),
        "negativeExampleCount": len(negative_examples),
        "fullFrameEmptyLabelNegativeCount": len(empty_full_frame_negatives),
        "unsafeFullFrameNegativeCount": len(unsafe_rows),
        "negativeSemanticsSafeForFullFrameTraining": len(unsafe_rows) == 0,
        "unsafeRows": unsafe_rows,
    }


def _hard_negative_plan(probe_rows: list[dict[str, object]]) -> dict[str, object]:
    top_left_rows = [
        row for row in probe_rows
        if _safe_float(row.get("Source_X1")) <= 1.0 and _safe_float(row.get("Source_Y1")) <= 1.0
    ]
    seen = set()
    sampled = []
    for row in top_left_rows:
        frame = _safe_int(row.get("Frame_ID"), -1)
        bucket = frame // 25 if frame >= 0 else len(sampled)
        if bucket in seen:
            continue
        seen.add(bucket)
        sampled.append(
            {
                "frameIndex": frame,
                "sourceClipId": "trimed-5min.mp4",
                "cropWindow": [
                    _safe_float(row.get("Source_X1")),
                    _safe_float(row.get("Source_Y1")),
                    _safe_float(row.get("Source_X2")),
                    _safe_float(row.get("Source_Y2")),
                ],
                "truthUse": "hard_negative_top_left_artifact_candidate",
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "topLeftArtifactCandidateCount": len(top_left_rows),
        "dedupedTopLeftArtifactCandidateCount": len(sampled),
        "sampledHardNegativeCandidates": sampled[:200],
        "hardNegativePolicy": "review_or_crop_before_training; do_not_export_as_full_frame_empty_label_without visible-ball review",
    }


def _manifest_delta(training_manifest: dict[str, object], negative_audit: dict[str, object], hard_negative_plan: dict[str, object]) -> dict[str, object]:
    positives = [dict(row) for row in training_manifest.get("positiveExamples") or [] if isinstance(row, dict)]
    negatives = [dict(row) for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]
    return {
        "generatedAt": _utc_now_iso(),
        "deltaType": "proposed_only",
        "groupedSplitRequired": True,
        "positiveExampleCount": len(positives),
        "negativeExampleCount": len(negatives),
        "hardNegativeCandidateCount": int(hard_negative_plan.get("dedupedTopLeftArtifactCandidateCount", 0)),
        "fullFrameNegativesRequiringReview": int(negative_audit.get("unsafeFullFrameNegativeCount", 0)),
        "positiveExamplesPreserved": positives,
        "negativeExamplesPreservedAsNegativeOnly": negatives,
        "hardNegativeCandidates": hard_negative_plan.get("sampledHardNegativeCandidates", []),
    }


def _select_decision(
    export_audit: dict[str, object],
    negative_audit: dict[str, object],
    precision_summary: dict[str, object],
) -> tuple[str, str, list[str]]:
    if _safe_int(export_audit.get("malformedLabelCount"), 0) or _safe_int(export_audit.get("bboxMismatchCount"), 0):
        return (
            BLOCKER_EXPORT_MALFORMED,
            NEXT_EXPORT_FIX,
            ["YOLO export labels are malformed or do not match reviewed bboxes."],
        )
    if _safe_int(negative_audit.get("unsafeFullFrameNegativeCount"), 0):
        return (
            BLOCKER_NEGATIVE_SEMANTICS_UNSAFE,
            NEXT_NEGATIVE_REVIEW,
            ["Full-frame empty-label negatives come from refuted seeds and need visible-ball review or crop conversion."],
        )
    if _safe_float(precision_summary.get("positiveLocalizationHitRate"), 0.0) <= 0.0:
        return (
            BLOCKER_LOCALIZATION_ZERO,
            NEXT_V7_1_PREP,
            ["The low-confidence v7 proof has frame hits but zero reviewed-positive localization hits."],
        )
    return (
        BLOCKER_ARTIFACT_GAP,
        NEXT_MANUAL_REVIEW,
        ["Training data quality artifacts are insufficient for a deterministic v7.1 decision."],
    )


def _markdown_summary(summary: dict[str, object], outcome: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Training Data Quality Refresh",
            "",
            f"- Goal achieved: `{outcome.get('goalAchieved')}`",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            f"- Positive localization hit rate: `{summary.get('positiveLocalizationHitRate')}`",
            f"- Unsafe full-frame negatives: `{summary.get('unsafeFullFrameNegativeCount')}`",
            "",
            str(outcome.get("englishSummary") or ""),
            "",
            str(outcome.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_training_data_quality_refresh(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    output_root = candidate_root / DEFAULT_OUTPUT_DIR_NAME
    training_manifest = _load_json(_training_manifest_path(storage_root), required=False)
    split_manifest = _load_json(_split_manifest_path(storage_root), required=False)
    precision_summary = _load_json(
        candidate_root / "v7_probe_precision_guardrail_audit_v1" / "precision_guardrail_summary.json",
        required=False,
    )
    precision_localization = _load_json(
        candidate_root / "v7_probe_precision_guardrail_audit_v1" / "positive_localization_audit.json",
        required=False,
    )
    if "positiveLocalizationHitRate" not in precision_summary and precision_localization:
        precision_summary = {**precision_summary, **precision_localization}
    probe_rows = _proof_rows(precision_summary)
    export_audit = _audit_yolo_export(training_manifest=training_manifest, split_manifest=split_manifest)
    negative_audit = _audit_negative_semantics(training_manifest, split_manifest)
    hard_negative_plan = _hard_negative_plan(probe_rows)
    manifest_delta = _manifest_delta(training_manifest, negative_audit, hard_negative_plan)
    dominant, next_family, reasons = _select_decision(export_audit, negative_audit, precision_summary)
    localization_audit = {
        "generatedAt": _utc_now_iso(),
        "sourcePrecisionAuditPath": str(candidate_root / "v7_probe_precision_guardrail_audit_v1" / "positive_localization_audit.json"),
        "positiveFrameHitRate": _safe_float(precision_summary.get("positiveFrameHitRate"), 0.0),
        "positiveLocalizationHitRate": _safe_float(precision_summary.get("positiveLocalizationHitRate"), 0.0),
        "positiveCenterDistanceHitRate": _safe_float(precision_summary.get("positiveCenterDistanceHitRate"), 0.0),
        "positiveIoUHitRate": _safe_float(precision_summary.get("positiveIoUHitRate"), 0.0),
        "medianCenterDistanceToReviewedBBox": _safe_float(precision_summary.get("medianCenterDistanceToReviewedBBox"), 0.0),
        "medianDetectedBoxAreaToGtBoxAreaRatio": _safe_float(precision_summary.get("medianDetectedBoxAreaToGtBoxAreaRatio"), 0.0),
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "attemptNumber": 1,
        "attemptApproachFamily": "localization_export_sanity_audit",
        "positiveExampleCount": _safe_int(training_manifest.get("positiveExampleCount"), len(training_manifest.get("positiveExamples") or [])),
        "negativeExampleCount": _safe_int(training_manifest.get("negativeExampleCount"), len(training_manifest.get("negativeExamples") or [])),
        "positiveLocalizationHitRate": localization_audit["positiveLocalizationHitRate"],
        "malformedLabelCount": export_audit["malformedLabelCount"],
        "bboxMismatchCount": export_audit["bboxMismatchCount"],
        "refutedSeedPositiveLabelCount": export_audit["refutedSeedPositiveLabelCount"],
        "unsafeFullFrameNegativeCount": negative_audit["unsafeFullFrameNegativeCount"],
        "hardNegativeCandidateCount": hard_negative_plan["dedupedTopLeftArtifactCandidateCount"],
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "runtimeDefaultMutationAllowed": False,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "classificationReasons": reasons,
        "decisions": [
            {
                "condition": "YOLO labels malformed or bbox mismatch",
                "matched": dominant == BLOCKER_EXPORT_MALFORMED,
                "nextCorrectiveFamily": NEXT_EXPORT_FIX,
            },
            {
                "condition": "full-frame empty-label negative semantics unsafe",
                "matched": dominant == BLOCKER_NEGATIVE_SEMANTICS_UNSAFE,
                "nextCorrectiveFamily": NEXT_NEGATIVE_REVIEW,
            },
            {
                "condition": "export sane but localization hit rate is zero",
                "matched": dominant == BLOCKER_LOCALIZATION_ZERO,
                "nextCorrectiveFamily": NEXT_V7_1_PREP,
            },
        ],
        "selectedNextCorrectiveFamily": next_family,
    }
    outcome = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Audit v7 labels, localization truth, and negative semantics before any v7.1 retraining.",
        "goalAchieved": dominant != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": False,
        "primaryBlocker": dominant,
        "nextRecommendedNextLever": next_family,
        "runtimeDefaultMutationAllowed": False,
        "englishSummary": f"V7 training data quality refresh classified the blocker as {dominant}.",
        "englishDecision": f"Advance to {next_family}; do not train, promote, or mutate runtime defaults in this batch.",
    }
    _write_json(output_root / "v7_training_data_quality_summary.json", summary)
    _write_json(output_root / "positive_localization_audit.json", localization_audit)
    _write_json(output_root / "yolo_export_label_sanity_audit.json", export_audit)
    _write_json(output_root / "negative_semantics_audit.json", negative_audit)
    _write_json(output_root / "hard_negative_mining_plan.json", hard_negative_plan)
    _write_json(output_root / "v7_1_training_manifest_delta.json", manifest_delta)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(
        _markdown_summary(summary, outcome),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_v7_training_data_quality_refresh(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
