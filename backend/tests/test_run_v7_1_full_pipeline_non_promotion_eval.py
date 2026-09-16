from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_full_pipeline_non_promotion_eval as pipeline_eval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_example(frame: int, size: int, *, split: str = "train") -> dict[str, object]:
    return {
        "exampleId": f"pos-{frame}-{size}",
        "frameIndex": frame,
        "sourceClipId": "trimed-5min.mp4",
        "split": split,
        "cropBounds": [100.0, 200.0, 100.0 + size, 200.0 + size],
        "cropSizePx": size,
        "cropFrameBbox": {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "sourceFrameBbox": {"x1": 220.0, "y1": 320.0, "x2": 236.0, "y2": 336.0},
    }


def _positive_row(example: dict[str, object], *, hit: bool = True) -> dict[str, object]:
    return {
        "exampleId": example["exampleId"],
        "truthType": "positive",
        "split": "train" if example["split"] == "train" else "val",
        "gtCropBbox": example["cropFrameBbox"],
        "predCropBbox": [120.0, 120.0, 136.0, 136.0] if hit else None,
        "confidence": 0.4 if hit else None,
        "iou": 1.0 if hit else 0.0,
        "centerDistancePx": 0.0 if hit else None,
        "isLocalizationHit": hit,
        "isFalsePositive": False,
        "isTopLeftArtifact": False,
        "isGiantBox": False,
        "detectedBoxAreaToGtBoxAreaRatio": 1.0 if hit else None,
    }


def _negative_row(example_id: str, *, false_positive: bool = False, top_left: bool = False) -> dict[str, object]:
    return {
        "exampleId": example_id,
        "truthType": "negative",
        "split": "canary",
        "predCropBbox": [0.0, 0.0, 220.0, 220.0] if false_positive else None,
        "confidence": 0.2 if false_positive else None,
        "isFalsePositive": false_positive,
        "isTopLeftArtifact": top_left,
        "isGiantBox": false_positive,
    }


def _write_guardrail_bundle(tmp_path: Path, *, local_checkpoint: bool = True, mode: str = "pass") -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    guardrail_root = candidate_root / "v7_1_crop_probe_precision_guardrail_audit_v1"
    manifest_root = candidate_root / "v7_1_crop_manifest_consistency_refresh_v1"
    best = candidate_root / "v7_1_bounded_retrain_v1" / "train_run" / "weights" / "best.pt"
    if local_checkpoint:
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_bytes(b"best")
    positives = [
        _positive_example(100, 256, split="train"),
        _positive_example(200, 256, split="validation"),
        _positive_example(300, 256, split="validation"),
    ]
    if mode == "coverage_gap":
        positives[1]["cropBounds"] = [0.0, 0.0, 64.0, 64.0]
    _write_json(
        manifest_root / "v7_1_local_crop_training_manifest.json",
        {
            "positiveCropExamples": positives,
            "positiveCropExampleCount": len(positives),
            "negativeCropExamples": [],
            "heldoutHardNegativeCanary": [],
        },
    )
    train_rows = [_positive_row(positives[0], hit=mode != "positive_fail")]
    val_rows = [
        _positive_row(positives[1], hit=mode not in {"positive_fail", "coverage_gap"}),
        _positive_row(positives[2], hit=True),
    ]
    top_left_fp = mode == "top_left"
    _write_json(guardrail_root / "train_positive_prediction_audit.json", {"rows": train_rows})
    _write_json(guardrail_root / "val_positive_prediction_audit.json", {"rows": val_rows})
    _write_json(guardrail_root / "hard_negative_prediction_audit.json", {"trainRows": [], "valRows": []})
    _write_json(guardrail_root / "heldout_canary_prediction_audit.json", {"rows": [_negative_row("canary-1", false_positive=False)]})
    _write_json(
        guardrail_root / "old_top_left_artifact_prediction_audit.json",
        {"rows": [_negative_row("top-left-1", false_positive=top_left_fp, top_left=top_left_fp)]},
    )
    _write_json(
        guardrail_root / "v7_1_crop_probe_precision_guardrail_summary.json",
        {
            "goalAchieved": True,
            "checkpointContractPassed": local_checkpoint,
            "inferenceUsedTrainedWeights": local_checkpoint,
            "inferenceUsedRemotePath": False,
            "inferenceUsedBaseModel": False,
            "selectedCheckpointForAudit": "best.pt",
            "selectedCheckpointSha256": "abc",
            "selectedAuditConf": 0.1,
            "secondaryConcern": "v7_1_validation_positive_recall_limited",
        },
    )
    _write_json(
        candidate_root / "v7_1_bounded_retrain_v1" / "v7_1_bounded_retrain_summary.json",
        {
            "bestWeightsPathLocal": str(best) if local_checkpoint else None,
            "checkpointContractPassed": local_checkpoint,
        },
    )
    return candidate_root


def test_full_pipeline_eval_passes_and_reports_stage_metrics(tmp_path: Path) -> None:
    candidate_root = _write_guardrail_bundle(tmp_path)

    payload = pipeline_eval.run_v7_1_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    output_root = candidate_root / "v7_1_full_pipeline_non_promotion_eval_v1"
    summary = json.loads((output_root / "v7_1_full_pipeline_non_promotion_summary.json").read_text(encoding="utf-8"))

    assert payload["primaryBlocker"] is None
    assert payload["trainingExecuted"] is False
    assert payload["checkpointContractPassed"] is True
    assert payload["pipelineCropContractMatchesTraining"] is True
    assert payload["projectionAuditPassed"] is True
    assert payload["positiveReviewedFrameCount"] == 3
    assert payload["candidateCropCoverageRate"] == 1.0
    assert payload["sourceFrameLocalizationHitRate"] == 1.0
    assert payload["observedBallAcceptanceRate"] == 1.0
    assert payload["nextRecommendedNextLever"] == "v7_1_positive_diversity_refresh"
    assert summary["promotionReady"] is False
    assert (output_root / "candidate_crop_coverage_audit.json").exists()


def test_full_pipeline_eval_fails_closed_without_checkpoint_contract(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, local_checkpoint=False)

    payload = pipeline_eval.run_v7_1_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_full_pipeline_checkpoint_contract_failure"
    assert payload["checkpointContractPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_training_config_or_export_debug"


def test_full_pipeline_eval_routes_candidate_crop_coverage_gap(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, mode="coverage_gap")

    payload = pipeline_eval.run_v7_1_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_full_pipeline_candidate_crop_coverage_gap"
    assert payload["candidateCropCoverageRate"] < 1.0
    assert payload["nextRecommendedNextLever"] == "v7_1_candidate_crop_generation_refresh"


def test_full_pipeline_eval_blocks_top_left_artifact_regression(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, mode="top_left")

    payload = pipeline_eval.run_v7_1_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_full_pipeline_top_left_artifact_regression"
    assert payload["oldTopLeftArtifactFalsePositiveFrameRate"] == 1.0
    assert payload["nextRecommendedNextLever"] == "v7_1_artifact_regression_debug"
