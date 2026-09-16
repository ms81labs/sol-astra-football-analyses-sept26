from __future__ import annotations

import csv
import json
from pathlib import Path

import backend.app.training_quality_gate as training_quality_gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_results_csv(
    path: Path,
    *,
    metric_rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "epoch",
        "metrics/precision(B)",
        "metrics/recall(B)",
        "metrics/mAP50(B)",
        "metrics/mAP50-95(B)",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metric_rows:
            writer.writerow(row)


def _write_dataset(
    export_root: Path,
    *,
    train_positive: int,
    train_empty: int,
    val_positive: int,
    val_empty: int,
) -> Path:
    for split_name, positive_count, empty_count in (
        ("train", train_positive, train_empty),
        ("val", val_positive, val_empty),
    ):
        images_dir = export_root / "images" / split_name
        labels_dir = export_root / "labels" / split_name
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        for index in range(positive_count):
            stem = f"{split_name}-positive-{index}"
            (images_dir / f"{stem}.jpg").write_bytes(b"image")
            (labels_dir / f"{stem}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        for index in range(empty_count):
            stem = f"{split_name}-empty-{index}"
            (images_dir / f"{stem}.jpg").write_bytes(b"image")
            (labels_dir / f"{stem}.txt").write_text("", encoding="utf-8")
    dataset_yaml = export_root / "dataset.yaml"
    dataset_yaml.write_text(
        "\n".join(
            [
                f"path: {export_root}",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: ball",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return dataset_yaml


def _write_proposal_window_alignment_report(
    batch_root: Path,
    *,
    window_family: str = "proposal_windows_075",
    validation_positive_window_kind_counts: dict[str, int] | None = None,
) -> None:
    _write_json(
        batch_root / "proposal_window_alignment_report.json",
        {
            "windowFamily": window_family,
            "validationPositiveWindowKindCounts": dict(validation_positive_window_kind_counts or {}),
        },
    )


class _FakeBoxes:
    def __init__(self, count: int) -> None:
        self._count = count

    def __len__(self) -> int:
        return self._count


class _FakeResult:
    def __init__(self, count: int) -> None:
        self.boxes = _FakeBoxes(count)


class _FakeModel:
    def __init__(self, detections_by_name: dict[str, int]) -> None:
        self._detections_by_name = dict(detections_by_name)

    def predict(self, source: str, **_kwargs) -> list[_FakeResult]:
        return [_FakeResult(self._detections_by_name.get(Path(source).name, 0))]


def test_run_training_quality_gate_fails_when_val_split_has_no_positive_labels(tmp_path: Path) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v4"
    export_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v1" / "yolo_export"
    dataset_yaml_path = _write_dataset(
        export_root,
        train_positive=2,
        train_empty=0,
        val_positive=0,
        val_empty=3,
    )
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v4",
            "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
            "resultsCsvPath": str(candidate_root / "results.csv"),
        },
    )
    (candidate_root / "weights" / "best.pt").parent.mkdir(parents=True, exist_ok=True)
    (candidate_root / "weights" / "best.pt").write_bytes(b"weights")
    _write_results_csv(
        candidate_root / "results.csv",
        metric_rows=[
            {
                "epoch": 1,
                "metrics/precision(B)": 0.0,
                "metrics/recall(B)": 0.0,
                "metrics/mAP50(B)": 0.0,
                "metrics/mAP50-95(B)": 0.0,
            }
        ],
    )

    result = training_quality_gate.run_training_quality_gate(
        candidate_root=candidate_root,
        dataset_yaml_path=dataset_yaml_path,
        model_factory=lambda _model_path: _FakeModel(
            {
                "train-positive-0.jpg": 1,
                "train-positive-1.jpg": 1,
            }
        ),
    )

    assert result["trainingQualityGatePassed"] is False
    assert result["trainingQualityGatePrimaryBlocker"] == "validation_split_has_no_positive_labels"
    assert result["validationImageCount"] == 3
    assert result["validationPositiveLabelImageCount"] == 0
    assert result["validationEmptyLabelImageCount"] == 3
    assert result["localPositiveSanityImageCount"] == 2
    assert result["localPositiveSanityDetectedImageCount"] == 2
    assert (candidate_root / "training_quality_gate_v1" / "quality_gate_summary.json").exists()


def test_run_training_quality_gate_fails_when_local_positive_sanity_detects_nothing(tmp_path: Path) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v5"
    export_root = tmp_path / "training_prep" / "touchline_validation_gate_remediation_v1" / "yolo_export"
    dataset_yaml_path = _write_dataset(
        export_root,
        train_positive=3,
        train_empty=0,
        val_positive=1,
        val_empty=1,
    )
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v5",
            "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
            "resultsCsvPath": str(candidate_root / "results.csv"),
        },
    )
    (candidate_root / "weights" / "best.pt").parent.mkdir(parents=True, exist_ok=True)
    (candidate_root / "weights" / "best.pt").write_bytes(b"weights")
    _write_results_csv(
        candidate_root / "results.csv",
        metric_rows=[
            {
                "epoch": 1,
                "metrics/precision(B)": 0.31,
                "metrics/recall(B)": 0.27,
                "metrics/mAP50(B)": 0.29,
                "metrics/mAP50-95(B)": 0.11,
            }
        ],
    )

    result = training_quality_gate.run_training_quality_gate(
        candidate_root=candidate_root,
        dataset_yaml_path=dataset_yaml_path,
        model_factory=lambda _model_path: _FakeModel({}),
    )

    assert result["trainingQualityGatePassed"] is False
    assert result["trainingQualityGatePrimaryBlocker"] == "local_positive_sanity_zero_detections"
    assert result["validationInformative"] is True
    assert result["maxValidationMap50"] == 0.29
    assert result["localPositiveSanityImageCount"] == 4
    assert result["localPositiveSanityDetectedImageCount"] == 0


def test_run_training_quality_gate_passes_with_informative_val_and_nonzero_signal(tmp_path: Path) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v5"
    export_root = tmp_path / "training_prep" / "touchline_validation_gate_remediation_v1" / "yolo_export"
    dataset_yaml_path = _write_dataset(
        export_root,
        train_positive=2,
        train_empty=1,
        val_positive=2,
        val_empty=1,
    )
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v5",
            "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
            "resultsCsvPath": str(candidate_root / "results.csv"),
        },
    )
    (candidate_root / "weights" / "best.pt").parent.mkdir(parents=True, exist_ok=True)
    (candidate_root / "weights" / "best.pt").write_bytes(b"weights")
    _write_results_csv(
        candidate_root / "results.csv",
        metric_rows=[
            {
                "epoch": 1,
                "metrics/precision(B)": 0.42,
                "metrics/recall(B)": 0.37,
                "metrics/mAP50(B)": 0.4,
                "metrics/mAP50-95(B)": 0.16,
            },
            {
                "epoch": 2,
                "metrics/precision(B)": 0.47,
                "metrics/recall(B)": 0.39,
                "metrics/mAP50(B)": 0.45,
                "metrics/mAP50-95(B)": 0.19,
            },
        ],
    )

    result = training_quality_gate.run_training_quality_gate(
        candidate_root=candidate_root,
        dataset_yaml_path=dataset_yaml_path,
        model_factory=lambda _model_path: _FakeModel(
            {
                "train-positive-0.jpg": 1,
                "train-positive-1.jpg": 1,
                "val-positive-0.jpg": 1,
            }
        ),
    )

    assert result["trainingQualityGatePassed"] is True
    assert result["trainingQualityGatePrimaryBlocker"] is None
    assert result["validationPositiveLabelImageCount"] == 2
    assert result["validationEmptyLabelImageCount"] == 1
    assert result["validationInformative"] is True
    assert result["maxValidationPrecision"] == 0.47
    assert result["maxValidationRecall"] == 0.39
    assert result["maxValidationMap50"] == 0.45
    assert result["localPositiveSanityDetectedImageCount"] == 3


def test_run_training_quality_gate_fails_when_proposal_window_sanity_detects_nothing(tmp_path: Path) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v6"
    export_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v2" / "yolo_export"
    dataset_yaml_path = _write_dataset(
        export_root,
        train_positive=2,
        train_empty=0,
        val_positive=2,
        val_empty=1,
    )
    _write_proposal_window_alignment_report(
        export_root.parent,
        validation_positive_window_kind_counts={"direct_seed_tight": 2},
    )
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
            "resultsCsvPath": str(candidate_root / "results.csv"),
        },
    )
    (candidate_root / "weights" / "best.pt").parent.mkdir(parents=True, exist_ok=True)
    (candidate_root / "weights" / "best.pt").write_bytes(b"weights")
    _write_results_csv(
        candidate_root / "results.csv",
        metric_rows=[
            {
                "epoch": 1,
                "metrics/precision(B)": 0.52,
                "metrics/recall(B)": 0.41,
                "metrics/mAP50(B)": 0.48,
                "metrics/mAP50-95(B)": 0.22,
            }
        ],
    )

    result = training_quality_gate.run_training_quality_gate(
        candidate_root=candidate_root,
        dataset_yaml_path=dataset_yaml_path,
        model_factory=lambda _model_path: _FakeModel(
            {
                "train-positive-0.jpg": 1,
                "train-positive-1.jpg": 1,
            }
        ),
    )

    assert result["trainingQualityGatePassed"] is False
    assert result["trainingQualityGatePrimaryBlocker"] == "proposal_window_sanity_zero_detections"
    assert result["proposalWindowValidationImageCount"] == 3
    assert result["proposalWindowValidationPositiveImageCount"] == 2
    assert result["proposalWindowSanityDetectedImageCount"] == 0
    assert result["proposalWindowSanityDetectionRate"] == 0.0
    assert result["proposalWindowSanityWindowKindCounts"] == {"direct_seed_tight": 2}


def test_run_training_quality_gate_passes_with_proposal_window_sanity_signal(tmp_path: Path) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v6"
    export_root = tmp_path / "training_prep" / "touchline_proposal_signal_generation_fix_v2" / "yolo_export"
    dataset_yaml_path = _write_dataset(
        export_root,
        train_positive=2,
        train_empty=0,
        val_positive=2,
        val_empty=1,
    )
    _write_proposal_window_alignment_report(
        export_root.parent,
        validation_positive_window_kind_counts={"direct_seed_tight": 1, "player_ranked": 1},
    )
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCandidateName": "touchline_detector_candidate_v6",
            "bestWeightsPath": str(candidate_root / "weights" / "best.pt"),
            "resultsCsvPath": str(candidate_root / "results.csv"),
        },
    )
    (candidate_root / "weights" / "best.pt").parent.mkdir(parents=True, exist_ok=True)
    (candidate_root / "weights" / "best.pt").write_bytes(b"weights")
    _write_results_csv(
        candidate_root / "results.csv",
        metric_rows=[
            {
                "epoch": 1,
                "metrics/precision(B)": 0.58,
                "metrics/recall(B)": 0.47,
                "metrics/mAP50(B)": 0.54,
                "metrics/mAP50-95(B)": 0.24,
            }
        ],
    )

    result = training_quality_gate.run_training_quality_gate(
        candidate_root=candidate_root,
        dataset_yaml_path=dataset_yaml_path,
        model_factory=lambda _model_path: _FakeModel(
            {
                "train-positive-0.jpg": 1,
                "train-positive-1.jpg": 1,
                "val-positive-0.jpg": 1,
            }
        ),
    )

    assert result["trainingQualityGatePassed"] is True
    assert result["trainingQualityGatePrimaryBlocker"] is None
    assert result["proposalWindowValidationImageCount"] == 3
    assert result["proposalWindowValidationPositiveImageCount"] == 2
    assert result["proposalWindowSanityDetectedImageCount"] == 1
    assert result["proposalWindowSanityDetectionRate"] == 0.5
    assert result["proposalWindowSanityWindowKindCounts"] == {
        "direct_seed_tight": 1,
        "player_ranked": 1,
    }
