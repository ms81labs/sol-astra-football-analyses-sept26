from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_probe_precision_guardrail_audit as precision_audit


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bundle(
    storage_root: Path,
    *,
    raw_rows: list[dict[str, object]],
    positive_frames: list[int],
    negative_frames: list[int],
    frame_count: int = 100,
) -> Path:
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    pod_root = storage_root / "pod_cycles" / "touchline-detector-candidate-v7-probe-assist-baseline-20260429111111"
    _write_json(
        candidate_root / "v7_probe_threshold_contract_fix_v1" / "threshold_contract_summary.json",
        {
            "dominantBlockerClass": "v7_probe_accepted_recovered",
            "nextCorrectiveFamily": "v7_probe_precision_guardrail_audit",
            "rawProbeObservedBallFrames": len({int(row["Frame_ID"]) for row in raw_rows}),
            "acceptedFrames": len({int(row["Frame_ID"]) for row in raw_rows}),
            "proofSource": str(pod_root),
        },
    )
    _write_json(
        pod_root / "proof_summary.json",
        {
            "frameCount": frame_count,
            "rawProbeObservedBallFrames": len({int(row["Frame_ID"]) for row in raw_rows}),
            "probeObservedBallFrames": len({int(row["Frame_ID"]) for row in raw_rows}),
            "acceptedBallFrames": len({int(row["Frame_ID"]) for row in raw_rows}),
        },
    )
    _write_json(
        pod_root / "ball_truth_layers.json",
        {
            "probeObservedBall": {"rawRows": raw_rows, "filteredRows": raw_rows},
            "acceptedBall": {"rows": raw_rows, "summary": {}},
        },
    )
    _write_json(
        pod_root / "ball_pipeline_trace.json",
        {
            "auxiliaryBallModelProfile": "ball_probe_only_v1_low_conf_001",
            "probeDetectorProfile": "ball_probe_only_v1_low_conf_001",
        },
    )
    exported_examples = [
        {
            "frameIndex": frame,
            "positiveLabelWritten": True,
            "truthUse": "reviewed_positive_training_seed",
            "sourceClipId": "trimed-5min.mp4",
        }
        for frame in positive_frames
    ] + [
        {
            "frameIndex": frame,
            "positiveLabelWritten": False,
            "truthUse": "reviewed_negative_training_seed",
            "sourceClipId": "trimed-5min.mp4",
        }
        for frame in negative_frames
    ]
    _write_json(
        storage_root
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "touchline_detector_candidate_v7_training_prep_v1"
        / "v7_training_manifest.json",
        {
            "positiveExamples": [
                {
                    "exampleId": f"positive-{frame}",
                    "frameIndex": frame,
                    "bbox": {"x1": 380.0, "y1": 680.0, "x2": 398.0, "y2": 698.0},
                    "truthUse": "reviewed_positive_training_seed",
                }
                for frame in positive_frames
            ],
            "negativeExamples": [
                {
                    "exampleId": f"negative-{frame}",
                    "frameIndex": frame,
                    "bbox": None,
                    "truthUse": "negative_only_refuted_seed",
                }
                for frame in negative_frames
            ],
        },
    )
    _write_json(
        storage_root
        / "training_prep"
        / "touchline_detector_candidate_v7_training_v1"
        / "yolo_export"
        / "split_manifest.json",
        {"exportedExamples": exported_examples},
    )
    return candidate_root


def _row(frame: int, conf: float, *, area: float = 5000.0) -> dict[str, object]:
    return {
        "Frame_ID": frame,
        "Timestamp": frame / 25.0,
        "Entity_Type": "ball",
        "Conf": conf,
        "Source_X1": 0.0,
        "Source_Y1": 0.0,
        "Source_X2": area ** 0.5,
        "Source_Y2": area ** 0.5,
    }


def test_precision_audit_selects_training_quality_refresh_for_low_conf_flood(tmp_path: Path) -> None:
    positive_frames = [10, 20]
    negative_frames = [30, 40, 50, 60]
    raw_rows = [_row(frame, 0.012, area=46000.0) for frame in positive_frames + negative_frames + [70, 80]]
    candidate_root = _write_bundle(
        tmp_path,
        raw_rows=raw_rows,
        positive_frames=positive_frames,
        negative_frames=negative_frames,
        frame_count=8,
    )

    payload = precision_audit.run_v7_probe_precision_guardrail_audit(storage_root=tmp_path)

    output_root = candidate_root / "v7_probe_precision_guardrail_audit_v1"
    summary = _load_json(output_root / "precision_guardrail_summary.json")
    geometry = _load_json(output_root / "v7_probe_geometry_guardrail_audit.json")
    localization = _load_json(output_root / "positive_localization_audit.json")
    outcome = _load_json(output_root / "batch_outcome_analysis.json")
    assert payload["dominantBlockerClass"] == "v7_low_conf_top_left_artifact_flood"
    assert summary["nextCorrectiveFamily"] == "v7_training_data_quality_refresh"
    assert summary["negativeFrameHitRate"] == 1.0
    assert summary["positiveLocalizationHitRate"] == 0.0
    assert summary["topLeftBoxShare"] == 1.0
    assert summary["nearConstantConfidenceShare"] == 1.0
    assert geometry["medianSourceBoxArea"] > 40000
    assert localization["positiveFrameHitRate"] == 1.0
    assert localization["positiveLocalizationHitRate"] == 0.0
    assert outcome["runtimeDefaultMutationAllowed"] is False
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_precision_audit_selects_threshold_contract_when_confidence_separates_positives(tmp_path: Path) -> None:
    positive_frames = [10, 20, 25]
    negative_frames = [30, 40, 50]
    raw_rows = [
        *[_row(frame, 0.035, area=800.0) for frame in positive_frames],
        *[_row(frame, 0.011, area=800.0) for frame in negative_frames],
    ]
    _write_bundle(tmp_path, raw_rows=raw_rows, positive_frames=positive_frames, negative_frames=negative_frames)

    payload = precision_audit.run_v7_probe_precision_guardrail_audit(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_threshold_precision_contract_available"
    assert payload["nextCorrectiveFamily"] == "v7_probe_threshold_sweep_contract"
    assert payload["recommendedConfidenceThreshold"] >= 0.015


def test_precision_audit_selects_geometry_contract_when_box_area_separates_negatives(tmp_path: Path) -> None:
    positive_frames = [10, 20]
    negative_frames = [30, 40, 50]
    raw_rows = [
        *[_row(frame, 0.012, area=900.0) for frame in positive_frames],
        *[_row(frame, 0.012, area=50000.0) for frame in negative_frames],
    ]
    _write_bundle(tmp_path, raw_rows=raw_rows, positive_frames=positive_frames, negative_frames=negative_frames)

    payload = precision_audit.run_v7_probe_precision_guardrail_audit(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_bbox_geometry_precision_contract_available"
    assert payload["nextCorrectiveFamily"] == "v7_probe_bbox_geometry_contract_fix"
