"""Shared runtime pilot evaluation; research command entry points remain separate."""
from __future__ import annotations
import importlib.util
import io
import math
from pathlib import Path
import subprocess
import sys
from contextlib import redirect_stdout
from typing import Mapping, Sequence
import numpy as np
from scipy.optimize import linear_sum_assignment

TRACKEVAL_COMMIT = "12c8791b303e0a0b50f753af204249e622d0281a"


def evaluation_frame_ids(task: Mapping[str, object], protocol: Mapping[str, object]) -> list[int]:
    frame_rule = protocol["evaluationFrames"]
    if not isinstance(frame_rule, Mapping):
        raise ValueError("evaluationFrames must be an object")
    fps = float(task["sourceFps"])
    target_fps = int(frame_rule["targetFps"])
    if not math.isfinite(fps) or fps <= 0 or target_fps <= 0:
        raise ValueError("sourceFps and targetFps must be positive")
    step = max(1, math.floor(fps / target_fps))
    start = int(task["sourceStartFrame"])
    end = int(task["sourceEndFrameExclusive"])
    selected = [frame_id for frame_id in range(start, end) if frame_id % step == 0]
    if task.get("evaluationFrameStep") != step or task.get("evaluationFrameCount") != len(selected):
        raise ValueError("task evaluation frame cadence does not match the frozen protocol")
    return selected


def _iou(left: Sequence[float], right: Sequence[float]) -> float:
    intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _prediction_bbox(row: Mapping[str, object]) -> tuple[float, float, float, float]:
    values = tuple(float(row[key]) for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2"))
    if any(not math.isfinite(value) for value in values) or values[0] >= values[2] or values[1] >= values[3]:
        raise ValueError("prediction bbox is invalid")
    return values


def _prediction_kind(row: Mapping[str, object]) -> str | None:
    entity_type = row.get("Entity_Type")
    if entity_type == "referee":
        return "referee"
    if entity_type in {"player", "my_team", "enemy", "home", "away"}:
        return "player"
    return None


def build_trackeval_sequence_data(
    task: Mapping[str, object],
    labels: Mapping[str, object],
    prediction_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
) -> dict[str, object]:
    frames = labels.get("frames")
    if not isinstance(frames, list):
        raise ValueError("labels must contain frames")
    selected = evaluation_frame_ids(task, protocol)
    labels_by_frame = {int(frame["frameId"]): frame for frame in frames if isinstance(frame, Mapping)}
    predictions_by_frame: dict[int, list[Mapping[str, object]]] = {}
    for row in prediction_rows:
        if _prediction_kind(row) is not None and int(row["Frame_ID"]) in selected:
            predictions_by_frame.setdefault(int(row["Frame_ID"]), []).append(row)
    truth_keys = sorted(
        {
            (str(entity["kind"]), str(entity["trackId"]))
            for frame in frames
            if isinstance(frame, Mapping) and int(frame["frameId"]) in selected
            for entity in frame.get("entities", [])
        }
    )
    prediction_keys = sorted(
        {
            (_prediction_kind(row), str(row["Track_ID"]) if int(row["Track_ID"]) >= 0 else f"untracked-{frame_id}-{index}")
            for frame_id, rows in predictions_by_frame.items()
            for index, row in enumerate(rows)
        }
    )
    truth_ids = {key: index for index, key in enumerate(truth_keys)}
    prediction_ids = {key: index for index, key in enumerate(prediction_keys)}
    gt_ids: list[np.ndarray] = []
    tracker_ids: list[np.ndarray] = []
    similarities: list[np.ndarray] = []
    for frame_id in selected:
        frame = labels_by_frame.get(frame_id)
        if not isinstance(frame, Mapping) or not isinstance(frame.get("entities"), list):
            raise ValueError(f"label frame {frame_id} is missing entity truth")
        truth = frame["entities"]
        predictions = predictions_by_frame.get(frame_id, [])
        gt_ids.append(np.asarray([truth_ids[(str(entity["kind"]), str(entity["trackId"]))] for entity in truth], dtype=int))
        tracker_ids.append(
            np.asarray(
                [
                    prediction_ids[
                        (
                            _prediction_kind(row),
                            str(row["Track_ID"]) if int(row["Track_ID"]) >= 0 else f"untracked-{frame_id}-{index}",
                        )
                    ]
                    for index, row in enumerate(predictions)
                ],
                dtype=int,
            )
        )
        similarities.append(
            np.asarray(
                [
                    [
                        _iou(entity["bbox"], _prediction_bbox(row))  # type: ignore[arg-type]
                        if entity["kind"] == _prediction_kind(row)
                        else 0.0
                        for row in predictions
                    ]
                    for entity in truth
                ],
                dtype=float,
            ).reshape((len(truth), len(predictions)))
        )
    return {
        "num_timesteps": len(selected),
        "num_gt_dets": sum(len(ids) for ids in gt_ids),
        "num_tracker_dets": sum(len(ids) for ids in tracker_ids),
        "num_gt_ids": len(truth_ids),
        "num_tracker_ids": len(prediction_ids),
        "gt_ids": gt_ids,
        "tracker_ids": tracker_ids,
        "similarity_scores": similarities,
    }


def _longest_tracking_gap(data: Mapping[str, object], threshold: float = 0.5) -> int:
    current = np.zeros(int(data["num_gt_ids"]), dtype=int)
    longest = 0
    for gt_ids, tracker_ids, similarity in zip(data["gt_ids"], data["tracker_ids"], data["similarity_scores"], strict=False):  # type: ignore[arg-type]
        present = set(gt_ids.tolist())
        matched: set[int] = set()
        if len(gt_ids) and len(tracker_ids):
            truth_indices, prediction_indices = linear_sum_assignment(-similarity)
            matched = {
                int(gt_ids[truth_index])
                for truth_index, prediction_index in zip(truth_indices, prediction_indices, strict=False)
                if similarity[truth_index, prediction_index] >= threshold
            }
        for truth_id in range(len(current)):
            current[truth_id] = current[truth_id] + 1 if truth_id in present and truth_id not in matched else 0
        longest = max(longest, int(current.max(initial=0)))
    return longest


def evaluate_tracking(data: Mapping[str, object], *, trackeval_root: Path) -> dict[str, object]:
    result = subprocess.run(
        ["git", "-C", str(trackeval_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode or result.stdout.strip() != TRACKEVAL_COMMIT:
        raise ValueError(f"trackeval_root must be the pinned TrackEval commit {TRACKEVAL_COMMIT}")
    trackeval_root = Path(trackeval_root).resolve()
    package_root = trackeval_root / "trackeval"
    init_path = package_root / "__init__.py"
    existing = sys.modules.get("trackeval")
    if existing is not None:
        module_file = getattr(existing, "__file__", None)
        if module_file is None or not Path(module_file).resolve().is_relative_to(trackeval_root):
            raise ValueError("a different TrackEval package is already imported")
        trackeval = existing
    else:
        spec = importlib.util.spec_from_file_location(
            "trackeval",
            init_path,
            submodule_search_locations=[str(package_root)],
        )
        if spec is None or spec.loader is None:
            raise ValueError("unable to load pinned TrackEval package")
        trackeval = importlib.util.module_from_spec(spec)
        sys.modules["trackeval"] = trackeval
        try:
            with redirect_stdout(io.StringIO()):
                spec.loader.exec_module(trackeval)
        except Exception:
            sys.modules.pop("trackeval", None)
            raise
    if not Path(trackeval.__file__).resolve().is_relative_to(trackeval_root):
        raise ValueError("a different TrackEval package is already imported")
    # TrackEval's pinned revision predates NumPy 1.24 alias removals.
    if not hasattr(np, "float"):
        np.float = float  # type: ignore[attr-defined]
    if not hasattr(np, "int"):
        np.int = int  # type: ignore[attr-defined]
    hota = trackeval.metrics.HOTA().eval_sequence(data)
    identity = trackeval.metrics.Identity({"THRESHOLD": 0.5, "PRINT_CONFIG": False}).eval_sequence(data)
    clear = trackeval.metrics.CLEAR({"THRESHOLD": 0.5, "PRINT_CONFIG": False}).eval_sequence(data)
    return {
        "trackEvalCommit": TRACKEVAL_COMMIT,
        "HOTA": float(np.mean(hota["HOTA"])),
        "DetA": float(np.mean(hota["DetA"])),
        "AssA": float(np.mean(hota["AssA"])),
        "IDF1": float(identity["IDF1"]),
        "identitySwitches": int(clear["IDSW"]),
        "longestTrackGapFrames": _longest_tracking_gap(data),
    }
