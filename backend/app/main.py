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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .jobs import JobDispatchError, JobRunner
from .job_routes import create_job_router
from .match_ingest_routes import create_match_ingest_router
from .match_runtime_routes import create_match_runtime_router
from .system_routes import create_system_router
from .match_detail_routes import create_match_detail_router
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
from .review_routes import create_review_router
from .artifact_routes import create_artifact_router
from .insight_routes import (
    _dashboard_average,
    _dashboard_difference,
    _dashboard_metric_value,
    _xg_balance,
    create_insight_router,
)
from .generations import StaleGeneration, GenerationRecoveryRequired
from .settings import ProcessingSettings, SettingsError, canonicalize_origin
from .trust_crops import compute_trust_crops
from .schemas import (
    CreateAnnotationRequest,
    CreateBundleRequest,
    CreateIssueRequest,
    MatchAnalyticsResponse,
    MatchConfig,
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
from .workbench.leftover_support import (
    EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR,
    EXTERNAL_BENCHMARK_UI_BINDING_DIR,
    EXTERNAL_SOCCERNET_UI_BINDING_DIR,
    EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR,
    EXTERNAL_SOCCERTRACK_UI_BINDING_DIR,
    VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_BOUNDED_NEXT_SAMPLE_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR,
    VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR,
    VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR,
    VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR,
    VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_REAL_VIDEO_SCALEOUT_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR,
    _as_box,
    _as_bytes,
    _as_detection,
    _as_label,
    _challenger_adapters_view,
    _decoder_challengers_view,
    _fixture_frame_source,
    _four_rates_view,
    _legacy_geometry,
    _legacy_geometry_profile,
    _production_decode_frames,
    _production_job_request,
    _stale_permissions_view,
    _unmeasured_landmark_preview,
    _unpromoted_receipt,
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
            storage.job_ledger.db_path,
            settings.provider_budget_limit,
            legacy_path=storage.storage_root / "provider-budget.sqlite3",
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

    app.include_router(create_match_ingest_router(storage, runner, settings))

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

    app.include_router(create_job_router(storage, runner, require_match))
    app.include_router(create_system_router(storage))

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

    app.include_router(create_match_runtime_router(storage, settings, require_match, snapshot_response))
    app.include_router(create_match_detail_router(storage, require_match, snapshot_response, provider_gateway))

    app.include_router(create_review_router(storage, require_match))
    app.include_router(create_insight_router(storage, require_match))
    app.include_router(create_artifact_router(storage, require_match, build_match_bundle))

    if settings.deployment_mode == "local":
        _retire_default_frontend_routes(app)
    return app


app = create_app()
