from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.run_promoted_v6_touchline_detector_candidate_v7_training as v7_training


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _synthetic_manifest() -> dict[str, object]:
    positives = [
        {
            "exampleId": "positive-train",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 10,
            "split": "train",
            "label": "ball",
            "bbox": {"x1": -5, "y1": 10, "x2": 25, "y2": 50},
            "truthUse": "reviewed_positive_training_seed",
        },
        {
            "exampleId": "positive-validation",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 20,
            "split": "validation",
            "label": "ball",
            "bbox": {"x1": 40, "y1": 40, "x2": 80, "y2": 90},
            "truthUse": "reviewed_positive_training_seed",
        },
    ]
    negatives = [
        {
            "exampleId": "negative-train",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 30,
            "split": "train",
            "label": "not_ball_refuted_seed",
            "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
            "truthUse": "negative_only_refuted_seed",
            "refutationUse": "negative_only_do_not_use_as_positive",
        },
        {
            "exampleId": "negative-validation",
            "sourceClipId": "trimed-5min.mp4",
            "frameIndex": 40,
            "split": "validation",
            "label": "not_ball_refuted_seed",
            "bbox": None,
            "truthUse": "negative_only_refuted_seed",
        },
    ]
    return {
        "batchName": "touchline_detector_candidate_v7_training_prep",
        "positiveExampleCount": len(positives),
        "negativeExampleCount": len(negatives),
        "positiveExamples": positives,
        "negativeExamples": negatives,
        "remainingPendingReviewCount": 0,
        "positiveBBoxMissingCount": 0,
    }


def test_write_yolo_export_writes_positive_and_empty_negative_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, Path]] = []

    def fake_extract(*, video_path: Path, frame_index: int, output_path: Path) -> tuple[int, int]:
        calls.append((video_path.name, frame_index, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpg")
        return 100, 100

    monkeypatch.setattr(v7_training, "_extract_frame_image", fake_extract)

    export = v7_training._write_yolo_export(
        training_manifest=_synthetic_manifest(),
        export_root=tmp_path / "yolo_export",
        videos_root=tmp_path / "videos",
    )

    assert export["positiveExampleCount"] == 2
    assert export["negativeExampleCount"] == 2
    assert export["invalidPositiveLabelCount"] == 0
    assert len(calls) == 4

    train_labels = sorted((tmp_path / "yolo_export" / "labels" / "train").glob("*.txt"))
    val_labels = sorted((tmp_path / "yolo_export" / "labels" / "val").glob("*.txt"))
    assert len(train_labels) == 2
    assert len(val_labels) == 2
    positive_label_text = [
        path.read_text(encoding="utf-8").strip()
        for path in train_labels + val_labels
        if "positive" in path.name
    ]
    negative_label_text = [
        path.read_text(encoding="utf-8").strip()
        for path in train_labels + val_labels
        if "negative" in path.name
    ]
    assert positive_label_text
    assert all(text.startswith("0 ") for text in positive_label_text)
    assert negative_label_text == ["", ""]

    dataset_yaml = (tmp_path / "yolo_export" / "dataset.yaml").read_text(encoding="utf-8")
    assert "train: images/train" in dataset_yaml
    assert "val: images/val" in dataset_yaml
    split_manifest = _load_json(tmp_path / "yolo_export" / "split_manifest.json")
    assert split_manifest["splits"]["train"]["positive"] == 1
    assert split_manifest["splits"]["train"]["negative"] == 1
    assert split_manifest["splits"]["val"]["positive"] == 1
    assert split_manifest["splits"]["val"]["negative"] == 1


def test_bbox_to_yolo_line_clamps_and_normalizes() -> None:
    line = v7_training._bbox_to_yolo_line(
        {"x1": -5, "y1": 10, "x2": 25, "y2": 50},
        frame_width=100,
        frame_height=100,
    )
    assert line == "0 0.125000 0.300000 0.250000 0.400000\n"

    assert (
        v7_training._bbox_to_yolo_line(
            {"x1": -5, "y1": -5, "x2": -1, "y2": -1},
            frame_width=100,
            frame_height=100,
        )
        is None
    )


def test_batch_outcome_advances_only_when_training_and_quality_gate_pass() -> None:
    passed = v7_training._build_batch_outcome_analysis(
        training_completed=True,
        weights_ready=True,
        training_quality_gate_passed=True,
        ready_for_detector_evaluation=True,
        primary_blocker=None,
        error_message=None,
    )
    assert passed["goalAchieved"] is True
    assert passed["nextRecommendedNextLever"] == "touchline_detector_candidate_v7_evaluation"

    failed = v7_training._build_batch_outcome_analysis(
        training_completed=True,
        weights_ready=True,
        training_quality_gate_passed=False,
        ready_for_detector_evaluation=False,
        primary_blocker="training_quality_gate_failed",
        error_message=None,
    )
    assert failed["goalAchieved"] is False
    assert failed["nextRecommendedNextLever"] == "v7_training_manifest_repair"


def test_v7_evaluation_contract_remains_compatible_with_generic_evaluator(tmp_path: Path) -> None:
    contract = v7_training._build_evaluation_contract(
        candidate_root=tmp_path / "candidate",
        best_weights_path="best.pt",
        last_weights_path="last.pt",
        ready_for_detector_evaluation=True,
        videos_root=tmp_path / "videos",
    )

    assert "localScreenTargetClipPath" in contract
    assert "remoteProofComparisonBaseline" in contract
    assert "activeFrozenBaseline" in contract
    assert contract["auxiliaryBallModelProfile"] == "ball_probe_only_v1"
    assert contract["candidateReadyForEvaluation"] is True
