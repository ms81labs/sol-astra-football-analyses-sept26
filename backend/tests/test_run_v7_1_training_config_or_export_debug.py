from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_training_config_or_export_debug as debug_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_tiny_debug_bundle(tmp_path: Path, *, label_rows: int = 10) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    tiny_root = candidate_root / "v7_1_tiny_overfit_sanity_train_v1"
    dataset_root = tiny_root / "tiny_dataset"
    for index in range(10):
        image = dataset_root / "images" / "train" / f"positive-{index}.jpg"
        label = dataset_root / "labels" / "train" / f"positive-{index}.txt"
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"jpg")
        label.write_text("0 0.5 0.5 0.1 0.1\n" if index < label_rows else "", encoding="utf-8")
    for index in range(20):
        image = dataset_root / "images" / "train" / f"negative-{index}.jpg"
        label = dataset_root / "labels" / "train" / f"negative-{index}.txt"
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"jpg")
        label.write_text("", encoding="utf-8")
    for split in ("val", "canary"):
        (dataset_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (dataset_root / "data.yaml").write_text(
        f"path: {dataset_root}\ntrain: images/train\nval: images/val\nnc: 1\nnames:\n  0: ball\n",
        encoding="utf-8",
    )
    weights = tiny_root / "train_run" / "weights" / "best.pt"
    weights.parent.mkdir(parents=True, exist_ok=True)
    weights.write_bytes(b"trained-weights")
    (tiny_root / "train_run" / "results.csv").parent.mkdir(parents=True, exist_ok=True)
    (tiny_root / "train_run" / "results.csv").write_text(
        "\n".join(
            [
                "epoch,train/box_loss,train/cls_loss,train/dfl_loss,val/box_loss,val/cls_loss,val/dfl_loss",
                "1,3.0,10.0,1.4,3.2,10.4,1.3",
                "2,2.0,8.0,1.0,2.8,9.0,1.1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        tiny_root / "training_run_summary.json",
        {
            "trainingCompleted": True,
            "bestWeightsPath": "/workspace/remote/best.pt",
            "bestWeightsPathLocal": str(weights),
            "modelPath": "/workspace/weights/yolov10n.pt",
            "trainKwargs": {"data": str(dataset_root / "data.yaml"), "imgsz": 256, "device": "cpu"},
        },
    )
    _write_json(
        tiny_root / "v7_1_tiny_overfit_sanity_train_audit.json",
        {
            "primaryBlocker": "v7_1_tiny_train_positive_localization_failure",
            "tinyTrainPositiveLocalizationHitRate": 0.0,
        },
    )
    _write_json(
        tiny_root / "inference_audit" / "train_positive_predictions.json",
        {"rows": [{"exampleId": f"positive-{index}", "predCropBbox": None} for index in range(10)]},
    )
    return candidate_root


def test_training_config_debug_detects_wrong_checkpoint_contract(tmp_path: Path) -> None:
    candidate_root = _write_tiny_debug_bundle(tmp_path)

    payload = debug_batch.run_v7_1_training_config_or_export_debug(storage_root=tmp_path)

    output_root = candidate_root / "v7_1_training_config_or_export_debug_v1"
    checkpoint_audit = json.loads((output_root / "checkpoint_hash_audit.json").read_text(encoding="utf-8"))
    loader_audit = json.loads((output_root / "yolo_dataset_loader_audit.json").read_text(encoding="utf-8"))
    results_audit = json.loads((output_root / "results_csv_audit.json").read_text(encoding="utf-8"))

    assert payload["primaryBlocker"] == "v7_1_wrong_checkpoint_for_inference"
    assert payload["nextRecommendedNextLever"] == "v7_1_tiny_overfit_retry_with_verified_config"
    assert checkpoint_audit["bestWeightsPathLocalExists"] is True
    assert checkpoint_audit["tinyScriptLegacyBestWeightsLocalPathPresent"] is False
    assert checkpoint_audit["remoteBestWeightsPathExistsLocally"] is False
    assert loader_audit["trainerObservedLabelRowCount"] == 10
    assert loader_audit["trainerObservedPositiveLabelImageCount"] == 10
    assert results_audit["boxLossNonZero"] is True
    assert results_audit["boxLossDecreased"] is True


def test_training_config_debug_detects_label_ingestion_failure(tmp_path: Path) -> None:
    _write_tiny_debug_bundle(tmp_path, label_rows=0)

    payload = debug_batch.run_v7_1_training_config_or_export_debug(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_1_yolo_trainer_label_ingestion_failure"
    assert payload["nextRecommendedNextLever"] == "v7_1_data_yaml_label_path_fix"
