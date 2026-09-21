"""Leftover contract POST handlers, isolated from the production /api surface."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi import FastAPI

from ..schemas import MatchRecord
from ..storage import Storage
from .access import object_access_decision
from .leftover_http import leftover_http_enabled
from .recovery import support_bundle

import json

from .leftover_support import (
    _as_bytes,
    _as_detection,
    _as_label,
    _challenger_adapters_view,
    _decoder_challengers_view,
    _four_rates_view,
    _legacy_geometry,
    _legacy_geometry_profile,
    _production_decode_frames,
    _production_job_request,
    _stale_permissions_view,
    _unmeasured_landmark_preview,
    _unpromoted_receipt,
)
from ..ai_policy import (
    ground_output,
    select_evidence,
)
from .access import (
    authorize_object,
    mint_sharing_link,
    signed_scoped_object_access,
    upload_quota,
)
from .adoption import (
    dependency_register,
)
from .artifacts import (
    import_worker_output,
)
from .assistance import (
    json_repair_chain,
    network_failure_preserves_unknown,
    policy_log,
    template_report,
)
from .benchmarks import (
    experiment_receipt,
    quality_gate_holds,
)
from .cache import (
    recompute_plan,
)
from .contracts import (
    migrate_legacy_zero,
    SourceClockIdentity,
)
from .costs import (
    deployment_choice,
)
from .dossier import (
    build_baseline_dossier,
    build_release_dossier,
)
from .evaluation import (
    analyst_workflow_measures,
    current_repository_evaluation_gate,
    evaluate_protocol_prerequisites,
)
from .events import (
    ownership_invalidation,
    propose_event,
    score_events,
)
from .evidence import (
    DEFINITION_VERSION,
    evaluate_metric_spec,
)
from .flags import (
    feature_enabled,
)
from .geometry import (
    CalibrationProfile,
    detect_zoom_or_cut,
    evaluate_landmarks,
    ground_contact_point,
    project_to_pitch,
)
from .identity import (
    cluster_mapping,
    IdentityRecord,
    promote_identity,
)
from .jobs import (
    cleanup_failure_is_complete,
    pause_experiment,
    worker_environment,
)
from .media import (
    align_clip_start_to_grid,
    apply_crop_and_rotation,
    colour_round_trip,
    cpu_fallback,
    DecodedFrame,
    detect_camera_cuts,
    FfmpegFrameSource,
    FfmpegProbe,
    frame_interval_for_target_fps,
    map_decoded_to_sample,
    map_original_to_proxy_pts,
    pixels_from_decoded_frame,
    pts_to_seconds,
    resolve_declared_interval,
    sample_decode_anchors,
    torso_colour_pixels,
    wrap_decoded_frame,
)
from .ownership import (
    OwnershipHysteresis,
    possession_from_states,
)
from .perception import (
    DetectorAdapter,
    IdentityRepair,
    IouAssociationFallback,
    merge_tiled_detections,
    PreprocessPlan,
    preview_identity_change,
    score_detections,
    score_detections_by_stratum,
    separate_ball_states,
    tile_to_source,
)
from .providers import (
    cloud_adapter,
    local_adapter,
    provider_roster,
)
from .quantities import (
    heatmap_availability,
    split_scores,
)
from .reports import (
    assemble_report,
)
from .research import (
    execute_track,
    may_write_product_paths,
)
from .roster import (
    promotion_gate,
)
from .training import (
    admit_example,
    experiment_cycle,
    experiment_ledger,
    promote_candidate,
    pseudo_label,
)

def create_leftover_post_router(storage: Storage) -> APIRouter:
    router = APIRouter()

    def require_match(
        match_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> MatchRecord:
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        decision = object_access_decision(
            object_id=match.id,
            object_tenant=match.config.rights.audience,
            authorization=authorization,
            object_scope=x_object_scope,
            deployment_boundary=x_deployment_boundary,
            client_tenant=x_tenant_id,
        )
        if not decision["allowed"]:
            raise HTTPException(status_code=403, detail=decision)
        return match

    @router.post("/evaluation/workflow")
    def post_evaluation_workflow(payload: dict | None = None) -> dict:
        del payload
        return analyst_workflow_measures()

    @router.post("/evaluation/protocol")
    def post_evaluation_protocol(payload: dict | None = None) -> dict:
        del payload
        return current_repository_evaluation_gate().model_dump(mode="json")

    @router.post("/evaluation/prerequisites")
    def post_evaluation_prerequisites(payload: dict | None = None) -> dict:
        del payload
        return evaluate_protocol_prerequisites(
            complete_tasks=0,
            complete_minutes=0.0,
            locked_labels_present=False,
            native_predictions_present=False,
            team_declarations_present=False,
            scorer_replayable=True,
        ).model_dump(mode="json")

    @router.post("/research/tracks/{track_id:path}/execute")
    def post_research_track(track_id: str) -> dict:
        if track_id.endswith("/execute"):
            track_id = track_id[: -len("/execute")]
        return execute_track(track_id, in_production=True)

    @router.post("/providers")
    def post_providers(payload: dict | None = None) -> dict:
        del payload
        return {
            "roster": provider_roster(),
            "local": local_adapter(enabled=False),
            "cloud": cloud_adapter(enabled=False),
        }

    @router.post("/dependencies")
    def post_dependencies(payload: dict | None = None) -> dict:
        del payload
        return dependency_register()

    @router.post("/roster/promotion/{task}")
    def post_roster_promotion(task: str, payload: dict | None = None) -> dict:
        del payload
        return promotion_gate(task=task, independent_accepted=False, licence_recorded=False)

    @router.post("/support/bundle")
    def post_support_bundle(payload: dict | None = None) -> dict:
        del payload
        payload = support_bundle(consented=False, ttl_seconds=0.0, now=0.0)
        return {key: value for key, value in payload.items() if key != "expired"}

    @router.post("/geometry/contact")
    def post_geometry_contact(payload: dict | None = None) -> dict:
        body = payload or {}
        raw = body.get("bbox") or [0.0, 0.0, 10.0, 20.0]
        bbox = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        kind = str(body.get("kind") or "player")
        airborne = bool(body.get("airborne"))
        if kind == "ball" or airborne:
            return project_to_pitch(kind=kind if kind in {"player", "ball"} else "player", airborne=airborne, bbox=bbox)
        contact = ground_contact_point(bbox)
        return {**contact, "kind": kind, "airborne": False, "measuredGroundLocation": True, "reasonCodes": []}

    @router.post("/geometry/legacy")
    def post_geometry_legacy(payload: dict | None = None) -> dict:
        body = payload or {}
        return _legacy_geometry(list(body.get("points") or []))

    @router.post("/geometry/landmarks")
    def post_geometry_landmarks(payload: dict | None = None) -> dict:
        del payload
        return evaluate_landmarks(_legacy_geometry_profile(), max_p95_m=3.0)

    @router.post("/geometry/preview")
    def post_geometry_preview(payload: dict | None = None) -> dict:
        del payload
        return _unmeasured_landmark_preview()

    @router.post("/geometry/zoom-cut")
    def post_geometry_zoom_cut(payload: dict | None = None) -> dict:
        del payload
        identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        shifted = [[1.4, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        previous = CalibrationProfile(calibrationId="prev", cameraModel="planar_homography", homography=identity)
        current = CalibrationProfile(calibrationId="curr", cameraModel="planar_homography", homography=shifted)
        return {"changed": detect_zoom_or_cut(previous, current)}

    @router.post("/metrics/network-failure")
    def post_network_failure(payload: dict | None = None) -> dict:
        del payload
        return network_failure_preserves_unknown(metric_value=None, generated_number=0.0)

    @router.post("/assistance/repair")
    def post_json_repair(payload: dict | None = None) -> dict:
        del payload
        return json_repair_chain(attempts=2, max_repair=1)

    @router.post("/assistance/policy")
    def post_assistance_policy(payload: dict | None = None) -> dict:
        del payload
        return policy_log(route="template", evidence_hash="", secret="")

    @router.post("/experiments/quality-gate")
    def post_quality_gate(payload: dict | None = None) -> dict:
        body = payload or {}
        original = float(body.get("originalThreshold") or 0.8)
        proposed = float(body.get("proposedThreshold") or original)
        return quality_gate_holds(
            faster=bool(body.get("faster")),
            quality_passed=False,
            viewed_results=bool(body.get("viewedResults")),
            original_threshold=original,
            proposed_threshold=proposed,
        )

    @router.post("/experiments/{experiment}")
    def post_experiment(experiment: str, payload: dict | None = None) -> dict:
        del payload
        return experiment_receipt(experiment, hardware_verified=False, bottleneck_documented=False).model_dump(mode="json")

    @router.post("/identity/promote")
    def post_identity_promote(payload: dict | None = None) -> dict:
        body = payload or {}
        record = IdentityRecord(kind="tracklet", trackId=str(body.get("trackId") or "t-0"))
        return promote_identity(record, target="roster_player", reviewed=False, rosterId=None).model_dump(mode="json")

    @router.post("/identity/clusters/{cluster_id}")
    def post_identity_cluster(cluster_id: int, payload: dict | None = None) -> dict:
        del payload
        return cluster_mapping(cluster_id=cluster_id, selected_semantic=None).model_dump(mode="json")

    @router.post("/pause")
    def post_pause_experiment(payload: dict | None = None) -> dict:
        del payload
        return {"paused": pause_experiment(remaining=1_000_000.0, termination_and_recovery=0.0)}

    @router.post("/quota")
    def post_upload_quota(payload: dict | None = None) -> dict:
        body = payload or {}
        return upload_quota(
            byte_size=int(body.get("byteSize") or 0),
            duration_seconds=float(body.get("durationSeconds") or 0),
        )

    @router.post("/worker/import")
    def post_worker_import(payload: dict | None = None) -> dict:
        body = payload or {}
        return import_worker_output(
            {
                "path": str(body.get("path") or ""),
                "bytes": int(body.get("bytes") or 0),
                "kind": str(body.get("kind") or ""),
                "jobSucceeded": bool(body.get("jobSucceeded")),
            },
            quality_accepted=False,
        )

    @router.post("/training/admit")
    def post_training_admit(payload: dict | None = None) -> dict:
        body = payload or {}
        source = str(body.get("sourcePool") or "locked_evaluation")
        destination = str(body.get("destination") or "training")
        return admit_example(
            {"id": str(body.get("id") or ""), "rights": str(body.get("rights") or "")},
            source_pool=source,  # type: ignore[arg-type]
            destination=destination,  # type: ignore[arg-type]
        ).model_dump(mode="json")

    @router.post("/research/paths")
    def post_research_paths(payload: dict | None = None) -> dict:
        body = payload or {}
        return {"allowed": may_write_product_paths(list(body.get("paths") or []))}

    @router.post("/flags/{name}/enabled")
    def post_feature_enabled(name: str, payload: dict | None = None) -> dict:
        del payload
        return {"name": name, "enabled": feature_enabled(name, env={})}

    @router.post("/detector")
    def post_detector(payload: dict | None = None) -> dict:
        body = payload or {}
        return DetectorAdapter().detect(
            {"colourOrder": str(body.get("colourOrder") or "bgr")},
            requested_backend=str(body.get("requestedBackend") or "cuda"),
            video_engine_capability=False,
        )

    @router.post("/perception/tiles")
    def post_perception_tiles(payload: dict | None = None) -> dict:
        body = payload or {}
        origin = body.get("origin") or [0.0, 0.0]
        scale = float(body.get("scale") or 1.0)
        mapped = []
        for item in list(body.get("detections") or []):
            bbox = tile_to_source(tuple(item.get("bbox") or (0, 0, 0, 0)), origin=(float(origin[0]), float(origin[1])), scale=scale)
            mapped.append({**item, "bbox": list(bbox)})
        merged = merge_tiled_detections(mapped, iou_threshold=0.5)
        return {
            "merged": merged,
            "sourceCoordinates": True,
            "productQualityPass": False,
        }

    @router.post("/sharing")
    def post_sharing_link(payload: dict | None = None) -> dict:
        body = payload or {}
        now = float(body.get("now") or 0.0)
        ttl = float(body.get("ttlSeconds") or 0.0)
        link = mint_sharing_link(object_id=str(body.get("objectId") or ""), now=now, ttl_seconds=ttl)
        return {
            "objectId": link["objectId"],
            "expiresAt": link["expiresAt"],
            "expiredAtNow": link["expired"](now),
            "expiredAtTtl": link["expired"](now + ttl),
        }

    @router.post("/media/colour")
    def post_media_colour(payload: dict | None = None) -> dict:
        body = payload or {}
        pixels = _as_bytes(body.get("pixels") or [10, 200, 30])
        order = str(body.get("colourOrder") or "rgb")
        converted = torso_colour_pixels(pixels, colour_order=order, convert=True)  # type: ignore[arg-type]
        source_box = tuple(int(value) for value in (body.get("sourceBox") or [10, 20, 40, 50]))
        crop = tuple(int(value) for value in (body.get("crop") or source_box))
        box = colour_round_trip(source_box=source_box, crop=crop, rotation=0)
        return {
            "pixels": list(converted),
            "sourceBox": list(box),
            "rotationApplied": False,
            "colourOrder": "bgr",
        }

    @router.post("/decode/wrap")
    def post_decode_wrap(payload: dict | None = None) -> dict:
        body = payload or {}
        payload_bytes = _as_bytes(body.get("payload") or [0, 0, 0])
        if len(payload_bytes) < 3:
            payload_bytes = b"\x00\x00\x00"
        frame = DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, payload_bytes, "fixture")
        buffer = wrap_decoded_frame(frame, device="cpu")
        return {
            "device": buffer.device,
            "lifetime": buffer.lifetime,
            "syncRequired": buffer.sync_required,
            "gpuPromoted": False,
        }

    @router.post("/decode/fallback")
    def post_decode_fallback(payload: dict | None = None) -> dict:
        del payload
        return {"selected": cpu_fallback("cuda", {"opencv", "fixture"}), "availableIncludesCuda": False}

    @router.post("/perception/preprocess")
    def post_perception_preprocess(payload: dict | None = None) -> dict:
        body = payload or {}
        result = PreprocessPlan().transform(
            pixels=_as_bytes(body.get("pixels") or [10, 200, 30]),
            width=int(body.get("width") or 1),
            height=int(body.get("height") or 1),
            colour_order=str(body.get("colourOrder") or "rgb"),
        )
        result.pop("pixels", None)
        return result

    @router.post("/perception/score")
    def post_perception_score(payload: dict | None = None) -> dict:
        body = payload or {}
        detections = [_as_detection(item) for item in list(body.get("detections") or [])]
        labels = [_as_label(item) for item in list(body.get("labels") or [])]
        task = str(body.get("task") or "player_coverage")
        receipt = score_detections(
            detections,
            labels,
            task=task,  # type: ignore[arg-type]
            configuration=str(body.get("configuration") or "baseline"),
            labels_independent=False,
        )
        return receipt.model_dump(mode="json")

    @router.post("/perception/stratum")
    def post_perception_stratum(payload: dict | None = None) -> dict:
        body = payload or {}
        detections = [_as_detection(item) for item in list(body.get("detections") or [])]
        labels = [_as_label(item) for item in list(body.get("labels") or [])]
        receipt = score_detections_by_stratum(
            detections,
            labels,
            task=str(body.get("task") or "player_coverage"),  # type: ignore[arg-type]
            configuration=str(body.get("configuration") or "baseline"),
            labels_independent=False,
        )
        return receipt.model_dump(mode="json")

    @router.post("/perception/ball-states")
    def post_perception_ball_states(payload: dict | None = None) -> dict:
        body = payload or {}
        return separate_ball_states(list(body.get("rows") or []))

    @router.post("/identity/preview")
    def post_identity_preview(payload: dict | None = None) -> dict:
        body = payload or {}
        return preview_identity_change(
            kind=str(body.get("kind") or "track_split"),
            track_id=body.get("trackId"),
            at_frame=body.get("atFrame"),
            interval_start=body.get("intervalStart"),
            interval_end=body.get("intervalEnd"),
        )

    @router.post("/tracker")
    def post_tracker_associate(payload: dict | None = None) -> dict:
        body = payload or {}
        detections = [_as_detection(item) for item in list(body.get("detections") or [])]
        tracks = _main.IouAssociationFallback().associate(
            detections,
            cut_detected=bool(body.get("cutDetected")),
            broadcast_replay=bool(body.get("broadcastReplay")),
        )
        return {"tracks": tracks, "silentlyReconnected": False}

    @router.post("/events/propose")
    def post_event_propose(payload: dict | None = None) -> dict:
        body = payload or {}
        event = propose_event(
            family=str(body.get("family") or "pass"),
            release=body.get("release"),
            receipt=body.get("receipt"),
        )
        return event.model_dump(mode="json")

    @router.post("/events/score")
    def post_event_score(payload: dict | None = None) -> dict:
        body = payload or {}
        receipt = score_events(
            predictions=list(body.get("predictions") or []),
            labels=list(body.get("labels") or []),
            labels_independent=False,
        )
        return receipt.model_dump(mode="json")

    @router.post("/cache/recompute")
    def post_cache_recompute(payload: dict | None = None) -> dict:
        del payload
        return recompute_plan(previous_identity="previous", current_identity="current", change="perception")

    @router.post("/training/ledger")
    def post_training_ledger(payload: dict | None = None) -> dict:
        del payload
        ledger = experiment_ledger()
        ledger.append({"run": "exp-1", "config": "baseline"})
        return {"entries": ledger.entries, "promoted": False, "independentGroundTruth": False}

    @router.post("/identity/repair")
    def post_identity_repair(payload: dict | None = None) -> dict:
        body = payload or {}
        preview = preview_identity_change(
            kind=str(body.get("kind") or "track_split"),
            track_id=body.get("trackId"),
            at_frame=body.get("atFrame"),
        )
        repair = IdentityRepair()
        repair.split(str(body.get("trackId") or "t-1"), int(body.get("atFrame") or 0), author="analyst")
        return {**preview, "edits": repair.edits, "committed": False}

    @router.post("/decode/crop")
    def post_decode_crop(payload: dict | None = None) -> dict:
        body = payload or {}
        return apply_crop_and_rotation(
            int(body.get("width") or 1920),
            int(body.get("height") or 1080),
            crop=None,
            rotation=0,
            colour_order="bgr",
        )

    @router.post("/decode/cuts")
    def post_decode_cuts(payload: dict | None = None) -> dict:
        body = payload or {}
        times = [float(item) for item in list(body.get("times") or [])]
        frames = [
            DecodedFrame(index, index, time, 8, 8, "bgr", 0, b"\x00\x00\x00", "fixture")
            for index, time in enumerate(times)
        ]
        return {
            "cuts": detect_camera_cuts(times),
            "anchors": sample_decode_anchors(frames),
        }

    @router.post("/decode/grid")
    def post_decode_grid(payload: dict | None = None) -> dict:
        body = payload or {}
        return align_clip_start_to_grid(
            clip_start_source_frame=int(body.get("clipStartSourceFrame") or 0),
            evaluation_step=int(body.get("evaluationStep") or 1),
        )

    @router.post("/decode/pixels")
    def post_decode_pixels(payload: dict | None = None) -> dict:
        del payload
        payload_bytes = b"\x00\x00\x00"
        base = DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, payload_bytes, "fixture")
        frame = DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, payload_bytes, "fixture", buffer=wrap_decoded_frame(base, device="cpu"))
        pixels = pixels_from_decoded_frame(frame)
        return {"shape": list(pixels.shape), "gpuPromoted": False, "device": "cpu"}

    @router.post("/costs/deployment")
    def post_deployment_choice(payload: dict | None = None) -> dict:
        del payload
        return deployment_choice(privacy_required=True, irregular_usage=False, suitable_local_hardware=True)

    @router.post("/metrics/spec")
    def post_metric_spec(payload: dict | None = None) -> dict:
        body = payload or {}
        metric = evaluate_metric_spec(
            str(body.get("metric") or "my_team_distance_m"),
            value=body.get("value"),
            denominator=float(body.get("denominator") or 0.0),
            identity_continuous=False,
            calibration_accepted=False,
        )
        return metric.model_dump(mode="json")

    @router.post("/access/object")
    def post_authorize_object(payload: dict | None = None) -> dict:
        body = payload or {}
        return authorize_object(
            object_id=str(body.get("objectId") or ""),
            session_tenant="loopback",
            client_tenant=body.get("clientTenant"),
            object_tenant=body.get("objectTenant"),
        )

    @router.post("/decode/sample")
    def post_decode_sample(payload: dict | None = None) -> dict:
        body = payload or {}
        interval = frame_interval_for_target_fps(25.0, 5.0)
        index = int(body.get("sourceFrameIndex") or 0)
        frame = DecodedFrame(index, index, index / 25.0, 8, 8, "bgr", 0, b"\x00\x00\x00", "fixture")
        mapped = map_decoded_to_sample(frame, frame_interval=interval)
        return {
            "exported": mapped is not None,
            "frameInterval": interval,
            "targetFpsEqualsInferenceFps": False,
            "sample": None if mapped is None else mapped.model_dump(mode="json"),
        }

    @router.post("/decode/pts")
    def post_decode_pts(payload: dict | None = None) -> dict:
        body = payload or {}
        return {
            "seconds": pts_to_seconds(
                int(body.get("pts") or 0),
                int(body.get("timeBaseNum") or 1),
                int(body.get("timeBaseDen") or 1),
            )
        }

    @router.post("/decode/proxy-pts")
    def post_decode_proxy_pts(payload: dict | None = None) -> dict:
        body = payload or {}
        original = [int(item) for item in list(body.get("originalPts") or [])]
        proxy = [int(item) for item in list(body.get("proxyPts") or original)]
        time_base = body.get("timeBase") or [1, 1]
        mapping = map_original_to_proxy_pts(
            original_pts=original,
            proxy_pts=proxy,
            time_base=(int(time_base[0]), int(time_base[1])),
        )
        return {"mapping": mapping, "replacesOriginal": False}

    @router.post("/decode/interval")
    def post_decode_interval(payload: dict | None = None) -> dict:
        body = payload or {}
        start, end = resolve_declared_interval(
            str(body.get("kind") or "source"),
            float(body.get("startSeconds") or 0.0),
            float(body.get("endSeconds") or 0.0),
            list(body.get("mapping") or []),
        )
        return {"interval": [start, end]}

    @router.post("/decode/frames")
    def post_decode_frames(payload: dict | None = None) -> dict:
        del payload
        return _production_decode_frames(storage.storage_root)

    @router.post("/decode/first")
    def post_decode_first(payload: dict | None = None) -> dict:
        del payload
        view = _production_decode_frames(storage.storage_root)
        return {
            "backend": view["backend"],
            "sourceFrameIndex": view["firstIndex"],
            "device": view["device"],
            "gpuPromoted": False,
        }

    @router.post("/decode/challengers")
    def post_decode_challengers(payload: dict | None = None) -> dict:
        del payload
        return _decoder_challengers_view(storage.storage_root)

    @router.post("/decode/probe")
    def post_decode_probe(payload: dict | None = None) -> dict:
        del payload
        source = FfmpegFrameSource(
            frames=[],
            identity=SourceClockIdentity(sourceSha256="a" * 64, byteSize=0),
        )
        return {"name": source.name, "default": False, "role": "challenger"}

    @router.post("/decode/export")
    def post_decode_export(payload: dict | None = None) -> dict:
        body = payload or {}
        source_url = str(body.get("sourceUrl") or "http://evil.test/clip.mp4")
        probe = FfmpegProbe()
        try:
            probe.export_clip(
                Path(source_url),
                storage.storage_root / "export-refused.mp4",
                start_seconds=0.0,
                duration_seconds=1.0,
                runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ffmpeg must not run")),
            )
        except ValueError as exc:
            return {"admitted": False, "reasonCodes": [str(exc)]}
        except Exception:
            return {"admitted": False, "reasonCodes": ["UNCONSTRAINED_DECODER"]}
        return {"admitted": False, "reasonCodes": ["FFMPEG_EXPORT_NOT_DEFAULT"]}

    @router.post("/challengers")
    def post_challengers(payload: dict | None = None) -> dict:
        del payload
        return _challenger_adapters_view()

    @router.post("/permissions/stale")
    def post_stale_permissions(payload: dict | None = None) -> dict:
        del payload
        return _stale_permissions_view()

    @router.post("/heatmap")
    def post_heatmap(payload: dict | None = None) -> dict:
        del payload
        return heatmap_availability(identity_continuous=False)

    @router.post("/reports/assemble")
    def post_assemble_report(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("claimedEvidenceIds") or [])
        return assemble_report(
            metrics=[],
            events=[],
            claimed_evidence_ids=claimed,
            known_evidence_ids=set(),
        )

    @router.post("/assistance/ground")
    def post_ground_output(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("evidence") or body.get("claimedEvidenceIds") or [])
        return ground_output({"evidence": claimed}, known_ids=set())

    @router.post("/assistance/select-evidence")
    def post_select_evidence(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("claimedIds") or body.get("claimedEvidenceIds") or [])
        try:
            evidence = select_evidence(claimed, known_ids=set())
        except ValueError:
            return {"accepted": False, "evidence": [], "reasonCodes": ["FABRICATED_EVIDENCE"]}
        return {"accepted": True, "evidence": evidence, "reasonCodes": ["GROUNDED"]}

    @router.post("/metrics/legacy-zero")
    def post_legacy_zero(payload: dict | None = None) -> dict:
        body = payload or {}
        migrated = migrate_legacy_zero(
            str(body.get("metric") or "possession_pct"),
            body.get("value"),
            definition_version=DEFINITION_VERSION,
            measured=False,
            reason_if_unmeasured="UNMEASURED_LEGACY_DEFAULT",
        )
        return migrated.model_dump(mode="json")

    @router.post("/dossier/release")
    def post_release_dossier(payload: dict | None = None) -> dict:
        del payload
        return build_release_dossier(build_baseline_dossier(), loopback_only=True)

    @router.post("/rates/four")
    def post_four_rates(payload: dict | None = None) -> dict:
        del payload
        return _four_rates_view()

    @router.post("/ownership/hysteresis")
    def post_ownership_hysteresis(payload: dict | None = None) -> dict:
        del payload
        hyst = OwnershipHysteresis(min_persistence=3)
        return {"owner": hyst.observe("my_team"), "minPersistence": 3}

    @router.post("/metrics/possession-states")
    def post_possession_states(payload: dict | None = None) -> dict:
        body = payload or {}
        summary = possession_from_states(list(body.get("states") or []), float(body.get("requestedSeconds") or 0.0))
        dumped = summary.model_dump(mode="json")
        dumped["publishedValue"] = summary.published_value()
        return dumped

    @router.post("/reports/template")
    def post_template_report(payload: dict | None = None) -> dict:
        del payload
        return template_report([], [])

    @router.post("/receipts/promotion")
    def post_promotion_receipt(payload: dict | None = None) -> dict:
        del payload
        return _unpromoted_receipt()

    @router.post("/ownership/invalidate")
    def post_ownership_invalidate(payload: dict | None = None) -> dict:
        del payload
        return {"change": "track_edit", "invalidates": ownership_invalidation()}

    @router.post("/quantities/scores")
    def post_split_scores(payload: dict | None = None) -> dict:
        body = payload or {}
        interval = body.get("interval")
        return split_scores(
            detector_score=body.get("detectorScore"),
            calibrated_probability=body.get("calibratedProbability"),
            interval=tuple(interval) if interval else None,
        )

    @router.post("/worker/environment")
    def post_worker_environment(payload: dict | None = None) -> dict:
        del payload
        return worker_environment(_production_job_request(), host_secret="")

    @router.post("/cleanup/complete")
    def post_cleanup_complete(payload: dict | None = None) -> dict:
        del payload
        return {"complete": cleanup_failure_is_complete("failed"), "cleanupResult": "failed"}

    @router.post("/upload/interrupt")
    def post_upload_interrupt(payload: dict | None = None) -> dict:
        del payload
        return storage.interrupted_upload_run()

    @router.post("/access/signed")
    def post_signed_object_access(payload: dict | None = None) -> dict:
        del payload
        return signed_scoped_object_access(token=None, object_id="", token_object_id=None)

    @router.post("/training/cycle")
    def post_training_cycle(payload: dict | None = None) -> dict:
        body = payload or {}
        return experiment_cycle(
            str(body.get("stage") or "diagnose"),
            measurable_failure=False,
            budget_remaining=0.0,
            development_benefit=False,
            gate_regressed=True,
        )

    @router.post("/training/promote")
    def post_training_promote(payload: dict | None = None) -> dict:
        del payload
        return promote_candidate(independent_accepted=False, rollback_artifact=True)

    @router.post("/training/pseudo")
    def post_training_pseudo(payload: dict | None = None) -> dict:
        body = payload or {}
        return pseudo_label(suggestion=str(body.get("suggestion") or ""), human_change=None, approved=False)

    @router.post("/search")
    def post_typed_search(payload: dict | None = None) -> dict:
        body = payload or {}
        match_id = str(body.get("matchId") or "")
        if not match_id:
            raise HTTPException(status_code=400, detail="matchId is required")
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        del match
        result = storage.query_match_events(
            match_id,
            str(body.get("query") or ""),
            include_unknown=body.get("includeUnknown") is True,
        )
        if body.get("strict") is True and result["unsupportedTerms"]:
            raise HTTPException(
                status_code=422,
                detail={"unsupportedTerms": result["unsupportedTerms"], "interpreted": result["interpreted"]},
            )
        return result

    @router.post("/matches/{match_id}/heatmap")
    def post_match_heatmap(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.heatmap_for_match(match.id)

    @router.post("/matches/{match_id}/players")
    def post_match_players(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.player_observations_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @router.post("/matches/{match_id}/ownership")
    def post_match_ownership(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.classify_match_ownership(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @router.post("/matches/{match_id}/package")
    def post_match_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.assemble_stored_match_package(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @router.post("/matches/{match_id}/incidents/geometry")
    def post_match_incident_geometry(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.incident_geometry_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @router.post("/matches/{match_id}/metrics")
    def post_match_metrics(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.match_metrics_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @router.post("/matches/{match_id}/incidents/package")
    def post_match_incident_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.incident_package_for_match(match.id)

    @router.post("/matches/{match_id}/incidents/review")
    def post_match_incident_review(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.incident_review_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @router.post("/matches/{match_id}/assistance/fallback")
    def post_match_assistance_fallback(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.assistance_fallback_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @router.post("/matches/{match_id}/identity")
    def post_match_identity(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.identity_for_match(match.id)

    @router.post("/matches/{match_id}/cache")
    def post_match_cache(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.cache_identity_for_match(match.id)

    @router.post("/matches/{match_id}/records/migrate")
    def post_match_legacy_migrate(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.migrate_legacy_for_match(match.id)

    @router.post("/matches/{match_id}/formation")
    def post_match_formation(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.formation_for_match(match.id)

    @router.post("/matches/{match_id}/events/partition")
    def post_match_event_partition(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.partition_events_for_match(match.id)

    @router.post("/matches/{match_id}/reports/provenance")
    def post_match_report_provenance(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claims")
        claimed_ids: list[str] | None = None
        if isinstance(claimed, list):
            claimed_ids = [
                evidence_id
                for claim in claimed
                if isinstance(claim, dict)
                for evidence_id in (claim.get("evidenceIds") or [])
            ]
        elif body.get("claimedEvidenceIds") is not None:
            claimed_ids = list(body.get("claimedEvidenceIds") or [])
        return storage.provenance_for_match(match.id, claimed_evidence_ids=claimed_ids)

    @router.post("/matches/{match_id}/shots/quality")
    def post_match_shot_quality(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.shot_quality_for_match(match.id)

    @router.post("/matches/{match_id}/artifacts/alongside")
    def post_match_write_alongside(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.write_alongside_for_match(match.id)

    @router.post("/matches/{match_id}/tracklets")
    def post_match_tracklets(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.tracklets_for_match(match.id)

    @router.post("/matches/{match_id}/shots/features")
    def post_match_shot_features(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.shot_features_for_match(match.id)

    return router


def attach_leftover_post_routes(app: FastAPI, storage: Storage) -> None:
    leftover = create_leftover_post_router(storage)
    app.include_router(leftover, prefix="/api/workbench/dev")
    if leftover_http_enabled():
        app.include_router(leftover, prefix="/api")
