from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_probe_threshold_preprocessing_fix as threshold_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bundle(tmp_path: Path) -> tuple[Path, Path]:
    storage_root = tmp_path
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    export_root = storage_root / "training_prep" / "touchline_detector_candidate_v7_training_v1" / "yolo_export"
    weights_path = candidate_root / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_bytes(b"fake weights")
    _write_json(
        candidate_root / "v7_probe_assist_integration_audit_v1" / "v7_probe_assist_integration_summary.json",
        {
            "dominantBlockerClass": "v7_preprocessing_or_threshold_mismatch",
            "nextCorrectiveFamily": "v7_probe_threshold_preprocessing_fix",
            "bestWeightsPathExists": True,
            "probePassAppearsInvoked": True,
            "rawProbeObservedBallFrames": 0,
        },
    )
    _write_json(
        candidate_root / "evaluation_contract.json",
        {
            "candidateWeights": {"bestWeightsPath": str(weights_path)},
            "candidateAuxiliaryBallModelPath": str(weights_path),
            "runtimeDefaultMutationAllowed": False,
        },
    )
    for split, frame_index in (("train", 240), ("val", 245)):
        image_path = export_root / "images" / split / f"positive-{frame_index}.jpg"
        label_path = export_root / "labels" / split / f"positive-{frame_index}.txt"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"not a real image for mocked tests")
        label_path.write_text("0 0.500000 0.500000 0.100000 0.100000\n", encoding="utf-8")
    return storage_root, weights_path


def test_threshold_audit_selects_contract_fix_when_offline_detections_exist(tmp_path: Path) -> None:
    storage_root, _weights_path = _write_bundle(tmp_path)

    def fake_predict(*, model_path: Path, image_paths: list[Path], conf_values: list[float], imgsz_values: list[int]) -> dict[str, object]:
        assert image_paths
        return {
            "modelPath": str(model_path),
            "grid": [{"conf": conf_values[0], "imgsz": imgsz_values[0], "detectedFrameCount": 2}],
            "perImage": [
                {"imagePath": str(image_paths[0]), "bestConfidence": 0.31, "bestClassId": 0, "detected": True},
                {"imagePath": str(image_paths[1]), "bestConfidence": 0.22, "bestClassId": 0, "detected": True},
            ],
            "detectedImageCount": 2,
            "wrongClassDetectionCount": 0,
        }

    payload = threshold_fix.run_v7_probe_threshold_preprocessing_fix(
        storage_root=storage_root,
        predictor=fake_predict,
    )

    output_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "v7_probe_threshold_preprocessing_fix_v1"
    summary = _load_json(output_root / "v7_probe_threshold_preprocessing_summary.json")
    matrix = _load_json(output_root / "offline_inference_threshold_matrix.json")
    outcome = _load_json(output_root / "batch_outcome_analysis.json")

    assert payload["dominantBlockerClass"] == "v7_offline_detections_available"
    assert summary["nextCorrectiveFamily"] == "v7_probe_threshold_contract_fix"
    assert matrix["detectedImageCount"] == 2
    assert outcome["runtimeDefaultMutationAllowed"] is False
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_threshold_audit_selects_training_refresh_when_model_still_detects_nothing(tmp_path: Path) -> None:
    storage_root, _weights_path = _write_bundle(tmp_path)

    def fake_predict(*, model_path: Path, image_paths: list[Path], conf_values: list[float], imgsz_values: list[int]) -> dict[str, object]:
        return {
            "modelPath": str(model_path),
            "grid": [],
            "perImage": [{"imagePath": str(path), "bestConfidence": 0.0, "bestClassId": None, "detected": False} for path in image_paths],
            "detectedImageCount": 0,
            "wrongClassDetectionCount": 0,
        }

    payload = threshold_fix.run_v7_probe_threshold_preprocessing_fix(
        storage_root=storage_root,
        predictor=fake_predict,
    )

    assert payload["dominantBlockerClass"] == "v7_model_quality_failure"
    assert payload["nextCorrectiveFamily"] == "v7_training_data_quality_refresh"


def test_threshold_audit_reports_artifact_gap_without_positive_images(tmp_path: Path) -> None:
    storage_root = tmp_path
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    weights_path = candidate_root / "weights" / "best.pt"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_bytes(b"fake weights")
    _write_json(
        candidate_root / "evaluation_contract.json",
        {"candidateWeights": {"bestWeightsPath": str(weights_path)}},
    )
    _write_json(
        candidate_root / "v7_probe_assist_integration_audit_v1" / "v7_probe_assist_integration_summary.json",
        {"dominantBlockerClass": "v7_preprocessing_or_threshold_mismatch"},
    )

    payload = threshold_fix.run_v7_probe_threshold_preprocessing_fix(storage_root=storage_root)

    assert payload["dominantBlockerClass"] == "v7_threshold_preprocessing_artifact_gap"
    assert payload["nextCorrectiveFamily"] == "v7_evaluation_proof_artifact_refresh"
