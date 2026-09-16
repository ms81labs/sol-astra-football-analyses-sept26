from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_1_tiny_overfit_retry_with_verified_config as retry_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_image(path: Path, *, positive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    image[:, :] = (30, 120, 50)
    if positive:
        cv2.circle(image, (128, 128), 8, (245, 245, 245), -1)
    cv2.imwrite(str(path), image)


def _write_label(path: Path, *, positive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0 0.5 0.5 0.0625 0.0625\n" if positive else "", encoding="utf-8")


def _write_retry_bundle(tmp_path: Path, *, local_weights: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    tiny_root = candidate_root / "v7_1_tiny_overfit_sanity_train_v1"
    dataset_root = tiny_root / "tiny_dataset"
    for index in range(10):
        _write_image(dataset_root / "images" / "train" / f"positive-{index}.jpg", positive=True)
        _write_label(dataset_root / "labels" / "train" / f"positive-{index}.txt", positive=True)
    for index in range(20):
        _write_image(dataset_root / "images" / "train" / f"negative-{index}.jpg")
        _write_label(dataset_root / "labels" / "train" / f"negative-{index}.txt")
    for index in range(5):
        _write_image(dataset_root / "images" / "val" / f"positive-val-{index}.jpg", positive=True)
        _write_label(dataset_root / "labels" / "val" / f"positive-val-{index}.txt", positive=True)
    for index in range(10):
        _write_image(dataset_root / "images" / "val" / f"negative-val-{index}.jpg")
        _write_label(dataset_root / "labels" / "val" / f"negative-val-{index}.txt")
    for index in range(20):
        _write_image(dataset_root / "images" / "canary" / f"canary-{index}.jpg")
        _write_label(dataset_root / "labels" / "canary" / f"canary-{index}.txt")
    (dataset_root / "data.yaml").write_text(
        f"path: {dataset_root}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  0: ball\n",
        encoding="utf-8",
    )
    weights_root = tiny_root / "train_run" / "weights"
    best = weights_root / "best.pt"
    last = weights_root / "last.pt"
    if local_weights:
        best.parent.mkdir(parents=True, exist_ok=True)
        best.write_bytes(b"best")
        last.write_bytes(b"last")
    _write_json(
        tiny_root / "training_run_summary.json",
        {
            "trainingCompleted": True,
            "bestWeightsPath": "/workspace/remote/best.pt",
            "lastWeightsPath": "/workspace/remote/last.pt",
            "bestWeightsPathLocal": str(best) if local_weights else None,
            "lastWeightsPathLocal": str(last) if local_weights else None,
        },
    )
    _write_json(
        candidate_root / "v7_1_training_config_or_export_debug_v1" / "batch_outcome_analysis.json",
        {
            "summary": {
                "primaryBlocker": "v7_1_wrong_checkpoint_for_inference",
                "trainerObservedLabelRowCount": 10,
                "boxLossNonZero": True,
                "boxLossDecreased": True,
            }
        },
    )
    return candidate_root


def _passing_predictor(*, model_path: Path, audit_sets: dict[str, list[dict[str, object]]], conf: float, **_kwargs: object) -> dict[str, object]:
    predictions: dict[str, list[dict[str, object]]] = {}
    for set_name, rows in audit_sets.items():
        predictions[set_name] = []
        for row in rows:
            if row["truthType"] == "positive" and conf <= 0.05:
                predictions[set_name].append(
                    {
                        "exampleId": row["exampleId"],
                        "confidence": 0.18,
                        "classId": 0,
                        "predCropBbox": [120.0, 120.0, 136.0, 136.0],
                    }
                )
            else:
                predictions[set_name].append(
                    {
                        "exampleId": row["exampleId"],
                        "confidence": None,
                        "classId": None,
                        "predCropBbox": None,
                    }
                )
    return {"predictions": predictions}


def test_verified_retry_passes_when_local_checkpoint_localizes_memorized_positives(tmp_path: Path) -> None:
    candidate_root = _write_retry_bundle(tmp_path)

    payload = retry_batch.run_v7_1_tiny_overfit_retry_with_verified_config(
        storage_root=tmp_path,
        predictor=_passing_predictor,
    )

    output_root = candidate_root / "v7_1_tiny_overfit_retry_with_verified_config_v1"
    summary = json.loads((output_root / "v7_1_tiny_overfit_retry_summary.json").read_text(encoding="utf-8"))

    assert payload["primaryBlocker"] is None
    assert payload["checkpointContractPassed"] is True
    assert payload["inferenceUsedTrainedWeights"] is True
    assert payload["selectedAuditConf"] == 0.05
    assert payload["tinyTrainPositiveLocalizationHitRate"] == 1.0
    assert payload["nextRecommendedNextLever"] == "v7_1_bounded_retrain"
    assert summary["acceptedCheckpointResultKeys"] == [
        "bestWeightsLocalPath",
        "bestWeightsPathLocal",
        "lastWeightsLocalPath",
        "lastWeightsPathLocal",
    ]


def test_verified_retry_fails_closed_without_local_checkpoint(tmp_path: Path) -> None:
    _write_retry_bundle(tmp_path, local_weights=False)
    predictor_calls: list[object] = []

    def predictor(**kwargs: object) -> dict[str, object]:
        predictor_calls.append(kwargs)
        return {"predictions": {}}

    payload = retry_batch.run_v7_1_tiny_overfit_retry_with_verified_config(
        storage_root=tmp_path,
        predictor=predictor,
    )

    assert predictor_calls == []
    assert payload["primaryBlocker"] == "v7_1_tiny_retry_missing_local_checkpoint"
    assert payload["checkpointContractPassed"] is False
    assert payload["nextRecommendedNextLever"] == "v7_1_training_config_or_export_debug"
