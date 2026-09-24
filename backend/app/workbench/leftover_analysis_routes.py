from __future__ import annotations
from fastapi import APIRouter
from ..storage import Storage
from .recovery import support_bundle
from .leftover_support import (
    _as_bytes,
    _as_detection,
    _as_label,
    _legacy_geometry,
    _legacy_geometry_profile,
    _unmeasured_landmark_preview,
)
from .access import (
    mint_sharing_link,
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
)
from .benchmarks import (
    experiment_receipt,
    quality_gate_holds,
)
from .cache import (
    recompute_plan,
)
from .evaluation import (
    analyst_workflow_measures,
    current_repository_evaluation_gate,
    evaluate_protocol_prerequisites,
)
from .events import (
    propose_event,
    score_events,
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
    pause_experiment,
)
from .media import (
    colour_round_trip,
    cpu_fallback,
    DecodedFrame,
    torso_colour_pixels,
    wrap_decoded_frame,
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
from .research import (
    execute_track,
    may_write_product_paths,
)
from .roster import (
    promotion_gate,
)
from .training import (
    admit_example,
    experiment_ledger,
)

def register_governance_post_routes(router: APIRouter, storage: Storage) -> None:
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



def register_perception_post_routes(router: APIRouter, storage: Storage) -> None:
    @router.post("/geometry/contact")
    def post_geometry_contact(payload: dict | None = None) -> dict:
        body = payload or {}
        raw = body.get("bbox") or [0.0, 0.0, 10.0, 20.0]
        bbox = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        kind = str(body.get("kind") or "player")
        airborne = bool(body.get("airborne"))
        if kind == "ball" or airborne:
            return project_to_pitch(kind="ball" if kind == "ball" else "player", airborne=airborne, bbox=bbox)
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
        tracks = IouAssociationFallback().associate(
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
