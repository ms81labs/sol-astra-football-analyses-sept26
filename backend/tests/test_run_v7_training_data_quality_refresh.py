from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

import backend.scripts.run_v7_training_data_quality_refresh as data_quality


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_image(path: Path, *, width: int = 100, height: int = 100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.imwrite(str(path), image)


def _write_quality_bundle(tmp_path: Path, *, bad_label: bool = False) -> Path:
    storage_root = tmp_path
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    proof_root = storage_root / "pod_cycles" / "touchline-detector-candidate-v7-probe-assist-baseline-20260429111111"
    positive_image = storage_root / "training_prep/touchline_detector_candidate_v7_training_v1/yolo_export/images/train/positive-10.jpg"
    negative_image = storage_root / "training_prep/touchline_detector_candidate_v7_training_v1/yolo_export/images/train/negative-20.jpg"
    positive_label = storage_root / "training_prep/touchline_detector_candidate_v7_training_v1/yolo_export/labels/train/positive-10.txt"
    negative_label = storage_root / "training_prep/touchline_detector_candidate_v7_training_v1/yolo_export/labels/train/negative-20.txt"
    _write_image(positive_image)
    _write_image(negative_image)
    positive_label.parent.mkdir(parents=True, exist_ok=True)
    positive_label.write_text("0 0.500000 0.500000 0.200000 0.200000\n" if not bad_label else "0 40 40 60 60\n", encoding="utf-8")
    negative_label.parent.mkdir(parents=True, exist_ok=True)
    negative_label.write_text("", encoding="utf-8")
    _write_json(
        storage_root / "benchmark_suites/frozen-viable-baseline-slice-suite/touchline_detector_candidate_v7_training_prep_v1/v7_training_manifest.json",
        {
            "positiveExampleCount": 1,
            "negativeExampleCount": 1,
            "refutedSeedsReusedAsPositiveEvidence": True,
            "positiveExamples": [
                {
                    "exampleId": "positive-10",
                    "frameIndex": 10,
                    "sourceClipId": "trimed-5min.mp4",
                    "bbox": {"x1": 40.0, "y1": 40.0, "x2": 60.0, "y2": 60.0},
                    "truthUse": "reviewed_positive_training_seed",
                    "split": "train",
                }
            ],
            "negativeExamples": [
                {
                    "exampleId": "negative-20",
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "bbox": None,
                    "truthUse": "negative_only_refuted_seed",
                    "split": "train",
                }
            ],
        },
    )
    _write_json(
        storage_root / "training_prep/touchline_detector_candidate_v7_training_v1/yolo_export/split_manifest.json",
        {
            "exportedExamples": [
                {
                    "exampleId": "positive-10",
                    "frameIndex": 10,
                    "truthUse": "reviewed_positive_training_seed",
                    "imagePath": str(positive_image),
                    "labelPath": str(positive_label),
                    "positiveLabelWritten": True,
                },
                {
                    "exampleId": "negative-20",
                    "frameIndex": 20,
                    "truthUse": "negative_only_refuted_seed",
                    "imagePath": str(negative_image),
                    "labelPath": str(negative_label),
                    "positiveLabelWritten": False,
                },
            ]
        },
    )
    _write_json(
        candidate_root / "v7_probe_precision_guardrail_audit_v1/precision_guardrail_summary.json",
        {
            "dominantBlockerClass": "v7_low_conf_top_left_artifact_flood",
            "positiveLocalizationHitRate": 0.0,
            "negativeFrameHitRate": 1.0,
            "frameHitRate": 1.0,
            "proofSource": str(proof_root),
        },
    )
    _write_json(
        proof_root / "ball_truth_layers.json",
        {
            "probeObservedBall": {
                "rawRows": [
                    {
                        "Frame_ID": frame,
                        "Conf": 0.012,
                        "Source_X1": 0.0,
                        "Source_Y1": 0.0,
                        "Source_X2": 200.0,
                        "Source_Y2": 230.0,
                    }
                    for frame in (10, 20, 30)
                ]
            }
        },
    )
    return candidate_root


def test_training_data_quality_refresh_flags_localization_and_negative_semantics(tmp_path: Path) -> None:
    candidate_root = _write_quality_bundle(tmp_path)

    payload = data_quality.run_v7_training_data_quality_refresh(storage_root=tmp_path)

    output_root = candidate_root / "v7_training_data_quality_refresh_v1"
    summary = _load_json(output_root / "v7_training_data_quality_summary.json")
    localization = _load_json(output_root / "positive_localization_audit.json")
    export_audit = _load_json(output_root / "yolo_export_label_sanity_audit.json")
    negative_audit = _load_json(output_root / "negative_semantics_audit.json")
    mining_plan = _load_json(output_root / "hard_negative_mining_plan.json")
    delta = _load_json(output_root / "v7_1_training_manifest_delta.json")

    assert payload["dominantBlockerClass"] == "v7_negative_semantics_unsafe"
    assert summary["nextCorrectiveFamily"] == "v7_negative_semantics_review"
    assert localization["positiveLocalizationHitRate"] == 0.0
    assert export_audit["malformedLabelCount"] == 0
    assert export_audit["refutedSeedPositiveLabelCount"] == 0
    assert export_audit["refutedPositiveOverlapIsMetadataOnly"] is True
    assert negative_audit["unsafeFullFrameNegativeCount"] == 1
    assert mining_plan["topLeftArtifactCandidateCount"] == 3
    assert delta["groupedSplitRequired"] is True
    assert delta["positiveExampleCount"] == 1
    assert delta["negativeExampleCount"] == 1
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_training_data_quality_refresh_selects_export_fix_for_malformed_labels(tmp_path: Path) -> None:
    _write_quality_bundle(tmp_path, bad_label=True)

    payload = data_quality.run_v7_training_data_quality_refresh(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_yolo_export_label_malformed"
    assert payload["nextCorrectiveFamily"] == "v7_yolo_export_contract_fix"
