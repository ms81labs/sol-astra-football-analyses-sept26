from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter
from ..storage import Storage
from .leftover_support import (
    _decoder_challengers_view,
    _production_decode_frames,
)
from .access import (
    authorize_object,
)
from .contracts import (
    SourceClockIdentity,
)
from .costs import (
    deployment_choice,
)
from .evidence import (
    evaluate_metric_spec,
)
from .media import (
    align_clip_start_to_grid,
    apply_crop_and_rotation,
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
    wrap_decoded_frame,
)

def register_media_post_routes(router: APIRouter, storage: Storage) -> None:
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
