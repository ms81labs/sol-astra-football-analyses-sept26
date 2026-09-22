from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_optional as _load_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.run_v7_1_crop_manifest_consistency_refresh import (  # noqa: E402
    _apply_group_split_policy,
    _split_leakage_audit,
)

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
V72_MANIFEST_DIR_NAME = "v7_2_training_manifest_prep_v1"
MISS_RESOLUTION_DIR_NAME = "football_external_soccernet_detector_miss_manual_review_resolution_v1"

NEXT_EXPORT_AUDIT = "v7_3_export_label_overlay_audit"
NEXT_MISS_CAPTURE = "football_external_soccernet_detector_miss_capture_and_label_queue"
NEXT_MISS_REVIEW = "football_external_soccernet_detector_miss_manual_review_resolution"
NEXT_V72_MANIFEST = "v7_2_training_manifest_prep"
NEXT_MANUAL_REVIEW = "manual_review_required"

BLOCKER_NO_MISSES = "v7_3_manifest_no_reviewed_real_detector_misses"
BLOCKER_MISS_BBOX = "v7_3_manifest_real_miss_bbox_quality_gap"
BLOCKER_V72_BASELINE = "v7_3_manifest_v7_2_baseline_manifest_missing"
BLOCKER_UNSAFE_NEGATIVE = "v7_3_manifest_unsafe_negative_leak"
BLOCKER_SPLIT = "v7_3_manifest_split_leakage"
BLOCKER_ARTIFACT = "v7_3_manifest_artifact_gap"

CROP_SIZES = (128, 192, 256)
MIN_REAL_MISS_SOURCE_COUNT = 1
MIN_BASE_POSITIVE_CROPS = 300
MIN_NEGATIVE_CROPS = 100
MIN_HELDOUT_CANARY = 20
MIN_BBOX_SIZE_PX = 2.0
MAX_BBOX_SIZE_PX = 80.0


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name




def _safe_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _bbox(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    x1 = _safe_float(value.get("x1"))
    y1 = _safe_float(value.get("y1"))
    x2 = _safe_float(value.get("x2"))
    y2 = _safe_float(value.get("y2"))
    if None in {x1, y1, x2, y2}:
        return None
    assert x1 is not None and y1 is not None and x2 is not None and y2 is not None
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        return None
    width = x2 - x1
    height = y2 - y1
    if width < MIN_BBOX_SIZE_PX or height < MIN_BBOX_SIZE_PX or width > MAX_BBOX_SIZE_PX or height > MAX_BBOX_SIZE_PX:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _bbox_center(bbox: dict[str, float]) -> tuple[float, float]:
    return (bbox["x1"] + bbox["x2"]) / 2.0, (bbox["y1"] + bbox["y2"]) / 2.0


def _crop_bounds_around_bbox(bbox: dict[str, float], crop_size: int) -> list[float]:
    cx, cy = _bbox_center(bbox)
    half = crop_size / 2.0
    return [round(cx - half, 3), round(cy - half, 3), round(cx + half, 3), round(cy + half, 3)]


def _local_bbox(bbox: dict[str, float], crop_bounds: list[float]) -> dict[str, float]:
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
    area = width * height
    if local_bbox["x1"] < 0 or local_bbox["y1"] < 0 or local_bbox["x2"] > crop_size or local_bbox["y2"] > crop_size:
        return False, "crop_local_bbox_outside_crop_bounds"
    if width <= 0 or height <= 0:
        return False, "crop_local_bbox_malformed"
    if width < 2 or height < 2 or width > 80 or height > 80 or area < 4 or area > 6400:
        return False, "crop_local_bbox_implausible_size"
    return True, "ok"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "v7_3_real_miss_manifest_prep",
                "successCriteria": [
                    "read reviewed SoccerNet real detector-miss truth",
                    "merge with the audited v7.2 crop manifest baseline",
                    "generate local positive crop records without training",
                    "route to v7.3 export/overlay audit only if all gates pass",
                ],
                "failureAdaptation": "If reviewed miss truth is missing, return to miss capture or review resolution.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "v7_3_manifest_geometry_repair",
                "successCriteria": [
                    "repair only bbox/crop geometry metadata",
                    "drop invalid crop variants rather than inventing labels",
                    "preserve v7.2 negative/canary safety invariants",
                ],
                "failureAdaptation": "If geometry remains invalid, route back to manual miss review.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "v7_3_manifest_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before export or training when manifest truth is incomplete.",
            },
        ],
    }


def _load_inputs(candidate_root: Path) -> dict[str, Any]:
    return {
        "v72Summary": _load_json(candidate_root / V72_MANIFEST_DIR_NAME / "v7_2_training_manifest_prep_summary.json"),
        "v72Manifest": _load_json(candidate_root / V72_MANIFEST_DIR_NAME / "v7_2_training_manifest.json"),
        "missSummary": _load_json(candidate_root / MISS_RESOLUTION_DIR_NAME / "detector_miss_manual_review_resolution_summary.json"),
        "missTruth": _load_json(candidate_root / MISS_RESOLUTION_DIR_NAME / "reviewed_real_detector_miss_truth_additions.json"),
    }


def _v72_baseline_ready(summary: dict[str, Any], manifest: dict[str, Any]) -> bool:
    return bool(
        isinstance(manifest, dict)
        and isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and len(manifest.get("positiveCropExamples") or []) >= MIN_BASE_POSITIVE_CROPS
        and len(manifest.get("negativeCropExamples") or []) >= MIN_NEGATIVE_CROPS
        and len(manifest.get("heldoutHardNegativeCanary") or []) >= MIN_HELDOUT_CANARY
        and _safe_int(manifest.get("unsafeFullFrameNegativeExportCount")) == 0
        and _safe_int(manifest.get("fullFrameEmptyLabelNegativeExportCount")) == 0
    )


def _miss_truth_ready(summary: dict[str, Any], truth: dict[str, Any]) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("v7_3TrainingDataReady") is True
        and _safe_int(summary.get("reviewedRealDetectorMissPositiveCount")) > 0
        and isinstance(truth.get("rows"), list)
    )


def _source_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row.get("sourceClipId") or "224p.mp4"), _safe_int(row.get("frameIndex"), -1)


def _normalize_real_miss_sources(rows: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: dict[tuple[str, int], dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("reviewStatus") != "reviewed_real_detector_miss_positive":
            continue
        bbox = _bbox(row.get("sourceFrameBbox"))
        frame = _safe_int(row.get("frameIndex"), -1)
        if bbox is None or frame < 0:
            invalid.append({"reviewItemId": row.get("reviewItemId"), "sourceFrameBbox": row.get("sourceFrameBbox"), "reason": "invalid_source_frame_bbox_or_frame"})
            continue
        normalized[_source_key(row)] = {
            "exampleId": row.get("reviewItemId") or f"soccernet-real-miss-{frame}",
            "sourceClipId": row.get("sourceClipId") or "224p.mp4",
            "frameIndex": frame,
            "sourceFrameBbox": bbox,
            "bbox": bbox,
            "sourceFrameWidth": 398,
            "sourceFrameHeight": 224,
            "sourceDataset": "soccernet",
            "sourceTruthBatch": "football_external_soccernet_detector_miss_manual_review_resolution_v1",
            "truthUse": "reviewed_soccernet_real_detector_miss_positive",
            "eventLabel": row.get("eventLabel"),
            "eventPositionMs": row.get("eventPositionMs"),
            "gameTime": row.get("gameTime"),
            "fullFrameImagePath": row.get("fullFrameImagePath"),
            "cropImagePath": row.get("cropImagePath"),
            "splitGroupId": row.get("splitGroupId") or f"soccernet-real-miss-{frame // 750:04d}",
            "visibilityClass": row.get("visibilityClass") or "clear",
            "contextTags": row.get("contextTags") if isinstance(row.get("contextTags"), list) else ["small_ball", "in_play"],
        }
    return [normalized[key] for key in sorted(normalized, key=lambda item: (item[0], item[1]))], invalid


def _build_real_miss_positive_crops(sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    crops: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    invalid_count = 0
    for source_index, row in enumerate(sources):
        bbox = _bbox(row.get("sourceFrameBbox"))
        for crop_size in CROP_SIZES:
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
            example_id = f"v7-3-soccernet-real-miss-crop-{row.get('frameIndex')}-{crop_size}"
            rows.append(
                {
                    "exampleId": example_id,
                    "sourcePositiveExampleId": row.get("exampleId"),
                    "frameIndex": row.get("frameIndex"),
                    "cropSizePx": crop_size,
                    "sourceFrameBbox": bbox,
                    "cropFrameBbox": crop_local_bbox,
                    "cropBounds": crop_bounds,
                    "valid": valid,
                    "reason": reason,
                }
            )
            if valid and bbox is not None and crop_bounds is not None and crop_local_bbox is not None:
                crops.append(
                    {
                        "exampleId": example_id,
                        "sourceClipId": row.get("sourceClipId") or "224p.mp4",
                        "frameIndex": row.get("frameIndex"),
                        "sourcePositiveExampleId": row.get("exampleId"),
                        "label": "ball",
                        "truthUse": "reviewed_soccernet_real_detector_miss_positive",
                        "exportUse": "yolo_positive_crop_with_ball_label",
                        "cropKind": "soccernet_real_miss_ball_centered_positive_crop",
                        "cropSizePx": crop_size,
                        "cropBounds": crop_bounds,
                        "sourceFrameBbox": bbox,
                        "cropFrameBbox": crop_local_bbox,
                        "sourceDataset": "soccernet",
                        "sourceTruthBatch": row.get("sourceTruthBatch"),
                        "fullFrameImagePath": row.get("fullFrameImagePath"),
                        "eventLabel": row.get("eventLabel"),
                        "eventPositionMs": row.get("eventPositionMs"),
                        "gameTime": row.get("gameTime"),
                        "splitGroupId": row.get("splitGroupId"),
                        "split": "validation" if source_index % 5 == 4 else "train",
                    }
                )
    return crops, {
        "generatedAt": _utc_now_iso(),
        "sourcePositiveCount": len(sources),
        "realMissPositiveCropExampleCount": len(crops),
        "invalidRealMissPositiveCropCount": invalid_count,
        "cropSizes": list(CROP_SIZES),
        "rows": rows,
    }


def _normalize_negative_rows(rows: list[Any]) -> tuple[list[dict[str, Any]], int]:
    normalized: list[dict[str, Any]] = []
    unsafe = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("truthUse") != "local_hard_negative_crop_only" or row.get("exportUse") != "yolo_empty_label_crop":
            unsafe += 1
            continue
        if row.get("sourceFullFrameNegativeExported") is True:
            unsafe += 1
            continue
        normalized.append(row)
    return normalized, unsafe


def _quality_gate(
    *,
    v72_ready: bool,
    miss_ready: bool,
    real_sources: list[dict[str, Any]],
    invalid_sources: list[dict[str, Any]],
    real_crops: list[dict[str, Any]],
    positive_crops: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
    canaries: list[dict[str, Any]],
    unsafe_negative_count: int,
    split_leakage_count: int,
    invalid_real_crop_count: int,
) -> dict[str, Any]:
    weak: list[str] = []
    if not v72_ready:
        weak.append("v7_2_baseline_manifest_missing_or_not_ready")
    if not miss_ready or len(real_sources) < MIN_REAL_MISS_SOURCE_COUNT:
        weak.append("reviewed_real_detector_miss_truth_missing")
    if invalid_sources or invalid_real_crop_count:
        weak.append("real_miss_bbox_quality_gap")
    if len(real_crops) < len(real_sources) * len(CROP_SIZES):
        weak.append("real_miss_crop_transform_gap")
    if len(positive_crops) < MIN_BASE_POSITIVE_CROPS:
        weak.append("positive_crop_example_count_below_minimum")
    if len(negatives) < MIN_NEGATIVE_CROPS:
        weak.append("local_hard_negative_count_below_minimum")
    if len(canaries) < MIN_HELDOUT_CANARY:
        weak.append("heldout_canary_count_below_minimum")
    if unsafe_negative_count:
        weak.append("unsafe_negative_leak")
    if split_leakage_count:
        weak.append("split_leakage")
    return {
        "generatedAt": _utc_now_iso(),
        "trainingPrepReady": not weak,
        "v72BaselineReady": v72_ready,
        "missTruthReady": miss_ready,
        "realMissReviewedPositiveSourceCount": len(real_sources),
        "realMissPositiveCropExampleCount": len(real_crops),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(canaries),
        "invalidRealMissSourceCount": len(invalid_sources),
        "invalidRealMissPositiveCropCount": invalid_real_crop_count,
        "unsafeFullFrameNegativeExportCount": unsafe_negative_count,
        "splitLeakageCount": split_leakage_count,
        "weakEvidenceReasons": weak,
    }


def _classify(quality: dict[str, Any]) -> tuple[str | None, str, bool]:
    weak = set(quality.get("weakEvidenceReasons") or [])
    if not weak:
        return None, NEXT_EXPORT_AUDIT, True
    if "reviewed_real_detector_miss_truth_missing" in weak:
        return BLOCKER_NO_MISSES, NEXT_MISS_CAPTURE, False
    if "real_miss_bbox_quality_gap" in weak or "real_miss_crop_transform_gap" in weak:
        return BLOCKER_MISS_BBOX, NEXT_MISS_REVIEW, False
    if "v7_2_baseline_manifest_missing_or_not_ready" in weak:
        return BLOCKER_V72_BASELINE, NEXT_V72_MANIFEST, False
    if "unsafe_negative_leak" in weak:
        return BLOCKER_UNSAFE_NEGATIVE, NEXT_MANUAL_REVIEW, False
    if "split_leakage" in weak:
        return BLOCKER_SPLIT, NEXT_MANUAL_REVIEW, False
    return BLOCKER_ARTIFACT, NEXT_MANUAL_REVIEW, False


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Training Manifest Prep From SoccerNet Real Misses",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Base v7.2 positive crops: `{summary.get('baseV72PositiveCropExampleCount')}`",
            f"- Real miss positive sources: `{summary.get('realMissReviewedPositiveSourceCount')}`",
            f"- Real miss positive crops: `{summary.get('realMissPositiveCropExampleCount')}`",
            f"- Total positive crops: `{summary.get('positiveCropExampleCount')}`",
            f"- Local hard negatives: `{summary.get('localHardNegativeCropCount')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_training_manifest_prep_from_soccernet_real_misses(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = candidate_root / output_dir_name
    output_root.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs(candidate_root)
    v72_manifest = inputs["v72Manifest"]
    v72_summary = inputs["v72Summary"]
    miss_summary = inputs["missSummary"]
    miss_truth = inputs["missTruth"]

    v72_ready = _v72_baseline_ready(v72_summary, v72_manifest)
    miss_ready = _miss_truth_ready(miss_summary, miss_truth)
    real_sources, invalid_sources = _normalize_real_miss_sources(miss_truth.get("rows") if isinstance(miss_truth.get("rows"), list) else [])
    real_crops, real_crop_audit = _build_real_miss_positive_crops(real_sources)
    base_positive_crops = [row for row in v72_manifest.get("positiveCropExamples") or [] if isinstance(row, dict)]
    negatives, unsafe_negatives = _normalize_negative_rows(v72_manifest.get("negativeCropExamples") if isinstance(v72_manifest.get("negativeCropExamples"), list) else [])
    canaries, unsafe_canaries = _normalize_negative_rows(v72_manifest.get("heldoutHardNegativeCanary") if isinstance(v72_manifest.get("heldoutHardNegativeCanary"), list) else [])
    all_positive_crops = [*base_positive_crops, *real_crops]
    _apply_group_split_policy([*all_positive_crops, *negatives])
    split_audit = _split_leakage_audit(all_positive_crops, negatives, repair_applied=True)
    quality = _quality_gate(
        v72_ready=v72_ready,
        miss_ready=miss_ready,
        real_sources=real_sources,
        invalid_sources=invalid_sources,
        real_crops=real_crops,
        positive_crops=all_positive_crops,
        negatives=negatives,
        canaries=canaries,
        unsafe_negative_count=unsafe_negatives + unsafe_canaries,
        split_leakage_count=split_audit["splitLeakageCount"],
        invalid_real_crop_count=real_crop_audit["invalidRealMissPositiveCropCount"],
    )
    primary_blocker, next_lever, ready = _classify(quality)
    summary = {
        "batchName": "v7_3_training_manifest_prep_from_soccernet_real_misses",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "trainingPrepReady": ready,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "baseV72PositiveCropExampleCount": len(base_positive_crops),
        "realMissReviewedPositiveSourceCount": len(real_sources),
        "realMissPositiveCropExampleCount": len(real_crops),
        "positiveCropExampleCount": len(all_positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(canaries),
        "invalidRealMissSourceCount": len(invalid_sources),
        "invalidRealMissPositiveCropCount": real_crop_audit["invalidRealMissPositiveCropCount"],
        "unsafeFullFrameNegativeExportCount": unsafe_negatives + unsafe_canaries,
        "fullFrameEmptyLabelNegativeExportCount": 0,
        "splitLeakageCount": split_audit["splitLeakageCount"],
        "weakEvidenceReasons": quality["weakEvidenceReasons"],
        "englishDecision": (
            "v7.3 manifest prep passed from reviewed SoccerNet real misses. Advance to export/overlay audit; do not train yet."
            if ready
            else "v7.3 manifest prep is blocked; do not export or train."
        ),
    }
    manifest = {
        "batchName": "v7_3_training_manifest_prep_from_soccernet_real_misses",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": "touchline_detector_candidate_v7_3",
        "sourceTrainingBatch": "v7_2_training_manifest_prep",
        "sourceRealMissReviewBatch": "football_external_soccernet_detector_miss_manual_review_resolution",
        "positiveTruthPolicy": "v7_2_reviewed_positive_plus_reviewed_soccernet_real_detector_miss_only",
        "negativeTruthPolicy": "v7_2_local_crop_negative_only_ball_free",
        "unsafeNegativePolicy": "preserved_as_evidence_excluded_from_training_export",
        "baseV72PositiveCropExampleCount": len(base_positive_crops),
        "realMissReviewedPositiveSourceCount": len(real_sources),
        "realMissPositiveCropExampleCount": len(real_crops),
        "positiveCropExampleCount": len(all_positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(canaries),
        "unsafeFullFrameNegativeExportCount": unsafe_negatives + unsafe_canaries,
        "fullFrameEmptyLabelNegativeExportCount": 0,
        "refutedSeedsReusedAsPositiveEvidence": False,
        "runtimeDefaultMutationAllowed": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "manifestReadyForExportAudit": ready,
        "realMissPositiveSourceExamples": real_sources,
        "positiveCropExamples": all_positive_crops,
        "negativeCropExamples": negatives,
        "heldoutHardNegativeCanary": canaries,
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "training_prep_ready", "observed": ready, "selected": ready, "nextFamily": NEXT_EXPORT_AUDIT},
            {"condition": "reviewed_real_miss_truth_missing", "observed": not miss_ready or not real_sources, "selected": primary_blocker == BLOCKER_NO_MISSES, "nextFamily": NEXT_MISS_CAPTURE},
            {"condition": "real_miss_bbox_quality_gap", "observed": bool(invalid_sources) or real_crop_audit["invalidRealMissPositiveCropCount"] > 0, "selected": primary_blocker == BLOCKER_MISS_BBOX, "nextFamily": NEXT_MISS_REVIEW},
            {"condition": "v7_2_baseline_missing", "observed": not v72_ready, "selected": primary_blocker == BLOCKER_V72_BASELINE, "nextFamily": NEXT_V72_MANIFEST},
        ],
    }
    _write_json(output_root / "v7_3_training_manifest_prep_summary.json", summary)
    _write_json(output_root / "v7_3_training_manifest.json", manifest)
    _write_json(output_root / "v7_3_manifest_quality_gate.json", quality)
    _write_json(output_root / "v7_3_real_miss_positive_crop_transform_audit.json", real_crop_audit)
    _write_json(output_root / "v7_3_real_miss_source_bbox_audit.json", {"generatedAt": _utc_now_iso(), "invalidRealMissSourceCount": len(invalid_sources), "rows": invalid_sources})
    _write_json(output_root / "v7_3_split_leakage_audit.json", split_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", _attempt_plan())
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "qualityGate": quality})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v7.3 manifest prep artifacts from reviewed SoccerNet real detector misses.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    args = parser.parse_args()
    payload = run_v7_3_training_manifest_prep_from_soccernet_real_misses(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
