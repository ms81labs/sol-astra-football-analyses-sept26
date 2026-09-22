"""Historical proposal recipe, retired with its RunPod execution path."""

from __future__ import annotations


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

import os
from pathlib import Path
import shlex
import tempfile

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.run_guerilla as run_guerilla  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402
import backend.train_custom as train_custom  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_proposal_signal_generation_fix_v1"
DEFAULT_TRAINING_BATCH_NAME = "touchline_detector_candidate_proposal_signal_generation_fix_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v4"
DEFAULT_PREVIOUS_BATCH_NAME = "touchline_model_data_quality_fix_v1"
DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME = "touchline_detector_candidate_v3"
DEFAULT_FAILURE_ANALYSIS_BATCH_NAME = "failure_analysis_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_COMPARISON_SOURCE_CLIP_ID = "trimed-football-2-1minute.mp4"
DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_EPOCHS = 12
DEFAULT_BATCH_SIZE = 8
DEFAULT_DEVICE = "0"
DEFAULT_WORKERS = 4
DEFAULT_SEED = 42
DEFAULT_EXECUTION_MODE = "remote_gpu"
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


def _json_safe_metrics(metrics: object) -> dict[str, object]:
    if not isinstance(metrics, dict):
        return {}
    normalized: dict[str, object] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            normalized[str(key)] = value
        elif isinstance(value, (int, float, str)) or value is None:
            normalized[str(key)] = value
        else:
            try:
                normalized[str(key)] = float(value)
            except (TypeError, ValueError):
                normalized[str(key)] = str(value)
    return normalized


def _paths(storage_root: Path) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    previous_root = storage_root / "training_prep" / DEFAULT_PREVIOUS_BATCH_NAME
    failure_root = (
        storage_root
        / "trained_detector_candidates"
        / DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME
        / DEFAULT_FAILURE_ANALYSIS_BATCH_NAME
    )
    artifact_root = storage_root / "training_prep" / DEFAULT_BATCH_NAME
    candidate_root = storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
    return {
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "failureAnalysisSummaryPath": failure_root / "failure_analysis_summary.json",
        "profileMatrixDeltaPath": failure_root / "profile_matrix_delta.json",
        "previousManifestPath": previous_root / "data_quality_fix_manifest.json",
        "previousOverlayPath": previous_root / "reviewed_label_overlay.json",
        "previousBatchOutcomePath": previous_root / "batch_outcome_analysis.json",
        "artifactRoot": artifact_root,
        "manifestPath": artifact_root / "proposal_signal_fix_manifest.json",
        "splitManifestPath": artifact_root / "split_manifest.json",
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
    runpod_session.require_retired_runpod_disabled()


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
    decision = str(review_item.get("decision") or "")
    if decision == "adjust_bbox" and isinstance(review_item.get("reviewedBBox"), dict):
        bbox = review_item["reviewedBBox"]
    elif decision == "accept_seed" and isinstance(review_item.get("seedBBox"), dict):
        bbox = review_item["seedBBox"]
    else:
        return None
    x1 = _safe_float(bbox.get("x1"), -1.0)
    y1 = _safe_float(bbox.get("y1"), -1.0)
    x2 = _safe_float(bbox.get("x2"), -1.0)
    y2 = _safe_float(bbox.get("y2"), -1.0)
    if min(x1, y1, x2, y2) < 0 or x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _bbox_center(bbox: dict[str, float]) -> tuple[float, float]:
    return ((bbox["x1"] + bbox["x2"]) / 2.0, (bbox["y1"] + bbox["y2"]) / 2.0)


def _bbox_area(bbox: dict[str, float]) -> float:
    return max(bbox["x2"] - bbox["x1"], 0.0) * max(bbox["y2"] - bbox["y1"], 0.0)


def _normalize_window(window: tuple[int, int, int, int] | tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    return (
        int(round(float(window[0]))),
        int(round(float(window[1]))),
        int(round(float(window[2]))),
        int(round(float(window[3]))),
    )


def _window_area(window: tuple[int, int, int, int]) -> float:
    return max(float(window[2] - window[0]), 0.0) * max(float(window[3] - window[1]), 0.0)


def _bbox_overlaps_window(bbox: dict[str, float], window: tuple[int, int, int, int]) -> bool:
    overlap_left = max(float(window[0]), bbox["x1"])
    overlap_top = max(float(window[1]), bbox["y1"])
    overlap_right = min(float(window[2]), bbox["x2"])
    overlap_bottom = min(float(window[3]), bbox["y2"])
    return overlap_right > overlap_left and overlap_bottom > overlap_top


def _crop_label_line(
    *,
    bbox: dict[str, float],
    crop_window: tuple[int, int, int, int],
) -> tuple[str, float]:
    crop_width = max(float(crop_window[2] - crop_window[0]), 1.0)
    crop_height = max(float(crop_window[3] - crop_window[1]), 1.0)
    local_x1 = max(bbox["x1"] - float(crop_window[0]), 0.0)
    local_y1 = max(bbox["y1"] - float(crop_window[1]), 0.0)
    local_x2 = min(bbox["x2"] - float(crop_window[0]), crop_width)
    local_y2 = min(bbox["y2"] - float(crop_window[1]), crop_height)
    if local_x2 <= local_x1 or local_y2 <= local_y1:
        raise ValueError("Bounding box does not intersect crop window")
    box_width = local_x2 - local_x1
    box_height = local_y2 - local_y1
    center_x = local_x1 + (box_width / 2.0)
    center_y = local_y1 + (box_height / 2.0)
    label_line = " ".join(
        [
            "0",
            f"{center_x / crop_width:.6f}",
            f"{center_y / crop_height:.6f}",
            f"{box_width / crop_width:.6f}",
            f"{box_height / crop_height:.6f}",
        ]
    )
    return label_line, (box_width * box_height) / (crop_width * crop_height)


def _load_player_rows_by_frame(storage: Storage, match_id: str) -> dict[int, list[dict[str, object]]]:
    rows = storage.load_raw_rows(match_id)
    by_frame: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        if row.get("Entity_Type") == "ball":
            continue
        if not all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
            continue
        frame_id = _safe_int(row.get("Frame_ID", row.get("frameId")), -1)
        if frame_id < 0:
            continue
        by_frame.setdefault(frame_id, []).append(dict(row))
    return by_frame


def _proposal_crop_specs_for_positive(
    *,
    frame_shape: tuple[int, int],
    bbox: dict[str, float],
    player_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    center = _bbox_center(bbox)
    source_box = (bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"])
    specs: list[dict[str, object]] = []
    seen: set[tuple[int, int, int, int]] = set()

    tight = run_guerilla._player_proposal_crop_window(frame_shape, source_box)
    if tight is not None:
        normalized_tight = _normalize_window(tight)
        if _bbox_overlaps_window(bbox, normalized_tight):
            specs.append(
                {
                    "cropWindowKind": "direct_seed_tight",
                    "cropWindow": normalized_tight,
                }
            )
            seen.add(normalized_tight)

    context_window, _expansion_px, _expanded = run_guerilla._player_biased_seed_context_crop_window(
        frame_shape,
        source_box,
        center,
    )
    if context_window is not None:
        normalized_context = _normalize_window(context_window)
        if normalized_context not in seen and _bbox_overlaps_window(bbox, normalized_context):
            specs.append(
                {
                    "cropWindowKind": "direct_seed_context",
                    "cropWindow": normalized_context,
                }
            )
            seen.add(normalized_context)

    ranked_windows: list[tuple[int, int, int, int]] = []
    for player_row in player_rows:
        source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
        player_window = run_guerilla._player_proposal_crop_window(
            frame_shape,
            tuple(_safe_float(player_row[key], 0.0) for key in source_keys),
        )
        if player_window is None:
            continue
        normalized_player_window = _normalize_window(player_window)
        if normalized_player_window in seen:
            continue
        if not _bbox_overlaps_window(bbox, normalized_player_window):
            continue
        ranked_windows.append(normalized_player_window)
    if ranked_windows:
        best_ranked = min(ranked_windows, key=_window_area)
        specs.append(
            {
                "cropWindowKind": "player_ranked",
                "cropWindow": best_ranked,
            }
        )
    return specs


def _proposal_crop_spec_for_negative(
    *,
    frame_shape: tuple[int, int],
    player_rows: list[dict[str, object]],
) -> dict[str, object] | None:
    ranked_windows: list[tuple[int, int, int, int]] = []
    for player_row in player_rows:
        source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
        player_window = run_guerilla._player_proposal_crop_window(
            frame_shape,
            tuple(_safe_float(player_row[key], 0.0) for key in source_keys),
        )
        if player_window is None:
            continue
        ranked_windows.append(_normalize_window(player_window))
    if not ranked_windows:
        return None
    return {
        "cropWindowKind": "player_ranked",
        "cropWindow": min(ranked_windows, key=_window_area),
    }


def _build_export_examples(
    *,
    current_manifest: dict[str, object],
    current_overlay: dict[str, object],
    storage: Storage,
) -> tuple[list[dict[str, object]], float, float]:
    unit_by_id = {
        str(unit.get("curationUnitId") or ""): dict(unit)
        for unit in list(current_manifest.get("curationUnits") or [])
        if isinstance(unit, dict)
    }
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

    export_examples: list[dict[str, object]] = []
    full_frame_relative_areas: list[float] = []
    proposal_relative_areas: list[float] = []

    for review_item in list(current_overlay.get("reviewItems") or []):
        if not isinstance(review_item, dict):
            continue
        bbox = _bbox_from_review_item(review_item)
        if bbox is None:
            continue
        curation_unit_id = str(review_item.get("curationUnitId") or "")
        unit = unit_by_id.get(curation_unit_id)
        if unit is None:
            continue
        video_path = Path(str((unit.get("examples") or [{}])[0].get("videoPath") or ""))
        if not str(video_path):
            continue
        frame_shape = _shape(video_path)
        frame_height, frame_width = frame_shape
        full_frame_relative_areas.append(_bbox_area(bbox) / max(float(frame_width * frame_height), 1.0))
        player_rows = _match_player_rows(str(review_item.get("matchId") or "")).get(
            _safe_int(review_item.get("frameIndex"), -1),
            [],
        )
        for crop_spec in _proposal_crop_specs_for_positive(
            frame_shape=frame_shape,
            bbox=bbox,
            player_rows=player_rows,
        ):
            label_line, area_share = _crop_label_line(
                bbox=bbox,
                crop_window=tuple(crop_spec["cropWindow"]),
            )
            proposal_relative_areas.append(area_share)
            export_examples.append(
                {
                    "curationUnitId": curation_unit_id,
                    "matchId": review_item.get("matchId"),
                    "split": review_item.get("split") or unit.get("split") or "train",
                    "frameId": _safe_int(review_item.get("frameIndex"), 0),
                    "videoPath": str(video_path),
                    "fileStem": f"{review_item.get('fileStem') or review_item.get('reviewItemId')}__{crop_spec['cropWindowKind']}",
                    "cropWindowKind": crop_spec["cropWindowKind"],
                    "cropWindow": tuple(crop_spec["cropWindow"]),
                    "labelLine": label_line,
                    "sourceLabelStatus": "reviewed_positive",
                    "seedSource": review_item.get("seedSource"),
                }
            )

    for unit in unit_by_id.values():
        examples = [dict(example) for example in list(unit.get("examples") or []) if isinstance(example, dict)]
        for example in examples:
            if str(example.get("seedSource") or "") != "hard_negative":
                continue
            video_path = Path(str(example.get("videoPath") or ""))
            if not str(video_path):
                continue
            frame_shape = _shape(video_path)
            player_rows = _match_player_rows(str(unit.get("matchId") or "")).get(
                _safe_int(example.get("frameId"), -1),
                [],
            )
            crop_spec = _proposal_crop_spec_for_negative(
                frame_shape=frame_shape,
                player_rows=player_rows,
            )
            if crop_spec is None:
                continue
            export_examples.append(
                {
                    "curationUnitId": unit.get("curationUnitId"),
                    "matchId": unit.get("matchId"),
                    "split": example.get("split") or unit.get("split") or "train",
                    "frameId": _safe_int(example.get("frameId"), 0),
                    "videoPath": str(video_path),
                    "fileStem": f"{example.get('fileStem') or unit.get('curationUnitId')}__{crop_spec['cropWindowKind']}_negative",
                    "cropWindowKind": crop_spec["cropWindowKind"],
                    "cropWindow": tuple(crop_spec["cropWindow"]),
                    "labelLine": "",
                    "sourceLabelStatus": "confirmed_negative",
                    "seedSource": example.get("seedSource"),
                }
            )

    return (
        export_examples,
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


def _build_split_manifest(export_examples: list[dict[str, object]]) -> dict[str, object]:
    curation_unit_splits: dict[str, set[str]] = {}
    for example in export_examples:
        curation_unit_id = str(example.get("curationUnitId") or "")
        split_name = str(example.get("split") or "")
        curation_unit_splits.setdefault(curation_unit_id, set()).add(split_name)
    leakage_detected = any(len(splits) > 1 for splits in curation_unit_splits.values())
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "exportImageMode": "proposal_crops",
        "curationUnitCount": len(curation_unit_splits),
        "sourceAwareSplitLeakageDetected": leakage_detected,
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
            "rootCauseClass": failure_analysis_summary.get("rootCauseClass"),
            "recommendedFixClass": failure_analysis_summary.get("recommendedFixClass"),
            "recommendedFixFocus": failure_analysis_summary.get("recommendedFixFocus"),
            "proposalPositiveExampleCount": manifest.get("proposalPositiveExampleCount"),
            "proposalNegativeExampleCount": manifest.get("proposalNegativeExampleCount"),
            "fullFrameMeanRelativeBallArea": manifest.get("fullFrameMeanRelativeBallArea"),
            "meanRelativeBallAreaInProposalCrops": manifest.get("meanRelativeBallAreaInProposalCrops"),
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
            "This export is proposal-crop aligned and is meant to match the auxiliary recovery detector task, not full-frame runtime detection.",
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
        "promotionReadySuccessMeans": [
            "candidate is good enough to enter bounded screen and proof evaluation",
            "candidate is not promoted into runtime defaults by this batch",
        ],
        "failFastConditions": [
            "training artifact missing",
            "weights unusable",
            "provenance incomplete",
            "no meaningful candidate output to evaluate",
        ],
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


def _candidate_ready_for_evaluation(
    *,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    remote_training_result: dict[str, object],
) -> tuple[bool, str | None]:
    if not weights_ready:
        return False, "weights_unusable"
    if not evaluation_contract_ready:
        return False, "evaluation_contract_incomplete"
    if not str(remote_training_result.get("remoteDatasetYamlPath") or "").strip():
        return False, "training_provenance_incomplete"
    if not str(remote_training_result.get("remoteModelPath") or "").strip():
        return False, "training_provenance_incomplete"
    return True, None


def _candidate_brainstorm_fixes(primary_blocker: str | None, error_message: str | None) -> list[str]:
    if primary_blocker == "remote_training_failed":
        fixes = [
            "Inspect the remote training error and rerun the proposal-signal batch after fixing the pod-side failure.",
            "Confirm the proposal-crop dataset staged correctly on the pod and that the remote dataset.yaml path points at the pod copy.",
        ]
        if error_message:
            fixes.append(f"Start with the captured training error: {error_message}")
        return fixes
    if primary_blocker == "weights_unusable":
        return [
            "Verify the remote Ultralytics run produced best.pt and last.pt, then rerun the proposal-signal batch.",
            "Confirm the weight pull-back paths match the remote training output paths.",
        ]
    if primary_blocker == "training_provenance_incomplete":
        return [
            "Restore missing remote training provenance fields so the batch records the dataset path and model path cleanly.",
            "Rerun the proposal-signal batch after the training summary is provenance-complete.",
        ]
    if primary_blocker == "evaluation_contract_incomplete":
        return [
            "Regenerate the evaluation contract and confirm it targets trimed-5min.mp4 with the standing 101 / 98 / false / 0.812 reference.",
        ]
    return [
        "Inspect the latest training_run_summary.json and batch_outcome_analysis.json before rerunning this batch.",
        "Fix the primary blocker and rerun the proposal-signal batch without moving the roadmap forward early.",
    ]


def _build_candidate_batch_outcome(
    *,
    training_completed: bool,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
    error_message: str | None,
) -> dict[str, object]:
    goal_achieved = ready_for_detector_evaluation
    if goal_achieved:
        english_summary = (
            "This batch trained a refreshed v4 detector candidate from proposal-aligned crops and produced a complete evaluation-ready artifact."
        )
        english_decision = (
            "The batch achieved its goal, but the roadmap stays pinned on evaluate_touchline_detector_candidate until v4 wins bounded evaluation."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a complete, evaluation-ready v4 detector candidate, but it did not get all the way there."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay on evaluate_touchline_detector_candidate while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Train one refreshed v4 detector candidate from proposal-aligned crops and make it evaluation-ready.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "evaluationContractReady": evaluation_contract_ready,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": [] if goal_achieved else _candidate_brainstorm_fixes(primary_blocker, error_message),
    }


def _candidate_batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
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
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Evaluation contract ready: {batch_outcome_analysis.get('evaluationContractReady')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def _overall_brainstorm_fixes(primary_blocker: str | None) -> list[str]:
    if primary_blocker == "proposal_crop_distribution_not_improved":
        return [
            "Inspect the generated proposal crops and widen or reposition the crop builder only if the exported ball area is still too close to full-frame scale.",
            "Prefer the crop window kind that most closely matches the successful baseline proposal profile before changing the training recipe.",
        ]
    if primary_blocker == "proposal_export_empty":
        return [
            "Inspect the reviewed overlay and match raw_rows to confirm the accepted positive frames still map onto valid proposal crops.",
            "Relax the crop-window selection slightly only if the saved artifacts prove the current overlap gate is too strict.",
        ]
    return [
        "Inspect the generated proposal-signal manifest and batch outcome before rerunning this batch.",
        "Keep the roadmap on evaluate_touchline_detector_candidate and fix the primary blocker without opening a new lane.",
    ]


def _build_batch_outcome_analysis(
    *,
    proposal_positive_example_count: int,
    proposal_negative_example_count: int,
    full_frame_mean_relative_ball_area: float,
    mean_relative_ball_area_in_proposal_crops: float,
    yolo_export_ready: bool,
    training_completed: bool,
    weights_ready: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    goal_achieved = (
        proposal_positive_example_count > 0
        and proposal_negative_example_count > 0
        and mean_relative_ball_area_in_proposal_crops > full_frame_mean_relative_ball_area
        and yolo_export_ready
        and training_completed
        and weights_ready
        and ready_for_detector_evaluation
    )
    if goal_achieved:
        english_summary = (
            "This batch converted the reviewed source set into proposal-aligned crops, increased the ball’s relative size in the export, and trained an evaluation-ready v4 candidate."
        )
        english_decision = (
            "The batch achieved its goal, but the suite still stays on evaluate_touchline_detector_candidate until v4 wins bounded evaluation."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to build a proposal-signal fix artifact and a complete v4 candidate, but it did not get all the way there."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay on evaluate_touchline_detector_candidate while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Create a proposal-aligned crop export and retrain one evaluation-ready touchline_detector_candidate_v4.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "proposalPositiveExampleCount": proposal_positive_example_count,
        "proposalNegativeExampleCount": proposal_negative_example_count,
        "fullFrameMeanRelativeBallArea": round(full_frame_mean_relative_ball_area, 8),
        "meanRelativeBallAreaInProposalCrops": round(mean_relative_ball_area_in_proposal_crops, 8),
        "yoloExportReady": yolo_export_ready,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
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
            f"Full-frame mean relative ball area: {batch_outcome_analysis.get('fullFrameMeanRelativeBallArea')}",
            f"Proposal mean relative ball area: {batch_outcome_analysis.get('meanRelativeBallAreaInProposalCrops')}",
            f"YOLO export ready: {batch_outcome_analysis.get('yoloExportReady')}",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def run_touchline_detector_candidate_proposal_signal_generation_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
