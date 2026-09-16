from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_1_training_manifest_prep as manifest_prep


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest_bundle(tmp_path: Path, *, include_unsafe_negative: bool = False) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    suite_root = tmp_path / "benchmark_suites/frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "touchline_detector_candidate_v7_training_prep_v1/v7_training_manifest.json",
        {
            "positiveExamples": [
                {
                    "exampleId": f"positive-{frame}",
                    "frameIndex": frame,
                    "sourceClipId": "trimed-5min.mp4",
                    "bbox": {"x1": 40.0, "y1": 40.0, "x2": 60.0, "y2": 60.0},
                    "truthUse": "reviewed_positive_training_seed",
                    "split": "train" if index % 3 else "validation",
                }
                for index, frame in enumerate(range(10, 40))
            ],
            "negativeExamples": [
                {
                    "exampleId": "unsafe-negative-20",
                    "frameIndex": 20,
                    "sourceClipId": "trimed-5min.mp4",
                    "truthUse": "negative_only_refuted_seed",
                }
            ]
            if include_unsafe_negative
            else [],
        },
    )
    conversion_root = candidate_root / "v7_negative_crop_conversion_plan_v1"
    _write_json(
        conversion_root / "v7_negative_crop_conversion_summary.json",
        {
            "dominantBlockerClass": "v7_negative_crop_conversion_ready",
            "roadmapAdvanceAllowed": True,
            "positiveExamplesPreserved": 30,
            "unsafeFullFrameNegativeExcludedCount": 78,
            "localHardNegativeCropCount": 5,
            "nextCorrectiveFamily": "v7_1_training_manifest_prep",
        },
    )
    _write_json(
        conversion_root / "local_hard_negative_crop_manifest.json",
        {
            "cropCount": 5,
            "crops": [
                {
                    "exampleId": f"crop-{frame}",
                    "frameIndex": frame,
                    "sourceClipId": "trimed-5min.mp4",
                    "cropWindow": [0.0, 0.0, 200.0, 230.0],
                    "truthUse": "local_hard_negative_top_left_artifact",
                    "sourceFullFrameNegativeExported": False,
                }
                for frame in (0, 25, 50, 75, 100)
            ],
        },
    )
    _write_json(
        conversion_root / "excluded_full_frame_negative_manifest.json",
        {"excluded": [{"exampleId": "unsafe-negative-20", "frameIndex": 20}]},
    )
    return candidate_root


def test_v7_1_manifest_prep_builds_ready_manifest_without_unsafe_negatives(tmp_path: Path) -> None:
    candidate_root = _write_manifest_bundle(tmp_path)

    payload = manifest_prep.run_v7_1_training_manifest_prep(
        storage_root=tmp_path,
        min_negative_examples=5,
    )

    output_root = candidate_root / "v7_1_training_manifest_prep_v1"
    summary = _load_json(output_root / "v7_1_training_manifest_prep_summary.json")
    manifest = _load_json(output_root / "v7_1_training_manifest.json")
    quality_gate = _load_json(output_root / "v7_1_manifest_quality_gate.json")

    assert payload["dominantBlockerClass"] == "v7_1_training_manifest_ready"
    assert summary["trainingPrepReady"] is True
    assert summary["positiveExampleCount"] == 30
    assert summary["negativeExampleCount"] == 5
    assert summary["unsafeFullFrameNegativeCount"] == 0
    assert summary["nextCorrectiveFamily"] == "touchline_detector_candidate_v7_1_training"
    assert len(manifest["positiveExamples"]) == 30
    assert len(manifest["negativeExamples"]) == 5
    assert manifest["negativeTruthPolicy"] == "local_crop_hard_negatives_only"
    assert all(row["truthUse"] == "local_hard_negative_top_left_artifact" for row in manifest["negativeExamples"])
    assert all(row["sourceFullFrameNegativeExported"] is False for row in manifest["negativeExamples"])
    assert quality_gate["refutedSeedPositiveLabelCount"] == 0
    assert quality_gate["unsafeFullFrameNegativeCount"] == 0
    assert quality_gate["groupedSplitRequired"] is True


def test_v7_1_manifest_prep_blocks_if_unsafe_full_frame_negative_leaks(tmp_path: Path) -> None:
    _write_manifest_bundle(tmp_path, include_unsafe_negative=True)

    payload = manifest_prep.run_v7_1_training_manifest_prep(
        storage_root=tmp_path,
        include_legacy_negatives=True,
    )

    assert payload["dominantBlockerClass"] == "v7_1_manifest_unsafe_negative_leak"
    assert payload["trainingPrepReady"] is False
    assert payload["nextCorrectiveFamily"] == "v7_negative_crop_conversion_plan"
