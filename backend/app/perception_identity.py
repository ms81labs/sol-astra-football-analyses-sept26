"""C05 input provenance for the existing interleaved detector/tracker pipeline.

These keys describe inputs, not cached primary detections: the retained rows also
contain recovery and projection. No model is loaded or downloaded to make a key.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import yaml

from .domain_types import Interval
from .workbench.cache import DetectionIdentity, TrackingIdentity
from .workbench.hashing import stream_sha256


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _file_digest(path) -> str | None:
    if path is None:
        return None
    try:
        return stream_sha256(Path(path)).sha256
    except (OSError, ValueError):
        return None


def _detector_defaults() -> str | None:
    try:
        path = Path(importlib.metadata.distribution("ultralytics").locate_file("ultralytics/cfg/default.yaml"))
        defaults = yaml.safe_load(path.read_text(encoding="utf-8"))
        return canonical_digest(defaults) if isinstance(defaults, dict) else None
    except (OSError, ValueError, TypeError, yaml.YAMLError, importlib.metadata.PackageNotFoundError):
        return None


def _reference_digest(path, *, project_relative=False):
    value = Path(path).expanduser()
    if project_relative and not value.is_absolute():
        value = Path(__file__).parents[2] / value
    return _file_digest(value)


def _bind_references(value):
    # These are real profile fields consumed by the producer's seed/audit loaders.
    if isinstance(value, dict):
        return {k: (_reference_digest(v, project_relative=True) if v else "disabled")
                if k.endswith("Path") and isinstance(v, str) else _bind_references(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_bind_references(v) for v in value]
    return value


def _tracker_config(path: Path | None):
    if path is None:
        # Match check_yaml's explicit-path-first resolution. If the installed
        # package cannot be resolved, do not substitute a filename for contents.
        path = Path("botsort.yaml")
        if not path.is_file():
            try:
                path = Path(importlib.metadata.distribution("ultralytics").locate_file(
                    "ultralytics/cfg/trackers/botsort.yaml"))
            except importlib.metadata.PackageNotFoundError:
                return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("tracker_type") != "botsort":
            return None
        if value.get("with_reid") is True and value.get("model") not in {None, "auto"}:
            reid = _file_digest(Path(value["model"]).expanduser())
            if reid is None:
                return None
            value["model"] = {"sha256": reid}
        return canonical_digest({"config": value, "persist": True,
            "reset": "new_source", "temporalPolicy": "source_global_grid"})
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return None


def capture_inputs(source: Path, *, model_path: str | None, tracker_path: Path | None = None,
                   auxiliary_ball_model_path: str | None = None, auxiliary_profile: str | None = None,
                   seed_paths: dict | None = None, acquisition_mode: str = "anchored_player_ranked_context_960",
                   repair_profile: str | None = None, geometry: dict | None = None) -> dict:
    """Snapshot actual determining inputs before/after producer execution."""
    from backend import run_guerilla as producer
    from .edge_share_repair_profiles import get_source_edge_share_repair_config
    repair = get_source_edge_share_repair_config(repair_profile)
    # None has an explicit semantic meaning only for optional/disabled inputs.
    seeds = {name: _reference_digest(path, project_relative=name in {"truth", "reviewed"}) if path else "disabled"
             for name, path in sorted((seed_paths or {}).items())}
    primary = {"source": _file_digest(source), "weights": _file_digest(model_path),
        "preprocessing": {"imgsz": producer.TRACKING_IMGSZ, "confidence": producer.TRACKING_CONF,
            "acquisition": acquisition_mode, "pixelOrder": "bgr", "targetFps": producer.TARGET_FPS,
            "producerSource": _file_digest(Path(producer.__file__)),
            "decoderSource": _file_digest(Path(__file__).parent / "workbench/media.py"),
            "libraryDefaults": _detector_defaults()},
        "classes": producer.detector_tracking_class_ids(producer.DETECTOR_PROFILE_COCO_TRACKING_FULL)}
    try:
        auxiliary = producer.detector_profile_spec(auxiliary_profile) if auxiliary_ball_model_path else "disabled"
    except ValueError:
        auxiliary = None
    recovery = {"sourceClipId": source.name, "auxiliaryWeights": _file_digest(auxiliary_ball_model_path) if auxiliary_ball_model_path else "disabled",
        "auxiliaryProfile": auxiliary,
        "repair": _bind_references(repair) if repair_profile else "disabled", "seeds": seeds,
        "geometry": geometry,
        "algorithms": {name: _file_digest(Path(__file__).parents[1] / name) for name in
            ("pitch_detector.py", "app/homography_utils.py", "app/edge_share_repair.py")},
        "ownerDistance": producer.MAX_OWNER_DISTANCE}
    return {"primary": primary, "tracker": _tracker_config(tracker_path), "recovery": recovery}


def _complete(value):
    if value is None:
        return False
    if isinstance(value, dict):
        return all(_complete(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(_complete(v) for v in value)
    return True


def envelope(digest: str | None, components: dict, reasons=()) -> dict:
    return {"digest": digest, "reusable": digest is not None, "components": components,
            "reasonCodes": list(reasons) if digest is None else []}


def layered_identities(before: dict, after: dict, payload: dict, source_clock: dict,
                       *, runtime_build: str | None) -> dict:
    primary = before["primary"]
    primary_stable = primary == after["primary"]
    tracker_stable = before["tracker"] == after["tracker"]
    recovery_stable = before["recovery"] == after["recovery"]
    anchors = payload.get("decodeAnchors", {})
    interval = None
    try:
        start, end = anchors.get("beginning"), anchors.get("end")
        if type(start) in (int, float) and type(end) in (int, float):
            interval = Interval(start=start, end=end)
    except (TypeError, ValueError):
        pass
    # The source probe and byte snapshot must describe the same asset.
    source = primary["source"] if primary["source"] == source_clock.get("sourceSha256") else None
    selection = {key: source_clock.get(key) for key in
        ("timeBaseNum", "timeBaseDen", "rotation", "frameCount", "nominalFps")}
    detection = DetectionIdentity(source_sha256=source, stream_index=0, interval=interval,
        weights_sha256=primary["weights"],
        preprocessing_id=canonical_digest({"config": primary["preprocessing"], "selection": selection})
            if _complete(primary["preprocessing"]) and _complete(selection) else None,
        class_map_id=canonical_digest(primary["classes"]), precision=payload.get("precision"),
        runtime_build=runtime_build if primary_stable else None)
    tracking = TrackingIdentity(detection, before["tracker"] if tracker_stable else None)
    observation_components = {"schemaVersion": 1, "kind": "combined_projected_observations",
        "tracking": tracking.digest(), "recovery": before["recovery"],
        "outputSchema": "guerilla_source_rows_v1"}
    observation_digest = (canonical_digest(observation_components)
        if tracking.reusable and recovery_stable and _complete(before["recovery"]) else None)
    return {
        "detectionIdentity": envelope(detection.digest(), detection.components(),
            ["INPUT_IDENTITY_INCOMPLETE"] if primary_stable else ["INPUT_CHANGED_DURING_EXECUTION"]),
        "trackingIdentity": envelope(tracking.digest(), tracking.components(),
            ["INPUT_IDENTITY_INCOMPLETE"] if tracker_stable and primary_stable else ["INPUT_CHANGED_DURING_EXECUTION"]),
        "observationIdentity": envelope(observation_digest, observation_components,
            ["INPUT_IDENTITY_INCOMPLETE"] if primary_stable and tracker_stable and recovery_stable
            else ["INPUT_CHANGED_DURING_EXECUTION"]),
    }
