from __future__ import annotations

import importlib.metadata
from pathlib import Path

from .schemas import MatchConfig
from .workbench.cache import recompute_plan
from .workbench.geometry import ground_contact_point, project_to_pitch
from .workbench.media import FrameSource, OpenCvFrameSource, decode_memory_policy, vid_stride_policy
from .workbench.hashing import HashCache

# Exposed at module level so tests can patch this name directly.
from backend.run_guerilla import TARGET_FPS, process_video as _process_video_impl


def _probe_source_clock(video_path: Path, frame_source: FrameSource | None) -> dict[str, object]:
    adapter = frame_source or OpenCvFrameSource()
    try:
        identity = adapter.probe(video_path)
        return identity.model_dump(mode="json")
    except Exception as exc:
        return {
            "sourceSha256": "",
            "byteSize": 0,
            "decodeErrors": ["probe_unavailable", type(exc).__name__],
        }


def process_video_input(
    video_path: Path,
    config: MatchConfig,
    *,
    model_path: str | None = None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
    progress_callback=None,
    match_id: str | None = None,
    job_id: str | None = None,
    primary_acquisition_mode: str = "anchored_player_ranked_context_960",
    frame_source: FrameSource | None = None,
    hash_cache: HashCache | None = None,
) -> dict[str, object]:
    if hash_cache is None and video_path.parent.name == "uploads":
        hash_cache = HashCache(video_path.parent.parent)
    adapter = frame_source or OpenCvFrameSource(hash_cache=hash_cache)
    if config.autoHomography:
        # Auto-detect: backend tries pitch_detector.py first, fallback to manual
        homography_points = None
        auto_homography = True
    elif len(config.manualHomographyPoints) == 4:
        homography_points = [[point.x, point.y] for point in config.manualHomographyPoints]
        auto_homography = False
    else:
        raise RuntimeError(
            f"manualHomographyPoints must contain exactly 4 points (got {len(config.manualHomographyPoints)}). "
            "Set autoHomography=True to use automatic pitch detection instead."
        )

    from .perception_identity import capture_inputs
    identity_args = dict(model_path=primary_model_path or model_path or "yolov10n.pt",
        auxiliary_ball_model_path=auxiliary_ball_model_path, auxiliary_profile=auxiliary_ball_model_profile,
        repair_profile=edge_share_repair_profile, acquisition_mode=primary_acquisition_mode,
        seed_paths={"baseline": baseline_guided_rescue_reference_path,
                    "truth": proposal_selection_truth_seed_path, "reviewed": reviewed_positive_anchor_seed_path},
        geometry={"auto": auto_homography, "manual": homography_points or []})
    before_inputs = capture_inputs(Path(video_path), **identity_args)
    result = _process_video_impl(
        str(video_path),
        output_parquet=None,
        model_path=model_path or "yolov10n.pt",
        primary_model_path=primary_model_path,
        primary_acquisition_mode=primary_acquisition_mode,
        auxiliary_ball_model_path=auxiliary_ball_model_path,
        auxiliary_ball_model_profile=auxiliary_ball_model_profile,
        edge_share_repair_profile=edge_share_repair_profile,
        baseline_guided_rescue_reference_path=baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
        homography_points=homography_points,
        return_rows=True,
        auto_homography=auto_homography,
        progress_callback=progress_callback,
        match_id=match_id,
        job_id=job_id,
        frame_source=adapter,
    )
    if not result:
        raise RuntimeError("Video pipeline did not return any tracking rows.")
    payload = result if isinstance(result, dict) else {"rows": result, "trackColors": {}}
    validate_producer_receipt(payload)
    source_clock = _probe_source_clock(Path(video_path), adapter)
    payload["sourceClock"] = source_clock
    identities = _layered_identities(
        payload,
        source_clock=source_clock,
        adapter=adapter,
        model_path=primary_model_path or model_path,
        hash_cache=hash_cache,
        before_inputs=before_inputs, after_inputs=capture_inputs(Path(video_path), **identity_args),
    )
    payload["detectionIdentity"] = identities["detectionIdentity"]
    payload["trackingIdentity"] = identities["trackingIdentity"]
    payload["observationIdentity"] = identities["observationIdentity"]
    payload["policy"] = declared_sampling_policy(source_clock, adapter)
    payload.setdefault(
        "hardware",
        {"declaredBackend": payload["policy"]["requestedBackend"], "observedDevice": None},
    )
    payload.setdefault("exportFpsEqualsInferenceFps", False)
    payload.setdefault("vidStridePolicy", vid_stride_policy())
    payload.setdefault(
        "projectionPolicy",
        {"playerAnchor": "ground_contact", "boxCentreIsFoot": False, "aerialBallMeasuredGroundLocation": False},
    )
    payload.setdefault(
        "decodeMemoryPolicy",
        decode_memory_policy(
            mode="offline",
            hardware_decode_ok=False,
            cuda_visible=False,
            video_engine_capability=False,
        ),
    )
    rows = payload.get("rows")
    if isinstance(rows, list):
        payload["rows"] = project_detected_rows(rows)
        payload["tracks"] = associate_projected_rows(payload["rows"], cut_detected=False)
    return payload


def declared_sampling_policy(source_clock: dict[str, object], adapter: FrameSource) -> dict[str, object]:
    nominal = source_clock.get("nominalFps")
    try:
        nominal_fps = float(nominal) if nominal not in {None, ""} else None
    except (TypeError, ValueError):
        nominal_fps = None
    interval = 1
    if nominal_fps and nominal_fps > TARGET_FPS:
        interval = int(nominal_fps / TARGET_FPS)
    return {
        "targetFps": float(TARGET_FPS),
        "frameInterval": interval,
        "temporalPolicy": "source_global_grid",
        "requestedBackend": f"{getattr(adapter, 'name', 'opencv')}+ultralytics_track",
    }


def validate_producer_receipt(payload: dict[str, object]) -> None:
    rates = payload.get("fourRates")
    required = (
        "decodeCount",
        "detectorPrimaryCount",
        "detectorRecoveryCount",
        "trackerUpdateCount",
        "exportCount",
    )
    if not isinstance(rates, dict) or any(type(rates.get(key)) is not int for key in required):
        raise RuntimeError("producer fourRates receipt is missing integer invocation counts")


def _layered_identities(
    payload: dict[str, object],
    *,
    source_clock: dict[str, object],
    adapter: FrameSource,
    model_path: str | None,
    hash_cache: HashCache | None,
    before_inputs: dict | None = None, after_inputs: dict | None = None,
) -> dict[str, object]:
    versions: list[str] = []
    runtime_known = True
    for package in ("ultralytics", "torch"):
        try:
            versions.append(f"{package}-{importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            runtime_known = False
    decoder_build = getattr(adapter, "runtime_build", None)
    if decoder_build is None and getattr(adapter, "name", None) == "opencv":
        try:
            decoder_build = f"opencv-{adapter._cv().__version__}"  # type: ignore[attr-defined]
        except (AttributeError, ImportError):
            runtime_known = False
    if not isinstance(decoder_build, str) or not decoder_build:
        runtime_known = False
    from .perception_identity import layered_identities
    incomplete = {"primary": {"source": None, "weights": None, "preprocessing": {}, "classes": []},
                  "tracker": None, "recovery": {"inputs": None}}
    return layered_identities(before_inputs or incomplete, after_inputs or incomplete,
        payload, source_clock, runtime_build=f"{decoder_build}|{'|'.join(versions)}" if runtime_known else None)


def project_detected_rows(rows: list[dict]) -> list[dict]:
    projected: list[dict] = []
    for row in rows:
        item = dict(row)
        kind = str(item.get("kind") or item.get("Entity_Type") or "").lower()
        box = _bbox_from_row(item)
        airborne = bool(item.get("airborne"))
        if box is not None:
            if kind == "ball" and airborne:
                item.update(project_to_pitch(kind="ball", airborne=True, bbox=box))
            elif kind in {"player", "person"}:
                contact = ground_contact_point(box)
                item.update(contact)
                item["kind"] = "player"
        projected.append(item)
    return projected


def _bbox_from_row(item: dict) -> tuple[float, float, float, float] | None:
    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if all(item.get(key) is not None for key in keys):
        return (
            float(item["Source_X1"]),
            float(item["Source_Y1"]),
            float(item["Source_X2"]),
            float(item["Source_Y2"]),
        )
    return None


def associate_projected_rows(
    rows: list[dict],
    *,
    cut_detected: bool = False,
    broadcast_replay: bool = False,
) -> list[dict]:
    tracks: list[dict] = []
    for row in rows:
        box = _bbox_from_row(row)
        if box is None:
            continue
        raw_kind = str(row.get("kind") or row.get("Entity_Type") or "other").lower()
        kind = "player" if raw_kind in {"player", "person"} else ("ball" if raw_kind == "ball" else "other")
        identity = row.get("Track_ID", row.get("trackId"))
        tracks.append(
            {
                "frameId": int(row.get("Frame_ID") or 0),
                "trackId": "unassigned" if identity is None or int(identity) < 0 else str(identity),
                "bbox": box,
                "kind": kind,
                "observationSource": row.get("observationSource", "observed"),
                "reset": bool(cut_detected or broadcast_replay),
                "silentlyReconnected": False,
                "productionPath": "botsort",
            }
        )
    return tracks


IMAGE_SPACE_SAFE_CHANGES = {"report", "calibration", "team_mapping", "track_edit", "ownership"}


def reprocess_for_change(
    *,
    change: str,
    previous_identity: str | None,
    current_identity: str,
    vision,
) -> dict[str, object]:
    plan = recompute_plan(
        previous_identity=previous_identity,
        current_identity=current_identity,
        change=change,
    )
    if change in IMAGE_SPACE_SAFE_CHANGES:
        # Compatibility planner has no artifact reader. Only Storage's canonical
        # materializer can report an executed, verified observation reuse.
        return {
            "kind": "plan", "visionInvoked": False, "rebuild": list(plan["rebuild"]),
            "reused": False, "imageSpaceDetectionsReused": False,
            "reason": "verified_observations_required",
        }
    # Equal keys alone never demonstrate an artifact hit.
    payload = vision()
    if not isinstance(payload, dict):
        payload = {"rows": payload}
    payload["visionInvoked"] = True
    payload["rebuild"] = list(plan["rebuild"])
    payload["reused"] = False
    payload["imageSpaceDetectionsReused"] = False
    return payload
