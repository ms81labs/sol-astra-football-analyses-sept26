"""Historical training recipe, retired with its RunPod execution path."""

from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import re
import shlex
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]

import backend.scripts.runpod_session as runpod_session  # noqa: E402

DEFAULT_SUITE_ROOT = REPO_ROOT / "backend" / "storage" / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_detector_candidate_v7_training_prep_v1"
DEFAULT_TRAINING_MANIFEST_PATH = DEFAULT_SUITE_ROOT / DEFAULT_TRAINING_PREP_BATCH_NAME / "v7_training_manifest.json"
DEFAULT_BATCH_NAME = "touchline_detector_candidate_v7_training"
DEFAULT_EXPORT_BATCH_NAME = "touchline_detector_candidate_v7_training_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_STORAGE_ROOT = REPO_ROOT / "backend" / "storage"
DEFAULT_EXPORT_ROOT = DEFAULT_STORAGE_ROOT / "training_prep" / DEFAULT_EXPORT_BATCH_NAME / "yolo_export"
DEFAULT_CANDIDATE_ROOT = DEFAULT_STORAGE_ROOT / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
DEFAULT_VIDEOS_ROOT = REPO_ROOT / "videos"
DEFAULT_EVALUATION_CLIP_ID = "trimed-5min.mp4"

DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_EPOCHS = 12
DEFAULT_BATCH_SIZE = 8
DEFAULT_DEVICE = "0"
DEFAULT_WORKERS = 4
DEFAULT_SEED = 42
PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")


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
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_stem(value: object) -> str:
    text = _SAFE_STEM_RE.sub("-", str(value or "").strip()).strip("-._")
    return text or "example"


def _split_name(raw_split: object) -> str:
    split = str(raw_split or "train").strip().lower()
    if split in {"validation", "valid", "val"}:
        return "val"
    return "train"


def _bbox_to_yolo_line(
    bbox: dict[str, object],
    *,
    frame_width: int,
    frame_height: int,
) -> str | None:
    if frame_width <= 0 or frame_height <= 0:
        return None
    x1 = max(0.0, min(float(frame_width), _safe_float(bbox.get("x1"))))
    y1 = max(0.0, min(float(frame_height), _safe_float(bbox.get("y1"))))
    x2 = max(0.0, min(float(frame_width), _safe_float(bbox.get("x2"))))
    y2 = max(0.0, min(float(frame_height), _safe_float(bbox.get("y2"))))
    if x2 <= x1 or y2 <= y1:
        return None
    cx = ((x1 + x2) / 2.0) / float(frame_width)
    cy = ((y1 + y2) / 2.0) / float(frame_height)
    width = (x2 - x1) / float(frame_width)
    height = (y2 - y1) / float(frame_height)
    return f"0 {cx:.6f} {cy:.6f} {width:.6f} {height:.6f}\n"


def _extract_frame_image(
    *,
    video_path: Path,
    frame_index: int,
    output_path: Path,
) -> tuple[int, int]:
    import cv2

    if frame_index < 0:
        raise ValueError(f"Invalid negative frame index {frame_index}")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found at {video_path}")
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise RuntimeError(f"Unable to open video {video_path}")
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Unable to read frame {frame_index} from {video_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"Unable to write extracted frame to {output_path}")
        height, width = frame.shape[:2]
        return int(width), int(height)
    finally:
        capture.release()


def _write_dataset_yaml(export_root: Path) -> Path:
    dataset_yaml_path = export_root / "dataset.yaml"
    dataset_yaml_path.write_text(
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
    return dataset_yaml_path


def _initial_split_counts() -> dict[str, dict[str, int]]:
    return {
        "train": {"positive": 0, "negative": 0, "invalidPositive": 0, "image": 0},
        "val": {"positive": 0, "negative": 0, "invalidPositive": 0, "image": 0},
    }


def _write_yolo_export(
    *,
    training_manifest: dict[str, object],
    export_root: Path,
    videos_root: Path,
) -> dict[str, object]:
    images_root = export_root / "images"
    labels_root = export_root / "labels"
    for split in ("train", "val"):
        (images_root / split).mkdir(parents=True, exist_ok=True)
        (labels_root / split).mkdir(parents=True, exist_ok=True)

    positives = [item for item in list(training_manifest.get("positiveExamples") or []) if isinstance(item, dict)]
    negatives = [item for item in list(training_manifest.get("negativeExamples") or []) if isinstance(item, dict)]
    exported_examples: list[dict[str, object]] = []
    invalid_positive_examples: list[dict[str, object]] = []
    extraction_errors: list[dict[str, object]] = []
    split_counts = _initial_split_counts()

    def export_example(example: dict[str, object], *, positive: bool) -> None:
        source_clip_id = str(example.get("sourceClipId") or "trimed-5min.mp4")
        frame_index = _safe_int(example.get("frameIndex"), -1)
        split = _split_name(example.get("split"))
        example_id = _safe_stem(example.get("exampleId") or f"{source_clip_id}-{frame_index}")
        stem = f"{example_id}__f{frame_index:06d}"
        image_path = images_root / split / f"{stem}.jpg"
        label_path = labels_root / split / f"{stem}.txt"
        label_text = ""
        try:
            frame_width, frame_height = _extract_frame_image(
                video_path=videos_root / source_clip_id,
                frame_index=frame_index,
                output_path=image_path,
            )
            if positive:
                bbox = example.get("bbox")
                if isinstance(bbox, dict):
                    label_text = _bbox_to_yolo_line(
                        bbox,
                        frame_width=frame_width,
                        frame_height=frame_height,
                    ) or ""
                if not label_text:
                    split_counts[split]["invalidPositive"] += 1
                    invalid_positive_examples.append(
                        {
                            "exampleId": example.get("exampleId"),
                            "sourceClipId": source_clip_id,
                            "frameIndex": frame_index,
                            "reason": "missing_or_invalid_bbox_after_clamp",
                        }
                    )
        except Exception as error:
            extraction_errors.append(
                {
                    "exampleId": example.get("exampleId"),
                    "sourceClipId": source_clip_id,
                    "frameIndex": frame_index,
                    "error": str(error),
                }
            )
            return
        label_path.write_text(label_text, encoding="utf-8")
        split_counts[split]["image"] += 1
        if label_text:
            split_counts[split]["positive"] += 1
        else:
            split_counts[split]["negative"] += 1
        exported_examples.append(
            {
                "exampleId": example.get("exampleId"),
                "sourceClipId": source_clip_id,
                "frameIndex": frame_index,
                "split": split,
                "truthUse": example.get("truthUse"),
                "imagePath": str(image_path),
                "labelPath": str(label_path),
                "positiveLabelWritten": bool(label_text),
            }
        )

    for example in positives:
        export_example(example, positive=True)
    for example in negatives:
        export_example(example, positive=False)

    dataset_yaml_path = _write_dataset_yaml(export_root)
    positive_count = sum(counts["positive"] for counts in split_counts.values())
    negative_count = sum(counts["negative"] for counts in split_counts.values())
    invalid_positive_count = sum(counts["invalidPositive"] for counts in split_counts.values())
    split_manifest = {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_BATCH_NAME,
        "sourceManifestPath": str(DEFAULT_TRAINING_MANIFEST_PATH),
        "splits": split_counts,
        "positiveExampleCount": positive_count,
        "negativeExampleCount": negative_count,
        "invalidPositiveLabelCount": invalid_positive_count,
        "sourceAwareSplitLeakageDetected": False,
        "readyForTraining": positive_count > 0 and negative_count > 0 and invalid_positive_count == 0 and not extraction_errors,
        "exportedExamples": exported_examples,
        "invalidPositiveExamples": invalid_positive_examples,
        "extractionErrors": extraction_errors,
    }
    _write_json(export_root / "split_manifest.json", split_manifest)
    export_summary = {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_BATCH_NAME,
        "exportRoot": str(export_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "positiveExampleCount": positive_count,
        "negativeExampleCount": negative_count,
        "invalidPositiveLabelCount": invalid_positive_count,
        "extractionErrorCount": len(extraction_errors),
        "yoloExportReady": bool(split_manifest["readyForTraining"]),
        "refutedSeedsReusedAsPositiveEvidence": False,
        "splitCounts": split_counts,
        "invalidPositiveExamples": invalid_positive_examples,
        "extractionErrors": extraction_errors,
    }
    _write_json(export_root.parent / "v7_training_export_summary.json", export_summary)
    return export_summary


def _training_recipe() -> dict[str, object]:
    return {
        "baseModelPath": DEFAULT_BASE_MODEL_PATH,
        "imgsz": DEFAULT_IMGSZ,
        "epochs": DEFAULT_EPOCHS,
        "batch": DEFAULT_BATCH_SIZE,
        "device": DEFAULT_DEVICE,
        "workers": DEFAULT_WORKERS,
        "seed": DEFAULT_SEED,
        "patience": DEFAULT_EPOCHS,
        "augmentationPolicy": {
            "degrees": 0.0,
            "translate": 0.05,
            "scale": 0.2,
            "shear": 0.0,
            "perspective": 0.0,
            "flipud": 0.0,
            "fliplr": 0.0,
            "mosaic": 0.0,
            "mixup": 0.0,
            "copy_paste": 0.0,
            "hsv_h": 0.01,
            "hsv_s": 0.2,
            "hsv_v": 0.2,
        },
    }


def _requested_gpu_id() -> str | None:
    loader = getattr(runpod_session, "_load_saved_runpod_gpu_id", None)
    if callable(loader):
        value = str(loader() or "").strip()
        if value:
            return value
    return None


def _create_remote_training_session(*, requested_gpu_id: str | None) -> tuple[dict[str, object], str | None]:
    try:
        return (
            runpod_session.create_runpod_session(
                clip_path=None,
                pod_name=f"{DEFAULT_CANDIDATE_NAME}-training",
                gpu_id=requested_gpu_id,
            ),
            None,
        )
    except Exception as error:
        if not requested_gpu_id:
            raise
        normalized = str(error).lower()
        if "not found" not in normalized and "unavailable" not in normalized and "requested gpu" not in normalized:
            raise
        session = runpod_session.create_runpod_session(
            clip_path=None,
            pod_name=f"{DEFAULT_CANDIDATE_NAME}-training",
            gpu_id=None,
        )
        return session, str(error)


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
    remote_export_root = f"{session['remoteStorageRoot']}/training_prep/{DEFAULT_EXPORT_BATCH_NAME}/yolo_export"
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


def _run_runpod_training(
    *,
    export_root: Path,
    dataset_yaml_path: Path,
    candidate_root: Path,
    training_recipe: dict[str, object],
) -> dict[str, object]:
    requested_gpu_id = _requested_gpu_id()
    session: dict[str, object] | None = None
    cleanup_result: dict[str, object] = {"podStopSucceeded": None, "podDeleteSucceeded": None, "cleanupErrors": []}
    try:
        session, fallback_reason = _create_remote_training_session(requested_gpu_id=requested_gpu_id)
        remote_dataset_yaml_path = _stage_dataset_on_pod(
            session=session,
            dataset_export_root=export_root,
            dataset_yaml_path=dataset_yaml_path,
        )
        staged_model = runpod_session.stage_model_on_pod(
            ssh_command=list(session["sshCommand"]),
            model_path=str(training_recipe["baseModelPath"]),
            remote_model_path=runpod_session.resolve_remote_model_path(str(training_recipe["baseModelPath"])),
            remote_repo_root=str(session["remoteRepoRoot"]),
        )
        remote_training_result = runpod_session.run_json_command_over_ssh(
            list(session["sshCommand"]),
            _build_remote_training_command(
                session=session,
                remote_dataset_yaml_path=remote_dataset_yaml_path,
                staged_model_path=str(staged_model["detectorModelPath"]),
                training_recipe=training_recipe,
                requested_gpu_id=requested_gpu_id,
            ),
        )
        remote_training_result.setdefault("trainingCompleted", True)
        remote_training_result.setdefault("remoteDatasetYamlPath", remote_dataset_yaml_path)
        remote_training_result.setdefault("remoteModelPath", staged_model["detectorModelPath"])
        if fallback_reason:
            remote_training_result["requestedGpuFallbackReason"] = fallback_reason
        weights_root = candidate_root / "weights"
        best_weights_path = _pull_remote_artifact(
            session=session,
            remote_path=str(remote_training_result.get("bestWeightsPath") or ""),
            local_path=weights_root / "best.pt",
        )
        last_weights_path = _pull_remote_artifact(
            session=session,
            remote_path=str(remote_training_result.get("lastWeightsPath") or ""),
            local_path=weights_root / "last.pt",
        )
        results_csv_path = _pull_remote_artifact(
            session=session,
            remote_path=str(remote_training_result.get("resultsCsvPath") or ""),
            local_path=candidate_root / "results.csv",
        )
        remote_training_result["bestWeightsLocalPath"] = best_weights_path
        remote_training_result["lastWeightsLocalPath"] = last_weights_path
        remote_training_result["resultsCsvLocalPath"] = results_csv_path
        return remote_training_result
    finally:
        if session is not None:
            cleanup_result = runpod_session.cleanup_runpod_session(
                session,
                stop_pod=True,
                delete_pod=True,
            )
            (candidate_root / "remote_cleanup_result.json").parent.mkdir(parents=True, exist_ok=True)
            _write_json(candidate_root / "remote_cleanup_result.json", cleanup_result)


def _validation_split_counts(dataset_yaml_path: Path) -> tuple[int, int, int]:
    dataset_root = dataset_yaml_path.parent
    val_images = sorted((dataset_root / "images" / "val").glob("*"))
    positive = 0
    empty = 0
    for image_path in val_images:
        if not image_path.is_file():
            continue
        label_path = dataset_root / "labels" / "val" / image_path.with_suffix(".txt").name
        label_text = label_path.read_text(encoding="utf-8").strip() if label_path.exists() else ""
        if label_text:
            positive += 1
        else:
            empty += 1
    return len([path for path in val_images if path.is_file()]), positive, empty


def _results_have_signal(results_csv_path: Path) -> bool:
    if not results_csv_path.exists():
        return False
    text = results_csv_path.read_text(encoding="utf-8").strip()
    if not text:
        return False
    lines = text.splitlines()
    if len(lines) <= 1:
        return False
    return any(any(ch.isdigit() and ch != "0" for ch in line) for line in lines[1:])


def _run_lightweight_quality_gate(
    *,
    candidate_root: Path,
    dataset_yaml_path: Path,
    training_completed: bool,
    weights_ready: bool,
) -> dict[str, object]:
    validation_image_count, validation_positive_count, validation_empty_count = _validation_split_counts(dataset_yaml_path)
    results_csv_path = candidate_root / "results.csv"
    metrics_have_signal = _results_have_signal(results_csv_path)
    primary_blocker: str | None = None
    if not training_completed:
        primary_blocker = "training_not_completed"
    elif not weights_ready:
        primary_blocker = "weights_missing"
    elif validation_image_count <= 0:
        primary_blocker = "validation_split_empty"
    elif validation_positive_count <= 0:
        primary_blocker = "validation_split_has_no_positive_labels"
    elif not metrics_have_signal:
        primary_blocker = "validation_metrics_missing_or_zero"
    summary = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "candidateRoot": str(candidate_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "validationImageCount": validation_image_count,
        "validationPositiveLabelImageCount": validation_positive_count,
        "validationEmptyLabelImageCount": validation_empty_count,
        "metricsHaveSignal": metrics_have_signal,
        "trainingQualityGatePassed": primary_blocker is None,
        "trainingQualityGatePrimaryBlocker": primary_blocker,
        "readyForDetectorEvaluation": primary_blocker is None,
    }
    _write_json(candidate_root / "training_quality_gate_v1" / "quality_gate_summary.json", summary)
    return summary


def _build_evaluation_contract(
    *,
    candidate_root: Path,
    best_weights_path: str | None,
    last_weights_path: str | None,
    ready_for_detector_evaluation: bool,
    videos_root: Path = DEFAULT_VIDEOS_ROOT,
) -> dict[str, object]:
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "trainingBatchName": DEFAULT_BATCH_NAME,
        "candidateRoot": str(candidate_root),
        "candidateReadyForEvaluation": ready_for_detector_evaluation,
        "localScreenTargetClipPath": str(videos_root / DEFAULT_EVALUATION_CLIP_ID),
        "remoteProofComparisonBaseline": dict(PLATEAU_BASELINE),
        "activeFrozenBaseline": {
            "detectorModelPath": DEFAULT_BASE_MODEL_PATH,
            "primaryMode": "anchored_player_ranked_context_960",
            "cleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "candidateWeights": {
            "bestWeightsPath": best_weights_path,
            "lastWeightsPath": last_weights_path,
        },
        "auxiliaryBallModelProfile": "ball_probe_only_v1",
        "runtimeDefaultMutationAllowed": False,
        "nextEvaluationBatch": "touchline_detector_candidate_v7_evaluation",
    }


def _build_batch_outcome_analysis(
    *,
    training_completed: bool,
    weights_ready: bool,
    training_quality_gate_passed: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
    error_message: str | None,
) -> dict[str, object]:
    goal_achieved = bool(
        training_completed and weights_ready and training_quality_gate_passed and ready_for_detector_evaluation
    )
    if goal_achieved:
        english_summary = (
            "The v7 detector training batch completed on RunPod, produced weights, passed the training-quality gate, and is ready for detector evaluation."
        )
        english_decision = (
            "Advance to touchline_detector_candidate_v7_evaluation. Runtime defaults remain frozen until evaluation and promotion truth clear the gate."
        )
        next_family = "touchline_detector_candidate_v7_evaluation"
    else:
        blocker = primary_blocker or "unknown_training_blocker"
        english_summary = (
            "The v7 training batch did not reach evaluation readiness. The export artifacts were kept so the next attempt can repair the exact blocker."
        )
        english_decision = f"Do not evaluate or promote v7 yet. Next corrective family: {blocker}."
        if blocker in {
            "export_not_ready",
            "training_quality_gate_failed",
            "validation_split_empty",
            "validation_split_has_no_positive_labels",
            "validation_metrics_missing_or_zero",
        }:
            next_family = "v7_training_manifest_repair"
        elif blocker == "runpod_training_required":
            next_family = "touchline_detector_candidate_v7_training_retry"
        else:
            next_family = "runpod_training_runtime_fix"
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "batchGoal": "Train touchline_detector_candidate_v7 from the reviewed v7 training manifest and stop at detector-evaluation readiness.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "runtimeDefaultMutationAllowed": False,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "primaryBlocker": primary_blocker,
        "errorMessage": error_message,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "nextRecommendedNextLever": next_family,
    }


def _batch_outcome_markdown(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            f"# {DEFAULT_BATCH_NAME}",
            "",
            f"- Goal achieved: `{payload.get('goalAchieved')}`",
            f"- Training completed: `{payload.get('trainingCompleted')}`",
            f"- Weights ready: `{payload.get('weightsReady')}`",
            f"- Quality gate passed: `{payload.get('trainingQualityGatePassed')}`",
            f"- Ready for detector evaluation: `{payload.get('readyForDetectorEvaluation')}`",
            f"- Primary blocker: `{payload.get('primaryBlocker')}`",
            f"- Next: `{payload.get('nextRecommendedNextLever')}`",
            "",
            str(payload.get("englishSummary") or ""),
            "",
            str(payload.get("englishDecision") or ""),
            "",
        ]
    )


def run_promoted_v6_touchline_detector_candidate_v7_training(
    *,
    training_manifest_path: Path = DEFAULT_TRAINING_MANIFEST_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    candidate_root: Path = DEFAULT_CANDIDATE_ROOT,
    videos_root: Path = DEFAULT_VIDEOS_ROOT,
    use_runpod: bool = False,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-manifest-path", type=Path, default=DEFAULT_TRAINING_MANIFEST_PATH)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--videos-root", type=Path, default=DEFAULT_VIDEOS_ROOT)
    parser.add_argument("--use-runpod", action="store_true")
    return parser.parse_args()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
