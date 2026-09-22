"""Historical proposal recipe, retired with its RunPod execution path."""

from __future__ import annotations


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import shlex
import tempfile

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.run_guerilla as run_guerilla  # noqa: E402
import backend.scripts.run_touchline_detector_candidate_proposal_signal_generation_fix as proposal_signal_fix_v1  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402
import backend.train_custom as train_custom  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_proposal_signal_generation_fix_v2"
DEFAULT_TRAINING_BATCH_NAME = "touchline_detector_candidate_v5_proposal_signal_generation_fix_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v6"
DEFAULT_PREVIOUS_BATCH_NAME = "touchline_model_data_quality_fix_v1"
DEFAULT_VALIDATION_REMEDIATION_BATCH_NAME = "touchline_validation_gate_remediation_v1"
DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME = "touchline_detector_candidate_v5"
DEFAULT_FAILURE_ANALYSIS_BATCH_NAME = "failure_analysis_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_COMPARISON_SOURCE_CLIP_ID = "trimed-football-2-1minute.mp4"
DEFAULT_BASELINE_CONTROL_BUNDLE_NAME = "yolov10n-pt-baseline-full-detector-baseline-control-20260422224502"
DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_EPOCHS = 12
DEFAULT_BATCH_SIZE = 8
DEFAULT_DEVICE = "0"
DEFAULT_WORKERS = 4
DEFAULT_SEED = 42
DEFAULT_EXECUTION_MODE = "remote_gpu"
DEFAULT_WINDOW_FAMILY = "proposal_windows_075"
DEFAULT_FRAME_INTERVAL = 5
NEGATIVE_CAP_MULTIPLIER = 2
MAX_NEGATIVE_NEAREST_FRAME_GAP = 40
NEXT_LEVER_EVALUATE = "evaluate_touchline_detector_candidate"
DETECTOR_PROFILE = "ball_probe_only_v1"
PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}






def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    return proposal_signal_fix_v1._safe_int(value, default)


def _safe_float(value: object, default: float = 0.0) -> float:
    return proposal_signal_fix_v1._safe_float(value, default)


def _json_safe_metrics(metrics: object) -> dict[str, object]:
    return proposal_signal_fix_v1._json_safe_metrics(metrics)


def _paths(storage_root: Path) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    previous_root = storage_root / "training_prep" / DEFAULT_PREVIOUS_BATCH_NAME
    remediation_root = storage_root / "training_prep" / DEFAULT_VALIDATION_REMEDIATION_BATCH_NAME
    failure_root = (
        storage_root
        / "trained_detector_candidates"
        / DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME
        / DEFAULT_FAILURE_ANALYSIS_BATCH_NAME
    )
    baseline_root = storage_root / "pod_cycles" / DEFAULT_BASELINE_CONTROL_BUNDLE_NAME
    artifact_root = storage_root / "training_prep" / DEFAULT_BATCH_NAME
    candidate_root = storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
    return {
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "failureAnalysisSummaryPath": failure_root / "failure_analysis_summary.json",
        "frameLevelProbeDeltaPath": failure_root / "frame_level_probe_delta.json",
        "previousManifestPath": previous_root / "data_quality_fix_manifest.json",
        "previousOverlayPath": previous_root / "reviewed_label_overlay.json",
        "previousBatchOutcomePath": previous_root / "batch_outcome_analysis.json",
        "validationGateManifestPath": remediation_root / "validation_gate_remediation_manifest.json",
        "validationSplitManifestPath": remediation_root / "split_manifest.json",
        "baselineBallTruthLayersPath": baseline_root / "ball_truth_layers.json",
        "artifactRoot": artifact_root,
        "manifestPath": artifact_root / "proposal_signal_fix_manifest.json",
        "splitManifestPath": artifact_root / "split_manifest.json",
        "alignmentReportPath": artifact_root / "proposal_window_alignment_report.json",
        "batchOutcomeJsonPath": artifact_root / "batch_outcome_analysis.json",
        "batchOutcomeMarkdownPath": artifact_root / "batch_outcome_analysis.md",
        "exportRoot": artifact_root / "yolo_export",
        "candidateRoot": candidate_root,
        "trainingConfigPath": candidate_root / "training_config.json",
        "trainingSummaryPath": candidate_root / "training_run_summary.json",
        "evaluationContractPath": candidate_root / "evaluation_contract.json",
        "candidateBatchOutcomeJsonPath": candidate_root / "batch_outcome_analysis.json",
        "candidateBatchOutcomeMarkdownPath": candidate_root / "batch_outcome_analysis.md",
        "remoteTrainingResultPath": candidate_root / "remote_training_result.json",
    }


def _requested_gpu_id() -> str | None:
    env_gpu_id = os.environ.get("RUNPOD_GPU_ID", "").strip()
    if env_gpu_id:
        return env_gpu_id
    loader = getattr(runpod_session, "_load_saved_runpod_gpu_id", None)
    if callable(loader):
        saved_gpu_id = str(loader()).strip()
        if saved_gpu_id:
            return saved_gpu_id
    return None


def _should_retry_without_requested_gpu(error_message: str, requested_gpu_id: str | None) -> bool:
    requested = str(requested_gpu_id or "").strip()
    if not requested:
        return False
    normalized = error_message.lower()
    return (
        f"requested gpu_id {requested!r}".lower() in normalized
        or f"requested gpu_id '{requested}'" in normalized
    ) and (
        "no longer any instances available" in normalized
        or "unable to create a runpod pod with requested gpu_id" in normalized
    )


def _create_remote_training_session(
    *,
    requested_gpu_id: str | None,
) -> tuple[dict[str, object], str | None]:
    try:
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=requested_gpu_id,
        )
        return session, None
    except Exception as error:
        error_message = str(error)
        if not _should_retry_without_requested_gpu(error_message, requested_gpu_id):
            raise
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=None,
        )
        return session, error_message


def _video_frame_shape(video_path: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        success, frame = capture.read()
        if not success or frame is None:
            raise RuntimeError(f"Could not read first frame from {video_path}")
        height, width = frame.shape[:2]
        return int(height), int(width)
    finally:
        capture.release()


def _extract_crop_image(
    *,
    video_path: Path,
    frame_id: int,
    crop_window: tuple[int, int, int, int],
    output_path: Path,
) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_id))
        success, frame = capture.read()
        if not success or frame is None:
            raise RuntimeError(f"Could not read frame {frame_id} from {video_path}")
        left, top, right, bottom = crop_window
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            raise RuntimeError(f"Empty crop for frame {frame_id} from {video_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), crop):
            raise RuntimeError(f"Could not write crop to {output_path}")
        height, width = crop.shape[:2]
        return int(width), int(height)
    finally:
        capture.release()


def _write_dataset_yaml(export_root: Path) -> None:
    dataset_yaml = "\n".join(
        [
            f"path: {export_root}",
            "train: images/train",
            "val: images/val",
            "names:",
            "  0: ball",
            "",
        ]
    )
    (export_root / "dataset.yaml").write_text(dataset_yaml, encoding="utf-8")


def _bbox_from_review_item(review_item: dict[str, object]) -> dict[str, float] | None:
    return proposal_signal_fix_v1._bbox_from_review_item(review_item)


def _bbox_center(bbox: dict[str, float]) -> tuple[float, float]:
    return proposal_signal_fix_v1._bbox_center(bbox)


def _bbox_area(bbox: dict[str, float]) -> float:
    return proposal_signal_fix_v1._bbox_area(bbox)


def _normalize_window(window: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return proposal_signal_fix_v1._normalize_window(window)


def _bbox_overlaps_window(bbox: dict[str, float], crop_window: tuple[int, int, int, int]) -> bool:
    return proposal_signal_fix_v1._bbox_overlaps_window(bbox, crop_window)


def _crop_label_line(
    *,
    bbox: dict[str, float],
    crop_window: tuple[int, int, int, int],
) -> tuple[str, float]:
    return proposal_signal_fix_v1._crop_label_line(bbox=bbox, crop_window=crop_window)


def _load_player_rows_by_frame(storage: Storage, match_id: str) -> dict[int, list[dict[str, object]]]:
    return proposal_signal_fix_v1._load_player_rows_by_frame(storage, match_id)


def _row_source_bbox(row: dict[str, object]) -> dict[str, float] | None:
    source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if not all(key in row for key in source_keys):
        return None
    x1 = _safe_float(row.get("Source_X1"), -1.0)
    y1 = _safe_float(row.get("Source_Y1"), -1.0)
    x2 = _safe_float(row.get("Source_X2"), -1.0)
    y2 = _safe_float(row.get("Source_Y2"), -1.0)
    if min(x1, y1, x2, y2) < 0 or x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _row_source_center(row: dict[str, object]) -> tuple[float, float] | None:
    bbox = _row_source_bbox(row)
    if bbox is None:
        return None
    return _bbox_center(bbox)


def _load_truth_layer_rows(
    *,
    ball_truth_layers: dict[str, object],
    layer_name: str,
    nested_key: str,
) -> list[dict[str, object]]:
    payload = ball_truth_layers.get(layer_name)
    if isinstance(payload, dict):
        rows = payload.get(nested_key) or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _best_rows_by_frame(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    best: dict[int, dict[str, object]] = {}
    for row in rows:
        frame_id = _safe_int(row.get("Frame_ID", row.get("frameId")), -1)
        if frame_id < 0:
            continue
        previous = best.get(frame_id)
        if previous is None or _safe_float(row.get("Conf"), 0.0) >= _safe_float(previous.get("Conf"), 0.0):
            best[frame_id] = dict(row)
    return best


def _unit_video_path(unit: dict[str, object]) -> Path | None:
    examples = [dict(example) for example in list(unit.get("examples") or []) if isinstance(example, dict)]
    for example in examples:
        video_path = Path(str(example.get("videoPath") or ""))
        if str(video_path):
            return video_path
    return None


def _build_unit_split_overrides(
    *,
    current_manifest: dict[str, object],
    validation_gate_manifest: dict[str, object],
) -> dict[str, str]:
    selected_val_positive_unit_id = str(validation_gate_manifest.get("selectedValidationPositiveCurationUnitId") or "")
    overrides: dict[str, str] = {}
    for unit in list(current_manifest.get("curationUnits") or []):
        if not isinstance(unit, dict):
            continue
        unit_id = str(unit.get("curationUnitId") or "")
        split = str(unit.get("split") or "train")
        overrides[unit_id] = split
    if selected_val_positive_unit_id:
        overrides[selected_val_positive_unit_id] = "val"
    return overrides


def _find_curation_unit_for_frame(
    *,
    curation_units: list[dict[str, object]],
    match_id: str,
    frame_id: int,
    source_clip_id: str,
) -> dict[str, object] | None:
    for unit in curation_units:
        if str(unit.get("matchId") or "") != match_id:
            continue
        if str(unit.get("sourceClipId") or "") != source_clip_id:
            continue
        if _safe_int(unit.get("frameStart"), -1) <= frame_id <= _safe_int(unit.get("frameEnd"), -1):
            return unit
    return None


def _build_runtime_proposal_specs_for_frame(
    *,
    frame_shape: tuple[int, int],
    player_rows_for_frame: list[dict[str, object]],
    seed_center: tuple[float, float],
    source_clip_id: str,
) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for row in player_rows_for_frame:
        copied = dict(row)
        copied["Frame_ID"] = 0
        normalized_rows.append(copied)
    crop_windows_by_frame, _diagnostics = run_guerilla._build_player_proposal_crop_windows_by_frame(
        frame_shape,
        frame_interval=1,
        player_rows=normalized_rows,
        observed_source_anchors={0: (float(seed_center[0]), float(seed_center[1]))},
        frame_count=1,
        max_proposals_per_frame=3,
        proposal_crop_width_ratio=0.35,
        proposal_crop_height_ratio=0.35,
        proposal_crop_padding_px=int(run_guerilla.PLAYER_PROPOSAL_CROP_PADDING_PX),
        source_clip_id=source_clip_id,
        edge_share_repair_profile=None,
    )
    specs = []
    for spec in crop_windows_by_frame.get(0, []):
        window = spec.get("window")
        if not isinstance(window, (list, tuple)) or len(window) != 4:
            continue
        specs.append(
            {
                "cropWindowKind": str(spec.get("proposalWindowKind") or "unknown"),
                "cropWindow": tuple(int(round(float(value))) for value in window),
            }
        )
    return specs


def _seed_center_for_negative_frame(
    *,
    frame_id: int,
    unit: dict[str, object],
    baseline_raw_rows_by_frame: dict[int, dict[str, object]],
    trusted_positive_centers_by_frame: dict[int, tuple[float, float]],
    player_rows_for_frame: list[dict[str, object]],
) -> tuple[float, float] | None:
    direct_raw = baseline_raw_rows_by_frame.get(frame_id)
    if isinstance(direct_raw, dict):
        direct_center = _row_source_center(direct_raw)
        if direct_center is not None:
            return direct_center

    frame_start = _safe_int(unit.get("frameStart"), 0)
    frame_end = _safe_int(unit.get("frameEnd"), 0)
    nearest_candidates: list[tuple[int, tuple[float, float]]] = []
    for candidate_frame_id, row in baseline_raw_rows_by_frame.items():
        if candidate_frame_id < frame_start or candidate_frame_id > frame_end:
            continue
        center = _row_source_center(row)
        if center is None:
            continue
        nearest_candidates.append((abs(candidate_frame_id - frame_id), center))
    if nearest_candidates:
        nearest_distance, nearest_center = min(nearest_candidates, key=lambda item: item[0])
        if nearest_distance <= MAX_NEGATIVE_NEAREST_FRAME_GAP:
            return nearest_center

    positive_candidates: list[tuple[int, tuple[float, float]]] = []
    for candidate_frame_id, center in trusted_positive_centers_by_frame.items():
        if candidate_frame_id < frame_start or candidate_frame_id > frame_end:
            continue
        positive_candidates.append((abs(candidate_frame_id - frame_id), center))
    if positive_candidates:
        nearest_distance, nearest_center = min(positive_candidates, key=lambda item: item[0])
        if nearest_distance <= MAX_NEGATIVE_NEAREST_FRAME_GAP:
            return nearest_center

    for player_row in player_rows_for_frame:
        center = _row_source_center(player_row)
        if center is not None:
            return center
    return None


def _build_export_examples(
    *,
    current_manifest: dict[str, object],
    current_overlay: dict[str, object],
    validation_gate_manifest: dict[str, object],
    ball_truth_layers: dict[str, object],
    frame_level_probe_delta: dict[str, object],
    storage: Storage,
) -> tuple[list[dict[str, object]], dict[str, object], float, float]:
    curation_units = [dict(unit) for unit in list(current_manifest.get("curationUnits") or []) if isinstance(unit, dict)]
    unit_by_id = {str(unit.get("curationUnitId") or ""): dict(unit) for unit in curation_units}
    split_overrides = _build_unit_split_overrides(
        current_manifest=current_manifest,
        validation_gate_manifest=validation_gate_manifest,
    )

    player_rows_by_match: dict[str, dict[int, list[dict[str, object]]]] = {}
    frame_shape_by_video: dict[Path, tuple[int, int]] = {}

    def _match_player_rows(match_id: str) -> dict[int, list[dict[str, object]]]:
        if match_id not in player_rows_by_match:
            player_rows_by_match[match_id] = _load_player_rows_by_frame(storage, match_id)
        return player_rows_by_match[match_id]

    def _shape(video_path: Path) -> tuple[int, int]:
        if video_path not in frame_shape_by_video:
            frame_shape_by_video[video_path] = _video_frame_shape(video_path)
        return frame_shape_by_video[video_path]

    trusted_positive_records: list[dict[str, object]] = []
    trusted_positive_frames: set[tuple[str, int]] = set()
    all_positive_bboxes_by_frame: dict[tuple[str, int], list[dict[str, float]]] = defaultdict(list)
    trusted_positive_centers_by_unit: dict[str, dict[int, tuple[float, float]]] = defaultdict(dict)

    for review_item in list(current_overlay.get("reviewItems") or []):
        if not isinstance(review_item, dict):
            continue
        bbox = _bbox_from_review_item(review_item)
        if bbox is None:
            continue
        decision = str(review_item.get("decision") or "")
        if decision not in {"accept_seed", "adjust_bbox"}:
            continue
        curation_unit_id = str(review_item.get("curationUnitId") or "")
        unit = unit_by_id.get(curation_unit_id)
        if unit is None:
            continue
        frame_id = _safe_int(review_item.get("frameIndex"), -1)
        if frame_id < 0:
            continue
        match_id = str(review_item.get("matchId") or unit.get("matchId") or "")
        video_path = _unit_video_path(unit)
        if video_path is None:
            continue
        split_name = split_overrides.get(curation_unit_id) or str(review_item.get("split") or unit.get("split") or "train")
        frame_key = (match_id, frame_id)
        trusted_positive_frames.add(frame_key)
        all_positive_bboxes_by_frame[frame_key].append(bbox)
        trusted_positive_centers_by_unit[curation_unit_id][frame_id] = _bbox_center(bbox)
        trusted_positive_records.append(
            {
                "curationUnitId": curation_unit_id,
                "matchId": match_id,
                "sourceClipId": str(unit.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID),
                "split": split_name,
                "frameId": frame_id,
                "videoPath": str(video_path),
                "fileStem": str(review_item.get("fileStem") or review_item.get("reviewItemId") or f"{curation_unit_id}__f{frame_id:04d}"),
                "bbox": bbox,
                "sourceLabelStatus": "reviewed_positive",
                "seedSource": review_item.get("seedSource"),
            }
        )

    baseline_accepted_rows = _load_truth_layer_rows(
        ball_truth_layers=ball_truth_layers,
        layer_name="acceptedBall",
        nested_key="rows",
    )
    for row in baseline_accepted_rows:
        frame_id = _safe_int(row.get("Frame_ID"), -1)
        if frame_id < 0:
            continue
        unit = _find_curation_unit_for_frame(
            curation_units=curation_units,
            match_id=str(curation_units[0].get("matchId") if curation_units else ""),
            frame_id=frame_id,
            source_clip_id=DEFAULT_FAILING_SOURCE_CLIP_ID,
        )
        if unit is None:
            continue
        match_id = str(unit.get("matchId") or "")
        frame_key = (match_id, frame_id)
        if frame_key in trusted_positive_frames:
            continue
        bbox = _row_source_bbox(row)
        video_path = _unit_video_path(unit)
        if bbox is None or video_path is None:
            continue
        curation_unit_id = str(unit.get("curationUnitId") or "")
        split_name = split_overrides.get(curation_unit_id) or str(unit.get("split") or "train")
        trusted_positive_frames.add(frame_key)
        all_positive_bboxes_by_frame[frame_key].append(bbox)
        trusted_positive_centers_by_unit[curation_unit_id][frame_id] = _bbox_center(bbox)
        trusted_positive_records.append(
            {
                "curationUnitId": curation_unit_id,
                "matchId": match_id,
                "sourceClipId": str(unit.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID),
                "split": split_name,
                "frameId": frame_id,
                "videoPath": str(video_path),
                "fileStem": f"{curation_unit_id}__f{frame_id:04d}__baseline_control_accepted_ball",
                "bbox": bbox,
                "sourceLabelStatus": "auto_accepted_pseudo_label",
                "seedSource": "baseline_control_accepted_ball",
            }
        )

    export_examples: list[dict[str, object]] = []
    negative_candidates: list[dict[str, object]] = []
    positive_keys: set[tuple[str, int, tuple[int, int, int, int]]] = set()
    negative_keys: set[tuple[str, int, tuple[int, int, int, int]]] = set()
    full_frame_relative_areas: list[float] = []
    proposal_relative_areas: list[float] = []
    positive_window_kind_counts: Counter[str] = Counter()
    negative_window_kind_counts: Counter[str] = Counter()
    negative_priority_counts: Counter[str] = Counter()

    def _append_positive_example(
        *,
        record: dict[str, object],
        crop_window_kind: str,
        crop_window: tuple[int, int, int, int],
    ) -> None:
        key = (str(record["matchId"]), _safe_int(record["frameId"]), tuple(crop_window))
        if key in positive_keys:
            return
        positive_keys.add(key)
        frame_shape = _shape(Path(str(record["videoPath"])))
        full_frame_relative_areas.append(_bbox_area(record["bbox"]) / max(float(frame_shape[0] * frame_shape[1]), 1.0))
        label_line, area_share = _crop_label_line(
            bbox=dict(record["bbox"]),
            crop_window=crop_window,
        )
        proposal_relative_areas.append(area_share)
        positive_window_kind_counts[crop_window_kind] += 1
        export_examples.append(
            {
                "curationUnitId": record["curationUnitId"],
                "matchId": record["matchId"],
                "split": record["split"],
                "frameId": record["frameId"],
                "videoPath": record["videoPath"],
                "fileStem": f"{record['fileStem']}__{crop_window_kind}",
                "cropWindowKind": crop_window_kind,
                "cropWindow": tuple(crop_window),
                "labelLine": label_line,
                "sourceLabelStatus": record["sourceLabelStatus"],
                "seedSource": record.get("seedSource"),
                "windowFamily": DEFAULT_WINDOW_FAMILY,
            }
        )

    def _append_negative_candidate(
        *,
        priority_label: str,
        priority_rank: int,
        curation_unit_id: str,
        match_id: str,
        split_name: str,
        frame_id: int,
        video_path: str,
        crop_window_kind: str,
        crop_window: tuple[int, int, int, int],
        seed_source: str,
        source_label_status: str,
        file_stem_prefix: str,
    ) -> None:
        key = (match_id, frame_id, tuple(crop_window))
        if key in positive_keys or key in negative_keys:
            return
        negative_keys.add(key)
        negative_priority_counts[priority_label] += 1
        negative_candidates.append(
            {
                "priorityRank": priority_rank,
                "priorityLabel": priority_label,
                "curationUnitId": curation_unit_id,
                "matchId": match_id,
                "split": split_name,
                "frameId": frame_id,
                "videoPath": video_path,
                "fileStem": f"{file_stem_prefix}__{crop_window_kind}__negative",
                "cropWindowKind": crop_window_kind,
                "cropWindow": tuple(crop_window),
                "labelLine": "",
                "sourceLabelStatus": source_label_status,
                "seedSource": seed_source,
                "windowFamily": DEFAULT_WINDOW_FAMILY,
            }
        )

    for record in trusted_positive_records:
        frame_id = _safe_int(record["frameId"], -1)
        if frame_id < 0:
            continue
        match_id = str(record["matchId"])
        frame_shape = _shape(Path(str(record["videoPath"])))
        player_rows_for_frame = _match_player_rows(match_id).get(frame_id, [])
        proposal_specs = _build_runtime_proposal_specs_for_frame(
            frame_shape=frame_shape,
            player_rows_for_frame=player_rows_for_frame,
            seed_center=_bbox_center(dict(record["bbox"])),
            source_clip_id=str(record["sourceClipId"] or DEFAULT_FAILING_SOURCE_CLIP_ID),
        )
        for spec in proposal_specs:
            crop_window = tuple(spec["cropWindow"])
            crop_window_kind = str(spec["cropWindowKind"])
            if _bbox_overlaps_window(dict(record["bbox"]), crop_window):
                _append_positive_example(
                    record=record,
                    crop_window_kind=crop_window_kind,
                    crop_window=crop_window,
                )
            else:
                _append_negative_candidate(
                    priority_label="other_non_overlap_runtime_windows",
                    priority_rank=2,
                    curation_unit_id=str(record["curationUnitId"]),
                    match_id=match_id,
                    split_name=str(record["split"]),
                    frame_id=frame_id,
                    video_path=str(record["videoPath"]),
                    crop_window_kind=crop_window_kind,
                    crop_window=crop_window,
                    seed_source="trusted_positive_non_overlap_runtime_window",
                    source_label_status="mined_negative",
                    file_stem_prefix=str(record["fileStem"]),
                )

    baseline_probe_raw_rows = _load_truth_layer_rows(
        ball_truth_layers=ball_truth_layers,
        layer_name="probeObservedBall",
        nested_key="rawRows",
    )
    baseline_raw_rows_by_frame = _best_rows_by_frame(baseline_probe_raw_rows)
    filtered_frame_ids = {
        _safe_int(frame_id, -1)
        for frame_id in list(
            (
                (frame_level_probe_delta.get("layers") or {})
                .get("filteredProbe", {})
                .get("baselineFrameIds")
                or []
            )
        )
        if _safe_int(frame_id, -1) >= 0
    }

    for unit in curation_units:
        curation_unit_id = str(unit.get("curationUnitId") or "")
        match_id = str(unit.get("matchId") or "")
        split_name = split_overrides.get(curation_unit_id) or str(unit.get("split") or "train")
        video_path = _unit_video_path(unit)
        if video_path is None:
            continue
        trusted_centers_by_frame = trusted_positive_centers_by_unit.get(curation_unit_id, {})
        for example in list(unit.get("examples") or []):
            if not isinstance(example, dict):
                continue
            if str(example.get("seedSource") or "") != "hard_negative":
                continue
            frame_id = _safe_int(example.get("frameId"), -1)
            if frame_id < 0:
                continue
            player_rows_for_frame = _match_player_rows(match_id).get(frame_id, [])
            seed_center = _seed_center_for_negative_frame(
                frame_id=frame_id,
                unit=unit,
                baseline_raw_rows_by_frame=baseline_raw_rows_by_frame,
                trusted_positive_centers_by_frame=trusted_centers_by_frame,
                player_rows_for_frame=player_rows_for_frame,
            )
            if seed_center is None:
                continue
            frame_shape = _shape(video_path)
            proposal_specs = _build_runtime_proposal_specs_for_frame(
                frame_shape=frame_shape,
                player_rows_for_frame=player_rows_for_frame,
                seed_center=seed_center,
                source_clip_id=str(unit.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID),
            )
            for spec in proposal_specs:
                crop_window = tuple(spec["cropWindow"])
                if any(
                    _bbox_overlaps_window(bbox, crop_window)
                    for bbox in all_positive_bboxes_by_frame.get((match_id, frame_id), [])
                ):
                    continue
                _append_negative_candidate(
                    priority_label="existing_confirmed_negative",
                    priority_rank=0,
                    curation_unit_id=curation_unit_id,
                    match_id=match_id,
                    split_name=split_name,
                    frame_id=frame_id,
                    video_path=str(video_path),
                    crop_window_kind=str(spec["cropWindowKind"]),
                    crop_window=crop_window,
                    seed_source="hard_negative",
                    source_label_status="confirmed_negative",
                    file_stem_prefix=str(example.get("fileStem") or f"{curation_unit_id}__f{frame_id:04d}"),
                )

    neighborhood_frame_ids = sorted(
        {
            frame_id
            for frame_id in (
                _safe_int(frame_id, -1)
                for frame_id in list(
                    (
                        (frame_level_probe_delta.get("layers") or {})
                        .get("rawProbe", {})
                        .get("baselineFrameIds")
                        or []
                    )
                )
            )
            if frame_id >= 0
        }
    )
    for frame_id in neighborhood_frame_ids:
        if any(key_frame == frame_id for _, key_frame in trusted_positive_frames):
            continue
        unit = _find_curation_unit_for_frame(
            curation_units=curation_units,
            match_id=str(curation_units[0].get("matchId") if curation_units else ""),
            frame_id=frame_id,
            source_clip_id=DEFAULT_FAILING_SOURCE_CLIP_ID,
        )
        if unit is None:
            continue
        curation_unit_id = str(unit.get("curationUnitId") or "")
        match_id = str(unit.get("matchId") or "")
        video_path = _unit_video_path(unit)
        if video_path is None:
            continue
        seed_row = baseline_raw_rows_by_frame.get(frame_id)
        seed_center = _row_source_center(seed_row) if seed_row is not None else None
        if seed_center is None:
            continue
        player_rows_for_frame = _match_player_rows(match_id).get(frame_id, [])
        proposal_specs = _build_runtime_proposal_specs_for_frame(
            frame_shape=_shape(video_path),
            player_rows_for_frame=player_rows_for_frame,
            seed_center=seed_center,
            source_clip_id=str(unit.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID),
        )
        priority_label = (
            "baseline_filtered_or_raw_probe_neighborhood"
            if frame_id in filtered_frame_ids
            else "baseline_raw_probe_neighborhood"
        )
        for spec in proposal_specs:
            crop_window = tuple(spec["cropWindow"])
            if any(
                _bbox_overlaps_window(bbox, crop_window)
                for bbox in all_positive_bboxes_by_frame.get((match_id, frame_id), [])
            ):
                continue
            _append_negative_candidate(
                priority_label=priority_label,
                priority_rank=1,
                curation_unit_id=curation_unit_id,
                match_id=match_id,
                split_name=split_overrides.get(curation_unit_id) or str(unit.get("split") or "train"),
                frame_id=frame_id,
                video_path=str(video_path),
                crop_window_kind=str(spec["cropWindowKind"]),
                crop_window=crop_window,
                seed_source=priority_label,
                source_label_status="mined_negative",
                file_stem_prefix=f"{curation_unit_id}__f{frame_id:04d}",
            )

    positive_count = len(export_examples)
    negative_limit = max(positive_count * NEGATIVE_CAP_MULTIPLIER, 0)
    selected_negative_candidates = sorted(
        negative_candidates,
        key=lambda item: (
            _safe_int(item.get("priorityRank"), 99),
            str(item.get("split") or ""),
            _safe_int(item.get("frameId"), 0),
            str(item.get("cropWindowKind") or ""),
            str(item.get("fileStem") or ""),
        ),
    )[:negative_limit]
    for example in selected_negative_candidates:
        negative_window_kind_counts[str(example["cropWindowKind"])] += 1
        export_examples.append(example)

    alignment = {
        "windowFamily": DEFAULT_WINDOW_FAMILY,
        "directSeedRetryPolicy": str(run_guerilla.DIRECT_SEED_RETRY_POLICY),
        "directSeedRetryScales": [int(scale) for scale in run_guerilla.DIRECT_SEED_RETRY_SCALES],
        "positiveWindowKindCounts": dict(positive_window_kind_counts),
        "negativeWindowKindCounts": dict(negative_window_kind_counts),
        "negativePriorityCounts": dict(negative_priority_counts),
    }
    return (
        export_examples,
        alignment,
        (sum(full_frame_relative_areas) / len(full_frame_relative_areas)) if full_frame_relative_areas else 0.0,
        (sum(proposal_relative_areas) / len(proposal_relative_areas)) if proposal_relative_areas else 0.0,
    )


def _write_yolo_export(
    *,
    export_root: Path,
    export_examples: list[dict[str, object]],
) -> dict[str, object]:
    images_root = export_root / "images"
    labels_root = export_root / "labels"
    for split_name in ("train", "val"):
        (images_root / split_name).mkdir(parents=True, exist_ok=True)
        (labels_root / split_name).mkdir(parents=True, exist_ok=True)

    exported_examples: list[dict[str, object]] = []
    positive_count = 0
    negative_count = 0
    for example in export_examples:
        split_name = str(example["split"])
        file_stem = str(example["fileStem"])
        crop_window = tuple(example["cropWindow"])
        output_image = images_root / split_name / f"{file_stem}.jpg"
        output_label = labels_root / split_name / f"{file_stem}.txt"
        _extract_crop_image(
            video_path=Path(str(example["videoPath"])),
            frame_id=_safe_int(example["frameId"], 0),
            crop_window=crop_window,
            output_path=output_image,
        )
        label_line = str(example.get("labelLine") or "")
        output_label.write_text(label_line, encoding="utf-8")
        if label_line:
            positive_count += 1
        else:
            negative_count += 1
        exported_examples.append(
            {
                "curationUnitId": example["curationUnitId"],
                "matchId": example["matchId"],
                "split": split_name,
                "frameId": _safe_int(example["frameId"]),
                "imagePath": str(output_image),
                "labelPath": str(output_label),
                "cropWindowKind": example["cropWindowKind"],
                "cropWindow": list(crop_window),
                "sourceLabelStatus": example["sourceLabelStatus"],
                "seedSource": example.get("seedSource"),
                "windowFamily": example.get("windowFamily") or DEFAULT_WINDOW_FAMILY,
            }
        )
    _write_dataset_yaml(export_root)
    return {
        "proposalPositiveExampleCount": positive_count,
        "proposalNegativeExampleCount": negative_count,
        "exportedExamples": exported_examples,
        "yoloExportReady": positive_count > 0 and any(
            example["split"] == "val" for example in exported_examples
        ),
    }


def _build_split_manifest(exported_examples: list[dict[str, object]]) -> dict[str, object]:
    unique_examples_by_label_path: dict[str, dict[str, object]] = {}
    for example in exported_examples:
        label_path = str(example.get("labelPath") or "")
        key = label_path or json.dumps(example, sort_keys=True)
        unique_examples_by_label_path[key] = dict(example)

    curation_unit_splits: dict[str, set[str]] = {}
    validation_image_count = 0
    validation_positive_label_image_count = 0
    validation_empty_label_image_count = 0
    for example in unique_examples_by_label_path.values():
        curation_unit_id = str(example.get("curationUnitId") or "")
        split_name = str(example.get("split") or "")
        curation_unit_splits.setdefault(curation_unit_id, set()).add(split_name)
        if split_name == "val":
            validation_image_count += 1
            label_path = Path(str(example.get("labelPath") or ""))
            label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
            if label_text:
                validation_positive_label_image_count += 1
            else:
                validation_empty_label_image_count += 1
    leakage_detected = any(len(splits) > 1 for splits in curation_unit_splits.values())
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "exportImageMode": "proposal_windows_075_crops",
        "curationUnitCount": len(curation_unit_splits),
        "validationImageCount": validation_image_count,
        "validationPositiveLabelImageCount": validation_positive_label_image_count,
        "validationEmptyLabelImageCount": validation_empty_label_image_count,
        "validationInformative": validation_positive_label_image_count > 0,
        "sourceAwareSplitLeakageDetected": leakage_detected,
    }


def _build_alignment_report(
    *,
    alignment: dict[str, object],
    exported_examples: list[dict[str, object]],
    split_manifest: dict[str, object],
) -> dict[str, object]:
    unique_examples_by_label_path: dict[str, dict[str, object]] = {}
    for example in exported_examples:
        label_path = str(example.get("labelPath") or "")
        key = label_path or json.dumps(example, sort_keys=True)
        unique_examples_by_label_path[key] = dict(example)

    validation_positive_window_kind_counts: Counter[str] = Counter()
    for example in unique_examples_by_label_path.values():
        if str(example.get("split") or "") != "val":
            continue
        label_path = Path(str(example.get("labelPath") or ""))
        label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
        if not label_text:
            continue
        validation_positive_window_kind_counts[str(example.get("cropWindowKind") or "unknown")] += 1
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "proposalSignalFixBatchName": DEFAULT_BATCH_NAME,
        "windowFamily": alignment.get("windowFamily") or DEFAULT_WINDOW_FAMILY,
        "directSeedRetryPolicy": alignment.get("directSeedRetryPolicy"),
        "directSeedRetryScales": list(alignment.get("directSeedRetryScales") or []),
        "positiveWindowKindCounts": dict(alignment.get("positiveWindowKindCounts") or {}),
        "negativeWindowKindCounts": dict(alignment.get("negativeWindowKindCounts") or {}),
        "validationPositiveWindowKindCounts": dict(validation_positive_window_kind_counts),
        "proposalWindowValidationImageCount": _safe_int(split_manifest.get("validationImageCount"), 0),
        "proposalWindowValidationPositiveImageCount": _safe_int(
            split_manifest.get("validationPositiveLabelImageCount"),
            0,
        ),
        "proposalWindowValidationEmptyImageCount": _safe_int(
            split_manifest.get("validationEmptyLabelImageCount"),
            0,
        ),
        "negativePriorityCounts": dict(alignment.get("negativePriorityCounts") or {}),
    }


def _training_recipe() -> dict[str, object]:
    return {
        "baseModelPath": DEFAULT_BASE_MODEL_PATH,
        "imgsz": DEFAULT_IMGSZ,
        "epochs": DEFAULT_EPOCHS,
        "batch": DEFAULT_BATCH_SIZE,
        "device": DEFAULT_DEVICE,
        "workers": DEFAULT_WORKERS,
        "seed": DEFAULT_SEED,
        "augmentationPolicy": dict(train_custom.DEFAULT_AUGMENTATION_POLICY),
        "patience": DEFAULT_EPOCHS,
    }


def _build_training_config(
    *,
    artifact_root: Path,
    dataset_yaml_path: Path,
    suite_summary: dict[str, object],
    active_lane_snapshot: dict[str, object],
    failure_analysis_summary: dict[str, object],
    manifest: dict[str, object],
    requested_gpu_id: str | None,
    execution_mode: str,
) -> dict[str, object]:
    return {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "artifactRoot": str(artifact_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "executionMode": execution_mode,
        "requestedGpuId": requested_gpu_id,
        "datasetLineage": {
            "proposalSignalFixBatchName": DEFAULT_BATCH_NAME,
            "previousDataQualityFixBatchName": DEFAULT_PREVIOUS_BATCH_NAME,
            "validationGateRemediationBatchName": DEFAULT_VALIDATION_REMEDIATION_BATCH_NAME,
            "rootCauseClass": failure_analysis_summary.get("rootCauseClass"),
            "recommendedFixClass": failure_analysis_summary.get("recommendedFixClass"),
            "recommendedFixFocus": failure_analysis_summary.get("recommendedFixFocus"),
            "proposalPositiveExampleCount": manifest.get("proposalPositiveExampleCount"),
            "proposalNegativeExampleCount": manifest.get("proposalNegativeExampleCount"),
            "windowFamily": manifest.get("windowFamily"),
            "positiveWindowKindCounts": manifest.get("positiveWindowKindCounts"),
            "negativeWindowKindCounts": manifest.get("negativeWindowKindCounts"),
        },
        "trainingRecipe": _training_recipe(),
        "baselineReference": {
            "suiteVerdict": suite_summary.get("suiteVerdict"),
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "baselineFingerprint": active_lane_snapshot.get("baselineFingerprint", {}),
        },
        "detectorProfile": DETECTOR_PROFILE,
        "notes": [
            "This export is runtime-window aligned to proposal_windows_075 instead of the older player-window approximation.",
            "Roadmap stays pinned on evaluate_touchline_detector_candidate even if this batch succeeds.",
        ],
    }


def _build_evaluation_contract(
    *,
    active_lane_snapshot: dict[str, object],
    best_weights_path: str | None,
    last_weights_path: str | None,
    candidate_ready: bool,
) -> dict[str, object]:
    baseline_fingerprint = dict(active_lane_snapshot.get("baselineFingerprint") or {})
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "candidateReadyForEvaluation": candidate_ready,
        "localScreenTargetClipPath": str(REPO_ROOT / "videos" / DEFAULT_FAILING_SOURCE_CLIP_ID),
        "remoteProofComparisonBaseline": dict(PLATEAU_BASELINE),
        "activeFrozenBaseline": {
            "detectorModelPath": baseline_fingerprint.get("detectorModelPath") or DEFAULT_BASE_MODEL_PATH,
            "primaryMode": baseline_fingerprint.get("primaryMode") or "anchored_player_ranked_context_960",
            "cleanupLane": baseline_fingerprint.get("cleanupLane") or "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "candidateWeights": {
            "bestWeightsPath": best_weights_path,
            "lastWeightsPath": last_weights_path,
        },
        "auxiliaryBallModelProfile": DETECTOR_PROFILE,
    }


def _rewrite_dataset_yaml_for_remote(dataset_yaml_path: Path, *, remote_export_root: str) -> str:
    rewritten_lines: list[str] = []
    replaced_path = False
    for raw_line in dataset_yaml_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("path:"):
            rewritten_lines.append(f"path: {remote_export_root}")
            replaced_path = True
        else:
            rewritten_lines.append(raw_line)
    if not replaced_path:
        rewritten_lines.insert(0, f"path: {remote_export_root}")
    rewritten_lines.append("")
    return "\n".join(rewritten_lines)


def _stage_dataset_on_pod(
    *,
    session: dict[str, object],
    dataset_export_root: Path,
    dataset_yaml_path: Path,
) -> str:
    remote_export_root = f"{session['remoteStorageRoot']}/training_prep/{DEFAULT_BATCH_NAME}/yolo_export"
    runpod_session.copy_directory_to_pod(
        ssh_command=list(session["sshCommand"]),
        local_path=dataset_export_root,
        remote_path=remote_export_root,
    )
    rewritten_dataset_yaml = _rewrite_dataset_yaml_for_remote(
        dataset_yaml_path,
        remote_export_root=remote_export_root,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dataset_yaml = Path(tmpdir) / "dataset.yaml"
        temp_dataset_yaml.write_text(rewritten_dataset_yaml, encoding="utf-8")
        runpod_session.copy_file_to_pod(
            list(session["sshCommand"]),
            local_path=temp_dataset_yaml,
            remote_path=f"{remote_export_root}/dataset.yaml",
        )
    return f"{remote_export_root}/dataset.yaml"


def _build_remote_training_command(
    *,
    session: dict[str, object],
    remote_dataset_yaml_path: str,
    staged_model_path: str,
    training_recipe: dict[str, object],
    requested_gpu_id: str | None,
) -> str:
    remote_repo_root = str(session["remoteRepoRoot"])
    remote_project_root = (
        f"{session['remoteStorageRoot']}/trained_detector_candidates/{DEFAULT_CANDIDATE_NAME}/ultralytics_run"
    )
    augmentation_policy = dict(training_recipe.get("augmentationPolicy") or {})
    remote_command = f"""
set -euo pipefail
cd {shlex.quote(remote_repo_root)}
source {shlex.quote(runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(remote_repo_root)}
export YOLO_CONFIG_DIR={shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
mkdir -p {shlex.quote(remote_project_root)} {shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
python - <<'PY'
import json
from pathlib import Path

import torch

import backend.train_custom as train_custom

result = train_custom.fine_tune(
    data_yaml={remote_dataset_yaml_path!r},
    model_path={staged_model_path!r},
    epochs={_safe_int(training_recipe.get("epochs"), DEFAULT_EPOCHS)},
    imgsz={_safe_int(training_recipe.get("imgsz"), DEFAULT_IMGSZ)},
    batch={_safe_int(training_recipe.get("batch"), DEFAULT_BATCH_SIZE)},
    device={str(training_recipe.get("device") or DEFAULT_DEVICE)!r},
    project={remote_project_root!r},
    name="training",
    patience={_safe_int(training_recipe.get("patience"), DEFAULT_EPOCHS)},
    workers={_safe_int(training_recipe.get("workers"), DEFAULT_WORKERS)},
    seed={_safe_int(training_recipe.get("seed"), DEFAULT_SEED)},
    augmentation_policy={augmentation_policy!r},
)
payload = dict(result)
payload["trainingCompleted"] = True
payload["remoteDatasetYamlPath"] = {remote_dataset_yaml_path!r}
payload["remoteModelPath"] = {staged_model_path!r}
payload["requestedGpuId"] = {requested_gpu_id!r}
payload["remoteDeviceName"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
payload["allocatedGpuId"] = payload["remoteDeviceName"]
print(json.dumps(payload))
PY
"""
    return f"bash -lc {shlex.quote(remote_command)}"


def _pull_remote_artifact(
    *,
    session: dict[str, object],
    remote_path: str | None,
    local_path: Path,
) -> str | None:
    runpod_session.require_retired_runpod_disabled()


def _allocated_gpu_id(session: dict[str, object], remote_training_result: dict[str, object]) -> str | None:
    for value in (
        remote_training_result.get("allocatedGpuId"),
        remote_training_result.get("remoteDeviceName"),
        (session.get("podPayload") or {}).get("gpuId") if isinstance(session.get("podPayload"), dict) else None,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


def _candidate_brainstorm_fixes(primary_blocker: str | None) -> list[str]:
    if primary_blocker == "proposal_window_sanity_zero_detections":
        return [
            "Inspect the runtime-aligned validation proposal windows locally and verify the detector produces non-zero detections before bounded evaluation.",
            "Keep the roadmap on evaluate_touchline_detector_candidate and iterate inside the same checklist.",
        ]
    if primary_blocker == "proposal_window_validation_has_no_positive_labels":
        return [
            "Repair the runtime-aligned validation slice so at least one positive failing-source proposal window remains in val.",
        ]
    if primary_blocker == "remote_training_failed":
        return [
            "Inspect the remote training error and rerun this proposal-window batch without advancing the roadmap.",
        ]
    if primary_blocker == "weights_unusable":
        return [
            "Recover the missing best.pt artifact or rerun the proposal-window training batch.",
        ]
    return [
        "Inspect the latest proposal_window_alignment_report.json, training_quality_gate_v1, and batch_outcome_analysis before rerunning this batch.",
        "Keep the roadmap on evaluate_touchline_detector_candidate until a later bounded evaluation actually wins.",
    ]


def _build_candidate_batch_outcome(
    *,
    training_completed: bool,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    training_quality_gate_passed: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    goal_achieved = ready_for_detector_evaluation
    if goal_achieved:
        english_summary = (
            "This batch trained a runtime-window-aligned v6 candidate and the strengthened proposal-window training-quality gate passed."
        )
        english_decision = (
            "The batch achieved its goal. The roadmap stays in Phase 3, but bounded detector evaluation is now allowed to resume with v6."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a runtime-window-aligned v6 candidate, but the proposal-signal remediation is still blocked."
        )
        english_decision = (
            f"The batch did not achieve its goal, so bounded evaluation must stay blocked while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Build one runtime-window-aligned v6 detector candidate and require the strengthened proposal-window training-quality gate to pass before bounded evaluation.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "evaluationContractReady": evaluation_contract_ready,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": [] if goal_achieved else _candidate_brainstorm_fixes(primary_blocker),
    }


def _candidate_batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Candidate Batch Outcome Analysis",
            "",
            f"Batch goal: {batch_outcome_analysis.get('batchGoal')}",
            f"Goal achieved: {batch_outcome_analysis.get('goalAchieved')}",
            f"Roadmap advance allowed: {batch_outcome_analysis.get('roadmapAdvanceAllowed')}",
            "",
            f"Summary: {batch_outcome_analysis.get('englishSummary')}",
            f"Decision: {batch_outcome_analysis.get('englishDecision')}",
            f"Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
            "",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Evaluation contract ready: {batch_outcome_analysis.get('evaluationContractReady')}",
            f"Training-quality gate passed: {batch_outcome_analysis.get('trainingQualityGatePassed')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def _overall_brainstorm_fixes(primary_blocker: str | None) -> list[str]:
    if primary_blocker == "proposal_export_empty":
        return [
            "Inspect the runtime-aligned proposal-window export and verify trusted positives overlap at least one generated proposal window.",
            "Do not reopen filtering or acceptance logic while proposal-stage signal is still empty.",
        ]
    return _candidate_brainstorm_fixes(primary_blocker)


def _build_batch_outcome_analysis(
    *,
    proposal_positive_example_count: int,
    proposal_negative_example_count: int,
    yolo_export_ready: bool,
    training_completed: bool,
    weights_ready: bool,
    training_quality_gate_passed: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    goal_achieved = (
        proposal_positive_example_count > 0
        and proposal_negative_example_count > 0
        and yolo_export_ready
        and training_completed
        and weights_ready
        and training_quality_gate_passed
        and ready_for_detector_evaluation
    )
    if goal_achieved:
        english_summary = (
            "This batch rebuilt the proposal export from runtime-aligned proposal windows, strengthened the live-aligned gate, and trained a new evaluation-ready v6 candidate."
        )
        english_decision = (
            "The batch achieved its goal, but the suite still stays on evaluate_touchline_detector_candidate until v6 wins bounded evaluation."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a runtime-window-aligned proposal-signal fix artifact and a complete v6 candidate, but it did not get all the way there."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay on evaluate_touchline_detector_candidate while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Create a runtime-window-aligned proposal export, retrain one gate-clean touchline_detector_candidate_v6, and keep the roadmap pinned on evaluate_touchline_detector_candidate.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "proposalPositiveExampleCount": proposal_positive_example_count,
        "proposalNegativeExampleCount": proposal_negative_example_count,
        "yoloExportReady": yolo_export_ready,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": [] if goal_achieved else _overall_brainstorm_fixes(primary_blocker),
    }


def _batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Batch Outcome Analysis",
            "",
            f"Batch goal: {batch_outcome_analysis.get('batchGoal')}",
            f"Goal achieved: {batch_outcome_analysis.get('goalAchieved')}",
            f"Roadmap advance allowed: {batch_outcome_analysis.get('roadmapAdvanceAllowed')}",
            "",
            f"Summary: {batch_outcome_analysis.get('englishSummary')}",
            f"Decision: {batch_outcome_analysis.get('englishDecision')}",
            f"Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
            "",
            f"Proposal positive example count: {batch_outcome_analysis.get('proposalPositiveExampleCount')}",
            f"Proposal negative example count: {batch_outcome_analysis.get('proposalNegativeExampleCount')}",
            f"YOLO export ready: {batch_outcome_analysis.get('yoloExportReady')}",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Training-quality gate passed: {batch_outcome_analysis.get('trainingQualityGatePassed')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def run_touchline_detector_candidate_v5_proposal_signal_generation_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
