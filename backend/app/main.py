from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .export_flatteners import (
    EVENT_CSV_FIELDS,
    FRAME_CSV_FIELDS,
    METRIC_CSV_FIELDS,
    flatten_events_for_csv,
    flatten_frames_for_csv,
    flatten_metrics_for_csv,
    render_csv,
)
from .jobs import JobDispatchError, JobRunner
from .workbench.errors import (
    BudgetExhausted,
    CorrectionApplicationError,
    DomainError,
    IdempotencyConflict,
    NotOwner,
    ReconciliationRequired,
    RetryBudgetExhausted,
    RouteRetired,
    StaleRevision,
    StaleTransition,
)
from .llm import run_analysis
from .provider_gateway import ProviderBudgetLedger, ProviderDenied, ProviderGateway
from .report_export import build_match_report_export
from .generations import StaleGeneration, GenerationRecoveryRequired
from .settings import ProcessingSettings, SettingsError, canonicalize_origin
from .trust_crops import compute_trust_crops
from .schemas import (
    CreateAnnotationRequest,
    CreateBundleRequest,
    CreateIssueRequest,
    MatchAnalyticsResponse,
    MatchConfig,
    MatchEventsResponse,
    MatchFramesResponse,
    MatchRecord,
    ReviewBundleItem,
    TrustCropSchema,
    TrustCropsResponse,
    UpdateBundleRequest,
    DashboardSummary,
    DashboardResponse,
    DashboardComparison,
    SeasonTrendPoint,
)
from .semantic_search import search_matches_by_tactical_themes, search_bundles_by_tactical_themes, detect_themes_for_match
from .storage import AdmissionOutcomeUncertainError, Storage, UploadTooLargeError
from .ai_policy import ground_output, select_evidence
from .workbench.access import (
    access_deletion_procedure,
    authorize_object,
    constrained_decoder,
    deployment_encryption,
    least_privilege_storage,
    mint_sharing_link,
    object_access_decision,
    protocol_network_allowlist,
    public_exposure_gate,
    signed_scoped_object_access,
    stale_permissions,
    untrusted_model_output,
    upload_quota,
    verify_hosted_token,
)
from .workbench.challengers import (
    gstreamer_adapter,
    kloppy_boundary,
    mcbyte_adapter,
    onnx_runtime_adapter,
    pynv_adapter,
    roboflow_trackers_adapter,
    tensorrt_adapter,
    trackeval_adapter,
)
from .workbench.admission import admit_camera, admit_media
from .workbench.artifacts import (
    columnar_observation_store,
    cross_tenant_cache_reuse,
    import_worker_output,
    object_storage_adapter,
    secrets_in_artifacts,
)
from .workbench.assistance import (
    dual_budgets,
    embeddings_retrieve,
    escalation_requires_quality_gap,
    json_repair_chain,
    network_failure_preserves_unknown,
    policy_log,
    preemptible_allowed,
    providers_disabled_fallback,
    template_report,
)
from .workbench.incidents import (
    broadcast_replay_not_simultaneous,
    elevated_body_part_homography,
    invisible_entity_not_repaired_by_larger_model,
    level0_incident_package,
    level1_positional_aid,
    level2_schematic_replay,
    level3_multiview,
    vlm_confidence_is_not_referee,
)
from .workbench.jobs import (
    JobRequest,
    attach_durable_job_view,
    cancellation_does_not_erase_charges,
    cleanup_failure_is_complete,
    deployment_mode,
    distributed_broker,
    egress_policy,
    pause_experiment,
    signed_scoped_job_access,
    vector_database,
    worker_environment,
)
from .workbench.contracts import SourceClockIdentity, migrate_legacy_zero, unknown_metric
from .workbench.costs import (
    credit_allocation,
    decimal_gb_to_gib,
    deployment_choice,
    historical_capacity_seconds,
    match_cost,
    reconcile_spend,
    reserve_budget,
    scale_scenario,
)
from .workbench.benchmarks import experiment_receipt, quality_gate_holds
from .workbench.decisions import architecture_decisions
from .workbench.dossier import build_baseline_dossier, build_release_dossier, http_dossier
from .workbench.evaluation import (
    analyst_workflow_measures,
    current_repository_evaluation_gate,
    evaluate_protocol_prerequisites,
    evaluation_measures,
    score_hota_idf1,
)
from .workbench.events import learned_temporal, ownership_invalidation, propose_event, score_events
from .workbench.geometry import (
    CalibrationProfile,
    detect_zoom_or_cut,
    evaluate_landmarks,
    from_legacy_four_points,
    ground_contact_point,
    preview_landmark_fit,
    project_to_pitch,
    withhold_if_invalid,
)
from .workbench.evidence import DEFINITION_VERSION, evaluate_metric_spec, inspect_metric, metric_dictionary, round_trip_unknown
from .workbench.cache import recompute_plan
from .workbench.flags import feature_enabled, feature_flags, shadow_metric
from .workbench.identity import (
    IdentityRecord,
    appearance_embedding_policy,
    candidate_rejoin,
    cluster_mapping,
    cross_season_identity,
    face_recognition,
    promote_identity,
    reconnect_across_cut,
)
from .workbench.executables import resolve_trusted_executable
from .workbench.milestones import milestone_plan, owners, progress_signal
from .workbench.native import (
    cuda_visibility_is_not_video_capability,
    custom_native_justification,
    ffmpeg_build_review,
    native_gate,
    no_rpc_fleet,
    pinned_native_artifacts,
    probe_gpu,
    qualified_os_profiles,
    quantized_weight_memory,
)
from .workbench.privacy import dpia_screen, residency_claim
from .workbench.perception import (
    Detection,
    DetectorAdapter,
    IdentityRepair,
    IouAssociationFallback,
    Label,
    PreprocessPlan,
    TrackerAdapter,
    merge_tiled_detections,
    preview_identity_change,
    score_detections,
    score_detections_by_stratum,
    separate_ball_states,
    tile_to_source,
)
from .workbench.quantities import heatmap_availability, pitch_axes, split_scores, transform_legacy_display
from .workbench.recovery import full_disk, recovery_objectives, support_bundle, unresolved_incidents
from .workbench.repository import RepositoryAdapter, http_may_run_gpu, vector_broker_required
from .workbench.reports import assemble_report, held_out_questions
from .workbench.research import execute_track, may_write_product_paths, research_lane
from .workbench.retention import PROTECTED, may_delete
from .workbench.media import (
    DecodedFrame,
    FfmpegFrameSource,
    FfmpegProbe,
    FixtureFrameSource,
    OpenCvFrameSource,
    PyAvFrameSource,
    SamplingAudit,
    TorchCodecFrameSource,
    apply_crop_and_rotation,
    align_clip_start_to_grid,
    colour_round_trip,
    cpu_fallback,
    decode_memory_policy,
    detect_camera_cuts,
    first_bgr_frame,
    four_rates_receipt,
    frame_interval_for_target_fps,
    iter_bgr_frames,
    map_decoded_to_sample,
    map_original_to_proxy_pts,
    pixels_from_decoded_frame,
    pts_to_seconds,
    resolve_declared_interval,
    sample_decode_anchors,
    torso_colour_pixels,
    vid_stride_policy,
    wrap_decoded_frame,
)
from .workbench.review import collaboration_lock, correction_api_payload, playlist_export_interval
from .workbench.adoption import dependency_register
from .workbench.providers import cloud_adapter, local_adapter, provider_roster
from .workbench.rights import dataset_manifest, evaluate_rights, incident_response, licence_register, rights_register
from .workbench.risks import independent_reviewer, risk_register, telestration_before_3d, worked_match_flow
from .workbench.rollback import rollback_release
from .workbench.roster import frontier_provider_role, label_products, model_roster, promotion_gate, video_model_roster
from .workbench.routes import create_workbench_router
from .workbench.receipts import promotion_receipt
from .workbench.ownership import OwnershipHysteresis, possession_from_states
from .workbench.shot_model import tree_challenger
from .workbench.timing import gpu_timing_scope, stage_timing
from .workbench.targets import metadata_api_targets
from .workbench.training import (
    admit_example,
    data_pools,
    drill_library,
    experiment_cycle,
    experiment_ledger,
    promote_candidate,
    pseudo_label,
    sampling_policy,
)
from .workbench.xt import xt_deferred_plan


STORAGE_ROOT_ENV = "GUERILLA_STORAGE_ROOT"
LOGGER = logging.getLogger(__name__)
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_DISPATCH_FAILED = "Job dispatch failed before processing started."
_DISPATCH_UNCERTAIN = "Job dispatch outcome is uncertain; automatic retry is disabled."


def _as_bytes(values: object) -> bytes:
    if isinstance(values, (bytes, bytearray)):
        return bytes(values)
    if isinstance(values, str):
        return values.encode("latin1")
    return bytes(int(item) for item in list(values or []))


def _as_box(values: object) -> tuple[float, float, float, float]:
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


class BrowserOriginMiddleware:
    """Reject unsafe browser requests before routing, body parsing or websocket acceptance."""

    def __init__(self, app: ASGIApp, trusted_origins: tuple[str, ...]) -> None:
        self.app = app
        self.trusted_origins = trusted_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"} and (
            scope["type"] == "websocket" or scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        ):
            headers = Headers(scope=scope)
            origins = headers.getlist("origin")
            if origins:
                allowed = False
                try:
                    if len(origins) == 1:
                        origin = canonicalize_origin(origins[0])
                        scheme = {"ws": "http", "wss": "https"}.get(scope["scheme"], scope["scheme"])
                        same_origin = canonicalize_origin(f"{scheme}://{headers.get('host', '')}")
                        allowed = origin == same_origin or origin in self.trusted_origins
                except SettingsError:
                    pass
                if not allowed:
                    if scope["type"] == "websocket":
                        await WebSocket(scope, receive, send).close(code=1008)
                    else:
                        await JSONResponse({"detail": "Untrusted request origin"}, status_code=403)(scope, receive, send)
                    return
        await self.app(scope, receive, send)


class HostedAuthMiddleware:
    """Authenticate once at the ASGI boundary; downstream headers are never identity."""

    def __init__(self, app: ASGIApp, *, secret: str, storage: Storage) -> None:
        self.app = app
        self.secret = secret
        self.storage = storage

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] not in {"http", "websocket"} or not path.startswith(("/api", "/ws")):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        authorization = Headers(scope=scope).get("authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        tenant = verify_hosted_token(self.secret, token)
        if tenant is None:
            if scope["type"] == "websocket":
                await WebSocket(scope, receive, send).close(code=1008)
            else:
                await JSONResponse({"detail": "Authentication required"}, status_code=401)(scope, receive, send)
            return
        scope.setdefault("state", {})["tenant"] = tenant

        internal_or_unscoped = (
            "/api/workbench",
            "/api/bundles",
            "/api/aggregate",
            "/api/search",
            "/api/library",
            "/api/dossier",
            "/api/capabilities",
            "/api/flags",
        )
        if path.startswith(internal_or_unscoped):
            if scope["type"] == "websocket":
                await WebSocket(scope, receive, send).close(code=1008)
            else:
                await JSONResponse({"detail": "Route is not available at the hosted boundary"}, status_code=403)(scope, receive, send)
            return

        match = None
        parts = path.strip("/").split("/")
        try:
            if len(parts) >= 3 and parts[:2] == ["api", "matches"]:
                match = self.storage.get_match(parts[2])
            elif len(parts) >= 3 and parts[:2] == ["api", "jobs"]:
                match = self.storage.get_match(self.storage.get_job(parts[2]).matchId)
            elif len(parts) >= 3 and parts[:2] == ["ws", "jobs"]:
                match = self.storage.get_match(self.storage.get_job(parts[2]).matchId)
        except KeyError:
            pass
        if match is not None and match.config.rights.audience != tenant:
            if scope["type"] == "websocket":
                await WebSocket(scope, receive, send).close(code=1008)
            else:
                await JSONResponse({"detail": "Object access denied"}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _default_storage_root() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "guerilla-analytics"


def _resolve_storage_root(storage_root: Path | str | None) -> Path:
    if storage_root is not None:
        return Path(storage_root).expanduser()
    configured_root = os.environ.get(STORAGE_ROOT_ENV)
    if configured_root and configured_root.strip():
        return Path(configured_root).expanduser()
    return _default_storage_root()


def _retire_default_frontend_routes(app: FastAPI) -> None:
    """Keep unsupported compatibility paths explicit without running dev handlers."""

    existing = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and not route.path.startswith("/api/workbench/dev/")
        for method in route.methods
    }
    for route in list(app.routes):
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/workbench/dev/"):
            continue
        path = "/api/" + route.path.removeprefix("/api/workbench/dev/")
        methods = {method for method in route.methods if (path, method) not in existing}
        if not methods:
            continue
        def retired_endpoint(replacement: str):
            async def retired() -> None:
                raise RouteRetired(replacement)

            return retired

        app.add_api_route(
            path,
            retired_endpoint(route.path),
            methods=methods,
            name=f"retired_{route.name}",
            include_in_schema=False,
        )


def build_match_bundle(storage: Storage, match_id: str, *, generation_id: str | None = None) -> dict[str, object]:
    from .match_bundle import build_match_bundle as assemble_match_bundle

    return assemble_match_bundle(storage, match_id, generation_id=generation_id)


def reprocess_video_match(storage: Storage, match_id: str, *, config: MatchConfig | None = None) -> None:
    from .processor import reprocess_video_match as execute_reprocess_video_match

    execute_reprocess_video_match(storage, match_id, config=config)


def build_selected_cluster_payload(storage: Storage, match_id: str) -> dict[str, object]:
    from .run_benchmarks import build_selected_cluster_payload as assemble_selected_cluster_payload

    return assemble_selected_cluster_payload(storage, match_id)


def summarize_match_benchmark(storage: Storage, match_id: str):
    from .run_benchmarks import summarize_match_benchmark as assemble_match_benchmark

    return assemble_match_benchmark(storage, match_id)


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


def _dashboard_metric_value(summary: dict, *, field: str, metric: str) -> float | None:
    """A missing/withheld measurement is not zero, including historical summaries."""
    record = next(
        (item for item in summary.get("metricAvailability") or [] if item.get("metric") == metric),
        None,
    )
    if record is not None and record.get("availability") not in {"available", "experimental"}:
        return None
    value = summary.get(field) if record is None else record.get("value")
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)


def _dashboard_average(summaries: list[dict], *, field: str, metric: str, digits: int = 1) -> float | None:
    values = [value for summary in summaries
              if (value := _dashboard_metric_value(summary, field=field, metric=metric)) is not None]
    return round(sum(values) / len(values), digits) if values else None


def _dashboard_difference(latest: dict, previous: dict, *, field: str, metric: str) -> float | None:
    left = _dashboard_metric_value(latest, field=field, metric=metric)
    right = _dashboard_metric_value(previous, field=field, metric=metric)
    return round(left - right, 1) if left is not None and right is not None else None


def _xg_balance(summary: dict) -> float | None:
    my_xg = summary.get("myTeamXg")
    enemy_xg = summary.get("enemyXg")
    if my_xg is None or enemy_xg is None:
        return None
    return round(float(my_xg) - float(enemy_xg), 2)


def create_app(
    storage_root: Path | str | None = None,
    run_jobs_inline: bool = False,
    settings: ProcessingSettings | None = None,
) -> FastAPI:
    settings = settings or ProcessingSettings.from_env()
    settings.validate_deployment()
    storage = Storage(_resolve_storage_root(storage_root))
    runner = JobRunner(storage.storage_root, run_jobs_inline=run_jobs_inline, settings=settings, ledger=storage.job_ledger)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        reclaimed = runner.ledger.reclaim_expired(now=time.time())
        if reclaimed:
            LOGGER.warning("reclaimed %d expired job lease(s)", len(reclaimed))
        yield
        storage.close()

    app = FastAPI(title="Guerilla Analytics API", version="0.1.0", lifespan=lifespan)
    app.state.storage = storage
    app.state.runner = runner
    provider_gateway = ProviderGateway(
        storage,
        settings,
        adapter_factory=lambda: run_analysis,
        budget_ledger=ProviderBudgetLedger(
            storage.storage_root / "provider-budget.sqlite3",
            settings.provider_budget_limit,
        ),
    )
    app.state.provider_gateway = provider_gateway

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        from .generations import GenerationRecoveryRequired, StaleGeneration, RetentionBusy
        from .semantic_commands import SemanticCommandError
        if isinstance(exc, SemanticCommandError):
            return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "detail": str(exc)})
        if isinstance(exc, GenerationRecoveryRequired):
            return JSONResponse(status_code=503, content={"error": exc.code})
        if isinstance(exc, (StaleGeneration, RetentionBusy)):
            return JSONResponse(status_code=409, content={"error": exc.code})
        if isinstance(exc, IdempotencyConflict):
            return JSONResponse(
                status_code=409,
                content={"error": "IDEMPOTENCY_CONFLICT", "requestId": exc.request_id},
            )
        if isinstance(exc, StaleRevision):
            return JSONResponse(
                status_code=409,
                content={"error": "STALE_REVISION", "expected": exc.expected, "actual": exc.actual},
            )
        if isinstance(exc, RouteRetired):
            return JSONResponse(
                status_code=410,
                content={"error": "ROUTE_RETIRED", "replacement": exc.replacement},
            )
        if isinstance(
            exc,
            (BudgetExhausted, NotOwner, ReconciliationRequired, RetryBudgetExhausted, StaleTransition),
        ):
            error_code = {
                BudgetExhausted: "BUDGET_EXHAUSTED",
                NotOwner: "NOT_OWNER",
                ReconciliationRequired: "RECONCILIATION_REQUIRED",
                RetryBudgetExhausted: "RETRY_BUDGET_EXHAUSTED",
                StaleTransition: "STALE_TRANSITION",
            }[type(exc)]
            content: dict[str, object] = {"error": error_code}
            if isinstance(exc, StaleTransition):
                content.update(expected=exc.expected, actual=exc.actual)
            return JSONResponse(status_code=409, content=content)
        if isinstance(exc, CorrectionApplicationError):
            return JSONResponse(
                status_code=500,
                content={"error": "CORRECTION_APPLICATION_FAILED", "commandId": exc.command_id},
            )
        return JSONResponse(status_code=400, content={"error": "DOMAIN_ERROR"})
    app.include_router(create_workbench_router(storage))
    from .workbench.leftover_http import LeftoverHttpGate
    from .workbench.leftover_get_routes import attach_leftover_get_routes
    from .workbench.leftover_routes import attach_leftover_post_routes

    attach_leftover_post_routes(app, storage)
    attach_leftover_get_routes(app, storage)
    app.add_middleware(LeftoverHttpGate)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "Authorization", "X-Object-Scope", "X-Deployment-Boundary", "X-Tenant-Id"],
    )
    app.add_middleware(BrowserOriginMiddleware, trusted_origins=settings.trusted_frontend_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"], www_redirect=False)
    if settings.deployment_mode == "hosted":
        app.add_middleware(HostedAuthMiddleware, secret=settings.auth_secret or "", storage=storage)

    @app.post("/api/matches", status_code=202)
    async def create_match(
        request: Request,
        name: str = Form(...),
        inputMode: str = Form(...),
        config: str = Form("{}"),
        budget: float = Form(0.0),
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict:
        if not math.isfinite(budget) or budget < 0:
            raise HTTPException(status_code=422, detail="budget must be finite and non-negative")
        if runner.settings.processing_backend == "daytona" and budget <= 0:
            raise HTTPException(
                status_code=422,
                detail="Daytona processing requires a positive authorised budget",
            )
        if idempotency_key is not None and _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
        admission_token = idempotency_key or uuid.uuid4().hex

        def response(job, *, outcome: str, reused: bool) -> dict:
            return {
                "matchId": job.matchId,
                "jobId": job.id,
                "status": job.status,
                "admissionToken": admission_token,
                "dispatchOutcome": outcome,
                "reused": reused,
            }

        admitted = await run_in_threadpool(storage.get_admission_by_token, admission_token)
        if admitted is not None:
            return response(admitted[1], outcome="reused", reused=True)

        if inputMode not in {"tracking_json", "video"}:
            raise HTTPException(status_code=422, detail="Invalid inputMode")
        try:
            config_model = MatchConfig.model_validate_json(config)
        except Exception as exc:  # pragma: no cover - FastAPI validation path
            raise HTTPException(status_code=400, detail=f"Invalid config payload: {exc}") from exc
        if settings.deployment_mode == "hosted":
            config_model = config_model.model_copy(
                update={"rights": config_model.rights.model_copy(update={"audience": request.state.tenant})}
            )

        if (
            inputMode == "video"
            and not config_model.autoHomography
            and len(config_model.manualHomographyPoints) != 4
        ):
            raise HTTPException(
                status_code=400,
                detail="manualHomographyPoints must contain exactly 4 points for video input, or set autoHomography=True.",
            )

        try:
            upload_path = await run_in_threadpool(
                storage.save_upload_stream,
                file.filename or "upload.bin",
                file.file,
                runner.settings.max_upload_bytes,
            )
        except UploadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        match_id = uuid.uuid4().hex
        job_id = uuid.uuid4().hex
        try:
            match, job, created = await run_in_threadpool(
                storage.admit_match_job,
                match_id=match_id,
                job_id=job_id,
                admission_token=admission_token,
                name=name,
                input_mode=inputMode,
                original_filename=file.filename or "upload.bin",
                input_path=upload_path,
                config=config_model,
            )
        except AdmissionOutcomeUncertainError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "admission_outcome_uncertain",
                    "matchId": match_id,
                    "jobId": job_id,
                    "admissionToken": admission_token,
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Match admission failed") from exc
        if not created:
            return response(job, outcome="reused", reused=True)

        try:
            runner.admit(
                job.id,
                match_id=match.id,
                source_sha256=storage.source_sha256(match.id),
                budget=budget,
            )
        except IdempotencyConflict:
            pass

        dispatch_outcome = "started"
        dispatch_error: str | None = None
        try:
            await run_in_threadpool(runner.start, job.id)
        except JobDispatchError as exc:
            if exc.child_may_have_started:
                dispatch_outcome = "uncertain"
                dispatch_error = _DISPATCH_UNCERTAIN
            else:
                dispatch_outcome = "failed"
                dispatch_error = _DISPATCH_FAILED
        except Exception:
            dispatch_outcome = "uncertain"
            dispatch_error = _DISPATCH_UNCERTAIN

        if dispatch_error is None:
            try:
                job = await run_in_threadpool(storage.mark_dispatched, job.id)
            except Exception:
                pass
        else:
            try:
                job = await run_in_threadpool(storage.mark_dispatch_failed, match.id, job.id, error=dispatch_error)
            except Exception:
                pass
        return response(job, outcome=dispatch_outcome, reused=False)

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

    @app.get("/api/jobs/{job_id}")
    def get_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)

    @app.get("/api/jobs/{job_id}/cost")
    def get_job_cost(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return runner.ledger.cost_for(job_id)

    @app.get("/api/jobs/{job_id}/budget")
    def get_job_budget(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        cost = runner.ledger.cost_for(job_id)
        reserved = reserve_budget(estimate=float(cost.get("reservedTotal") or 0.0))
        reconcile = reconcile_spend(reserved=float(reserved["reserved"]), actual=float(cost.get("actualTotal") or 0.0))
        return {"reserve": reserved, "reconcile": reconcile, "cost": cost}

    @app.get("/api/jobs/{job_id}/charges")
    def get_job_charges(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        view = attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
        cost = runner.ledger.cost_for(job_id)
        incurred = float(cost.get("actualTotal") or 0.0)
        if incurred == 0.0:
            incurred = float(cost.get("reservedTotal") or 0.0)
        cancelled = bool(view.get("cancelRequested") or job.status == "cancelled")
        return cancellation_does_not_erase_charges(cancelled=cancelled, incurred=incurred)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        runner.ledger.request_cancel(job_id)
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)

    @app.post("/api/jobs/{job_id}/retry")
    def retry_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        runner.retry(job_id)
        job = storage.reset_job_for_retry(job_id)
        runner.start(job_id)
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)

    @app.post("/api/jobs/{job_id}/timeout")
    def timeout_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        try:
            runner.ledger.timeout_before_response(job_id, owner_id=f"job:{job_id}")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)

    @app.post("/api/jobs/{job_id}/lost-connection")
    def lost_connection_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        try:
            runner.ledger.lost_connection(job_id, owner_id=f"job:{job_id}")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)

    @app.get("/api/jobs/{job_id}/rates")
    def get_job_rates(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return storage.four_rates_for_match(match.id)

    @app.get("/api/metrics/dictionary")
    def get_metric_dictionary() -> dict:
        return {"metrics": metric_dictionary()}

    @app.get("/api/flags")
    def get_feature_flags() -> dict:
        return feature_flags()

    @app.get("/api/dossier")
    def get_dossier() -> dict:
        payload = http_dossier()
        return {key: payload[key] for key in ("baseline", "release", "evaluation", "gpu", "native")}

    @app.get("/api/capabilities")
    def get_capabilities() -> dict:
        return {"capabilities": http_dossier()["capabilities"]}

    @app.post("/api/library/search")
    def post_library_search(payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.search_stored_library(str(body.get("query") or ""))

    @app.get("/api/metrics/inspect/{metric}")
    def get_metric_inspect(metric: str) -> dict:
        return inspect_metric(metric)

    @app.post("/api/rollback")
    def post_rollback(payload: dict | None = None) -> dict:
        body = payload or {}
        return rollback_release(
            flag_name=str(body.get("flagName") or "unspecified"),
            affected_outputs=list(body.get("affectedOutputs") or []),
        )

    @app.post("/api/media/admit")
    def post_media_admit(payload: dict | None = None) -> dict:
        body = payload or {}
        identity = SourceClockIdentity(
            sourceSha256=str(body.get("sourceSha256") or ""),
            byteSize=int(body.get("byteSize") or 0),
            codec=body.get("codec"),
            audioTracks=int(body.get("audioTracks") or 0),
            decodeErrors=list(body.get("decodeErrors") or []),
            variableFrameRate=bool(body.get("variableFrameRate")),
            rotation=int(body.get("rotation") or 0),
        )
        return admit_media(
            identity,
            existing_digests=set(body.get("existingDigests") or []),
            require_audio=bool(body.get("requireAudio")),
            source_url=body.get("sourceUrl"),
        )

    @app.post("/api/cost/estimate")
    def post_cost_estimate(payload: dict | None = None) -> dict:
        body = payload or {}
        return match_cost(
            allocated_compute=float(body.get("allocatedCompute") or 0.0),
            retained_storage=float(body.get("retainedStorage") or 0.0),
            transfer=float(body.get("transfer") or 0.0),
            model_api=float(body.get("modelApi") or 0.0),
            retry_overhead=float(body.get("retryOverhead") or 0.0),
            review_labour=float(body.get("reviewLabour") or 0.0),
            fixed_share=float(body.get("fixedShare") or 0.0),
            export_fps=body.get("exportFps"),
        ).model_dump(mode="json")

    @app.post("/api/rights/evaluate")
    def post_rights_evaluate(payload: dict | None = None) -> dict:
        body = payload or {}
        return evaluate_rights(
            {
                "asset": str(body.get("asset") or "match_recording"),
                "commercialPermission": "uncertain",
                "cloudPermitted": False,
            }
        ).model_dump(mode="json")

    @app.post("/api/access/deletion")
    def post_access_deletion(payload: dict | None = None) -> dict:
        body = payload or {}
        return access_deletion_procedure(
            requested=bool(body.get("requested")),
            controller_recorded=False,
        )

    @app.post("/api/retention/delete")
    def post_retention_delete(payload: dict | None = None) -> dict:
        body = payload or {}
        kind = str(body.get("kind") or "")
        authorised = bool(body.get("authorisedPolicy"))
        return {
            "kind": kind,
            "mayDelete": may_delete(kind, authorised_policy=authorised),
            "protected": kind in PROTECTED,
        }

    @app.post("/api/playlists/export-interval")
    def export_playlist_interval(payload: dict | None = None) -> dict:
        body = payload or {}
        try:
            return playlist_export_interval(body, float(body.get("sourceFps") or 25.0))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/matches")
    def list_matches(request: Request) -> list[dict]:
        matches = storage.list_matches()
        if settings.deployment_mode == "hosted":
            matches = [match for match in matches if match.config.rights.audience == request.state.tenant]
        return [match.model_dump(mode="json") for match in matches]

    def snapshot_response(match_id: str, load, generation_id: str | None = None) -> dict:
        """Generation selection is explicit across independently fetched panes."""
        from contextlib import ExitStack
        with ExitStack() as stack:
            try:
                ref = stack.enter_context(storage.generation_snapshot(match_id, generation_id=generation_id))
            except FileNotFoundError:
                if generation_id is not None:
                    raise
                ref = None  # Preserve documented brand-new/not-ready outcomes.
            result = load()
            return {**result, "generationId": ref.generationId if ref is not None else None}

    @app.get("/api/matches/{match_id}")
    def get_match(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        def detail() -> dict:
            result = storage.get_match(match.id).model_dump(mode="json")
            try:
                ref = storage.current_generation(match.id)
            except FileNotFoundError:
                return result
            manifest, _ = storage.generations.manifest(match.id, ref.generationId)
            # Playlist/history effects must be selected from this snapshot, not
            # from a newer operational log fetched by another browser request.
            result["includedCommandIds"] = manifest.includedCommandIds
            return result
        return snapshot_response(match.id, detail, generationId)

    @app.post("/api/matches/{match_id}/jobs", status_code=202)
    def post_match_job(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        request_id = str(body.get("requestId") or uuid.uuid4().hex)
        try:
            budget = float(body.get("budget") or 0.0)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="budget must be numeric") from exc
        if not math.isfinite(budget) or budget < 0:
            raise HTTPException(status_code=422, detail="budget must be finite and non-negative")
        if runner.settings.processing_backend == "daytona" and budget <= 0:
            raise HTTPException(
                status_code=422,
                detail="Daytona processing requires a positive authorised budget",
            )
        try:
            job, created = storage.ensure_job(
                match.id,
                request_id,
                created_status="queued",
                budget=budget,
                authorised_location=(
                    "daytona"
                    if runner.settings.processing_backend == "daytona"
                    else "local"
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            attempt = runner.admit(
                request_id,
                match_id=match.id,
                source_sha256=storage.source_sha256(match.id),
                budget=budget,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="idempotent request payload mismatch") from exc
        view = attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
        return {
            "matchId": match.id,
            "jobId": job.id,
            "status": job.status,
            "attemptId": attempt.attemptId,
            "costReserved": float(attempt.reservedCost),
            "reused": not created,
            "cancelRequested": view["cancelRequested"],
            "terminated": view["terminated"],
            "cleanupResult": view["cleanupResult"],
            "durablePhase": view["durablePhase"],
        }

    @app.get("/api/matches/{match_id}/video")
    def get_match_video(match: MatchRecord = Depends(require_match)):
        if match.inputMode != "video":
            raise HTTPException(status_code=409, detail="Video playback is only available for video-backed matches.")

        video_path = storage.get_match_input_path(match.id)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found.")

        return FileResponse(video_path, media_type="video/mp4", filename=match.originalFilename)

    @app.get("/api/matches/{match_id}/frames")
    def get_frames(
        match: MatchRecord = Depends(require_match),
        afterFrame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        generationId: str | None = None,
    ) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                page = storage.load_frames_page(match.id, after_frame=afterFrame, cursor=cursor, limit=limit)
                response = MatchFramesResponse(
                    matchId=match.id, frames=page["frames"], nextCursor=page["nextCursor"],
                    frameCount=page["frameCount"], intervalEndpoint=page["intervalEndpoint"],
                ).model_dump(mode="json")
                return {**response, "generationId": ref.generationId}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/evidence")
    def get_match_evidence(
        match: MatchRecord = Depends(require_match),
        intervalStart: float | None = None,
        intervalEnd: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
        generationId: str | None = None,
    ) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.load_evidence_page(
                match.id, interval_start=intervalStart, interval_end=intervalEnd,
                cursor=cursor, limit=limit,
            ), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Evidence not ready") from exc

    @app.get("/api/matches/{match_id}/analytics")
    def get_analytics(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                summary, assignments, formation_timeline, shots = storage.load_analytics(match.id)
                response = MatchAnalyticsResponse(
                    matchId=match.id, summary=summary, ballAssignments=assignments,
                    formationTimeline=formation_timeline, shots=shots,
                ).model_dump(mode="json")
                return {**response, "generationId": ref.generationId}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.post("/api/matches/{match_id}/corrections")
    def post_match_correction(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        if not isinstance(body.get("payload", {}), dict):
            from .semantic_commands import SemanticCommandError
            raise SemanticCommandError("INVALID_COMMAND_PAYLOAD", "Command payload must be an object")
        if body.get("kind") == "calibration":
            from .semantic_commands import SemanticCommandError
            raise SemanticCommandError("CALIBRATION_COMMIT_REQUIRED", "Use the validated calibration commit endpoint")
        try:
            saved = storage.submit_correction(
                match.id,
                kind=str(body.get("kind") or ""),
                payload=dict(body.get("payload") or {}),
                author=str(body.get("author") or "analyst"),
                expected_version=body.get("expectedVersion"),
                base_generation=body.get("baseGeneration"),
                command_id=body.get("commandId"),
                idempotency_key=body.get("idempotencyKey"),
                crash_before_commit=bool(body.get("crashBeforeCommit")),
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(include_context=False, include_input=False),
            ) from exc
        return correction_api_payload(saved)

    @app.post("/api/matches/{match_id}/corrections/{correction_id}/recover")
    def recover_match_correction(correction_id: str, match: MatchRecord = Depends(require_match)) -> dict:
        try:
            saved = storage.recover_correction(match.id, correction_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Correction not found") from exc
        return correction_api_payload(saved)

    @app.post("/api/matches/{match_id}/corrections/{correction_id}/undo")
    def undo_match_correction(correction_id: str, match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        try:
            body = payload or {}
            saved = storage.undo_correction(match.id, correction_id,
                expected_version=body.get("expectedVersion"), base_generation=body.get("baseGeneration"),
                command_id=body.get("commandId"), idempotency_key=body.get("idempotencyKey"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Correction not found") from exc
        return correction_api_payload(saved)

    @app.get("/api/matches/{match_id}/corrections")
    def list_match_corrections(match: MatchRecord = Depends(require_match), state: str | None = None) -> dict:
        return {"items": storage.list_corrections(match.id, state=state)}

    @app.post("/api/matches/{match_id}/queries")
    def post_match_query(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return snapshot_response(match.id, lambda: storage.query_match_events(match.id, str(body.get("query") or "")), body.get("generationId"))

    @app.post("/api/matches/{match_id}/reports")
    def post_match_report(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claimedEvidenceIds")
        try:
            return storage.assemble_match_report(
                match.id,
                claimed_evidence_ids=claimed,
                narrative=body.get("narrative"),
                generation_id=body.get("generationId"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/heatmap")
    def get_match_heatmap(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.heatmap_for_match(match.id), generationId)

    @app.get("/api/matches/{match_id}/players")
    def get_match_players(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.player_observations_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/ownership")
    def get_match_ownership(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.classify_match_ownership(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/package")
    def get_match_package(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.assemble_stored_match_package(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/incidents/geometry")
    def get_match_incident_geometry(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.incident_geometry_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/setup")
    def match_setup(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.assess_stored_match_setup(match.id), generationId)

    @app.get("/api/matches/{match_id}/rates")
    def match_rates(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.four_rates_for_match(match.id)

    @app.get("/api/matches/{match_id}/metrics")
    def get_match_metrics(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.match_metrics_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/metrics/inspect/{metric}")
    def inspect_stored_metric(metric: str, match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.inspect_match_metric(match.id, metric), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/incidents/package")
    def get_match_incident_package(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.incident_package_for_match(match.id)

    @app.get("/api/matches/{match_id}/clock")
    def get_match_clock(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.clock_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/incidents/review")
    def get_match_incident_review(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.incident_review_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/privacy")
    def get_match_privacy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.dpia_for_match(match.id)

    @app.get("/api/matches/{match_id}/setup/preview")
    def get_match_setup_preview(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.preview_landmark_for_match(match.id), generationId)

    @app.post("/api/matches/{match_id}/calibration/commit")
    def commit_match_calibration(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.commit_calibration_for_match(match.id, payload or {})

    @app.post("/api/matches/{match_id}/recompute")
    def post_match_recompute(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.recompute_for_match(match.id, str(body.get("change") or "report"))

    @app.post("/api/matches/{match_id}/recompute/execute")
    def post_match_recompute_execute(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.execute_recompute(match.id, str(body.get("change") or "report")).model_dump(mode="json")

    @app.get("/api/matches/{match_id}/promotion")
    def get_match_promotion(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.promotion_receipt_for_match(match.id)

    @app.get("/api/matches/{match_id}/quality")
    def get_match_quality(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.quality_timeline_for_match(match.id), generationId)

    @app.get("/api/matches/{match_id}/identity")
    def get_match_identity(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.identity_for_match(match.id), generationId)

    @app.post("/api/matches/{match_id}/identity/repair")
    def post_match_identity_repair(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.repair_identity_for_match(match.id, payload)

    @app.post("/api/matches/{match_id}/identity/promote")
    def post_match_identity_promote(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.promote_identity_for_match(match.id, payload)

    @app.get("/api/matches/{match_id}/history")
    def get_match_history(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.history_for_match(match.id)

    @app.get("/api/matches/{match_id}/cache")
    def get_match_cache(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.cache_identity_for_match(match.id)

    @app.get("/api/matches/{match_id}/records/migrate")
    def get_match_legacy_migrate(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.migrate_legacy_for_match(match.id)

    @app.get("/api/matches/{match_id}/attack-direction")
    def get_match_attack_direction(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.attack_direction_for_match(match.id, team="my_team", period=1)

    @app.post("/api/matches/{match_id}/attack-direction")
    def post_match_attack_direction(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.attack_direction_for_match(
            match.id,
            team=str(body.get("team") or "my_team"),
            period=int(body.get("period") or 1),
        )

    @app.get("/api/matches/{match_id}/calibration")
    def get_match_calibration(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.calibration_for_match(match.id)

    @app.post("/api/matches/{match_id}/calibration")
    def post_match_calibration(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.calibration_for_match(match.id, payload)

    @app.get("/api/matches/{match_id}/formation")
    def get_match_formation(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.formation_for_match(match.id), generationId)

    @app.get("/api/matches/{match_id}/events/partition")
    def get_match_event_partition(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.partition_events_for_match(match.id)

    @app.get("/api/matches/{match_id}/reports/provenance")
    def get_match_report_provenance(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.provenance_for_match(match.id)

    @app.get("/api/matches/{match_id}/reports/coverage")
    def get_match_report_coverage(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.coverage_for_match(match.id), generationId)

    @app.get("/api/matches/{match_id}/shots/quality")
    def get_match_shot_quality(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_quality_for_match(match.id)

    @app.get("/api/matches/{match_id}/media/proxy")
    def get_match_proxy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.proxy_assets_for_match(match.id)

    @app.get("/api/matches/{match_id}/edits")
    def get_match_edits(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return storage.edit_list_for_match(match.id, generation_id=generationId)

    @app.post("/api/matches/{match_id}/edits/render")
    def post_match_edit_render(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.render_edit_for_match(
            match.id,
            start=float(body.get("start") or 0.0),
            end=float(body.get("end") or 0.0),
            generation_id=body.get("generationId"),
        )

    @app.get("/api/matches/{match_id}/tracklets")
    def get_match_tracklets(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.tracklets_for_match(match.id)

    @app.get("/api/matches/{match_id}/geometry/distance")
    def get_match_derived_distance(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.derived_distance_for_match(match.id), generationId)

    @app.get("/api/matches/{match_id}/shots/features")
    def get_match_shot_features(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_features_for_match(match.id)

    @app.post("/api/matches/{match_id}/recovery/import")
    def post_match_corrupted_import(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.corrupted_import_for_match(match.id, str(body.get("actualSha256") or ""))

    @app.post("/api/matches/{match_id}/assistance/report")
    def post_match_assistance_report(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claimedEvidenceIds")
        try:
            return storage.assemble_match_report(
                match.id,
                claimed_evidence_ids=claimed,
                narrative=body.get("narrative"),
                generation_id=body.get("generationId"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/events")
    def get_events(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                response = MatchEventsResponse(matchId=match.id, events=storage.load_events(match.id))
                return {**response.model_dump(mode="json"), "generationId": ref.generationId}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc

    def snapshot_csv(match: MatchRecord, generation_id: str | None, kind: str) -> Response:
        try:
            with storage.generation_snapshot(match.id, generation_id=generation_id) as ref:
                if kind == "frames":
                    rows, fields = flatten_frames_for_csv(storage.load_frames(match.id)), FRAME_CSV_FIELDS
                elif kind == "events":
                    rows, fields = flatten_events_for_csv(storage.load_events(match.id)), EVENT_CSV_FIELDS
                else:
                    summary, _, _, _ = storage.load_analytics(match.id)
                    rows, fields = flatten_metrics_for_csv(summary.metricAvailability), METRIC_CSV_FIELDS
                csv_payload = render_csv(rows, fields)
                return Response(content=csv_payload, media_type="text/csv", headers={
                    "Content-Disposition": f'attachment; filename="{match.id}-{kind}.csv"',
                    "X-Generation-Id": ref.generationId})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @app.get("/api/matches/{match_id}/export/frames.csv")
    def export_frames_csv(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> Response:
        return snapshot_csv(match, generationId, "frames")

    @app.get("/api/matches/{match_id}/export/events.csv")
    def export_events_csv(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> Response:
        return snapshot_csv(match, generationId, "events")

    @app.get("/api/matches/{match_id}/export/metrics.csv")
    def export_metrics_csv(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> Response:
        return snapshot_csv(match, generationId, "metrics")

    @app.get("/api/matches/{match_id}/export/match.json")
    def export_match_json(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return build_match_bundle(storage, match.id, generation_id=generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @app.get("/api/matches/{match_id}/reports")
    def get_generation_reports(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        from .report_store import ReportStore
        try:
            return ReportStore(storage).view(match.id, generation_id=generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Reports not ready") from exc

    @app.get("/api/matches/{match_id}/reports/legacy/{task_type}")
    def get_legacy_report(task_type: str, match: MatchRecord = Depends(require_match)) -> dict:
        from .report_store import ReportStore
        try:
            return ReportStore(storage).legacy(match.id, task_type)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Legacy report unavailable") from exc

    @app.post("/api/matches/{match_id}/analysis/{analysis_type}")
    def analyze_match(analysis_type: str, match: MatchRecord = Depends(require_match), body: dict | None = None) -> dict:
        match_id = match.id
        body = body or {}
        if analysis_type in {"offside", "spacing"}:
            return storage.incident_geometry_for_match(match_id)
        try:
            result = provider_gateway.execute(
                match_id,
                analysis_type,
                requested_provider=body.get("provider"),
                body=body,
            )
        except (StaleGeneration, GenerationRecoveryRequired):
            raise
        except ProviderDenied as exc:
            raise HTTPException(status_code=403, detail={"reasonCodes": exc.reason_codes}) from exc
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return result

    @app.get("/api/matches/{match_id}/report/html")
    def get_match_report_html(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> HTMLResponse:
        from .report_store import ReportStore
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as generation:
                summary, _, formation_timeline, shots = storage.load_analytics(match.id)
                events = storage.load_events(match.id)
                view = ReportStore(storage).view(match.id, generation_id=generation.generationId)
                reports = view["reports"]
                html = build_match_report_export(
                    match=storage.get_match(match.id), summary=summary, formation_timeline=formation_timeline,
                    shots=shots, events=events,
                    tactical_report=reports.get("tactical_report", {}).get("payload"),
                    drills=reports.get("drills", {}).get("payload"), report_context=view)
                return HTMLResponse(content=html, headers={"X-Generation-Id": generation.generationId})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/benchmark")
    def get_match_benchmark(match: MatchRecord = Depends(require_match), includeSelectedClusterProbe: bool = False,
                            generationId: str | None = None) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                summary = summarize_match_benchmark(storage, match.id)
                from .run_benchmarks import build_snapshot_cluster_payload
                response = summary.model_dump(mode="json") if not includeSelectedClusterProbe else {
                    "saved": summary.model_dump(mode="json"),
                    **build_snapshot_cluster_payload(summary, storage.get_match(match.id))}
                return {**response, "matchId": match.id, "generationId": ref.generationId,
                        "diagnosticProvenance": "flat_diagnostics_unverified_source_binding"}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not ready") from exc

    @app.patch("/api/matches/{match_id}/config")
    def update_match_config(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        from .review_service import ReviewService
        try:
            _config, command = ReviewService(storage).configure(match.id, payload or {})
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="Required match artifacts are not available for reprocessing.") from exc
        if command is not None and command.appliedGeneration is not None:
            with storage.generation_snapshot(match.id, generation_id=command.appliedGeneration):
                response = storage.get_match(match.id).model_dump(mode="json")
            response["correction"] = correction_api_payload(command)
            response["generationId"] = command.appliedGeneration
            return response
        response = storage.get_match(match.id).model_dump(mode="json")
        if command is not None:
            response["correction"] = correction_api_payload(command)
            response["generationId"] = None
        return response

    @app.websocket("/ws/jobs/{job_id}")
    async def job_updates(websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        last_payload = None
        try:
            while True:
                try:
                    payload = (await run_in_threadpool(storage.get_job, job_id)).model_dump(mode="json")
                    payload = attach_durable_job_view(payload, storage.job_ledger)
                except KeyError:
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    return
                if payload != last_payload:
                    await websocket.send_json(payload)
                    last_payload = payload
                ledger_status = payload.get("ledgerStatus")
                if (
                    ledger_status in {"complete", "failed", "cancelled"}
                    or ledger_status is None
                    and payload["status"] in {"completed", "complete", "failed", "cancelled"}
                ):
                    await websocket.close()
                    return
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if message["type"] == "websocket.disconnect":
                    return
        except WebSocketDisconnect:
            return

    # ===== Review Bundles / Playlists =====

    @app.get("/api/bundles")
    def list_bundles(tags: str | None = None) -> list[dict]:
        """List all bundles, optionally filtered by tags (comma-separated)."""
        tag_list = tags.split(",") if tags else None
        return [b.model_dump(mode="json") for b in storage.list_review_bundles(tag_list)]

    @app.get("/api/bundles/{bundle_id}")
    def get_bundle(bundle_id: str) -> dict:
        """Get a single bundle by ID."""
        try:
            return storage.get_review_bundle(bundle_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Bundle not found") from exc

    @app.post("/api/bundles", status_code=201)
    def create_bundle(request: CreateBundleRequest) -> dict:
        """Create a new review bundle/playlist."""
        items = [ReviewBundleItem.model_validate(item) for item in request.items]
        bundle = storage.create_review_bundle(
            name=request.name,
            description=request.description,
            items=items,
            tags=request.tags,
        )
        return bundle.model_dump(mode="json")

    @app.put("/api/bundles/{bundle_id}")
    def update_bundle(bundle_id: str, request: UpdateBundleRequest) -> dict:
        """Update an existing bundle."""
        items = [ReviewBundleItem.model_validate(item) for item in request.items] if request.items is not None else None
        try:
            bundle = storage.update_review_bundle(
                bundle_id,
                name=request.name,
                description=request.description,
                items=items,
                tags=request.tags,
            )
            return bundle.model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Bundle not found") from exc

    @app.delete("/api/bundles/{bundle_id}", status_code=204)
    def delete_bundle(bundle_id: str) -> None:
        """Delete a bundle."""
        try:
            storage.delete_review_bundle(bundle_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Bundle not found") from exc

    # ===== Annotations & Issues =====

    @app.get("/api/matches/{match_id}/annotations")
    def list_annotations(match: MatchRecord = Depends(require_match)) -> dict:
        """List all annotations for a match."""
        annotations = storage.list_annotations(match.id)
        return {"matchId": match.id, "annotations": [a.model_dump(mode="json") for a in annotations]}

    @app.post("/api/matches/{match_id}/annotations", status_code=201)
    def create_annotation(request: CreateAnnotationRequest, match: MatchRecord = Depends(require_match)) -> dict:
        """Create a new annotation on a match."""
        record = storage.create_annotation(match.id, request)
        return record.model_dump(mode="json")

    @app.delete("/api/matches/{match_id}/annotations/{annotation_id}", status_code=204)
    def delete_annotation(annotation_id: str, match: MatchRecord = Depends(require_match)) -> None:
        """Delete an annotation."""
        try:
            storage.delete_annotation(match.id, annotation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @app.get("/api/matches/{match_id}/issues")
    def list_issues(match: MatchRecord = Depends(require_match)) -> dict:
        """List all issues for a match."""
        issues = storage.list_issues(match.id)
        return {"matchId": match.id, "issues": [i.model_dump(mode="json") for i in issues]}

    @app.post("/api/matches/{match_id}/issues", status_code=201)
    def create_issue(request: CreateIssueRequest, match: MatchRecord = Depends(require_match)) -> dict:
        """Create a new issue on a match."""
        record = storage.create_issue(match.id, request)
        return record.model_dump(mode="json")

    @app.delete("/api/matches/{match_id}/issues/{issue_id}", status_code=204)
    def delete_issue(issue_id: str, match: MatchRecord = Depends(require_match)) -> None:
        """Delete an issue."""
        try:
            storage.delete_issue(match.id, issue_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @app.get("/api/matches/{match_id}/trust-crops")
    def get_trust_crops(match: MatchRecord = Depends(require_match), limit: int = 20) -> dict:
        """Compute heuristic-based trust crop queue for a match.

        Frames are scored by uncertainty: ball teleport distance,
        track ID switch frequency, team flip rate, possession gaps.
        """
        try:
            frames = storage.load_frames(match.id)
            _summary, assignments, _, _ = storage.load_analytics(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames or analytics not ready") from exc

        frames_dicts = [f.model_dump() for f in frames]
        assignments_dicts = [a.model_dump() for a in assignments]
        crops = compute_trust_crops(frames_dicts, assignments_dicts, max_crops=limit)
        response = TrustCropsResponse(
            matchId=match.id,
            crops=[TrustCropSchema(
                frameStart=crop.frameStart,
                frameEnd=crop.frameEnd,
                timestampStart=crop.timestampStart,
                timestampEnd=crop.timestampEnd,
                score=crop.score,
                reasons=crop.reasons,
            ) for crop in crops],
            totalFrames=len(frames),
        )
        return response.model_dump(mode="json")

    # ===== Dashboard =====

    @app.get("/api/aggregate/dashboard")
    def get_dashboard() -> dict:
        """Aggregate stats across all completed matches."""
        all_matches = storage.list_matches_with_analytics()
        if not all_matches:
            empty = DashboardResponse(
                summary=DashboardSummary(
                    matchCount=0, avgPossession=None, avgMyTeamXg=None, avgEnemyXg=None,
                    avgXgDiff=None, avgMyTeamSprints=None, avgEnemySprints=None,
                    mostUsedFormation=None,
                ),
            )
            return empty.model_dump(mode="json")

        summaries = [m["summary"] for m in all_matches]
        measured_possession = [s["possession"] for s in summaries if s.get("possession") is not None]
        avg_pos = sum(measured_possession) / len(measured_possession) if measured_possession else None
        avg_my_xg = _dashboard_average(summaries, field="myTeamXg", metric="my_team_experimental_shot_quality_sum", digits=2)
        avg_enemy_xg = _dashboard_average(summaries, field="enemyXg", metric="enemy_experimental_shot_quality_sum", digits=2)
        avg_xg_diff = None if avg_my_xg is None or avg_enemy_xg is None else round(avg_my_xg - avg_enemy_xg, 2)
        avg_my_sprints = _dashboard_average(summaries, field="myTeamSprints", metric="my_team_sprints")
        avg_enemy_sprints = _dashboard_average(summaries, field="enemySprints", metric="enemy_sprints")

        from collections import Counter
        formations = [s.get("formation") for s in summaries if s.get("formation") and s.get("formation") != "-"]
        most_used = Counter(formations).most_common(1)[0][0] if formations else None

        summary = DashboardSummary(
            matchCount=len(summaries),
            avgPossession=round(avg_pos, 1) if avg_pos is not None else None,
            avgMyTeamXg=avg_my_xg,
            avgEnemyXg=avg_enemy_xg,
            avgXgDiff=avg_xg_diff,
            avgMyTeamSprints=avg_my_sprints,
            avgEnemySprints=avg_enemy_sprints,
            mostUsedFormation=most_used,
        )

        # Season trends — one point per match
        sorted_matches = sorted(all_matches, key=lambda m: m["createdAt"])
        from .schemas import MatchSummary as MSS
        trends = [
            SeasonTrendPoint(
                matchId=m["matchId"],
                name=m["matchName"],
                date=m["createdAt"],
                summary=MSS.model_validate(m["summary"]),
            )
            for m in sorted_matches
        ]

        # Comparison delta between last 2 matches
        last_two = sorted(all_matches, key=lambda m: m["createdAt"], reverse=True)[:2]
        comparison = None
        if len(last_two) == 2:
            latest, previous = last_two[0], last_two[1]
            s_latest = latest["summary"]
            s_prev = previous["summary"]
            comparison = DashboardComparison(
                latestMatchId=latest["matchId"],
                latestMatchName=latest["matchName"],
                previousMatchId=previous["matchId"],
                previousMatchName=previous["matchName"],
                possessionDelta=(
                    round(s_latest["possession"] - s_prev["possession"], 1)
                    if s_latest.get("possession") is not None and s_prev.get("possession") is not None
                    else None
                ),
                xgDiffDelta=(
                    round(latest_balance - previous_balance, 2)
                    if (latest_balance := _xg_balance(s_latest)) is not None
                    and (previous_balance := _xg_balance(s_prev)) is not None
                    else None
                ),
                myTeamSprintsDelta=_dashboard_difference(
                    s_latest, s_prev, field="myTeamSprints", metric="my_team_sprints",
                ),
                enemySprintsDelta=_dashboard_difference(
                    s_latest, s_prev, field="enemySprints", metric="enemy_sprints",
                ),
            )

        response = DashboardResponse(
            summary=summary,
            comparison=comparison,
            opponentRollups=[],
            playerTrendSnapshots=[],
            trends=trends,
        )
        return response.model_dump(mode="json")

    # ===== Semantic Search / Tactical Theme Search =====

    @app.get("/api/search/matches")
    def search_matches(
        q: str,
        limit: int = 10,
        match_ids: str | None = None,
    ) -> dict:
        """Search matches by tactical themes using natural language.
        
        Args:
            q: Natural language search query (e.g., "high press counter-attacks")
            limit: Maximum number of results (default 10, max 50)
            match_ids: Optional comma-separated list of match IDs to search
        
        Returns:
            Semantic search results with relevance scores and matched themes
        """
        limit = min(max(1, limit), 50)
        match_id_list = match_ids.split(",") if match_ids else None
        
        # Get all matches with analytics
        all_matches = storage.list_matches_with_analytics()
        
        # Filter by specific match IDs if provided
        if match_id_list:
            all_matches = [m for m in all_matches if m["matchId"] in match_id_list]
        
        if not all_matches:
            return {
                "query": q,
                "results": [],
                "totalMatches": 0,
                "searchMetadata": {
                    "availableMatches": 0,
                    "filtersApplied": bool(match_ids),
                },
            }
        
        # Perform semantic search
        results = search_matches_by_tactical_themes(q, all_matches)
        
        # Apply limit
        results = results[:limit]
        
        return {
            "query": q,
            "results": results,
            "totalMatches": len(results),
            "searchMetadata": {
                "availableMatches": len(all_matches),
                "filtersApplied": bool(match_ids),
            },
        }

    @app.get("/api/search/bundles")
    def search_bundles(q: str, limit: int = 10) -> dict:
        """Search bundles by tactical themes using natural language.
        
        Args:
            q: Natural language search query (e.g., "counter-attack wing play")
            limit: Maximum number of results (default 10, max 50)
        
        Returns:
            Bundle search results with relevance scores and matched themes
        """
        limit = min(max(1, limit), 50)
        bundles = storage.list_review_bundles()
        results = search_bundles_by_tactical_themes(q, bundles)
        results = results[:limit]
        
        return {
            "query": q,
            "results": results,
            "totalMatches": len(results),
        }

    @app.get("/api/matches/{match_id}/themes")
    def get_match_themes(match: MatchRecord = Depends(require_match)) -> dict:
        """Get detected tactical themes for a specific match.
        
        Returns:
            Match with detected tactical themes and strength scores
        """
        try:
            summary, _, _, _ = storage.load_analytics(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        
        theme_data = detect_themes_for_match(summary.model_dump(mode="json"))
        
        return {
            "matchId": match.id,
            **theme_data,
        }

    @app.get("/api/search/tactical-themes")
    def list_tactical_themes() -> dict:
        """List available tactical themes for search.
        
        Returns:
            Dictionary of available tactical themes with descriptions
        """
        from .semantic_search import TACTICAL_KEYWORDS
        
        theme_descriptions = {
            "high_press": "Aggressive pressing in the opponent's half, often triggering counter-attacks",
            "low_block": "Deep defensive shape, compact and organized around the penalty area",
            "mid_block": "Balanced defensive shape in the middle third",
            "counter_attack": "Fast transitions after winning possession, bypassing midfield",
            "possession_based": "High possession, patient build-up play from the back",
            "direct_play": "Long balls and vertical passing to bypass midfield",
            "wing_play": "Attacks through the flanks with crosses from wide positions",
            "through_balls": "Vertical passes breaking the defensive line",
            "defensive_transition": "Regaining defensive shape after losing possession",
            "offensive_transition": "Quick attack after winning possession high up",
            "deep_defense": "Very low defensive line, protecting the goal closely",
            "aggressive_press": "Intense man-to-man pressing, hunting in groups",
            "passive_press": "Soft containment, waiting for the opponent to make mistakes",
        }
        
        return {
            "themes": [
                {
                    "id": theme_id,
                    "description": theme_descriptions.get(theme_id, ""),
                    "keywords": TACTICAL_KEYWORDS.get(theme_id, [])[:5],  # Top 5 keywords
                }
                for theme_id in TACTICAL_KEYWORDS
            ]
        }

    if settings.deployment_mode == "local":
        _retire_default_frontend_routes(app)
    return app


app = create_app()
