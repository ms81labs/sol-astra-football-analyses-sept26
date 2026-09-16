from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_3_crop_probe_precision_guardrail_audit as guardrail


def _write_image(path: Path, *, positive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    image[:, :] = (34, 122, 54)
    if positive:
        cv2.circle(image, (128, 128), 8, (245, 245, 245), -1)
    cv2.imwrite(str(path), image)


def _write_label(path: Path, *, positive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0 0.50000000 0.50000000 0.06250000 0.06250000\n" if positive else "", encoding="utf-8")


def _write_v7_3_bounded_bundle(tmp_path: Path, *, local_checkpoint: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    bounded_root = candidate_root / "v7_3_bounded_retrain_v1"
    dataset_root = bounded_root / "bounded_dataset_snapshot"
    for index in range(438):
        _write_image(dataset_root / "images" / "train" / f"train-positive-{index:03d}.jpg", positive=True)
        _write_label(dataset_root / "labels" / "train" / f"train-positive-{index:03d}.txt", positive=True)
    for index in range(144):
        _write_image(dataset_root / "images" / "train" / f"train-negative-{index:03d}.jpg")
        _write_label(dataset_root / "labels" / "train" / f"train-negative-{index:03d}.txt")
    for index in range(171):
        _write_image(dataset_root / "images" / "val" / f"val-positive-{index:03d}.jpg", positive=True)
        _write_label(dataset_root / "labels" / "val" / f"val-positive-{index:03d}.txt", positive=True)
    for index in range(36):
        _write_image(dataset_root / "images" / "val" / f"val-negative-{index:03d}.jpg")
        _write_label(dataset_root / "labels" / "val" / f"val-negative-{index:03d}.txt")
    for index in range(20):
        _write_image(dataset_root / "images" / "canary" / f"canary-{index:03d}.jpg")
        _write_label(dataset_root / "labels" / "canary" / f"canary-{index:03d}.txt")
    (dataset_root / "data.yaml").write_text(
        f"path: {dataset_root}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  0: ball\n",
        encoding="utf-8",
    )
    best = bounded_root / "train_run" / "weights" / "best.pt"
    last = bounded_root / "train_run" / "weights" / "last.pt"
    if local_checkpoint:
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_bytes(b"v7-3-best")
        last.write_bytes(b"v7-3-last")
    (bounded_root / "v7_3_bounded_retrain_summary.json").write_text(
        json.dumps(
            {
                "batchName": "v7_3_bounded_retrain",
                "goalAchieved": True,
                "checkpointContractPassed": local_checkpoint,
                "inferenceUsedTrainedWeights": local_checkpoint,
                "inferenceUsedRemotePath": False,
                "inferenceUsedBaseModel": False,
                "selectedCheckpointForVerdict": "best.pt",
                "bestWeightsPathLocal": str(best) if local_checkpoint else None,
                "lastWeightsPathLocal": str(last) if local_checkpoint else None,
                "trainingDatasetPositiveCount": 609,
                "trainingDatasetHardNegativeCount": 180,
                "heldoutHardNegativeCanaryCount": 20,
            }
        ),
        encoding="utf-8",
    )
    return candidate_root


def _predictor(mode: str = "pass") -> guardrail.Predictor:
    def predictor(*, audit_sets: dict[str, list[dict[str, object]]], conf: float, **_kwargs: object) -> dict[str, object]:
        predictions: dict[str, list[dict[str, object]]] = {}
        for set_name, rows in audit_sets.items():
            predictions[set_name] = []
            for row in rows:
                pred = None
                confidence = None
                if row["truthType"] == "positive" and conf <= 0.10:
                    pred = [120.0, 120.0, 136.0, 136.0]
                    confidence = 0.62
                    if mode == "val_fail" and set_name == "bounded_val_positive":
                        pred = None
                        confidence = None
                elif mode == "top_left" and row["truthType"] == "negative" and conf <= 0.10:
                    pred = [0.0, 0.0, 220.0, 220.0]
                    confidence = 0.18
                predictions[set_name].append(
                    {
                        "exampleId": row["exampleId"],
                        "confidence": confidence,
                        "classId": 0 if pred else None,
                        "predCropBbox": pred,
                    }
                )
        return {"predictions": predictions}

    return predictor


def test_v7_3_crop_probe_guardrail_passes_strong_precision_and_recall(tmp_path: Path) -> None:
    candidate_root = _write_v7_3_bounded_bundle(tmp_path)

    payload = guardrail.run_v7_3_crop_probe_precision_guardrail_audit(
        storage_root=tmp_path,
        predictor=_predictor(),
    )

    output_root = candidate_root / "v7_3_crop_probe_precision_guardrail_audit_v1"
    summary = json.loads((output_root / "v7_3_crop_probe_precision_guardrail_summary.json").read_text(encoding="utf-8"))

    assert payload["batchName"] == "v7_3_crop_probe_precision_guardrail_audit"
    assert payload["primaryBlocker"] is None
    assert payload["checkpointContractPassed"] is True
    assert payload["trainingExecuted"] is False
    assert payload["boundedTrainPositiveLocalizationHitRate"] == 1.0
    assert payload["boundedValPositiveLocalizationHitRate"] == 1.0
    assert payload["heldoutCanaryFalsePositiveFrameRate"] == 0.0
    assert payload["oldTopLeftArtifactFalsePositiveFrameRate"] == 0.0
    assert payload["secondaryConcern"] is None
    assert payload["recallGuardrailStrength"] == "strong_pass"
    assert payload["nextRecommendedNextLever"] == "v7_3_full_pipeline_non_promotion_eval"
    assert payload["promotionReady"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["attemptPlanFamilies"] == [
        "v7_3_crop_probe_precision_guardrail_audit",
        "v7_3_guardrail_operating_point_repair",
        "v7_3_guardrail_blocker_summary",
    ]
    assert summary["precisionGuardrailPassed"] is True
    assert (output_root / "validation_positive_miss_analysis.json").exists()
    assert (output_root / "worst_positive_misses_contact_sheet.jpg").exists()
    assert (output_root / "top_left_artifact_contact_sheet.jpg").exists()


def test_v7_3_crop_probe_guardrail_fails_closed_without_local_checkpoint(tmp_path: Path) -> None:
    _write_v7_3_bounded_bundle(tmp_path, local_checkpoint=False)
    predictor_calls: list[object] = []

    def predictor(**kwargs: object) -> dict[str, object]:
        predictor_calls.append(kwargs)
        return {"predictions": {}}

    payload = guardrail.run_v7_3_crop_probe_precision_guardrail_audit(storage_root=tmp_path, predictor=predictor)

    assert predictor_calls == []
    assert payload["primaryBlocker"] == "v7_3_crop_probe_checkpoint_contract_failure"
    assert payload["checkpointContractPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_3_training_config_or_export_debug"


def test_v7_3_crop_probe_guardrail_blocks_top_left_artifact_regression(tmp_path: Path) -> None:
    _write_v7_3_bounded_bundle(tmp_path)

    payload = guardrail.run_v7_3_crop_probe_precision_guardrail_audit(
        storage_root=tmp_path,
        predictor=_predictor(mode="top_left"),
    )

    assert payload["primaryBlocker"] == "v7_3_crop_probe_top_left_artifact_regression"
    assert payload["topLeftArtifactShare"] > 0.0
    assert payload["nextRecommendedNextLever"] == "v7_3_artifact_regression_debug"


def test_v7_3_crop_probe_guardrail_routes_hard_validation_recall_failure_to_diversity(tmp_path: Path) -> None:
    _write_v7_3_bounded_bundle(tmp_path)

    payload = guardrail.run_v7_3_crop_probe_precision_guardrail_audit(
        storage_root=tmp_path,
        predictor=_predictor(mode="val_fail"),
    )

    assert payload["primaryBlocker"] == "v7_3_crop_probe_validation_recall_insufficient"
    assert payload["boundedTrainPositiveLocalizationHitRate"] == 1.0
    assert payload["boundedValPositiveLocalizationHitRate"] == 0.0
    assert payload["nextRecommendedNextLever"] == "v7_3_positive_diversity_refresh"
