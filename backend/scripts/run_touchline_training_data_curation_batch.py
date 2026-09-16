from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT, canonicalize_benchmark_video_path  # noqa: E402
from backend.app.schemas import CreateIssueRequest  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
from backend.app.trust_crops import compute_trust_crops  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_training_data_curation_foundation"
DEFAULT_SUITE_DIRNAME = "frozen-viable-baseline-slice-suite"
DEFAULT_MAX_TRUST_CROPS_PER_MATCH = 5
DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT = 3
SEEDED_ISSUE_NOTE_PREFIX = f"[training-prep:{DEFAULT_BATCH_NAME}]"
NEXT_LEVER_PREPARE = "prepare_touchline_training_data"
NEXT_LEVER_TRAIN = "train_touchline_detector_candidate"


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object payload in {path}")
    return payload


def _load_optional_analysis_artifact(storage: Storage, match_id: str, analysis_type: str) -> dict[str, object]:
    try:
        payload = storage.load_analysis_artifact(match_id, analysis_type)
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _storage_artifact_paths(storage_root: Path) -> dict[str, Path]:
    suite_dir = Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_DIRNAME
    return {
        "activeLaneSnapshotPath": suite_dir / "active_lane_snapshot.json",
        "failureAuditPath": suite_dir / "primary_source_robustness_failure_audit.json",
        "sliceProjectionPath": suite_dir / "primary_source_robustness_slice_projection.json",
        "detectorBreadthMatrixPath": suite_dir / "detector_breadth_matrix.json",
    }


def select_representative_projection_rows(
    *,
    rows: list[dict[str, object]],
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    failing_rows = [
        dict(row) for row in rows if str(row.get("sourceClipId") or "") == failing_source_clip_id
    ]
    comparison_rows = [
        dict(row) for row in rows if str(row.get("sourceClipId") or "") == comparison_source_clip_id
    ]
    if not failing_rows:
        raise ValueError(f"No baseline rows found for failing source {failing_source_clip_id}")
    if not comparison_rows:
        raise ValueError(f"No baseline rows found for comparison source {comparison_source_clip_id}")

    failing_row = min(
        failing_rows,
        key=lambda row: (
            bool(row.get("ballTrackViable")),
            -_safe_float(row.get("ballTrackEdgeFrameShare"), 0.0),
            _safe_float(row.get("acceptedBallRatio"), 0.0),
            _safe_float(row.get("controlledPossessionRatio"), 0.0),
            str(row.get("matchId") or ""),
        ),
    )
    comparison_row = min(
        comparison_rows,
        key=lambda row: (
            not bool(row.get("ballTrackViable")),
            _safe_float(row.get("ballTrackEdgeFrameShare"), 0.0),
            -_safe_float(row.get("acceptedBallRatio"), 0.0),
            -_safe_float(row.get("controlledPossessionRatio"), 0.0),
            str(row.get("matchId") or ""),
        ),
    )
    return failing_row, comparison_row


def _truth_gate_reason_lookup(
    failure_audit_payload: dict[str, object],
    *,
    config_name: str,
) -> dict[str, list[str]]:
    configs = failure_audit_payload.get("configs")
    if not isinstance(configs, dict):
        return {}
    config_payload = configs.get(config_name)
    if not isinstance(config_payload, dict):
        return {}
    diagnostics = config_payload.get("sliceDiagnostics")
    if not isinstance(diagnostics, list):
        return {}
    lookup: dict[str, list[str]] = {}
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        match_id = str(item.get("matchId") or "")
        if not match_id:
            continue
        reasons = item.get("truthGateReasons")
        lookup[match_id] = list(reasons) if isinstance(reasons, list) else []
    return lookup


def _resolve_video_path(storage: Storage, match_id: str, source_clip_id: str) -> Path:
    candidates: list[Path] = []
    try:
        trace = storage.load_analysis_artifact(match_id, "ball_pipeline_trace")
    except FileNotFoundError:
        trace = {}
    if isinstance(trace, dict):
        candidate = canonicalize_benchmark_video_path(str(trace.get("videoPath") or ""))
        if candidate:
            candidates.append(Path(candidate))
    try:
        candidates.append(storage.get_match_input_path(match_id))
    except KeyError:
        pass
    candidates.append(REPO_ROOT / "videos" / source_clip_id)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve a video path for match {match_id}")


def _proof_summary_fallback(
    *,
    ball_truth_layers: dict[str, object],
    active_lane_snapshot: dict[str, object],
    detector_breadth_matrix: dict[str, object],
) -> dict[str, object]:
    direct_observation_breakdown = (
        ball_truth_layers.get("directObservationBreakdown")
        if isinstance(ball_truth_layers.get("directObservationBreakdown"), dict)
        else {}
    )
    detector_model_path = (
        direct_observation_breakdown.get("frozenDetectorModelPath")
        or detector_breadth_matrix.get("screenWinningDetectorModelPath")
        or active_lane_snapshot.get("baselineFingerprint", {}).get("detectorModelPath")
        or "yolov10n.pt"
    )
    return {
        "detectorModelPath": detector_model_path,
        "detectorModelName": Path(str(detector_model_path)).name,
    }


def _extract_frame_image(*, video_path: Path, frame_id: int, output_path: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        success, frame = capture.read()
        if not success or frame is None:
            raise RuntimeError(f"Could not read frame {frame_id} from {video_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"Could not write extracted frame to {output_path}")
        height, width = frame.shape[:2]
        return int(width), int(height)
    finally:
        capture.release()


def _row_bbox(row: dict[str, object]) -> tuple[float, float, float, float] | None:
    keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if not all(key in row for key in keys):
        return None
    x1 = _safe_float(row.get("Source_X1"), default=-1.0)
    y1 = _safe_float(row.get("Source_Y1"), default=-1.0)
    x2 = _safe_float(row.get("Source_X2"), default=-1.0)
    y2 = _safe_float(row.get("Source_Y2"), default=-1.0)
    if min(x1, y1, x2, y2) < 0:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _frame_id(row: dict[str, object]) -> int:
    return _safe_int(row.get("Frame_ID", row.get("frameId")), -1)


def _group_rows_by_frame(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        frame_id = _frame_id(row)
        if frame_id < 0:
            continue
        grouped.setdefault(frame_id, []).append(dict(row))
    return grouped


def _select_seed_row(
    *,
    frame_id: int,
    accepted_by_frame: dict[int, list[dict[str, object]]],
    probe_filtered_by_frame: dict[int, list[dict[str, object]]],
    probe_raw_by_frame: dict[int, list[dict[str, object]]],
) -> tuple[str, dict[str, object]] | None:
    for seed_source, grouped_rows in (
        ("accepted_ball", accepted_by_frame),
        ("probe_filtered", probe_filtered_by_frame),
        ("probe_raw", probe_raw_by_frame),
    ):
        for row in grouped_rows.get(frame_id, []):
            if _row_bbox(row) is not None:
                return seed_source, row
    return None


def _stable_curation_unit_id(*, batch_name: str, match_id: str, frame_start: int, frame_end: int) -> str:
    raw = f"{batch_name}:{match_id}:{frame_start}:{frame_end}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _yolo_label_line(row: dict[str, object], *, frame_width: int, frame_height: int) -> str:
    bbox = _row_bbox(row)
    if bbox is None:
        raise ValueError("Row is missing a saved source bbox")
    x1, y1, x2, y2 = bbox
    x_center = ((x1 + x2) / 2.0) / frame_width
    y_center = ((y1 + y2) / 2.0) / frame_height
    width = (x2 - x1) / frame_width
    height = (y2 - y1) / frame_height
    return f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def _write_dataset_yaml(export_root: Path) -> None:
    content = "\n".join(
        [
            f"path: {export_root}",
            "train: images/train",
            "val: images/val",
            "names:",
            "  0: ball",
            "",
        ]
    )
    (export_root / "dataset.yaml").write_text(content, encoding="utf-8")


def _issue_note(curation_unit: dict[str, object]) -> str:
    reasons = ",".join(curation_unit.get("trustCropReasons", []))
    return (
        f"{SEEDED_ISSUE_NOTE_PREFIX} unit={curation_unit['curationUnitId']} "
        f"source={curation_unit['sourceClipId']} "
        f"frames={curation_unit['frameStart']}-{curation_unit['frameEnd']} "
        f"score={curation_unit['trustCropScore']} "
        f"reasons={reasons} "
        f"labelStatus={curation_unit['labelStatus']}"
    )


def _seed_issues(
    storage: Storage,
    *,
    curation_units: list[dict[str, object]],
) -> dict[str, object]:
    removed_count = 0
    seeded_count = 0
    report_matches: dict[str, dict[str, object]] = {}
    match_ids = {str(unit["matchId"]) for unit in curation_units}
    for match_id in sorted(match_ids):
        existing = storage.list_issues(match_id)
        report_matches[match_id] = {
            "removedIssueIds": [],
            "seededIssueIds": [],
            "seededCurationUnitIds": [],
        }
        for issue in existing:
            if issue.note.startswith(SEEDED_ISSUE_NOTE_PREFIX):
                storage.delete_issue(match_id, issue.id)
                removed_count += 1
                report_matches[match_id]["removedIssueIds"].append(issue.id)

    for unit in curation_units:
        match_id = str(unit["matchId"])
        record = storage.create_issue(
            match_id,
            CreateIssueRequest(
                frameStart=_safe_int(unit["frameStart"]),
                frameEnd=_safe_int(unit["frameEnd"]),
                timestampStart=_safe_float(unit["timestampStart"]),
                timestampEnd=_safe_float(unit["timestampEnd"]),
                bucket="tracking_failure",
                processingBackend="unknown",
                evidenceTarget="trust_eval",
                note=_issue_note(unit),
            ),
        )
        seeded_count += 1
        report_matches[match_id]["seededIssueIds"].append(record.id)
        report_matches[match_id]["seededCurationUnitIds"].append(unit["curationUnitId"])

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": DEFAULT_BATCH_NAME,
        "seededIssueCount": seeded_count,
        "removedPriorSeededIssueCount": removed_count,
        "matches": report_matches,
    }


def _build_export_plan_for_unit(
    *,
    split_name: str,
    video_path: Path,
    frame_records: list[dict[str, object]],
    match_id: str,
    frame_start: int,
    accepted_by_frame: dict[int, list[dict[str, object]]],
    probe_filtered_by_frame: dict[int, list[dict[str, object]]],
    probe_raw_by_frame: dict[int, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], str]:
    examples: list[dict[str, object]] = []
    primary_seed_source = "hard_negative"
    negative_count = 0
    for frame_record in frame_records:
        frame_id = _safe_int(frame_record.get("frameId"), -1)
        if frame_id < 0:
            continue
        file_stem = f"{match_id}__{frame_start}__f{frame_id:04d}"
        selected = _select_seed_row(
            frame_id=frame_id,
            accepted_by_frame=accepted_by_frame,
            probe_filtered_by_frame=probe_filtered_by_frame,
            probe_raw_by_frame=probe_raw_by_frame,
        )
        if selected is None:
            if negative_count >= DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT:
                continue
            negative_count += 1
            examples.append(
                {
                    "split": split_name,
                    "fileStem": file_stem,
                    "frameId": frame_id,
                    "videoPath": str(video_path),
                    "seedSource": "hard_negative",
                    "labelLine": "",
                }
            )
            continue

        seed_source, row = selected
        if primary_seed_source == "hard_negative":
            primary_seed_source = seed_source
        examples.append(
            {
                "split": split_name,
                "fileStem": file_stem,
                "frameId": frame_id,
                "videoPath": str(video_path),
                "seedSource": seed_source,
                "row": row,
            }
        )
    return examples, primary_seed_source


def _write_yolo_export(
    *,
    export_root: Path,
    curation_units: list[dict[str, object]],
) -> dict[str, object]:
    images_root = export_root / "images"
    labels_root = export_root / "labels"
    for split_name in ("train", "val"):
        (images_root / split_name).mkdir(parents=True, exist_ok=True)
        (labels_root / split_name).mkdir(parents=True, exist_ok=True)

    positive_count = 0
    negative_count = 0
    exported_examples: list[dict[str, object]] = []
    for unit in curation_units:
        for example in unit.get("examples", []):
            split_name = str(example["split"])
            file_stem = str(example["fileStem"])
            output_image = images_root / split_name / f"{file_stem}.jpg"
            frame_width, frame_height = _extract_frame_image(
                video_path=Path(str(example["videoPath"])),
                frame_id=_safe_int(example["frameId"], 0),
                output_path=output_image,
            )
            output_label = labels_root / split_name / f"{file_stem}.txt"
            if example["seedSource"] == "hard_negative":
                output_label.write_text("", encoding="utf-8")
                negative_count += 1
            else:
                output_label.write_text(
                    _yolo_label_line(example["row"], frame_width=frame_width, frame_height=frame_height),
                    encoding="utf-8",
                )
                positive_count += 1
            exported_examples.append(
                {
                    "curationUnitId": unit["curationUnitId"],
                    "split": split_name,
                    "fileStem": file_stem,
                    "frameId": _safe_int(example["frameId"]),
                    "seedSource": example["seedSource"],
                    "imagePath": str(output_image),
                    "labelPath": str(output_label),
                }
            )
    _write_dataset_yaml(export_root)
    return {
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "exportedExamples": exported_examples,
        "yoloExportReady": positive_count > 0 and any(
            example["split"] == "val" for example in exported_examples
        ),
    }


def _build_split_manifest(curation_units: list[dict[str, object]]) -> dict[str, object]:
    splits: dict[str, dict[str, object]] = {
        "train": {"curationUnitIds": [], "sourceClipIds": set(), "positiveSeedExampleCount": 0, "negativeSeedExampleCount": 0},
        "val": {"curationUnitIds": [], "sourceClipIds": set(), "positiveSeedExampleCount": 0, "negativeSeedExampleCount": 0},
    }
    seen_units: set[tuple[str, str]] = set()
    leakage_detected = False
    for unit in curation_units:
        split_name = str(unit["split"])
        unit_key = (split_name, str(unit["curationUnitId"]))
        if unit_key in seen_units:
            leakage_detected = True
        seen_units.add(unit_key)
        split = splits[split_name]
        split["curationUnitIds"].append(unit["curationUnitId"])
        split["sourceClipIds"].add(str(unit["sourceClipId"]))
        split["positiveSeedExampleCount"] += _safe_int(unit["positiveSeedExampleCount"], 0)
        split["negativeSeedExampleCount"] += _safe_int(unit["negativeSeedExampleCount"], 0)

    normalized_splits: dict[str, dict[str, object]] = {}
    for split_name, split in splits.items():
        normalized_splits[split_name] = {
            "curationUnitIds": list(split["curationUnitIds"]),
            "sourceClipIds": sorted(split["sourceClipIds"]),
            "curationUnitCount": len(split["curationUnitIds"]),
            "positiveSeedExampleCount": _safe_int(split["positiveSeedExampleCount"]),
            "negativeSeedExampleCount": _safe_int(split["negativeSeedExampleCount"]),
        }
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": DEFAULT_BATCH_NAME,
        "policy": "source_clip_window_level_deterministic_split",
        "sourceAwareSplitLeakageDetected": leakage_detected,
        "heldOutSplitAssessment": (
            "limited_single_control_source"
            if len(normalized_splits["val"]["sourceClipIds"]) <= 1
            else "multi_source"
        ),
        "splits": normalized_splits,
    }


def run_touchline_training_data_curation_batch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    storage = Storage(storage_root)
    artifact_paths = _storage_artifact_paths(storage_root)
    active_lane_snapshot = _load_json(artifact_paths["activeLaneSnapshotPath"])
    failure_audit = _load_json(artifact_paths["failureAuditPath"])
    slice_projection = _load_json(artifact_paths["sliceProjectionPath"])
    detector_breadth_matrix = _load_json(artifact_paths["detectorBreadthMatrixPath"])

    failing_source_clip_id = str(active_lane_snapshot.get("failingSourceClipId") or "trimed-5min.mp4")
    comparison_source_clip_id = str(
        active_lane_snapshot.get("comparisonSourceClipId") or "trimed-football-2-1minute.mp4"
    )
    baseline_config_name = str(
        active_lane_snapshot.get("sourceRobustnessActiveConfigName") or "source_robustness_baseline_current"
    )
    baseline_rows = (
        slice_projection.get("configs", {}).get(baseline_config_name, {}).get("rows", [])
        if isinstance(slice_projection.get("configs"), dict)
        else []
    )
    if not isinstance(baseline_rows, list):
        raise ValueError("Baseline slice projection rows are unavailable")

    failing_row, control_row = select_representative_projection_rows(
        rows=[dict(row) for row in baseline_rows if isinstance(row, dict)],
        failing_source_clip_id=failing_source_clip_id,
        comparison_source_clip_id=comparison_source_clip_id,
    )
    truth_gate_lookup = _truth_gate_reason_lookup(failure_audit, config_name=baseline_config_name)

    representative_rows = [failing_row, control_row]
    curation_units: list[dict[str, object]] = []
    for representative_row in representative_rows:
        match_id = str(representative_row["matchId"])
        source_clip_id = str(representative_row["sourceClipId"])
        video_path = _resolve_video_path(storage, match_id, source_clip_id)
        frames = [frame.model_dump() for frame in storage.load_frames(match_id)]
        _summary, assignments, _formation, _shots = storage.load_analytics(match_id)
        trust_crops = compute_trust_crops(
            frames,
            [assignment.model_dump() for assignment in assignments],
            max_crops=DEFAULT_MAX_TRUST_CROPS_PER_MATCH,
        )
        ball_truth_layers = storage.load_analysis_artifact(match_id, "ball_truth_layers")
        accepted_rows = list((ball_truth_layers.get("acceptedBall") or {}).get("rows") or [])
        probe_observed_ball = ball_truth_layers.get("probeObservedBall") or {}
        probe_filtered_rows = list(probe_observed_ball.get("filteredRows") or [])
        probe_raw_rows = list(probe_observed_ball.get("rawRows") or [])
        proof_summary = _load_optional_analysis_artifact(storage, match_id, "proof_summary")
        if not proof_summary:
            proof_summary = _proof_summary_fallback(
                ball_truth_layers=ball_truth_layers,
                active_lane_snapshot=active_lane_snapshot,
                detector_breadth_matrix=detector_breadth_matrix,
            )
        trace_payload = _load_optional_analysis_artifact(storage, match_id, "ball_pipeline_trace")
        accepted_by_frame = _group_rows_by_frame([dict(row) for row in accepted_rows if isinstance(row, dict)])
        probe_filtered_by_frame = _group_rows_by_frame([dict(row) for row in probe_filtered_rows if isinstance(row, dict)])
        probe_raw_by_frame = _group_rows_by_frame([dict(row) for row in probe_raw_rows if isinstance(row, dict)])
        split_name = "train" if source_clip_id == failing_source_clip_id else "val"
        truth_gate_reasons = truth_gate_lookup.get(match_id) or list(representative_row.get("truthGateReasons", []))
        for crop in trust_crops[:DEFAULT_MAX_TRUST_CROPS_PER_MATCH]:
            frame_records = [
                frame
                for frame in frames
                if _safe_int(frame.get("frameId"), -1) >= crop.frameStart
                and _safe_int(frame.get("frameId"), -1) <= crop.frameEnd
            ]
            if not frame_records:
                continue
            curation_unit_id = _stable_curation_unit_id(
                batch_name=DEFAULT_BATCH_NAME,
                match_id=match_id,
                frame_start=crop.frameStart,
                frame_end=crop.frameEnd,
            )
            examples, primary_seed_source = _build_export_plan_for_unit(
                split_name=split_name,
                video_path=video_path,
                frame_records=frame_records,
                match_id=match_id,
                frame_start=crop.frameStart,
                accepted_by_frame=accepted_by_frame,
                probe_filtered_by_frame=probe_filtered_by_frame,
                probe_raw_by_frame=probe_raw_by_frame,
            )
            positive_count = sum(1 for example in examples if example["seedSource"] != "hard_negative")
            negative_count = sum(1 for example in examples if example["seedSource"] == "hard_negative")
            curation_units.append(
                {
                    "curationUnitId": curation_unit_id,
                    "batchName": DEFAULT_BATCH_NAME,
                    "sourceClipId": source_clip_id,
                    "matchId": match_id,
                    "frameStart": crop.frameStart,
                    "frameEnd": crop.frameEnd,
                    "timestampStart": crop.timestampStart,
                    "timestampEnd": crop.timestampEnd,
                    "trustCropScore": crop.score,
                    "trustCropReasons": list(crop.reasons),
                    "truthGateReasons": truth_gate_reasons,
                    "detectorConfigProvenance": {
                        "baselineConfigName": baseline_config_name,
                        "sourceRobustnessBestConfigName": active_lane_snapshot.get("sourceRobustnessBestConfigName"),
                        "sourceRobustnessRecommendedNextLever": active_lane_snapshot.get(
                            "sourceRobustnessRecommendedNextLever"
                        ),
                        "detectorModelPath": proof_summary.get("detectorModelPath"),
                        "screenWinningDetectorModelPath": detector_breadth_matrix.get("screenWinningDetectorModelPath"),
                    },
                    "artifactLineagePaths": {
                        "activeLaneSnapshotPath": str(artifact_paths["activeLaneSnapshotPath"]),
                        "failureAuditPath": str(artifact_paths["failureAuditPath"]),
                        "sliceProjectionPath": str(artifact_paths["sliceProjectionPath"]),
                        "detectorBreadthMatrixPath": str(artifact_paths["detectorBreadthMatrixPath"]),
                        "ballTruthLayersPath": str(storage._match_dir(match_id) / "ball_truth_layers.json"),
                        "proofSummaryPath": str(storage._match_dir(match_id) / "proof_summary.json"),
                        "ballPipelineTracePath": str(storage._match_dir(match_id) / "ball_pipeline_trace.json"),
                    },
                    "labelStatus": "seeded_review_required",
                    "seedSource": primary_seed_source,
                    "split": split_name,
                    "positiveSeedExampleCount": positive_count,
                    "negativeSeedExampleCount": negative_count,
                    "examples": examples,
                    "videoPath": str(video_path),
                    "detectorBreadthFalsified": bool(detector_breadth_matrix.get("detectorBreadthFalsified")),
                    "sourceRobustnessOutcome": active_lane_snapshot.get("sourceRobustnessOutcome"),
                    "sourceRobustnessRecommendedNextLever": active_lane_snapshot.get(
                        "sourceRobustnessRecommendedNextLever"
                    ),
                    "traceVideoPath": trace_payload.get("videoPath"),
                }
            )

    artifact_root = storage_root / "training_prep" / DEFAULT_BATCH_NAME
    artifact_root.mkdir(parents=True, exist_ok=True)
    yolo_export_root = artifact_root / "yolo_export"
    yolo_export_root.mkdir(parents=True, exist_ok=True)
    export_result = _write_yolo_export(export_root=yolo_export_root, curation_units=curation_units)
    split_manifest = _build_split_manifest(curation_units)
    issue_report = _seed_issues(storage, curation_units=curation_units)

    for unit in curation_units:
        unit.pop("examples", None)

    positive_count = _safe_int(export_result["positiveSeedExampleCount"])
    negative_count = _safe_int(export_result["negativeSeedExampleCount"])
    yolo_export_ready = bool(export_result["yoloExportReady"])
    leakage_detected = bool(split_manifest["sourceAwareSplitLeakageDetected"])
    ready_for_detector_training = yolo_export_ready and not leakage_detected and _safe_int(
        issue_report["seededIssueCount"]
    ) > 0
    primary_blocker = None if ready_for_detector_training else (
        "source_aware_split_leakage_detected" if leakage_detected else "insufficient_export_examples"
    )

    curation_manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "batchName": DEFAULT_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "representativeFailingMatchId": failing_row["matchId"],
        "representativeControlMatchId": control_row["matchId"],
        "curationUnitCount": len(curation_units),
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "yoloExportReady": yolo_export_ready,
        "readyForDetectorTraining": ready_for_detector_training,
        "trainingPrepPrimaryBlocker": primary_blocker,
        "curationUnits": curation_units,
        "yoloExportPath": str(yolo_export_root),
        "nextRecommendedNextLever": NEXT_LEVER_TRAIN if ready_for_detector_training else NEXT_LEVER_PREPARE,
    }
    split_manifest.update(
        {
            "positiveSeedExampleCount": positive_count,
            "negativeSeedExampleCount": negative_count,
            "readyForDetectorTraining": ready_for_detector_training,
            "trainingPrepPrimaryBlocker": primary_blocker,
        }
    )

    (artifact_root / "curation_manifest.json").write_text(json.dumps(curation_manifest, indent=2), encoding="utf-8")
    (artifact_root / "split_manifest.json").write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")
    (artifact_root / "seeded_issue_report.json").write_text(json.dumps(issue_report, indent=2), encoding="utf-8")

    return {
        "batchName": DEFAULT_BATCH_NAME,
        "artifactRoot": str(artifact_root),
        "representativeFailingMatchId": str(failing_row["matchId"]),
        "representativeControlMatchId": str(control_row["matchId"]),
        "curationUnitCount": len(curation_units),
        "curationUnitIds": [str(unit["curationUnitId"]) for unit in curation_units],
        "seededIssueCount": _safe_int(issue_report["seededIssueCount"]),
        "removedPriorSeededIssueCount": _safe_int(issue_report["removedPriorSeededIssueCount"]),
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "sourceAwareSplitLeakageDetected": leakage_detected,
        "yoloExportReady": yolo_export_ready,
        "readyForDetectorTraining": ready_for_detector_training,
        "trainingPrepPrimaryBlocker": primary_blocker,
        "nextRecommendedNextLever": NEXT_LEVER_TRAIN if ready_for_detector_training else NEXT_LEVER_PREPARE,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the touchline training data curation foundation batch.")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    args = parser.parse_args()
    result = run_touchline_training_data_curation_batch(storage_root=Path(args.storage_root))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
