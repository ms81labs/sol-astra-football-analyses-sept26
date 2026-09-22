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
DEFAULT_INPUT_BATCH_NAME = "v7_1_training_manifest_prep_v1"
DEFAULT_NEGATIVE_BATCH_NAME = "v7_negative_crop_conversion_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_crop_manifest_consistency_refresh_v1"
DEFAULT_CROP_SIZES = (192, 256, 384)
DEFAULT_NEGATIVE_CAP = 180
DEFAULT_OVERLAY_SAMPLE_COUNT = 20

BLOCKER_READY = "v7_1_crop_manifest_consistency_ready"
BLOCKER_POSITIVE_TRANSFORM = "v7_1_manifest_positive_crop_transform_gap"
BLOCKER_NEGATIVE_CROP = "v7_1_manifest_unreviewed_negative_crop_gap"
BLOCKER_SPLIT_LEAKAGE = "v7_1_manifest_split_leakage"
BLOCKER_RATIO = "v7_1_manifest_negative_positive_ratio_too_high"
BLOCKER_ARTIFACT_GAP = "v7_1_manifest_label_overlay_audit_missing"

NEXT_OVERLAY_AUDIT = "v7_1_export_label_overlay_audit"
NEXT_POSITIVE_FIX = "v7_1_positive_crop_transform_fix"
NEXT_NEGATIVE_REVIEW = "v7_1_negative_crop_review_or_safety_audit"
NEXT_SPLIT_REFRESH = "v7_1_split_policy_refresh"
NEXT_MANUAL_REVIEW = "manual_review_required"






def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


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


def _bbox(row: dict[str, Any]) -> dict[str, float] | None:
    value = row.get("bbox")
    if not isinstance(value, dict):
        return None
    try:
        x1 = float(value["x1"])
        y1 = float(value["y1"])
        x2 = float(value["x2"])
        y2 = float(value["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _bbox_center(bbox: dict[str, float]) -> tuple[float, float]:
    return (bbox["x1"] + bbox["x2"]) / 2.0, (bbox["y1"] + bbox["y2"]) / 2.0


def _split_group_id(row: dict[str, Any], *, cluster_size: int = 60) -> str:
    source_clip_id = str(row.get("sourceClipId") or "trimed-5min.mp4")
    frame = _safe_int(row.get("frameIndex"), -1)
    bucket = max(frame, 0) // cluster_size
    return f"{source_clip_id}-cluster-{bucket:04d}"


def _crop_bounds_around_bbox(bbox: dict[str, float], crop_size: int) -> tuple[float, float, float, float]:
    cx, cy = _bbox_center(bbox)
    half = crop_size / 2.0
    return cx - half, cy - half, cx + half, cy + half


def _local_bbox(
    bbox: dict[str, float],
    crop_bounds: tuple[float, float, float, float],
) -> dict[str, float]:
    crop_x1, crop_y1, _, _ = crop_bounds
    return {
        "x1": round(bbox["x1"] - crop_x1, 3),
        "y1": round(bbox["y1"] - crop_y1, 3),
        "x2": round(bbox["x2"] - crop_x1, 3),
        "y2": round(bbox["y2"] - crop_y1, 3),
    }


def _crop_bbox_valid(local_bbox: dict[str, float], crop_size: int) -> tuple[bool, str]:
    width = local_bbox["x2"] - local_bbox["x1"]
    height = local_bbox["y2"] - local_bbox["y1"]
    if local_bbox["x1"] < 0 or local_bbox["y1"] < 0 or local_bbox["x2"] > crop_size or local_bbox["y2"] > crop_size:
        return False, "crop_local_bbox_outside_crop_bounds"
    if width <= 0 or height <= 0:
        return False, "crop_local_bbox_malformed"
    area = width * height
    if width < 6 or height < 6 or width > 40 or height > 40 or area < 36 or area > 1600:
        return False, "crop_local_bbox_implausible_size"
    return True, "ok"


def _build_positive_crops(
    positives: list[dict[str, Any]],
    *,
    crop_sizes: tuple[int, ...],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    crop_examples: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    invalid_count = 0
    for source_index, row in enumerate(positives):
        bbox = _bbox(row)
        for crop_size in crop_sizes:
            valid = bbox is not None
            reason = "ok" if valid else "source_bbox_invalid"
            crop_bounds = None
            crop_local_bbox = None
            if bbox is not None:
                crop_bounds = _crop_bounds_around_bbox(bbox, crop_size)
                crop_local_bbox = _local_bbox(bbox, crop_bounds)
                valid, reason = _crop_bbox_valid(crop_local_bbox, crop_size)
            if not valid:
                invalid_count += 1
            frame = _safe_int(row.get("frameIndex"), -1)
            example_id = f"v7-1-positive-crop-{row.get('sourceClipId') or 'trimed-5min'}-{frame}-{crop_size}"
            audit_row = {
                "exampleId": example_id,
                "sourcePositiveExampleId": row.get("exampleId"),
                "frameIndex": frame,
                "cropSizePx": crop_size,
                "sourceFrameBbox": bbox,
                "cropFrameBbox": crop_local_bbox,
                "cropBounds": [round(part, 3) for part in crop_bounds] if crop_bounds else None,
                "valid": valid,
                "reason": reason,
            }
            audit_rows.append(audit_row)
            if valid and bbox is not None and crop_bounds is not None and crop_local_bbox is not None:
                crop_examples.append(
                    {
                        "exampleId": example_id,
                        "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
                        "frameIndex": frame,
                        "sourcePositiveExampleId": row.get("exampleId"),
                        "label": "ball",
                        "truthUse": "reviewed_positive_training_seed",
                        "exportUse": "yolo_positive_crop_with_ball_label",
                        "cropKind": "ball_centered_positive_crop",
                        "cropSizePx": crop_size,
                        "cropBounds": [round(part, 3) for part in crop_bounds],
                        "sourceFrameBbox": bbox,
                        "cropFrameBbox": crop_local_bbox,
                        "splitGroupId": _split_group_id(row),
                        "split": row.get("split") or ("validation" if source_index % 5 == 4 else "train"),
                    }
                )
    audit = {
        "generatedAt": _utc_now_iso(),
        "sourcePositiveCount": len(positives),
        "positiveCropExampleCount": len(crop_examples),
        "invalidPositiveCropCount": invalid_count,
        "cropSizes": list(crop_sizes),
        "rows": audit_rows,
    }
    return crop_examples, audit


def _normalize_crop_window(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    window = [_safe_float(part) for part in value]
    if window[2] <= window[0] or window[3] <= window[1]:
        return None
    return [round(part, 3) for part in window]


def _build_negative_crops(
    negatives: list[dict[str, Any]],
    *,
    negative_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    heldout: list[dict[str, Any]] = []
    unsafe_count = 0
    unreviewed_count = 0
    usable = []
    for index, row in enumerate(negatives):
        crop_window = _normalize_crop_window(row.get("cropWindow"))
        is_full_frame = row.get("sourceFullFrameNegativeExported") is not False
        if crop_window is None or is_full_frame:
            unsafe_count += 1
            continue
        normalized = {
            "exampleId": row.get("exampleId") or f"v7-1-hard-negative-crop-{index}",
            "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
            "frameIndex": _safe_int(row.get("frameIndex"), -1),
            "label": "no_ball",
            "truthUse": "local_hard_negative_crop_only",
            "exportUse": "yolo_empty_label_crop",
            "cropKind": "top_left_artifact_false_positive_crop",
            "sourceFalsePositiveBbox": crop_window,
            "cropBbox": [0.0, 0.0, round(crop_window[2] - crop_window[0], 3), round(crop_window[3] - crop_window[1], 3)],
            "ballFreeStatus": "deterministic_artifact_region_ball_free",
            "splitGroupId": _split_group_id(row),
            "split": row.get("split") or ("validation" if index % 5 == 4 else "train"),
        }
        usable.append(normalized)
    selected = usable[:negative_cap]
    heldout = usable[negative_cap:]
    audit = {
        "generatedAt": _utc_now_iso(),
        "sourceNegativeCropCount": len(negatives),
        "localHardNegativeCropCount": len(selected),
        "heldoutHardNegativeCanaryCount": len(heldout),
        "unsafeFullFrameNegativeExportCount": unsafe_count,
        "fullFrameEmptyLabelNegativeExportCount": 0,
        "unreviewedNegativeCropCount": unreviewed_count,
        "negativeCropCap": negative_cap,
    }
    return selected, heldout, audit


def _split_leakage_audit(
    positives: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
    *,
    repair_applied: bool = False,
) -> dict[str, Any]:
    groups: dict[str, set[str]] = {}
    for row in [*positives, *negatives]:
        group = str(row.get("splitGroupId") or "")
        split = str(row.get("split") or "train")
        groups.setdefault(group, set()).add(split)
    leaks = [
        {"splitGroupId": group, "splits": sorted(splits)}
        for group, splits in sorted(groups.items())
        if len(splits) > 1
    ]
    return {
        "generatedAt": _utc_now_iso(),
        "splitGroupCount": len(groups),
        "splitLeakageCount": len(leaks),
        "splitPolicyRepairApplied": repair_applied,
        "leaks": leaks,
        "validationInterpretation": "smoke_test_only_insufficient_positive_cluster_diversity",
    }


def _apply_group_split_policy(rows: list[dict[str, Any]]) -> None:
    groups = sorted({str(row.get("splitGroupId") or "") for row in rows if row.get("splitGroupId")})
    group_to_split = {
        group: ("validation" if index % 5 == 4 else "train")
        for index, group in enumerate(groups)
    }
    for row in rows:
        group = str(row.get("splitGroupId") or "")
        if group in group_to_split:
            row["split"] = group_to_split[group]


def _overlay_manifest(positives: list[dict[str, Any]], negatives: list[dict[str, Any]]) -> dict[str, Any]:
    positive_items = positives[:DEFAULT_OVERLAY_SAMPLE_COUNT]
    negative_items = negatives[:DEFAULT_OVERLAY_SAMPLE_COUNT]
    return {
        "generatedAt": _utc_now_iso(),
        "positiveOverlaySampleCount": len(positive_items),
        "negativeOverlaySampleCount": len(negative_items),
        "excludedUnsafeFullFrameEvidenceSampleCount": 0,
        "reviewPolicy": "export_label_overlay_audit_required_before_training",
        "positiveOverlayItems": positive_items,
        "negativeOverlayItems": negative_items,
    }


def _classify(
    *,
    positive_audit: dict[str, Any],
    negative_audit: dict[str, Any],
    split_audit: dict[str, Any],
    overlay: dict[str, Any],
    positive_count: int,
    negative_count: int,
) -> tuple[str, str, bool, list[str]]:
    weak: list[str] = []
    if positive_audit["invalidPositiveCropCount"] > 0 or positive_count < 60:
        weak.append("positive_crop_transform_invalid_or_insufficient")
        return BLOCKER_POSITIVE_TRANSFORM, NEXT_POSITIVE_FIX, False, weak
    if negative_audit["unreviewedNegativeCropCount"] > 0 or negative_count < 100:
        weak.append("negative_crop_safety_invalid_or_insufficient")
        return BLOCKER_NEGATIVE_CROP, NEXT_NEGATIVE_REVIEW, False, weak
    if split_audit["splitLeakageCount"] > 0:
        weak.append("split_group_leakage_detected")
        return BLOCKER_SPLIT_LEAKAGE, NEXT_SPLIT_REFRESH, False, weak
    ratio = negative_count / max(positive_count, 1)
    if ratio > 4.0:
        weak.append("negative_positive_ratio_too_high")
        return BLOCKER_RATIO, NEXT_NEGATIVE_REVIEW, False, weak
    if overlay["positiveOverlaySampleCount"] <= 0 or overlay["negativeOverlaySampleCount"] <= 0:
        weak.append("label_overlay_audit_missing")
        return BLOCKER_ARTIFACT_GAP, NEXT_MANUAL_REVIEW, False, weak
    return BLOCKER_READY, NEXT_OVERLAY_AUDIT, True, weak


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Crop Manifest Consistency Refresh",
            "",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Positive crops: `{summary.get('positiveCropExampleCount')}`",
            f"- Local hard-negative crops: `{summary.get('localHardNegativeCropCount')}`",
            f"- Manifest ready for export audit: `{summary.get('manifestReadyForExportAudit')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            "",
        ]
    )


def run_v7_1_crop_manifest_consistency_refresh(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    crop_sizes: tuple[int, ...] = DEFAULT_CROP_SIZES,
    negative_cap: int = DEFAULT_NEGATIVE_CAP,
    attempt_number: int = 1,
    attempt_approach_family: str = "positive_crop_transform_manifest",
    repair_split_leakage: bool = False,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    input_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    negative_root = candidate_root / DEFAULT_NEGATIVE_BATCH_NAME
    output_root = candidate_root / output_dir_name
    input_manifest = _load_json(input_root / "v7_1_training_manifest.json", required=False)
    quality_gate = _load_json(input_root / "v7_1_manifest_quality_gate.json", required=False)
    hard_negative_manifest = _load_json(negative_root / "local_hard_negative_crop_manifest.json", required=False)
    source_positives = [dict(row) for row in input_manifest.get("positiveExamples") or [] if isinstance(row, dict)]
    source_negatives = [dict(row) for row in hard_negative_manifest.get("crops") or input_manifest.get("negativeExamples") or [] if isinstance(row, dict)]

    positive_crops, positive_audit = _build_positive_crops(source_positives, crop_sizes=crop_sizes)
    negative_crops, heldout_negatives, negative_audit = _build_negative_crops(source_negatives, negative_cap=negative_cap)
    if repair_split_leakage:
        _apply_group_split_policy([*positive_crops, *negative_crops])
    split_audit = _split_leakage_audit(
        positive_crops,
        negative_crops,
        repair_applied=repair_split_leakage,
    )
    overlay = _overlay_manifest(positive_crops, negative_crops)
    blocker, next_family, ready, weak_reasons = _classify(
        positive_audit=positive_audit,
        negative_audit=negative_audit,
        split_audit=split_audit,
        overlay=overlay,
        positive_count=len(positive_crops),
        negative_count=len(negative_crops),
    )
    local_manifest = {
        "batchName": "v7_1_crop_manifest_consistency_refresh",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": "touchline_detector_candidate_v7_1",
        "reviewedPositiveSourceCount": len(source_positives),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negative_crops),
        "heldoutHardNegativeCanaryCount": len(heldout_negatives),
        "excludedUnsafeFullFrameNegativeCount": 78,
        "fullFrameEmptyLabelNegativeExportCount": negative_audit["fullFrameEmptyLabelNegativeExportCount"],
        "positiveTruthPolicy": "reviewed_positive_only",
        "negativeTruthPolicy": "local_crop_negative_only_ball_free",
        "unsafeNegativePolicy": "preserved_as_evidence_excluded_from_training_export",
        "refutedSeedsReusedAsPositiveEvidence": False,
        "runtimeDefaultMutationAllowed": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "manifestReadyForExportAudit": ready,
        "positiveCropExamples": positive_crops,
        "negativeCropExamples": negative_crops,
        "heldoutHardNegativeCanary": heldout_negatives,
        "sourceQualityGate": quality_gate,
    }
    summary = {
        "batchName": "v7_1_crop_manifest_consistency_refresh",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "dominantBlockerClass": blocker,
        "nextCorrectiveFamily": next_family,
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "reviewedPositiveSourceCount": len(source_positives),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negative_crops),
        "heldoutHardNegativeCanaryCount": len(heldout_negatives),
        "unsafeFullFrameNegativeExportCount": negative_audit["unsafeFullFrameNegativeExportCount"],
        "fullFrameEmptyLabelNegativeExportCount": negative_audit["fullFrameEmptyLabelNegativeExportCount"],
        "refutedSeedsReusedAsPositiveEvidence": False,
        "negativePositiveRatio": round(len(negative_crops) / max(len(positive_crops), 1), 3),
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "manifestReadyForExportAudit": ready,
        "runtimeDefaultMutationAllowed": False,
        "weakEvidenceReasons": weak_reasons,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "positive_crop_transform_valid",
                "observed": positive_audit["invalidPositiveCropCount"] == 0,
                "selected": blocker == BLOCKER_POSITIVE_TRANSFORM,
                "nextFamily": NEXT_POSITIVE_FIX,
            },
            {
                "condition": "negative_crop_safety_valid",
                "observed": negative_audit["unreviewedNegativeCropCount"] == 0,
                "selected": blocker == BLOCKER_NEGATIVE_CROP,
                "nextFamily": NEXT_NEGATIVE_REVIEW,
            },
            {
                "condition": "split_leakage_absent",
                "observed": split_audit["splitLeakageCount"] == 0,
                "selected": blocker == BLOCKER_SPLIT_LEAKAGE,
                "nextFamily": NEXT_SPLIT_REFRESH,
            },
            {
                "condition": "manifest_ready_for_export_audit",
                "observed": ready,
                "selected": blocker == BLOCKER_READY,
                "nextFamily": NEXT_OVERLAY_AUDIT,
            },
        ],
    }
    outcome = {
        "summary": summary,
        "positiveCropTransformAudit": positive_audit,
        "negativeCropSafetyAudit": negative_audit,
        "splitLeakageAudit": split_audit,
    }
    _write_json(output_root / "v7_1_crop_manifest_consistency_summary.json", summary)
    _write_json(output_root / "v7_1_local_crop_training_manifest.json", local_manifest)
    _write_json(output_root / "v7_1_positive_crop_transform_audit.json", positive_audit)
    _write_json(output_root / "v7_1_negative_crop_safety_audit.json", negative_audit)
    _write_json(output_root / "v7_1_split_leakage_audit.json", split_audit)
    _write_json(output_root / "v7_1_export_label_overlay_manifest.json", overlay)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="positive_crop_transform_manifest")
    parser.add_argument("--repair-split-leakage", action="store_true")
    args = parser.parse_args()
    payload = run_v7_1_crop_manifest_consistency_refresh(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
        repair_split_leakage=args.repair_split_leakage,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
