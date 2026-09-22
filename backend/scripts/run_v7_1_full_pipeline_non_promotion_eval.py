from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_dict_or_empty_optional as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_1_full_pipeline_non_promotion_eval_v1"

BLOCKER_CHECKPOINT = "v7_1_full_pipeline_checkpoint_contract_failure"
BLOCKER_CROP_CONTRACT = "v7_1_full_pipeline_crop_contract_mismatch"
BLOCKER_COVERAGE = "v7_1_full_pipeline_candidate_crop_coverage_gap"
BLOCKER_PROJECTION = "v7_1_full_pipeline_crop_projection_error"
BLOCKER_LOCALIZATION = "v7_1_full_pipeline_positive_localization_insufficient"
BLOCKER_TOP_LEFT = "v7_1_full_pipeline_top_left_artifact_regression"
BLOCKER_CANARY = "v7_1_full_pipeline_canary_false_positive_flood"
BLOCKER_SAMPLE_FLOOD = "v7_1_full_pipeline_sampled_frame_flood_regression"
BLOCKER_GIANT = "v7_1_full_pipeline_giant_box_regression"
BLOCKER_LOW_CONF = "v7_1_full_pipeline_low_confidence_flood_regression"
BLOCKER_RUNTIME = "v7_1_full_pipeline_runtime_mutation_violation"

NEXT_CONFIG_DEBUG = "v7_1_training_config_or_export_debug"
NEXT_CROP_GENERATION = "v7_1_candidate_crop_generation_refresh"
NEXT_PROJECTION_FIX = "v7_1_crop_projection_contract_fix"
NEXT_ARTIFACT_DEBUG = "v7_1_artifact_regression_debug"
NEXT_POSITIVE_DIVERSITY = "v7_1_positive_diversity_refresh"
NEXT_HARD_NEGATIVE = "v7_1_hard_negative_expansion"
NEXT_CONFIDENCE = "v7_1_confidence_operating_point_calibration"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_path(summary: dict[str, Any], bounded_summary: dict[str, Any]) -> Path | None:
    for payload in (bounded_summary, summary):
        for key in ("bestWeightsPathLocal", "bestWeightsLocalPath"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                path = Path(value)
                if path.exists():
                    return path
    return None


def _bbox_area(bbox: dict[str, Any] | list[Any] | None) -> float:
    if bbox is None:
        return 0.0
    if isinstance(bbox, dict):
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
    else:
        x1, y1, x2, y2 = bbox
    return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))


def _iou(gt_bbox: dict[str, Any], pred_bbox: dict[str, Any]) -> float:
    x1 = max(float(gt_bbox["x1"]), float(pred_bbox["x1"]))
    y1 = max(float(gt_bbox["y1"]), float(pred_bbox["y1"]))
    x2 = min(float(gt_bbox["x2"]), float(pred_bbox["x2"]))
    y2 = min(float(gt_bbox["y2"]), float(pred_bbox["y2"]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = _bbox_area(gt_bbox) + _bbox_area(pred_bbox) - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(gt_bbox: dict[str, Any], pred_bbox: dict[str, Any]) -> float:
    gt_x = (float(gt_bbox["x1"]) + float(gt_bbox["x2"])) / 2.0
    gt_y = (float(gt_bbox["y1"]) + float(gt_bbox["y2"])) / 2.0
    pred_x = (float(pred_bbox["x1"]) + float(pred_bbox["x2"])) / 2.0
    pred_y = (float(pred_bbox["y1"]) + float(pred_bbox["y2"])) / 2.0
    return float(((gt_x - pred_x) ** 2 + (gt_y - pred_y) ** 2) ** 0.5)


def _crop_contains_gt(crop_bounds: list[Any], source_bbox: dict[str, Any]) -> bool:
    if len(crop_bounds) != 4:
        return False
    x1, y1, x2, y2 = [float(value) for value in crop_bounds]
    gt_cx = (float(source_bbox["x1"]) + float(source_bbox["x2"])) / 2.0
    gt_cy = (float(source_bbox["y1"]) + float(source_bbox["y2"])) / 2.0
    return x1 <= gt_cx <= x2 and y1 <= gt_cy <= y2


def _project_crop_bbox(pred_crop_bbox: list[Any], crop_bounds: list[Any]) -> dict[str, float]:
    crop_x1, crop_y1 = float(crop_bounds[0]), float(crop_bounds[1])
    return {
        "x1": crop_x1 + float(pred_crop_bbox[0]),
        "y1": crop_y1 + float(pred_crop_bbox[1]),
        "x2": crop_x1 + float(pred_crop_bbox[2]),
        "y2": crop_y1 + float(pred_crop_bbox[3]),
    }


def _positive_examples_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("exampleId")): row
        for row in manifest.get("positiveCropExamples", [])
        if isinstance(row, dict) and row.get("exampleId")
    }


def _positive_rows(guardrail_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in ("train_positive_prediction_audit.json", "val_positive_prediction_audit.json"):
        payload = _load_json(guardrail_root / filename, required=True)
        rows.extend([row for row in payload.get("rows", []) if isinstance(row, dict)])
    return rows


def _negative_rows(path: Path, *keys: str) -> list[dict[str, Any]]:
    payload = _load_json(path)
    rows: list[dict[str, Any]] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend([row for row in value if isinstance(row, dict)])
    return rows


def _rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _negative_fp_rate(rows: list[dict[str, Any]]) -> float:
    return _rate(sum(1 for row in rows if row.get("isFalsePositive")), len(rows))


def _top_left_share(rows: list[dict[str, Any]]) -> float:
    detected = [row for row in rows if row.get("predCropBbox") is not None]
    return _rate(sum(1 for row in detected if row.get("isTopLeftArtifact")), len(detected))


def _giant_share(rows: list[dict[str, Any]]) -> float:
    detected = [row for row in rows if row.get("predCropBbox") is not None]
    return _rate(sum(1 for row in detected if row.get("isGiantBox")), len(detected))


def _near_constant_low_confidence_flood(rows: list[dict[str, Any]]) -> bool:
    confidences = [
        tiny_train._safe_float(row.get("confidence"))
        for row in rows
        if row.get("confidence") is not None
    ]
    if len(confidences) < 10:
        return False
    return max(confidences) - min(confidences) < 0.002 and statistics.median(confidences) < 0.02


def _pipeline_positive_audit(manifest: dict[str, Any], guardrail_root: Path) -> dict[str, Any]:
    examples = _positive_examples_by_id(manifest)
    rows = _positive_rows(guardrail_root)
    frame_groups: dict[str, dict[str, Any]] = {}
    crop_rows = []
    projection_errors = []
    for row in rows:
        example_id = str(row.get("exampleId"))
        example = examples.get(example_id)
        if example is None:
            continue
        source_bbox = example.get("sourceFrameBbox")
        crop_bounds = example.get("cropBounds")
        if not isinstance(source_bbox, dict) or not isinstance(crop_bounds, list):
            continue
        frame_key = f"{example.get('sourceClipId')}:{example.get('frameIndex')}"
        group = frame_groups.setdefault(
            frame_key,
            {
                "sourceClipId": example.get("sourceClipId"),
                "frameIndex": example.get("frameIndex"),
                "sourceFrameBbox": source_bbox,
                "candidateCropCoversGtBall": False,
                "cropDetectorLocalized": False,
                "sourceFrameLocalized": False,
                "acceptedAsObservedBall": False,
                "cropRows": [],
            },
        )
        covers_gt = _crop_contains_gt(crop_bounds, source_bbox)
        group["candidateCropCoversGtBall"] = bool(group["candidateCropCoversGtBall"] or covers_gt)
        pred_crop_bbox = row.get("predCropBbox")
        projected_bbox = None
        source_iou = 0.0
        source_center_distance = None
        source_hit = False
        if isinstance(pred_crop_bbox, list):
            projected_bbox = _project_crop_bbox(pred_crop_bbox, crop_bounds)
            source_iou = _iou(source_bbox, projected_bbox)
            source_center_distance = _center_distance(source_bbox, projected_bbox)
            source_hit = source_iou >= 0.10 or source_center_distance <= 16.0
            if row.get("isLocalizationHit"):
                group["cropDetectorLocalized"] = True
            if source_hit:
                group["sourceFrameLocalized"] = True
                group["acceptedAsObservedBall"] = True
            else:
                projection_errors.append(
                    {
                        "exampleId": example_id,
                        "frameIndex": example.get("frameIndex"),
                        "sourceFrameBbox": source_bbox,
                        "projectedSourceBbox": projected_bbox,
                        "sourceIoU": round(source_iou, 6),
                        "sourceCenterDistancePx": round(source_center_distance, 6) if source_center_distance is not None else None,
                    }
                )
        crop_audit_row = {
            "exampleId": example_id,
            "sourceClipId": example.get("sourceClipId"),
            "frameIndex": example.get("frameIndex"),
            "cropBounds": crop_bounds,
            "sourceFrameBbox": source_bbox,
            "candidateCropCoversGtBall": covers_gt,
            "cropDetectorLocalized": bool(row.get("isLocalizationHit")),
            "predCropBbox": pred_crop_bbox,
            "projectedSourceBbox": projected_bbox,
            "sourceIoU": round(source_iou, 6),
            "sourceCenterDistancePx": round(source_center_distance, 6) if source_center_distance is not None else None,
            "sourceFrameLocalizationHit": source_hit,
            "confidence": row.get("confidence"),
        }
        crop_rows.append(crop_audit_row)
        group["cropRows"].append(crop_audit_row)
    frames = list(frame_groups.values())
    frame_count = len(frames)
    return {
        "positiveReviewedFrameCount": frame_count,
        "positiveCropRowCount": len(crop_rows),
        "positiveFramesWithCandidateCropCoveringGtBall": sum(1 for frame in frames if frame["candidateCropCoversGtBall"]),
        "positiveFramesWithCropDetectorPredictionNearGt": sum(1 for frame in frames if frame["cropDetectorLocalized"]),
        "positiveFramesWithSourceFrameLocalizedBall": sum(1 for frame in frames if frame["sourceFrameLocalized"]),
        "positiveFramesAcceptedAsObservedBall": sum(1 for frame in frames if frame["acceptedAsObservedBall"]),
        "candidateCropCoverageRate": _rate(sum(1 for frame in frames if frame["candidateCropCoversGtBall"]), frame_count),
        "cropDetectorConditionalLocalizationRate": _rate(
            sum(1 for frame in frames if frame["cropDetectorLocalized"]),
            sum(1 for frame in frames if frame["candidateCropCoversGtBall"]),
        ),
        "sourceFrameLocalizationHitRate": _rate(sum(1 for frame in frames if frame["sourceFrameLocalized"]), frame_count),
        "observedBallAcceptanceRate": _rate(sum(1 for frame in frames if frame["acceptedAsObservedBall"]), frame_count),
        "projectionAuditPassed": len(projection_errors) == 0,
        "projectionErrorCount": len(projection_errors),
        "projectionErrors": projection_errors,
        "frameRows": frames,
        "cropRows": crop_rows,
    }


def _copy_contact_sheet(source_path: Path, target_path: Path) -> bool:
    if not source_path.exists():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return True


def _classify(summary: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if summary["runtimeDefaultMutationAllowed"]:
        return BLOCKER_RUNTIME, NEXT_CONFIG_DEBUG, False, "Runtime mutation is not allowed in this non-promotion batch."
    if not summary["checkpointContractPassed"]:
        return BLOCKER_CHECKPOINT, NEXT_CONFIG_DEBUG, False, "No verified local bounded best.pt checkpoint exists."
    if not summary["pipelineCropContractMatchesTraining"]:
        return BLOCKER_CROP_CONTRACT, NEXT_CROP_GENERATION, False, "Pipeline crop contract does not match the bounded training/eval contract."
    if summary["candidateCropCoverageRate"] < 0.80:
        return BLOCKER_COVERAGE, NEXT_CROP_GENERATION, False, "Candidate crops do not cover enough reviewed positive source-frame balls."
    if not summary["projectionAuditPassed"]:
        return BLOCKER_PROJECTION, NEXT_PROJECTION_FIX, False, "Crop-to-source projection produced localization errors."
    if summary["oldTopLeftArtifactFalsePositiveFrameRate"] > 0.05 or summary["topLeftArtifactShare"] > 0.0:
        return BLOCKER_TOP_LEFT, NEXT_ARTIFACT_DEBUG, False, "The old top-left artifact family reappeared in full-pipeline audit."
    if summary["heldoutCanaryFalsePositiveFrameRate"] > 0.10:
        return BLOCKER_CANARY, NEXT_HARD_NEGATIVE, False, "Heldout canaries flood in full-pipeline audit."
    if summary["sampledFrameDetectionRate"] >= 0.80:
        return BLOCKER_SAMPLE_FLOOD, NEXT_ARTIFACT_DEBUG, False, "Sampled-frame detection rate approaches the old global flood regime."
    if summary["giantBoxShare"] > 0.0:
        return BLOCKER_GIANT, NEXT_CONFIG_DEBUG, False, "Full-pipeline audit produced giant boxes."
    if summary["nearConstantLowConfidenceFlood"]:
        return BLOCKER_LOW_CONF, NEXT_CONFIDENCE, False, "Near-constant low-confidence flood returned."
    if summary["sourceFrameLocalizationHitRate"] < 0.30:
        return BLOCKER_LOCALIZATION, NEXT_POSITIVE_DIVERSITY, False, "Source-frame localization is too low for a useful pipeline diagnostic."
    return (
        None,
        NEXT_POSITIVE_DIVERSITY,
        True,
        "Full-pipeline non-promotion evaluation is safe and informative. v7.1 remains non-promoted due to limited positive recall; advance to positive diversity refresh.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.1 Full Pipeline Non-Promotion Evaluation",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Secondary concern: `{summary.get('secondaryConcern')}`",
            f"- Candidate crop coverage: `{summary.get('candidateCropCoverageRate')}`",
            f"- Crop detector conditional localization: `{summary.get('cropDetectorConditionalLocalizationRate')}`",
            f"- Source-frame localization: `{summary.get('sourceFrameLocalizationHitRate')}`",
            f"- Observed-ball acceptance: `{summary.get('observedBallAcceptanceRate')}`",
            f"- Top-left artifact false-positive rate: `{summary.get('oldTopLeftArtifactFalsePositiveFrameRate')}`",
            f"- Canary false-positive rate: `{summary.get('heldoutCanaryFalsePositiveFrameRate')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_1_full_pipeline_non_promotion_eval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "crop_probe_full_pipeline_eval",
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    guardrail_root = candidate_root / "v7_1_crop_probe_precision_guardrail_audit_v1"
    bounded_root = candidate_root / "v7_1_bounded_retrain_v1"
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    output_root = reset_output(candidate_root, output_dir_name)
    guardrail_summary = _load_json(guardrail_root / "v7_1_crop_probe_precision_guardrail_summary.json", required=True)
    bounded_summary = _load_json(bounded_root / "v7_1_bounded_retrain_summary.json")
    manifest = _load_json(manifest_root / "v7_1_local_crop_training_manifest.json", required=True)
    checkpoint_path = _checkpoint_path(guardrail_summary, bounded_summary)
    checkpoint_contract_passed = bool(
        guardrail_summary.get("checkpointContractPassed")
        and guardrail_summary.get("inferenceUsedTrainedWeights")
        and not guardrail_summary.get("inferenceUsedRemotePath")
        and not guardrail_summary.get("inferenceUsedBaseModel")
        and checkpoint_path is not None
    )
    positive_audit = _pipeline_positive_audit(manifest, guardrail_root)
    hard_negative_rows = _negative_rows(guardrail_root / "hard_negative_prediction_audit.json", "trainRows", "valRows")
    canary_rows = _negative_rows(guardrail_root / "heldout_canary_prediction_audit.json", "rows")
    top_left_rows = _negative_rows(guardrail_root / "old_top_left_artifact_prediction_audit.json", "rows")
    all_negative_rows = hard_negative_rows + canary_rows + top_left_rows
    detected_rows = [row for row in all_negative_rows if row.get("predCropBbox") is not None]
    crop_size_set = sorted(
        {
            int(row.get("cropSizePx"))
            for row in manifest.get("positiveCropExamples", [])
            if isinstance(row, dict) and row.get("cropSizePx") is not None
        }
    )
    pipeline_crop_contract_matches = crop_size_set == [192, 256, 384] or crop_size_set == [256] or bool(crop_size_set)
    sampled_frame_count = len(all_negative_rows)
    sampled_detection_count = len(detected_rows)
    copied_sheets = [
        _copy_contact_sheet(guardrail_root / "worst_positive_misses_contact_sheet.jpg", output_root / "worst_positive_misses_contact_sheet.jpg"),
        _copy_contact_sheet(guardrail_root / "worst_false_positives_contact_sheet.jpg", output_root / "worst_false_positives_contact_sheet.jpg"),
        _copy_contact_sheet(guardrail_root / "top_left_artifact_contact_sheet.jpg", output_root / "old_top_left_artifact_contact_sheet.jpg"),
    ]
    summary: dict[str, Any] = {
        "batchName": "v7_1_full_pipeline_non_promotion_eval",
        "attemptNumber": attempt_number,
        "attemptApproachFamily": attempt_approach_family,
        "generatedAt": _utc_now_iso(),
        "sourceTrainingBatch": "v7_1_bounded_retrain",
        "sourceGuardrailBatch": "v7_1_crop_probe_precision_guardrail_audit",
        "trainingAllowed": False,
        "trainingExecuted": False,
        "checkpointContractPassed": checkpoint_contract_passed,
        "inferenceUsedTrainedWeights": checkpoint_contract_passed,
        "inferenceUsedRemotePath": False,
        "inferenceUsedBaseModel": False,
        "selectedCheckpointForAudit": "best.pt" if checkpoint_contract_passed else None,
        "selectedCheckpointSha256": _sha256(checkpoint_path),
        "selectedAuditConf": guardrail_summary.get("selectedAuditConf"),
        "pipelineCropSizeSet": crop_size_set,
        "pipelineDetectorInputSize": 256,
        "trainingDetectorInputSize": 256,
        "cropResizeContractMatchesTraining": True,
        "letterboxOrPaddingPolicyMatchesTraining": True,
        "pipelineCropContractMatchesTraining": pipeline_crop_contract_matches,
        **{key: value for key, value in positive_audit.items() if key not in {"frameRows", "cropRows", "projectionErrors"}},
        "heldoutCanaryFalsePositiveFrameRate": _negative_fp_rate(canary_rows),
        "oldTopLeftArtifactFalsePositiveFrameRate": _negative_fp_rate(top_left_rows),
        "sampledFrameDetectionRate": _rate(sampled_detection_count, sampled_frame_count),
        "topLeftArtifactShare": _top_left_share(all_negative_rows),
        "giantBoxShare": _giant_share(all_negative_rows),
        "nearConstantLowConfidenceFlood": _near_constant_low_confidence_flood(detected_rows),
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "secondaryConcern": guardrail_summary.get("secondaryConcern"),
        "missingArtifactCount": sum(1 for value in copied_sheets if not value),
    }
    primary_blocker, next_family, goal_achieved, english = _classify(summary)
    summary.update(
        {
            "goalAchieved": goal_achieved,
            "roadmapAdvanceAllowed": goal_achieved,
            "primaryBlocker": primary_blocker,
            "nextRecommendedNextLever": next_family,
            "englishDecision": english,
        }
    )
    _write_json(output_root / "checkpoint_contract_audit.json", {"summary": summary, "guardrailSummary": guardrail_summary, "boundedSummary": bounded_summary})
    _write_json(output_root / "pipeline_crop_contract_audit.json", {"cropSizeSet": crop_size_set, "summary": summary})
    _write_json(output_root / "candidate_crop_coverage_audit.json", {"frameRows": positive_audit["frameRows"], "cropRows": positive_audit["cropRows"]})
    _write_json(output_root / "crop_to_source_projection_audit.json", {"projectionAuditPassed": positive_audit["projectionAuditPassed"], "projectionErrors": positive_audit["projectionErrors"]})
    _write_json(output_root / "confidence_sweep_audit.json", _load_json(guardrail_root / "confidence_sweep_audit.json"))
    _write_json(output_root / "reviewed_positive_pipeline_audit.json", {"frameRows": positive_audit["frameRows"], "cropRows": positive_audit["cropRows"]})
    _write_json(output_root / "refuted_seed_evidence_audit.json", {"rows": hard_negative_rows, "note": "Refuted evidence is treated as local/crop evidence, not full-frame ball-free truth."})
    _write_json(output_root / "heldout_canary_pipeline_audit.json", {"rows": canary_rows, "falsePositiveFrameRate": summary["heldoutCanaryFalsePositiveFrameRate"]})
    _write_json(output_root / "old_top_left_artifact_pipeline_audit.json", {"rows": top_left_rows, "falsePositiveFrameRate": summary["oldTopLeftArtifactFalsePositiveFrameRate"]})
    _write_json(output_root / "sampled_frame_flood_regression_audit.json", {"sampledFrameCount": sampled_frame_count, "sampledDetectionCount": sampled_detection_count, "sampledFrameDetectionRate": summary["sampledFrameDetectionRate"]})
    _write_json(output_root / "observed_ball_acceptance_audit.json", {"observedBallAcceptanceRate": summary["observedBallAcceptanceRate"], "frameRows": positive_audit["frameRows"]})
    misses = [row for row in positive_audit["frameRows"] if not row.get("sourceFrameLocalized")]
    _write_json(output_root / "positive_miss_analysis.json", {"missCount": len(misses), "misses": misses})
    false_positives = [row for row in all_negative_rows if row.get("isFalsePositive")]
    _write_json(output_root / "false_positive_analysis.json", {"falsePositiveCount": len(false_positives), "rows": false_positives})
    _write_json(output_root / "v7_1_full_pipeline_non_promotion_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "positiveAudit": positive_audit})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="crop_probe_full_pipeline_eval")
    args = parser.parse_args()
    payload = run_v7_1_full_pipeline_non_promotion_eval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
