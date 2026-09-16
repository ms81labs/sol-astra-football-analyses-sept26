from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_3_full_pipeline_non_promotion_eval as pipeline_eval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _touch_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"artifact")


def _positive_example(frame: int, size: int, *, split: str = "train") -> dict[str, object]:
    return {
        "exampleId": f"v7-3-pos-{frame}-{size}",
        "frameIndex": frame,
        "sourceClipId": "224p.mp4",
        "sourceDataset": "soccernet",
        "split": split,
        "cropBounds": [100.0, 50.0, 100.0 + size, 50.0 + size],
        "cropSizePx": size,
        "cropFrameBbox": {"x1": 120.0, "y1": 120.0, "x2": 136.0, "y2": 136.0},
        "sourceFrameBbox": {"x1": 220.0, "y1": 170.0, "x2": 236.0, "y2": 186.0},
    }


def _positive_row(example: dict[str, object], *, hit: bool = True) -> dict[str, object]:
    bbox = example["cropFrameBbox"]
    assert isinstance(bbox, dict)
    return {
        "exampleId": example["exampleId"],
        "truthType": "positive",
        "split": "train" if example["split"] == "train" else "val",
        "gtCropBbox": example["cropFrameBbox"],
        "predCropBbox": [bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]] if hit else None,
        "confidence": 0.8 if hit else None,
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
    guardrail_root = candidate_root / "v7_3_crop_probe_precision_guardrail_audit_v1"
    manifest_root = candidate_root / "v7_3_training_manifest_prep_from_soccernet_real_misses_v1"
    bounded_root = candidate_root / "v7_3_bounded_retrain_v1"
    best = bounded_root / "train_run" / "weights" / "best.pt"
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
    if mode == "projection_error":
        positives[1]["sourceFrameBbox"] = {"x1": 300.0, "y1": 170.0, "x2": 316.0, "y2": 186.0}

    _write_json(
        manifest_root / "v7_3_training_manifest.json",
        {
            "positiveCropExamples": positives,
            "positiveCropExampleCount": len(positives),
            "negativeCropExamples": [],
            "heldoutHardNegativeCanary": [],
            "promotionReady": False,
            "candidateReadyForEvaluation": False,
            "runtimeDefaultMutationAllowed": False,
        },
    )

    train_rows = [_positive_row(positives[0], hit=True)]
    val_rows = [_positive_row(positives[1], hit=mode != "coverage_gap"), _positive_row(positives[2], hit=True)]
    top_left_fp = mode == "top_left"
    _write_json(guardrail_root / "train_positive_prediction_audit.json", {"rows": train_rows})
    _write_json(guardrail_root / "val_positive_prediction_audit.json", {"rows": val_rows})
    _write_json(guardrail_root / "hard_negative_prediction_audit.json", {"trainRows": [], "valRows": []})
    _write_json(guardrail_root / "heldout_canary_prediction_audit.json", {"rows": [_negative_row("canary-1")]})
    _write_json(
        guardrail_root / "old_top_left_artifact_prediction_audit.json",
        {"rows": [_negative_row("top-left-1", false_positive=top_left_fp, top_left=top_left_fp)]},
    )
    _write_json(guardrail_root / "confidence_sweep_audit.json", {"selectedConf": 0.1, "sweeps": []})
    _touch_file(guardrail_root / "worst_positive_misses_contact_sheet.jpg")
    _touch_file(guardrail_root / "worst_false_positives_contact_sheet.jpg")
    _touch_file(guardrail_root / "top_left_artifact_contact_sheet.jpg")
    _write_json(
        guardrail_root / "v7_3_crop_probe_precision_guardrail_summary.json",
        {
            "goalAchieved": True,
            "checkpointContractPassed": local_checkpoint,
            "inferenceUsedTrainedWeights": local_checkpoint,
            "inferenceUsedRemotePath": False,
            "inferenceUsedBaseModel": False,
            "selectedCheckpointForAudit": "best.pt",
            "selectedCheckpointSha256": "abc",
            "selectedAuditConf": 0.1,
            "recallGuardrailStrength": "strong_pass",
            "secondaryConcern": None,
        },
    )
    _write_json(
        bounded_root / "v7_3_bounded_retrain_summary.json",
        {
            "bestWeightsPathLocal": str(best) if local_checkpoint else None,
            "checkpointContractPassed": local_checkpoint,
        },
    )
    return candidate_root


def test_v7_3_full_pipeline_eval_passes_strong_pipeline_signal(tmp_path: Path) -> None:
    candidate_root = _write_guardrail_bundle(tmp_path)

    payload = pipeline_eval.run_v7_3_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    output_root = candidate_root / "v7_3_full_pipeline_non_promotion_eval_v1"
    summary = json.loads((output_root / "v7_3_full_pipeline_non_promotion_summary.json").read_text(encoding="utf-8"))

    assert payload["primaryBlocker"] is None
    assert payload["trainingExecuted"] is False
    assert payload["checkpointContractPassed"] is True
    assert payload["pipelineCropContractMatchesTraining"] is True
    assert payload["projectionAuditPassed"] is True
    assert payload["positiveReviewedFrameCount"] == 3
    assert payload["candidateCropCoverageRate"] == 1.0
    assert payload["sourceFrameLocalizationHitRate"] == 1.0
    assert payload["observedBallAcceptanceRate"] == 1.0
    assert payload["nextRecommendedNextLever"] == "v7_3_promotion_readiness_validation"
    assert summary["promotionReady"] is False
    assert summary["candidateReadyForEvaluation"] is False
    assert (output_root / "candidate_crop_coverage_audit.json").exists()


def test_v7_3_full_pipeline_eval_fails_closed_without_checkpoint_contract(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, local_checkpoint=False)

    payload = pipeline_eval.run_v7_3_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_full_pipeline_checkpoint_contract_failure"
    assert payload["checkpointContractPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_training_config_or_export_debug"


def test_v7_3_full_pipeline_eval_routes_candidate_crop_coverage_gap(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, mode="coverage_gap")

    payload = pipeline_eval.run_v7_3_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_full_pipeline_candidate_crop_coverage_gap"
    assert payload["candidateCropCoverageRate"] < 1.0
    assert payload["nextRecommendedNextLever"] == "v7_3_candidate_crop_generation_refresh"


def test_v7_3_full_pipeline_eval_routes_projection_error(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, mode="projection_error")

    payload = pipeline_eval.run_v7_3_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_full_pipeline_crop_projection_error"
    assert payload["projectionAuditPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_crop_projection_contract_fix"


def test_v7_3_full_pipeline_eval_blocks_top_left_artifact_regression(tmp_path: Path) -> None:
    _write_guardrail_bundle(tmp_path, mode="top_left")

    payload = pipeline_eval.run_v7_3_full_pipeline_non_promotion_eval(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_3_full_pipeline_top_left_artifact_regression"
    assert payload["oldTopLeftArtifactFalsePositiveFrameRate"] == 1.0
    assert payload["nextRecommendedNextLever"] == "v7_3_artifact_regression_debug"
