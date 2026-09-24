"""Compatibility helpers shared by main and the isolated leftover routers."""

from __future__ import annotations

from collections.abc import Iterable

from pathlib import Path

from .access import stale_permissions
from .challengers import (
    gstreamer_adapter,
    kloppy_boundary,
    mcbyte_adapter,
    onnx_runtime_adapter,
    pynv_adapter,
    roboflow_trackers_adapter,
    tensorrt_adapter,
    trackeval_adapter,
)
from .contracts import SourceClockIdentity
from .geometry import (
    evaluate_landmarks,
    from_legacy_four_points,
    preview_landmark_fit,
    withhold_if_invalid,
)
from .jobs import JobRequest
from .media import (
    DecodedFrame,
    FfmpegFrameSource,
    FixtureFrameSource,
    OpenCvFrameSource,
    PyAvFrameSource,
    SamplingAudit,
    TorchCodecFrameSource,
    cpu_fallback,
    first_bgr_frame,
    four_rates_receipt,
    iter_bgr_frames,
)
from .perception import Detection, Label
from .receipts import promotion_receipt

def _as_bytes(values: Iterable[int | str] | bytes | bytearray | str | None) -> bytes:
    if isinstance(values, (bytes, bytearray)):
        return bytes(values)
    if isinstance(values, str):
        return values.encode("latin1")
    return bytes(int(item) for item in list(values or []))


def _as_box(values: Iterable[float | str] | None) -> tuple[float, float, float, float]:
    box = list(values or [0.0, 0.0, 1.0, 1.0])
    return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))


def _as_detection(item: dict) -> Detection:
    return Detection(
        frameId=int(item.get("frameId") or 0),
        bbox=_as_box(item.get("bbox")),
        score=float(item.get("score") or 0.0),
        kind=item.get("kind") or "player",
        stratum=item.get("stratum") or "near",
    )


def _as_label(item: dict) -> Label:
    return Label(
        frameId=int(item.get("frameId") or 0),
        bbox=_as_box(item.get("bbox")),
        kind=item.get("kind") or "player",
        stratum=item.get("stratum") or "near",
        visible=item.get("visible", True),
    )


def _production_job_request() -> JobRequest:
    return JobRequest(
        requestId="production",
        matchId="unknown",
        sourceSha256="0" * 64,
        intervalStart=0.0,
        intervalEnd=0.0,
        temporalPolicy="source_global_grid",
        decoderVersion="opencv",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=0.0,
        authorisedLocation="local",
        namespace="production",
    )


def _legacy_geometry_profile(points: list | None = None):
    pts = list(points or [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}])
    if len(pts) != 4:
        pts = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
    return from_legacy_four_points(
        [{"x": float(item.get("x") or 0.0), "y": float(item.get("y") or 0.0)} for item in pts],
        calibration_id="legacy",
    )


def _legacy_geometry(points: list | None = None) -> dict:
    profile = _legacy_geometry_profile(points)
    evaluation = evaluate_landmarks(profile, max_p95_m=3.0)
    withheld = withhold_if_invalid(profile, "team_width_m")
    dumped = profile.model_dump(mode="json")
    return {**dumped, "evaluation": evaluation, "withheld": withheld}


def _four_rates_view() -> dict:
    audit = SamplingAudit(
        source_sha256="0" * 64,
        declared_target_fps=5.0,
        nominal_fps=25.0,
        frame_interval=5,
        selected_backend="ultralytics_track",
    )
    for _ in range(25):
        audit.record_decoded_frame()
        audit.record_primary_inference()
        audit.record_tracker_update()
    for _ in range(3):
        audit.record_recovery_inference()
    for _ in range(5):
        audit.record_export_sample()
    receipt = four_rates_receipt(audit)
    return {
        "decodeCount": receipt.decodeCount,
        "detectorPrimaryCount": receipt.detectorPrimaryCount,
        "detectorRecoveryCount": receipt.detectorRecoveryCount,
        "trackerUpdateCount": receipt.trackerUpdateCount,
        "exportCount": receipt.exportCount,
        "exportFpsEqualsInferenceFps": receipt.exportFpsEqualsInferenceFps,
        "decodeFpsEqualsExportFps": receipt.decodeFpsEqualsExportFps,
        "notes": list(receipt.notes),
    }


def _unpromoted_receipt() -> dict:
    return promotion_receipt(
        source_sha256=None,
        weights=None,
        configuration=None,
        hardware=None,
        native_builds=[],
        selected_backend=None,
        frame_count=None,
        call_count=None,
        cold_timing_ms=None,
        warm_timing_ms=None,
        peak_memory_bytes=None,
        transferred_bytes=None,
        output_quality="unproven",
        accepted_coverage=0.0,
        failure_cases=["labels_incomplete"],
        allocated_spend=0.0,
        fallback_event=None,
    )


def _fixture_frame_source() -> tuple[list[DecodedFrame], FixtureFrameSource]:
    identity = SourceClockIdentity(sourceSha256="a" * 64, byteSize=3)
    frames = [
        DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, b"\x00\x00\x00", "fixture"),
        DecodedFrame(1, 1, 0.04, 1, 1, "bgr", 0, b"\x00\x00\x00", "fixture"),
    ]
    return frames, FixtureFrameSource(frames, identity)


def _stale_permissions_view() -> dict:
    return stale_permissions(permission_expires_at=0.0, now=1.0)


def _challenger_adapters_view() -> dict:
    return {
        "kloppy": kloppy_boundary(),
        "roboflow": roboflow_trackers_adapter(),
        "mcbyte": mcbyte_adapter(),
        "onnx": onnx_runtime_adapter(),
        "tensorrt": tensorrt_adapter(),
        "pynv": pynv_adapter(),
        "gstreamer": gstreamer_adapter(),
        "trackeval": trackeval_adapter(),
    }


def _decoder_challengers_view(storage_root: Path) -> dict:
    path = Path(storage_root) / "decode-fixture.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"src")
    pyav = PyAvFrameSource()
    torchcodec = TorchCodecFrameSource()
    ffmpeg = FfmpegFrameSource(
        frames=[],
        identity=SourceClockIdentity(sourceSha256="a" * 64, byteSize=0),
    )
    pyav_error = None
    torch_error = None
    try:
        list(pyav.iter_frames(path))
    except RuntimeError as exc:
        pyav_error = str(exc)
    try:
        list(torchcodec.iter_frames(path))
    except RuntimeError as exc:
        torch_error = str(exc)
    return {
        "pyav": {
            "name": pyav.name,
            "default": False,
            "enabled": False,
            "role": "challenger",
            "error": pyav_error,
        },
        "torchcodec": {
            "name": torchcodec.name,
            "default": False,
            "enabled": False,
            "role": "challenger",
            "error": torch_error,
        },
        "ffmpeg": {"name": ffmpeg.name, "default": False, "enabled": False, "role": "challenger"},
        "selected": cpu_fallback("cuda", {"opencv", "fixture"}),
    }


def _production_decode_frames(storage_root: Path) -> dict:
    path = Path(storage_root) / "decode-fixture.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"src")
    _, source = _fixture_frame_source()
    decoded = list(iter_bgr_frames(path, source))
    first = first_bgr_frame(path, source)
    buffer = decoded[0].buffer if decoded else None
    return {
        "backend": source.name,
        "defaultBackend": OpenCvFrameSource.name,
        "pyavDefault": False,
        "torchcodecDefault": False,
        "device": "cpu" if buffer is None else buffer.device,
        "gpuPromoted": False,
        "indexes": [frame.source_frame_index for frame in decoded],
        "firstIndex": None if first is None else first.source_frame_index,
    }


def _unmeasured_landmark_preview() -> dict:
    preview = preview_landmark_fit(residual_p95_m=float("inf"), max_p95_m=3.0)
    preview["residualP95M"] = None
    preview["measured"] = False
    preview["accepted"] = False
    preview["reasonCodes"] = ["LANDMARK_RESIDUAL_UNMEASURED"]
    return preview

EXTERNAL_SOCCERNET_UI_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/football_external_soccernet_analysis_product_ui_binding_v1"
)
EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/football_external_soccertrack_match_bundle_bridge_smoke_v1"
)
EXTERNAL_SOCCERTRACK_UI_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/football_external_soccertrack_analysis_product_ui_binding_v1"
)
EXTERNAL_BENCHMARK_UI_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/football_external_benchmark_product_ui_binding_v1"
)
EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/football_external_benchmark_product_decision_surface_v1"
)
VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_finish_line_product_binding_v1"
)
VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_acceptance_report_route_binding_v1"
)
VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_operator_handoff_route_binding_v1"
)
VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_release_readout_route_binding_v1"
)
VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_post_release_monitoring_route_binding_v1"
)
VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_detector_evaluation_report_route_binding_v1"
)
VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_promotion_review_report_route_binding_v1"
)
VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_promoted_runtime_post_release_monitoring_route_binding_v1"
)
VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_operator_dashboard_polish_v1"
)
VIDEO_TO_ANALYSIS_REAL_VIDEO_SCALEOUT_REPORT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_real_video_scaleout_report_route_binding_v1"
)
VIDEO_TO_ANALYSIS_BOUNDED_NEXT_SAMPLE_REPORT_BINDING_DIR = (
    "trained_detector_candidates"
    "/touchline_detector_candidate_v7"
    "/video_to_analysis_bounded_next_sample_report_route_binding_v1"
)
